from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ("management", "0006_rename_management_s_user_id_e7e6c0_idx_management__user_id_b4054d_idx_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE management_screenshot
                ADD COLUMN IF NOT EXISTS image_blob bytea NULL;
            """,
            reverse_sql="""
                ALTER TABLE management_screenshot
                DROP COLUMN IF EXISTS image_blob;
            """,
        ),
    ]