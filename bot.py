import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

import ai
import db
from config import (ADMIN_IDS, ADMIN_USERNAME, CARD_INFO, FREE_CHAT_PER_DAY, PUBLIC_URL, REF_PERCENT,
                    REQUIRED_CHANNEL, START_BONUS, TOPUP_BONUS_PERCENT, XAI_MODEL, MAX_RUNNING_JOBS, JOB_TIMEOUT)
from generator import generate
from tools import LANGS, TOOLS

router = Router()
log = logging.getLogger("bot")


class Order(StatesGroup):
    topic = State()


class Chat(StatesGroup):
    talking = State()


def som(x: int) -> str:
    return f"{x:,}".replace(",", " ") + " so'm"


def app_url(**q) -> str:
    from urllib.parse import urlencode
    return f"{PUBLIC_URL}/app" + ("?" + urlencode(q) if q else "")


def app_menu():
    """Har bir tugma Mini App'ni ochadi (kerakli vosita yoki bo'lim bilan)."""
    kb = InlineKeyboardBuilder()
    for key, t in TOOLS.items():
        if t["group"] == "main":
            kb.button(text=t["title"], web_app=WebAppInfo(url=app_url(tool=key)))
    kb.adjust(2)
    row = InlineKeyboardBuilder()
    row.button(text="➕ Barcha vositalar", web_app=WebAppInfo(url=app_url(picker=1)))
    row.adjust(1)
    kb.attach(row)
    row2 = InlineKeyboardBuilder()
    row2.button(text="💰 Hamyon", web_app=WebAppInfo(url=app_url(tab="wallet")))
    row2.button(text="📁 Ishlarim", web_app=WebAppInfo(url=app_url(tab="jobs")))
    row2.button(text="🎁 Taklif", web_app=WebAppInfo(url=app_url(tab="wallet")))
    row2.adjust(3)
    kb.attach(row2)
    return kb.as_markup()


def main_menu(group: str = "main"):
    if PUBLIC_URL:
        return app_menu()
    kb = InlineKeyboardBuilder()
    for key, t in TOOLS.items():
        if t["group"] == group:
            kb.button(text=t["title"], callback_data=f"t:{key}")
    kb.adjust(2)
    kb2 = InlineKeyboardBuilder()
    if group == "main":
        kb2.button(text="➕ Boshqa vositalar", callback_data="menu:more")
    else:
        kb2.button(text="⬅️ Asosiy menyu", callback_data="menu:main")
    kb.attach(kb2)
    row = InlineKeyboardBuilder()
    row.button(text="💰 Hamyon", callback_data="wallet")
    row.button(text="📁 Ishlarim", callback_data="jobs")
    row.button(text="🎁 Taklif", callback_data="invite")
    row.adjust(3)
    kb.attach(row)
    return kb.as_markup()


async def subscribed(bot: Bot, uid: int) -> bool:
    if not REQUIRED_CHANNEL:
        return True
    try:
        m = await bot.get_chat_member(REQUIRED_CHANNEL, uid)
        return m.status in ("member", "administrator", "creator")
    except Exception:  # noqa: BLE001
        return True  # kanal sozlanmagan bo'lsa, foydalanuvchini to'smaymiz


def sub_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="📢 Kanalga obuna bo'lish", url=f"https://t.me/{REQUIRED_CHANNEL.lstrip('@')}")
    kb.button(text="✅ Tekshirish", callback_data="check_sub")
    kb.adjust(1)
    return kb.as_markup()


async def show_menu(msg: Message, text: str = "Nima yaratamiz?"):
    await msg.answer(text, reply_markup=main_menu("main"))


# ------------------------------------------------------------------ start / menyu

@router.message(CommandStart())
async def start(m: Message, command: CommandObject, state: FSMContext):
    await state.clear()
    ref = None
    if command.args and command.args.startswith("ref_"):
        try:
            ref = int(command.args[4:])
        except ValueError:
            pass
    u, new = db.get_or_create_user(m.from_user.id, m.from_user.full_name, ref)
    hi = f"Assalomu alaykum, {m.from_user.first_name}! 👋\n\nSlayd, referat, mustaqil ish va boshqa hujjatlarni bir necha daqiqada tayyorlayman."
    if new:
        hi += f"\n\n🎁 Sizga {som(START_BONUS)} bonus berildi."
    await m.answer(hi)
    if not await subscribed(m.bot, m.from_user.id):
        await m.answer("Botdan to'liq foydalanish uchun kanalga obuna bo'ling:", reply_markup=sub_kb())
        return
    await show_menu(m)


@router.message(Command("menu"))
async def menu_cmd(m: Message, state: FSMContext):
    await state.clear()
    await show_menu(m)


