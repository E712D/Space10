from datetime import date
from django.contrib.gis.geos import Point
from rest_framework import status
from rest_framework.test import APITestCase
from persistence.models import User, Plot, Season, StrategicReport, PredictionReport, ModelVersion


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