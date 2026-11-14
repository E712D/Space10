import os
from datetime import date
from django.http import FileResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from persistence.repositories import PlotRepository, SeasonRepository, WeatherRepository, CropRepository, ReportRepository
from core.services.ml_adapter import MlAdapter
from core.services.orchestrator import Orchestrator
from core.services.audio_service import generate_report_audio
from .serializers import AnalyzePlotRequestSerializer

class UnitOfWorkRepositories:
    """Regroupe les repositories pour l'orchestrateur."""
    def __init__(self):
        self.plots = PlotRepository()
        self.seasons = SeasonRepository()
        self.weather = WeatherRepository()
        self.crops = CropRepository()
        self.reports = ReportRepository()


class AnalyzePlotView(APIView):
    """
    Endpoint pour lancer l'analyse agronomique complète d'une parcelle (POST).
    """
    def post(self, request):
        serializer = AnalyzePlotRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        plot_id = data.get("plot_id")
        season_label = data.get("season_label")
        today = data.get("today", date.today())

        try:
            # Initialisation de la chaîne
            repos = UnitOfWorkRepositories()
            ml_adapter = MlAdapter()
            orchestrator = Orchestrator(repos=repos, ml_adapter=ml_adapter)

            # Exécution de l'analyse
            result = orchestrator.run_analysis(
                plot_id=plot_id,
                season_label=season_label,
                today=today
            )

            return Response(result, status=status.HTTP_200_OK)

        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"Erreur interne : {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PlotSeasonsView(APIView):
    """
    Endpoint pour lister l'historique des saisons d'une parcelle (GET).
    """
    def get(self, request, plot_id: int):
        try:
            season_repo = SeasonRepository()
            seasons = season_repo.list_plot_seasons(plot_id)
            
            return Response({
                "plot_id": plot_id,
                "seasons": seasons
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({"error": f"Erreur interne : {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ReportAudioView(APIView):
    """
    Endpoint pour générer et renvoyer le flux audio (.mp3) du rapport agronomique (GET).
    """
    def get(self, request, plot_id: int):
        season_id = request.query_params.get("season_id")
        report_repo = ReportRepository()
        
        report = report_repo.get_report(season_id) if season_id else None
        if not report:
            return Response({"error": "Aucun rapport figé trouvé pour générer l'audio."}, status=status.HTTP_404_NOT_FOUND)

        recommendations = report.get("recommendations", {}).get("recommendations", [])
        reco_text = ", ".join([f"Culture recommandée : {r.get('crop_code')} avec un score de {r.get('score', 0)}" for r in recommendations[:2]])
        
        summary_text = (
            f"Rapport pour la parcelle numéro {plot_id}. "
            f"Voici les recommandations principales pour votre saison : {reco_text}. "
            f"Veuillez consulter l'application pour plus de détails."
        )

        audio_filename = f"report_plot_{plot_id}_season_{season_id}.mp3"
        audio_path = os.path.join("/tmp", audio_filename)
        
        try:
            generate_report_audio(summary_text, audio_path)
            
            response = FileResponse(open(audio_path, 'rb'), content_type='audio/mpeg')
            response['Content-Disposition'] = f'inline; filename="{audio_filename}"'
            return response
        except Exception as e:
            return Response({"error": f"Erreur lors de la génération audio : {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)