@router.callback_query(F.data == "check_sub")
async def check_sub(cb: CallbackQuery):
    if await subscribed(cb.bot, cb.from_user.id):
        await cb.message.answer("✅ Rahmat!")
        await show_menu(cb.message)
    else:
        await cb.answer("Hali obuna bo'lmagansiz", show_alert=True)


@router.callback_query(F.data.startswith("menu:"))
async def menu_cb(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_reply_markup(reply_markup=main_menu(cb.data.split(":")[1]))
    await cb.answer()


# ------------------------------------------------------------------ hamyon

def wallet_text(uid: int) -> str:
    u = db.get_user(uid)
    bal = u.balance if u else 0
    return (f"💰 Balans: {som(bal)}\n\n"
            f"To'ldirish:\n{CARD_INFO}\n\n"
            f"To'lovdan so'ng chek (skrinshot) rasmini shu botga yuboring"
            f"{' yoki ' + ADMIN_USERNAME + ' ga' if ADMIN_USERNAME else ''}. "
            f"Admin tasdiqlagach balans to'ldiriladi va +{TOPUP_BONUS_PERCENT}% bonus qo'shiladi.")


@router.message(Command("balans"))
async def balans_cmd(m: Message):
    await m.answer(wallet_text(m.from_user.id))


@router.callback_query(F.data == "wallet")
async def wallet_cb(cb: CallbackQuery):
    await cb.message.answer(wallet_text(cb.from_user.id))
    await cb.answer()


@router.callback_query(F.data == "invite")
async def invite_cb(cb: CallbackQuery):
    me = await cb.bot.get_me()
    await cb.message.answer(
        f"🎁 Do'stingizni taklif qiling: do'stingiz balansini to'ldirgan sari sizga {REF_PERCENT}% bonus.\n\n"
        f"Sizning havolangiz:\nhttps://t.me/{me.username}?start=ref_{cb.from_user.id}")
    await cb.answer()


@router.callback_query(F.data == "jobs")
async def jobs_cb(cb: CallbackQuery):
    jobs = [j for j in db.list_jobs(cb.from_user.id) if j.tool != "chat"]
    if not jobs:
        await cb.message.answer("Hali ishlar yo'q. Yangi ish yarating 👇")
    else:
        icon = {"done": "✅", "failed": "❌", "running": "⏳"}
        lines = [f"{icon.get(j.status, '•')} {TOOLS.get(j.tool, {}).get('title', j.tool)} — {j.topic[:40]}" for j in jobs]
        await cb.message.answer("📁 Oxirgi ishlaringiz:\n\n" + "\n".join(lines))
    await cb.answer()


@router.message(F.photo | F.document)
async def receipt(m: Message, state: FSMContext):
    """Chek rasmi adminlarga yuboriladi."""
    if await state.get_state():
        return
    for admin in ADMIN_IDS:
        try:
            await m.bot.send_message(admin, f"🧾 Chek: {m.from_user.full_name} (ID: {m.from_user.id})\n"
                                            f"Tasdiqlash: /add {m.from_user.id} SUMMA")
            await m.forward(admin)
        except Exception:  # noqa: BLE001
            log.exception("admin'ga yuborilmadi")
    await m.answer("🧾 Chek adminga yuborildi. Tasdiqlangach balansingiz to'ldiriladi.")


# ------------------------------------------------------------------ admin

async def credit_topup(bot: Bot, uid: int, amount: int) -> int:
    """Balansni to'ldiradi, +bonus beradi, taklif qilganga bonus yuboradi. Bonus summasini qaytaradi."""
    bonus = amount * TOPUP_BONUS_PERCENT // 100
    db.add_balance(uid, amount, "topup", "to'lov tasdiqlandi")
    if bonus:
        db.add_balance(uid, bonus, "bonus", f"+{TOPUP_BONUS_PERCENT}% to'ldirish bonusi")
    u = db.get_user(uid)
    if u and u.referrer_id:
        rb = amount * REF_PERCENT // 100
        db.add_balance(u.referrer_id, rb, "ref", f"do'st {uid} to'ldirdi")
        try:
            await bot.send_message(u.referrer_id, f"🎁 Do'stingiz balansini to'ldirdi: sizga +{som(rb)} bonus.")
        except Exception:  # noqa: BLE001
            pass
    try:
        await bot.send_message(uid, f"✅ Balansingiz to'ldirildi: +{som(amount)} (+{som(bonus)} bonus).")
    except Exception:  # noqa: BLE001
        pass
    return bonus


@router.message(Command("add"))
async def admin_add(m: Message, command: CommandObject):
    if m.from_user.id not in ADMIN_IDS:
        return
    try:
        uid, amount = [int(x) for x in (command.args or "").split()]
    except ValueError:
        await m.answer("Format: /add USER_ID SUMMA")
        return
    if not (1 <= amount <= 10_000_000):
        await m.answer("Summa 1 dan 10 000 000 gacha bo'lishi kerak")
        return
    if not db.get_user(uid):
        await m.answer("Foydalanuvchi topilmadi")
        return
    bonus = await credit_topup(m.bot, uid, amount)
    await m.answer(f"✅ {uid} balansiga {som(amount)} + {som(bonus)} bonus qo'shildi.")


@router.message(Command("setbal"))
async def admin_setbal(m: Message, command: CommandObject):
    if m.from_user.id not in ADMIN_IDS:
        return
    try:
        uid, amount = [int(x) for x in (command.args or "").split()]
    except ValueError:
        await m.answer("Format: /setbal USER_ID SUMMA")
        return
    db.set_balance(uid, amount)
    await m.answer(f"✅ {uid} balansi {som(amount)} qilib o'rnatildi.")


@router.message(Command("testai"))
async def admin_testai(m: Message):
    if m.from_user.id not in ADMIN_IDS:
        return
    try:
        r = await ai.ask("Bitta so'z bilan 'salom' deb javob ber", max_tokens=50)
        await m.answer(f"✅ AI ishlayapti (model: {XAI_MODEL}):\n{r[:200]}")
    except Exception as e:  # noqa: BLE001
        await m.answer(f"❌ {str(e)[:900]}")


@router.callback_query(F.data.startswith("tp:"))
async def topup_decide(cb: CallbackQuery):
    """Admin chek ostidagi Tasdiqlash / Rad etish tugmalari."""
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer("Ruxsat yo'q", show_alert=True)
        return
    _, action, tid = cb.data.split(":")
    t = db.decide_topup(int(tid), "approved" if action == "ok" else "rejected")
    if not t:
        await cb.answer("Bu to'lov allaqachon ko'rib chiqilgan", show_alert=True)
        return
    if action == "ok":
        bonus = await credit_topup(cb.bot, t.user_id, t.amount)
        mark = f"✅ TASDIQLANDI: +{som(t.amount)} (+{som(bonus)} bonus)"
    else:
        mark = "❌ RAD ETILDI"
        try:
            await cb.bot.send_message(t.user_id, f"❌ {som(t.amount)} to'lovingiz tasdiqlanmadi. "
                                                 "Chek noto'g'ri bo'lsa, qayta yuboring yoki adminga yozing"
                                                 f"{' ' + ADMIN_USERNAME if ADMIN_USERNAME else ''}.")
        except Exception:  # noqa: BLE001
            pass
    try:
        await cb.message.edit_caption(caption=(cb.message.caption or "") + f"\n\n{mark}", reply_markup=None)
    except Exception:  # noqa: BLE001
        pass
    await cb.answer("Bajarildi")


@router.message(Command("stat"))
async def admin_stat(m: Message):
    if m.from_user.id in ADMIN_IDS:
        users, jobs, revenue = db.stats()
        await m.answer(f"👥 Foydalanuvchilar: {users}\n📄 Ishlar: {jobs}\n💵 Tushum: {som(revenue)}")


# ------------------------------------------------------------------ vosita tanlash

@router.callback_query(F.data.startswith("t:"))
async def pick_tool(cb: CallbackQuery, state: FSMContext):
    key = cb.data[2:]
    tool = TOOLS.get(key)
    if not tool:
        await cb.answer()
        return
    if tool.get("enabled", True) is False:
        await cb.answer("Tez orada qo'shiladi 🚀", show_alert=True)
        return
    if not await subscribed(cb.bot, cb.from_user.id):
        await cb.message.answer("Avval kanalga obuna bo'ling:", reply_markup=sub_kb())
        await cb.answer()
        return
    await state.clear()
    if tool["kind"] == "chat":
        await state.set_state(Chat.talking)
        await cb.message.answer(f"🤖 Savolingizni yozing (kuniga {FREE_CHAT_PER_DAY} ta tekin). Chiqish: /menu")
    else:
        await state.update_data(tool=key)
        await state.set_state(Order.topic)
        await cb.message.answer(f"{tool['title']}\n\n{tool['ask']}")
    await cb.answer()


@router.message(Order.topic, F.text)
async def got_topic(m: Message, state: FSMContext):
    topic = m.text.strip()
    if len(topic) < 3 or topic.startswith("/"):
        await m.answer("Iltimos, mavzuni matn bilan yozing.")
        return
    await state.update_data(topic=topic[:TOOLS[(await state.get_data()).get("tool", "slayd")].get("max_len", 1500)])
    kb = InlineKeyboardBuilder()
    for code, (label, _) in LANGS.items():
        kb.button(text=label, callback_data=f"l:{code}")
    kb.adjust(3)
    await m.answer("Tilni tanlang:", reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("l:"))
async def got_lang(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if "tool" not in data:
        await cb.answer("Qaytadan boshlang: /menu", show_alert=True)
        return
    await state.update_data(lang=cb.data[2:])
    tool = TOOLS[data["tool"]]
    kb = InlineKeyboardBuilder()
    for i, o in enumerate(tool["options"]):
        label = o["label"] if "so'm" in o["label"] else f"{o['label']} · {som(o['price'])}"
        kb.button(text=label, callback_data=f"o:{i}")
    kb.adjust(1)
    await cb.message.answer("Hajmni tanlang (bosganingizda ish boshlanadi, narx balansdan yechiladi):",
                            reply_markup=kb.as_markup())
    await cb.answer()


@router.callback_query(F.data.startswith("o:"))
async def got_option(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not all(k in data for k in ("tool", "topic", "lang")):
        await cb.answer("Qaytadan boshlang: /menu", show_alert=True)
        return
    await state.clear()
    key, topic, lang = data["tool"], data["topic"], data["lang"]
    opt = TOOLS[key]["options"][int(cb.data[2:])]
    price = opt["price"]
    uid = cb.from_user.id
    db.get_or_create_user(uid, cb.from_user.full_name)
    if db.count_running(uid) >= MAX_RUNNING_JOBS:
        await cb.message.answer("Sizda hozir 2 ta ish tayyorlanmoqda. Biri tugagach yangisini boshlang.")
        await cb.answer()
        return

    if not db.charge(uid, price, f"{key}: {topic[:60]}"):
        u = db.get_user(uid)
        await cb.message.answer(f"Balans yetarli emas.\nKerak: {som(price)}\nBalansingiz: {som(u.balance)}\n\n"
                                + wallet_text(uid))
        await cb.answer()
        return

    job_id = db.create_job(uid, key, topic, price)
    await cb.message.answer("⏳ Tayyorlanmoqda, bu 1–3 daqiqa oladi. Tayyor bo'lgach fayl yuboriladi.")
    await cb.answer()
    asyncio.create_task(run_job(cb.bot, cb.message.chat.id, uid, job_id, key, opt, topic, lang, price))


async def run_job(bot: Bot, chat_id: int, uid: int, job_id: int, key: str, opt: dict,
                  topic: str, lang: str, price: int):
    try:
        filename, data = await asyncio.wait_for(generate(key, opt, topic, lang), JOB_TIMEOUT)
        await bot.send_document(chat_id, BufferedInputFile(data, filename=filename),
                                caption=f"✅ Tayyor! {TOOLS[key]['title']}\n\n"
                                        "Faktlar va manbalarni topshirishdan oldin o'zingiz tekshiring.")
        db.finish_job(job_id, "done")
    except Exception as e:  # noqa: BLE001
        log.exception("ish bajarilmadi")
        for a in ADMIN_IDS:
            try:
                await bot.send_message(a, f"⚠️ Ish xatosi (user {uid}, {key}):\n{str(e)[:700]}")
            except Exception:  # noqa: BLE001
                pass
        db.finish_job(job_id, "failed")
        db.add_balance(uid, price, "refund", f"job {job_id}")
        await bot.send_message(chat_id, f"😔 Xatolik yuz berdi. {som(price)} balansingizga qaytarildi. "
                                        "Birozdan so'ng qayta urinib ko'ring.")
    else:
        await bot.send_message(chat_id, "Yana nima yaratamiz? 👇", reply_markup=main_menu("main"))


# ------------------------------------------------------------------ tekin AI yordamchi

@router.message(Chat.talking, F.text)
async def chat_msg(m: Message):
    if m.text.startswith("/"):
        return
    if db.count_today(m.from_user.id, "chat") >= FREE_CHAT_PER_DAY:
        await m.answer(f"Bugungi tekin limit ({FREE_CHAT_PER_DAY} ta) tugadi. Ertaga qaytib keling 🙂")
        return
    db.log_chat(m.from_user.id)
    try:
        sys = ("Siz talabalarga yordam beradigan AI yordamchisiz. Qisqa, aniq va o'zbek tilida (foydalanuvchi boshqa tilda "
               "yozsa, o'sha tilda) javob bering. Narxlar haqida so'ralsa: slayd 2 250 so'm, referat 2 250 so'mdan.")
        await m.answer(await ai.ask(m.text, system=sys, max_tokens=1200))
    except Exception:  # noqa: BLE001
        log.exception("chat xatosi")
        await m.answer("Hozir javob bera olmayman, birozdan so'ng urinib ko'ring.")


@router.message()
async def fallback(m: Message):
    await show_menu(m, "Menyudan tanlang 👇")
