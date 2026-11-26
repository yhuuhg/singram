import asyncio
import sqlite3
import time
import random
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

BOT_TOKEN = "9125288007:AAEq_c9LNw3M-vXkK9x9c2t7DwS4v76MWAM"
ADMIN = "clawdyc"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

db = sqlite3.connect("game.db", check_same_thread=False)
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

cur.execute("""CREATE TABLE IF NOT EXISTS active_mines (
    user_id INTEGER PRIMARY KEY,
    bet INTEGER,
    mines INTEGER,
    opened TEXT,
    bombs TEXT,
    mult REAL DEFAULT 1.0
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS active_rocket (
    user_id INTEGER PRIMARY KEY,
    bet INTEGER,
    crash REAL,
    start REAL,
    status TEXT
)""")
db.commit()

class Form(StatesGroup):
    mines_bet = State()
    mines_count = State()
    dice_bet = State()
    roulette_bet = State()
    exchange = State()

def user(user_obj):
    uid = user_obj.id
    uname = (user_obj.username or "").lower()
    cur.execute("SELECT id FROM users WHERE id=?", (uid,))
    if not cur.fetchone():
        cur.execute("INSERT INTO users (id, name, username) VALUES (?,?,?)",
                    (uid, user_obj.first_name or "Player", uname))
    else:
        cur.execute("UPDATE users SET name=?, username=? WHERE id=?",
                    (user_obj.first_name or "Player", uname, uid))
    db.commit()

def get(uid):
    cur.execute("SELECT name, stars, level, last_click, games_played, premium_until, number FROM users WHERE id=?", (uid,))
    return cur.fetchone()

def stars(uid, amount):
    cur.execute("UPDATE users SET stars = stars + ? WHERE id=?", (amount, uid))
    db.commit()

def fmt(n):
    return f"{n:,}".replace(",", " ")

def kb_main():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🎮 Игры"), KeyboardButton(text="👤 Профиль")],
        [KeyboardButton(text="⛏ Майнинг"), KeyboardButton(text="🏆 Рейтинг")],
        [KeyboardButton(text="💱 Обменник"), KeyboardButton(text="🛒 Shop")]
    ], resize_keyboard=True)

def kb_back():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Меню", callback_data="main")]])

# ====================== START ======================
@dp.message(CommandStart())
async def start(m: types.Message):
    user(m.from_user)
    await m.answer("Главное меню", reply_markup=kb_main())

# ====================== MENU ======================
@dp.message(F.text == "⛏ Майнинг")
async def mining(m: types.Message):
    user(m.from_user)
    uid = m.from_user.id
    u = get(uid)
    now = time.time()

    if now - u[3] < 1:
        return await m.answer(f"⏳ Подожди {round(1-(now-u[3]),1)} сек")

    income = 1
    if u[2] >= 2: income = 5
    if u[2] >= 3: income = 25
    if u[2] >= 4: income = 100
    if u[2] >= 5: income = 1000
    if u[5] and u[5] > now:
        income = int(income * 1.5)

    stars(uid, income)
    cur.execute("UPDATE users SET last_click=? WHERE id=?", (now, uid))
    db.commit()
    u = get(uid)
    await m.answer(f"⛏ +{income}⭐\nВсего: {fmt(u[1])}⭐", reply_markup=kb_main())

@dp.message(F.text == "👤 Профиль")
async def profile(m: types.Message):
    user(m.from_user)
    uid = m.from_user.id
    u = get(uid)
    cur.execute("SELECT COUNT(*) FROM users WHERE stars > ?", (u[1],))
    rank = cur.fetchone()[0] + 1
    prem = f"✅ {int((u[5]-time.time())/86400)} дн." if u[5] and u[5] > time.time() else "❌"
    num = u[6] or "—"
    admin = "Администратор" if (m.from_user.username or "").lower() == ADMIN else "Игрок"

    text = (f"👤 Профиль\n\n"
            f"Имя: {u[0]}\n"
            f"⭐ Звезды: {fmt(u[1])}\n"
            f"Уровень: {u[2]}\n"
            f"Место: #{rank}\n"
            f"Игр: {u[4]}\n"
            f"Ранг: {admin}\n"
            f"Premium: {prem}\n"
            f"Номер: {num}")
    await m.answer(text, reply_markup=kb_main())

