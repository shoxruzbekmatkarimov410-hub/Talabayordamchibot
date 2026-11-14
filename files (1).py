import io
import re
from datetime import datetime

from docx import Document
from docx.enum.table import WD_ROW_HEIGHT_RULE
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from pptx import Presentation
from pptx.dml.color import RGBColor as PRGB
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches, Pt as PPt

# ---------------------------------------------------------------- DOCX


def _runs(par, text: str):
    for part in re.split(r"(\*\*[^*]+\*\*)", text):
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            par.add_run(part[2:-2]).bold = True
        elif part:
            par.add_run(part)


def make_docx(title: str, md: str, academic: bool = True, cover: dict | None = None) -> bytes:
    d = Document()
    for s in d.sections:
        s.left_margin, s.right_margin = Cm(3), Cm(1.5)
        s.top_margin = s.bottom_margin = Cm(2)
    st = d.styles["Normal"]
    st.font.name = "Times New Roman"
    st.font.size = Pt(14 if academic else 12)
    st.paragraph_format.line_spacing = 1.5 if academic else 1.15

    def heading(text, level):
        h = d.add_heading(level=level)
        r = h.add_run(text)
        r.font.name = "Times New Roman"
        r.font.color.rgb = RGBColor(0, 0, 0)
        r.font.size = Pt({0: 20, 1: 16, 2: 14, 3: 13}.get(level, 12))
        if level in (0, 1):
            h.alignment = WD_ALIGN_PARAGRAPH.CENTER

    if cover:
        def cline(text, size=14, bold=False, before=0):
            p = d.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(before)
            r = p.add_run(text)
            r.bold = bold
            r.font.size = Pt(size)
        if cover.get("org"):
            cline(cover["org"].upper(), 14, True)
        cline(cover.get("kind", "").upper(), 24, True, 150)
        cline(title, 18, False, 24)
        if cover.get("subject"):
            cline("Fan: " + cover["subject"], 14, False, 120)
        if cover.get("author"):
            cline("Bajardi: " + cover["author"], 14, False, 12)
        cline(str(datetime.now().year), 14, False, 80)
        d.add_page_break()
    elif title:
        heading(title, 0)

    lines = md.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            i += 1
            continue
        m = re.match(r"^(#{1,4})\s+(.*)", line)
        if m:
            heading(m.group(2).strip("* "), min(len(m.group(1)), 3))
        elif line.lstrip().startswith("|"):
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                    rows.append(cells)
                i += 1
            if rows:
                cols = max(len(r) for r in rows)
                t = d.add_table(rows=len(rows), cols=cols)
                t.style = "Table Grid"
                for ri, r in enumerate(rows):
                    for ci in range(cols):
                        cell = t.cell(ri, ci)
                        cell.text = ""
                        _runs(cell.paragraphs[0], r[ci] if ci < len(r) else "")
                        if ri == 0:
                            for run in cell.paragraphs[0].runs:
                                run.bold = True
                d.add_paragraph()
            continue
        elif re.match(r"^\s*[-*•]\s+", line):
            p = d.add_paragraph(style="List Bullet")
            _runs(p, re.sub(r"^\s*[-*•]\s+", "", line))
        elif re.match(r"^\s*\d+[.)]\s+", line):
            p = d.add_paragraph(style="List Number")
            _runs(p, re.sub(r"^\s*\d+[.)]\s+", "", line))
        else:
            p = d.add_paragraph()
            _runs(p, line)
            if academic:
                p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                p.paragraph_format.first_line_indent = Cm(1.25)
        i += 1

    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------- PPTX

PALETTES = {  # to'q, och fon, urg'u
    "blue": ("1F3A5F", "F4F7FB", "2E86DE"),
    "green": ("1E4D3A", "F3F9F5", "27AE60"),
    "purple": ("3B2667", "F7F4FC", "8E5CF7"),
    "orange": ("3D2A14", "FFF8F0", "F39C12"),
}


def _rect(slide, x, y, w, h, color):
    sh = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
    sh.fill.solid()
    sh.fill.fore_color.rgb = PRGB.from_string(color)
    sh.line.fill.background()
    return sh


def _text(slide, x, y, w, h, text, size, color, bold=False):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    r = tf.paragraphs[0].add_run()
    r.text = text
    r.font.size = PPt(size)
    r.font.bold = bold
    r.font.color.rgb = PRGB.from_string(color)
    return tf


