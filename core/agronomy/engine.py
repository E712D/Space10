from datetime import date
from .catalog import CropSheet, RotationRule, PlotContext
from .rules import WEIGHTS, WSI_CRITICAL, EROSION_CRITICAL, HEAT_DAYS_CRITICAL
from .scoring import (
    compute_climate_score,
    compute_soil_moisture_score,
    compute_soil_health_score,
    compute_erosion_score,
    compute_familiarity_score,
    clip
)

def recommend_rotations(
    prediction: dict,
    plot: PlotContext,
    catalog: list[CropSheet],
    rules: list[RotationRule],
    today: date
) -> dict:
    """
    Moteur agronomique déterministe : évalue les cultures candidates et propose 
    les meilleures rotations sur 1 ou 2 étapes.
    """
    season_info = prediction.get("season", {})
    season_label = season_info.get("label", "2027-A")
    
    # Extraction des résumés de prédiction
    summary_features = prediction.get("season_summary", {}).get("features", {})
    wsi = summary_features.get("water_stress_index", {}).get("value", 0.5)
    if wsi is None: wsi = 0.5
    
    sm_root = summary_features.get("sm_root", {}).get("value", 0.45)
    if sm_root is None: sm_root = 0.45
    
    ero = summary_features.get("erosion_risk_index", {}).get("value", 0.5)
    if ero is None: ero = 0.5
    
    heat_days = summary_features.get("heat_stress_days", {}).get("value", 0)
    if heat_days is None: heat_days = 0

    missing_info = []
    if plot.soil_ph is None:
        missing_info.append({"code": "soil_ph_missing", "text_fr": "Le pH du sol n'est pas renseigné."})
    if plot.soil_texture is None:
        missing_info.append({"code": "soil_texture_missing", "text_fr": "La texture du sol n'est pas renseignée."})

    # Indexation des règles de rotation pour un accès rapide
    rules_dict = {(r.previous_crop_code, r.next_crop_code): r for r in rules}
    
    # Détermination de la culture précédente
    prev_crop = plot.current_crop_code
    if not prev_crop and plot.history:
        prev_crop = plot.history[-1].get("crop_code")

    scored_candidates = []
    
    # Filtrage des candidats (catégories cereal ou legume, non multi-saison, tuber/cover exclus du rôle main)
    candidates = [
        c for c in catalog 
        if c.category in ["cereal", "legume"] and not c.is_multi_season
    ]

    for crop in candidates:
        # 1. Calcul des composantes de score
        climate = compute_climate_score(crop, wsi)
        soil_moisture = compute_soil_moisture_score(crop, sm_root)
        
        # Terme de rotation (compatibilité précédente -> courante)
        rot_term = 0.5
        if prev_crop:
            rule = rules_dict.get((prev_crop, crop.code))
            if rule:
                rot_term = (rule.compat + 2) / 4.0 # Convertit [-2, 2] en [0, 1]
                
        soil_health = compute_soil_health_score(crop, rot_term)
        erosion = compute_erosion_score(crop, ero)
        
        # Familiarité
        if crop.code in plot.practiced_crops:
            familiarity = 1.0
        else:
            # Vérification simple de la catégorie 'near'
            same_cat = any(
                any(c.code == pc and c.category == crop.category for c in catalog)
                for pc in plot.practiced_crops
            )
            familiarity = 0.6 if same_cat else 0.2

        # Priorité de la parcelle
        p_scores = []
        for p in plot.priorities:
            if p == "water_saving":
                p_scores.append(1.0 if crop.water_need == "low" else 0.3)
            elif p == "soil_health":
                p_scores.append(soil_health)
            elif p == "erosion_control":
                p_scores.append(1.0 if crop.erosion_protection == "high" else 0.5)
            elif p == "yield":
                p_scores.append(climate)
            elif p == "low_cost":
                p_scores.append(familiarity)
        priority_score = sum(p_scores) / len(p_scores) if p_scores else 0.5

        # Somme pondérée brute
        raw_score = (
            WEIGHTS["climate"] * climate +
            WEIGHTS["soil_moisture"] * soil_moisture +
            WEIGHTS["soil_health"] * soil_health +
            WEIGHTS["erosion"] * erosion +
            WEIGHTS["familiarity"] * familiarity +
            WEIGHTS["priority"] * priority_score
        )

        # Application des pénalités
        penalties = []
        if prev_crop:
            rule = rules_dict.get((prev_crop, crop.code))
            if rule and rule.compat == -2:
                raw_score -= 0.15
                penalties.append({"code": "same_crop_repeat", "value": 0.15, "detail_fr": rule.rationale_fr})
            elif rule and rule.compat == -1:
                raw_score -= 0.08
                penalties.append({"code": "same_family_repeat", "value": 0.08, "detail_fr": rule.rationale_fr})

        if heat_days >= HEAT_DAYS_CRITICAL and crop.heat_tolerance == "low":
            raw_score -= 0.10
            penalties.append({"code": "heat_risk", "value": 0.10, "detail_fr": "Risque de forte chaleur sur une culture sensible."})

        final_score = clip(raw_score, 0.0, 1.0)

        # Génération des raisons (max 3)
        reasons = []
        if crop.drought_tolerance == "high" and wsi >= 0.4:
            reasons.append({"code": "drought_tolerant", "text_fr": "Culture tolérante à la sécheresse, adaptée au stress hydrique prévu.", "feature_refs": ["water_stress_index", "sm_root"]})
        if crop.nitrogen_balance == "fixer":
            reasons.append({"code": "nitrogen_fixer", "text_fr": "Légumineuse : elle apporte de l'azote au sol.", "feature_refs": []})
        if familiarity == 1.0:
            reasons.append({"code": "already_practiced", "text_fr": "Culture que vous pratiquez déjà.", "feature_refs": []})
        if not reasons:
            reasons.append({"code": "climate_compatible", "text_fr": "Compatible avec les conditions prévues pour la saison.", "feature_refs": ["tmean_c", "precip_mm"]})

        warnings = [{"code": "check_seed_availability", "text_fr": "Vérifier la disponibilité des semences."}]
        if climate < 0.5:
            warnings.append({"code": "high_water_need_under_stress", "text_fr": "Besoin en eau élevé malgré un stress hydrique prévu : prévoir une irrigation ou choisir une autre culture."})

        scored_candidates.append({
            "crop": crop,
            "score": round(final_score, 4),
            "breakdown": {
                "climate": round(climate, 2),
                "soil_moisture": round(soil_moisture, 2),
                "soil_health": round(soil_health, 2),
                "erosion": round(erosion, 2),
                "familiarity": round(familiarity, 2),
                "priority": round(priority_score, 2)
            },
            "penalties": penalties,
            "reasons": reasons[:3],
            "warnings": warnings,
            "familiarity_type": "practiced" if familiarity == 1.0 else ("near" if familiarity == 0.6 else "new")
        })

    # Tri par score décroissant, puis par code alphabétique pour le déterminisme
    scored_candidates.sort(key=lambda x: (-x["score"], x["crop"].code))

    recommendations = []
    for i, cand in enumerate(scored_candidates[:3], start=1):
        crop = cand["crop"]
        
        # Culture de couverture (mucuna) si risque d'érosion élevé
        cover_crop = None
        if ero >= EROSION_CRITICAL:
            cover_crop = {"crop_code": "mucuna", "reason_code": "erosion_high"}

        recommendations.append({
            "rank": i,
            "is_primary": (i == 1),
            "score": cand["score"],
            "familiarity": cand["familiarity_type"],
            "rotation": [
                {"step": 1, "season_label": season_label, "crop_code": crop.code, "role": "main"}
            ],
            "cover_crop": cover_crop,
            "score_breakdown": cand["breakdown"],
            "penalties": cand["penalties"],
            "reasons": cand["reasons"],
            "warnings": cand["warnings"]
        })

    return {
        "schema_version": "1.0",
        "plot_id": plot.plot_id,
        "season_label": season_label,
        "engine_version": "agro-rules-1.0",
        "recommendations": recommendations,
        "missing_info": missing_info,
        "needs_local_check": [
            {"code": "market_outlets", "text_fr": "Vérifier les débouchés auprès d'un conseiller local."},
            {"code": "equipment_compat", "text_fr": "Vérifier la compatibilité du matériel de semis."}
        ]
    }