@dp.message(F.text == "🏆 Рейтинг")
async def top(m: types.Message):
    user(m.from_user)
    cur.execute("SELECT name, stars FROM users ORDER BY stars DESC LIMIT 10")
    rows = cur.fetchall()
    text = "🏆 Топ 10:\n\n"
    for i, r in enumerate(rows, 1):
        text += f"{i}. {r[0]} — {fmt(r[1])}⭐\n"
    await m.answer(text, reply_markup=kb_main())

@dp.message(F.text == "🎮 Игры")
async def games(m: types.Message):
    user(m.from_user)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💣 Мины", callback_data="mines")],
        [InlineKeyboardButton(text="🚀 Ракета", callback_data="rocket")],
        [InlineKeyboardButton(text="🎲 Кости", callback_data="dice")],
        [InlineKeyboardButton(text="🎰 Рулетка", callback_data="roulette")],
        [InlineKeyboardButton(text="🔙", callback_data="main")]
    ])
    await m.answer("🎮 Выбери игру:", reply_markup=kb)

@dp.message(F.text == "🛒 Shop")
async def shop(m: types.Message):
    user(m.from_user)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Premium 10М", callback_data="buy_prem")],
        [InlineKeyboardButton(text="📱 +888 10М", callback_data="buy_888")],
        [InlineKeyboardButton(text="📱 +7 1М", callback_data="buy_7")],
        [InlineKeyboardButton(text="📱 +380 1М", callback_data="buy_380")],
        [InlineKeyboardButton(text="🔙", callback_data="main")]
    ])
    await m.answer("🛒 Магазин", reply_markup=kb)

@dp.message(F.text == "💱 Обменник")
async def exchange(m: types.Message, state: FSMContext):
    user(m.from_user)
    await m.answer("💱 1 TON = 200⭐\nНапиши количество TON:")
    await state.set_state(Form.exchange)

@dp.message(Form.exchange)
async def do_exchange(m: types.Message, state: FSMContext):
    try:
        ton = float(m.text.replace(",", "."))
        if ton <= 0: raise ValueError
    except:
        await state.clear()
        return await m.answer("Неверное число", reply_markup=kb_main())
    add = int(ton * 200)
    stars(m.from_user.id, add)
    await state.clear()
    await m.answer(f"✅ +{fmt(add)}⭐", reply_markup=kb_main())

# ====================== ADMIN ======================
@dp.message(Command("give"))
async def give(m: types.Message):
    if (m.from_user.username or "").lower() != ADMIN:
        return await m.answer("❌ Нет доступа")

    try:
        parts = m.text.split()
        amount = int(parts[1])
        uname = parts[2].replace("@", "").lower()
    except:
        return await m.answer("Формат: /give 100000 username")

    cur.execute("SELECT id FROM users WHERE username=?", (uname,))
    row = cur.fetchone()
    if not row:
        return await m.answer("❌ Пользователь не найден")

    stars(row[0], amount)
    await m.answer(f"✅ Выдано {fmt(amount)}⭐ → @{uname}")

@dp.message(Command("news"))
async def news(m: types.Message):
    if (m.from_user.username or "").lower() != ADMIN:
        return await m.answer("❌ Нет доступа")
    text = m.text[6:].strip()
    if not text:
        return await m.answer("Формат: /news текст")
    cur.execute("SELECT id FROM users")
    c = 0
    for (uid,) in cur.fetchall():
        try:
            await bot.send_message(uid, f"📢 {text}")
            c += 1
        except: pass
    await m.answer(f"✅ Отправлено {c}")

# ====================== CALLBACKS ======================
@dp.callback_query(F.data == "main")
async def cb_main(c: types.CallbackQuery):
    await c.message.answer("Главное меню", reply_markup=kb_main())
    await c.answer()

@dp.callback_query(F.data == "buy_prem")
async def buy_prem(c: types.CallbackQuery):
    user(c.from_user)
    u = get(c.from_user.id)
    if u[1] < 10_000_000:
        return await c.answer("Недостаточно звёзд", show_alert=True)
    stars(c.from_user.id, -10_000_000)
    cur.execute("UPDATE users SET premium_until=? WHERE id=?", (time.time()+30*86400, c.from_user.id))
    db.commit()
    await c.message.edit_text("✅ Premium на 30 дней!", reply_markup=kb_back())
    await c.answer()

