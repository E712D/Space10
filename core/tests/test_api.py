from datetime import date, timedelta
import json
from unittest.mock import patch
import pandas as pd
from django.contrib.gis.geos import Point
from rest_framework import status
from rest_framework.test import APITestCase
from persistence.models import User, Plot, Season, StrategicReport, PredictionReport, ModelVersion, WeatherDaily
from core.services.weather_service import NasaPowerService, WeatherService
from core.services.ml_adapter import MlAdapter


class Space10ApiIntegrationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create(
            full_name="Test Agronome",
            role="agronomist",
            language="fr"
        )

        self.point = Point(-5.2767, 6.8276, srid=4326)
        self.plot = Plot.objects.create(
            user=self.user,
            name="Parcelle Test Automatisé",
            centroid=self.point,
            soil_texture="argilo-limoneux",
            soil_ph=6.5,
            slope_pct=1.5
        )

        self.season = Season.objects.create(
            plot=self.plot,
            label="2026-A",
            start_date=date(2026, 3, 1),
            end_date=date(2026, 7, 31),
            lock_date=date(2026, 6, 1),
            status="open"
        )

    def test_plot_analysis_endpoint(self):
        url = "/api/plots/analyze/"
        payload = {
            "plot_id": self.plot.id,
            "season_label": "2026-A",
            "today": "2026-11-14"
        }

        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        self.assertEqual(data["plot_id"], self.plot.id)
        self.assertIn("season", data)
        self.assertEqual(data["season"]["label"], "2026-A")
        self.assertIn("prediction", data)
        self.assertEqual(data["prediction"]["status"], "success")
        self.assertTrue(data["locked"])

    def test_fallback_prediction_normalizes_missing_numeric_values(self):
        adapter = MlAdapter()
        prediction = adapter._fallback_prediction(
            pd.DataFrame([
                {
                    "date": date(2026, 1, 15),
                    "precip_mm": 12.0,
                    "tmean_c": 28.0,
                    "tmax_c": 34.0,
                    "tmin_c": 22.0,
                    "sm_root": float("nan"),
                }
            ]),
            "2027-A",
            date(2027, 3, 1),
            date(2027, 7, 31),
        )

        json.dumps(prediction, allow_nan=False)
        self.assertGreater(prediction["periods"][0]["features"]["sm_surface"]["value"], 0)
        self.assertLessEqual(prediction["periods"][0]["features"]["sm_surface"]["value"], 0.73)

    def test_season_lock_and_strategic_report(self):
        lock_url = f"/api/seasons/{self.season.id}/lock/"
        response = self.client.post(lock_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Vérification en base que le statut est mis à jour
        self.season.refresh_from_db()
        self.assertEqual(self.season.status, "locked")

        StrategicReport.objects.create(
            season=self.season,
            content="Bilan stratégique de test pour la saison 2026-A."
        )

        report_url = f"/api/reports/{self.season.id}/"
        res_report = self.client.get(report_url)
        self.assertEqual(res_report.status_code, status.HTTP_200_OK)
        self.assertIn("Bilan stratégique", res_report.json()["content"])

    def test_model_versions_and_learning_loop(self):
        ModelVersion.objects.create(
            version_tag="v1.0.0",
            file_path="models/weights/v1.0.0.joblib",
            metrics={"rmse": 12.5},
            is_active=True
        )

        models_url = "/api/models/"
        res_models = self.client.get(models_url)
        self.assertEqual(res_models.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_models.json()["models"]), 1)

        PredictionReport.objects.create(
            season=self.season,
            plot=self.plot,
            features_snapshot={"expected_precip_mm": 500.0},
            recommendations_snapshot={}
        )

        eval_url = "/api/learning/evaluate/"
        res_eval = self.client.post(eval_url, {"season_id": self.season.id}, format="json")
        self.assertEqual(res_eval.status_code, status.HTTP_200_OK)
        self.assertEqual(res_eval.json()["status"], "evaluated_successfully")

        retrain_url = "/api/learning/retrain/"
        res_retrain = self.client.post(retrain_url)
        self.assertEqual(res_retrain.status_code, status.HTTP_202_ACCEPTED)
        self.assertIn("retraining triggered", res_retrain.json()["status"])

    def test_v1_analysis_matches_frontend_contract(self):
        plot_response = self.client.get("/api/v1/plots/")
        self.assertEqual(plot_response.status_code, status.HTTP_200_OK)
        plot_data = plot_response.json()[0]
        self.assertIn("owner_name", plot_data)
        self.assertIsInstance(plot_data["practiced_crops"], list)
        self.assertIsInstance(plot_data["crop_history"], list)

        response = self.client.post(
            f"/api/v1/plots/{self.plot.id}/analysis/",
            {"season_label": "2026-A", "today": "2026-01-15"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["plot_id"], str(self.plot.id))
        self.assertIn("season", data)
        self.assertIn("prediction", data)
        self.assertIn("recommendation", data)
        self.assertIn("main_crop", data["recommendation"])
        self.assertIn("report", data)

    def test_v1_plot_creation_accepts_bouake_coordinates(self):
        response = self.client.post(
            "/api/v1/plots/",
            {
                "name": "Nouvelle parcelle Bouaké",
                "owner_name": "Exploitant test",
                "latitude": 7.6939,
                "longitude": -5.0302,
                "area_ha": 1.5,
                "soil_texture": "loamy",
                "soil_ph": 6.2,
                "slope_pct": None,
                "practiced_crops": [],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()["latitude"], 7.6939)
        self.assertEqual(response.json()["longitude"], -5.0302)

    @patch("core.views.WeatherService.fetch_daily", return_value=pd.DataFrame())
    def test_current_weather_ignores_incomplete_latest_record(self, _fetch_daily):
        WeatherDaily.objects.create(
            plot=self.plot,
            obs_date=date.today(),
            sources={"provider": "NASA POWER"},
        )
        WeatherDaily.objects.create(
            plot=self.plot,
            obs_date=date.today() - timedelta(days=1),
            tmax_c=31.5,
            precip_mm=4.0,
            sources={"provider": "NASA POWER"},
        )

        response = self.client.get(f"/api/v1/plots/{self.plot.id}/seasons/current/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["quality"], "observed")
        self.assertEqual(data["series_30d"][-1]["t2m_max_c"], 31.5)

    def test_v1_support_modules_are_available(self):
        self.assertEqual(self.client.get("/api/v1/health/").status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get("/api/v1/system/clock/").status_code, status.HTTP_200_OK)
        crops = self.client.get("/api/v1/crops/")
        self.assertEqual(crops.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(crops.json()), 3)

        current = self.client.get(f"/api/v1/plots/{self.plot.id}/seasons/current/")
        self.assertEqual(current.status_code, status.HTTP_200_OK)
        current_data = current.json()
        self.assertIn("next_season", current_data)
        self.assertIn("name_fr", current_data["next_season"])
        self.assertIn("months", current_data["next_season"])
        with patch(
            "core.services.chatbot_orchestrator.ChatbotOrchestrator._run_analysis",
            return_value={
                "prediction": {"season_summary": {"features": {}}},
                "recommendations": [
                    {"rotation": [{"crop_code": "maize"}]},
                    {"rotation": [{"crop_code": "rice"}]},
                ],
            },
        ):
            voice = self.client.post(
                "/api/v1/voice/ask/",
                {"plot_id": str(self.plot.id), "question": "Quelle culture planter ?"},
                format="json",
            )
        self.assertEqual(voice.status_code, status.HTTP_200_OK)
        self.assertIn("answer_text", voice.json())
        self.assertIn("Maize", voice.json()["answer_text"])
        self.assertNotIn("Lancez", voice.json()["answer_text"])

    def test_voice_answers_use_requested_metric(self):
        analysis = {
            "prediction": {
                "season_summary": {
                    "precip_total_mm": {"value": 780},
                    "features": {
                        "water_stress_index": {"value": 0.62},
                        "sm_root": {"value": 0.38},
                    },
                },
                "periods": [
                    {
                        "period": "2027-03",
                        "features": {
                            "precip_mm": {"value": 120},
                            "t2m_max_c": {"value": 33},
                            "heat_stress_days": {"value": 2},
                        },
                    },
                    {
                        "period": "2027-04",
                        "features": {
                            "precip_mm": {"value": 210},
                            "t2m_max_c": {"value": 36},
                            "heat_stress_days": {"value": 8},
                        },
                    },
                ],
                "critical_periods": [],
            },
            "recommendations": [],
        }
        with patch("core.services.chatbot_orchestrator.ChatbotOrchestrator._run_analysis", return_value=analysis):
            rain = self.client.post(
                "/api/v1/voice/ask/",
                {"plot_id": str(self.plot.id), "question": "Quel mois aura le plus de pluie ?"},
                format="json",
            ).json()
            heat = self.client.post(
                "/api/v1/voice/ask/",
                {"plot_id": str(self.plot.id), "question": "Quelle température fera-t-il ?"},
                format="json",
            ).json()
            water = self.client.post(
                "/api/v1/voice/ask/",
                {"plot_id": str(self.plot.id), "question": "Le sol aura-t-il assez d'eau ?"},
                format="json",
            ).json()

        self.assertIn("780 mm", rain["answer_text"])
        self.assertIn("2027-04", rain["answer_text"])
        self.assertIn("36 °C", heat["answer_text"])
        self.assertIn("38 %", water["answer_text"])
        self.assertNotEqual(rain["answer_text"], heat["answer_text"])
        self.assertNotEqual(heat["answer_text"], water["answer_text"])

    def test_voice_understands_contextual_risk_question(self):
        analysis = {
            "prediction": {
                "critical_periods": [
                    {"message_fr": "Surveillez les fortes pluies en juin."},
                ],
                "periods": [],
            },
            "recommendations": [],
        }
        with patch("core.services.chatbot_orchestrator.ChatbotOrchestrator._run_analysis", return_value=analysis):
            response = self.client.post(
                "/api/v1/voice/ask/",
                {"plot_id": str(self.plot.id), "question": "Quand faut-il faire attention ?"},
                format="json",
            )
        data = response.json()
        self.assertEqual(data["intent"], "critical_periods")
        self.assertIn("fortes pluies", data["answer_text"])

    def test_voice_rejects_non_agricultural_questions(self):
        response = self.client.post(
            "/api/v1/voice/ask/",
            {"plot_id": str(self.plot.id), "question": "Qui a gagné le match hier ?"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["intent"], "out_of_scope")
        self.assertIn("spécialisé dans l'agriculture", response.json()["answer_text"])

    def test_voice_uses_ivoirian_season_context(self):
        analysis = {
            "season": {
                "label": "2027-A",
                "start_date": date(2027, 3, 1),
                "end_date": date(2027, 7, 31),
            },
            "prediction": {
                "season": {"label": "2027-A"},
                "periods": [],
            },
            "recommendations": [],
        }
        with patch("core.services.chatbot_orchestrator.ChatbotOrchestrator._run_analysis", return_value=analysis):
            response = self.client.post(
                "/api/v1/voice/ask/",
                {"plot_id": str(self.plot.id), "question": "Parle-moi de la saison agricole"},
                format="json",
            )
        data = response.json()
        self.assertEqual(data["intent"], "season_calendar")
        self.assertIn("grande saison agricole", data["answer_text"])
        self.assertIn("2027-A", data["answer_text"])

        sports = self.client.post(
            "/api/v1/voice/ask/",
            {"plot_id": str(self.plot.id), "question": "Parle-moi de la saison de football"},
            format="json",
        )
        self.assertEqual(sports.json()["intent"], "out_of_scope")

    def test_voice_distinguishes_crop_climate_question_from_crop_recommendation(self):
        analysis = {
            "season": {"label": "2027-A", "start_date": date(2027, 3, 1), "end_date": date(2027, 7, 31)},
            "prediction": {
                "season": {"label": "2027-A"},
                "periods": [{
                    "period": "2027-04",
                    "features": {"t2m_max_c": {"value": 36}},
                }],
            },
            "recommendations": [{"rotation": [{"crop_code": "cowpea"}]}],
        }
        with patch("core.services.chatbot_orchestrator.ChatbotOrchestrator._run_analysis", return_value=analysis):
            response = self.client.post(
                "/api/v1/voice/ask/",
                {"plot_id": str(self.plot.id), "question": "Quel climat est le plus adapté pour la culture de tomate ?"},
                format="json",
            )
        data = response.json()
        self.assertEqual(data["intent"], "crop_knowledge")
        self.assertIn("18 à 27 °C", data["answer_text"])
        self.assertIn("36 °C", data["answer_text"])
        self.assertNotIn("cowpea", data["answer_text"].casefold())
        self.assertEqual(data["sources"][0]["name"], "Référentiel agronomique tomate")

    def test_voice_recognizes_pepper_climate_question(self):
        response = self.client.post(
            "/api/v1/voice/ask/",
            {"plot_id": str(self.plot.id), "question": "Quel climat est adapté pour la culture de piment ?"},
            format="json",
        )
        data = response.json()
        self.assertEqual(data["intent"], "crop_knowledge")
        self.assertIn("20 à 30 °C", data["answer_text"])
        self.assertNotIn("Cowpea", data["answer_text"])

    def test_voice_answers_crop_season_instead_of_recommending_another_crop(self):
        with patch(
            "core.services.chatbot_orchestrator.ChatbotOrchestrator._run_analysis",
            return_value={"prediction": {}, "recommendations": [{"rotation": [{"crop_code": "cowpea"}]}]},
        ):
            response = self.client.post(
                "/api/v1/voice/ask/",
                {"plot_id": str(self.plot.id), "question": "Quelle est la meilleure saison pour la culture du tomate ?"},
                format="json",
            )
        data = response.json()
        self.assertEqual(data["intent"], "crop_season")
        self.assertIn("novembre à février", data["answer_text"])
        self.assertNotIn("Cowpea", data["answer_text"])

    @patch("core.services.weather_service.httpx.get")
    def test_nasa_power_service_maps_daily_parameters(self, mock_get):
        response = mock_get.return_value
        response.json.return_value = {
            "properties": {
                "parameter": {
                    "T2M": {"20261114": 27.5},
                    "T2M_MAX": {"20261114": 33.2},
                    "T2M_MIN": {"20261114": 21.1},
                    "PRECTOTCORR": {"20261114": 8.4},
                    "RH2M": {"20261114": 76},
                    "ALLSKY_SFC_SW_DWN": {"20261114": 18.2},
                }
            }
        }
        result = NasaPowerService().fetch_daily(
            6.8276, -5.2767, date(2026, 11, 14), date(2026, 11, 14)
        )
        self.assertEqual(result.iloc[0]["date"], date(2026, 11, 14))
        self.assertEqual(result.iloc[0]["precip_mm"], 8.4)
        self.assertEqual(result.iloc[0]["sources"]["provider"], "NASA POWER")

    @patch("core.services.weather_service.httpx.get")
    def test_weather_service_maps_open_meteo_daily_response(self, mock_get):
        mock_response = mock_get.return_value
        mock_response.json.return_value = {
            "daily": {
                "time": ["2026-11-14"],
                "temperature_2m_max": [31.2],
                "temperature_2m_min": [22.1],
                "temperature_2m_mean": [26.7],
                "precipitation_sum": [4.5],
                "relative_humidity_2m_mean": [78],
                "et0_fao_evapotranspiration": [3.1],
                "soil_moisture_0_to_7cm_mean": [0.2],
                "soil_moisture_7_to_28cm_mean": [0.3],
            }
        }

        result = WeatherService().fetch_daily(
            6.8276,
            -5.2767,
            date(2026, 11, 14),
            date(2026, 11, 14),
        )

        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(result.iloc[0]["tmax_c"], 31.2)
        self.assertEqual(result.iloc[0]["precip_mm"], 4.5)
        mock_response.raise_for_status.assert_called_once_with()
        mock_get.assert_called_once()