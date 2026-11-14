"""Mini App uchun API. Autentifikatsiya: Telegram initData (HMAC) tekshiriladi."""
import asyncio
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

import db
from config import (ADMIN_USERNAME, BOT_TOKEN, CARD_INFO, REF_PERCENT, START_BONUS,
                    TOPUP_BONUS_PERCENT)
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
    return {"id": user["id"], "name": name or "do'st", "balance": u.balance,
            "card_info": CARD_INFO, "admin": ADMIN_USERNAME, "bot": info.username,
            "bonus": TOPUP_BONUS_PERCENT, "ref": REF_PERCENT, "start_bonus": START_BONUS}


@router.get("/tools")
async def tools(user: dict = Depends(auth)):
    return {"langs": {k: v[0] for k, v in LANGS.items()},
            "tools": [{"key": k, "title": t["title"], "group": t["group"], "kind": t["kind"],
                       "enabled": t.get("enabled", True), "ask": t.get("ask", ""),
                       "options": [{"label": o["label"], "price": o["price"]} for o in t.get("options", [])]}
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


@router.post("/create")
async def create(body: CreateIn, user: dict = Depends(auth)):
    from bot import run_job, subscribed

    tool = TOOLS.get(body.tool)
    if not tool or tool["kind"] not in ("pptx", "longdoc", "doc") or tool.get("enabled", True) is False:
        raise HTTPException(400, "Bu vosita mavjud emas")
    topic = body.topic.strip()[:1500]
    if len(topic) < 3:
        raise HTTPException(400, "Mavzuni yozing")
    if body.lang not in LANGS or not (0 <= body.opt < len(tool["options"])):
        raise HTTPException(400, "Noto'g'ri tanlov")
    uid = user["id"]
    name = (user.get("first_name", "") + " " + user.get("last_name", "")).strip()
    db.get_or_create_user(uid, name)
    if not await subscribed(BOT, uid):
        raise HTTPException(403, "Avval kanalga obuna bo'ling")
    opt = tool["options"][body.opt]
    price = opt["price"]
    if not db.charge(uid, price, f"{body.tool}: {topic[:60]}"):
        raise HTTPException(402, "Balans yetarli emas")
    job_id = db.create_job(uid, body.tool, topic, price)
    t = asyncio.create_task(run_job(BOT, uid, uid, job_id, body.tool, opt, topic, body.lang, price))
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)
    return {"balance": db.get_user(uid).balance, "job": job_id}
