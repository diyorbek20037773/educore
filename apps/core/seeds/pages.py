"""Seed data: static pages and FAQ (SPEC §6.12, §12). Drafts until the owner supplies official texts (HA9)."""

from __future__ import annotations

# (slug, title, body html, show_in_footer, order)
PAGES: list[tuple[str, str, str, bool, int]] = [
    (
        "biz-haqimizda",
        "Biz haqimizda",
        "<p>EDUCORE — Oʻzbekiston Respublikasining beshta huquqni muhofaza qilish taʼlim muassasasining yagona "
        "rasmiy axborot-tahliliy platformasi. Platforma muassasalarning rasmiy Telegram kanallaridagi xabarlarni "
        "real vaqtda yigʻadi, ularni tahririyat standartlari asosida maqolaga aylantiradi va muassasalar, "
        "yoʻnalishlar, qabul, tadbirlar hamda tahliliy koʻrsatkichlarni bir joyda taqdim etadi.</p>"
        "<p>Har bir maqolada asl manba — muassasa nomi va rasmiy Telegram xabariga havola koʻrsatiladi.</p>",
        True,
        1,
    ),
    (
        "aloqa",
        "Aloqa",
        "<p>Platforma faoliyati yuzasidan savol va takliflaringizni «Murojaat» boʻlimi orqali yuborishingiz "
        "mumkin. Muayyan muassasa bilan bogʻliq masalalar boʻyicha muassasa sahifasidagi aloqa maʼlumotlaridan "
        "foydalaning.</p>",
        True,
        2,
    ),
    (
        "maxfiylik-siyosati",
        "Maxfiylik siyosati",
        "<p>Platforma tashrif buyuruvchilarni kuzatuvchi cookie fayllaridan foydalanmaydi. Sahifalarni koʻrish "
        "statistikasi shaxsni aniqlab boʻlmaydigan, har kuni yangilanadigan xesh qiymatlar asosida yuritiladi.</p>"
        "<p>Murojaat shaklida koʻrsatilgan shaxsiy maʼlumotlar faqat murojaatni koʻrib chiqish uchun ishlatiladi, "
        "vakolatli xodimlargagina koʻrinadi va murojaat yopilganidan 24 oy oʻtgach anonimlashtiriladi.</p>",
        True,
        3,
    ),
    (
        "foydalanish-shartlari",
        "Foydalanish shartlari",
        "<p>Platformadagi materiallar muassasalarning rasmiy ochiq manbalariga asoslanadi. Materiallardan "
        "foydalanganda EDUCORE va asl manbaga havola koʻrsatilishi shart.</p>",
        True,
        4,
    ),
    (
        "talabalar",
        "Talabalar",
        "<p>Talabalar hayoti, oʻquv jarayoni, yotoqxona, stipendiya va ilmiy faoliyat haqida foydali "
        "maʼlumotlar.</p>",
        False,
        10,
    ),
    (
        "kursantlar",
        "Kursantlar",
        "<p>Kursantlarning kundalik xizmati, jismoniy va kasbiy tayyorgarligi, taʼtillar va yashash sharoitlari "
        "haqida maʼlumotlar.</p>",
        False,
        11,
    ),
]

# (topic, question, answer)
FAQ: list[tuple[str, str, str]] = [
    (
        "qabul",
        "Hujjatlar qachon qabul qilinadi?",
        "Qabul muddatlari har yili muassasa tomonidan eʼlon qilinadi va «Qabul» boʻlimida eʼlon qilingan sanalar "
        "koʻrsatiladi.",
    ),
    (
        "qabul",
        "Qabul uchun qanday hujjatlar kerak?",
        "Odatda taʼlim toʻgʻrisidagi hujjat, pasport, fotosuratlar va tibbiy maʼlumotnoma talab qilinadi. Aniq "
        "roʻyxat har bir qabul eʼlonida keltiriladi.",
    ),
    (
        "qabul",
        "Qizlar ham oʻqishga kira oladimi?",
        "Koʻpgina yoʻnalishlarda qizlar uchun ham kvotalar ajratiladi. Aniq maʼlumot muassasa qabul komissiyasida.",
    ),
    (
        "qabul",
        "Jismoniy tayyorgarlik sinovi qanday oʻtkaziladi?",
        "Sinov meʼyorlari har bir muassasa tomonidan belgilanadi va qabul eʼlonida eʼlon qilinadi.",
    ),
    (
        "talim",
        "Oʻqish qaysi tillarda olib boriladi?",
        "Asosan oʻzbek tilida, ayrim yoʻnalishlarda rus va ingliz tillarida ham taʼlim beriladi.",
    ),
    (
        "talim",
        "Sirtqi yoki masofaviy taʼlim mavjudmi?",
        "Ayrim magistratura va malaka oshirish dasturlari sirtqi yoki masofaviy shaklda tashkil etiladi.",
    ),
    (
        "kursant",
        "Kursantlar yotoqxonada yashaydimi?",
        "Kunduzgi taʼlimdagi kursantlar odatda muassasa kazarmasi yoki yotoqxonasida yashaydi.",
    ),
    (
        "kursant",
        "Kursantlarga taʼtil beriladimi?",
        "Ha, oʻquv yili davomida qishki va yozgi taʼtillar belgilangan tartibda beriladi.",
    ),
    (
        "talaba",
        "Talabalarga stipendiya toʻlanadimi?",
        "Stipendiya va boshqa ijtimoiy kafolatlar amaldagi qonunchilik va muassasa tartibiga muvofiq belgilanadi.",
    ),
    (
        "talaba",
        "Talabalar ilmiy faoliyat bilan shugʻullana oladimi?",
        "Ha, talabalar ilmiy toʻgaraklar, konferensiyalar va tanlovlarda ishtirok etishlari mumkin.",
    ),
    (
        "kasb",
        "Bitiruvchilar qayerda ishlaydi?",
        "Bitiruvchilar asosan tegishli vazirlik va idoralar tizimida xizmatga tayinlanadi.",
    ),
    (
        "kasb",
        "Kasb tanlashda qaysi boʻlim yordam beradi?",
        "«Kasblar» boʻlimida har bir kasbning vazifalari, talablari va qaysi muassasada oʻqitilishi keltirilgan.",
    ),
    (
        "murojaat",
        "Murojaat qancha muddatda koʻrib chiqiladi?",
        "Murojaatlar qonunchilikda belgilangan muddatlarda, odatda 15 ish kuni ichida koʻrib chiqiladi.",
    ),
    (
        "murojaat",
        "Murojaatim holatini qanday bilaman?",
        "Murojaat yuborilgach berilgan kuzatuv kodi orqali «Murojaatni kuzatish» sahifasida holatni koʻrishingiz "
        "mumkin.",
    ),
    (
        "umumiy",
        "Maqolalar qayerdan olinadi?",
        "Barcha maqolalar muassasalarning rasmiy Telegram kanallaridagi xabarlar asosida tayyorlanadi va manbaga "
        "havola beriladi.",
    ),
    ("umumiy", "Sayt qaysi tillarda ishlaydi?", "Oʻzbek (lotin va kirill), rus va ingliz tillarida."),
]
