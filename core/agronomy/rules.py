# Pondérations des composantes du score final (somme = 1.00)
WEIGHTS = {
    "climate": 0.30,
    "soil_moisture": 0.15,
    "soil_health": 0.15,
    "erosion": 0.10,
    "familiarity": 0.20,
    "priority": 0.10
}

# Conversion qualitative -> numérique
WATER_N = {"low": 0.2, "medium": 0.5, "high": 0.8}
TOL_N = {"low": 0.2, "medium": 0.6, "high": 1.0}
PROT_N = {"low": 0.2, "medium": 0.6, "high": 1.0}
NITRO_N = {"fixer": 1.0, "neutral": 0.5, "demanding": 0.2}

# Règles de durée et de nouveauté
SEASON_TOLERANCE_DAYS = 30
NOVELTY_MIN_GAIN = 0.15

# Seuils critiques pour les pénalités et alertes
WSI_CRITICAL = 0.6
EROSION_CRITICAL = 0.6
HEAT_DAYS_CRITICAL = 5