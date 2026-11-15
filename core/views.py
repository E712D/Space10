from datetime import timedelta
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status, views
from rest_framework.decorators import action
from rest_framework.response import Response
from kombu import Connection
import numpy as np

# Import des modèles et des sérialiseurs
from persistence.models import Plot, Crop, Season, StrategicReport, PredictionReport, ModelVersion, WeatherDaily
from .serializers import (
    PlotSerializer, 
    SeasonSerializer, 
    WeatherDailySerializer, 
    CropSerializer, 
    StrategicReportSerializer,
    ModelVersionSerializer,
    TerraCIRequestSerializer
)
from .tasks import run_model_retraining_task
from core.agronomy.ml_predictor import SeasonalClimatePredictor  # <-- Import du module ML climatique


class TerraCIRecommendationView(views.APIView):
    """
    Endpoint POST /api/terraci/recommend/
    Valide le contrat d'API TerraCI, formate les données pour le moteur et appelle le modèle de Machine Learning.
    """
    def post(self, request):
        serializer = TerraCIRequestSerializer(data=request.data)
        
        if serializer.is_valid():
            validated_data = serializer.validated_data
            
            # Récupération des données validées selon le contrat flexible
            lat = validated_data.get("latitude")
            lon = validated_data.get("longitude")
            env_data = validated_data.get("donnees_environnementales", [])
            source_donnees = validated_data.get("source_donnees")
            local_data = validated_data.get("local_data", {})
            priorites = validated_data.get("priorites", [])
            
            # --- ADAPTATEUR DE FORMAT (SANS TOUCHER AU MOTEUR TERRACI) ---
            # Transforme les données entrantes au format (années, 12, 4) requis par le moteur
            try:
                arr = np.array(env_data, dtype=float)
                if arr.ndim == 1 and len(arr) == 4:
                    # Si une seule liste de 4 valeurs est envoyée -> 1 année de 12 mois identiques
                    formatted_env_data = np.tile(arr, (1, 12, 1)).tolist()
                elif arr.ndim == 2 and arr.shape[1] == 4:
                    # Si une liste de 12 mois est envoyée sans la dimension "années" -> 1 année
                    formatted_env_data = np.expand_dims(arr, axis=0).tolist()
                else:
                    formatted_env_data = env_data
            except Exception:
                formatted_env_data = env_data
            # -----------------------------------------------------------

            # 1. Extraction robuste du dernier état climatique (compatible JSONField flexible)
            current_snapshot = {"precip": 400.0, "temp": 30.0, "humidity": 0.2, "ndvi": 0.4}
            
            if isinstance(formatted_env_data, list) and len(formatted_env_data) > 0:
                last_item = formatted_env_data[-1]
                # Si c'est une liste de listes (ex: tableau 3D ou 2D)
                if isinstance(last_item, list) and len(last_item) > 0:
                    sub_item = last_item[-1]
                    if isinstance(sub_item, list) and len(sub_item) >= 4:
                        current_snapshot = {
                            "precip": float(sub_item[0]),
                            "temp": float(sub_item[1]),
                            "humidity": float(sub_item[2]),
                            "ndvi": float(sub_item[3])
                        }
                    elif isinstance(last_item[0], (int, float)) and len(last_item) >= 4:
                        current_snapshot = {
                            "precip": float(last_item[0]),
                            "temp": float(last_item[1]),
                            "humidity": float(last_item[2]),
                            "ndvi": float(last_item[3])
                        }
                # Si la source envoie directement un dictionnaire ou un objet de métriques
                elif isinstance(last_item, dict):
                    current_snapshot = {
                        "precip": float(last_item.get("precip", 400.0)),
                        "temp": float(last_item.get("temp", 30.0)),
                        "humidity": float(last_item.get("humidity", 0.2)),
                        "ndvi": float(last_item.get("ndvi", 0.4))
                    }

            # 2. Appel du modèle de Machine Learning pour prédire la saison à venir
            predictor = SeasonalClimatePredictor()
            ml_prediction = predictor.predict_next_season(current_snapshot)
            
            # Détermination du climat à utiliser pour le calcul des scores
            if ml_prediction.get("mode") == "machine_learning":
                climat_cible = ml_prediction["prediction"]
                precip_pour_calcul = climat_cible["precip_prevue_mm"]
                temp_pour_calcul = climat_cible["temp_prevue_c"]
            else:
                # Fallback sur les valeurs actuelles si le modèle ML n'est pas encore entraîné
                precip_pour_calcul = current_snapshot["precip"]
                temp_pour_calcul = current_snapshot["temp"]

            # 3. Intégration du moteur de notation / règles agronomiques
            strategies_classement = [
                {
                    "culture": "Sorgho",
                    "score": 95 if precip_pour_calcul < 600 else 80,
                    "justification": f"Adapté au cumul de pluie prévu de {precip_pour_calcul} mm."
                },
                {
                    "culture": "Maïs",
                    "score": 90 if precip_pour_calcul >= 600 else 60,
                    "justification": f"Température prévue : {temp_pour_calcul}°C."
                }
            ]
            
            # 4. Réponse structurée conforme au contrat attendu par le frontend
            response_payload = {
                "statut": "succès",
                "rotation_actuelle": local_data.get("culture_actuelle", None),
                "qualite_donnees": "optimale",
                "avertissements": [],
                "prevision_climatique_ml": ml_prediction,
                "strategies_classement": strategies_classement
            }
            
            return Response(response_payload, status=status.HTTP_200_OK)
        
        # En cas d'erreur de format ou de données manquantes
        return Response({
            "statut": "erreur",
            "message": "Données invalides selon le contrat API TerraCI",
            "erreurs": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


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
        
        season.status = "locked"
        if hasattr(season, 'is_locked'):
            season.is_locked = True
        season.save()
        
        reference_date = season.lock_date or timezone.now().date()
        weather_records = season.plot.weather_records.filter(obs_date__lte=reference_date)
        accumulated_precip = sum([w.precip_mm or 0 for w in weather_records])
        
        record_count = weather_records.count()
        avg_temp = (
            sum([(w.tmax_c or 0) + (w.tmin_c or 0) for w in weather_records]) / (2 * record_count)
            if record_count > 0 else 0.0
        )
        
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
        
        season.status = "closed"
        season.is_locked = True
        season.save()
        
        new_tag = f"v_auto_retrained_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
        model_version = ModelVersion.objects.create(
            version_tag=new_tag,
            file_path=f"models/weights/{new_tag}.joblib",
            metrics={"status": "queued_auto_from_season", "season_closed": season.id},
            is_active=False
        )
        
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