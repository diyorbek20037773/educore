"""Seed data: the five institutions, their Telegram sources and contacts (SPEC §12).

Sources checked 2026-09-25: channel titles/about texts on t.me, gov.uz/oz/fvv-akademiya, akademiya.fvv.uz,
akadmvd.uz, proacademy.uz, mgjxu.uz, customs.uz. Everything stays `needs_verification=True` until the
owner confirms it in admin (HA9).
"""

from __future__ import annotations

from typing import Any

INSTITUTIONS: list[dict[str, Any]] = [
    {
        "slug": "fvv-akademiyasi",
        "order": 1,
        "abbreviation": "FVV",
        "kind": "academy",
        "short_name": "FVV Akademiyasi",
        "full_name": "Oʻzbekiston Respublikasi Favqulodda vaziyatlar vazirligi Akademiyasi",
        "parent_body": "Oʻzbekiston Respublikasi Favqulodda vaziyatlar vazirligi",
        "description": (
            "<p>Favqulodda vaziyatlar vazirligi Akademiyasi — favqulodda vaziyatlarning oldini olish va "
            "ularni bartaraf etish, yongʻin xavfsizligi hamda fuqaro muhofazasi sohasi uchun kadrlar "
            "tayyorlaydigan, qayta tayyorlaydigan va malakasini oshiradigan oliy taʼlim muassasasi.</p>"
        ),
        "mission": (
            "<p>Favqulodda vaziyatlarning oldini olish va bartaraf etish tizimi uchun yuqori malakali, "
            "vatanparvar mutaxassislarni tayyorlash.</p>"
        ),
        "website_url": "https://akademiya.fvv.uz",
        "telegram_username": "fvvakad_uz",
        "city": "Toshkent",
        "color": "#E4552F",
        "color_text": "#B93A1E",
    },
    {
        "slug": "iiv-akademiyasi",
        "order": 2,
        "abbreviation": "IIV",
        "kind": "academy",
        "short_name": "IIV Akademiyasi",
        "full_name": "Oʻzbekiston Respublikasi Ichki ishlar vazirligi Akademiyasi",
        "parent_body": "Oʻzbekiston Respublikasi Ichki ishlar vazirligi",
        "description": (
            "<p>Ichki ishlar vazirligi Akademiyasi — ichki ishlar organlari uchun huquqshunos va tezkor "
            "xodimlarni tayyorlaydigan, ularning malakasini oshiradigan yetakchi oliy taʼlim va ilmiy "
            "muassasa.</p>"
        ),
        "mission": (
            "<p>Jamoat tartibini saqlash va huquqbuzarliklarning oldini olish sohasida professional, "
            "qonunga sodiq kadrlarni tayyorlash.</p>"
        ),
        "website_url": "https://akadmvd.uz",
        "telegram_username": "akadmvduz",
        "email": "info@akadmvd.uz",
        "city": "Toshkent",
        "color": "#2B6FD6",
        "color_text": "#1F55B0",
    },
    {
        "slug": "bojxona-instituti",
        "order": 3,
        "abbreviation": "DBQ",
        "kind": "institute",
        "short_name": "Bojxona instituti",
        "full_name": "Oʻzbekiston Respublikasi Davlat bojxona qoʻmitasining Bojxona instituti",
        "parent_body": "Oʻzbekiston Respublikasi Davlat bojxona qoʻmitasi",
        "description": (
            "<p>Bojxona instituti — bojxona organlari xodimlarini tayyorlash, qayta tayyorlash va "
            "malakasini oshirishga ixtisoslashgan oliy taʼlim hamda ilmiy-metodik muassasa.</p>"
        ),
        "mission": "<p>Bojxona ishi sohasida zamonaviy bilim va koʻnikmalarga ega kadrlarni tayyorlash.</p>",
        "website_url": "https://customs.uz",
        "telegram_username": "dbq_bojxona_instituti",
        "address": "Toshkent shahri, Shayxontohur tumani, Qoziobod koʻchasi 2-tor, 118-uy",
        "city": "Toshkent",
        "color": "#1FA463",
        "color_text": "#177A49",
    },
    {
        "slug": "huquqni-muhofaza-qilish-akademiyasi",
        "order": 4,
        "abbreviation": "HMQA",
        "kind": "academy",
        "short_name": "Huquqni muhofaza qilish akademiyasi",
        "full_name": "Oʻzbekiston Respublikasi Huquqni muhofaza qilish akademiyasi",
        "parent_body": "Oʻzbekiston Respublikasi Bosh prokuraturasi",
        "description": (
            "<p>Huquqni muhofaza qilish akademiyasi — prokuratura va boshqa huquqni muhofaza qiluvchi "
            "organlar xodimlarining malakasini oshirish, magistratura va ilmiy tadqiqotlar markazi.</p>"
        ),
        "mission": (
            "<p>Qonuniylikni taʼminlash tizimi uchun yuksak malakali, halol va tashabbuskor rahbar "
            "kadrlarni tayyorlash.</p>"
        ),
        "website_url": "https://proacademy.uz",
        "telegram_username": "thelawenforcementacademy",
        "email": "info@proacademy.uz",
        "phone": "+998 71 202 04 96",
        "city": "Toshkent",
        "color": "#9C4DC4",
        "color_text": "#7A36A0",
    },
    {
        "slug": "jamoat-xavfsizligi-universiteti",
        "order": 5,
        "abbreviation": "JXU",
        "kind": "university",
        "short_name": "Jamoat xavfsizligi universiteti",
        "full_name": "Oʻzbekiston Respublikasi Jamoat xavfsizligi universiteti",
        "parent_body": "Oʻzbekiston Respublikasi Milliy gvardiyasi",
        "description": (
            "<p>Jamoat xavfsizligi universiteti — jamoat xavfsizligi va tartibini taʼminlash sohasi uchun "
            "ofitser kadrlarni tayyorlaydigan oliy taʼlim muassasasi.</p>"
        ),
        "mission": (
            "<p>Jamoat xavfsizligini taʼminlashga qodir, jismonan chiniqqan va maʼnan yetuk ofitserlarni "
            "tarbiyalash.</p>"
        ),
        "website_url": "https://mgjxu.uz",
        "telegram_username": "jamoat_xavfsizligi_universiteti",
        "city": "Toshkent",
        "color": "#0E97A5",
        "color_text": "#0B7381",
    },
]

