from django.urls import path, include
from rest_framework.routers import DefaultRouter
from core.views import (
    PlotViewSet, CropViewSet, SeasonViewSet,
    StrategicReportView, ModelVersionListView,
    LearningEvaluateView, LearningRetrainView
)
from .views import AnalyzePlotView, PlotSeasonsView, ReportAudioView

# Routeur DRF principal pour toutes les ressources gérées par des ViewSets
router = DefaultRouter()
router.register(r'plots', PlotViewSet, basename='plot')
router.register(r'crops', CropViewSet, basename='crop')
router.register(r'seasons', SeasonViewSet, basename='season')

urlpatterns = [
    # 1. Vues personnalisées existantes
    path('plots/analyze/', AnalyzePlotView.as_view(), name='analyze-plot'),
    path('plots/<int:plot_id>/seasons/', PlotSeasonsView.as_view(), name='plot-seasons'),
    path('plots/<int:plot_id>/report/audio/', ReportAudioView.as_view(), name='plot-report-audio'),

    # 2. Nouveaux endpoints spécifiques
    path('reports/<int:season_id>/', StrategicReportView.as_view(), name='strategic-report'),
    path('models/', ModelVersionListView.as_view(), name='model-list'),
    path('learning/evaluate/', LearningEvaluateView.as_view(), name='learning-evaluate'),
    path('learning/retrain/', LearningRetrainView.as_view(), name='learning-retrain'),

    # 3. Routes automatiques générées par les routeurs DRF (plots/, crops/, seasons/ et leurs actions comme lock/)
    path('', include(router.urls)),
]