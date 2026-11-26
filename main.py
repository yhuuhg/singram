
import asyncio
import os
import time
import random
import sqlite3

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton
)

# ================= CONFIG =================

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USERNAME = "clawdyc"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not configured!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

db = sqlite3.connect("game.db", check_same_thread=False)
db.row_factory = sqlite3.Row

# ================= DATABASE =================

db.execute("""
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY,
    name TEXT,
    stars INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    last_click REAL DEFAULT 0,
    join_date REAL DEFAULT 0,
    games_played INTEGER DEFAULT 0
)
""")

db.execute("""
CREATE TABLE IF NOT EXISTS active_mines(
    user_id INTEGER PRIMARY KEY,
    bet INTEGER,
    mines_count INTEGER,
    opened TEXT,
    mine_positions TEXT,
    multiplier REAL DEFAULT 1.0
)
""")

db.execute("""
CREATE TABLE IF NOT EXISTS transactions(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER,
    target_id INTEGER,
    amount INTEGER,
    created_at REAL
)
""")

# Получаем список существующих колонок
cursor = db.execute("PRAGMA table_info(users)")
columns = {row[1] for row in cursor.fetchall()}   # row[1] — это название колонки

migrations = {
    "username": "TEXT",
    "gram": "INTEGER DEFAULT 0",
    "coins": "INTEGER DEFAULT 0",
    "gift_count": "INTEGER DEFAULT 0"
}

for column, definition in migrations.items():
    if column not in columns:
        db.execute(f"ALTER TABLE users ADD COLUMN {column} {definition}")

db.commit()

# ================= SETTINGS =================

LEVEL_REWARDS = {
    1: 1,
    2: 5,
    3: 25,
    4: 100,
    5: 500,
    6: 2000
}

LEVEL_COSTS = {
    2: 10000,
    3: 50000,
    4: 150000,
    5: 400000,
    6: 1000000
}

MINES_BET = 100
db_lock = asyncio.Lock()


# ================= HELPERS =================

def fmt(number):
    return f"{number:,}".replace(",", " ")


def get_user(uid):
    return db.execute(
        "SELECT * FROM users WHERE id=?",
        (uid,)
    ).fetchone()


def register_user(user):
    db.execute("""
        INSERT OR IGNORE INTO users(id, name, join_date)
        VALUES (?, ?, ?)
    """, (user.id, user.first_name, time.time()))

    db.execute("""
        UPDATE users
        SET name=?, username=?
        WHERE id=?
    """, (user.first_name, user.username, user.id))

    db.commit()


def is_admin(user):
    return (user.username or "").lower() == ADMIN_USERNAME.lower()


def get_rank(uid):
    user = get_user(uid)
    if not user:
        return 0

    return db.execute(
        "SELECT COUNT(*) FROM users WHERE stars > ?",
        (user["stars"],)
    ).fetchone()[0] + 1


# ================= KEYBOARDS =================

def main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🎮 Games"),
                KeyboardButton(text="👤 Profile")
            ],
            [
                KeyboardButton(text="⛏ Mining"),
                KeyboardButton(text="🏆 Leaderboard")
            ]
        ],
        resize_keyboard=True
    )


def games_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💣 Mines")],
            [KeyboardButton(text="🔙 Main Menu")]
        ],
        resize_keyboard=True
    )


def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔙 Main Menu",
            callback_data="main"
        )]
    ])


def mining_kb(level):
    buttons = []

    if level < 6:
        cost = LEVEL_COSTS[level + 1]
        buttons.append([
            InlineKeyboardButton(
                text=f"⬆️ Upgrade — {fmt(cost)} ⭐",
                callback_data="upgrade_mining"
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def leaderboard_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐ Stars", callback_data="top_stars"),
            InlineKeyboardButton(text="💎 Gram", callback_data="top_gram")
        ],
        [
            InlineKeyboardButton(text="🪙 Coin", callback_data="top_coins"),
            InlineKeyboardButton(text="⛏ Mining", callback_data="top_level")
        ],
        [
            InlineKeyboardButton(text="🎁 Gifts", callback_data="top_gifts")
        ]
    ])


# ================= START =================

@dp.message(CommandStart())
async def start(msg: types.Message):
    register_user(msg.from_user)

    await msg.answer(
        "Welcome to Telegram Simulator!\n\nChoose an option:",
        reply_markup=main_kb()
    )


# ================= MAIN MENU =================

@dp.message(F.text == "🔙 Main Menu")
async def main_menu(msg: types.Message):
    register_user(msg.from_user)
    await msg.answer(
        "🏠 Main Menu\n\nChoose an option:",
        reply_markup=main_kb()
    )


