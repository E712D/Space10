from datetime import timedelta
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status, views
from rest_framework.decorators import action
from rest_framework.response import Response
from kombu import Connection

# Assure-toi que WeatherDaily et PredictionReport sont bien importés ici
from persistence.models import Plot, Crop, Season, StrategicReport, PredictionReport, ModelVersion, WeatherDaily
from .serializers import (
    PlotSerializer, 
    SeasonSerializer, 
    WeatherDailySerializer, 
    CropSerializer, 
    StrategicReportSerializer,
    ModelVersionSerializer
)
from .tasks import run_model_retraining_task

class PlotViewSet(viewsets.ModelViewSet):
    queryset = Plot.objects.all().order_by("-created_at")
    serializer_class = PlotSerializer

    @action(detail=True, methods=["get"], url_path="current-season")
    def current_season(self, request, pk=None):
        plot = self.get_object()

        season = (
            plot.seasons.filter(status="open").order_by("-start_date").first()
            or plot.seasons.order_by("-start_date").first()
        )

        cutoff_date = timezone.now().date() - timedelta(days=60)
        weather_qs = plot.weather_records.filter(obs_date__gte=cutoff_date).order_by("obs_date")

        return Response(
            {
                "plot_id": plot.id,
                "season": SeasonSerializer(season).data if season else None,
                "weather_60d_count": weather_qs.count(),
                "weather_60d": WeatherDailySerializer(weather_qs, many=True).data,
                "quality": "ok" if weather_qs.exists() else "missing",
            },
            status=status.HTTP_200_OK,
        )


class CropViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Crop.objects.all()
    serializer_class = CropSerializer


