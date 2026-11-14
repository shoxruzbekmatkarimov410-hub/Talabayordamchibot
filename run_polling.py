"""Kompyuteringizda sinash uchun: python run_polling.py (webhook kerak emas)"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

import db
from bot import router
from config import BOT_TOKEN


async def main():
    logging.basicConfig(level=logging.INFO)
    db.init()
    bot = Bot(BOT_TOKEN)
    await bot.delete_webhook(drop_pending_updates=True)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await dp.start_polling(bot)


asyncio.run(main())
