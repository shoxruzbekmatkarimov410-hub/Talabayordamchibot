import io
import re

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
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


def make_docx(title: str, md: str, academic: bool = True) -> bytes:
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

    if title:
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


def make_pptx(title: str, slides: list, palette: str = "blue") -> bytes:
    dark, light, accent = PALETTES.get(palette, PALETTES["blue"])
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    blank = prs.slide_layouts[6]
    W, H = prs.slide_width, prs.slide_height

    s = prs.slides.add_slide(blank)
    _rect(s, 0, 0, W, H, dark)
    _rect(s, Inches(0.8), Inches(3.9), Inches(2.2), Inches(0.12), accent)
    _text(s, Inches(0.8), Inches(1.8), Inches(11.5), Inches(2), title, 44, "FFFFFF", True)

    for sd in slides:
        s = prs.slides.add_slide(blank)
        _rect(s, 0, 0, W, H, light)
        _rect(s, 0, 0, Inches(0.35), H, accent)
        _rect(s, Inches(0.35), 0, W - Inches(0.35), Inches(1.4), dark)
        _text(s, Inches(0.9), Inches(0.3), Inches(11.5), Inches(1), str(sd.get("title", "")), 30, "FFFFFF", True)
        bullets = [str(b) for b in sd.get("bullets", [])][:7]
        size = 24 if len(bullets) <= 4 else 20
        tb = s.shapes.add_textbox(Inches(0.9), Inches(1.9), Inches(11.6), Inches(5))
        tf = tb.text_frame
        tf.word_wrap = True
        for k, b in enumerate(bullets):
            p = tf.paragraphs[0] if k == 0 else tf.add_paragraph()
            p.space_after = PPt(14)
            r = p.add_run()
            r.text = "•  " + b
            r.font.size = PPt(size)
            r.font.color.rgb = PRGB.from_string("222222")
        if sd.get("notes"):
            s.notes_slide.notes_text_frame.text = str(sd["notes"])

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()
