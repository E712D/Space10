from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("persistence", "0006_seed_bouake_demo_plots")]

    operations = [
        migrations.AlterField(
            model_name="plot",
            name="slope_pct",
            field=models.DecimalField(
                blank=True,
                decimal_places=1,
                default=0.0,
                max_digits=4,
                null=True,
            ),
        ),
    ]
