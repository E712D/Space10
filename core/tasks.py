from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from persistence.models import Season, ModelVersion, PredictionReport
from kombu import Connection
from core.agronomy.ml_predictor import SeasonalClimatePredictor


@shared_task
def run_model_retraining_task(model_id):
    """
    Tâche de fond asynchrone pour exécuter le réentraînement réel du modèle climatique ML.
    """
    try:
        model_version = ModelVersion.objects.get(pk=model_id)
        model_version.metrics = {"status": "training_in_progress", "r2_score": None}
        model_version.save()

        # Lancement de l'entraînement réel via scikit-learn
        predictor = SeasonalClimatePredictor()
        result = predictor.train()

        if result.get("status") == "success":
            # Mise à jour avec les vraies métriques du modèle entraîné
            model_version.file_path = predictor.model_path
            model_version.metrics = {
                "status": "completed", 
                "r2_score": result["r2_score"],
                "samples_trained": result["samples_trained"]
            }
            model_version.is_active = True
            model_version.save()
            
            return f"Modèle climatique {model_version.version_tag} réentraîné avec succès. Score R2: {result['r2_score']}"
        else:
            # Gestion du cas où il n'y a pas encore assez de données historiques
            reason = result.get("message", "Données insuffisantes")
            model_version.metrics = {"status": "failed_insufficient_data", "reason": reason}
            model_version.save()
            return f"Réentraînement ignoré : {reason}"

    except ModelVersion.DoesNotExist:
        return f"ModelVersion avec l'ID {model_id} introuvable."
    except Exception as e:
        return f"Erreur lors du réentraînement du modèle : {str(e)}"


@shared_task
def check_season_milestones():
    """
    Tâche planifiée quotidienne (via Celery Beat) :
    1. Verrouille automatiquement les saisons 10 jours avant leur fin.
    2. Clôture et lance le réentraînement automatique le jour exact de la fin de la saison.
    """
    today = timezone.now().date()
    
    # --- JALON 1 : Verrouillage automatique (10 jours avant la fin) ---
    target_lock_date = today + timedelta(days=10)
    seasons_to_lock = Season.objects.filter(end_date=target_lock_date, status="open")
    
    for season in seasons_to_lock:
        season.status = "locked"
        if hasattr(season, 'is_locked'):
            season.is_locked = True
        season.save()
        
        # Fige un rapport prédictif de sécurité à cette date
        reference_date = season.lock_date or today
        weather_records = season.plot.weather_records.filter(obs_date__lte=reference_date)
        accumulated_precip = sum([w.precip_mm or 0 for w in weather_records])
        record_count = weather_records.count()
        avg_temp = (
            sum([(w.temp_max_c or 0) + (w.temp_min_c or 0) for w in weather_records]) / (2 * record_count)
            if record_count > 0 else 0.0
        )
        
        features_snapshot = {
            "locked_at": str(timezone.now()),
            "lock_date": str(reference_date),
            "accumulated_precip_mm": round(accumulated_precip, 2),
            "average_temperature_c": round(avg_temp, 2),
            "weather_records_analyzed": record_count,
        }
        PredictionReport.objects.update_or_create(
            season=season,
            defaults={
                'plot': season.plot,
                'features_snapshot': features_snapshot,
                'recommendations_snapshot': {"status": "frozen_10d_before_end", "season_label": season.label}
            }
        )

    # --- JALON 2 : Clôture et réentraînement automatique (Le jour J de la fin) ---
    seasons_to_close = Season.objects.filter(end_date=today).exclude(status="closed")
    
    for season in seasons_to_close:
        season.status = "closed"
        season.is_locked = True
        season.save()
        
        # Création de la version de modèle pour l'apprentissage post-saison
        new_tag = f"v_auto_retrained_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
        model_version = ModelVersion.objects.create(
            version_tag=new_tag,
            file_path=f"models/weights/{new_tag}.joblib",
            metrics={"status": "queued_auto_from_season_end", "season_closed": season.id},
            is_active=False
        )
        
        # Déclenchement sécurisé de la tâche Celery (anti-bug Python 3.14)
        try:
            with Connection('redis://127.0.0.1:6379/0', transport='redis') as conn:
                run_model_retraining_task.apply_async(args=[model_version.id], connection=conn)
        except Exception as e:
            pass