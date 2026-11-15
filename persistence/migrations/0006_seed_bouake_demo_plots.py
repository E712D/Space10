from django.contrib.gis.geos import Point
from django.db import migrations


DEMO_PLOTS = (
    ("BOU-P001", "Parcelle démonstration Nord Bouaké", 7.6939, -5.0302, 2.4, "loamy", 6.2),
    ("BOU-P002", "Parcelle démonstration Est Bouaké", 7.7050, -5.0150, 1.8, "clay_loam", 6.5),
    ("BOU-P003", "Parcelle démonstration Sud Bouaké", 7.6750, -5.0450, 3.1, "sandy_loam", 5.9),
    ("BOU-P004", "Parcelle démonstration Ouest Bouaké", 7.7200, -5.0600, 2.0, "loamy", 6.7),
)


def seed_bouake_plots(apps, schema_editor):
    User = apps.get_model("persistence", "User")
    Plot = apps.get_model("persistence", "Plot")
    user, _ = User.objects.get_or_create(
        full_name="Compte démonstration Bouaké",
        defaults={"role": "farmer", "language": "fr"},
    )
    for code, name, latitude, longitude, area, texture, ph in DEMO_PLOTS:
        Plot.objects.update_or_create(
            code=code,
            defaults={
                "user": user,
                "name": name,
                "centroid": Point(longitude, latitude, srid=4326),
                "area_ha": area,
                "soil_texture": texture,
                "soil_ph": ph,
                "priorities": ["water_saving", "soil_health"],
            },
        )


class Migration(migrations.Migration):
    dependencies = [("persistence", "0005_seed_crop_catalog")]

    operations = [migrations.RunPython(seed_bouake_plots, migrations.RunPython.noop)]
