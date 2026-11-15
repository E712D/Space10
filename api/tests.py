from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory
from api.views import TerraCIRecommendationView


class TerraCIRecommendationApiTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.payload = {
            "latitude": 7.689,
            "longitude": -5.0284,
            "donnees_environnementales": [
                [[80, 30, 0.2, 0.4] for _ in range(12)]
            ],
            "source_donnees": "fixture de test",
            "local_data": {
                "mois_saison": [3, 4, 5, 6, 7],
                "culture_actuelle": "niebe",
            },
            "priorites": ["hydrique"],
        }

    def post_recommendation(self, payload):
        request = self.factory.post(
            "/api/terraci/recommend/",
            payload,
            format="json",
        )
        return TerraCIRecommendationView.as_view()(request)

    def test_recommendation_endpoint_returns_frontend_result(self):
        response = self.post_recommendation(self.payload)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertEqual(data["statut"], "success")
        self.assertEqual(data["rotation_actuelle"]["culture"], "niebe")
        self.assertIn("hydrique", data["strategies_classement"])
        self.assertEqual(data["qualite_donnees"]["origine"], "fixture de test")

    def test_rejects_environmental_year_with_wrong_month_count(self):
        self.payload["donnees_environnementales"] = [
            [[80, 30, 0.2, 0.4] for _ in range(11)]
        ]

        response = self.post_recommendation(self.payload)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("12 mois", str(response.data))

    def test_recognized_maraichere_is_not_scored(self):
        self.payload["local_data"]["culture_actuelle"] = "tomate"

        response = self.post_recommendation(self.payload)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertEqual(data["statut"], "catalogue_incomplet")
        self.assertIsNone(data["strategies_classement"]["temoin"]["culture"])
