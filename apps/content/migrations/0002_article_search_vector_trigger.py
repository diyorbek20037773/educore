"""Maintain Article.search_vector in the database: title (A), lead + ru/en titles (B), body text (C)."""

from django.db import migrations

FORWARD = r"""
CREATE OR REPLACE FUNCTION content_article_search_vector_update() RETURNS trigger AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('simple', unaccent(coalesce(NEW.title_uz, NEW.title, ''))), 'A') ||
        setweight(to_tsvector('simple', unaccent(
            coalesce(NEW.lead_uz, NEW.lead, '') || ' ' || coalesce(NEW.title_ru, '') || ' ' || coalesce(NEW.title_en, '')
        )), 'B') ||
        setweight(to_tsvector('simple', unaccent(
            regexp_replace(coalesce(NEW.body_uz, NEW.body, ''), '<[^>]+>', ' ', 'g')
        )), 'C');
    RETURN NEW;
END
$$ LANGUAGE plpgsql;

CREATE TRIGGER content_article_search_vector_trg
    BEFORE INSERT OR UPDATE ON content_article
    FOR EACH ROW EXECUTE FUNCTION content_article_search_vector_update();
"""

REVERSE = """
DROP TRIGGER IF EXISTS content_article_search_vector_trg ON content_article;
DROP FUNCTION IF EXISTS content_article_search_vector_update();
"""


class Migration(migrations.Migration):
    dependencies = [("content", "0001_articles_events_admissions_stories")]

    operations = [migrations.RunSQL(FORWARD, REVERSE)]
