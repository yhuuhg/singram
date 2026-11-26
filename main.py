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
ADMIN_USERNAME = "clawdyc"

bot = Bot(BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

db = sqlite3.connect("game.db", check_same_thread=False)
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    name TEXT,
    username TEXT DEFAULT '',
    stars INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    last_click REAL DEFAULT 0,
    join_date REAL DEFAULT 0,
    games_played INTEGER DEFAULT 0,
    is_admin INTEGER DEFAULT 0,
    premium_until REAL DEFAULT 0,
    number TEXT DEFAULT NULL
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS active_mines (
    user_id INTEGER PRIMARY KEY,
    bet INTEGER,
    mines_count INTEGER,
    opened TEXT,
    mine_positions TEXT,
    multiplier REAL DEFAULT 1.0
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS active_rocket (
    user_id INTEGER PRIMARY KEY,
    bet INTEGER,
    crash_point REAL,
    start_time REAL,
    status TEXT DEFAULT 'flying'
)
""")
db.commit()

LEVELS = {1: 1, 2: 5, 3: 25, 4: 100, 5: 1000}

class BetState(StatesGroup):
    mines_bet = State()
    mines_count = State()
    dice_bet = State()
    roulette_bet = State()
    exchange = State()

def ensure_user(user: types.User):
    uid = user.id
    username = (user.username or "").lower()
    is_adm = 1 if username == ADMIN_USERNAME.lower() else 0

    cur.execute("SELECT id FROM users WHERE id=?", (uid,))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users (id, name, username, join_date, is_admin) VALUES (?, ?, ?, ?, ?)",
            (uid, user.first_name, username, time.time(), is_adm)
        )
    else:
        cur.execute(
            "UPDATE users SET name=?, username=?, is_admin=? WHERE id=?",
            (user.first_name, username, is_adm, uid)
        )
    db.commit()

def get_user(uid):
    cur.execute("SELECT name, stars, level, last_click, games_played, is_admin, premium_until, number FROM users WHERE id=?", (uid,))
    return cur.fetchone()

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
async def cmd_start(msg: types.Message):
    ensure_user(msg.from_user)
    await msg.answer("Главное меню\n\nВыбери раздел:", reply_markup=main_kb())

# ====================== REPLY BUTTONS ======================
@dp.message(F.text == "⛏ Майнинг")
async def btn_mining(msg: types.Message):
    ensure_user(msg.from_user)
    uid = msg.from_user.id
    now = time.time()
    u = get_user(uid)

    if now - u[3] < 1.0:
        return await msg.answer(f"⏳ Подожди {round(1 - (now - u[3]), 1)} сек.")

    income = LEVELS.get(u[2], 1)
    if u[6] and u[6] > now:
        income = int(income * 1.5)

    cur.execute("UPDATE users SET stars = stars + ?, last_click = ? WHERE id=?", (income, now, uid))
    db.commit()
    u = get_user(uid)

    await msg.answer(f"⛏ +{income}⭐\n\nВсего: {fmt(u[1])}⭐\nУровень: {u[2]}", reply_markup=main_kb())

@dp.message(F.text == "👤 Профиль")
async def btn_profile(msg: types.Message):
    ensure_user(msg.from_user)
    uid = msg.from_user.id
    u = get_user(uid)

    cur.execute("SELECT COUNT(*) FROM users WHERE stars > ?", (u[1],))
    rank = cur.fetchone()[0] + 1

    premium = "❌"
    if u[6] and u[6] > time.time():
        days = int((u[6] - time.time()) / 86400)
        premium = f"✅ {days} дн."

    number = u[7] if u[7] else "—"
    rank_name = "Администратор" if (msg.from_user.username or "").lower() == ADMIN_USERNAME else "Игрок"

    text = (
        f"👤 Профиль\n\n"
        f"Имя: {u[0]}\n"
        f"⭐ Звезды: {fmt(u[1])}\n"
        f"Уровень: {u[2]}\n"
        f"Место: #{rank}\n"
        f"Игр: {u[4]}\n"
        f"Ранг: {rank_name}\n"
        f"Premium: {premium}\n"
        f"Номер: {number}"
    )
    await msg.answer(text, reply_markup=main_kb())

@dp.message(F.text == "🏆 Рейтинг")
async def btn_top(msg: types.Message):
    ensure_user(msg.from_user)
    cur.execute("SELECT name, stars FROM users ORDER BY stars DESC LIMIT 10")
    rows = cur.fetchall()
    text = "🏆 Топ 10:\n\n"
    for i, r in enumerate(rows, 1):
        text += f"{i}. {r[0]} — {fmt(r[1])}⭐\n"
    await msg.answer(text, reply_markup=main_kb())

@dp.message(F.text == "🎮 Игры")
async def btn_games(msg: types.Message):
    ensure_user(msg.from_user)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💣 Мины", callback_data="mines")],
        [InlineKeyboardButton(text="🚀 Ракета", callback_data="rocket")],
        [InlineKeyboardButton(text="🎲 Кости", callback_data="dice")],
        [InlineKeyboardButton(text="🎰 Рулетка", callback_data="roulette")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main")]
    ])
    await msg.answer("🎮 Выбери игру:", reply_markup=kb)

@dp.message(F.text == "🛒 Shop")
async def btn_shop(msg: types.Message):
    ensure_user(msg.from_user)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Premium 10М (30д)", callback_data="buy_premium")],
        [InlineKeyboardButton(text="📱 +888 — 10М", callback_data="buy_888")],
        [InlineKeyboardButton(text="📱 +7 — 1М", callback_data="buy_7")],
        [InlineKeyboardButton(text="📱 +380 — 1М", callback_data="buy_380")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main")]
    ])
    await msg.answer("🛒 Магазин", reply_markup=kb)

@dp.message(F.text == "💱 Обменник")
async def btn_exchange(msg: types.Message, state: FSMContext):
    ensure_user(msg.from_user)
    await msg.answer("💱 1 TON = 200⭐\nНапиши количество TON:")
    await state.set_state(BetState.exchange)

@dp.message(BetState.exchange)
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
    await msg.answer(f"✅ +{fmt(stars)}⭐", reply_markup=main_kb())

# ====================== ADMIN ======================
@dp.message(Command("give"))
async def cmd_give(msg: types.Message):
    if (msg.from_user.username or "").lower() != ADMIN_USERNAME:
        return await msg.answer("❌ Нет доступа")

    try:
        parts = msg.text.split()
        amount = int(parts[1])
        username = parts[2].replace("@", "").lower()
    except:
        return await msg.answer("Формат: /give 50000 username")

    cur.execute("SELECT id FROM users WHERE LOWER(username)=?", (username,))
    row = cur.fetchone()
    if not row:
        return await msg.answer("❌ Пользователь не найден")

    cur.execute("UPDATE users SET stars = stars + ? WHERE id=?", (amount, row[0]))
    db.commit()
    await msg.answer(f"✅ Выдано {fmt(amount)}⭐ → @{username}")

@dp.message(Command("news"))
async def cmd_news(msg: types.Message):
    if (msg.from_user.username or "").lower() != ADMIN_USERNAME:
        return await msg.answer("❌ Нет доступа")

    text = msg.text[6:].strip()
    if not text:
        return await msg.answer("Формат: /news текст")

    cur.execute("SELECT id FROM users")
    count = 0
    for (uid,) in cur.fetchall():
        try:
            await bot.send_message(uid, f"📢 {text}")
            count += 1
        except:
            pass
    await msg.answer(f"✅ Отправлено {count} игрокам")

# ====================== CALLBACKS ======================
@dp.callback_query(F.data == "main")
async def cb_main(cb: types.CallbackQuery):
    await cb.message.answer("Главное меню", reply_markup=main_kb())

@dp.callback_query(F.data == "buy_premium")
async def buy_premium(cb: types.CallbackQuery):
    ensure_user(cb.from_user)
    uid = cb.from_user.id
    u = get_user(uid)
    if u[1] < 10_000_000:
        return await cb.answer("Недостаточно звёзд!", show_alert=True)

    cur.execute("UPDATE users SET stars = stars - 10000000, premium_until = ? WHERE id=?",
                (time.time() + 30*86400, uid))
    db.commit()
    await cb.message.edit_text("✅ Premium куплен на 30 дней!", reply_markup=back_kb())

@dp.callback_query(F.data.in_(["buy_888", "buy_7", "buy_380"]))
async def buy_number(cb: types.CallbackQuery):
    ensure_user(cb.from_user)
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
    await cb.message.edit_text(f"✅ Номер получен:\n`{number}`", reply_markup=back_kb(), parse_mode="Markdown")

# ====================== MINES ======================
@dp.callback_query(F.data == "mines")
async def mines_start(cb: types.CallbackQuery, state: FSMContext):
    ensure_user(cb.from_user)
    await state.set_state(BetState.mines_bet)
    await cb.message.edit_text("💣 Мины\nНапиши ставку (число):")

@dp.message(BetState.mines_bet)
async def mines_bet(msg: types.Message, state: FSMContext):
    try:
        bet = int(msg.text.replace(" ", "").replace(",", ""))
        if bet < 100 or bet > 1_000_000:
            return await msg.answer("Ставка от 100 до 1 000 000")
    except:
        return await msg.answer("Напиши просто число")

    if get_user(msg.from_user.id)[1] < bet:
        await state.clear()
        return await msg.answer("Недостаточно звёзд!", reply_markup=main_kb())

    await state.update_data(bet=bet)
    await state.set_state(BetState.mines_count)
    await msg.answer("Теперь количество мин (1–24):")

@dp.message(BetState.mines_count)
async def mines_count(msg: types.Message, state: FSMContext):
    try:
        mines = int(msg.text)
        if not 1 <= mines <= 24:
            return await msg.answer("От 1 до 24")
    except:
        return await msg.answer("Напиши число")

    data = await state.get_data()
    bet = data["bet"]
    await state.clear()
    uid = msg.from_user.id

    if get_user(uid)[1] < bet:
        return await msg.answer("Недостаточно звёзд!", reply_markup=main_kb())

    cur.execute("UPDATE users SET stars = stars - ? WHERE id=?", (bet, uid))
    positions = random.sample(range(25), mines)
    cur.execute("INSERT OR REPLACE INTO active_mines VALUES (?,?,?,?,?,1.0)",
                (uid, bet, mines, "", ",".join(map(str, positions))))
    db.commit()

    kb = []
    row = []
    for i in range(25):
        row.append(InlineKeyboardButton(text="🔲", callback_data=f"m_{i}"))
        if len(row) == 5:
            kb.append(row)
            row = []
    kb.append([InlineKeyboardButton(text="💰 Забрать", callback_data="m_cash")])
    kb.append([InlineKeyboardButton(text="🔙", callback_data="main")])

    await msg.answer(f"💣 Мины ×{mines}\nСтавка: {fmt(bet)}⭐", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("m_"))
async def mines_click(cb: types.CallbackQuery):
    uid = cb.from_user.id
    data = cb.data

    if data == "m_cash":
        cur.execute("SELECT bet, multiplier FROM active_mines WHERE user_id=?", (uid,))
        s = cur.fetchone()
        if not s:
            return await cb.answer("Нет игры")
        win = int(s[0] * s[1])
        cur.execute("UPDATE users SET stars = stars + ? WHERE id=?", (win, uid))
        cur.execute("DELETE FROM active_mines WHERE user_id=?", (uid,))
        db.commit()
        await cb.message.edit_text(f"✅ Забрал {fmt(win)}⭐", reply_markup=back_kb())
        return

    cell = int(data.split("_")[1])
    cur.execute("SELECT bet, mines_count, opened, mine_positions FROM active_mines WHERE user_id=?", (uid,))
    s = cur.fetchone()
    if not s:
        return await cb.answer("Нет игры")

    bet, mines, opened_str, pos_str = s
    opened = [int(x) for x in opened_str.split(",")] if opened_str else []
    bombs = [int(x) for x in pos_str.split(",")]

    if cell in opened:
        return await cb.answer("Уже открыто")

    if cell in bombs:
        cur.execute("DELETE FROM active_mines WHERE user_id=?", (uid,))
        db.commit()
        await cb.message.edit_text(f"💥 БУМ! -{fmt(bet)}⭐", reply_markup=back_kb())
        return

    opened.append(cell)
    safe = 25 - mines
    k = len(opened)
    prob = 1.0
    for i in range(k):
        prob *= (safe - i) / (25 - i)
    mult = min(round((1/prob)*0.95, 2), 100)
    win = int(bet * mult)

    cur.execute("UPDATE active_mines SET opened=?, multiplier=? WHERE user_id=?",
                (",".join(map(str, opened)), mult, uid))
    db.commit()

    if len(opened) == safe:
        cur.execute("UPDATE users SET stars = stars + ? WHERE id=?", (win, uid))
        cur.execute("DELETE FROM active_mines WHERE user_id=?", (uid,))
        db.commit()
        await cb.message.edit_text(f"✅ Все открыты! +{fmt(win)}⭐", reply_markup=back_kb())
        return

    kb = []
    row = []
    for i in range(25):
        txt = "✅" if i in opened else "🔲"
        row.append(InlineKeyboardButton(text=txt, callback_data=f"m_{i}" if i not in opened else "noop"))
        if len(row) == 5:
            kb.append(row)
            row = []
    kb.append([InlineKeyboardButton(text="💰 Забрать", callback_data="m_cash")])
    kb.append([InlineKeyboardButton(text="🔙", callback_data="main")])

    await cb.message.edit_text(f"💣 {mult}x | {fmt(win)}⭐", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "noop")
async def noop(cb: types.CallbackQuery):
    await cb.answer()

# ====================== ROCKET ======================
@dp.callback_query(F.data == "rocket")
async def rocket_menu(cb: types.CallbackQuery):
    ensure_user(cb.from_user)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="100", callback_data="r_100"),
         InlineKeyboardButton(text="1K", callback_data="r_1000"),
         InlineKeyboardButton(text="10K", callback_data="r_10000")],
        [InlineKeyboardButton(text="100K", callback_data="r_100000"),
         InlineKeyboardButton(text="1M", callback_data="r_1000000")],
        [InlineKeyboardButton(text="🔙", callback_data="main")]
    ])
    await cb.message.edit_text("🚀 Выбери ставку:", reply_markup=kb)

@dp.callback_query(F.data.startswith("r_"))
async def rocket_start(cb: types.CallbackQuery):
    uid = cb.from_user.id
    bet = int(cb.data.split("_")[1])
    u = get_user(uid)

    if u[1] < bet:
        return await cb.answer("Недостаточно звёзд!", show_alert=True)

    cur.execute("SELECT 1 FROM active_rocket WHERE user_id=?", (uid,))
    if cur.fetchone():
        return await cb.answer("Уже летит!", show_alert=True)

    cur.execute("UPDATE users SET stars = stars - ? WHERE id=?", (bet, uid))
    crash = round(random.uniform(1.2, 10.0), 2)
    cur.execute("INSERT INTO active_rocket VALUES (?,?,?,?, 'flying')", (uid, bet, crash, time.time()))
    db.commit()

    asyncio.create_task(rocket_loop(cb.message, uid, bet, crash))

async def rocket_loop(message, uid, bet, crash):
    mult = 1.0
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💰 ЗАБРАТЬ", callback_data="r_cash")]])
    try:
        while True:
            cur.execute("SELECT status FROM active_rocket WHERE user_id=?", (uid,))
            row = cur.fetchone()
            if not row or row[0] != "flying":
                break

            mult = round(mult + 0.2 + mult*0.05, 2)
            if mult >= crash:
                cur.execute("DELETE FROM active_rocket WHERE user_id=?", (uid,))
                db.commit()
                await message.edit_text(f"💥 {crash}x\n-{fmt(bet)}⭐", reply_markup=back_kb())
                break

            try:
                await message.edit_text(f"🚀 {mult}x\n{fmt(int(bet*mult))}⭐", reply_markup=kb)
            except:
                pass
            await asyncio.sleep(0.7)
    except:
        cur.execute("DELETE FROM active_rocket WHERE user_id=?", (uid,))
        db.commit()

@dp.callback_query(F.data == "r_cash")
async def rocket_cash(cb: types.CallbackQuery):
    uid = cb.from_user.id
    cur.execute("SELECT bet, status FROM active_rocket WHERE user_id=?", (uid,))
    row = cur.fetchone()
    if not row or row[1] != "flying":
        return await cb.answer("Поздно")

    win = int(row[0] * 2.0)
    cur.execute("UPDATE users SET stars = stars + ? WHERE id=?", (win, uid))
    cur.execute("DELETE FROM active_rocket WHERE user_id=?", (uid,))
    db.commit()
    await cb.message.edit_text(f"✅ +{fmt(win)}⭐", reply_markup=back_kb())

# ====================== DICE (с анимацией) ======================
@dp.callback_query(F.data == "dice")
async def dice_start(cb: types.CallbackQuery, state: FSMContext):
    ensure_user(cb.from_user)
    await state.set_state(BetState.dice_bet)
    await cb.message.edit_text("🎲 Напиши ставку:")

@dp.message(BetState.dice_bet)
async def dice_play(msg: types.Message, state: FSMContext):
    try:
        bet = int(msg.text.replace(" ", "").replace(",", ""))
        if bet < 100 or bet > 1_000_000:
            return await msg.answer("Ставка от 100 до 1 000 000")
    except:
        return await msg.answer("Напиши просто число")

    uid = msg.from_user.id
    u = get_user(uid)
    if u[1] < bet:
        await state.clear()
        return await msg.answer("Недостаточно звёзд!", reply_markup=main_kb())

    await state.clear()
    cur.execute("UPDATE users SET stars = stars - ? WHERE id=?", (bet, uid))
    db.commit()

    # Анимация костей
    anim_msg = await msg.answer("🎲 Бросаем кости...")

    dice_faces = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]

    for _ in range(7):
        p = random.choice(dice_faces)
        b = random.choice(dice_faces)
        try:
            await anim_msg.edit_text(f"🎲 Бросаем...\n\nТы:  {p}\nБот: {b}")
        except:
            pass
        await asyncio.sleep(0.32)

    # Финальный результат
    player = random.randint(1, 6)
    bot_dice = random.randint(1, 6)

    player_face = dice_faces[player-1]
    bot_face = dice_faces[bot_dice-1]

    if player > bot_dice:
        cur.execute("UPDATE users SET stars = stars + ? WHERE id=?", (bet * 2, uid))
        result = f"✅ Победа!\n\nТы:  {player_face} ({player})\nБот: {bot_face} ({bot_dice})\n\n+{fmt(bet)}⭐"
    elif player < bot_dice:
        result = f"❌ Поражение\n\nТы:  {player_face} ({player})\nБот: {bot_face} ({bot_dice})\n\n-{fmt(bet)}⭐"
    else:
        cur.execute("UPDATE users SET stars = stars + ? WHERE id=?", (bet, uid))
        result = f"🤝 Ничья!\n\nТы:  {player_face} ({player})\nБот: {bot_face} ({bot_dice})\n\nСтавка возвращена"

    db.commit()
    await anim_msg.edit_text(result, reply_markup=back_kb())

# ====================== ROULETTE (с анимацией) ======================
@dp.callback_query(F.data == "roulette")
async def roulette_start(cb: types.CallbackQuery, state: FSMContext):
    ensure_user(cb.from_user)
    await state.set_state(BetState.roulette_bet)
    await cb.message.edit_text("🎰 Напиши ставку:")

@dp.message(BetState.roulette_bet)
async def roulette_bet(msg: types.Message, state: FSMContext):
    try:
        bet = int(msg.text.replace(" ", "").replace(",", ""))
        if bet < 100 or bet > 1_000_000:
            return await msg.answer("Ставка от 100 до 1 000 000")
    except:
        return await msg.answer("Напиши просто число")

    if get_user(msg.from_user.id)[1] < bet:
        await state.clear()
        return await msg.answer("Недостаточно звёзд!", reply_markup=main_kb())

    await state.update_data(bet=bet)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔴 Красный", callback_data="ro_red")],
        [InlineKeyboardButton(text="⚫ Чёрный", callback_data="ro_black")],
        [InlineKeyboardButton(text="⚪ Белый", callback_data="ro_white")]
    ])
    await msg.answer("Выбери цвет:", reply_markup=kb)

@dp.callback_query(F.data.startswith("ro_"))
async def roulette_play(cb: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    bet = data.get("bet")
    await state.clear()
    if not bet:
        return

    uid = cb.from_user.id
    color = cb.data.split("_")[1]

    u = get_user(uid)
    if u[1] < bet:
        return await cb.answer("Недостаточно звёзд!", show_alert=True)

    cur.execute("UPDATE users SET stars = stars - ? WHERE id=?", (bet, uid))
    db.commit()

    # Анимация рулетки
    colors = ["🔴", "⚫", "⚪"]
    msg = cb.message

    for i in range(11):
        random.shuffle(colors)
        text = f"🎰 Крутится...\n\n{'   '.join(colors)}\n\n⬇️"
        try:
            await msg.edit_text(text)
        except:
            pass
        await asyncio.sleep(0.26 if i < 8 else 0.42)

    # Результат
    result = random.choice(["red", "black", "white"])
    emoji = {"red": "🔴", "black": "⚫", "white": "⚪"}[result]

    if color == result:
        cur.execute("UPDATE users SET stars = stars + ? WHERE id=?", (bet * 2, uid))
        text = f"✅ Победа!\n\nВыпало: {emoji}\n\n+{fmt(bet)}⭐"
    else:
        text = f"❌ Проигрыш\n\nВыпало: {emoji}\n\n-{fmt(bet)}⭐"

    db.commit()
    await msg.edit_text(text, reply_markup=back_kb())

async def main():
    print("BOT STARTED")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
