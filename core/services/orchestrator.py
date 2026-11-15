from datetime import date, timedelta
from .season_calendar import next_season, season_window, default_lock_date
from ..agronomy.engine import recommend_rotations
from ..agronomy.catalog import CropSheet, RotationRule, PlotContext
from persistence.models import Season

class Orchestrator:
    """
    Orchestre le cycle d'analyse complet d'une parcelle :
    Météo -> Prédiction ML -> Moteur Agronomique -> Sauvegarde & Verrouillage.
    """
    def __init__(self, repos, ml_adapter):
        self.repos = repos
        self.ml = ml_adapter

    def run_analysis(self, plot_id: int, season_label: str | None, today: date) -> dict:
        """Exécute l'analyse complète pour une parcelle et une saison donnée."""
        
        # 1. Récupération de la parcelle
        plot = self.repos.plots.get_plot(plot_id)
        if not plot:
            raise ValueError(f"Parcelle introuvable : {plot_id}")

        # 2. Détermination de la saison
        target_season_label = season_label or next_season(today)
        start_date, end_date = season_window(target_season_label)
        lock_date = default_lock_date(start_date)

        season = self.repos.seasons.get_or_create_season(
            plot_id=plot_id,
            season_label=target_season_label,
            start_date=start_date,
            end_date=end_date,
            lock_date=lock_date
        )

        # 3. Vérification du verrouillage paresseux (Lazy Lock)
        is_locked_due = (today >= lock_date) or (season.get("status") == "locked")
        existing_report = self.repos.reports.get_report(season["id"])
        
        if is_locked_due and existing_report:
            # Si la saison est verrouillée et qu'on a déjà un rapport figé, on le retourne directement
            return {
                "plot_id": plot_id,
                "season": {**season, "status": "locked"},
                "prediction": existing_report["features"],
                "recommendations": existing_report["recommendations"].get("recommendations", []),
                "missing_info": existing_report["recommendations"].get("missing_info", []),
                "needs_local_check": existing_report["recommendations"].get("needs_local_check", []),
                "locked": True,
                "locked_at": existing_report.get("locked_at")
            }

        # 4. Récupération des données météo (via ML Adapter)
        last_weather_date = self.repos.weather.get_last_weather_date(plot_id)
        # Une nouvelle parcelle doit disposer d'une année locale pour établir
        # une climatologie mensuelle, sans bloquer l'API sur plusieurs décennies.
        fetch_start = last_weather_date + timedelta(days=1) if last_weather_date else today - timedelta(days=365)
        fetch_end = today - timedelta(days=1)

        if fetch_start <= fetch_end:
            try:
                daily_df = self.ml.fetch_daily(
                    latitude=plot["latitude"],
                    longitude=plot["longitude"],
                    start=fetch_start,
                    end=fetch_end,
                    point_id=plot_id
                )
                if not daily_df.empty:
                    self.repos.weather.upsert_weather_daily(plot_id, daily_df)
            except Exception as e:
                # Si échec réseau mais qu'on a déjà de l'historique, on continue avec un avertissement
                if not last_weather_date:
                    raise RuntimeError(f"Impossible de récupérer les données NASA POWER : {e}")

        # 5. Préparation des données pour la prédiction
        weather_df = self.repos.weather.get_weather_daily(plot_id, date(1991, 1, 1), today - timedelta(days=1))
        
        prediction_output = self.ml.predict(
            daily_df=weather_df,
            plot_id=plot_id,
            latitude=plot["latitude"],
            longitude=plot["longitude"],
            season_label=target_season_label,
            season_start=start_date,
            season_end=end_date,
            soil_texture=plot.get("soil_texture"),
            slope_pct=plot.get("slope_pct")
        )

        # 6. Exécution du moteur agronomique
        crops_data = self.repos.crops.list_crops()
        rules_data = self.repos.crops.list_rotation_rules()
        
        crop_sheets = [CropSheet(**c) for c in crops_data]
        rotation_rules = [RotationRule(**r) for r in rules_data]
        
        plot_context = PlotContext(
            plot_id=plot_id,
            soil_texture=plot.get("soil_texture"),
            soil_ph=plot.get("soil_ph"),
            priorities=plot.get("priorities", []),
            practiced_crops=plot.get("practiced_crops", []),
            current_crop_code=plot.get("current_crop_code"),
            history=plot.get("history", [])
        )

        engine_output = recommend_rotations(
            prediction=prediction_output,
            plot=plot_context,
            catalog=crop_sheets,
            rules=rotation_rules,
            today=today
        )

        # 7. Sauvegarde et verrouillage si la date de verrouillage est atteinte ou dépassée
        is_now_locked = (today >= lock_date)
        if is_now_locked:
            # Enregistrement du rapport figé pour la future boucle d'apprentissage MLOps
            self.repos.reports.save_prediction_report(
                season_id=season["id"],
                plot_id=plot_id,
                features=prediction_output,
                recommendations=engine_output
            )
            # Mise à jour du statut de la saison en base de données
            Season.objects.filter(pk=season["id"]).update(status="locked")
            season["status"] = "locked"

        return {
            "plot_id": plot_id,
            "season": season,
            "prediction": prediction_output,
            "recommendations": engine_output.get("recommendations", []),
            "missing_info": engine_output.get("missing_info", []),
            "needs_local_check": engine_output.get("needs_local_check", []),
            "locked": is_now_locked
        }