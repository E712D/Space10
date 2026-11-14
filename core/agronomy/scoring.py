from .catalog import CropSheet
from .rules import WATER_N, TOL_N, PROT_N, NITRO_N

def clip(val: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Assure qu'une valeur reste bornée entre min_val et max_val."""
    return max(min_val, min(max_val, val))

def compute_climate_score(crop: CropSheet, water_stress_index: float) -> float:
    """Calcule la composante climat (résistance au stress hydrique prévu)."""
    pressure = WATER_N.get(crop.water_need, 0.5) * (1 - 0.5 * TOL_N.get(crop.drought_tolerance, 0.6))
    score = 1 - clip(water_stress_index * pressure / 0.8, 0.0, 1.0)
    return float(score)

def compute_soil_moisture_score(crop: CropSheet, sm_root: float) -> float:
    """Calcule la composante humidité du sol par rapport aux besoins de la culture."""
    water_need_val = WATER_N.get(crop.water_need, 0.5)
    deficiency_factor = clip(max(0.0, 0.45 - sm_root) / 0.45, 0.0, 1.0)
    score = 1 - deficiency_factor * (water_need_val / 0.8)
    return float(clip(score, 0.0, 1.0))

def compute_soil_health_score(crop: CropSheet, rot_term: float) -> float:
    """Calcule la santé du sol (bilan azoté + terme de rotation)."""
    nitro_val = NITRO_N.get(crop.nitrogen_balance, 0.5)
    score = 0.5 * nitro_val + 0.5 * rot_term
    return float(clip(score, 0.0, 1.0))

def compute_erosion_score(crop: CropSheet, erosion_risk_index: float) -> float:
    """Calcule la protection contre l'érosion."""
    prot_val = PROT_N.get(crop.erosion_protection, 0.6)
    score = 1 - erosion_risk_index * (1 - prot_val)
    return float(clip(score, 0.0, 1.0))

def compute_familiarity_score(crop_code: str, plot_context) -> float:
    """Évalue la familiarité de l'agriculteur avec la culture."""
    if crop_code in plot_context.practiced_crops:
        return 1.0
    
    # Vérification si 'near' (même catégorie qu'une culture pratiquée)
    # Note: On s'appuiera sur le catalogue complet pour valider la catégorie si besoin
    return 0.6 # Valeur par défaut 'near' ou 'new' (0.2) gérée finement dans l'engine