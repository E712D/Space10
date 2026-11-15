import os
import joblib
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.multioutput import MultiOutputRegressor
from persistence.models import Season

MODEL_DIR = "media/models/climate"

class SeasonalClimatePredictor:
    def __init__(self):
        os.makedirs(MODEL_DIR, exist_ok=True)
        self.model_path = os.path.join(MODEL_DIR, "climate_rf_model.joblib")

    def prepare_dataset(self):
        """
        Extrait l'historique des saisons clôturées depuis Supabase 
        pour construire la matrice d'apprentissage (X -> Y).
        """
        seasons = Season.objects.filter(status="closed").prefetch_related('plot__weather_records', 'prediction_report')
        
        records = []
        for s in seasons:
            report = getattr(s, 'prediction_report', None)
            if report and report.features_snapshot:
                feat = report.features_snapshot
                records.append({
                    "season_id": s.id,
                    "year": s.start_date.year if s.start_date else 2025,
                    "precip": feat.get("accumulated_precip_mm", 0.0),
                    "temp": feat.get("average_temperature_c", 0.0),
                    "humidity": feat.get("average_humidity", 0.2), # Valeur par défaut si absent
                    "ndvi": feat.get("average_ndvi", 0.4)          # Valeur par défaut si absent
                })
        
        if len(records) < 3:
            return None, None # Pas assez de données historiques

        df = pd.DataFrame(records)
        df = df.sort_values(by="year")

        # --- CONCEPTION DES FEATURES (X) ET CIBLES (Y) ---
        # Pour chaque saison t, on essaie de prédire ses paramètres à partir de la saison précédente (t-1)
        df['prev_precip'] = df['precip'].shift(1)
        df['prev_temp'] = df['temp'].shift(1)
        df['prev_humidity'] = df['humidity'].shift(1)
        df['prev_ndvi'] = df['ndvi'].shift(1)
        
        df = df.dropna() # Supprimer la première ligne qui n'a pas de passée

        if len(df) < 2:
            return None, None

        X = df[['prev_precip', 'prev_temp', 'prev_humidity', 'prev_ndvi']]
        Y = df[['precip', 'temp', 'humidity', 'ndvi']] # Les 4 paramètres à prédire

        return X, Y

    def train(self):
        """
        Entraîne le modèle de régression multi-sorties avec Random Forest.
        """
        X, Y = self.prepare_dataset()
        if X is None or Y is None:
            return {"status": "error", "message": "Données historiques insuffisantes pour l'apprentissage."}

        # Modèle multi-sorties (permet de prédire les 4 paramètres climatiques en même temps)
        base_model = RandomForestRegressor(n_estimators=50, random_state=42)
        model = MultiOutputRegressor(base_model)
        
        model.fit(X, Y)
        
        # Sauvegarde du modèle sur le disque
        joblib.dump(model, self.model_path)
        
        score = model.score(X, Y)
        return {
            "status": "success",
            "r2_score": round(float(score), 2),
            "samples_trained": len(X)
        }

    def predict_next_season(self, current_season_data):
        """
        Prédit les 4 paramètres de la saison à venir (Y) 
        en se basant sur les données de la saison actuelle (X).
        
        current_season_data = {"precip": 400.0, "temp": 30.0, "humidity": 0.2, "ndvi": 0.4}
        """
        if not os.path.exists(self.model_path):
            # Fallback si le modèle n'est pas encore entraîné : on retourne les données brutes adaptées
            return {
                "mode": "fallback_brut",
                "prediction": {
                    "precip_prevue_mm": current_season_data.get("precip", 400.0),
                    "temp_prevue_c": current_season_data.get("temp", 30.0),
                    "humidity_prevue": current_season_data.get("humidity", 0.2),
                    "ndvi_prevu": current_season_data.get("ndvi", 0.4)
                }
            }

        model = joblib.load(self.model_path)
        
        X_new = np.array([[
            current_season_data.get("precip", 0),
            current_season_data.get("temp", 0),
            current_season_data.get("humidity", 0),
            current_season_data.get("ndvi", 0)
        ]])

        pred = model.predict(X_new)[0]

        return {
            "mode": "machine_learning",
            "prediction": {
                "precip_prevue_mm": round(float(pred[0]), 2),
                "temp_prevue_c": round(float(pred[1]), 2),
                "humidity_prevue": round(float(pred[2]), 4),
                "ndvi_prevu": round(float(pred[3]), 4)
            }
        }