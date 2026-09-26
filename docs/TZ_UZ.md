# EDUCORE — Toʻliq texnik topshiriq va tushuntirish (oʻzbek tilida)

> Bu hujjat loyiha egasi (Marjona) uchun yozilgan. Unda butun tizim — nima qurilayotgani, nima uchun aynan
> shunday qurilayotgani, qanday ishlashi, sizdan nima talab qilinishi va Claude Code bilan qanday ishlash
> kerakligi — oddiy tilda, lekin toʻliq tushuntirilgan. Claude Code uchun majburiy texnik hujjatlar ingliz
> tilida `SPEC.md`, `ARCHITECTURE.md`, `AI_PIPELINE.md`, `DEVOPS.md`, `PHASES.md` fayllarida; bu hujjat ularning
> mazmunini oʻzbek tilida ochib beradi. Ikkisi oʻrtasida farq boʻlsa, inglizcha hujjatlar ustun.

---

## 1. Loyiha nima?

**Educore** — Oʻzbekiston Respublikasining beshta huquqni muhofaza qilish taʼlim muassasasining rasmiy
Telegram kanallarini bitta rasmiy veb‑platformaga birlashtiradigan tizim:

| # | Muassasa | Telegram | Sayt rangi |
|---|---|---|---|
| 1 | FVV Akademiyasi (Favqulodda vaziyatlar vazirligi Akademiyasi) | @fvvakad_uz | toʻq sariq `#E4552F` |
| 2 | IIV Akademiyasi (Ichki ishlar vazirligi Akademiyasi) | @akadmvduz | koʻk `#2B6FD6` |
| 3 | Bojxona instituti (Davlat bojxona qoʻmitasi) | @DBQ_BOJXONA_INSTITUTI | yashil `#1FA463` |
| 4 | Huquqni muhofaza qilish akademiyasi | @TheLawEnforcementAcademy | binafsha `#9C4DC4` |
| 5 | Jamoat xavfsizligi universiteti | @jamoat_xavfsizligi_universiteti | moviy‑yashil `#0E97A5` |

Tizim nima qiladi:

1. Beshta kanalni **real vaqtda** kuzatadi. Kanalga yangi post chiqsa, 5 soniya ichida bizning bazaga tushadi
   (matn, rasmlar, video, hujjatlar, koʻrishlar soni va h.k.). Eski postlar ham (har kanaldan 500 tagacha)
   bir marta yuklab olinadi, shunda sayt boʻsh boʻlmaydi.
2. Har bir postni **AI tahririyati** rasmiy uslubdagi maqolaga aylantiradi: sarlavha, kirish (lid), matn, kategoriya,
   teglar, SEO, muqova rasmi. AI **manbada yoʻq faktni qoʻsha olmaydi** — buni alohida "fakt‑tekshiruv" bosqichi
   nazorat qiladi. Postdan tadbir, qabul eʼloni, muvaffaqiyat hikoyasi kabi **strukturali obyektlar** ham
   ajratib olinadi (masalan, "Ochiq eshiklar kuni — 3‑oktabr" avtomatik tadbirlar kalendariga tushadi).
3. Maqola siyosatga koʻra **avtomatik nashr qilinadi** (siz talab qilganingizdek — agent oʻzi tayyorlab saytga joylaydi).
   Shubhali holatlar (fakt‑tekshiruvdan oʻtmagan, xavfli mazmun, ishonch darajasi past) avtomatik nashr
   qilinmaydi — admin paneldagi "Koʻrib chiqish navbati"ga tushadi, muharrir bir tugma bilan tasdiqlaydi.
4. Sayt Times Higher Education uslubida: **dashboard** (KPI plitkalar, grafiklar, jonli lenta), muassasalar
   profillari va taqqoslash, yoʻnalishlar, qabul, talabalar/kursantlar, kasblar, tadbirlar, motivatsiya,
   analitika, murojaat. Toʻrt til: oʻzbek (lotin, asosiy), oʻzbek (kirill), rus, ingliz.
5. Admin panel (muharrirlar uchun): tahririyat navbati, Telegram manbalari monitoringi, AI xarajatlari,
   murojaatlar inboxi, sozlamalar. Ikki bosqichli autentifikatsiya (2FA) majburiy.
6. DevOps: Docker, bitta buyruq bilan deploy, avtomatik zaxira nusxalar, monitoring, ogohlantirishlar
   (Telegram‑bot orqali sizga), xavfsizlik.

