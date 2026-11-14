from dataclasses import dataclass, field

@dataclass
class CropSheet:
    code: str
    name_fr: str
    name_en: str
    category: str  # 'cereal', 'legume', 'tuber', 'cover'
    water_need: str  # 'low', 'medium', 'high'
    drought_tolerance: str  # 'low', 'medium', 'high'
    heat_tolerance: str  # 'low', 'medium', 'high'
    erosion_protection: str  # 'low', 'medium', 'high'
    nitrogen_balance: str  # 'fixer', 'neutral', 'demanding'
    cycle_days: int
    is_multi_season: bool = False
    sensitive_start_das: int | None = None
    sensitive_end_das: int | None = None
    source_note: str = "indicative values - to be validated"

@dataclass
class RotationRule:
    previous_crop_code: str
    next_crop_code: str
    compat: int  # entre -2 et 2
    rationale_fr: str

@dataclass
class PlotContext:
    plot_id: int
    soil_texture: str | None  # 'sandy', 'loam', 'silty', 'clay'
    soil_ph: float | None
    priorities: list[str]  # ['water_saving', 'soil_health', etc.]
    practiced_crops: list[str]
    current_crop_code: str | None
    history: list[dict] = field(default_factory=list)