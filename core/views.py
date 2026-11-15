from datetime import timedelta
from datetime import date
import logging
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.db import DatabaseError, connection
from django.db.models import Q
import httpx
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
from core.services.season_calendar import current_season, next_season, season_profile, season_window
from core.services.orchestrator import Orchestrator
from core.services.ml_adapter import MlAdapter
from core.services.weather_service import WeatherService
from core.services.chatbot_orchestrator import ChatbotOrchestrator
from persistence.repositories import PlotRepository, SeasonRepository, WeatherRepository, CropRepository, ReportRepository

_clock_override = None
logger = logging.getLogger(__name__)


class HealthView(views.APIView):
    def get(self, request):
        database = "ok"
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except DatabaseError:
            database = "down"
        return Response({
            "status": "ok" if database == "ok" else "degraded",
            "database": database,
            "ml_mode": "mock" if MlAdapter().use_mock else "real",
            "model_version": getattr(MlAdapter(), "active_version", None),
            "llm_enabled": False,
        })


class ClockView(views.APIView):
    def get(self, request):
        return Response({
            "today": _clock_override or timezone.now().date(),
            "is_overridden": _clock_override is not None,
        })

    def put(self, request):
        global _clock_override
        value = request.data.get("today")
        if value is None:
            _clock_override = None
        else:
            try:
                _clock_override = date.fromisoformat(value)
            except (TypeError, ValueError):
                return Response({"error": {"code": "VALIDATION_ERROR", "message": "La date doit respecter le format YYYY-MM-DD."}}, status=status.HTTP_400_BAD_REQUEST)
        return self.get(request)


class VoiceAskView(views.APIView):
    suggestions = [
        "Quelle culture planter ?",
        "Va-t-il beaucoup pleuvoir ?",
        "Quand faut-il faire attention ?",
    ]

    def post(self, request):
        question = str(request.data.get("question", "")).strip()
        plot_id = request.data.get("plot_id")
        if not question or plot_id in (None, ""):
            return Response({"error": {"code": "VALIDATION_ERROR", "message": "La parcelle et la question sont obligatoires."}}, status=status.HTTP_400_BAD_REQUEST)
        plot = get_object_or_404(Plot, pk=plot_id)
        try:
            result = ChatbotOrchestrator(plot, question).answer()
        except (RuntimeError, ValueError) as exc:
            logger.warning("Automatic chatbot analysis failed for plot %s: %s", plot.id, exc)
            result = {
                "intent": "unknown",
                "answer_text": "Je n'ai pas pu interroger les données pour le moment. Réessayez dans quelques instants.",
                "speak_text": "Je n'ai pas pu interroger les données pour le moment. Réessayez dans quelques instants.",
                "data_missing": True,
                "llm_used": False,
                "sources": [],
                "cached": False,
            }
        result["suggestions"] = self.suggestions
        return Response(result)


class CurrentSeasonView(views.APIView):
    def get(self, request, plot_id):
        plot = get_object_or_404(Plot, pk=plot_id)
        today = timezone.now().date()
        current_label = current_season(today)
        next_label = next_season(today)

        def calendar_entry(label):
            start, end = season_window(label)
            return {
                **season_profile(label),
                "start_date": start,
                "end_date": end,
                "prediction_ready": label in set(plot.seasons.values_list("label", flat=True)),
            }

        complete_weather = (
            Q(tmax_c__isnull=False)
            | Q(precip_mm__isnull=False)
            | Q(sm_root__isnull=False)
        )
        latest = plot.weather_records.filter(complete_weather).order_by("-obs_date").first()
        if latest is None or latest.obs_date < today - timedelta(days=2):
            try:
                weather = WeatherService().fetch_daily(
                    plot.centroid.y,
                    plot.centroid.x,
                    today - timedelta(days=30),
                    today,
                )
                if not weather.empty:
                    WeatherRepository().upsert_weather_daily(plot.id, weather)
            except (httpx.HTTPError, ValueError) as exc:
                logger.warning("Automatic weather refresh failed for plot %s: %s", plot.id, exc)
        season = (
            plot.seasons.filter(status="open").order_by("-start_date").first()
            or plot.seasons.order_by("-start_date").first()
        )
        cutoff_date = timezone.now().date() - timedelta(days=30)
        weather = WeatherDailySerializer(
            plot.weather_records.filter(obs_date__gte=cutoff_date).filter(complete_weather).order_by("obs_date"),
            many=True,
        ).data
        return Response({
            "plot_id": str(plot.id),
            "season_label": season.label if season else "",
            "current_season": calendar_entry(current_label) if current_label else None,
            "next_season": calendar_entry(next_label),
            "as_of": timezone.now().date(),
            "quality": "observed" if weather else "missing",
            "precip_7d_mm": sum((item["precip_mm"] or 0) for item in weather[-7:]) if weather else None,
            "precip_30d_mm": sum((item["precip_mm"] or 0) for item in weather) if weather else None,
            "et0_7d_mm": sum((item["et0_mm"] or 0) for item in weather[-7:]) if weather else None,
            "et0_30d_mm": sum((item["et0_mm"] or 0) for item in weather) if weather else None,
            "trend": {"sm_root_7d_change": None},
            "series_30d": [{
                "date": item["obs_date"],
                "precip_mm": item["precip_mm"],
                "t2m_max_c": item["tmax_c"],
                "sm_root": item["sm_root"],
            } for item in weather],
            "alerts": [],
        })