# Contacts per institution slug: (kind, title, phone, email, hours). Phones are left blank where unknown.
CONTACTS: dict[str, list[tuple[str, str, str, str, str]]] = {
    slug: [
        ("admissions", "Qabul komissiyasi", "", "", "Dushanba–juma, 09:00–18:00"),
        ("press", "Matbuot xizmati", "", "", "Dushanba–juma, 09:00–18:00"),
        ("appeals", "Murojaatlar bilan ishlash boʻlimi", "", "", "Dushanba–juma, 09:00–18:00"),
    ]
    for slug in (
        "fvv-akademiyasi",
        "iiv-akademiyasi",
        "bojxona-instituti",
        "huquqni-muhofaza-qilish-akademiyasi",
        "jamoat-xavfsizligi-universiteti",
    )
}
CONTACTS["huquqni-muhofaza-qilish-akademiyasi"][1] = (
    "press",
    "Matbuot xizmati",
    "+998 71 202 04 96",
    "info@proacademy.uz",
    "Dushanba–juma, 09:00–18:00",
)
CONTACTS["iiv-akademiyasi"][2] = (
    "appeals",
    "Murojaatlar bilan ishlash boʻlimi",
    "",
    "info@akadmvd.uz",
    "Dushanba–juma, 09:00–18:00",
)

# KPI placeholders created for the current academic year with an empty value ("—" on the site).
METRIC_KEYS: tuple[str, ...] = (
    "students",
    "cadets",
    "faculty",
    "programs",
    "graduates",
    "dormitory_places",
    "labs",
    "partners",
)

# Generic signature lines stripped before AI (per-source regexes are editable in admin).
SIGNATURE_PATTERNS: list[str] = [
    r"(?im)^\s*@\w+\s*$",
    r"(?im)^.*rasmiy (telegram )?kanal(i)?.*$",
    r"(?im)^\s*(👉|➡️|🔗)?\s*(obuna boʻling|obuna bo'ling|kanalga obuna).*$",
]
