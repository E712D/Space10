from rest_framework import serializers

class AnalyzePlotRequestSerializer(serializers.Serializer):
    plot_id = serializers.IntegerField(help_text="ID de la parcelle à analyser")
    season_label = serializers.CharField(required=False, allow_blank=True, help_text="Libellé optionnel (ex: 2027-A)")
    today = serializers.DateField(required=False, help_text="Date de référence (par défaut : aujourd'hui)")