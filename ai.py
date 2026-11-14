import asyncio
import json
import re

import httpx

from config import AI_BASE_URL, XAI_API_KEY, XAI_MODEL

SYSTEM = ("Siz talabalar uchun akademik kontent yozadigan tajribali o'qituvchi va muharrirsiz. "
          "Faktlarni to'qimang; ishonchsiz raqam, iqtibos va manbalarni keltirmang. "
          "Faqat so'ralgan formatda javob bering, ortiqcha kirish so'zlarisiz.")


async def ask(prompt: str, system: str = SYSTEM, max_tokens: int = 6000, temperature: float = 0.7) -> str:
    payload = {
        "model": XAI_MODEL,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {"Authorization": f"Bearer {XAI_API_KEY}"}
    last = None
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=240) as c:
                r = await c.post(f"{AI_BASE_URL}/chat/completions", json=payload, headers=headers)
            if r.status_code in (429, 500, 502, 503, 504):
                raise RuntimeError(f"AI vaqtincha band: {r.status_code}")
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:  # noqa: BLE001
            last = e
            await asyncio.sleep(2 + attempt * 3)
    raise RuntimeError(f"AI xatosi: {last}")


def extract_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    a, b = text.find("{"), text.rfind("}")
    if a == -1 or b == -1:
        raise ValueError("JSON topilmadi")
    return json.loads(text[a:b + 1])