@dp.message(F.text == "🎮 Games")
async def games(msg: types.Message):
    register_user(msg.from_user)
    await msg.answer("🎮 Games\n\nChoose a game:", reply_markup=games_kb())


@dp.message(F.text == "💣 Mines")
async def mines_menu(msg: types.Message):
    register_user(msg.from_user)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="3 Mines", callback_data="mines_3"),
            InlineKeyboardButton(text="5 Mines", callback_data="mines_5")
        ],
        [
            InlineKeyboardButton(text="10 Mines", callback_data="mines_10")
        ]
    ])

    await msg.answer(
        "💣 Mines\n\nChoose the number of mines:",
        reply_markup=kb
    )


# ================= PROFILE =================

@dp.message(F.text == "👤 Profile")
async def profile(msg: types.Message):
    register_user(msg.from_user)
    u = get_user(msg.from_user.id)

    await msg.answer(
        f"👤 Profile\n\n"
        f"Name: {u['name']}\n"
        f"Username: @{u['username'] or 'not set'}\n\n"
        f"⭐ Stars: {fmt(u['stars'])}\n"
        f"💎 Gram: {fmt(u['gram'])}\n"
        f"🪙 Coin: {fmt(u['coins'])}\n"
        f"⛏ Mining Level: {u['level']}/6\n"
        f"🎮 Games Played: {u['games_played']}\n"
        f"🏆 Stars Rank: #{get_rank(msg.from_user.id)}",
        reply_markup=main_kb()
    )


# ================= MINING =================

@dp.message(F.text == "⛏ Mining")
async def mining(msg: types.Message):
    register_user(msg.from_user)

    uid = msg.from_user.id
    now = time.time()
    u = get_user(uid)

    if now - u["last_click"] < 1:
        return await msg.answer("⏳ Please wait 1 second!")

    income = LEVEL_REWARDS.get(u["level"], 1)

    db.execute("""
        UPDATE users
        SET stars=stars+?, last_click=?
        WHERE id=?
    """, (income, now, uid))
    db.commit()

    u = get_user(uid)

    text = (
        f"⛏️ Mining Farm\n\n"
        f"+{fmt(income)} ⭐\n"
        f"Balance: {fmt(u['stars'])} ⭐\n\n"
        f"Level: {u['level']}/6\n"
        f"Income per click: {fmt(income)} ⭐\n"
    )

    if u["level"] < 6:
        text += f"\nNext upgrade: {fmt(LEVEL_COSTS[u['level'] + 1])} ⭐"
    else:
        text += "\n🏆 Maximum mining level reached!"

    await msg.answer(text, reply_markup=mining_kb(u["level"]))


@dp.callback_query(F.data == "upgrade_mining")
async def upgrade_mining(cb: types.CallbackQuery):
    register_user(cb.from_user)

    async with db_lock:
        db.execute("BEGIN IMMEDIATE")
        u = get_user(cb.from_user.id)
        level = u["level"]

        if level >= 6:
            db.rollback()
            return await cb.answer("Maximum level reached!", show_alert=True)

        cost = LEVEL_COSTS[level + 1]

        if u["stars"] < cost:
            db.rollback()
            return await cb.answer(
                f"Not enough Stars! Need {fmt(cost)} ⭐",
                show_alert=True
            )

        db.execute("""
            UPDATE users
            SET stars=stars-?, level=level+1
            WHERE id=?
        """, (cost, cb.from_user.id))
        db.commit()

    u = get_user(cb.from_user.id)

    await cb.message.edit_text(
        f"✅ Mining upgraded!\n\n"
        f"New level: {u['level']}/6\n"
        f"Income per click: {fmt(LEVEL_REWARDS[u['level']])} ⭐\n"
        f"Balance: {fmt(u['stars'])} ⭐",
        reply_markup=mining_kb(u["level"])
    )
    await cb.answer("Upgrade successful!")


# ================= ADMIN GIVE =================