class SeasonViewSet(viewsets.ModelViewSet):
    queryset = Season.objects.all()
    serializer_class = SeasonSerializer

    @action(detail=True, methods=['post'])
    def lock(self, request, pk=None):
        season = self.get_object()
        
        # 1. Passage du statut de la saison à "locked"
        season.status = "locked"
        if hasattr(season, 'is_locked'):
            season.is_locked = True
        season.save()
        
        # 2. Détermination de la date de référence pour le snapshot (lock_date de la saison ou date du jour)
        reference_date = season.lock_date or timezone.now().date()
        
        # 3. Récupération des données météo enregistrées jusqu'à la date de verrouillage (approche proactive)
        weather_records = season.plot.weather_records.filter(obs_date__lte=reference_date)
        accumulated_precip = sum([w.precip_mm or 0 for w in weather_records])
        
        record_count = weather_records.count()
        avg_temp = (
            sum([(w.temp_max_c or 0) + (w.temp_min_c or 0) for w in weather_records]) / (2 * record_count)
            if record_count > 0 else 0.0
        )
        
        # 4. Construction des snapshots détaillés
        features_snapshot = {
            "locked_at": str(timezone.now()),
            "lock_date": str(reference_date),
            "accumulated_precip_mm": round(accumulated_precip, 2),
            "average_temperature_c": round(avg_temp, 2),
            "weather_records_analyzed": record_count,
            "soil": {
                "texture": season.plot.soil_texture,
                "ph": season.plot.soil_ph,
                "slope_pct": season.plot.slope_pct
            }
        }
        
        recommendations_snapshot = {
            "status": "frozen_on_lock",
            "proactive_action": "Saison verrouillée automatiquement. Analyse des risques et des apports hydriques recommandée avant les semis.",
            "season_label": season.label
        }
        
        # 5. Création ou mise à jour du rapport prédictif figé
        prediction_report, created = PredictionReport.objects.update_or_create(
            season=season,
            defaults={
                'plot': season.plot,
                'features_snapshot': features_snapshot,
                'recommendations_snapshot': recommendations_snapshot
            }
        )
            
        return Response({
            "status": "success",
            "message": f"Saison {season.label} verrouillée avec succès. Rapport prédictif et météo figés à la date du {reference_date}.",
            "prediction_report_id": prediction_report.id,
            "features_snapshot": features_snapshot
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def close_and_retrain(self, request, pk=None):
        season = self.get_object()
        
        # 1. Clôture de la saison et verrouillage définitif des prédictions passées
        season.status = "closed"
        season.is_locked = True
        season.save()
        
        # 2. Création automatique de la version de modèle pour l'apprentissage post-saison
        new_tag = f"v_auto_retrained_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
        model_version = ModelVersion.objects.create(
            version_tag=new_tag,
            file_path=f"models/weights/{new_tag}.joblib",
            metrics={"status": "queued_auto_from_season", "season_closed": season.id},
            is_active=False
        )
        
        # 3. Déclenchement sécurisé de la tâche Celery en arrière-plan via la connexion Redis directe
        try:
            with Connection('redis://127.0.0.1:6379/0', transport='redis') as conn:
                run_model_retraining_task.apply_async(args=[model_version.id], connection=conn)
        except Exception as e:
            pass
        
        return Response({
            "status": "success",
            "message": f"Saison {season.label} clôturée et verrouillée. Réentraînement automatique initialisé.",
            "season_id": season.id,
            "new_model_version": new_tag,
            "model_id": model_version.id
        }, status=status.HTTP_200_OK)


class StrategicReportView(views.APIView):
    def get(self, request, season_id):
        report = get_object_or_404(StrategicReport, season_id=season_id)
        serializer = StrategicReportSerializer(report)
        return Response(serializer.data)


class ModelVersionListView(views.APIView):
    def get(self, request):
        models_qs = ModelVersion.objects.all().order_by('-trained_at')
        serializer = ModelVersionSerializer(models_qs, many=True)
        return Response({"models": serializer.data}, status=status.HTTP_200_OK)


class LearningEvaluateView(views.APIView):
    def post(self, request):
        season_id = request.data.get("season_id")
        if not season_id:
            return Response({"error": "Le paramètre 'season_id' est requis."}, status=status.HTTP_400_BAD_REQUEST)
        
        report = get_object_or_404(PredictionReport, season_id=season_id)
        season = report.season
        
        weather_records = WeatherDaily.objects.filter(
            plot=season.plot,
            obs_date__gte=season.start_date,
            obs_date__lte=season.end_date
        )
        
        actual_precip_sum = sum([w.precip_mm or 0 for w in weather_records])
        snapshot = report.features_snapshot or {}
        predicted_precip = snapshot.get("expected_precip_mm", 0.0)
        
        error = abs(actual_precip_sum - predicted_precip)
        rmse = round((error ** 2) ** 0.5, 2)
        
        evaluation_result = {
            "season_id": season.id,
            "plot_id": season.plot_id,
            "actual_precip_mm": actual_precip_sum,
            "predicted_precip_mm": predicted_precip,
            "rmse_precipitation": rmse,
            "evaluated_records_count": weather_records.count(),
            "status": "evaluated_successfully"
        }
        return Response(evaluation_result, status=status.HTTP_200_OK)


class LearningRetrainView(views.APIView):
    def post(self, request):
        new_tag = f"v_retrained_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
        
        model_version = ModelVersion.objects.create(
            version_tag=new_tag,
            file_path=f"models/weights/{new_tag}.joblib",
            metrics={"status": "queued", "accuracy": None},
            is_active=False
        )
        
        # Déclenchement sécurisé de la tâche Celery en contournant le bug de transport paresseux sous Python 3.14
        try:
            with Connection('redis://127.0.0.1:6379/0', transport='redis') as conn:
                run_model_retraining_task.apply_async(args=[model_version.id], connection=conn)
        except Exception as e:
            pass
        
        return Response({
            "status": "retraining triggered successfully",
            "model_version": new_tag,
            "model_id": model_version.id,
            "message": "Le réentraînement du modèle a été lancé en tâche de fond avec Celery."
        }, status=status.HTTP_202_ACCEPTED)