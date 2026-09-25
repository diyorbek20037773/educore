"""PostgreSQL extensions required by EDUCORE: pgvector, trigram similarity, accent-insensitive search."""

from django.contrib.postgres.operations import CreateExtension, TrigramExtension, UnaccentExtension
from django.db import migrations


class Migration(migrations.Migration):
    initial = True
    dependencies: list[tuple[str, str]] = []

    operations = [
        CreateExtension("vector"),
        TrigramExtension(),
        UnaccentExtension(),
    ]
