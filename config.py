import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
XAI_API_KEY = os.getenv("XAI_API_KEY", "")
XAI_MODEL = os.getenv("XAI_MODEL", "grok-4.3")  # console.x.ai'dan tekshiring
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://api.x.ai/v1").rstrip("/")
DATABASE_URL = os.getenv("DATABASE_URL", "") or "sqlite:///local.db"
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x}
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "")
CARD_INFO = os.getenv("CARD_INFO", "To'lov rekvizitlari hali kiritilmagan")
REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL", "")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "change-me")
# Render bu o'zgaruvchini o'zi beradi
PUBLIC_URL = os.getenv("PUBLIC_URL") or os.getenv("RENDER_EXTERNAL_URL", "")

START_BONUS = 2000          # so'm
TOPUP_BONUS_PERCENT = 10    # to'ldirishga bonus
REF_PERCENT = 10            # do'st to'ldirganda taklif qilganga
FREE_CHAT_PER_DAY = 10