@dp.callback_query(F.data.startswith("buy_"))
async def buy_num(c: types.CallbackQuery):
    user(c.from_user)
    code = c.data.split("_")[1]
    price = 10_000_000 if code == "888" else 1_000_000
    u = get(c.from_user.id)
    if u[1] < price:
        return await c.answer("Недостаточно звёзд", show_alert=True)

    if code == "888":
        num = f"+888{random.randint(10000000,99999999)}"
    elif code == "7":
        num = f"+7{random.randint(9000000000,9999999999)}"
    else:
        num = f"+380{random.randint(100000000,999999999)}"

    stars(c.from_user.id, -price)
    cur.execute("UPDATE users SET number=? WHERE id=?", (num, c.from_user.id))
    db.commit()
    await c.message.edit_text(f"✅ Номер:\n`{num}`", reply_markup=kb_back(), parse_mode="Markdown")
    await c.answer()

# ====================== MINES ======================
@dp.callback_query(F.data == "mines")
async def mines(c: types.CallbackQuery, state: FSMContext):
    user(c.from_user)
    await state.set_state(Form.mines_bet)
    await c.message.edit_text("💣 Напиши ставку:")
    await c.answer()

@dp.message(Form.mines_bet)
async def mines_bet(m: types.Message, state: FSMContext):
    try:
        bet = int(m.text.replace(" ", ""))
        if bet < 100 or bet > 1000000: raise ValueError
    except:
        return await m.answer("Число от 100 до 1 000 000")
    if get(m.from_user.id)[1] < bet:
        await state.clear()
        return await m.answer("Недостаточно звёзд", reply_markup=kb_main())
    await state.update_data(bet=bet)
    await state.set_state(Form.mines_count)
    await m.answer("Количество мин (1-24):")

@dp.message(Form.mines_count)
async def mines_count(m: types.Message, state: FSMContext):
    try:
        mines = int(m.text)
        if not 1 <= mines <= 24: raise ValueError
    except:
        return await m.answer("От 1 до 24")
    data = await state.get_data()
    bet = data["bet"]
    await state.clear()
    uid = m.from_user.id
    if get(uid)[1] < bet:
        return await m.answer("Недостаточно звёзд", reply_markup=kb_main())

    stars(uid, -bet)
    bombs = random.sample(range(25), mines)
    cur.execute("INSERT OR REPLACE INTO active_mines VALUES (?,?,?,?,?,1.0)",
                (uid, bet, mines, "", ",".join(map(str, bombs))))
    db.commit()

    kb = []
    row = []
    for i in range(25):
        row.append(InlineKeyboardButton(text="🔲", callback_data=f"open_{i}"))
        if len(row) == 5:
            kb.append(row)
            row = []
    kb.append([InlineKeyboardButton(text="💰 Забрать", callback_data="cash")])
    kb.append([InlineKeyboardButton(text="🔙", callback_data="main")])
    await m.answer(f"💣 Мины ×{mines} | Ставка {fmt(bet)}⭐", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("open_"))