@dp.message(Command("give"))
async def give_stars(msg: types.Message):
    register_user(msg.from_user)

    if not is_admin(msg.from_user):
        return await msg.answer("⛔ You are not authorized.")

    args = (msg.text or "").split()

    if len(args) != 3:
        return await msg.answer(
            "Usage: /give @username amount\n"
            "Example: /give @player123 50000"
        )

    username = args[1].lstrip("@").lower()

    try:
        amount = int(args[2])
    except ValueError:
        return await msg.answer("❌ Amount must be a whole number.")

    if not username or amount <= 0 or amount > 1_000_000_000_000:
        return await msg.answer("❌ Invalid username or amount.")

    target = db.execute(
        "SELECT id FROM users WHERE LOWER(username)=?",
        (username,)
    ).fetchone()

    if not target:
        return await msg.answer(
            "❌ Player not found. They must start the bot first."
        )

    async with db_lock:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "UPDATE users SET stars=stars+? WHERE id=?",
            (amount, target["id"])
        )
        db.execute("""
            INSERT INTO transactions(admin_id, target_id, amount, created_at)
            VALUES (?, ?, ?, ?)
        """, (msg.from_user.id, target["id"], amount, time.time()))
        db.commit()

    await msg.answer(
        f"✅ Sent {fmt(amount)} ⭐ to @{username}."
    )

    try:
        await bot.send_message(
            target["id"],
            f"🎁 You received {fmt(amount)} Stars from the administration!"
        )
    except Exception:
        await msg.answer("⚠️ Balance updated, but notification failed.")


# ================= LEADERBOARDS =================

@dp.message(F.text == "🏆 Leaderboard")
async def top_menu(msg: types.Message):
    register_user(msg.from_user)
    await msg.answer(
        "🏆 Leaderboards\n\nChoose a ranking:",
        reply_markup=leaderboard_kb()
    )


async def show_top(cb, column, title, suffix=""):
    allowed = {"stars", "gram", "coins", "level", "gift_count"}

    if column not in allowed:
        return await cb.answer("Invalid ranking.")

    rows = db.execute(
        f"""
        SELECT id, name, username, {column} AS score
        FROM users
        ORDER BY {column} DESC, id ASC
        LIMIT 10
        """
    ).fetchall()

    text = f"{title}\n\n"

    if not rows or all(row["score"] == 0 for row in rows):
        text += "No rankings available yet."
    else:
        for i, row in enumerate(rows, 1):
            name = f"@{row['username']}" if row["username"] else row["name"]
            text += f"{i}. {name} — {fmt(row['score'])}{suffix}\n"

    user = get_user(cb.from_user.id)

    if user:
        rank = db.execute(
            f"SELECT COUNT(*) FROM users WHERE {column} > ?",
            (user[column],)
        ).fetchone()[0] + 1
        text += f"\nYour position: #{rank}"

    await cb.message.edit_text(text, reply_markup=leaderboard_kb())
    await cb.answer()


@dp.callback_query(F.data == "top_stars")
async def top_stars(cb):
    await show_top(cb, "stars", "⭐ TOP 10 STARS", " ⭐")


@dp.callback_query(F.data == "top_gram")
async def top_gram(cb):
    await show_top(cb, "gram", "💎 TOP 10 GRAM", " 💎")


@dp.callback_query(F.data == "top_coins")
async def top_coins(cb):
    await show_top(cb, "coins", "🪙 TOP 10 COINS", " 🪙")


@dp.callback_query(F.data == "top_level")
async def top_level(cb):
    await show_top(cb, "level", "⛏ TOP 10 MINING LEVELS")


@dp.callback_query(F.data == "top_gifts")
async def top_gifts(cb):
    await show_top(cb, "gift_count", "🎁 TOP 10 GIFT COLLECTORS", " gifts")


# ================= MINES =================

def mines_grid(opened_list):
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

    kb.append([
        InlineKeyboardButton(text="💰 Cash Out", callback_data="cashout")
    ])
    kb.append([
        InlineKeyboardButton(text="🔙 Main Menu", callback_data="main")
    ])

    return InlineKeyboardMarkup(inline_keyboard=kb)


