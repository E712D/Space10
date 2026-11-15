from datetime import date
import math
import pandas as pd
from django.contrib.gis.geos import Point
from .models import Plot, Season, WeatherDaily, Crop, PredictionReport

class PlotRepository:
    def get_plot(self, plot_id: int) -> dict | None:
        try:
            p = Plot.objects.prefetch_related('weather_records').get(pk=plot_id)
            lat = p.centroid.y if p.centroid else 0.0
            lon = p.centroid.x if p.centroid else 0.0
            
            return {
                "plot_id": p.id,
                "name": p.name,
                "latitude": lat,
                "longitude": lon,
                "soil_texture": p.soil_texture,
                "soil_ph": float(p.soil_ph) if p.soil_ph else None,
                "slope_pct": float(p.slope_pct) if p.slope_pct else 0.0,
                "priorities": p.priorities,
                "practiced_crops": [],
                "current_crop_code": None,
                "history": []
            }
        except Plot.DoesNotExist:
            return None


class SeasonRepository:
    def get_or_create_season(self, plot_id: int, season_label: str, start_date: date, end_date: date, lock_date: date) -> dict:
        plot = Plot.objects.get(pk=plot_id)
        season, created = Season.objects.get_or_create(
            plot=plot,
            label=season_label,
            defaults={
                "start_date": start_date,
                "end_date": end_date,
                "lock_date": lock_date,
                "status": "open"
            }
        )
        return {
            "id": season.id,
            "plot_id": plot_id,
            "label": season.label,
            "start_date": season.start_date,
            "end_date": season.end_date,
            "lock_date": season.lock_date,
            "status": season.status
        }

    def list_plot_seasons(self, plot_id: int) -> list[dict]:
        """Liste toutes les saisons d'une parcelle avec leur statut et rapport associé."""
        seasons = Season.objects.filter(plot_id=plot_id).order_by('-start_date')
        result = []
        for s in seasons:
            # Vérifie s'il existe un rapport figé pour cette saison
            has_report = hasattr(s, 'prediction_report')
            result.append({
                "id": s.id,
                "label": s.label,
                "start_date": s.start_date,
                "end_date": s.end_date,
                "lock_date": s.lock_date,
                "status": s.status,
                "has_frozen_report": has_report
            })
        return result


class WeatherRepository:
    def get_last_weather_date(self, plot_id: int) -> date | None:
        last_record = WeatherDaily.objects.filter(plot_id=plot_id).order_by('-obs_date').first()
        return last_record.obs_date if last_record else None

    def get_weather_daily(self, plot_id: int, start: date, end: date) -> pd.DataFrame:
        qs = WeatherDaily.objects.filter(plot_id=plot_id, obs_date__range=(start, end)).order_by('obs_date')
        data = list(qs.values('obs_date', 'tmax_c', 'tmin_c', 'tmean_c', 'precip_mm', 'rh_pct', 'solar_mj_m2', 'sm_surface', 'sm_root', 'et0_mm', 'ndvi'))
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        df.rename(columns={'obs_date': 'date'}, inplace=True)
        return df

    def upsert_weather_daily(self, plot_id: int, df: pd.DataFrame):
        plot = Plot.objects.get(pk=plot_id)
        def finite(value):
            if value is None or pd.isna(value):
                return None
            try:
                return value if math.isfinite(float(value)) else None
            except (TypeError, ValueError):
                return None

        for _, row in df.iterrows():
            WeatherDaily.objects.update_or_create(
                plot=plot,
                obs_date=row['date'],
                defaults={
                    'tmax_c': finite(row.get('tmax_c')),
                    'tmin_c': finite(row.get('tmin_c')),
                    'tmean_c': finite(row.get('tmean_c')),
                    'precip_mm': finite(row.get('precip_mm')),
                    'rh_pct': finite(row.get('rh_pct')),
                    'solar_mj_m2': finite(row.get('solar_mj_m2')),
                    'sm_surface': finite(row.get('sm_surface')),
                    'sm_root': finite(row.get('sm_root')),
                    'et0_mm': finite(row.get('et0_mm')),
                    'ndvi': finite(row.get('ndvi')),
                    'sources': row.get('sources') or {'provider': 'unknown'},
                }
            )


class CropRepository:
    def list_crops(self) -> list[dict]:
        return list(Crop.objects.all().values())

    def list_rotation_rules(self) -> list:
        return []


class ReportRepository:
    def save_prediction_report(self, season_id: int, plot_id: int, features: dict, recommendations: dict) -> int:
        """Enregistre le rapport figé au moment du lock_date."""
        report, created = PredictionReport.objects.update_or_create(
            season_id=season_id,
            defaults={
                "plot_id": plot_id,
                "features_snapshot": features,
                "recommendations_snapshot": recommendations
            }
        )
        return report.id

    def get_report(self, season_id: int) -> dict | None:
        """Récupère le rapport figé d'une saison s'il existe."""
        try:
            report = PredictionReport.objects.get(season_id=season_id)
            return {
                "report_id": report.id,
                "locked_at": report.locked_at,
                "features": report.features_snapshot,
                "recommendations": report.recommendations_snapshot
            }
        except PredictionReport.DoesNotExist:
            return None