import os
from datetime import date
import pandas as pd
from django.conf import settings

# Importation conditionnelle ou bascule selon configuration
ML_AVAILABLE = True

try:
    from ml import mock as ml_mock
except ImportError:
    ml_mock = None
    ML_AVAILABLE = False

try:
    from ml import predict as ml_predict
except ImportError:
    ml_predict = None

try:
    from ml import evaluate as ml_evaluate
except ImportError:
    ml_evaluate = None

try:
    from ml import retrain as ml_retrain
except ImportError:
    ml_retrain = None

try:
    from ml import nasa_power as ml_power
except ImportError:
    ml_power = None


class MlAdapter:
    """
    Adaptateur unifié pour interagir soit avec le vrai package ML, 
    soit avec les mocks de développement.
    """
    def __init__(self):
        # On lit la variable d'environnement ou le settings Django
        self.use_mock = getattr(settings, "USE_MOCK_ML", os.getenv("USE_MOCK_ML", "true").lower() == "true")
        self.active_version = getattr(settings, "ML_ACTIVE_VERSION", "v1.0.0")

    def fetch_daily(self, latitude: float, longitude: float, start: date, end: date, point_id: int | str = "na") -> pd.DataFrame:
        """Récupère les données météo journalières (NASA POWER ou mock)."""
        if self.use_mock or not ML_AVAILABLE or ml_mock is None:
            if ml_mock and hasattr(ml_mock, "mock_daily"):
                return ml_mock.mock_daily(latitude, longitude, start, end)
            return pd.DataFrame()
        
        if ml_power and hasattr(ml_power, "fetch_power_daily"):
            return ml_power.fetch_power_daily(latitude, longitude, start, end, point_id=point_id)
        return pd.DataFrame()

    def predict(
        self,
        daily_df: pd.DataFrame,
        plot_id: int,
        latitude: float,
        longitude: float,
        season_label: str,
        season_start: date,
        season_end: date,
        soil_texture: str | None = None,
        slope_pct: float | None = None,
        forecast_origin: date | None = None
    ) -> dict:
        """Exécute la prédiction saisonnière."""
        if self.use_mock or not ML_AVAILABLE or ml_mock is None:
            if ml_mock and hasattr(ml_mock, "mock_prediction"):
                return ml_mock.mock_prediction(
                    plot_id=plot_id,
                    latitude=latitude,
                    longitude=longitude,
                    season_label=season_label,
                    season_start=season_start,
                    season_end=season_end
                )
            return {"status": "success", "recommendations": {}}
        
        if ml_predict and hasattr(ml_predict, "predict_season"):
            return ml_predict.predict_season(
                daily_df=daily_df,
                plot_id=plot_id,
                latitude=latitude,
                longitude=longitude,
                season_label=season_label,
                season_start=season_start,
                season_end=season_end,
                soil_texture=soil_texture,
                slope_pct=slope_pct,
                forecast_origin=forecast_origin,
                model_version=self.active_version
            )
        return {"status": "error", "message": "predict_season not available"}

    def compute_errors(self, prediction: dict, observed_daily_df: pd.DataFrame) -> dict:
        """Compare les prévisions aux observations réelles."""
        if self.use_mock or not ML_AVAILABLE or ml_evaluate is None:
            return {"errors": [], "skipped_periods": [], "mae_by_feature": {}}
        
        return ml_evaluate.compute_errors(prediction, observed_daily_df)

    def retrain(self, cutoff_date: date, parent_version: str, new_version: str) -> dict:
        """Déclenche le réentraînement du modèle."""
        if self.use_mock or not ML_AVAILABLE or ml_retrain is None:
            return {
                "version": new_version,
                "parent_version": parent_version,
                "trained_data_end": str(cutoff_date),
                "metrics": {"skill_pct": 5.0}
            }
        
        return ml_retrain.retrain(cutoff_date=cutoff_date, parent_version=parent_version, new_version=new_version)