Qisqasi: **Telegram → ma'lumotlar ombori → AI → strukturali kontent → rasmiy sayt + dashboard.**

---

## 2. Nima uchun Django (Python)? Telegramdan maʼlumot olishda .NET bilan farqi bormi?

Ikkala texnologiya ham Telegramdan bir xil usulda maʼlumot oladi — **MTProto** (Telegramning oʻz protokoli)
orqali. Python uchun bu kutubxona **Telethon**, C# uchun **WTelegramClient**. Imkoniyatlari bir xil: real
vaqt yangilanishlari, tarix (eski postlar), media yuklab olish, tahrir/oʻchirish hodisalari. Shuning uchun
Telegram qismida farq yoʻq.

Farq boshqa joyda:

| Mezon | Django (tanlandi) | .NET |
|---|---|---|
| Admin panel (tahririyat navbati, manbalar, murojaatlar) | Django Admin tayyor, `django-unfold` bilan zamonaviy koʻrinish — kunlar tejaladi | Noldan yozish kerak (haftalar) |
| AI ekotizimi (Anthropic SDK, embedding modellari, pgvector) | Eng boy, birinchi navbatda Python | Bor, lekin kamroq |
| Tarjima/i18n, sitemap, RSS, FTS qidiruv | Django ichida tayyor | Alohida kutubxonalar |
| Yakka dasturchi uchun kod hajmi | Kam | Koʻp |
| Ishlash tezligi | Bu loyiha uchun yetarli (kesh + Caddy) | Tezroq, lekin bu yerda kerak emas |

Xulosa: Telegram uchun ikkalasi ham bir xil ishlaydi, sizga Django qulay — **Django tanlandi**.

---

## 3. Umumiy arxitektura (soddalashtirilgan)

```
Telegram kanallari (5 ta)
        │  MTProto (Telethon), real vaqt + tarix
        ▼
 INGESTOR (bitta jarayon)  ──► PostgreSQL 17 (+pgvector)  ◄── WEB (Django: sayt, admin, API)
        │  media originallari        │  ▲                          ▲
        ▼                            │  │ outbox hodisalari        │
 Fayl ombori (media)                 ▼  │                          │
                              CELERY ISHCHILARI ──► AI (Anthropic API) — Redis (navbat, kesh, qulflar)
                              (AI, media, statistika, ogohlantirish)
```

Barcha qismlar **bitta Docker obrazidan** ishga tushadi, faqat buyruq har xil: `web`, `worker`, `worker-ingest`,
`beat` (jadval), `ingestor` (Telegram), `migrate` (bir martalik), `caddy` (HTTPS), `db`, `redis`, `backup`.

### 3.1 Muhim qarorlar va sabablari
- **Ingestor faqat bitta.** Bitta Telegram sessiyani ikkita jarayon parallel ishlatsa, Telegram sessiyani
  uzib qoʻyishi yoki postlar ikki marta ishlanishi mumkin. Shuning uchun Redis'da "lider qulfi" bor: ikkinchi
  nusxa ishga tushsa, kutib turadi.
- **Outbox (transaksion "chiqish qutisi").** Post bazaga yozilishi bilan bir xil tranzaksiyada "hodisa" yoziladi.
  AI ishchilari vaqtincha ishlamasa ham hodisa yoʻqolmaydi — ular tiklangach navbatdagi hodisalarni oladi.
- **Idempotentlik.** Har bir post `(manba, telegram_message_id)` boʻyicha unikal — bir xil post ikki marta kelsa
  ham ikkita yozuv/maqola boʻlmaydi. AI bosqichlari ham qayta ishlaganda bir xil natija beradi (kesh).
- **Hech narsa fizik oʻchirilmaydi.** Telegramda post oʻchirilsa, bizda `is_deleted=true` belgisi qoʻyiladi va
  maqola arxivga oʻtadi (sozlanadi). Audit uchun asl JSON saqlanadi.
- **AI hech qachon toʻgʻridan‑toʻgʻri saytga yozmaydi.** U faqat "qoralama" beradi; nashr siyosati (§5.4) qaror qiladi.

---

## 4. Telegram integratsiyasi — batafsil

### 4.1 Qanday ulanamiz?
- Telegramda ikki xil API bor: **Bot API** va **MTProto (client API)**. Bot faqat oʻzi admin boʻlgan kanal
  postlarini oladi. Biz beshta kanalning egasi emasmiz — shuning uchun **oddiy foydalanuvchi akkaunti** bilan
  MTProto orqali ulanamiz (xuddi telefondagi Telegram ilovasi kabi, lekin dasturiy).
