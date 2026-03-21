from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("management", "0004_alter_project_options_alter_team_options_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Screenshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("image", models.ImageField(upload_to="screenshots/%Y/%m/%d/")),
                ("capture_source", models.CharField(choices=[("screen-share", "Screen Share")], default="screen-share", max_length=20)),
                ("captured_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("project", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="screenshots", to="management.project")),
                ("time_entry", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="screenshots", to="management.timeentry")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="screenshots", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-captured_at"],
            },
        ),
        migrations.AddIndex(
            model_name="screenshot",
            index=models.Index(fields=["user", "captured_at"], name="management_s_user_id_e7e6c0_idx"),
        ),
        migrations.AddIndex(
            model_name="screenshot",
            index=models.Index(fields=["time_entry", "captured_at"], name="management_s_time_en_0219b6_idx"),
        ),
        migrations.AddIndex(
            model_name="screenshot",
            index=models.Index(fields=["project", "captured_at"], name="management_s_project_6ece43_idx"),
        ),
    ]
