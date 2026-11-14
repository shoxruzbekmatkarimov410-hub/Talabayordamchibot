"""Vosita turiga qarab fayl yasaydi. Qaytaradi: (fayl_nomi, bytes)."""
import asyncio
import re

import ai
import files
from tools import (CROSSWORD_PROMPT, DOC_PROMPT, LANGS, OUTLINE_PROMPT, PPTX_PROMPT, PRO_PPTX_PROMPT,
                   REFS_PROMPT, SECTION_PROMPT, TOOLS, TRANSLATE_PROMPT)

DOC_TEMPLATES = {"translate": TRANSLATE_PROMPT}


def fill(tpl: str, **kw) -> str:
    for k, v in kw.items():
        tpl = tpl.replace("{" + k + "}", str(v))
    return tpl


def safe_name(topic: str, ext: str) -> str:
    base = re.sub(r"[^\w\-]+", "_", topic[:60], flags=re.U).strip("_")[:40] or "ish"
    return f"{base}.{ext}"


async def generate(tool_key: str, opt: dict, topic: str, lang_code: str):
    tool = TOOLS[tool_key]
    lang = LANGS[lang_code][1]
    kind = tool["kind"]
    meta = opt.get("meta") or {}

    if kind == "pptx":
        tpl = PRO_PPTX_PROMPT if tool.get("pro") else PPTX_PROMPT
        raw = await ai.ask(fill(tpl, topic=topic, lang=lang, n=opt["count"] - 1),
                           temperature=0.6, max_tokens=9000 if tool.get("pro") else 6000)
        data = ai.extract_json(raw)
        slides = data.get("slides", [])
        if not slides:
            raise RuntimeError("AI bo'sh slayd qaytardi")
        return safe_name(topic, "pptx"), files.make_pptx(data.get("title") or topic, slides,
                                                          opt.get("palette", "blue"), meta, opt.get("logo"))

    if kind == "crossword":
        raw = await ai.ask(fill(CROSSWORD_PROMPT, topic=topic, lang=lang), temperature=0.5)
        items = ai.extract_json(raw).get("words", [])
        return safe_name(topic, "docx"), files.make_crossword_docx("Krossvord: " + topic[:80], items)

    if kind == "doc":
        tpl = DOC_TEMPLATES.get(tool.get("tpl"), DOC_PROMPT)
        md = await ai.ask(fill(tpl, topic=topic, lang=lang, words=opt["words"], extra=tool.get("extra", "")),
                          max_tokens=8000)
        title = "" if tool_key in ("rezyume", "tarjimon") else topic[:120]
        return safe_name(topic, "docx"), files.make_docx(title, md, academic=tool.get("academic", True))

    if kind == "longdoc":
        pages = opt["pages"]
        n = max(5, min(12, pages // 2 + 1))
        raw = await ai.ask(fill(OUTLINE_PROMPT, topic=topic, lang=lang, style=tool["style"],
                                pages=pages, n=n), temperature=0.5)
        outline = ai.extract_json(raw)
        sections = outline.get("sections", [])
        if len(sections) < 3:
            raise RuntimeError("AI reja tuza olmadi")
        plan = "; ".join(s.get("title", "") for s in sections)
        words = max(200, int(pages * 280 / len(sections)))
        sem = asyncio.Semaphore(3)

        async def write(sec):
            async with sem:
                return await ai.ask(fill(SECTION_PROMPT, topic=topic, lang=lang, style=tool["style"], plan=plan,
                                         section=sec.get("title", ""), points=", ".join(sec.get("points", [])),
                                         words=words), max_tokens=6000)

        bodies = await asyncio.gather(*[write(s) for s in sections])
        refs = await ai.ask(fill(REFS_PROMPT, topic=topic, lang=lang), max_tokens=800)
        md = [f"# {sec.get('title', '')}\n\n{body}\n" for sec, body in zip(sections, bodies)]
        md.append(f"# Foydalanilgan adabiyotlar\n\n{refs}\n")
        title = outline.get("title") or topic
        cover = None
        if meta.get("org") or meta.get("author") or meta.get("subject"):
            cover = {"kind": tool["style"], **{k: meta.get(k, "") for k in ("org", "author", "subject")}}
        return safe_name(topic, "docx"), files.make_docx(title, "\n".join(md), academic=True, cover=cover)

    raise RuntimeError("Noma'lum vosita turi")