def _value(value, quality="missing"):
    return {"value": value, "q10": None, "q90": None, "quality": quality if value is not None else "missing"}


def _analysis_contract(plot, result):
    """Translate the legacy orchestration result into the frontend API contract."""
    prediction = result.get("prediction") or {}
    summary = prediction.get("season_summary", {}).get("features", {})
    season = result["season"]
    recommendations = result.get("recommendations", [])
    scores = []
    for item in recommendations:
        rotation = item.get("rotation", [{}])
        crop_code = rotation[0].get("crop_code", "unknown")
        scores.append({
            "crop_code": crop_code,
            "name_fr": crop_code.replace("_", " ").capitalize(),
            "score": round(float(item.get("score", 0)) * 100, 1),
            "reasons": [reason.get("text_fr", "") for reason in item.get("reasons", [])],
            "penalties": [penalty.get("detail_fr", "") for penalty in item.get("penalties", [])],
        })
    if not scores:
        scores = [{
            "crop_code": "maize",
            "name_fr": "Maïs",
            "score": 0,
            "reasons": [],
            "penalties": [],
        }]
    season_summary = {
        "precip_total_mm": _value(summary.get("precip_total_mm", {}).get("value")),
        "heat_stress_days_total": _value(summary.get("heat_stress_days", {}).get("value")),
        "mean_water_stress_index": _value(summary.get("water_stress_index", {}).get("value")),
    }
    return {
        "plot_id": str(plot["plot_id"]),
        "season": {
            "season_label": season["label"],
            "profile": season_profile(season["label"]),
            "season_start": season["start_date"],
            "season_end": season["end_date"],
            "lock_date": season["lock_date"],
            "status": "locked" if result.get("locked") else "draft",
            "prediction_version": None,
        },
        "prediction": {
            "plot_id": str(plot["plot_id"]),
            "season_label": season["label"],
            "season_start": season["start_date"],
            "season_end": season["end_date"],
            "forecast_origin": date.today(),
            "model_version": "mock" if prediction.get("status") == "success" else "unknown",
            "periods": prediction.get("periods", []),
            "season_summary": season_summary,
            "critical_periods": prediction.get("critical_periods", []),
            "baseline_comparison": prediction.get("baseline_comparison", []),
            "warnings": prediction.get("warnings", []),
        },
        "recommendation": {
            "main_crop": scores[0],
            "next_crop": scores[1] if len(scores) > 1 else None,
            "top_3": scores[:3],
            "cover_crops": [],
            "warnings": [],
            "missing_info": result.get("missing_info", []),
        },
        "report": {
            "plot_id": str(plot["plot_id"]),
            "season_label": season["label"],
            "status": "locked" if result.get("locked") else "draft",
            "version": 0,
            "text_fr": "Analyse disponible. Vérifiez les informations locales avant toute décision.",
            "created_at": date.today().isoformat() + "T00:00:00Z",
            "locked_at": result.get("locked_at"),
        },
        "timings_ms": {},
    }


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

    @action(detail=True, methods=["post"], url_path="analysis")
    def analysis(self, request, pk=None):
        plot = self.get_object()
        payload = request.data if isinstance(request.data, dict) else {}
        try:
            result = Orchestrator(
                repos=type("Repositories", (), {
                    "plots": PlotRepository(),
                    "seasons": SeasonRepository(),
                    "weather": WeatherRepository(),
                    "crops": CropRepository(),
                    "reports": ReportRepository(),
                })(),
                ml_adapter=MlAdapter(),
            ).run_analysis(
                plot_id=plot.pk,
                season_label=payload.get("season_label"),
                today=date.fromisoformat(payload["today"]) if payload.get("today") else timezone.now().date(),
            )
        except ValueError as exc:
            return Response({"error": {"code": "VALIDATION_ERROR", "message": str(exc)}}, status=status.HTTP_400_BAD_REQUEST)
        except RuntimeError as exc:
            return Response({"error": {"code": "UPSTREAM_ERROR", "message": str(exc)}}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(_analysis_contract(PlotRepository().get_plot(plot.pk), result), status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="current-season")
    def current_season(self, request, pk=None):
        plot = self.get_object()

        season = (
            plot.seasons.filter(status="open").order_by("-start_date").first()
            or plot.seasons.order_by("-start_date").first()
        )

        cutoff_date = timezone.now().date() - timedelta(days=60)
        weather_qs = plot.weather_records.filter(obs_date__gte=cutoff_date).order_by("obs_date")

        weather = WeatherDailySerializer(weather_qs, many=True).data
        return Response({
            "plot_id": str(plot.id),
            "season_label": season.label if season else "",
            "as_of": timezone.now().date(),
            "quality": "observed" if weather else "missing",
            "precip_7d_mm": sum((item["precip_mm"] or 0) for item in weather[-7:]) if weather else None,
            "precip_30d_mm": sum((item["precip_mm"] or 0) for item in weather) if weather else None,
            "et0_7d_mm": sum((item["et0_mm"] or 0) for item in weather[-7:]) if weather else None,
            "et0_30d_mm": sum((item["et0_mm"] or 0) for item in weather) if weather else None,
            "trend": {"sm_root_7d_change": None},
            "series_30d": [{
                "date": item["obs_date"],
                "precip_mm": item["precip_mm"],
                "t2m_max_c": item["tmax_c"],
                "sm_root": item["sm_root"],
            } for item in weather],
            "alerts": [],
        }, status=status.HTTP_200_OK)


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
                "ph": float(season.plot.soil_ph) if season.plot.soil_ph is not None else None,
                "slope_pct": float(season.plot.slope_pct) if season.plot.slope_pct is not None else None
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


class PlotSeasonReportView(views.APIView):
    def get(self, request, plot_id, season_label):
        season = get_object_or_404(Season, plot_id=plot_id, label=season_label)
        report = PredictionReport.objects.filter(season=season).first()
        if not report:
            return Response({"error": {"code": "NOT_FOUND", "message": "Aucun bilan pour cette saison."}}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            "plot_id": str(plot_id),
            "season_label": season.label,
            "status": season.status,
            "version": 0,
            "text_fr": "Rapport figé disponible. Vérifiez les informations locales avant toute décision.",
            "created_at": report.locked_at,
            "locked_at": report.locked_at,
        })


