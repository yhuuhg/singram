import asyncio
import sqlite3
import time
import random
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

BOT_TOKEN = "9125288007:AAEq_c9LNw3M-vXkK9x9c2t7DwS4v76MWAM"
ADMIN = "clawdyc"

# Абсолютный путь к базе (очень важно для FadeHost)
DB_PATH = "/data/app/game.db"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Подключаемся к базе
db = sqlite3.connect(DB_PATH, check_same_thread=False)
cur = db.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    name TEXT,
    username TEXT DEFAULT '',
    stars INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    last_click REAL DEFAULT 0,
    games_played INTEGER DEFAULT 0,
    premium_until REAL DEFAULT 0,
    number TEXT
)""")
db.commit()

print(f"DATABASE PATH: {DB_PATH}")
print("Tables created successfully")

class Form(StatesGroup):
    mines_bet = State()
    mines_count = State()
    dice_bet = State()
    roulette_bet = State()
    exchange = State()

def ensure_user(user_obj):
    uid = user_obj.id
    uname = (user_obj.username or "").lower()
    cur.execute("SELECT id FROM users WHERE id = ?", (uid,))
    if not cur.fetchone():
        cur.execute("INSERT INTO users (id, name, username, stars) VALUES (?, ?, ?, 0)",
                    (uid, user_obj.first_name or "Player", uname))
        db.commit()
        print(f"Created user {uid}")
    else:
        cur.execute("UPDATE users SET name = ?, username = ? WHERE id = ?",
                    (user_obj.first_name or "Player", uname, uid))
        db.commit()

def get_stars(uid):
    cur.execute("SELECT stars FROM users WHERE id = ?", (uid,))
    row = cur.fetchone()
    return row[0] if row else 0

def add_stars(uid, amount):
    cur.execute("UPDATE users SET stars = stars + ? WHERE id = ?", (amount, uid))
    db.commit()
    print(f"Added {amount} stars to {uid}. New balance: {get_stars(uid)}")

def fmt(n):
    return f"{n:,}".replace(",", " ")

def main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎮 Игры"), KeyboardButton(text="👤 Профиль")],
            [KeyboardButton(text="⛏ Майнинг"), KeyboardButton(text="🏆 Рейтинг")],
            [KeyboardButton(text="💱 Обменник"), KeyboardButton(text="🛒 Shop")]
        ],
        resize_keyboard=True
    )

def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Меню", callback_data="main")]
    ])

# ====================== START ======================
@dp.message(CommandStart())
async def start(m: types.Message):
    ensure_user(m.from_user)
    balance = get_stars(m.from_user.id)
    await m.answer(f"Главное меню\n\nТвой баланс: {fmt(balance)}⭐", reply_markup=main_kb())

# ====================== PROFILE ======================
@dp.message(F.text == "👤 Профиль")
async def profile(m: types.Message):
    ensure_user(m.from_user)
    uid = m.from_user.id
    cur.execute("SELECT name, stars, level, games_played, premium_until, number FROM users WHERE id=?", (uid,))
    u = cur.fetchone()
    
    cur.execute("SELECT COUNT(*) FROM users WHERE stars > ?", (u[1],))
    rank = cur.fetchone()[0] + 1
    
    prem = "❌"
    if u[4] and u[4] > time.time():
        prem = f"✅ {int((u[4]-time.time())/86400)} дн."
    
    admin = "Администратор" if (m.from_user.username or "").lower() == ADMIN else "Игрок"
    
    text = (f"👤 Профиль\n\n"
            f"Имя: {u[0]}\n"
            f"⭐ Звезды: <b>{fmt(u[1])}</b>\n"
            f"Уровень: {u[2]}\n"
            f"Место: #{rank}\n"
            f"Игр: {u[3]}\n"
            f"Ранг: {admin}\n"
            f"Premium: {prem}\n"
            f"Номер: {u[5] or '—'}")
    await m.answer(text, reply_markup=main_kb(), parse_mode="HTML")

# ====================== MINING ======================
@dp.message(F.text == "⛏ Майнинг")
async def mining(m: types.Message):
    ensure_user(m.from_user)
    uid = m.from_user.id
    now = time.time()
    
    cur.execute("SELECT stars, level, last_click, premium_until FROM users WHERE id=?", (uid,))
    u = cur.fetchone()
    
    if now - u[2] < 1.0:
        return await m.answer(f"⏳ Подожди {round(1.0 - (now - u[2]), 1)} сек")
    
    income = 1
    if u[1] >= 2: income = 5
    if u[1] >= 3: income = 25
    if u[1] >= 4: income = 100
    if u[1] >= 5: income = 1000
    
    if u[3] and u[3] > now:
        income = int(income * 1.5)
    
    add_stars(uid, income)
    cur.execute("UPDATE users SET last_click=? WHERE id=?", (now, uid))
    db.commit()
    
    new_balance = get_stars(uid)
    await m.answer(f"⛏ +{income}⭐\n\nБаланс: <b>{fmt(new_balance)}⭐</b>", 
                   reply_markup=main_kb(), parse_mode="HTML")

# ====================== GIVE ======================
@dp.message(Command("give"))
async def give(m: types.Message):
    if (m.from_user.username or "").lower() != ADMIN:
        return await m.answer("❌ Нет доступа")
    
    try:
        parts = m.text.split()
        amount = int(parts[1])
        uname = parts[2].replace("@", "").lower()
    except:
        return await m.answer("Формат:\n`/give 1000000 username`", parse_mode="Markdown")
    
    cur.execute("SELECT id, stars FROM users WHERE username=?", (uname,))
    row = cur.fetchone()
    
    if not row:
        return await m.answer(f"❌ Пользователь @{uname} не найден в базе")
    
    add_stars(row[0], amount)
    new_bal = get_stars(row[0])
    
    await m.answer(f"✅ Выдано <b>{fmt(amount)}⭐</b> → @{uname}\n"
                   f"Новый баланс: <b>{fmt(new_bal)}⭐</b>", parse_mode="HTML")

# ====================== TOP ======================
@dp.message(F.text == "🏆 Рейтинг")
async def top(m: types.Message):
    ensure_user(m.from_user)
    cur.execute("SELECT name, stars FROM users ORDER BY stars DESC LIMIT 10")
    rows = cur.fetchall()
    text = "🏆 Топ 10:\n\n"
    for i, r in enumerate(rows, 1):
        text += f"{i}. {r[0]} — {fmt(r[1])}⭐\n"
    await m.answer(text, reply_markup=main_kb())

# ====================== GAMES MENU ======================
@dp.message(F.text == "🎮 Игры")
async def games(m: types.Message):
    ensure_user(m.from_user)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💣 Мины", callback_data="mines")],
        [InlineKeyboardButton(text="🚀 Ракета", callback_data="rocket")],
        [InlineKeyboardButton(text="🎲 Кости", callback_data="dice")],
        [InlineKeyboardButton(text="🎰 Рулетка", callback_data="roulette")],
        [InlineKeyboardButton(text="🔙", callback_data="main")]
    ])
    await m.answer("🎮 Выбери игру:", reply_markup=kb)

@dp.callback_query(F.data == "main")
async def cb_main(c: types.CallbackQuery):
    await c.message.answer("Главное меню", reply_markup=main_kb())
    await c.answer()

# ====================== SHOP ======================
@dp.message(F.text == "🛒 Shop")
async def shop(m: types.Message):
    ensure_user(m.from_user)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Premium 10М", callback_data="buy_prem")],
        [InlineKeyboardButton(text="📱 +888 — 10М", callback_data="buy_888")],
        [InlineKeyboardButton(text="📱 +7 — 1М", callback_data="buy_7")],
        [InlineKeyboardButton(text="📱 +380 — 1М", callback_data="buy_380")],
        [InlineKeyboardButton(text="🔙", callback_data="main")]
    ])
    await m.answer("🛒 Магазин", reply_markup=kb)

@dp.callback_query(F.data == "buy_prem")
async def buy_prem(c: types.CallbackQuery):
    ensure_user(c.from_user)
    uid = c.from_user.id
    if get_stars(uid) < 10_000_000:
        return await c.answer("Недостаточно звёзд!", show_alert=True)
    
    add_stars(uid, -10_000_000)
    cur.execute("UPDATE users SET premium_until=? WHERE id=?", (time.time() + 30*86400, uid))
    db.commit()
    await c.message.edit_text("✅ Premium куплен на 30 дней!", reply_markup=back_kb())
    await c.answer()

@dp.callback_query(F.data.startswith("buy_"))
async def buy_number(c: types.CallbackQuery):
    ensure_user(c.from_user)
    uid = c.from_user.id
    code = c.data.split("_")[1]
    price = 10_000_000 if code == "888" else 1_000_000
    
    if get_stars(uid) < price:
        return await c.answer("Недостаточно звёзд!", show_alert=True)
    
    if code == "888":
        number = f"+888{random.randint(10000000,99999999)}"
    elif code == "7":
        number = f"+7{random.randint(9000000000,9999999999)}"
    else:
        number = f"+380{random.randint(100000000,999999999)}"
    
    add_stars(uid, -price)
    cur.execute("UPDATE users SET number=? WHERE id=?", (number, uid))
    db.commit()
    await c.message.edit_text(f"✅ Номер:\n`{number}`", reply_markup=back_kb(), parse_mode="Markdown")
    await c.answer()

# ====================== EXCHANGE ======================
@dp.message(F.text == "💱 Обменник")
async def exchange(m: types.Message, state: FSMContext):
    ensure_user(m.from_user)
    await m.answer("💱 1 TON = 200⭐\nНапиши количество TON:")
    await state.set_state(Form.exchange)

@dp.message(Form.exchange)
async def do_exchange(m: types.Message, state: FSMContext):
    try:
        ton = float(m.text.replace(",", "."))
        if ton <= 0: raise ValueError
    except:
        await state.clear()
        return await m.answer("Неверное число", reply_markup=main_kb())
    
    add = int(ton * 200)
    add_stars(m.from_user.id, add)
    await state.clear()
    await m.answer(f"✅ +{fmt(add)}⭐\nБаланс: {fmt(get_stars(m.from_user.id))}⭐", reply_markup=main_kb())

# ====================== DICE ======================
@dp.callback_query(F.data == "dice")
async
