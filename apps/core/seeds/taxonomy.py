"""Seed data: the 16 categories (SPEC §2.6) and starter tags."""

from __future__ import annotations

# (slug, name, icon (lucide), show_in_nav, description)
CATEGORIES: list[tuple[str, str, str, bool, str]] = [
    ("yangiliklar", "Yangiliklar", "newspaper", True, "Muassasalar hayotidagi dolzarb yangiliklar."),
    ("maqolalar", "Maqolalar", "file-text", True, "Tahliliy va keng qamrovli maqolalar."),
    ("talim", "Taʼlim", "graduation-cap", True, "Oʻquv jarayoni, dasturlar va metodika."),
    ("qabul", "Qabul", "clipboard-check", True, "Qabul kvotalari, muddatlari va talablari."),
    ("talabalar", "Talabalar", "users", False, "Talabalar hayoti va yutuqlari."),
    ("kursantlar", "Kursantlar", "shield", False, "Kursantlar tayyorgarligi va xizmati."),
    ("kasblar", "Kasblar", "briefcase", False, "Huquqni muhofaza qilish sohasidagi kasblar."),
    ("tadbirlar", "Tadbirlar", "calendar-days", True, "Konferensiya, seminar va uchrashuvlar."),
    ("motivatsiya", "Motivatsiya", "sparkles", False, "Ilhomlantiruvchi hikoyalar va shaxslar."),
    ("ilm-fan", "Ilm-fan", "flask-conical", False, "Ilmiy tadqiqotlar, dissertatsiyalar va nashrlar."),
    ("xalqaro-hamkorlik", "Xalqaro hamkorlik", "globe", False, "Xorijiy hamkorlar bilan aloqalar."),
    ("sport", "Sport", "trophy", False, "Sport musobaqalari va jismoniy tayyorgarlik."),
    ("manaviyat", "Maʼnaviyat va madaniyat", "landmark", False, "Maʼnaviy-maʼrifiy va madaniy tadbirlar."),
    (
        "rahbariyat",
        "Rahbariyat va tashriflar",
        "building",
        False,
        "Rahbariyat faoliyati va rasmiy tashriflar.",
    ),
    ("elonlar", "Eʼlonlar", "megaphone", False, "Rasmiy eʼlonlar va xabarnomalar."),
    ("tabriklar", "Tabriklar", "party-popper", False, "Bayram va sanalar munosabati bilan tabriklar."),
]

CATEGORY_COLOR = "#1B3A6B"  # single hue for category charts (SPEC §7.4 sequential rule)

# (slug, name)
TAGS: list[tuple[str, str]] = [
    ("qabul-2026", "Qabul 2026"),
    ("kursantlar", "Kursantlar"),
    ("talabalar", "Talabalar"),
    ("ochiq-eshiklar-kuni", "Ochiq eshiklar kuni"),
    ("ilmiy-konferensiya", "Ilmiy konferensiya"),
    ("xalqaro-hamkorlik", "Xalqaro hamkorlik"),
    ("sport", "Sport"),
    ("yongin-xavfsizligi", "Yongʻin xavfsizligi"),
    ("jamoat-tartibi", "Jamoat tartibi"),
    ("bojxona", "Bojxona"),
    ("prokuratura", "Prokuratura"),
    ("malaka-oshirish", "Malaka oshirish"),
]
