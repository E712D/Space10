from django.urls import path, include
from rest_framework.routers import DefaultRouter
from core.views import (
    PlotViewSet, CropViewSet, SeasonViewSet,
    StrategicReportView, ModelVersionListView,
    LearningEvaluateView, LearningRetrainView,
    PlotSeasonReportView, PlotSeasonLockView, PlotLearningLoopView,
    PlotSeasonEvaluateView, ModelRetrainView,
    HealthView, ClockView, VoiceAskView, CurrentSeasonView,
)
from .views import (
    AnalyzePlotView,
    PlotSeasonsView,
    ReportAudioView,
    TerraCIRecommendationView,
)

# Routeur DRF principal pour toutes les ressources gérées par des ViewSets
router = DefaultRouter()
router.register(r'plots', PlotViewSet, basename='plot')
router.register(r'crops', CropViewSet, basename='crop')
router.register(r'seasons', SeasonViewSet, basename='season')

urlpatterns = [
    path('health/', HealthView.as_view(), name='health'),
    path('system/clock/', ClockView.as_view(), name='clock'),
    path('voice/ask/', VoiceAskView.as_view(), name='voice-ask'),
    path('plots/<int:plot_id>/seasons/current/', CurrentSeasonView.as_view(), name='current-season'),
    # 1. Vues personnalisées existantes
    path('plots/analyze/', AnalyzePlotView.as_view(), name='analyze-plot'),
    path('terraci/recommend/', TerraCIRecommendationView.as_view(), name='terraci-recommend'),
    path('plots/<int:plot_id>/seasons/', PlotSeasonsView.as_view(), name='plot-seasons'),
    path('plots/<int:plot_id>/report/audio/', ReportAudioView.as_view(), name='plot-report-audio'),
    path('plots/<int:plot_id>/seasons/<str:season_label>/report/', PlotSeasonReportView.as_view(), name='plot-season-report'),
    path('plots/<int:plot_id>/seasons/<str:season_label>/lock/', PlotSeasonLockView.as_view(), name='plot-season-lock'),
    path('plots/<int:plot_id>/seasons/<str:season_label>/evaluate/', PlotSeasonEvaluateView.as_view(), name='plot-season-evaluate'),
    path('plots/<int:plot_id>/learning-loop/', PlotLearningLoopView.as_view(), name='plot-learning-loop'),

    # 2. Nouveaux endpoints spécifiques
    path('reports/<int:season_id>/', StrategicReportView.as_view(), name='strategic-report'),
    path('models/', ModelVersionListView.as_view(), name='model-list'),
    path('models/retrain/', ModelRetrainView.as_view(), name='model-retrain'),
    path('learning/evaluate/', LearningEvaluateView.as_view(), name='learning-evaluate'),
    path('learning/retrain/', LearningRetrainView.as_view(), name='learning-retrain'),

    # 3. Routes automatiques générées par les routeurs DRF (plots/, crops/, seasons/ et leurs actions comme lock/)
    path('', include(router.urls)),
]