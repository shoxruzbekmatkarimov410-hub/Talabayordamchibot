"""Vosita turiga qarab fayl yasaydi. Qaytaradi: (fayl_nomi, bytes)."""
import asyncio
import re

import ai
import files
from tools import (DOC_PROMPT, LANGS, OUTLINE_PROMPT, PPTX_PROMPT, REFS_PROMPT,
                   SECTION_PROMPT, TOOLS)


def fill(tpl: str, **kw) -> str:
    for k, v in kw.items():
        tpl = tpl.replace("{" + k + "}", str(v))
    return tpl


def safe_name(topic: str, ext: str) -> str:
    base = re.sub(r"[^\w\-]+", "_", topic, flags=re.U).strip("_")[:40] or "ish"
    return f"{base}.{ext}"


async def generate(tool_key: str, opt: dict, topic: str, lang_code: str):
    tool = TOOLS[tool_key]
    lang = LANGS[lang_code][1]
    kind = tool["kind"]

    if kind == "pptx":
        raw = await ai.ask(fill(PPTX_PROMPT, topic=topic, lang=lang, n=opt["count"] - 1), temperature=0.6)
        data = ai.extract_json(raw)
        slides = data.get("slides", [])
        if not slides:
            raise RuntimeError("AI bo'sh slayd qaytardi")
        return safe_name(topic, "pptx"), files.make_pptx(data.get("title") or topic, slides)

    if kind == "doc":
        md = await ai.ask(fill(DOC_PROMPT, topic=topic, lang=lang, words=opt["words"],
                               extra=tool.get("extra", "")), max_tokens=8000)
        title = topic[:120] if tool_key != "rezyume" else ""
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
        md = []
        for sec, body in zip(sections, bodies):
            md.append(f"# {sec.get('title', '')}\n\n{body}\n")
        md.append(f"# Foydalanilgan adabiyotlar\n\n{refs}\n")
        title = outline.get("title") or topic
        return safe_name(topic, "docx"), files.make_docx(title, "\n".join(md), academic=True)

    raise RuntimeError("Noma'lum vosita turi")