async def open_cell(c: types.CallbackQuery):
    uid = c.from_user.id
    cell = int(c.data.split("_")[1])
    cur.execute("SELECT bet, mines, opened, bombs FROM active_mines WHERE user_id=?", (uid,))
    s = cur.fetchone()
    if not s:
        return await c.answer("Нет игры")

    bet, mines, opened_s, bombs_s = s
    opened = [int(x) for x in opened_s.split(",")] if opened_s else []
    bombs = [int(x) for x in bombs_s.split(",")]

    if cell in opened:
        return await c.answer("Уже открыто")
    if cell in bombs:
        cur.execute("DELETE FROM active_mines WHERE user_id=?", (uid,))
        db.commit()
        await c.message.edit_text(f"💥 БУМ! -{fmt(bet)}⭐", reply_markup=kb_back())
        return await c.answer()

    opened.append(cell)
    safe = 25 - mines
    k = len(opened)
    p = 1.0
    for i in range(k):
        p *= (safe - i) / (25 - i)
    mult = min(round((1/p)*0.96, 2), 50)
    win = int(bet * mult)

    cur.execute("UPDATE active_mines SET opened=?, mult=? WHERE user_id=?",
                (",".join(map(str, opened)), mult, uid))
    db.commit()

    if len(opened) == safe:
        stars(uid, win)
        cur.execute("DELETE FROM active_mines WHERE user_id=?", (uid,))
        db.commit()
        await c.message.edit_text(f"✅ Все открыты! +{fmt(win)}⭐", reply_markup=kb_back())
        return await c.answer()

    kb = []
    row = []
    for i in range(25):
        t = "✅" if i in opened else "🔲"
        row.append(InlineKeyboardButton(text=t, callback_data=f"open_{i}" if i not in opened else "x"))
        if len(row) == 5:
            kb.append(row)
            row = []
    kb.append([InlineKeyboardButton(text="💰 Забрать", callback_data="cash")])
    kb.append([InlineKeyboardButton(text="🔙", callback_data="main")])
    await c.message.edit_text(f"💣 {mult}x | {fmt(win)}⭐", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await c.answer()

@dp.callback_query(F.data == "cash")
async def cashout(c: types.CallbackQuery):
    uid = c.from_user.id
    cur.execute("SELECT bet, mult FROM active_mines WHERE user_id=?", (uid,))
    s = cur.fetchone()
    if not s:
        return await c.answer("Нет игры")
    win = int(s[0] * s[1])
    stars(uid, win)
    cur.execute("DELETE FROM active_mines WHERE user_id=?", (uid,))
    db.commit()
    await c.message.edit_text(f"✅ +{fmt(win)}⭐", reply_markup=kb_back())
    await c.answer()

@dp.callback_query(F.data == "x")
async def x(c: types.CallbackQuery):
    await c.answer()

# ====================== ROCKET ======================
@dp.callback_query(F.data == "rocket")
async def rocket_menu(c: types.CallbackQuery):
    user(c.from_user)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="100", callback_data="rk_100"),
         InlineKeyboardButton(text="1K", callback_data="rk_1000"),
         InlineKeyboardButton(text="10K", callback_data="rk_10000")],
        [InlineKeyboardButton(text="100K", callback_data="rk_100000"),
         InlineKeyboardButton(text="1M", callback_data="rk_1000000")],
        [InlineKeyboardButton(text="🔙", callback_data="main")]
    ])
    await c.message.edit_text("🚀 Выбери ставку:", reply_markup=kb)
    await c.answer()

@dp.callback_query(F.data.startswith("rk_"))
async def rocket_start(c: types.CallbackQuery):
    uid = c.from_user.id
    bet = int(c.data.split("_")[1])
    u = get(uid)
    if u[1] < bet:
        return await c.answer("Недостаточно звёзд", show_alert=True)

    cur.execute("SELECT 1 FROM active_rocket WHERE user_id=?", (uid,))
    if cur.fetchone():
        return await c.answer("Уже летит", show_alert=True)

    stars(uid, -bet)
    crash = round(random.uniform(1.3, 8.0), 2)
    cur.execute("INSERT INTO active_rocket VALUES (?,?,?,?,'flying')", (uid, bet, crash, time.time()))
    db.commit()
    asyncio.create_task(rocket_fly(c.message, uid, bet, crash))
    await c.answer()

async def rocket_fly(msg, uid, bet, crash):
    mult = 1.0
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💰 ЗАБРАТЬ", callback_data="rk_cash")]])
    try:
        while True:
            cur.execute("SELECT status FROM active_rocket WHERE user_id=?", (uid,))
            r = cur.fetchone()
            if not r or r[0] != "flying":
                break
            mult = round(mult + 0.15 + mult*0.03, 2)
            if mult >= crash:
                cur.execute("DELETE FROM active_rocket WHERE user_id=?", (uid,))
                db.commit()
                await msg.edit_text(f"💥 {crash}x\n-{fmt(bet)}⭐", reply_markup=kb_back())
                break
            try:
                await msg.edit_text(f"🚀 {mult}x\n{fmt(int(bet*mult))}⭐", reply_markup=kb)
            except: pass
            await asyncio.sleep(0.65)
    except:
        cur.execute("DELETE FROM active_rocket WHERE user_id=?", (uid,))
        db.commit()