class PlotSeasonLockView(views.APIView):
    def post(self, request, plot_id, season_label):
        season = get_object_or_404(Season, plot_id=plot_id, label=season_label)
        if season.status != "open":
            return Response({"error": {"code": "CONFLICT", "message": "La saison est déjà verrouillée."}}, status=status.HTTP_409_CONFLICT)
        season.status = "locked"
        season.save(update_fields=["status"])
        report, _ = PredictionReport.objects.update_or_create(
            season=season,
            defaults={
                "plot": season.plot,
                "features_snapshot": {"lock_date": str(season.lock_date)},
                "recommendations_snapshot": {},
            },
        )
        return Response({
            "plot_id": str(plot_id),
            "season_label": season.label,
            "status": "locked",
            "version": 0,
            "text_fr": "Saison verrouillée. Vérifiez les informations locales avant toute décision.",
            "created_at": report.locked_at,
            "locked_at": report.locked_at,
        })


class PlotLearningLoopView(views.APIView):
    def get(self, request, plot_id):
        plot = get_object_or_404(Plot, pk=plot_id)
        active = ModelVersion.objects.filter(is_active=True).order_by("-trained_at").first()
        model = ModelVersionSerializer(active).data if active else None
        return Response({
            "plot_id": str(plot.id),
            "evaluated_season": "",
            "evaluation": None,
            "previous_model": None,
            "current_model": model,
            "data_refresh": "live" if plot.weather_records.exists() else "cached_only",
        })


class PlotSeasonEvaluateView(views.APIView):
    def post(self, request, plot_id, season_label):
        season = get_object_or_404(Season, plot_id=plot_id, label=season_label)
        report = PredictionReport.objects.filter(season=season).first()
        records = WeatherDaily.objects.filter(
            plot_id=plot_id,
            obs_date__gte=season.start_date,
            obs_date__lte=season.end_date,
        )
        observed_precip = sum(record.precip_mm or 0 for record in records)
        predicted_precip = (report.features_snapshot or {}).get("expected_precip_mm", 0) if report else 0
        error = abs(observed_precip - predicted_precip)
        return Response({
            "plot_id": str(plot_id),
            "season_label": season.label,
            "model_version": "unknown",
            "errors": [{
                "period": season.label,
                "target": "precip_mm",
                "predicted": predicted_precip,
                "observed": observed_precip,
                "abs_error": error,
                "pct_error": (error / abs(predicted_precip) * 100) if predicted_precip else None,
            }],
            "skipped_periods": [] if records.exists() else [season.label],
        })


class ModelRetrainView(views.APIView):
    def post(self, request):
        version_tag = f"v_retrained_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
        model_version = ModelVersion.objects.create(
            version_tag=version_tag,
            file_path="media/models/climate/climate_rf_model.joblib",
            metrics={"status": "queued"},
            is_active=False,
        )
        return Response(ModelVersionSerializer(model_version).data, status=status.HTTP_202_ACCEPTED)


class ModelVersionListView(views.APIView):
    def get(self, request):
        models_qs = ModelVersion.objects.all().order_by('-trained_at')
        serializer = ModelVersionSerializer(models_qs, many=True)
        return Response(serializer.data if request.path.startswith("/api/v1/") else {"models": serializer.data}, status=status.HTTP_200_OK)


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