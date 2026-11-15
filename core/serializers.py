from django.contrib.gis.geos import Point
from rest_framework import serializers
from persistence.models import Plot, Season, WeatherDaily, Crop, StrategicReport, ModelVersion


class PlotSerializer(serializers.ModelSerializer):
    latitude = serializers.FloatField(write_only=False)
    longitude = serializers.FloatField(write_only=False)

    class Meta:
        model = Plot
        fields = [
            "id",
            "user",
            "code",
            "name",
            "latitude",
            "longitude",
            "boundary",
            "area_ha",
            "soil_texture",
            "soil_ph",
            "soil_organic_matter_pct",
            "slope_pct",
            "priorities",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.centroid:
            data["longitude"] = instance.centroid.x
            data["latitude"] = instance.centroid.y
        return data

    def create(self, validated_data):
        lat = validated_data.pop("latitude")
        lon = validated_data.pop("longitude")
        validated_data["centroid"] = Point(lon, lat, srid=4326)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        lat = validated_data.pop("latitude", None)
        lon = validated_data.pop("longitude", None)
        if lat is not None and lon is not None:
            instance.centroid = Point(lon, lat, srid=4326)
        return super().update(instance, validated_data)


class WeatherDailySerializer(serializers.ModelSerializer):
    class Meta:
        model = WeatherDaily
        fields = [
            "obs_date",
            "tmax_c",
            "tmin_c",
            "tmean_c",
            "precip_mm",
            "rh_pct",
            "solar_mj_m2",
            "sm_surface",
            "sm_root",
            "et0_mm",
            "ndvi",
            "sources",
        ]


class SeasonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Season
        fields = ["id", "label", "start_date", "end_date", "lock_date", "status"]


class CropSerializer(serializers.ModelSerializer):
    class Meta:
        model = Crop
        fields = '__all__'


class StrategicReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = StrategicReport
        fields = '__all__'


class ModelVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModelVersion
        fields = '__all__'


# --- CONTRAT API TERRACI (VERSION FLEXIBLE / PRODUCTION) ---

class TerraCILocalDataSerializer(serializers.Serializer):
    mois_saison = serializers.ListField(
        child=serializers.IntegerField(min_value=1, max_value=12),
        required=False
    )
    culture_actuelle = serializers.CharField(required=False, allow_blank=True)


class TerraCIRequestSerializer(serializers.Serializer):
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)
    
    # Utilisation de JSONField pour accepter de manière souple n'importe quelle structure 
    # de données environnementales (listes simples, tableaux 2D ou 3D) en provenance des sources externes
    donnees_environnementales = serializers.JSONField(required=True)
    
    source_donnees = serializers.CharField(max_length=255, required=False, allow_blank=True)
    local_data = TerraCILocalDataSerializer(required=False)
    priorites = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )