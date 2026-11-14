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