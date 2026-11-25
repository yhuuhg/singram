import asyncio, sqlite3, time
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = "9125288007:AAEq_c9LNw3M-vXkK9x9c2t7DwS4v76MWAM"

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

db = sqlite3.connect("game.db", check_same_thread=False)
cur = db.cursor()
cur.execute("""CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY, 
    name TEXT, 
    stars INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1, 
    last_click REAL DEFAULT 0, 
    join_date REAL DEFAULT 0
)""")
db.commit()

LEVELS = {1: 1, 2: 5, 3: 25, 4: 100, 5: 1000}

def get_user(uid):
    cur.execute("SELECT name, stars, level, last_click FROM users WHERE id=?", (uid,))
    return cur.fetchone()

def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⛏ Фарм", callback_data="farm")],
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")]
    ])

@dp.message(CommandStart())
async def start(msg: types.Message):
    cur.execute("INSERT OR IGNORE INTO users(id, name, join_date) VALUES(?,?,?)", 
                (msg.from_user.id, msg.from_user.first_name, time.time()))
    db.commit()
    await msg.answer("Main menu:", reply_markup=main_kb())

@dp.callback_query(lambda c: c.data == "farm")
async def farm(cb: types.CallbackQuery):
    uid = cb.from_user.id
    now = time.time()
    u = get_user(uid)
    
    if now - u[3] < 1.0:
        return await cb.answer("Wait 1 sec!", show_alert=True)
    
    income = LEVELS[u[2]]
    cur.execute("UPDATE users SET stars = stars + ?, last_click = ? WHERE id=?", (income, now, uid))
    db.commit()
    
    u = get_user(uid)
    await cb.message.edit_text(f"+{income}⭐\nTotal: {u[1]}⭐\nLevel: {u[2]}", reply_markup=main_kb())
    await cb.answer(f"+{income}⭐")

@dp.callback_query(lambda c: c.data == "profile")
async def profile(cb: types.CallbackQuery):
    u = get_user(cb.from_user.id)
    await cb.message.edit_text(f"👤 Name: {u[0]}\n⭐ Stars: {u[1]}\nLevel: {u[2]}", reply_markup=main_kb())
    await cb.answer()

async def main():
    print("BOT STARTED!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