@dp.callback_query(F.data.in_(["mines_3", "mines_5", "mines_10"]))
async def start_mines(cb: types.CallbackQuery):
    register_user(cb.from_user)

    uid = cb.from_user.id
    mines_count = int(cb.data.split("_")[1])

    async with db_lock:
        db.execute("BEGIN IMMEDIATE")
        u = get_user(uid)

        if u["stars"] < MINES_BET:
            db.rollback()
            return await cb.answer("You need 100 Stars!", show_alert=True)

        existing = db.execute(
            "SELECT user_id FROM active_mines WHERE user_id=?",
            (uid,)
        ).fetchone()

        if existing:
            db.rollback()
            return await cb.answer("You already have an active game!", show_alert=True)

        positions = random.sample(range(25), mines_count)

        db.execute(
            "UPDATE users SET stars=stars-? WHERE id=?",
            (MINES_BET, uid)
        )

        db.execute("""
            INSERT INTO active_mines
            (user_id, bet, mines_count, opened, mine_positions, multiplier)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            uid, MINES_BET, mines_count, "",
            ",".join(map(str, positions)), 1.0
        ))
        db.commit()

    await cb.message.edit_text(
        f"💣 Mines ({mines_count})\n\n"
        f"Bet: {MINES_BET} ⭐\n"
        f"Multiplier: 1.0x\n"
        f"Potential win: {MINES_BET} ⭐",
        reply_markup=mines_grid([])
    )
    await cb.answer()


@dp.callback_query(F.data.startswith("open_"))
async def open_cell(cb: types.CallbackQuery):
    uid = cb.from_user.id

    try:
        cell = int(cb.data.split("_")[1])
    except (ValueError, IndexError):
        return await cb.answer("Invalid cell!")

    if not 0 <= cell < 25:
        return await cb.answer("Invalid cell!")

    async with db_lock:
        db.execute("BEGIN IMMEDIATE")

        session = db.execute("""
            SELECT bet, mines_count, opened, mine_positions, multiplier
            FROM active_mines WHERE user_id=?
        """, (uid,)).fetchone()

        if not session:
            db.rollback()
            return await cb.answer("Game not found!", show_alert=True)

        bet, mines_count, opened_str, mine_pos_str, mult = session
        opened = [int(x) for x in opened_str.split(",") if x]
        mine_pos = [int(x) for x in mine_pos_str.split(",") if x]

        if cell in opened:
            db.rollback()
            return await cb.answer("Already opened!")

        if cell in mine_pos:
            db.execute("DELETE FROM active_mines WHERE user_id=?", (uid,))
            db.execute(
                "UPDATE users SET games_played=games_played+1 WHERE id=?",
                (uid,)
            )
            db.commit()

            return await cb.message.edit_text(
                f"💥 BOOM! You hit a mine!\n\nYou lost {bet} ⭐.",
                reply_markup=back_kb()
            )

        opened.append(cell)
        safe_cells = 25 - mines_count
        probability = 1.0

        for i in range(len(opened)):
            probability *= (safe_cells - i) / (25 - i)

        multiplier = min(round((1 / probability) * 0.95, 2), 100.0)
        win = int(bet * multiplier)

        if len(opened) == safe_cells:
            db.execute("""
                UPDATE users
                SET stars=stars+?, games_played=games_played+1
                WHERE id=?
            """, (win, uid))
            db.execute("DELETE FROM active_mines WHERE user_id=?", (uid,))
            db.commit()

            return await cb.message.edit_text(
                f"✅ All safe cells opened!\n\n"
                f"You won {fmt(win)} ⭐\n"
                f"Multiplier: {multiplier}x",
                reply_markup=back_kb()
            )

        db.execute("""
            UPDATE active_mines
            SET opened=?, multiplier=?
            WHERE user_id=?
        """, (",".join(map(str, opened)), multiplier, uid))
        db.commit()

    await cb.message.edit_text(
        f"💣 Mines ({mines_count})\n\n"
        f"Bet: {bet} ⭐\n"
        f"Multiplier: {multiplier}x\n"
        f"Current win: {fmt(win)} ⭐",
        reply_markup=mines_grid(opened)
    )
    await cb.answer()


@dp.callback_query(F.data == "cashout")
async def cashout(cb: types.CallbackQuery):
    uid = cb.from_user.id

    async with db_lock:
        db.execute("BEGIN IMMEDIATE")

        session = db.execute(
            "SELECT bet, multiplier FROM active_mines WHERE user_id=?",
            (uid,)
        ).fetchone()

        if not session:
            db.rollback()
            return await cb.answer("Game not found!", show_alert=True)

        bet, mult = session
        win = int(bet * mult)

        db.execute("""
            UPDATE users
            SET stars=stars+?, games_played=games_played+1
            WHERE id=?
        """, (win, uid))

        db.execute("DELETE FROM active_mines WHERE user_id=?", (uid,))
        db.commit()

    await cb.message.edit_text(
        f"✅ You collected your winnings!\n\n"
        f"Won: {fmt(win)} ⭐\n"
        f"Multiplier: {mult}x",
        reply_markup=back_kb()
    )
    await cb.answer()


# ================= NAVIGATION =================

@dp.callback_query(F.data == "main")
async def main_from_mines(cb: types.CallbackQuery):
    await cb.message.answer(
        "🏠 Main Menu\n\nChoose an option:",
        reply_markup=main_kb()
    )
    await cb.answer()


@dp.callback_query(F.data == "noop")
async def noop(cb: types.CallbackQuery):
    await cb.answer("Already opened!")


# ================= START BOT =================

async def main():
    print("Telegram Simulator is starting...")
    await bot.delete_webhook(drop_pending_updates=True)
    print("Bot is running!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())


