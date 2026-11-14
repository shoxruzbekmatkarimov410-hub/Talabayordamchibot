"""Mini App uchun API. Autentifikatsiya: Telegram initData (HMAC) tekshiriladi."""
import asyncio
import base64
import binascii
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

import db
from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from config import (MAX_RUNNING_JOBS, ADMIN_IDS, ADMIN_USERNAME, BOT_TOKEN, CARD_INFO, REF_PERCENT, START_BONUS,
                    TOPUP_BONUS_PERCENT)
from files import PALETTES
from tools import LANGS, TOOLS

router = APIRouter(prefix="/api")
BOT = None            # main.py o'rnatadi
_tasks: set = set()


def auth(authorization: str = Header(default="")) -> dict:
    if not authorization.startswith("tma "):
        raise HTTPException(401, "Ilovani Telegram ichida oching")
    data = dict(parse_qsl(authorization[4:], keep_blank_values=True))
    got = data.pop("hash", "")
    check = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    calc = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc, got):
        raise HTTPException(401, "Autentifikatsiya xatosi")
    if time.time() - int(data.get("auth_date", "0")) > 86400:
        raise HTTPException(401, "Ilovani qayta oching")
    return json.loads(data["user"])


@router.get("/me")
async def me(user: dict = Depends(auth)):
    name = (user.get("first_name", "") + " " + user.get("last_name", "")).strip()
    u, _ = db.get_or_create_user(user["id"], name)
    info = await BOT.get_me()
    return {"id": user["id"], "name": name or "do'st", "balance": u.balance, "rated": db.has_tx(user["id"], "rating_bonus"),
            "card_info": CARD_INFO, "admin": ADMIN_USERNAME, "bot": info.username,
            "bonus": TOPUP_BONUS_PERCENT, "ref": REF_PERCENT, "start_bonus": START_BONUS}


@router.get("/tools")
async def tools(user: dict = Depends(auth)):
    return {"langs": {k: v[0] for k, v in LANGS.items()},
            "tools": [{"key": k, "title": t["title"], "group": t["group"], "kind": t["kind"],
                       "enabled": t.get("enabled", True), "ask": t.get("ask", ""),
                       "meta": bool(t.get("meta")), "logo": bool(t.get("logo")), "max_len": t.get("max_len", 1500),
                       "options": [{"label": o["label"], "price": o["price"], "max": o.get("max")} for o in t.get("options", [])]}
                      for k, t in TOOLS.items()]}


@router.get("/jobs")
async def jobs(user: dict = Depends(auth)):
    return [{"id": j.id, "tool": TOOLS.get(j.tool, {}).get("title", j.tool), "topic": j.topic[:80],
             "status": j.status, "price": j.price}
            for j in db.list_jobs(user["id"], 20) if j.tool != "chat"]


class CreateIn(BaseModel):
    tool: str
    topic: str
    lang: str
    opt: int
    palette: str = "blue"
    meta: dict = {}
    logo: str = ""


@router.post("/create")
async def create(body: CreateIn, user: dict = Depends(auth)):
    from bot import run_job, subscribed

    tool = TOOLS.get(body.tool)
    if not tool or tool["kind"] not in ("pptx", "longdoc", "doc", "crossword") or tool.get("enabled", True) is False:
        raise HTTPException(400, "Bu vosita mavjud emas")
    topic = body.topic.strip()
    if len(topic) < 3:
        raise HTTPException(400, "Mavzuni yozing")
    if body.lang not in LANGS or not (0 <= body.opt < len(tool["options"])):
        raise HTTPException(400, "Noto'g'ri tanlov")
    limit = tool["options"][body.opt].get("max") or tool.get("max_len", 1500)
    if len(topic) > limit:
        raise HTTPException(400, f"Matn uzun: {limit} belgidan oshmasin")
    uid = user["id"]
    name = (user.get("first_name", "") + " " + user.get("last_name", "")).strip()
    db.get_or_create_user(uid, name)
    if not await subscribed(BOT, uid):
        raise HTTPException(403, "Avval kanalga obuna bo'ling")
    if db.count_running(uid) >= MAX_RUNNING_JOBS:
        raise HTTPException(429, "Sizda 2 ta ish tayyorlanmoqda. Biri tugagach yangisini boshlang")
    opt = dict(tool["options"][body.opt])
    if body.palette in PALETTES:
        opt["palette"] = body.palette
    if tool.get("meta"):
        opt["meta"] = {k: str(body.meta.get(k, ""))[:100].strip() for k in ("author", "org", "subject")}
    if tool.get("logo") and body.logo:
        try:
            raw = base64.b64decode(body.logo, validate=True)
        except (binascii.Error, ValueError):
            raise HTTPException(400, "Logotip noto'g'ri")
        if len(raw) > 1_500_000 or not (raw[:8] == b"\x89PNG\r\n\x1a\n" or raw[:2] == b"\xff\xd8"):
            raise HTTPException(400, "Logotip PNG yoki JPG bo'lsin")
        opt["logo"] = raw
    price = opt["price"]
    if not db.charge(uid, price, f"{body.tool}: {topic[:60]}"):
        raise HTTPException(402, "Balans yetarli emas")
    job_id = db.create_job(uid, body.tool, topic, price)
    t = asyncio.create_task(run_job(BOT, uid, uid, job_id, body.tool, opt, topic, body.lang, price))
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)
    return {"balance": db.get_user(uid).balance, "job": job_id}