def _bullets(slide, x, y, w, h, bullets, size, color="222222"):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    for k, b in enumerate(bullets):
        p = tf.paragraphs[0] if k == 0 else tf.add_paragraph()
        p.space_after = PPt(12)
        r = p.add_run()
        r.text = "•  " + str(b)
        r.font.size = PPt(size)
        r.font.color.rgb = PRGB.from_string(color)


def _logo(slide, logo, x, y, h):
    try:
        slide.shapes.add_picture(io.BytesIO(logo), x, y, height=h)
    except Exception:  # noqa: BLE001
        pass


def make_pptx(title: str, slides: list, palette: str = "blue", meta: dict | None = None,
              logo: bytes | None = None) -> bytes:
    meta = meta or {}
    dark, light, accent = PALETTES.get(palette, PALETTES["blue"])
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    blank = prs.slide_layouts[6]
    W, H = prs.slide_width, prs.slide_height

    s = prs.slides.add_slide(blank)
    _rect(s, 0, 0, W, H, dark)
    _rect(s, Inches(0.8), Inches(3.9), Inches(2.2), Inches(0.12), accent)
    _text(s, Inches(0.8), Inches(1.6), Inches(11.5), Inches(2.2), title, 44 if len(title) < 60 else 34, "FFFFFF", True)
    for i, line in enumerate([meta.get(k) for k in ("org", "subject", "author") if meta.get(k)]):
        _text(s, Inches(0.8), Inches(4.3 + 0.5 * i), Inches(11.5), Inches(0.5), line, 20, "DDE3FF")
    if logo:
        _logo(s, logo, Inches(0.8), Inches(0.5), Inches(1.1))

    for sd in slides:
        lay = sd.get("layout", "bullets")
        s = prs.slides.add_slide(blank)
        _rect(s, 0, 0, W, H, light)
        _rect(s, 0, 0, Inches(0.35), H, accent)
        _rect(s, Inches(0.35), 0, W - Inches(0.35), Inches(1.4), dark)
        ttl = str(sd.get("title", ""))
        _text(s, Inches(0.9), Inches(0.3), Inches(10.4 if logo else 11.5), Inches(1), ttl, 30 if len(ttl) < 45 else 24, "FFFFFF", True)
        if logo:
            _logo(s, logo, W - Inches(1.7), Inches(0.25), Inches(0.9))
        y = Inches(1.9)
        bullets = [str(b) for b in sd.get("bullets", [])][:7]
        if lay == "stats" and sd.get("stats"):
            st = sd["stats"][:4]
            gap = Inches(0.3)
            cw = (Inches(11.6) - gap * (len(st) - 1)) // len(st)
            for i, x in enumerate(st):
                left = Inches(0.9) + i * (cw + gap)
                _rect(s, left, y, cw, Inches(3.4), "FFFFFF")
                _rect(s, left, y, cw, Inches(0.12), accent)
                _text(s, left + Inches(0.2), y + Inches(0.6), cw - Inches(0.4), Inches(1.2), str(x.get("value", "")), 44, accent, True)
                _text(s, left + Inches(0.2), y + Inches(1.9), cw - Inches(0.4), Inches(1.4), str(x.get("label", "")), 18, "333333")
        elif lay == "two_col" and sd.get("left") and sd.get("right"):
            for i, side in enumerate((sd["left"], sd["right"])):
                left = Inches(0.9) + i * Inches(6.0)
                _text(s, left, y, Inches(5.5), Inches(0.6), str(side.get("title", "")), 24, accent, True)
                _bullets(s, left, y + Inches(0.7), Inches(5.5), Inches(4), [str(b) for b in side.get("bullets", [])][:6], 20)
        elif lay == "callout" and sd.get("callout"):
            _bullets(s, Inches(0.9), y, Inches(7.2), Inches(4.8), bullets, 22)
            _rect(s, Inches(8.6), y, Inches(3.9), Inches(3.6), accent)
            _text(s, Inches(8.85), y + Inches(0.4), Inches(3.4), Inches(3), str(sd["callout"]), 22, "FFFFFF", True)
        else:
            _bullets(s, Inches(0.9), y, Inches(11.6), Inches(5), bullets, 24 if len(bullets) <= 4 else 20)
        if sd.get("notes"):
            s.notes_slide.notes_text_frame.text = str(sd["notes"])

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------- KROSSVORD

