from rest_framework import serializers

class AnalyzePlotRequestSerializer(serializers.Serializer):
    plot_id = serializers.IntegerField(help_text="ID de la parcelle à analyser")
    season_label = serializers.CharField(required=False, allow_blank=True, help_text="Libellé optionnel (ex: 2027-A)")
    today = serializers.DateField(required=False, help_text="Date de référence (par défaut : aujourd'hui)")


class TerraCIRecommendationRequestSerializer(serializers.Serializer):
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)
    
    # Remplacement des ListField stricts par JSONField pour accepter de manière souple 
    # n'importe quelle structure (listes simples, 2D ou 3D) en provenance des sources externes
    donnees_environnementales = serializers.JSONField(required=True)
    
    source_donnees = serializers.CharField(
        trim_whitespace=True,
        allow_blank=False,
        help_text="Origine réelle des observations transmises.",
    )
    local_data = serializers.JSONField(required=False, default=dict)
    priorites = serializers.ListField(
        child=serializers.ChoiceField(
            choices=("temoin", "hydrique", "regeneration")
        ),
        required=False,
        default=list,
    )

    def validate_local_data(self, local_data):
        if not isinstance(local_data, dict):
            raise serializers.ValidationError("local_data doit être un objet JSON.")
        return local_data