- Buning uchun kerak: https://my.telegram.org → "API development tools" → `api_id` va `api_hash`
  (5 daqiqalik ish, bepul). Va **alohida telefon raqami** (haqiqiy SIM, +998; virtual raqam emas). Bu akkaunt
  faqat shu ish uchun: beshta kanalga aʼzo boʻladi, hech kimga yozmaydi. 2FA yoqib qoʻying.
- Birinchi kirish bir marta interaktiv: `make tg-login` → telefon → SMS/ilovadagi kod → (2FA parol).
  Sessiya faylga saqlanadi (`/data/telegram/educore.session`) — bu **parol bilan teng maxfiy fayl**, Git'ga
  tushmaydi, zaxira nusxada shifrlanadi.

### 4.2 Nimalar olinadi?
Har bir post uchun: matn, formatlash (entities), havolalar, xeshteglar, sana, tahrir sanasi, koʻrishlar,
ulashishlar, reaksiyalar, forward maʼlumoti, albom (bir nechta rasm bitta post sifatida), media fayllar
(rasm, video ≤ 200 MB, hujjat ≤ 50 MB, audio), asl postga havola (`https://t.me/kanal/123`), toʻliq xom JSON.

### 4.3 Real vaqt, tahrir, oʻchirish
- Yangi post → 5 soniyada bazada; media yuklab olingach (maksimum 120 s kutiladi) "hodisa" chiqadi → AI boshlanadi.
- Post tahrirlansa → matn/media yangilanadi; agar mazmun oʻzgargan boʻlsa maqola qayta yaratiladi
  (eski versiya tarixda qoladi, saytda "Yangilangan" belgisi).
- Post oʻchirilsa → `is_deleted`, maqola arxivlanadi (saytda 410 sahifa), roʻyxatlardan chiqadi.
- Albom (bir postda 5 ta rasm) → bitta post, 5 ta media.

### 4.4 Ishonchlilik
- **Tarixni yuklash** (`make tg-backfill`): har kanaldan 500 tagacha eski post; sekin, Telegram limitlariga
  hurmat bilan (FloodWait boʻlsa kutadi). Qayta ishga tushirsangiz dublikat boʻlmaydi.
- **Boʻshliqlarni tekshirish** (har 10 daqiqada): oxirgi 100 postni Telegram bilan solishtiradi; oʻtkazib
  yuborilgan boʻlsa oladi; oʻchirilganini aniqlaydi. Telegram bilan faqat ingestor jarayoni gaplashadi — tarix
  yuklash, tekshiruv va koʻrsatkich yangilash buyruqlari unga "soʻrov" (IngestionRequest) sifatida beriladi,
  bajarilishi admin panelda koʻrinadi.
- **Yurak urishi (heartbeat)**: ingestor har 30 s "men tirikman" deb yozadi; 3 daqiqa jim boʻlsa — sizga
  Telegram‑bot orqali ogohlantirish, manbalar "offline" boʻladi; tiklangach "tiklandi" xabari.
- **Yangi kanal qoʻshish** — admin paneldan bitta yozuv; kod oʻzgarmaydi, qayta ishga tushirish shart emas.

### 4.5 Xavflar va choralar
- Telegram avtomatlashtirilgan akkauntni cheklashi mumkin. Chora: alohida haqiqiy raqam, faqat oʻqish, limitlarga
  rioya, "keldi‑ketdi" harakatlar yoʻq. 4 yildan beri shunday ishlatiladigan Telethon loyihalari koʻp.
- Sessiya bekor boʻlsa (masalan, telefonda "barcha qurilmalardan chiqish" bosilsa) — ingestor toʻxtaydi,
  ogohlantirish keladi, `make tg-login` qayta bajariladi; oʻtkazib yuborilgan postlar tiklanadi.

---

## 5. AI tahririyati — batafsil

