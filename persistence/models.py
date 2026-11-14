from django.contrib.gis.db import models as gis_models
from django.db import models

class User(models.Model):
    full_name = models.TextField()
    role = models.TextField(
        default='farmer', 
        choices=[('farmer', 'Farmer'), ('relay', 'Relay'), ('advisor', 'Advisor')]
    )
    language = models.TextField(default='fr')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'users'

class Plot(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='plots')
    code = models.TextField(unique=True, null=True, blank=True)
    name = models.TextField()
    centroid = gis_models.PointField(srid=4326) # x = longitude, y = latitude
    boundary = gis_models.PolygonField(srid=4326, null=True, blank=True)
    area_ha = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    soil_texture = models.TextField(null=True, blank=True)
    soil_ph = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    soil_organic_matter_pct = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    slope_pct = models.DecimalField(max_digits=4, decimal_places=1, default=0.0)
    priorities = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'plots'

class Crop(models.Model):
    code = models.TextField(primary_key=True)
    name_fr = models.TextField()
    name_en = models.TextField()
    category = models.TextField()
    water_need = models.TextField()
    drought_tolerance = models.TextField()
    heat_tolerance = models.TextField()
    erosion_protection = models.TextField()
    nitrogen_balance = models.TextField()
    cycle_days = models.IntegerField()
    is_multi_season = models.BooleanField(default=False)
    sensitive_start_das = models.IntegerField(null=True, blank=True)
    sensitive_end_das = models.IntegerField(null=True, blank=True)
    source_note = models.TextField(default='indicative values - to be validated')

    class Meta:
        db_table = 'crops'

class WeatherDaily(models.Model):
    plot = models.ForeignKey(Plot, on_delete=models.CASCADE, related_name='weather_records')
    obs_date = models.DateField()
    tmax_c = models.FloatField(null=True, blank=True)
    tmin_c = models.FloatField(null=True, blank=True)
    tmean_c = models.FloatField(null=True, blank=True)
    precip_mm = models.FloatField(null=True, blank=True)
    rh_pct = models.FloatField(null=True, blank=True)
    solar_mj_m2 = models.FloatField(null=True, blank=True)
    sm_surface = models.FloatField(null=True, blank=True)
    sm_root = models.FloatField(null=True, blank=True)
    et0_mm = models.FloatField(null=True, blank=True)
    ndvi = models.FloatField(null=True, blank=True)
    sources = models.JSONField(default=dict)
    ingested_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'weather_daily'
        unique_together = ('plot', 'obs_date')

class Season(models.Model):
    """Modèle représentant une saison agricole liée à une parcelle."""
    plot = models.ForeignKey(Plot, on_delete=models.CASCADE, related_name="seasons")
    label = models.CharField(max_length=20, verbose_name="Libellé de saison (ex: 2027-A)")
    start_date = models.DateField(verbose_name="Date de début")
    end_date = models.DateField(verbose_name="Date de fin")
    lock_date = models.DateField(verbose_name="Date de verrouillage")
    status = models.CharField(max_length=20, default="open", verbose_name="Statut (open / locked)")

    class Meta:
        db_table = "persistence_season"
        unique_together = ("plot", "label")

    def __str__(self):
        return f"Saison {self.label} (Parcelle {self.plot_id})"

class StrategicReport(models.Model):
    """Modèle pour restituer le bilan stratégique textuel en français (<= 150 mots)."""
    season = models.OneToOneField(Season, on_delete=models.CASCADE, related_name="strategic_report")
    content = models.TextField(help_text="Bilan stratégique textuel en français (<= 150 mots)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'strategic_reports'

    def __str__(self):
        return f"Bilan stratégique - Saison {self.season.label}"

class PredictionReport(models.Model):
    """Stocke le rapport de prédiction figé à la date de verrouillage (lock_date)."""
    season = models.OneToOneField('Season', on_delete=models.CASCADE, related_name='prediction_report')
    plot = models.ForeignKey(Plot, on_delete=models.CASCADE, related_name='prediction_reports')
    
    features_snapshot = models.JSONField(verbose_name="Caractéristiques météo/sol utilisées au moment du gel")
    recommendations_snapshot = models.JSONField(verbose_name="Recommandations et scores générés")
    
    locked_at = models.DateTimeField(auto_now_add=True, verbose_name="Date et heure du verrouillage")

    class Meta:
        db_table = 'prediction_reports'

    def __str__(self):
        return f"Rapport figé - Saison {self.season.label} (Parcelle {self.plot_id})"


class ModelVersion(models.Model):
    """Enregistre les versions de modèles Edge AI / ML entraînées."""
    version_tag = models.CharField(max_length=50, unique=True, verbose_name="Tag de version (ex: v1.2.0)")
    file_path = models.CharField(max_length=255, verbose_name="Chemin du fichier du modèle")
    metrics = models.JSONField(default=dict, help_text="Métriques (précision, RMSE, F1-score, etc.)")
    is_active = models.BooleanField(default=False, verbose_name="Modèle actif en production")
    trained_at = models.DateTimeField(auto_now_add=True, verbose_name="Date d'entraînement")

    class Meta:
        db_table = 'model_versions'

    def __str__(self):
        status = "Actif" % self.is_active if self.is_active else "Inactif"
        return f"Modèle {self.version_tag} ({status})"