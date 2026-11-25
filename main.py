import asyncio, sqlite3, time, random, math
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = "9125288007:AAEq_c9LNw3M-vXkK9x9c2t7DwS4v76MWAM"

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

db = sqlite3.connect("game.db", check_same_thread=False)
cur = db.cursor()
cur.execute("""CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY, name TEXT, stars INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1, last_click REAL DEFAULT 0, join_date REAL DEFAULT 0,
    games_played INTEGER DEFAULT 0
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS active_mines(
    user_id INTEGER PRIMARY KEY,
    bet INTEGER,
    mines_count INTEGER,
    opened TEXT,
    mine_positions TEXT,
    multiplier REAL DEFAULT 1.0
)""")
db.commit()

LEVELS = {1: 1, 2: 5, 3: 25, 4: 100, 5: 1000}

def get_user(uid):
    cur.execute("SELECT name, stars, level, last_click, games_played FROM users WHERE id=?", (uid,))
    return cur.fetchone()

def get_rank(uid):
    cur.execute("SELECT COUNT(*) FROM users WHERE stars > (SELECT stars FROM users WHERE id=?)", (uid,))
    return cur.fetchone()[0] + 1

def fmt(num):
    return f"{num:,}".replace(",", " ")

def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Игры", callback_data="games"), InlineKeyboardButton(text="👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton(text="⛏ Майнинг", callback_data="mining"), InlineKeyboardButton(text="🏆 Рейтинг", callback_data="top")]
    ])

def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main")]
    ])

def mining_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⛏ Фарм", callback_data="farm")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main")]
    ])

def mines_grid(mines_count, opened_list):
    kb = []
    row = []
    for i in range(25):
        if i in opened_list:
            row.append(InlineKeyboardButton(text="✅", callback_data="noop"))
        else:
            row.append(InlineKeyboardButton(text="🔲", callback_data=f"open_{i}"))
        if len(row) == 5:
            kb.append(row)
            row = []
    
    kb.append([InlineKeyboardButton(text="💰 Забрать", callback_data="cashout")])
    kb.append([InlineKeyboardButton(text="🔙 Главное меню", callback_data="main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

@dp.message(CommandStart())
async def start(msg: types.Message):
    cur.execute("INSERT OR IGNORE INTO users(id, name, join_date) VALUES(?,?,?)", 
                (msg.from_user.id, msg.from_user.first_name, time.time()))
    db.commit()
    await msg.answer("Главное меню\n\nВыбери раздел:", reply_markup=main_kb())

@dp.callback_query(lambda c: c.data == "main")
async def main_menu(cb: types.CallbackQuery):
    await cb.message.edit_text("Главное меню\n\nВыбери раздел:", reply_markup=main_kb())

@dp.callback_query(lambda c: c.data == "mining")
async def mining(cb: types.CallbackQuery):
    u = get_user(cb.from_user.id)
    await cb.message.edit_text(f"Майнинг\n\n⭐ Всего: {fmt(u[1])}\nУровень: {u[2]}\n\nЖми кнопку ниже:", reply_markup=mining_kb())

@dp.callback_query(lambda c: c.data == "farm")
async def farm(cb: types.CallbackQuery):
    uid = cb.from_user.id
    now = time.time()
    u = get_user(uid)
    if now - u[3] < 1.0:
        return await cb.answer("Подожди 1 секунду!", show_alert=True)
    income = LEVELS[u[2]]
    cur.execute("UPDATE users SET stars = stars + ?, last_click = ? WHERE id=?", (income, now, uid))
    db.commit()
    u = get_user(uid)
    await cb.message.edit_text(f"Майнинг\n\n⭐ Всего: {fmt(u[1])}\nУровень: {u[2]}\n\nЖми кнопку ниже:", reply_markup=mining_kb())
    await cb.answer(f"+{income}⭐")

@dp.callback_query(lambda c: c.data == "profile")
async def profile(cb: types.CallbackQuery):
    uid = cb.from_user.id
    u = get_user(uid)
    rank = get_rank(uid)
    await cb.message.edit_text(
        f"👤 Профиль\n\nИмя: {u[0]}\n⭐ Звезды: {fmt(u[1])}\nУровень майнинга: {u[2]}\nМесто в рейтинге: #{rank}\nСыграно игр: {u[4]}", 
        reply_markup=back_kb()
    )

@dp.callback_query(lambda c: c.data == "top")
async def top(cb: types.CallbackQuery):
    cur.execute("SELECT name, stars FROM users ORDER BY stars DESC LIMIT 10")
    rows = cur.fetchall()
    text = "🏆 Топ 10 игроков:\n\n"
    for i, row in enumerate(rows, 1):
        text += f"{i}. {row[0]} — {fmt(row[1])}⭐\n"
    await cb.message.edit_text(text, reply_markup=back_kb())

@dp.callback_query(lambda c: c.data == "games")
async def games(cb: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💣 Мины", callback_data="mines_menu")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main")]
    ])
    await cb.message.edit_text("🎮 Игры\n\nВыбери игру:", reply_markup=kb)

