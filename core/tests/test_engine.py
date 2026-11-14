from datetime import date
from core.services.season_calendar import current_season, next_season, season_window
from core.services.ml_adapter import MlAdapter
from core.agronomy.catalog import CropSheet, RotationRule, PlotContext
from core.agronomy.engine import recommend_rotations

def run_smoke_test():
    print("--- DÉBUT DU TEST DE VALIDATION (SMOKE TEST) ---")
    
    # 1. Test du Calendrier
    today = date(2027, 4, 15)
    curr = current_season(today)
    nxt = next_season(today)
    print(f"Date du jour : {today}")
    print(f"Saison courante : {curr}")
    print(f"Prochaine saison : {nxt}")
    
    # 2. Test du Moteur Agronomique avec des données factices
    catalog = [
        CropSheet(
            code="maize", name_fr="Maïs", name_en="Maize", category="cereal",
            water_need="medium", drought_tolerance="medium", heat_tolerance="medium",
            erosion_protection="medium", nitrogen_balance="demanding", cycle_days=120
        ),
        CropSheet(
            code="cowpea", name_fr="Niébé", name_en="Cowpea", category="legume",
            water_need="low", drought_tolerance="high", heat_tolerance="high",
            erosion_protection="high", nitrogen_balance="fixer", cycle_days=90
        )
    ]
    
    rules = [
        RotationRule(previous_crop_code="maize", next_crop_code="cowpea", compat=2, rationale_fr="Excellente rotation.")
    ]
    
    plot = PlotContext(
        plot_id=1,
        soil_texture="loam",
        soil_ph=6.5,
        priorities=["water_saving", "soil_health"],
        practiced_crops=["maize"],
        current_crop_code="maize"
    )
    
    prediction_mock = {
        "season": {"label": nxt},
        "season_summary": {
            "features": {
                "water_stress_index": {"value": 0.3},
                "sm_root": {"value": 0.5},
                "erosion_risk_index": {"value": 0.2},
                "heat_stress_days": {"value": 1}
            }
        }
    }
    
    result = recommend_rotations(prediction_mock, plot, catalog, rules, today)
    print("\nRecommandations générées avec succès :")
    for rec in result["recommendations"]:
        print(f"Rang {rec['rank']} : {rec['rotation'][0]['crop_code']} (Score: {rec['score']})")

    print("--- FIN DU TEST : TOUT FONCTIONNE CORRECTEMENT ---")

if __name__ == "__main__":
    run_smoke_test()