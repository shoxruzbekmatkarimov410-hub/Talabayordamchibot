"""Barcha vositalar shu yerda sozlanadi. Yangi vosita qo'shish = shu ro'yxatga yozuv qo'shish.

Narxlar: raqobatchi narxi x 0,75 (so'm). "TAXMIN" deb belgilanganlari videoda ko'rinmagan.
kind:  pptx    -> .pptx taqdimot
       longdoc -> bob-bob yoziladigan uzun .docx (referat, mustaqil ish)
       doc     -> bitta so'rovda .docx
       chat    -> tekin AI yordamchi
"""

LANGS = {
    "uz": ("🇺🇿 O'zbekcha", "o'zbek tilida (lotin yozuvida)"),
    "ru": ("🇷🇺 Русский", "rus tilida"),
    "en": ("🇬🇧 English", "ingliz tilida"),
}

PAGES = [
    {"label": "10–15 bet", "pages": 12, "price": 2250},
    {"label": "16–24 bet", "pages": 20, "price": 3400},
    {"label": "25–30 bet", "pages": 28, "price": 4500},
]


def slide_price(n: int) -> int:
    return 2250 if n <= 20 else 2250 + (n - 20) * 375


TOOLS = {
    "slayd": {
        "title": "📊 Slayd", "kind": "pptx", "group": "main", "meta": True, "logo": True,
        "ask": "Taqdimot mavzusini yozing (masalan: Fotosintez jarayoni):",
        "options": [{"label": f"{n} ta slayd · {slide_price(n):,} so'm".replace(",", " "),
                     "count": n, "price": slide_price(n)} for n in (6, 10, 15, 20, 25, 30)],
    },
    "pro_slayd": {  # raqobatchi: 8 000 dan -> 6 000 dan
        "title": "💎 Pro slayd", "kind": "pptx", "group": "main", "pro": True, "meta": True, "logo": True,
        "ask": "Taqdimot mavzusini yozing. Pro slaydda raqamlar, taqqoslash va muhim fakt maketlari bor:",
        "options": [{"label": f"{n} ta slayd", "count": n, "price": 6000 if n <= 20 else 7500} for n in (6, 10, 15, 20, 30)],
    },
    "mustaqil": {
        "title": "📝 Mustaqil ish", "kind": "longdoc", "group": "main", "style": "mustaqil ish", "meta": True,
        "ask": "Mustaqil ish mavzusini yozing:",
        "options": PAGES,
    },
    "referat": {
        "title": "📖 Referat", "kind": "longdoc", "group": "main", "style": "referat", "meta": True,
        "ask": "Referat mavzusini yozing:",
        "options": PAGES,
    },
    "insho": {
        "title": "✍️ Insho", "kind": "doc", "group": "main",
        "ask": "Insho mavzusini yozing:",
        "extra": "Insho tuzilmasi: kirish, 2–3 asosiy fikr (dalillar bilan), xulosa. Badiiy-ilmiy uslub.",
        "options": [{"label": f"{i} varaq", "words": 250 * i, "price": p}
                    for i, p in zip(range(1, 6), (1500, 1900, 2250, 2600, 3000))],
    },
    "test": {
        "title": "✅ Test yaratuvchi", "kind": "doc", "group": "main",
        "ask": "Test mavzusini yozing:",
        "extra": "Ko'p variantli test (A, B, C, D). Har bir savol raqamlansin. Oxirida 'Javoblar kaliti' bo'limi.",
        "options": [{"label": "10 ta savol", "words": 450, "price": 2250},
                    {"label": "20 ta savol", "words": 900, "price": 3000},
                    {"label": "30 ta savol", "words": 1350, "price": 3750}],
    },
    "maqola": {
        "title": "📰 Maqola", "kind": "doc", "group": "more",
        "ask": "Maqola mavzusini yozing:",
        "extra": "Professional maqola: jozibali sarlavha, kirish, bo'limlar (## sarlavhalar bilan), xulosa.",
        "options": [{"label": "~800 so'z", "words": 800, "price": 3000},
                    {"label": "~1500 so'z", "words": 1500, "price": 4500}],
    },
    "dars_rejasi": {
        "title": "🎓 Dars rejasi", "kind": "doc", "group": "more",
        "ask": "Dars mavzusi, sinf/kursni yozing:",
        "extra": "Dars rejasi: maqsad, vazifalar, jihozlar, dars bosqichlari (vaqt bilan, jadvalda), baholash, uyga vazifa.",
        "options": [{"label": "Standart", "words": 700, "price": 3000}],
    },
    "kalitlar": {
        "title": "🔑 Kalitlar (keys)", "kind": "doc", "group": "more",
        "ask": "Keys uchun fan va mavzuni yozing:",
        "extra": "Vaziyatli topshiriq (keys): vaziyat tavsifi, 5 ta savol, yechim namunasi.",
        "options": [{"label": "Standart", "words": 900, "price": 4500}],
    },
    "krossvord": {
        "title": "🧩 Krossvord", "kind": "crossword", "group": "more",
        "ask": "Krossvord mavzusini yozing:",
        "options": [{"label": "Katakli krossvord (~15 so'z)", "price": 1500}],
    },
    "flesh": {
        "title": "🗂 Flesh kartalar", "kind": "doc", "group": "more",
        "ask": "Flesh kartalar mavzusini yozing:",
        "extra": "20 ta flesh karta. Jadval: | № | Atama yoki savol | Javob |.",
        "options": [{"label": "20 ta karta", "words": 500, "price": 1500}],
    },
    "glossariy": {  # TAXMIN narx
        "title": "📚 Glossariy", "kind": "doc", "group": "more",
        "ask": "Glossariy mavzusini yozing:",
        "extra": "25 ta atama va ularning qisqa ta'rifi, alifbo tartibida.",
        "options": [{"label": "25 ta atama", "words": 700, "price": 1500}],
    },
    "rezyume": {  # TAXMIN narx
        "title": "💼 Rezyume", "kind": "doc", "group": "more", "academic": False,
        "ask": "Ma'lumotlaringizni yozing: ism, ta'lim, tajriba, ko'nikmalar, qaysi lavozimga:",
        "extra": "Professional rezyume (CV). Faqat berilgan ma'lumotdan foydalaning, yo'q narsani to'qimang.",
        "options": [{"label": "Standart", "words": 400, "price": 2250}],
    },
    "tarjimon": {  # TAXMIN narx
        "title": "🌐 Tarjimon", "kind": "doc", "group": "more", "academic": False, "tpl": "translate", "max_len": 6000,
        "ask": "Tarjima qilinadigan matnni yozing yoki joylang. Pastdan qaysi tilga tarjima qilishni tanlang:",
        "options": [{"label": "2 000 belgigacha", "words": 0, "price": 1500, "max": 2000},
                    {"label": "6 000 belgigacha", "words": 0, "price": 3000, "max": 6000}],
    },
    "xarita": {  # TAXMIN narx
        "title": "🗺 Texnologik xarita", "kind": "doc", "group": "more", "academic": False,
        "ask": "Dars mavzusi, fan va sinf/kursni yozing:",
        "extra": ("Dars texnologik xaritasi. Jadval: | Bosqich | Vaqt | O'qituvchi faoliyati | O'quvchi faoliyati | Metod va vositalar |. "
                  "Kamida 6 ta bosqich. Jadvaldan oldin dars maqsadi va kutilgan natijalarni yozing."),
        "options": [{"label": "Standart", "words": 600, "price": 3000}],
    },
    "saralash": {  # TAXMIN narx
        "title": "🗃 Saralash o'yini", "kind": "doc", "group": "more", "academic": False,
        "ask": "Saralash o'yini mavzusini yozing:",
        "extra": ("Saralash o'yini: 3–4 kategoriya va jami 20 ta element. Tuzilma: 1) o'yin qoidasi (2 gap), "
                  "2) kategoriyalar jadvali, 3) kesib olinadigan elementlar jadvali | № | Element |, "
                  "4) 'Javoblar kaliti' jadvali (kategoriya va unga tegishli elementlar)."),
        "options": [{"label": "20 ta element", "words": 400, "price": 1500}],
    },
    "ai_chat": {"title": "🤖 AI yordamchi (tekin)", "kind": "chat", "group": "more"},
    # Studio hali yoqilmagan (rasm, ovoz, video narxi yuqori)
    "studio": {"title": "🎨 Studio (rasm/ovoz/video)", "kind": "soon", "group": "more", "enabled": False},
}

