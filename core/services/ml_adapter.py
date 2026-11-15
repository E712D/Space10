import os
import calendar
from datetime import date
import httpx
import pandas as pd
from django.conf import settings
from .weather_service import NasaPowerService, WeatherService

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
        self.weather_service = WeatherService()
        self.nasa_service = NasaPowerService()

    def fetch_daily(self, latitude: float, longitude: float, start: date, end: date, point_id: int | str = "na") -> pd.DataFrame:
        """Récupère les observations NASA POWER, avec Open-Meteo comme secours."""
        if (end - start).days <= 370:
            try:
                return self.nasa_service.fetch_daily(latitude, longitude, start, end)
            except (httpx.HTTPError, ValueError):
                return self.weather_service.fetch_daily(latitude, longitude, start, end)
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
            return self._fallback_prediction(
                daily_df=daily_df,
                season_label=season_label,
                season_start=season_start,
                season_end=season_end,
            )
        
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

    def _fallback_prediction(self, daily_df: pd.DataFrame, season_label: str, season_start: date, season_end: date) -> dict:
        """Produit une prévision structurée et explicitement estimée sans modèle chargé."""
        def finite_or(number, default):
            try:
                value = float(number)
                return value if pd.notna(value) and value == value and abs(value) != float("inf") else default
            except (TypeError, ValueError):
                return default

        observed = not daily_df.empty
        monthly_baseline = {}
        if observed and "date" in daily_df:
            history = daily_df.copy()
            history["_date"] = pd.to_datetime(history["date"])
            history["_month"] = history["_date"].dt.month
            history["_year"] = history["_date"].dt.year
            monthly_rain = (
                history.groupby(["_year", "_month"])["precip_mm"].sum(min_count=1)
                .groupby(level=1)
                .mean()
                if "precip_mm" in history
                else pd.Series(dtype=float)
            )
            for month, rows in history.groupby("_month"):
                monthly_precip = finite_or(monthly_rain.get(month), None)
                monthly_sm_root = None
                if "sm_root" in rows:
                    numeric_sm_root = pd.to_numeric(rows["sm_root"], errors="coerce")
                    if numeric_sm_root.notna().any():
                        monthly_sm_root = finite_or(numeric_sm_root.mean(), None)
                if monthly_sm_root is None and monthly_precip is not None:
                    monthly_sm_root = 0.18 + min(0.55, max(0.0, monthly_precip) / 500.0 * 0.55)
                monthly_baseline[month] = {
                    "precip_mm": monthly_precip,
                    "tmean_c": finite_or(rows["tmean_c"].mean(), None) if "tmean_c" in rows else None,
                    "tmax_c": finite_or(rows["tmax_c"].mean(), None) if "tmax_c" in rows else None,
                    "tmin_c": finite_or(rows["tmin_c"].mean(), None) if "tmin_c" in rows else None,
                    "sm_root": monthly_sm_root,
                }
        rows = []
        cursor = season_start.replace(day=1)
        while cursor <= season_end:
            month_end = date(cursor.year, cursor.month, calendar.monthrange(cursor.year, cursor.month)[1])
            month_end = min(month_end, season_end)
            month_data = daily_df[
                (daily_df["date"] >= cursor) & (daily_df["date"] <= month_end)
            ] if observed and "date" in daily_df else pd.DataFrame()
            baseline = monthly_baseline.get(cursor.month, {})
            precip = (
                finite_or(month_data["precip_mm"].sum(), 150.0)
                if not month_data.empty and "precip_mm" in month_data
                else finite_or(baseline.get("precip_mm"), 150.0)
            )
            tmean = (
                finite_or(month_data["tmean_c"].mean(), 29.0)
                if not month_data.empty and "tmean_c" in month_data
                else finite_or(baseline.get("tmean_c"), 29.0)
            )
            tmax = (
                finite_or(month_data["tmax_c"].mean(), 34.0)
                if not month_data.empty and "tmax_c" in month_data
                else finite_or(baseline.get("tmax_c"), 34.0)
            )
            tmin = (
                finite_or(month_data["tmin_c"].mean(), 23.0)
                if not month_data.empty and "tmin_c" in month_data
                else finite_or(baseline.get("tmin_c"), 23.0)
            )
            sm_root = (
                finite_or(month_data["sm_root"].mean(), 0.45)
                if not month_data.empty and "sm_root" in month_data
                else finite_or(baseline.get("sm_root"), 0.45)
            )
            if month_data.empty:
                sm_root = 0.18 + min(0.55, max(0.0, precip) / 500.0 * 0.55)
            if not month_data.empty and "sm_root" in month_data and month_data["sm_root"].isna().all() and "precip_mm" in month_data:
                monthly_precip = finite_or(month_data["precip_mm"].sum(), 0.0)
                sm_root = 0.18 + min(0.55, max(0.0, monthly_precip) / 500.0 * 0.55)
            heat_days = max(0, round((tmax - 32) * 4))
            quality = "observed" if not month_data.empty else "estimated"

            def value(number, digits=2):
                rounded = round(number, digits)
                return {"value": rounded, "q10": rounded, "q90": rounded, "quality": quality}

            water_stress = max(0.0, min(1.0, 1 - sm_root))
            erosion = max(0.0, min(1.0, precip / 500))
            rows.append({
                "period": f"{cursor.year:04d}-{cursor.month:02d}",
                "lead_months": len(rows) + 1,
                "features": {
                    "t2m_mean_c": value(tmean, 1), "t2m_max_c": value(tmax, 1), "t2m_min_c": value(tmin, 1),
                    "precip_mm": value(precip), "rain_days": value(0), "heavy_rain_days": value(0),
                    "dry_days": value(0), "heat_stress_days": value(heat_days), "rh2m_pct": value(70, 1),
                    "solar_mj_m2": value(18, 1), "sm_surface": value(sm_root), "sm_root": value(sm_root),
                    "et0_mm": value(120), "ndvi": value(0.5, 2),
                },
                "indices": {
                    "water_stress_index": value(water_stress), "erosion_risk_index": value(erosion),
                    "infiltration_capacity_index": value(0.5),
                },
            })
            cursor = date(cursor.year + (1 if cursor.month == 12 else 0), 1 if cursor.month == 12 else cursor.month + 1, 1)

        total_precip = sum(p["features"]["precip_mm"]["value"] for p in rows)
        heat_total = sum(p["features"]["heat_stress_days"]["value"] for p in rows)
        water_mean = sum(p["indices"]["water_stress_index"]["value"] for p in rows) / len(rows) if rows else 0
        return {
            "status": "success",
            "season": {"label": season_label},
            "model_version": self.active_version,
            "periods": rows,
            "season_summary": {
                "precip_total_mm": value(total_precip),
                "heat_stress_days_total": value(heat_total),
                "mean_water_stress_index": value(water_mean),
                "features": {
                    "precip_total_mm": value(total_precip),
                    "water_stress_index": value(water_mean),
                    "sm_root": value(
                        sum(p["features"]["sm_root"]["value"] for p in rows) / len(rows)
                        if rows else 0.45
                    ),
                    "erosion_risk_index": value(max((p["indices"]["erosion_risk_index"]["value"] for p in rows), default=0)),
                    "heat_stress_days": value(heat_total),
                },
            },
            "critical_periods": [],
            "baseline_comparison": [],
            "warnings": ["Prévision estimée : aucun modèle ML externe n'est chargé."],
        }

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