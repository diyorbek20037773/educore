"""Transliteration golden corpus (AC1.3) and text helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from apps.core.text import normalize_uzbek_apostrophes, slugify_uz, word_count
from apps.core.translit import html_to_cyrillic, is_mostly_cyrillic, to_cyrillic, to_latin

CORPUS = [
    tuple(line.split("\t"))
    for line in (Path(__file__).parent / "data" / "translit_corpus.tsv")
    .read_text(encoding="utf-8")
    .splitlines()
    if line.strip()
]


def test_corpus_has_at_least_200_words() -> None:
    assert len(CORPUS) >= 200


@pytest.mark.parametrize(("latin", "cyrillic"), CORPUS)
def test_golden_pair(latin: str, cyrillic: str) -> None:
    assert to_cyrillic(latin) == cyrillic
    assert to_latin(cyrillic) == latin


def test_round_trip_on_whole_corpus_as_one_text() -> None:
    latin_text = " ".join(lat for lat, _ in CORPUS)
    assert to_latin(to_cyrillic(latin_text)) == latin_text


def test_sentence_with_punctuation_and_case() -> None:
    text = "IIV Akademiyasi kursantlari sport musobaqasida gʻolib boʻldi!"
    assert to_cyrillic(text) == "ИИВ Академияси курсантлари спорт мусобақасида ғолиб бўлди!"


def test_ascii_apostrophes_are_normalized_before_transliteration() -> None:
    assert to_cyrillic("O'zbekiston, g‘alaba, ta'lim") == "Ўзбекистон, ғалаба, таълим"


def test_urls_emails_mentions_hashtags_untouched() -> None:
    text = "Batafsil: https://akadmvd.uz/news?id=5 info@akadmvd.uz @akadmvduz #qabul2026 xabar"
    out = to_cyrillic(text)
    for token in ("https://akadmvd.uz/news?id=5", "info@akadmvd.uz", "@akadmvduz", "#qabul2026"):
        assert token in out
    assert out.endswith("хабар")


def test_html_only_text_nodes_change() -> None:
    html = '<p>Yangi <a href="https://t.me/fvvakad_uz">kanal</a></p>'
    assert html_to_cyrillic(html) == '<p>Янги <a href="https://t.me/fvvakad_uz">канал</a></p>'


def test_cyrillic_query_normalization() -> None:
    assert to_latin("Тошкент шаҳрида қабул") == "Toshkent shahrida qabul"


def test_script_detection() -> None:
    assert is_mostly_cyrillic("Тошкент шаҳрида")
    assert not is_mostly_cyrillic("Toshkent shahrida")
    assert not is_mostly_cyrillic("123 !!!")


def test_apostrophe_normalization() -> None:
    assert normalize_uzbek_apostrophes("o'qish, g`oya, ma’lumot") == "oʻqish, gʻoya, maʼlumot"
    assert normalize_uzbek_apostrophes("'quoted'") == "'quoted'"


def test_slugify_uz() -> None:
    assert slugify_uz("Oʻzbekiston yoʻllari: 2026-yil!") == "ozbekiston-yollari-2026-yil"
    assert slugify_uz("Тошкент шаҳри") == "toshkent-shahri"


def test_word_count() -> None:
    assert word_count("Bir, ikki uch.") == 3
