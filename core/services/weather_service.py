from datetime import date
import math

import httpx
import pandas as pd


OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
NASA_POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"


class WeatherService:
    """Fetches recent observations from the free Open-Meteo API."""

    def fetch_daily(self, latitude: float, longitude: float, start: date, end: date) -> pd.DataFrame:
        response = httpx.get(
            OPEN_METEO_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "timezone": "UTC",
                "daily": ",".join(
                    (
                        "temperature_2m_max",
                        "temperature_2m_min",
                        "temperature_2m_mean",
                        "precipitation_sum",
                        "relative_humidity_2m_mean",
                        "et0_fao_evapotranspiration",
                        "soil_moisture_0_to_7cm_mean",
                        "soil_moisture_7_to_28cm_mean",
                    )
                ),
            },
            timeout=8,
        )
        response.raise_for_status()
        daily = response.json().get("daily", {})
        dates = daily.get("time", [])
        if not dates:
            return pd.DataFrame()
        return pd.DataFrame({
            "date": dates,
            "tmax_c": daily.get("temperature_2m_max", []),
            "tmin_c": daily.get("temperature_2m_min", []),
            "tmean_c": daily.get("temperature_2m_mean", []),
            "precip_mm": daily.get("precipitation_sum", []),
            "rh_pct": daily.get("relative_humidity_2m_mean", []),
            "et0_mm": daily.get("et0_fao_evapotranspiration", []),
            "sm_surface": daily.get("soil_moisture_0_to_7cm_mean", []),
            "sm_root": daily.get("soil_moisture_7_to_28cm_mean", []),
        })


class NasaPowerService:
    """Fetches daily agro-meteorological observations for a plot coordinate."""

    parameters = "T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,RH2M,ALLSKY_SFC_SW_DWN"

    def fetch_daily(self, latitude: float, longitude: float, start: date, end: date) -> pd.DataFrame:
        response = httpx.get(
            NASA_POWER_URL,
            params={
                "parameters": self.parameters,
                "community": "AG",
                "longitude": longitude,
                "latitude": latitude,
                "start": start.strftime("%Y%m%d"),
                "end": end.strftime("%Y%m%d"),
                "format": "JSON",
                "time-standard": "UTC",
            },
            headers={"User-Agent": "Space10/1.0"},
            timeout=20,
        )
        response.raise_for_status()
        values = response.json().get("properties", {}).get("parameter", {})
        dates = sorted(set().union(*(series.keys() for series in values.values())))
        if not dates:
            return pd.DataFrame()

        def value(parameter, day):
            number = values.get(parameter, {}).get(day)
            if number in (None, -999, -999.0):
                return None
            try:
                return number if math.isfinite(float(number)) else None
            except (TypeError, ValueError):
                return None

        return pd.DataFrame([
            {
                "date": date(int(day[:4]), int(day[4:6]), int(day[6:])),
                "tmax_c": value("T2M_MAX", day),
                "tmin_c": value("T2M_MIN", day),
                "tmean_c": value("T2M", day),
                "precip_mm": value("PRECTOTCORR", day),
                "rh_pct": value("RH2M", day),
                "solar_mj_m2": value("ALLSKY_SFC_SW_DWN", day),
                "sources": {"provider": "NASA POWER", "dataset": "AG"},
            }
            for day in dates
        ])