### 5.1 Bosqichlar (har bir post uchun)
1. **Triaj (qoidalar, AI'siz):** boʻsh, "Assalomu alaykum!", faqat stiker, 12 soʻzdan kam va rasmsiz, xizmat
   xabarlari — oʻtkazib yuboriladi (`skipped`), lekin admin panelda koʻrinadi va majburan ishlatish mumkin.
2. **Tozalash:** kanal imzosi, takroriy havolalar olib tashlanadi; yozuv (lotin/kirill) aniqlanadi.
3. **Tahlil (tez model — Haiku):** til, kontent turi (yangilik/tadbir/qabul/hikoya/eʼlon/tabrik/reklama…),
   kategoriya (16 tadan biri), auditoriya, muhimlik (1–5), shaxslar, tashkilotlar, sanalar; agar tadbir/qabul
   boʻlsa — strukturali maʼlumot (sana, joy, kvota…).
4. **Embedding (mahalliy model, bepul):** matnning "maʼno vektori" — dublikatlarni topish uchun.
5. **Dublikat tekshiruvi:** boshqa muassasa ±72 soat ichida xuddi shu voqeani yozgan boʻlsa (oʻxshashlik ≥ 0.86 va
   AI tasdiqlasa) — yangi maqola yaratilmaydi, mavjud maqolaga **ikkinchi manba** qoʻshiladi ("3 ta muassasa
   xabar berdi"). Yangi fakt boʻlsa maqola bir marta yangilanadi.
6. **Maqola yaratish (asosiy model — Sonnet):** sarlavha ≤ 90 belgi, lid ≤ 220, matn 120–600 soʻz (manba
   hajmiga qarab, "suv" qoʻshilmaydi), SEO, teglar, ishonch darajasi (0–1), muharrirga eslatmalar.
7. **Fakt‑tekshiruv (Haiku):** maqoladagi har bir daʼvo manbada bormi? Yoʻq boʻlsa — bir marta qayta yozdiriladi;
   yana boʻlsa — koʻrib chiqish navbatiga. Xavf belgilari (shaxsiy maʼlumot, voyaga yetmaganlar, ayblanuvchi
   ismlari, siyosiy baho, tibbiy maʼlumot) → hech qachon avtomatik nashr yoʻq.
8. **Media tanlash:** eng katta rasm muqova, qolganlari galereya; video boʻlsa kadr; media boʻlmasa muassasa
   rangidagi standart muqova.
9. **Strukturali obyektlar:** Tadbir, Qabul, Hikoya avtomatik yaratiladi (tekshiruv belgisi bilan); Yoʻnalish/Kasb
   faqat qoralama sifatida (muharrir tasdiqlaydi).
10. **Nashr siyosati** (§5.4) → nashr yoki koʻrib chiqish.
11. **Nashrdan keyin:** kirillcha nusxa (transliteratsiya, AI'siz, bir zumda), rus/ingliz tarjimalari (AI, fon rejimida,
    nashrni ushlab qolmaydi), kesh yangilanadi, sitemap, statistika, muharrirlarga xabar.

### 5.2 AI qanday "aldamasligi" taʼminlanadi?
- Prompt (koʻrsatma) qatʼiy: "manbada yoʻq sana, raqam, ism, lavozim, sabab, natijani qoʻshma"; noaniq joylar
  "xabar berilishicha" bilan.
- Alohida fakt‑tekshiruv bosqichi (boshqa model, boshqa vazifa) — "ikkinchi koʻz".
- Muassasa profili (rasmiy nom, tuzilma) — yagona ruxsat etilgan qoʻshimcha kontekst.
- Har bir maqola ostida **"Manba"** bloki: muassasa nomi + asl Telegram postga havola. Oʻquvchi doim asl xabarni
  koʻra oladi.
- Har bir AI chaqiruvi bazada saqlanadi (model, token, narx, natija) — audit va xarajat nazorati.

### 5.3 Modellar va narx
- Asosiy model: `claude-sonnet-5` (maqola, tarjima). Tez model: `claude-haiku-4-5-20251001` (tahlil, fakt‑tekshiruv).
  Model nomlari faqat `.env` da — kod oʻzgarmasdan almashtiriladi.
- Taxminiy xarajat: **bitta post ≈ $0.05** (tarjimalar bilan), ≈ $0.025 (tarjimasiz). Kuniga 25 post ≈ $1.3 →
  **oyiga ≈ $40**. Dastlabki tarix (5 × 150 post) ≈ $40 bir marta. Kunlik byudjet limiti bor (`AI_DAILY_USD_BUDGET`,
  boshlanishiga $5; tarixni yuklash kuni vaqtincha $50 qilib qoʻyasiz): tugasa, postlar navbatda kutadi, sizga xabar
  keladi, ertasi kuni davom etadi.
- Dasturlash va testlash paytida AI umuman chaqirilmaydi (`AI_PROVIDER=mock` — soxta, bepul provayder).

### 5.4 Nashr siyosati (admin panelda oʻzgartiriladi)
| Rejim | Maʼnosi |
|---|---|
| `auto` (standart) | Fakt‑tekshiruvdan oʻtgan, xavf belgisi yoʻq, ishonch ≥ 0.75, muhimlik ≥ 2, reklama emas → **darhol nashr**. Qolganlari → koʻrib chiqish navbati |
| `review` | Hamma narsa avval muharrirga |
| `off` | Faqat saqlanadi, maqola yaratilmaydi |

Ishlab chiqarishda tizim `review` rejimida boshlanadi (`.env.example` shunday): birinchi 1–2 hafta sifatni koʻring,
"oltin toʻplam" testida kategoriya aniqligi ≥ 90 % boʻlgach admin paneldan `auto` ga oʻting — shundan keyin agent
maqolalarni oʻzi joylaydi.

---

## 6. Sayt tuzilmasi (bo'limlar)

Asosiy menyu: **Bosh sahifa · Muassasalar · Yangiliklar · Taʼlim (Yoʻnalishlar, Qabul, Talabalar, Kursantlar) ·
Kasblar · Tadbirlar · Motivatsiya · Analitika · Murojaat**, qidiruv, til, kunduzgi/tungi rejim.

**Bosh sahifa** — asosiy maqola + 3 ta ikkinchi darajali; 5 ta KPI plitka (30 kunlik mini‑grafik bilan);
**Jonli lenta** (har 30 s yangilanadi, muassasa boʻyicha filtr); 5 muassasa kartasi (mini‑statistika, sparkline);
2 ta grafik (12 oylik faollik dinamikasi — har muassasa oʻz rangida; mavzular taqsimoti); Taʼlim va qabul (ochiq
qabullar uchun sanoq); Kursantlar/talabalar; Kasblar; Tadbirlar; Motivatsiya karuseli; Analitika; Murojaat chaqiruvi.

**Muassasalar** — roʻyxat; profil sahifasi (brend rangi, logotip, KPI, grafiklar, tablar: Umumiy, Yoʻnalishlar,
Qabul, Talabalar va kursantlar, Yangiliklar, Tadbirlar, Aloqa); **Taqqoslash** sahifasi (jadval + grafiklar + radar, CSV).

**Yangiliklar** — filtrli roʻyxat (muassasa, kategoriya, sana), cheksiz aylantirish; maqola sahifasi (muqova,
galereya, teglar, **Manba bloki**, oʻxshash maqolalar). **Maqolalar** — tahliliy/uzun materiallar, haftalik sharh.

**Yoʻnalishlar** — katalog (muassasa/daraja/shakl filtrlari), tafsilot sahifasi. **Qabul** — har muassasa boʻyicha
eʼlon, muddatlar, talablar, hujjatlar, kvota, aloqa, FAQ. **Talabalar** / **Kursantlar** — hub sahifalar (kirish,
FAQ, tegishli yangiliklar, tadbirlar, hikoyalar, foydali kontaktlar).

**Kasblar** — 20+ kasb (masalan: qutqaruvchi, bojxona inspektori, tergovchi, kriminalist, kiberxavfsizlik
mutaxassisi…): tavsif, vazifalar, talablar, qaysi muassasada oʻqiladi, unvon tizimi, ish joylari.

**Tadbirlar** — roʻyxat + oylik kalendar, `.ics` yuklab olish. **Motivatsiya** — muvaffaqiyat hikoyalari (iqtibos,
shaxs, muassasa). **Analitika** — 7 ta interaktiv grafik (faollik, kategoriyalar, taqqoslash, nashr vaqti xaritasi,
Telegram koʻrsatkichlari, trend mavzular, qabul jadvali), filtrlar, jadval koʻrinishi, CSV.

**Murojaat** — forma (muassasa, mavzu, ism, telefon, email, xabar, fayl, rozilik, bot‑himoya), kuzatuv kodi
`EDC-2026-000123`, kuzatuv sahifasi; moderatorlar admin panelda javob beradi, arizachiga email ketadi.

Qoʻshimcha: qidiruv (lotin/kirill farqisiz), RSS (umumiy/muassasa/kategoriya), sitemap, JSON‑LD (SEO), PWA
manifest, 404/410/500/texnik ishlar sahifalari, maxfiylik siyosati.

### 6.1 Dizayn
Rasmiy, premium, "maʼlumot birinchi": toʻq koʻk (`#0B1F3A`) + oq + tilla urgʻu (`#C9A227`), sarlavhalar uchun
serif shrift (Source Serif 4), matn uchun Open Sans (ADR-029: THE bosh sahifasi uslubi — kulrang fon, oq
kartochkalar, qora sarlavha paneli); 12 ustunli toʻr, kartochkalar, yumshoq soyalar; kunduzgi va
tungi rejim; 360 px telefondan boshlab moslashuvchan; WCAG AA (kontrast, klaviatura, ekran oʻquvchilar).
Grafiklar (Apache ECharts): har muassasa **doimiy oʻz rangida** (rang‑ajrata olmaydiganlar uchun ham
tekshirilgan palitra), ikki oʻqli grafiklar yoʻq, har grafikda jadval koʻrinishi va CSV. Lighthouse (mobil)
≥ 90 — majburiy sifat mezoni.

---

## 7. Admin panel (muharrirlar uchun)
- **Dashboard:** bugun kelgan postlar, ishlanganlar, koʻrib chiqish kutayotganlar, nashr qilinganlar, xatolar;
  AI xarajati (bugun/oy, byudjetga nisbatan); ingestor holati (heartbeat, har manba boʻyicha status/kechikish);
  ochiq murojaatlar; 14 kunlik grafik.
- **Tahririyat:** maqolalar (filtrlar, koʻrib chiqish navbati, oldindan koʻrish, asl Telegram matni yonma‑yon),
  amallar: nashr, arxiv, qayta yaratish, qayta tarjima, asosiy qilish, boshqa maqolaga birlashtirish.
- **Telegram:** manbalar (status, hisoblagichlar, tarix yuklash, oʻchirish), postlar (xom JSON, qayta ishlash),
  media, outbox (qayta urinish).
- **AI:** chaqiruvlar (bosqich, model, token, narx, natija), kunlik byudjet, klasterlar.
- **Kontent:** kategoriyalar, teglar, tadbirlar, qabul, yoʻnalishlar, kasblar, hikoyalar, sahifalar, FAQ,
  muassasalar, kontaktlar, koʻrsatkichlar ("tekshirilishi kerak" filtri va ommaviy "tasdiqlash").
- **Murojaatlar:** inbox, status, biriktirish, javob, ichki izoh, CSV, muddati oʻtganlar (15 ish kuni).
- **Sozlamalar:** nashr rejimi, ishonch chegarasi, oʻchirilgan manba siyosati, byudjet, tarjima tillari, kontaktlar;
  foydalanuvchilar va rollar (`admin`, `editor`, `moderator`, `analyst`), 2FA.

---

## 8. Xavfsizlik va maxfiylik
HTTPS majburiy (Caddy avtomatik sertifikat), HSTS, CSP, xavfsiz cookie'lar; admin yoʻli maxfiy + 2FA + 5 marta
notoʻgʻri parolda bloklash; formalar tezlik cheklovi + Turnstile; yuklangan fayllar tekshiriladi; AI matni HTML
tozalagichdan oʻtadi; maxfiy kalitlar faqat `.env` da (Git'ga tushmaydi, Claude Code ham uni ochmaydi);
konteynerlar root'siz; baza va Redis tashqariga ochilmaydi; tashrif statistikasi cookie'siz (kunlik tuzli xesh);
murojaatlardagi shaxsiy maʼlumotlar va biriktirilgan fayllar faqat moderatorlarga koʻrinadi (fayllar ommaviy
media papkasidan tashqarida, alohida himoyalangan joyda saqlanadi) va 24 oydan keyin anonimlashtiriladi;
haftalik zaifliklar tekshiruvi (`pip-audit`, Trivy).

Huquqiy eslatma: Telegram kanallari ommaviy va rasmiy; biz kontentni manba va havola bilan qayta nashr qilamiz.
Shunga qaramay, muassasalardan rasmiy rozilik/xabardorlik olish tavsiya etiladi (ayniqsa rasmlar boʻyicha).

---

## 9. DevOps — qanday ishga tushadi va yashaydi
- **Dasturlash:** `make up` (Docker: baza, Redis, pochta‑test, web, ishchilar) → `make migrate` → `make seed-demo`
  (5 muassasa, kategoriyalar, 20+ kasb, yoʻnalishlar, 40 ta namunaviy post va soxta‑AI maqolalar) → sayt
  http://localhost:8000 da toʻliq ishlaydi — Telegram va AI kalitlarisiz ham.
- **CI (GitHub Actions):** har commit'da lint, testlar (qamrov ≥ 80 % asosiy modullarda), migratsiya tekshiruvi,
  `check --deploy`, xavfsizlik skanerlari, Docker build.
- **Deploy:** `v1.0.0` kabi teg → obraz GHCR'ga → serverga SSH → `docker compose pull && up -d` (avval migratsiya)
  → `healthz` tekshiruvi → muvaffaqiyatsiz boʻlsa avtomatik oldingi versiyaga qaytish → sizga bot xabari.
- **Server:** Ubuntu 24.04, kamida 4 vCPU / 8 GB RAM / 80 GB NVMe; `scripts/server-setup.sh` hammasini
  (Docker, firewall, fail2ban, avtomatik yangilanishlar, swap, vaqt sinxroni) bir marta sozlaydi.
- **Zaxira:** har kuni 03:00 — baza (`pg_dump`), media, Telegram sessiya; shifrlangan; 7 kun serverda, 30 kun
  tashqi S3'da; tiklash skripti va mashq (RUNBOOK'da qayd etiladi).
- **Monitoring:** `/healthz`, `/readyz`, Prometheus metrikalari (ixtiyoriy Grafana), JSON loglar, Sentry (ixtiyoriy),
  ogohlantirishlar Telegram‑bot orqali: ingestor toʻxtadi, manba buzildi, AI byudjeti tugadi, zaxira xatosi,
  deploy natijasi, yangi murojaat, koʻrib chiqish kerak boʻlgan maqola.

---

## 10. Sizdan nima kerak (inson harakati nuqtalari)

| Qachon | Nima | Qayerdan |
|---|---|---|
| 0‑bosqich | Boʻsh GitHub repozitoriy (CI uchun); kompyuterda Node.js ≥ 20 va Chrome (Lighthouse sifat testi uchun) | github.com |
| 2‑bosqich | `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`; alohida telefon raqami; `make tg-login` da kodni kiritish; **siz admin boʻlgan yopiq test‑kanal** (real vaqt testlari uchun) | https://my.telegram.org → API development tools |
| 3‑bosqich | `ANTHROPIC_API_KEY` | https://platform.claude.com (toʻlov usuli bilan) |
| 7‑bosqich (ixtiyoriy) | Cloudflare Turnstile kalitlari (forma himoyasi), ogohlantirish boti tokeni (@BotFather) va sizning chat ID, SMTP (email), Sentry DSN | mos xizmatlar |
| 8‑bosqich | VPS (Ubuntu 24.04), domen (masalan `educore.uz`) va DNS A yozuvi, GitHub secrets (`DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, `GHCR_PAT` — obrazlarni yuklab olish uchun token), zaxira shifrlash uchun `age` ochiq kaliti (maxfiy kalitni oflayn saqlaysiz) | VPS provayder, domen registratori, GitHub |
| 9‑bosqich | "Biz haqimizda", kontaktlar matnlari; yoʻnalishlar/kasblar/koʻrsatkichlarni tekshirib tasdiqlash | muassasalar |

Kalitlarni **siz oʻzingiz** `.env` fayliga yozasiz (namuna: `.env.example`). Claude Code `.env` ni ochmaydi.

---

## 11. Claude Code bilan qanday ishlaysiz — qadam‑baqadam

1. Kompyuterga oʻrnating: Docker Desktop, Git, VS Code, Claude Code (`npm install -g @anthropic-ai/claude-code`
   yoki rasmiy oʻrnatuvchi — https://docs.claude.com/en/docs/claude-code).
2. Boʻsh papka oching (masalan `C:\projects\educore` yoki `~/projects/educore`) va **ushbu toʻplamdagi barcha
   fayllarni** (shu jumladan yashirin `.claude/` papkasini) shu papkaga koʻchiring.
3. VS Code → papkani oching → terminal → `claude` deb yozing.
4. `PROMPT.md` faylining birinchi chiziqdan pastki qismini toʻliq nusxalab, birinchi xabar sifatida yuboring.
5. Claude Code hujjatlarni oʻqiydi, sizga oʻzbekcha qisqa hisobot beradi (nima kerakligini roʻyxat qiladi) va
   0‑bosqichni boshlaydi. U har bosqich oxirida oʻzbekcha hisobot yozadi: nima qilindi, qanday tekshirasiz
   (aniq buyruqlar/URL), keyingi qadam, sizdan nima kerak.
6. U kalit soʻrasa: `.env` ga yozing (`.env.example` dan nusxa olib), keyin unga "davom et" deng.
7. Kontekst toʻlib qolsa yoki yangi kun boshlansa: `claude` → `PROMPT.md` oxiridagi **RESUME** matnini yuboring.
   U `docs/PROGRESS.md` dan qayerda qolganini bilib oladi va davom etadi.
8. `.claude/settings.json` tufayli oddiy buyruqlar (make, uv, docker compose, git, pytest…) tasdiqsiz bajariladi;
   xavfli buyruqlar (volume oʻchirish, force push, `.env` oʻqish) taqiqlangan. Toʻliq avtonomiya uchun
   `claude --dangerously-skip-permissions` ham bor, lekin tavsiya etilmaydi.

Eng muhim tekshiruv vositasi — `docs/PROGRESS.md`: har bir vazifa sana bilan belgilanadi, har bosqichning
qabul mezonlari (AC) dalil bilan yoziladi. Agar u yerda "tick" boʻlmasa — ish tugamagan.

---

## 12. Bosqichlar va taxminiy muddat (bitta dasturchi + Claude Code)

| Bosqich | Mazmuni | Kun |
|---|---|---|
| 0 | Repozitoriy, Docker, sozlamalar, CI skeleti, dizayn poydevori | 0.5 |
| 1 | Barcha modellar, migratsiyalar, boshlangʻich maʼlumotlar, admin | 1.5 |
| 2 | Telegram: real vaqt, tarix, albomlar, media, tahrir/oʻchirish, outbox, monitoring | 3 |
| 3 | AI tahririyati: bosqichlar, dublikatlar, fakt‑tekshiruv, nashr siyosati, tarjimalar, tahririyat navbati | 3 |
| 4 | Sayt: dizayn tizimi, barcha sahifalar, jonli lenta, grafiklar, 4 til, SEO | 5 |
| 5 | Analitika: kunlik agregatlar, 7 grafik, taqqoslash, admin dashboard | 1.5 |
| 6 | Murojaatlar va bildirishnomalar | 1 |
| 7 | Ommaviy API, xavfsizlik, monitoring, ogohlantirishlar | 1.5 |
| 8 | Ishlab chiqarish deploy: compose, Caddy, CI/CD, zaxira, runbook | 1.5 |
| 9 | Tarixni ishlash, kontentni tekshirish, yakuniy QA, topshirish | 1.5 |
| | **Jami** | **≈ 20 ish kuni** |

Yakuniy "tayyor" mezonlari (`CLAUDE.md §10`): sayt domen va HTTPS bilan ishlaydi; 5 manba "live"; yangi post
≤ 60 s da maqola boʻladi; tahrir/oʻchirish aks etadi; har muassasadan ≥ 150 maqola; barcha sahifalar 4 tilda,
Lighthouse ≥ 90; admin toʻliq, 2FA; analitika real maʼlumotda; API hujjatlangan; CI yashil, testlar ≥ 80 %;
zaxira va tiklash mashqi bajarilgan; ogohlantirishlar isbotlangan; hujjatlar toʻliq.

---

## 13. Keyingi bosqichlar (v2 gʻoyalari, hozir doiraga kirmaydi)
Mobil ilova (API tayyor), Bot API orqali kanallarning oʻzi bizga admin huquqi bersa, foydalanuvchi
obunalari/push, sharhlar, reytinglar (THE "Rankings" analogi — muassasalar koʻrsatkichlari asosida),
Kubernetes (faqat yuk oshsa), 50–100 manba (faqat admin paneldagi yozuvlar).

---

## 14. Tez‑tez soʻraladigan savollar
**AI notoʻgʻri maqola yozsa‑chi?** — Fakt‑tekshiruv toʻxtatadi; oʻtib ketsa ham admin panelda bir tugma bilan
arxivlanadi, "Manba" bloki asl xabarni koʻrsatadi, har bir versiya tarixda.
**Telegram akkaunt bloklansa‑chi?** — Tizim toʻxtamaydi (sayt ishlaydi), ogohlantirish keladi, boshqa raqam bilan
`make tg-login` — postlar tiklanadi.
**Internet/server uzilsa‑chi?** — Qayta ulanish avtomatik; oʻtkazib yuborilgan postlar catch‑up va gap‑check bilan
olinadi; hech narsa yoʻqolmaydi (outbox).
**Yana kanal qoʻshish?** — Admin → Telegram sources → yangi yozuv (username + muassasa). 60 soniyada ishlaydi.
**Kod kimniki?** — Sizniki; barcha kod, prompt'lar, hujjatlar repozitoriyda; tashqi bogʻliqliklar faqat ochiq
manbali kutubxonalar va Anthropic API.