@dp.callback_query(F.data == "rk_cash")
async def rocket_cash(c: types.CallbackQuery):
    uid = c.from_user.id
    cur.execute("SELECT bet, crash, start, status FROM active_rocket WHERE user_id=?", (uid,))
    r = cur.fetchone()
    if not r or r[3] != "flying":
        return await c.answer("Поздно")

    elapsed = time.time() - r[2]
    mult = round(1.0 + elapsed * 0.22, 2)
    if mult >= r[1]:
        return await c.answer("Уже взорвалась")

    win = int(r[0] * mult)
    stars(uid, win)
    cur.execute("DELETE FROM active_rocket WHERE user_id=?", (uid,))
    db.commit()
    await c.message.edit_text(f"✅ {mult}x\n+{fmt(win)}⭐", reply_markup=kb_back())
    await c.answer()

# ====================== DICE ======================
@dp.callback_query(F.data == "dice")
async def dice(c: types.CallbackQuery, state: FSMContext):
    user(c.from_user)
    await state.set_state(Form.dice_bet)
    await c.message.edit_text("🎲 Напиши ставку:")
    await c.answer()

@dp.message(Form.dice_bet)
async def dice_play(m: types.Message, state: FSMContext):
    try:
        bet = int(m.text.replace(" ", ""))
        if bet < 100 or bet > 1000000: raise ValueError
    except:
        return await m.answer("Число от 100 до 1М")
    uid = m.from_user.id
    if get(uid)[1] < bet:
        await state.clear()
        return await m.answer("Недостаточно звёзд", reply_markup=kb_main())

    await state.clear()
    stars(uid, -bet)

    anim = await m.answer("🎲 Бросаем...")
    faces = ["⚀","⚁","⚂","⚃","⚄","⚅"]
    for _ in range(7):
        try:
            await anim.edit_text(f"🎲\nТы: {random.choice(faces)}\nБот: {random.choice(faces)}")
        except: pass
        await asyncio.sleep(0.28)

    p, b = random.randint(1,6), random.randint(1,6)
    if p > b:
        stars(uid, bet*2)
        txt = f"✅ {faces[p-1]} vs {faces[b-1]}\n+{fmt(bet)}⭐"
    elif p < b:
        txt = f"❌ {faces[p-1]} vs {faces[b-1]}\n-{fmt(bet)}⭐"
    else:
        stars(uid, bet)
        txt = f"🤝 {faces[p-1]} vs {faces[b-1]}\nНичья"
    await anim.edit_text(txt, reply_markup=kb_back())

# ====================== ROULETTE ======================
@dp.callback_query(F.data == "roulette")
async def roulette(c: types.CallbackQuery, state: FSMContext):
    user(c.from_user)
    await state.set_state(Form.roulette_bet)
    await c.message.edit_text("🎰 Напиши ставку:")
    await c.answer()

@dp.message(Form.roulette_bet)
async def roulette_bet(m: types.Message, state: FSMContext):
    try:
        bet = int(m.text.replace(" ", ""))
        if bet < 100 or bet > 1000000: raise ValueError
    except:
        return await m.answer("Число от 100 до 1М")
    if get(m.from_user.id)[1] < bet:
        await state.clear()
        return await m.answer("Недостаточно звёзд", reply_markup=kb_main())
    await state.update_data(bet=bet)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔴", callback_data="rl_red"),
         InlineKeyboardButton(text="⚫", callback_data="rl_black"),
         InlineKeyboardButton(text="⚪", callback_data="rl_white")]
    ])
    await m.answer("Выбери цвет:", reply_markup=kb)

@dp.callback_query(F.data.startswith("rl_"))
async def roulette_play(c: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    bet = data.get("bet")
    await state.clear()
    if not bet:
        return await c.answer()
    uid = c.from_user.id
    color = c.data.split("_")[1]
    if get(uid)[1] < bet:
        return await c.answer("Недостаточно звёзд", show_alert=True)

    stars(uid, -bet)

    cols = ["🔴","⚫","⚪"]
    for i in range(10):
        random.shuffle(cols)
        try:
            await c.message.edit_text(f"🎰 {' '.join(cols)}\n⬇️")
        except: pass
        await asyncio.sleep(0.27 if i < 7 else 0.4)

    res = random.choice(["red","black","white"])
    emoji = {"red":"🔴","black":"⚫","white":"⚪"}[res]
    if color == res:
        stars(uid, bet*2)
        txt = f"✅ {emoji}\n+{fmt(bet)}⭐"
    else:
        txt = f"❌ {emoji}\n-{fmt(bet)}⭐"
    await c.message.edit_text(txt, reply_markup=kb_back())
    await c.answer()

# ====================== RUN ======================
async def main():
    print("BOT STARTED")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
