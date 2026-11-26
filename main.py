import asyncio
import sqlite3
import time
import random
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

BOT_TOKEN = "9125288007:AAEq_c9LNw3M-vXkK9x9c2t7DwS4v76MWAM"
ADMIN_USERNAME = "clawdyc"

bot = Bot(BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

db = sqlite3.connect("game.db", check_same_thread=False)
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY,
    name TEXT,
    username TEXT,
    stars INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    last_click REAL DEFAULT 0,
    join_date REAL DEFAULT 0,
    games_played INTEGER DEFAULT 0,
    lang TEXT DEFAULT 'ru',
    is_admin INTEGER DEFAULT 0,
    premium_until REAL DEFAULT 0,
    number TEXT DEFAULT NULL
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS active_mines(
    user_id INTEGER PRIMARY KEY,
    bet INTEGER,
    mines_count INTEGER,
    opened TEXT,
    mine_positions TEXT,
    multiplier REAL DEFAULT 1.0
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS active_rocket(
    user_id INTEGER PRIMARY KEY,
    bet INTEGER,
    crash_point REAL,
    start_time REAL,
    status TEXT DEFAULT 'flying'
)
""")
db.commit()

LEVELS = {1: 1, 2: 5, 3: 25, 4: 100, 5: 1000}

class MinesStates(StatesGroup):
    waiting_bet = State()
    waiting_mines = State()

class DiceStates(StatesGroup):
    waiting_bet = State()

class RouletteStates(StatesGroup):
    waiting_bet = State()

def is_admin(user: types.User) -> bool:
    return bool(user.username and user.username.lower() == ADMIN_USERNAME.lower())

def get_user(uid):
    cur.execute("SELECT name, stars, level, last_click, games_played, is_admin, lang, premium_until, number FROM users WHERE id=?", (uid,))
    return cur.fetchone()

def get_rank(uid):
    cur.execute("SELECT COUNT(*) FROM users WHERE stars > (SELECT stars FROM users WHERE id=?)", (uid,))
    return cur.fetchone()[0] + 1

def fmt(num):
    return f"{num:,}".replace(",", " ")

def main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎮 Игры"), KeyboardButton(text="👤 Профиль")],
            [KeyboardButton(text="⛏ Майнинг"), KeyboardButton(text="🏆 Рейтинг")],
            [KeyboardButton(text="💱 Обменник"), KeyboardButton(text="🛒 Shop")]
        ],
        resize_keyboard=True
    )

def back_ikb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main")]
    ])

# ====================== START ======================
@dp.message(CommandStart())
async def start(msg: types.Message):
    uid = msg.from_user.id
    username = msg.from_user.username or ""
    admin = 1 if is_admin(msg.from_user) else 0

    cur.execute("""
        INSERT OR IGNORE INTO users(id, name, username, join_date, is_admin)
        VALUES(?,?,?,?,?)
    """, (uid, msg.from_user.first_name, username, time.time(), admin))

    if admin:
        cur.execute("UPDATE users SET is_admin=1, username=? WHERE id=?", (username, uid))
    db.commit()

    await msg.answer("Главное меню\n\nВыбери раздел:", reply_markup=main_kb())

# ====================== REPLY BUTTONS ======================
@dp.message(F.text == "⛏ Майнинг")
async def mining_button(msg: types.Message):
    uid = msg.from_user.id
    now = time.time()
    u = get_user(uid)

    if not u:
        return await msg.answer("Сначала нажми /start")

    if now - u[3] < 1.0:
        return await msg.answer("⏳ Подожди 1 секунду!")

    income = LEVELS.get(u[2], 1)
    if u[7] and u[7] > time.time():  # premium
        income = int(income * 1.5)

    cur.execute("UPDATE users SET stars = stars + ?, last_click = ? WHERE id=?", (income, now, uid))
    db.commit()

    u = get_user(uid)
    await msg.answer(
        f"⛏ Майнинг\n\n"
        f"⭐ Всего: {fmt(u[1])}\n"
        f"Уровень: {u[2]}\n\n"
        f"+{income}⭐",
        reply_markup=main_kb()
    )

@dp.message(F.text == "👤 Профиль")
async def profile_button(msg: types.Message):
    uid = msg.from_user.id
    u = get_user(uid)
    if not u:
        return await msg.answer("Сначала /start")

    rank = get_rank(uid)
    rank_name = "Администратор" if is_admin(msg.from_user) else "Игрок"

    premium = "❌"
    if u[7] and u[7] > time.time():
        days = int((u[7] - time.time()) / 86400)
        premium = f"✅ ещё {days} дн."

    number = u[8] if u[8] else "—"

    text = (
        f"👤 Профиль\n\n"
        f"Имя: {u[0]}\n"
        f"⭐ Звезды: {fmt(u[1])}\n"
        f"Уровень майнинга: {u[2]}\n"
        f"Место в рейтинге: #{rank}\n"
        f"Сыграно игр: {u[4]}\n"
        f"Ранг: {rank_name}\n"
        f"Premium: {premium}\n"
        f"Номер: {number}"
    )
    await msg.answer(text, reply_markup=main_kb())

@dp.message(F.text == "🏆 Рейтинг")
async def top_button(msg: types.Message):
    cur.execute("SELECT name, stars FROM users ORDER BY stars DESC LIMIT 10")
    rows = cur.fetchall()
    text = "🏆 Топ 10 игроков:\n\n"
    for i, row in enumerate(rows, 1):
        text += f"{i}. {row[0]} — {fmt(row[1])}⭐\n"
    await msg.answer(text, reply_markup=main_kb())

@dp.message(F.text == "🎮 Игры")
async def games_button(msg: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💣 Мины", callback_data="mines_menu")],
        [InlineKeyboardButton(text="🚀 Ракета", callback_data="rocket_menu")],
        [InlineKeyboardButton(text="🎲 Кости", callback_data="dice_menu")],
        [InlineKeyboardButton(text="🎰 Рулетка", callback_data="roulette_menu")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main")]
    ])
    await msg.answer("🎮 Игры\n\nВыбери игру:", reply_markup=kb)

@dp.message(F.text == "🛒 Shop")
async def shop_button(msg: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Premium — 10М ⭐ (30 дней)", callback_data="buy_premium")],
        [InlineKeyboardButton(text="📱 +888 — 10М ⭐", callback_data="buy_888")],
        [InlineKeyboardButton(text="📱 +7 — 1М ⭐", callback_data="buy_7")],
        [InlineKeyboardButton(text="📱 +380 — 1М ⭐", callback_data="buy_380")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main")]
    ])
    await msg.answer("🛒 Магазин", reply_markup=kb)

@dp.message(F.text == "💱 Обменник")
async def exchange_button(msg: types.Message, state: FSMContext):
    await msg.answer("💱 Обменник\n\nКурс: 1 TON = 200 ⭐\n\nВведи количество TON:")
    await state.set_state("exchange")

@dp.message(F.state == "exchange")
async def process_exchange(msg: types.Message, state: FSMContext):
    try:
        ton = float(msg.text.replace(",", "."))
        if ton <= 0:
            raise ValueError
    except:
        await state.clear()
        return await msg.answer("❌ Неверное число", reply_markup=main_kb())

    stars = int(ton * 200)
    cur.execute("UPDATE users SET stars = stars + ? WHERE id=?", (stars, msg.from_user.id))
    db.commit()
    await state.clear()
    await msg.answer(f"✅ Получено +{fmt(stars)} ⭐", reply_markup=main_kb())

# ====================== ADMIN ======================
@dp.message(Command("give"))
async def give_cmd(msg: types.Message):
    if not is_admin(msg.from_user):
        return await msg.answer("❌ Нет доступа")

    try:
        parts = msg.text.split()
        amount = int(parts[1])
        username = parts[2].replace("@", "").lower()
    except:
        return await msg.answer("Использование: /give сумма юзернейм")

    cur.execute("SELECT id FROM users WHERE LOWER(username)=?", (username,))
    row = cur.fetchone()
    if not row:
        return await msg.answer("❌ Пользователь не найден")

    cur.execute("UPDATE users SET stars = stars + ? WHERE id=?", (amount, row[0]))
    db.commit()
    await msg.answer(f"✅ Выдано {fmt(amount)}⭐ пользователю @{username}")

@dp.message(Command("news"))
async def news_cmd(msg: types.Message):
    if not is_admin(msg.from_user):
        return await msg.answer("❌ Нет доступа")

    text = msg.text[6:].strip()
    if not text:
        return await msg.answer("Использование: /news текст")

    cur.execute("SELECT id FROM users")
    users = cur.fetchall()
    count = 0
    for (uid,) in users:
        try:
            await bot.send_message(uid, f"📢 {text}")
            count += 1
        except:
            pass
    await msg.answer(f"✅ Отправлено {count} игрокам")

# ====================== CALLBACKS ======================
@dp.callback_query(F.data == "main")
async def cb_main(cb: types.CallbackQuery):
    await cb.message.answer("Главное меню\n\nВыбери раздел:", reply_markup=main_kb())

@dp.callback_query(F.data == "buy_premium")
async def buy_premium(cb: types.CallbackQuery):
    uid = cb.from_user.id
    u = get_user(uid)
    if u[1] < 10_000_000:
        return await cb.answer("Недостаточно звёзд!", show_alert=True)

    cur.execute("UPDATE users SET stars = stars - 10000000, premium_until = ? WHERE id=?",
                (time.time() + 30 * 86400, uid))
    db.commit()
    await cb.message.edit_text("✅ Premium куплен на 30 дней!", reply_markup=back_ikb())

@dp.callback_query(F.data.in_(["buy_888", "buy_7", "buy_380"]))
async def buy_number(cb: types.CallbackQuery):
    uid = cb.from_user.id
    u = get_user(uid)
    code = cb.data.split("_")[1]

    price = 10_000_000 if code == "888" else 1_000_000
    if u[1] < price:
        return await cb.answer("Недостаточно звёзд!", show_alert=True)

    if code == "888":
        number = f"+888{random.randint(10000000, 99999999)}"
    elif code == "7":
        number = f"+7{random.randint(9000000000, 9999999999)}"
    else:
        number = f"+380{random.randint(100000000, 999999999)}"

    cur.execute("UPDATE users SET stars = stars - ?, number = ? WHERE id=?", (price, number, uid))
    db.commit()
    await cb.message.edit_text(f"✅ Номер получен!\n\n`{number}`", reply_markup=back_ikb(), parse_mode="Markdown")

# ====================== MINES ======================
@dp.callback_query(F.data == "mines_menu")
async def mines_menu(cb: types.CallbackQuery, state: FSMContext):
    await state.set_state(MinesStates.waiting_bet)
    await cb.message.edit_text("💣 Мины\n\nВведи ставку (100 — 1 000 000):")

@dp.message(MinesStates.waiting_bet)
async def mines_bet(msg: types.Message, state: FSMContext):
    try:
        bet = int(msg.text.replace(" ", ""))
        if bet < 100 or bet > 1_000_000:
            return await msg.answer("Ставка от 100 до 1 000 000")
    except:
        return await msg.answer("Введи число")

    u = get_user(msg.from_user.id)
    if u[1] < bet:
        await state.clear()
        return await msg.answer("Недостаточно звёзд!", reply_markup=main_kb())

    await state.update_data(bet=bet)
    await state.set_state(MinesStates.waiting_mines)
    await msg.answer("Теперь введи количество мин (1–24):")

@dp.message(MinesStates.waiting_mines)
async def mines_count(msg: types.Message, state: FSMContext):
    try:
        mines = int(msg.text)
        if mines < 1 or mines > 24:
            return await msg.answer("От 1 до 24")
    except:
        return await msg.answer("Введи число")

    data = await state.get_data()
    bet = data["bet"]
    await state.clear()

    uid = msg.from_user.id
    u = get_user(uid)
    if u[1] < bet:
        return await msg.answer("Недостаточно звёзд!", reply_markup=main_kb())

    cur.execute("UPDATE users SET stars = stars - ? WHERE id=?", (bet, uid))
    positions = random.sample(range(25), mines)
    cur.execute("INSERT OR REPLACE INTO active_mines VALUES (?,?,?,?,?,?)",
                (uid, bet, mines, "", ",".join(map(str, positions)), 1.0))
    db.commit()

    kb = []
    row = []
    for i in range(25):
        row.append(InlineKeyboardButton(text="🔲", callback_data=f"open_{i}"))
        if len(row) == 5:
            kb.append(row)
            row = []
    kb.append([InlineKeyboardButton(text="💰 Забрать", callback_data="cashout")])
    kb.append([InlineKeyboardButton(text="🔙 Меню", callback_data="main")])

    await msg.answer(f"💣 Мины ({mines})\nСтавка: {fmt(bet)}⭐\nМножитель: 1.00x",
                     reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("open_"))
async def open_cell(cb: types.CallbackQuery):
    uid = cb.from_user.id
    cell = int(cb.data.split("_")[1])

    cur.execute("SELECT bet, mines_count, opened, mine_positions FROM active_mines WHERE user_id=?", (uid,))
    s = cur.fetchone()
    if not s:
        return await cb.answer("Игра не найдена")

    bet, mines, opened_str, pos_str = s
    opened = [int(x) for x in opened_str.split(",")] if opened_str else []
    mines_pos = [int(x) for x in pos_str.split(",")]

    if cell in opened:
        return await cb.answer("Уже открыто")

    if cell in mines_pos:
        cur.execute("DELETE FROM active_mines WHERE user_id=?", (uid,))
        db.commit()
        await cb.message.edit_text(f"💥 БУМ! Ставка {fmt(bet)}⭐ сгорела.", reply_markup=back_ikb())
        return

    opened.append(cell)
    safe = 25 - mines
    k = len(opened)
    prob = 1.0
    for i in range(k):
        prob *= (safe - i) / (25 - i)
    mult = min(round((1 / prob) * 0.95, 2), 100.0)
    win = int(bet * mult)

    cur.execute("UPDATE active_mines SET opened=?, multiplier=? WHERE user_id=?",
                (",".join(map(str, opened)), mult, uid))
    db.commit()

    if len(opened) == safe:
        cur.execute("UPDATE users SET stars = stars + ? WHERE id=?", (win, uid))
        cur.execute("DELETE FROM active_mines WHERE user_id=?", (uid,))
        db.commit()
        await cb.message.edit_text(f"✅ Все клетки открыты!\nВыигрыш: {fmt(win)}⭐", reply_markup=back_ikb())
        return

    # rebuild keyboard
    kb = []
    row = []
    for i in range(25):
        txt = "✅" if i in opened else "🔲"
        row.append(InlineKeyboardButton(text=txt, callback_data=f"open_{i}" if i not in opened else "noop"))
        if len(row) == 5:
            kb.append(row)
            row = []
    kb.append([InlineKeyboardButton(text="💰 Забрать", callback_data="cashout")])
    kb.append([InlineKeyboardButton(text="🔙 Меню", callback_data="main")])

    await cb.message.edit_text(
        f"💣 Мины ({mines})\nСтавка: {fmt(bet)}⭐\nМножитель: {mult}x\nВыигрыш: {fmt(win)}⭐",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )

@dp.callback_query(F.data == "cashout")
async def cashout(cb: types.CallbackQuery):
    uid = cb.from_user.id
    cur.execute("SELECT bet, multiplier FROM active_mines WHERE user_id=?", (uid,))
    s = cur.fetchone()
    if not s:
        return await cb.answer("Нет игры")

    bet, mult = s
    win = int(bet * mult)
    cur.execute("UPDATE users SET stars = stars + ? WHERE id=?", (win, uid))
    cur.execute("DELETE FROM active_mines WHERE user_id=?", (uid,))
    db.commit()
    await cb.message.edit_text(f"✅ Забрал {fmt(win)}⭐", reply_markup=back_ikb())

@dp.callback_query(F.data == "noop")
async def noop(cb: types.CallbackQuery):
    await cb.answer()

# ====================== ROCKET (упрощённый) ======================
@dp.callback_query(F.data == "rocket_menu")
async def rocket_menu(cb: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="100", callback_data="rocket_100"),
         InlineKeyboardButton(text="1000", callback_data="rocket_1000"),
         InlineKeyboardButton(text="10000", callback_data="rocket_10000")],
        [InlineKeyboardButton(text="100000", callback_data="rocket_100000"),
         InlineKeyboardButton(text="1000000", callback_data="rocket_1000000")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main")]
    ])
    await cb.message.edit_text("🚀 Ракета\nВыбери ставку:", reply_markup=kb)

@dp.callback_query(F.data.startswith("rocket_"))
async def rocket_start(cb: types.CallbackQuery):
    uid = cb.from_user.id
    bet = int(cb.data.split("_")[1])
    u = get_user(uid)

    if u[1] < bet:
        return await cb.answer("Недостаточно звёзд!", show_alert=True)

    cur.execute("SELECT 1 FROM active_rocket WHERE user_id=?", (uid,))
    if cur.fetchone():
        return await cb.answer("Уже есть активная ракета!", show_alert=True)

    cur.execute("UPDATE users SET stars = stars - ? WHERE id=?", (bet, uid))
    crash = round(random.uniform(1.01, 15.0), 2)
    cur.execute("INSERT INTO active_rocket VALUES (?,?,?,?,?)", (uid, bet, crash, time.time(), "flying"))
    db.commit()

    asyncio.create_task(rocket_loop(cb.message, uid, bet, crash))

async def rocket_loop(message, uid, bet, crash):
    mult = 1.00
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 ЗАБРАТЬ", callback_data="rocket_cash")]
    ])
    try:
        while True:
            cur.execute("SELECT status FROM active_rocket WHERE user_id=?", (uid,))
            row = cur.fetchone()
            if not row or row[0] != "flying":
                break

            mult = round(mult + 0.15 + (mult * 0.03), 2)
            if mult >= crash:
                cur.execute("DELETE FROM active_rocket WHERE user_id=?", (uid,))
                db.commit()
                await message.edit_text(f"💥 Взорвалась на {crash}x\nПотерял {fmt(bet)}⭐", reply_markup=back_ikb())
                break

            win = int(bet * mult)
            try:
                await message.edit_text(
                    f"🚀 Летит...\n\nМножитель: <b>{mult}x</b>\nВыигрыш: {fmt(win)}⭐",
                    reply_markup=kb, parse_mode="HTML"
                )
            except:
                pass
            await asyncio.sleep(0.8)
    except:
        cur.execute("DELETE FROM active_rocket WHERE user_id=?", (uid,))
        db.commit()

@dp.callback_query(F.data == "rocket_cash")
async def rocket_cash(cb: types.CallbackQuery):
    uid = cb.from_user.id
    cur.execute("SELECT bet, crash_point, start_time, status FROM active_rocket WHERE user_id=?", (uid,))
    row = cur.fetchone()
    if not row or row[3] != "flying":
        return await cb.answer("Уже поздно")

    bet = row[0]
    # просто даём текущий приблизительный множитель
    mult = 2.0  # упрощённо
    win = int(bet * mult)

    cur.execute("UPDATE users SET stars = stars + ? WHERE id=?", (win, uid))
    cur.execute("DELETE FROM active_rocket WHERE user_id=?", (uid,))
    db.commit()
    await cb.message.edit_text(f"✅ Забрал {fmt(win)}⭐", reply_markup=back_ikb())

# ====================== DICE ======================
@dp.callback_query(F.data == "dice_menu")
async def dice_menu(cb: types.CallbackQuery, state: FSMContext):
    await state.set_state(DiceStates.waiting_bet)
    await cb.message.edit_text("🎲 Кости\nВведи ставку (100–1000000):")

@dp.message(DiceStates.waiting_bet)
async def dice_bet(msg: types.Message, state: FSMContext):
    try:
        bet = int(msg.text.replace(" ", ""))
        if bet < 100 or bet > 1000000:
            return await msg.answer("От 100 до 1 000 000")
    except:
        return await msg.answer("Введи число")

    uid = msg.from_user.id
    u = get_user(uid)
    if u[1] < bet:
        await state.clear()
        return await msg.answer("Недостаточно звёзд!", reply_markup=main_kb())

    await state.clear()
    cur.execute("UPDATE users SET stars = stars - ? WHERE id=?", (bet, uid))

    player = random.randint(1, 6)
    bot_d = random.randint(1, 6)

    if player > bot_d:
        cur.execute("UPDATE users SET stars = stars + ? WHERE id=?", (bet * 2, uid))
        text = f"✅ Победа!\nТы: {player} | Бот: {bot_d}\n+{fmt(bet)}⭐"
    elif player < bot_d:
        text = f"❌ Поражение\nТы: {player} | Бот: {bot_d}\n-{fmt(bet)}⭐"
    else:
        cur.execute("UPDATE users SET stars = stars + ? WHERE id=?", (bet, uid))
        text = f"🤝 Ничья\nТы: {player} | Бот: {bot_d}\nСтавка возвращена"

    db.commit()
    await msg.answer(text, reply_markup=main_kb())

# ====================== ROULETTE ======================
@dp.callback_query(F.data == "roulette_menu")
async def roulette_menu(cb: types.CallbackQuery, state: FSMContext):
    await state.set_state(RouletteStates.waiting_bet)
    await cb.message.edit_text("🎰 Рулетка\nВведи ставку:")

@dp.message(RouletteStates.waiting_bet)
async def roulette_bet(msg: types.Message, state: FSMContext):
    try:
        bet = int(msg.text.replace(" ", ""))
        if bet < 100 or bet > 1000000:
            return await msg.answer("От 100 до 1 000 000")
    except:
        return await msg.answer("Введи число")

    uid = msg.from_user.id
    u = get_user(uid)
    if u[1] < bet:
        await state.clear()
        return await msg.answer("Недостаточно звёзд!", reply_markup=main_kb())

    await state.update_data(bet=bet)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔴 Красный", callback_data="rou_red")],
        [InlineKeyboardButton(text="⚫ Чёрный", callback_data="rou_black")],
        [InlineKeyboardButton(text="⚪ Белый", callback_data="rou_white")]
    ])
    await msg.answer("Выбери цвет:", reply_markup=kb)

@dp.callback_query(F.data.startswith("rou_"))
async def roulette_play(cb: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    bet = data.get("bet")
    await state.clear()
    if not bet:
        return

    uid = cb.from_user.id
    color = cb.data.split("_")[1]

    cur.execute("UPDATE users SET stars = stars - ? WHERE id=?", (bet, uid))
    db.commit()

    # простая анимация
    for _ in range(5):
        emojis = random.sample(["🔴", "⚫", "⚪"], 3)
        try:
            await cb.message.edit_text(f"🎰 {' | '.join(emojis)}")
        except:
            pass
        await asyncio.sleep(0.3)

    result = random.choice(["red", "black", "white"])
    emoji = {"red": "🔴", "black": "⚫", "white": "⚪"}[result]

    if color == result:
        cur.execute("UPDATE users SET stars = stars + ? WHERE id=?", (bet * 2, uid))
        text = f"✅ Победа! Выпало {emoji}\n+{fmt(bet)}⭐"
    else:
        text = f"❌ Проигрыш. Выпало {emoji}\n-{fmt(bet)}⭐"

    db.commit()
    await cb.message.edit_text(text, reply_markup=back_ikb())

async def main():
    print("BOT STARTED")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