# ---------------- promptlar ----------------

PPTX_PROMPT = """Mavzu: {topic}
Til: {lang}
Taqdimot uchun {n} ta mazmunli slayd tayyorlang (sarlavha slaydi alohida qo'shiladi).
Birinchi mazmunli slayd — Reja, oxirgisi — Xulosa.
Har bir slaydda 3–5 ta qisqa band (har biri 12 so'zdan oshmasin) va 1–2 gaplik "notes" (nutq matni) bo'lsin.
Faqat JSON qaytaring, boshqa matn yozmang:
{"title": "...", "slides": [{"title": "...", "bullets": ["...", "..."], "notes": "..."}]}"""

DOC_PROMPT = """Mavzu: {topic}
Til: {lang}
Hajm: taxminan {words} so'z.
{extra}
Markdown formatda yozing: # sarlavha, ## bo'lim, - ro'yxat, **qalin**, kerak bo'lsa | jadval |. Faqat hujjat matnini yozing."""

OUTLINE_PROMPT = """Mavzu: {topic}
Til: {lang}
Hujjat turi: {style}, hajmi taxminan {pages} bet.
{n} ta bo'limdan iborat reja tuzing: 1-bo'lim "Kirish", oxirgi bo'lim "Xulosa", o'rtadagilari mavzuning asosiy boblari.
Faqat JSON qaytaring:
{"title": "...", "sections": [{"title": "...", "points": ["...", "..."]}]}"""