@router.get("/topups")
async def topups(user: dict = Depends(auth)):
    return [{"id": t.id, "amount": t.amount, "status": t.status} for t in db.list_topups(user["id"], 5)]


class TopupIn(BaseModel):
    amount: int
    image: str  # base64 JPEG


@router.post("/topup")
async def topup(body: TopupIn, user: dict = Depends(auth)):
    from bot import som

    if not (1000 <= body.amount <= 10_000_000):
        raise HTTPException(400, "Summa 1 000 dan 10 000 000 so'mgacha bo'lishi kerak")
    try:
        raw = base64.b64decode(body.image, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(400, "Chek rasmi noto'g'ri")
    if len(raw) > 8_000_000 or raw[:2] != b"\xff\xd8":
        raise HTTPException(400, "Chek rasmini (JPG/PNG) yuboring")
    if not ADMIN_IDS:
        raise HTTPException(500, "Admin sozlanmagan (ADMIN_IDS)")
    uid = user["id"]
    name = (user.get("first_name", "") + " " + user.get("last_name", "")).strip()
    db.get_or_create_user(uid, name)
    if sum(1 for t in db.list_topups(uid, 10) if t.status == "pending") >= 3:
        raise HTTPException(429, "Avvalgi to'lovlaringiz tasdiqlanishini kuting")
    tid = db.create_topup(uid, body.amount)
    bonus = body.amount * TOPUP_BONUS_PERCENT // 100
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"tp:ok:{tid}"),
        InlineKeyboardButton(text="❌ Rad etish", callback_data=f"tp:no:{tid}")]])
    caption = (f"🧾 To'lov #{tid}\n👤 {name or 'Foydalanuvchi'} (ID {uid})"
               f"{' @' + user['username'] if user.get('username') else ''}\n"
               f"💰 {som(body.amount)} (+{som(bonus)} bonus)")
    sent = 0
    for a in ADMIN_IDS:
        try:
            await BOT.send_photo(a, BufferedInputFile(raw, filename="chek.jpg"), caption=caption, reply_markup=kb)
            sent += 1
        except Exception:  # noqa: BLE001
            pass
    if not sent:
        db.decide_topup(tid, "rejected")
        raise HTTPException(500, "Adminga yuborib bo'lmadi. Admin botga /start yozgan bo'lishi kerak")
    return {"id": tid}


class RateIn(BaseModel):
    stars: int
    text: str


@router.post("/rate")
async def rate(body: RateIn, user: dict = Depends(auth)):
    uid = user["id"]
    text = body.text.strip()
    if not (1 <= body.stars <= 5) or len(text) < 5:
        raise HTTPException(400, "Yulduz tanlang va fikringizni yozing")
    if db.count_done(uid) == 0:
        raise HTTPException(400, "Avval kamida bitta hujjat yarating")
    if not db.give_once(uid, 500, "rating_bonus", f"{body.stars} yulduz"):
        raise HTTPException(400, "Siz allaqachon baholagansiz")
    for a in ADMIN_IDS:
        try:
            await BOT.send_message(a, f"⭐ Baho: {body.stars}/5 (ID {uid})\n{text[:500]}")
        except Exception:  # noqa: BLE001
            pass
    return {"balance": db.get_user(uid).balance}
