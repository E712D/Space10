from django.contrib.gis.geos import Point
from rest_framework import serializers
from persistence.models import Plot, Season, WeatherDaily, Crop, StrategicReport, ModelVersion


class PlotSerializer(serializers.ModelSerializer):
    latitude = serializers.FloatField(write_only=True, required=True)
    longitude = serializers.FloatField(write_only=True, required=True)
    area_ha = serializers.DecimalField(max_digits=10, decimal_places=2, coerce_to_string=False, allow_null=True, required=False)
    soil_ph = serializers.DecimalField(max_digits=3, decimal_places=1, coerce_to_string=False, allow_null=True, required=False)
    soil_organic_matter_pct = serializers.DecimalField(max_digits=4, decimal_places=1, coerce_to_string=False, allow_null=True, required=False)
    slope_pct = serializers.DecimalField(max_digits=4, decimal_places=1, coerce_to_string=False, allow_null=True, required=False)
    owner_name = serializers.CharField(write_only=True, required=False, default="")
    plot_id = serializers.CharField(source="id", read_only=True)
    crop_history = serializers.SerializerMethodField()
    practiced_crops = serializers.SerializerMethodField()

    class Meta:
        model = Plot
        fields = [
            "id",
            "user",
            "plot_id",
            "code",
            "name",
            "owner_name",
            "latitude",
            "longitude",
            "boundary",
            "area_ha",
            "soil_texture",
            "soil_ph",
            "soil_organic_matter_pct",
            "slope_pct",
            "priorities",
            "crop_history",
            "practiced_crops",
            "created_at",
        ]
        read_only_fields = ["id", "user", "created_at"]

    def get_crop_history(self, instance):
        return []

    def get_practiced_crops(self, instance):
        return []

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["owner_name"] = instance.user.full_name if instance.user_id and instance.user else ""
        if instance.centroid:
            data["longitude"] = instance.centroid.x
            data["latitude"] = instance.centroid.y
        else:
            data["longitude"] = None
            data["latitude"] = None
        return data

    def create(self, validated_data):
        lat = validated_data.pop("latitude")
        lon = validated_data.pop("longitude")
        owner_name = validated_data.pop("owner_name", "").strip() or "Exploitant"
        from persistence.models import User
        validated_data["user"], _ = User.objects.get_or_create(
            full_name=owner_name,
            defaults={"role": "farmer", "language": "fr"},
        )
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
    nitrogen_role = serializers.CharField(source="nitrogen_balance", read_only=True)
    is_cover_crop = serializers.SerializerMethodField()
    water_need_mm = serializers.SerializerMethodField()

    class Meta:
        model = Crop
        fields = [
            "code", "name_fr", "name_en", "category", "water_need",
            "water_need_mm", "drought_tolerance", "heat_tolerance",
            "erosion_protection", "nitrogen_balance", "nitrogen_role",
            "cycle_days", "is_multi_season", "is_cover_crop",
            "sensitive_start_das", "sensitive_end_das", "source_note",
        ]

    def get_is_cover_crop(self, instance):
        return instance.category == "cover"

    def get_water_need_mm(self, instance):
        return {"low": 350, "medium": 550, "high": 800}.get(instance.water_need, None)


class StrategicReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = StrategicReport
        fields = '__all__'


class ModelVersionSerializer(serializers.ModelSerializer):
    version = serializers.CharField(source="version_tag", read_only=True)
    parent_version = serializers.SerializerMethodField()
    trained_until = serializers.SerializerMethodField()
    skill_pct = serializers.SerializerMethodField()
    interval_coverage = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(source="trained_at", read_only=True)

    class Meta:
        model = ModelVersion
        fields = [
            "id", "version_tag", "version", "parent_version", "file_path",
            "metrics", "is_active", "trained_at", "trained_until",
            "skill_pct", "interval_coverage", "created_at",
        ]

    def get_parent_version(self, instance):
        return instance.metrics.get("parent_version") if isinstance(instance.metrics, dict) else None

    def get_trained_until(self, instance):
        return instance.trained_at.date() if instance.trained_at else None

    def get_skill_pct(self, instance):
        return instance.metrics.get("skill_pct") if isinstance(instance.metrics, dict) else None

    def get_interval_coverage(self, instance):
        return instance.metrics.get("interval_coverage") if isinstance(instance.metrics, dict) else None


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