SECTION_PROMPT = """Mavzu: {topic}
Til: {lang}
Hujjat: {style}. Hujjat rejasi: {plan}
Endi faqat "{section}" bo'limini yozing (bo'lim rejasi: {points}).
Hajm: taxminan {words} so'z. Akademik uslub, mantiqiy bog'langan paragraflar. Bo'lim sarlavhasini yozmang.
Aniq statistika, iqtibos va manba nomlarini to'qimang; ishonchsiz bo'lsangiz umumiy ifodalardan foydalaning."""

REFS_PROMPT = """Mavzu: {topic}
Til: {lang}
"Foydalanilgan adabiyotlar" bo'limi uchun 8 ta ADABIYOT TURI/yo'nalishini ro'yxat qilib yozing (masalan: "{topic} bo'yicha darsliklar", rasmiy statistika to'plamlari). 
Aniq muallif, yil yoki sahifa to'qimang. Faqat ro'yxat, har satr "- " bilan."""


PRO_PPTX_PROMPT = """Mavzu: {topic}
Til: {lang}
Professional taqdimot: {n} ta mazmunli slayd (sarlavha slaydi alohida qo'shiladi). 1-slayd Reja, oxirgisi Xulosa.
Turli maketlardan foydalaning. Har slaydda "layout" maydoni bo'lsin:
- {"layout":"bullets","title":"...","bullets":["..."],"notes":"..."}
- {"layout":"stats","title":"...","stats":[{"value":"85%","label":"..."}],"notes":"..."} (2–4 ta raqam; faqat ishonchli, umumiy ma'lumot; aniq raqam bilmasangiz bullets ishlating)
- {"layout":"two_col","title":"...","left":{"title":"...","bullets":["..."]},"right":{"title":"...","bullets":["..."]},"notes":"..."} (taqqoslash uchun)
- {"layout":"callout","title":"...","bullets":["..."],"callout":"Muhim fakt yoki g'oya (1–2 gap)","notes":"..."}
Kamida bitta two_col va bitta callout ishlating. Har band 12 so'zdan oshmasin, "notes" 1–2 gap.
Faqat JSON qaytaring: {"title": "...", "slides": [...]}"""

TRANSLATE_PROMPT = """Quyidagi matnni {lang} yozib tarjima qiling. Ma'no, uslub va abzaslarni saqlang, hech narsa qo'shmang va tushirib qoldirmang.
Faqat tarjimani yozing.

MATN:
{topic}"""

CROSSWORD_PROMPT = """Mavzu: {topic}
Til: {lang}
Krossvord uchun 20 ta so'z va ularning qisqa ta'rifi (savol) tuzing. So'zlar bitta so'zdan iborat, 4–12 harf, bo'sh joy, defis va apostrofsiz, mavzuga oid, turli harflardan boshlansin.
Faqat JSON qaytaring: {"words": [{"word": "...", "clue": "..."}]}"""
