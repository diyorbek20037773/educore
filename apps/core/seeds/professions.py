"""Seed data: professions (kasblar) — ≥ 20 realistic drafts, all `needs_verification=True` (SPEC §12).

Each entry: slug, name, icon, institutions (abbreviations), summary, responsibilities, requirements, work places.
Shared texts (education path, rank system, salary note) are filled per institution by the seeding service.
"""

from __future__ import annotations

from typing import Any

PROFESSIONS: list[dict[str, Any]] = [
    {
        "slug": "yongin-xavfsizligi-muhandisi",
        "name": "Yongʻin xavfsizligi muhandisi",
        "icon": "flame",
        "institutions": ["FVV"],
        "summary": "Binolar va inshootlarda yongʻin xavfini baholaydi, profilaktik choralarni loyihalaydi.",
        "responsibilities": "Yongʻin xavfsizligi talablariga rioya etilishini tekshirish; loyihalarni ekspertizadan "
        "oʻtkazish; yongʻinga qarshi tizimlarni sinovdan oʻtkazish; aholiga yoʻriqnoma berish.",
        "requirements": "Fizika va kimyo boʻyicha puxta bilim, texnik chizmalarni oʻqiy olish, masʼuliyat.",
        "work_places": "Favqulodda vaziyatlar vazirligi boʻlinmalari, davlat yongʻin nazorati organlari.",
    },
    {
        "slug": "qutqaruvchi",
        "name": "Qutqaruvchi",
        "icon": "life-buoy",
        "institutions": ["FVV"],
        "summary": "Favqulodda vaziyatlarda odamlarni qutqaradi va birinchi yordam koʻrsatadi.",
        "responsibilities": "Qidiruv-qutqaruv ishlarini olib borish; zarar koʻrganlarga birinchi tibbiy yordam "
        "koʻrsatish; maxsus texnika va jihozlardan foydalanish.",
        "requirements": "Yuqori jismoniy tayyorgarlik, stressga chidamlilik, jamoada ishlay olish.",
        "work_places": "Qutqaruv otryadlari, tezkor qidiruv-qutqaruv boʻlinmalari.",
    },
    {
        "slug": "favqulodda-vaziyatlar-dispetcheri",
        "name": "Favqulodda vaziyatlar dispetcheri",
        "icon": "radio",
        "institutions": ["FVV"],
        "summary": "Chaqiruvlarni qabul qiladi va kuch-vositalarni voqea joyiga yoʻnaltiradi.",
        "responsibilities": "112 xizmatiga kelgan chaqiruvlarni qayd etish; boʻlinmalar harakatini muvofiqlashtirish; "
        "vaziyat haqida tezkor axborot tayyorlash.",
        "requirements": "Tez qaror qabul qilish, aniq nutq, axborot tizimlari bilan ishlash koʻnikmasi.",
        "work_places": "Yagona navbatchilik-dispetcherlik xizmatlari, inqiroz boshqaruv markazlari.",
    },
    {
        "slug": "ekologik-nazorat-inspektori",
        "name": "Ekologik nazorat inspektori",
        "icon": "leaf",
        "institutions": ["FVV", "JXU"],
        "summary": "Texnogen va ekologik xavflarni kuzatadi, qoidabuzarliklarning oldini oladi.",
        "responsibilities": "Xavfli obyektlarni monitoring qilish; ekologik talablar bajarilishini nazorat qilish; "
        "xulosalar tayyorlash.",
        "requirements": "Ekologiya va kimyo asoslari, huquqiy hujjatlar bilan ishlash.",
        "work_places": "Nazorat inspeksiyalari, monitoring markazlari.",
    },
    {
        "slug": "tergovchi",
        "name": "Tergovchi",
        "icon": "search",
        "institutions": ["IIV", "HMQA"],
        "summary": "Jinoyat ishlarini tergov qiladi, dalillarni toʻplaydi va baholaydi.",
        "responsibilities": "Tergov harakatlarini oʻtkazish; guvohlarni soʻroq qilish; ekspertizalar tayinlash; "
        "ish materiallarini sudga tayyorlash.",
        "requirements": "Jinoyat va jinoyat-protsessual huquqini chuqur bilish, mantiqiy fikrlash, xolislik.",
        "work_places": "Ichki ishlar organlarining tergov boʻlinmalari, prokuratura organlari.",
    },
    {
        "slug": "tezkor-qidiruv-xodimi",
        "name": "Tezkor-qidiruv xodimi",
        "icon": "radar",
        "institutions": ["IIV"],
        "summary": "Jinoyatlarni ochish va oldini olish uchun tezkor-qidiruv tadbirlarini oʻtkazadi.",
        "responsibilities": "Tezkor maʼlumotlarni toʻplash va tahlil qilish; qidiruvdagi shaxslarni aniqlash; "
        "tergov bilan hamkorlik qilish.",
        "requirements": "Kuzatuvchanlik, jismoniy tayyorgarlik, qonunchilikni bilish.",
        "work_places": "Jinoyat qidiruv boʻlinmalari, tezkor xizmatlar.",
    },
    {
        "slug": "profilaktika-inspektori",
        "name": "Profilaktika inspektori",
        "icon": "house",
        "institutions": ["IIV", "JXU"],
        "summary": "Mahallada huquqbuzarliklarning oldini olish ishlarini tashkil etadi.",
        "responsibilities": "Aholi bilan profilaktik suhbatlar; ijtimoiy xavfli oilalar bilan ishlash; "
        "mahalla faollari bilan hamkorlik.",
        "requirements": "Muloqot madaniyati, sabr-toqat, huquqiy bilim.",
        "work_places": "Hududiy ichki ishlar boʻlimlari, mahalla profilaktika punktlari.",
    },
    {
        "slug": "patrul-post-xizmati-xodimi",
        "name": "Patrul-post xizmati xodimi",
        "icon": "siren",
        "institutions": ["IIV", "JXU"],
        "summary": "Koʻcha va jamoat joylarida tartibni saqlaydi.",
        "responsibilities": "Patrul yoʻnalishlarida xizmat oʻtash; huquqbuzarliklarga zudlik bilan chora koʻrish; "
        "fuqarolarga yordam berish.",
        "requirements": "Jismoniy chidamlilik, xushmuomalalik, tez qaror qabul qilish.",
        "work_places": "Patrul-post xizmati boʻlinmalari.",
    },
    {
        "slug": "yol-harakati-xavfsizligi-inspektori",
        "name": "Yoʻl harakati xavfsizligi inspektori",
        "icon": "traffic-cone",
        "institutions": ["IIV"],
        "summary": "Yoʻl harakati qoidalariga rioya etilishini nazorat qiladi.",
        "responsibilities": "Yoʻl-transport hodisalarini rasmiylashtirish; profilaktik reydlar; haydovchilar bilan "
        "tushuntirish ishlari.",
        "requirements": "Yoʻl harakati qoidalarini mukammal bilish, eʼtiborlilik.",
        "work_places": "Yoʻl harakati xavfsizligi xizmati boʻlinmalari.",
    },
    {
        "slug": "migratsiya-xizmati-xodimi",
        "name": "Migratsiya xizmati xodimi",
        "icon": "id-card",
        "institutions": ["IIV"],
        "summary": "Fuqarolik va migratsiya masalalari boʻyicha davlat xizmatlarini koʻrsatadi.",
        "responsibilities": "Hujjatlarni rasmiylashtirish; migratsiya qoidalariga rioya etilishini nazorat qilish.",
        "requirements": "Maʼmuriy huquq, xorijiy til asoslari, axborot tizimlari bilan ishlash.",
        "work_places": "Migratsiya va fuqarolikni rasmiylashtirish boʻlimlari.",
    },
    {
        "slug": "kriminalist-ekspert",
        "name": "Kriminalist-ekspert",
        "icon": "fingerprint-pattern",
        "institutions": ["IIV", "HMQA"],
        "summary": "Ashyoviy dalillarni ilmiy usullar bilan tadqiq qiladi.",
        "responsibilities": "Hodisa joyini koʻzdan kechirishda ishtirok etish; daktiloskopik, trasologik va boshqa "
        "ekspertizalar oʻtkazish.",
        "requirements": "Tabiiy fanlar, aniqlik, laboratoriya jihozlari bilan ishlash.",
        "work_places": "Ekspert-kriminalistika markazlari.",
    },
    {
        "slug": "kiberxavfsizlik-mutaxassisi",
        "name": "Kiberxavfsizlik mutaxassisi",
        "icon": "shield-check",
        "institutions": ["IIV", "HMQA", "JXU"],
        "summary": "Axborot tizimlarini himoya qiladi va kiberjinoyatlarga qarshi kurashadi.",
        "responsibilities": "Kiberhujumlarni aniqlash va tahlil qilish; raqamli dalillarni toʻplash; "
        "himoya choralarini joriy etish.",
        "requirements": "Tarmoq texnologiyalari, dasturlash asoslari, analitik fikrlash.",
        "work_places": "Kiberxavfsizlik boʻlinmalari, axborot texnologiyalari xizmatlari.",
    },
    {
        "slug": "it-forensika-mutaxassisi",
        "name": "IT-forensika mutaxassisi",
        "icon": "hard-drive",
        "institutions": ["IIV", "HMQA"],
        "summary": "Kompyuter va mobil qurilmalardan raqamli dalillarni ajratib oladi.",
        "responsibilities": "Raqamli qurilmalarni tekshirish; oʻchirilgan maʼlumotlarni tiklash; ekspert xulosasi "
        "tayyorlash.",
        "requirements": "Operatsion tizimlar, fayl tizimlari va maxsus dasturlarni bilish.",
        "work_places": "Raqamli ekspertiza laboratoriyalari.",
    },
    {
        "slug": "prokuror-yordamchisi",
        "name": "Prokuror yordamchisi",
        "icon": "scale",
        "institutions": ["HMQA"],
        "summary": "Qonunlar ijrosi ustidan nazoratda prokurorga koʻmaklashadi.",
        "responsibilities": "Tekshiruvlar oʻtkazish; murojaatlarni koʻrib chiqish; sudlarda davlat ayblovini "
        "qoʻllab-quvvatlashda ishtirok etish.",
        "requirements": "Oliy yuridik maʼlumot, notiqlik, hujjatlar bilan ishlash madaniyati.",
        "work_places": "Tuman va shahar prokuraturalari.",
    },
    {
        "slug": "huquqshunos",
        "name": "Huquqshunos",
        "icon": "book-open",
        "institutions": ["HMQA", "IIV", "DBQ"],
        "summary": "Tashkilot faoliyatining qonuniyligini taʼminlaydi va huquqiy maslahat beradi.",
        "responsibilities": "Hujjatlarni huquqiy ekspertizadan oʻtkazish; shartnomalar tayyorlash; sudlarda "
        "manfaatlarni himoya qilish.",
        "requirements": "Amaldagi qonunchilikni bilish, yozma nutq madaniyati.",
        "work_places": "Davlat organlarining yuridik xizmatlari.",
    },
    {
        "slug": "bojxona-inspektori",
        "name": "Bojxona inspektori",
        "icon": "package-search",
        "institutions": ["DBQ"],
        "summary": "Tovarlar va transport vositalarini bojxona nazoratidan oʻtkazadi.",
        "responsibilities": "Bojxona deklaratsiyalarini tekshirish; bojxona toʻlovlarini hisoblash; kontrabandaning "
        "oldini olish.",
        "requirements": "Iqtisodiyot va bojxona huquqi asoslari, xorijiy til, diqqat.",
        "work_places": "Bojxona postlari va chegara nazorat punktlari.",
    },
    {
        "slug": "bojxona-kinologi",
        "name": "Bojxona kinologi",
        "icon": "dog",
        "institutions": ["DBQ"],
        "summary": "Xizmat itlari yordamida taqiqlangan moddalarni aniqlaydi.",
        "responsibilities": "Xizmat itlarini tayyorlash va parvarishlash; yuklar va yoʻlovchilarni koʻrikdan "
        "oʻtkazishda ishtirok etish.",
        "requirements": "Hayvonlarga mehr, sabr, jismoniy tayyorgarlik.",
        "work_places": "Bojxona kinologiya markazlari va postlari.",
    },
    {
        "slug": "jamoat-xavfsizligi-inspektori",
        "name": "Jamoat xavfsizligi inspektori",
        "icon": "shield-half",
        "institutions": ["JXU"],
        "summary": "Ommaviy tadbirlar va muhim obyektlarda xavfsizlikni taʼminlaydi.",
        "responsibilities": "Obyektlarni qoʻriqlash rejalarini tuzish; ommaviy tadbirlarda tartibni saqlash; "
        "xavflarni baholash.",
        "requirements": "Harbiy-jismoniy tayyorgarlik, tashkilotchilik.",
        "work_places": "Milliy gvardiya boʻlinmalari, qoʻriqlash xizmatlari.",
    },
    {
        "slug": "sudmed-ekspert-yordamchisi",
        "name": "Sud-tibbiy ekspert yordamchisi",
        "icon": "stethoscope",
        "institutions": ["IIV"],
        "summary": "Sud-tibbiy ekspertizalarni oʻtkazishda ekspertga yordam beradi.",
        "responsibilities": "Namuna olish va saqlash; laboratoriya tahlillarida ishtirok etish; hujjatlarni "
        "rasmiylashtirish.",
        "requirements": "Biologiya va anatomiya asoslari, aniqlik.",
        "work_places": "Sud-tibbiy ekspertiza muassasalari.",
    },
    {
        "slug": "psixolog",
        "name": "Psixolog",
        "icon": "brain",
        "institutions": ["IIV", "JXU", "FVV"],
        "summary": "Xodimlarning psixologik tayyorgarligi va salomatligini qoʻllab-quvvatlaydi.",
        "responsibilities": "Psixologik diagnostika; stressdan keyingi reabilitatsiya; kasbiy tanlovda ishtirok etish.",
        "requirements": "Psixologiya boʻyicha oliy maʼlumot, empatiya, konfidensiallik.",
        "work_places": "Kadrlar va psixologik taʼminot boʻlinmalari.",
    },
    {
        "slug": "fuqaro-muhofazasi-mutaxassisi",
        "name": "Fuqaro muhofazasi mutaxassisi",
        "icon": "umbrella",
        "institutions": ["FVV"],
        "summary": "Aholini va hududlarni favqulodda vaziyatlardan muhofaza qilish tadbirlarini rejalaydi.",
        "responsibilities": "Evakuatsiya rejalarini ishlab chiqish; oʻquv mashgʻulotlari oʻtkazish; xabar berish "
        "tizimlarini nazorat qilish.",
        "requirements": "Tashkilotchilik, rejalashtirish koʻnikmasi.",
        "work_places": "Hokimliklar va korxonalarning fuqaro muhofazasi shtablari.",
    },
]
