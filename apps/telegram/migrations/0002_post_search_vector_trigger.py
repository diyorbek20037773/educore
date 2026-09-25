"""Maintain TelegramPost.search_vector in the database (accent-insensitive, `simple` config)."""

from django.db import migrations

FORWARD = """
CREATE OR REPLACE FUNCTION telegram_post_search_vector_update() RETURNS trigger AS $$
BEGIN
    NEW.search_vector := to_tsvector('simple', unaccent(coalesce(NEW.text, '')));
    RETURN NEW;
END
$$ LANGUAGE plpgsql;

CREATE TRIGGER telegram_post_search_vector_trg
    BEFORE INSERT OR UPDATE OF text ON telegram_telegrampost
    FOR EACH ROW EXECUTE FUNCTION telegram_post_search_vector_update();
"""

REVERSE = """
DROP TRIGGER IF EXISTS telegram_post_search_vector_trg ON telegram_telegrampost;
DROP FUNCTION IF EXISTS telegram_post_search_vector_update();
"""


class Migration(migrations.Migration):
    dependencies = [("telegram", "0001_sources_posts_media_outbox")]

    operations = [migrations.RunSQL(FORWARD, REVERSE)]