def build_crossword(items: list):
    ws, seen = [], set()
    for it in items:
        w = "".join(ch for ch in str(it.get("word", "")).upper() if ch.isalpha())
        if 3 <= len(w) <= 15 and w not in seen:
            seen.add(w)
            ws.append((w, str(it.get("clue", "")).strip()))
    ws.sort(key=lambda x: -len(x[0]))
    grid, dirs, placed = {}, {}, []

    def fits(w, r, c, dr, dc):
        if (r - dr, c - dc) in grid or (r + dr * len(w), c + dc * len(w)) in grid:
            return -1
        inter = 0
        for i, ch in enumerate(w):
            p = (r + dr * i, c + dc * i)
            g = grid.get(p)
            if g is None:
                if (p[0] + dc, p[1] + dr) in grid or (p[0] - dc, p[1] - dr) in grid:
                    return -1
            else:
                if g != ch or (dr, dc) in dirs[p]:
                    return -1
                inter += 1
        return inter

    def put(w, clue, r, c, dr, dc):
        for i, ch in enumerate(w):
            p = (r + dr * i, c + dc * i)
            grid[p] = ch
            dirs.setdefault(p, set()).add((dr, dc))
        placed.append({"word": w, "clue": clue, "r": r, "c": c, "dr": dr, "dc": dc})

    for w, clue in ws:
        if not placed:
            put(w, clue, 0, 0, 0, 1)
            continue
        best = None
        for (pr, pc), g in list(grid.items()):
            for i, ch in enumerate(w):
                if ch != g:
                    continue
                for dr, dc in ((0, 1), (1, 0)):
                    r, c = pr - dr * i, pc - dc * i
                    inter = fits(w, r, c, dr, dc)
                    if inter < 1:
                        continue
                    rs = [p[0] for p in grid] + [r, r + dr * (len(w) - 1)]
                    cs = [p[1] for p in grid] + [c, c + dc * (len(w) - 1)]
                    score = (max(rs) - min(rs) + 1) * (max(cs) - min(cs) + 1) - inter * 6
                    if best is None or score < best[0]:
                        best = (score, r, c, dr, dc)
        if best:
            put(w, clue, *best[1:])
    return placed, grid


def _borders(cell):
    pr = cell._tc.get_or_add_tcPr()
    b = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        e = OxmlElement(f"w:{edge}")
        e.set(qn("w:val"), "single")
        e.set(qn("w:sz"), "8")
        e.set(qn("w:color"), "000000")
        b.append(e)
    pr.append(b)


def make_crossword_docx(title: str, items: list) -> bytes:
    placed, grid = build_crossword(items)
    if len(placed) < 5:
        raise RuntimeError("Krossvord tuzib bo'lmadi (so'zlar kam)")
    r0, c0 = min(p[0] for p in grid), min(p[1] for p in grid)
    R, C = max(p[0] for p in grid) - r0 + 1, max(p[1] for p in grid) - c0 + 1
    starts = sorted({(p["r"], p["c"]) for p in placed})
    num = {pos: i + 1 for i, pos in enumerate(starts)}

    d = Document()
    for s in d.sections:
        s.left_margin = s.right_margin = Cm(1.5)
        s.top_margin = s.bottom_margin = Cm(1.5)
    d.styles["Normal"].font.name = "Times New Roman"
    d.styles["Normal"].font.size = Pt(12)

    def draw(show_letters):
        t = d.add_table(rows=R, cols=C)
        t.autofit = False
        size = Cm(min(0.95, 17.5 / C))
        for ri in range(R):
            t.rows[ri].height = size
            t.rows[ri].height_rule = WD_ROW_HEIGHT_RULE.EXACTLY
            for ci in range(C):
                cell = t.cell(ri, ci)
                cell.width = size
                pos = (ri + r0, ci + c0)
                par = cell.paragraphs[0]
                par.paragraph_format.space_after = Pt(0)
                par.paragraph_format.line_spacing = 1
                if pos in grid:
                    _borders(cell)
                    if show_letters:
                        par.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        par.add_run(grid[pos]).bold = True
                    elif pos in num:
                        par.add_run(str(num[pos])).font.size = Pt(7)

    h = d.add_heading(level=1)
    h.add_run(title).font.color.rgb = RGBColor(0, 0, 0)
    draw(False)
    d.add_paragraph()
    for label, key in (("Gorizontal", "dc"), ("Vertikal", "dr")):
        p = d.add_paragraph()
        p.add_run(label).bold = True
        for it in sorted((x for x in placed if x[key] == 1), key=lambda x: num[(x["r"], x["c"])]):
            d.add_paragraph(f"{num[(it['r'], it['c'])]}. {it['clue']} ({len(it['word'])} harf)")
    d.add_page_break()
    h = d.add_heading(level=1)
    h.add_run("Javoblar").font.color.rgb = RGBColor(0, 0, 0)
    draw(True)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()
