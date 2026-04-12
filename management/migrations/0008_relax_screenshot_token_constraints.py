from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("management", "0007_add_image_blob_if_missing"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='management_screenshot' AND column_name='access_token'
                ) THEN
                    ALTER TABLE management_screenshot ALTER COLUMN access_token DROP NOT NULL;
                END IF;

                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='management_screenshot' AND column_name='refresh_token'
                ) THEN
                    ALTER TABLE management_screenshot ALTER COLUMN refresh_token DROP NOT NULL;
                END IF;

                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='management_screenshot' AND column_name='token_type'
                ) THEN
                    ALTER TABLE management_screenshot ALTER COLUMN token_type DROP NOT NULL;
                END IF;

                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='management_screenshot' AND column_name='expires_in'
                ) THEN
                    ALTER TABLE management_screenshot ALTER COLUMN expires_in DROP NOT NULL;
                END IF;
            END $$;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]