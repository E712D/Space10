from django.db import migrations


CROPS = [
    ("maize", "Maïs", "Maize", "cereal", "medium", "medium", "medium", "medium", "demanding", 110, False),
    ("rice", "Riz pluvial", "Rainfed rice", "cereal", "high", "low", "medium", "medium", "demanding", 120, False),
    ("sorghum", "Sorgho", "Sorghum", "cereal", "low", "high", "high", "medium", "neutral", 110, False),
    ("cassava", "Manioc", "Cassava", "tuber", "medium", "high", "high", "high", "neutral", 300, False),
    ("yam", "Igname", "Yam", "tuber", "high", "medium", "medium", "high", "demanding", 240, False),
    ("groundnut", "Arachide", "Groundnut", "legume", "medium", "medium", "medium", "high", "fixer", 100, False),
    ("cowpea", "Niebe", "Cowpea", "legume", "low", "high", "high", "high", "fixer", 75, False),
    ("soybean", "Soja", "Soybean", "legume", "medium", "medium", "medium", "medium", "fixer", 100, False),
    ("mucuna", "Mucuna", "Mucuna", "cover", "medium", "high", "high", "high", "fixer", 120, True),
]


def seed_crops(apps, schema_editor):
    Crop = apps.get_model("persistence", "Crop")
    for row in CROPS:
        (
            code, name_fr, name_en, category, water_need, drought_tolerance,
            heat_tolerance, erosion_protection, nitrogen_balance, cycle_days,
            is_multi_season,
        ) = row
        Crop.objects.update_or_create(
            code=code,
            defaults={
                "name_fr": name_fr,
                "name_en": name_en,
                "category": category,
                "water_need": water_need,
                "drought_tolerance": drought_tolerance,
                "heat_tolerance": heat_tolerance,
                "erosion_protection": erosion_protection,
                "nitrogen_balance": nitrogen_balance,
                "cycle_days": cycle_days,
                "is_multi_season": is_multi_season,
                "source_note": "Catalogue initial Space10 a valider localement",
            },
        )


def unseed_crops(apps, schema_editor):
    apps.get_model("persistence", "Crop").objects.filter(
        source_note="Catalogue initial Space10 a valider localement"
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("persistence", "0004_modelversion"),
    ]

    operations = [
        migrations.RunPython(seed_crops, unseed_crops),
    ]
