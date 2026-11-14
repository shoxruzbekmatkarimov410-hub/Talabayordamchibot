"""Render uchun kirish nuqtasi: uvicorn main:app"""
import logging
import os
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import MenuButtonWebApp, Update, WebAppInfo
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()
    if PUBLIC_URL:
        await bot.set_webhook(f"{PUBLIC_URL}/webhook", secret_token=WEBHOOK_SECRET,
                              drop_pending_updates=True)
        await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(
            text="Ilova", web_app=WebAppInfo(url=f"{PUBLIC_URL}/app")))
    yield
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