@dp.callback_query(lambda c: c.data == "mines_menu")
async def mines_menu(cb: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="3 мины", callback_data="mines_3"), InlineKeyboardButton(text="5 мин", callback_data="mines_5")],
        [InlineKeyboardButton(text="10 мин", callback_data="mines_10")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main")]
    ])
    await cb.message.edit_text("💣 Мины\n\nВыбери количество мин (чем больше мин, тем выше множитель):", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("mines_") and c.data != "mines_menu")
async def start_mines(cb: types.CallbackQuery):
    uid = cb.from_user.id
    u = get_user(uid)
    mines_count = int(cb.data.split("_")[1])
    
    if u[1] < 100:
        return await cb.answer("Нужно минимум 100⭐ для игры!", show_alert=True)
        
    bet = 100
    cur.execute("UPDATE users SET stars = stars - ? WHERE id=?", (bet, uid))
    
    positions = random.sample(range(25), mines_count)
    positions_str = ",".join(map(str, positions))
    
    cur.execute("INSERT OR REPLACE INTO active_mines(user_id, bet, mines_count, opened, mine_positions, multiplier) VALUES(?,?,?,?,?,?)",
                (uid, bet, mines_count, "", positions_str, 1.0))
    db.commit()
    
    await cb.message.edit_text(f"💣 Мины ({mines_count} шт)\n\nСтавка: 100⭐\nМножитель: 1.0x\nВыигрыш: 0⭐", reply_markup=mines_grid(mines_count, []))

@dp.callback_query(lambda c: c.data.startswith("open_"))
async def open_cell(cb: types.CallbackQuery):
    uid = cb.from_user.id
    cell = int(cb.data.split("_")[1])
    
    cur.execute("SELECT bet, mines_count, opened, mine_positions, multiplier FROM active_mines WHERE user_id=?", (uid,))
    session = cur.fetchone()
    
    if not session:
        return await cb.answer("Игра не найдена!", show_alert=True)
        
    bet, mines_count, opened_str, mine_pos_str, mult = session
    opened = [int(x) for x in opened_str.split(",")] if opened_str else []
    mine_pos = [int(x) for x in mine_pos_str.split(",")]
    
    if cell in opened:
        return await cb.answer("Уже открыто!")
        
    if cell in mine_pos:
        cur.execute("DELETE FROM active_mines WHERE user_id=?", (uid,))
        cur.execute("UPDATE users SET games_played = games_played + 1 WHERE id=?", (uid,))
        db.commit()
        await cb.message.edit_text(f"💥 БУМ! Ты попал на мину.\nСтавка {bet}⭐ сгорела.", reply_markup=back_kb())
        return
        
    opened.append(cell)
    opened_str = ",".join(map(str, opened))
    
    safe_cells = 25 - mines_count
    k = len(opened)
    prob = 1.0
    for i in range(k):
        prob *= (safe_cells - i) / (25 - i)
    
    multiplier = round((1 / prob) * 0.95, 2) if prob > 0 else 100.0
    multiplier = min(multiplier, 100.0)
    win = int(bet * multiplier)
    
    cur.execute("UPDATE active_mines SET opened=?, multiplier=? WHERE user_id=?", (opened_str, multiplier, uid))
    db.commit()
    
    if len(opened) == safe_cells:
        cur.execute("UPDATE users SET stars = stars + ?, games_played = games_played + 1 WHERE id=?", (win, uid))
        cur.execute("DELETE FROM active_mines WHERE user_id=?", (uid,))
        db.commit()
        await cb.message.edit_text(f"✅ Ты открыл все безопасные клетки!\nВыиграл {fmt(win)}⭐ (Множитель {multiplier}x)", reply_markup=back_kb())
        return

    await cb.message.edit_text(
        f"💣 Мины ({mines_count} шт)\n\nСтавка: {bet}⭐\nМножитель: {multiplier}x\nТекущий выигрыш: {fmt(win)}⭐", 
        reply_markup=mines_grid(mines_count, opened)
    )

@dp.callback_query(lambda c: c.data == "cashout")
async def cashout(cb: types.CallbackQuery):
    uid = cb.from_user.id
    cur.execute("SELECT bet, multiplier FROM active_mines WHERE user_id=?", (uid,))
    session = cur.fetchone()
    
    if not session:
        return await cb.answer("Игра не найдена!", show_alert=True)
        
    bet, mult = session
    win = int(bet * mult)
    
    cur.execute("UPDATE users SET stars = stars + ?, games_played = games_played + 1 WHERE id=?", (win, uid))
    cur.execute("DELETE FROM active_mines WHERE user_id=?", (uid,))
    db.commit()
    
    await cb.message.edit_text(f"✅ Ты забрал выигрыш: {fmt(win)}⭐ (Множитель {mult}x)", reply_markup=back_kb())

@dp.callback_query(lambda c: c.data == "noop")
async def noop(cb: types.CallbackQuery):
    await cb.answer()

async def main():
    print("BOT STARTED!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
