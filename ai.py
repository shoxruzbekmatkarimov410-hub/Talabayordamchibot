import asyncio
import json
import logging
import re

import httpx

from config import (AI_BASE_URL, FALLBACK_API_KEY, FALLBACK_BASE_URL, FALLBACK_MODEL,
                    XAI_API_KEY, XAI_MODEL)

log = logging.getLogger("ai")

SYSTEM = ("Siz talabalar uchun akademik kontent yozadigan tajribali o'qituvchi va muharrirsiz. "
          "Faktlarni to'qimang; ishonchsiz raqam, iqtibos va manbalarni keltirmang. "
          "Faqat so'ralgan formatda javob bering, ortiqcha kirish so'zlarisiz.")

_picked: dict = {}  # model nomi noto'g'ri bo'lsa, avtomatik topilgan model


def providers() -> list:
    p = []
    if XAI_API_KEY:
        p.append({"name": "asosiy", "base": AI_BASE_URL, "key": XAI_API_KEY, "model": XAI_MODEL, "auto": True})
    if FALLBACK_API_KEY and FALLBACK_BASE_URL and FALLBACK_MODEL:
        p.append({"name": "zaxira", "base": FALLBACK_BASE_URL, "key": FALLBACK_API_KEY,
                  "model": FALLBACK_MODEL, "auto": False})
    return p


async def _pick_model(client: httpx.AsyncClient, prov: dict):
    """Provayderning mavjud modellaridan mos matn modelini tanlaydi (xAI uchun)."""
    r = await client.get(prov["base"] + "/models", headers={"Authorization": f"Bearer {prov['key']}"})
    if r.status_code >= 400:
        return None
    ids = [m.get("id", "") for m in r.json().get("data", [])]
    bad = ("image", "imagine", "video", "vision", "embed", "tts", "whisper", "audio")
    cands = [i for i in ids if "grok" in i and not any(b in i for b in bad)]
    fast = [i for i in cands if "fast" in i or "mini" in i] or cands
    return sorted(fast)[-1] if fast else None


async def _call(prov: dict, prompt: str, system: str, max_tokens: int, temperature: float) -> str:
    model = _picked.get(prov["base"], prov["model"])
    tried_pick = False
    headers = {"Authorization": f"Bearer {prov['key']}"}
    async with httpx.AsyncClient(timeout=240) as c:
        for attempt in range(3):
            payload = {"model": model, "temperature": temperature, "max_tokens": max_tokens,
                       "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]}
            try:
                r = await c.post(f"{prov['base']}/chat/completions", json=payload, headers=headers)
            except httpx.HTTPError as e:
                if attempt == 2:
                    raise RuntimeError(f"{prov['name']}: ulanish xatosi {type(e).__name__}")
                await asyncio.sleep(2 + attempt * 2)
                continue
            if r.status_code in (429, 500, 502, 503, 504):
                if attempt == 2:
                    raise RuntimeError(f"{prov['name']}: band ({r.status_code}) {r.text[:150]}")
                await asyncio.sleep(3 + attempt * 4)
                continue
            if r.status_code in (400, 404) and prov["auto"] and not tried_pick and "model" in r.text.lower():
                tried_pick = True
                alt = await _pick_model(c, prov)
                if alt and alt != model:
                    log.warning("model %s topilmadi, %s ishlatiladi", model, alt)
                    model = _picked[prov["base"]] = alt
                    continue
            if r.status_code >= 400:
                raise RuntimeError(f"{prov['name']} {r.status_code} (model {model}): {r.text[:250]}")
            text = (r.json().get("choices") or [{}])[0].get("message", {}).get("content")
            if not text or not text.strip():
                raise RuntimeError(f"{prov['name']}: AI bo'sh javob qaytardi")
            return text.strip()
    raise RuntimeError(f"{prov['name']}: javob olinmadi")


async def ask(prompt: str, system: str = SYSTEM, max_tokens: int = 6000, temperature: float = 0.7) -> str:
    provs = providers()
    if not provs:
        raise RuntimeError("AI kaliti kiritilmagan (XAI_API_KEY)")
    errors = []
    for prov in provs:
        try:
            return await _call(prov, prompt, system, max_tokens, temperature)
        except Exception as e:  # noqa: BLE001
            log.warning("AI %s xato: %s", prov["name"], e)
            errors.append(str(e))
    raise RuntimeError(" | ".join(errors))


def extract_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    a, b = text.find("{"), text.rfind("}")
    if a == -1 or b == -1:
        raise ValueError("AI JSON qaytarmadi")
    try:
        return json.loads(text[a:b + 1])
    except json.JSONDecodeError:
        fixed = re.sub(r",\s*([}\]])", r"\1", text[a:b + 1])  # ortiqcha vergullar
        return json.loads(fixed)
