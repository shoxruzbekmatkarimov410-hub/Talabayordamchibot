"""Render uchun kirish nuqtasi: uvicorn main:app"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import MenuButtonWebApp, Update, WebAppInfo
import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse

import api
import db
from bot import router
from config import BOT_TOKEN, PUBLIC_URL, WEBHOOK_SECRET

logging.basicConfig(level=logging.INFO)
bot = Bot(BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
dp.include_router(router)
api.BOT = bot
INDEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")


async def keepalive():
    """Render bepul serveri uxlab qolmasligi uchun o'zini har 10 daqiqada chaqiradi."""
    async with httpx.AsyncClient(timeout=20) as c:
        while True:
            await asyncio.sleep(600)
            try:
                await c.get(PUBLIC_URL + "/")
            except Exception:  # noqa: BLE001
                pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()
    for job_id, uid, price in db.recover_stuck():  # qayta ishga tushganda to'xtab qolgan ishlar
        try:
            await bot.send_message(uid, f"😔 Server qayta ishga tushgani uchun ish #{job_id} bajarilmadi. "
                                        f"{price:,} so'm balansingizga qaytarildi.".replace(",", " "))
        except Exception:  # noqa: BLE001
            pass
    ka = asyncio.create_task(keepalive()) if PUBLIC_URL else None
    if PUBLIC_URL:
        await bot.set_webhook(f"{PUBLIC_URL}/webhook", secret_token=WEBHOOK_SECRET,
                              drop_pending_updates=True)
        await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(
            text="Ilova", web_app=WebAppInfo(url=f"{PUBLIC_URL}/app")))
    yield
    if ka:
        ka.cancel()
    await bot.session.close()


app = FastAPI(lifespan=lifespan)
app.include_router(api.router)


@app.get("/")
async def health():
    return {"ok": True}


@app.get("/app")
async def mini_app():
    return FileResponse(INDEX, media_type="text/html")


@app.post("/webhook")
async def webhook(request: Request, x_telegram_bot_api_secret_token: str = Header(default="")):
    if x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
        raise HTTPException(403)
    update = Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}
