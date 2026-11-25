
import asyncio
import sqlite3
import time
import random

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton
)

import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "PASTE_YOUR_NEW_TOKEN_HERE")

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
    join_date REAL DEFAULT 0,
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
    cur.execute(
        "SELECT name, stars, level, last_click, games_played FROM users WHERE id=?",
        (uid,)
    )
    return cur.fetchone()


def get_rank(uid):
    cur.execute(
        "SELECT COUNT(*) FROM users WHERE stars > (SELECT stars FROM users WHERE id=?)",
        (uid,)
    )
    return cur.fetchone()[0] + 1


def fmt(num):
    return f"{num:,}".replace(",", " ")


# MAIN MENU — BUTTONS NEXT TO MESSAGE INPUT

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


# GAMES MENU — NORMAL TELEGRAM KEYBOARD

def games_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💣 Mines")],
            [KeyboardButton(text="🔙 Main Menu")]
        ],
        resize_keyboard=True
    )


# INLINE BUTTONS — ONLY FOR MINES

def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Main Menu", callback_data="main")]
    ])


def mines_grid(mines_count, opened_list):
    kb = []
    row = []

    for i in range(25):
        if i in opened_list:
            row.append(
                InlineKeyboardButton(text="✅", callback_data="noop")
            )
        else:
            row.append(
                InlineKeyboardButton(text="🔲", callback_data=f"open_{i}")
            )

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


# START

@dp.message(CommandStart())
async def start(msg: types.Message):
    cur.execute(
        "INSERT OR IGNORE INTO users(id, name, join_date) VALUES(?,?,?)",
        (msg.from_user.id, msg.from_user.first_name, time.time())
    )
    db.commit()

    await msg.answer(
        "Welcome to Telegram Simulator!\n\nChoose an option from the menu below:",
        reply_markup=main_kb()
    )


# MAIN MENU

@dp.message(F.text == "🔙 Main Menu")
async def main_menu(msg: types.Message):
    await msg.answer(
        "🏠 Main Menu\n\nChoose an option:",
        reply_markup=main_kb()
    )


# GAMES

@dp.message(F.text == "🎮 Games")
async def games(msg: types.Message):
    await msg.answer(
        "🎮 Games\n\nChoose a game:",
        reply_markup=games_kb()
    )


# MINES MENU

@dp.message(F.text == "💣 Mines")
async def mines_menu(msg: types.Message):
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


# PROFILE

@dp.message(F.text == "👤 Profile")
async def profile(msg: types.Message):
    uid = msg.from_user.id
    u = get_user(uid)
    rank = get_rank(uid)

    await msg.answer(
        f"👤 Profile\n\n"
        f"Name: {u[0]}\n"
        f"⭐ Stars: {fmt(u[1])}\n"
        f"Mining Level: {u[2]}\n"
        f"Leaderboard Rank: #{rank}\n"
        f"Games Played: {u[4]}",
        reply_markup=main_kb()
    )


# LEADERBOARD

@dp.message(F.text == "🏆 Leaderboard")
async def top(msg: types.Message):
    cur.execute(
        "SELECT name, stars FROM users ORDER BY stars DESC LIMIT 10"
    )
    rows = cur.fetchall()

    text = "🏆 Top 10 Players:\n\n"

    for i, row in enumerate(rows, 1):
        text += f"{i}. {row[0]} — {fmt(row[1])}⭐\n"

    await msg.answer(text, reply_markup=main_kb())


# MINING — EACH CLICK GIVES STARS

@dp.message(F.text == "⛏ Mining")
async def mining(msg: types.Message):
    uid = msg.from_user.id
    now = time.time()

    u = get_user(uid)

    if now - u[3] < 1.0:
        return await msg.answer("⏳ Please wait 1 second!")

    income = LEVELS.get(u[2], 1)

    cur.execute(
        "UPDATE users SET stars = stars + ?, last_click = ? WHERE id=?",
        (income, now, uid)
    )
    db.commit()

    u = get_user(uid)

    await msg.answer(
        f"⛏ Mining successful!\n\n"
        f"+{income} ⭐\n"
        f"Total Stars: {fmt(u[1])}\n"
        f"Mining Level: {u[2]}\n\n"
        f"Click Mining again to earn more Stars!",
        reply_markup=main_kb()
    )


# START MINES GAME

@dp.callback_query(F.data.in_(["mines_3", "mines_5", "mines_10"]))
async def start_mines(cb: types.CallbackQuery):
    uid = cb.from_user.id
    u = get_user(uid)

    mines_count = int(cb.data.split("_")[1])

    if u[1] < 100:
        return await cb.answer(
            "You need at least 100 Stars!",
            show_alert=True
        )

    bet = 100

    cur.execute(
        "UPDATE users SET stars = stars - ? WHERE id=?",
        (bet, uid)
    )

    positions = random.sample(range(25), mines_count)
    positions_str = ",".join(map(str, positions))

    cur.execute(
        """INSERT OR REPLACE INTO active_mines
        (user_id, bet, mines_count, opened, mine_positions, multiplier)
        VALUES(?,?,?,?,?,?)""",
        (uid, bet, mines_count, "", positions_str, 1.0)
    )

    db.commit()

    await cb.message.edit_text(
        f"💣 Mines ({mines_count})\n\n"
        f"Bet: 100⭐\n"
        f"Multiplier: 1.0x\n"
        f"Potential Win: 100⭐",
        reply_markup=mines_grid(mines_count, [])
    )

    await cb.answer()


# OPEN CELL

@dp.callback_query(F.data.startswith("open_"))
async def open_cell(cb: types.CallbackQuery):
    uid = cb.from_user.id
    cell = int(cb.data.split("_")[1])

    cur.execute(
        """SELECT bet, mines_count, opened, mine_positions, multiplier
        FROM active_mines WHERE user_id=?""",
        (uid,)
    )

    session = cur.fetchone()

    if not session:
        return await cb.answer("Game not found!", show_alert=True)

    bet, mines_count, opened_str, mine_pos_str, mult = session

    opened = [int(x) for x in opened_str.split(",")] if opened_str else []
    mine_pos = [int(x) for x in mine_pos_str.split(",")]

    if cell in opened:
        return await cb.answer("Already opened!")

    if cell in mine_pos:
        cur.execute(
            "DELETE FROM active_mines WHERE user_id=?",
            (uid,)
        )

        cur.execute(
            "UPDATE users SET games_played = games_played + 1 WHERE id=?",
            (uid,)
        )

        db.commit()

        await cb.message.edit_text(
            f"💥 BOOM! You hit a mine!\n\n"
            f"You lost {bet}⭐.",
            reply_markup=back_kb()
        )

        return await cb.answer()

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

    cur.execute(
        "UPDATE active_mines SET opened=?, multiplier=? WHERE user_id=?",
        (opened_str, multiplier, uid)
    )

    db.commit()

    if len(opened) == safe_cells:
        cur.execute(
            """UPDATE users
            SET stars = stars + ?, games_played = games_played + 1
            WHERE id=?""",
            (win, uid)
        )

        cur.execute(
            "DELETE FROM active_mines WHERE user_id=?",
            (uid,)
        )

        db.commit()

        await cb.message.edit_text(
            f"✅ All safe cells opened!\n\n"
            f"You won {fmt(win)}⭐\n"
            f"Multiplier: {multiplier}x",
            reply_markup=back_kb()
        )

        return await cb.answer()

    await cb.message.edit_text(
        f"💣 Mines ({mines_count})\n\n"
        f"Bet: {bet}⭐\n"
        f"Multiplier: {multiplier}x\n"
        f"Current Win: {fmt(win)}⭐",
        reply_markup=mines_grid(mines_count, opened)
    )

    await cb.answer()


# CASH OUT

@dp.callback_query(F.data == "cashout")
async def cashout(cb: types.CallbackQuery):
    uid = cb.from_user.id

    cur.execute(
        "SELECT bet, multiplier FROM active_mines WHERE user_id=?",
        (uid,)
    )

    session = cur.fetchone()

    if not session:
        return await cb.answer("Game not found!", show_alert=True)

    bet, mult = session
    win = int(bet * mult)

    cur.execute(
        """UPDATE users
        SET stars = stars + ?, games_played = games_played + 1
        WHERE id=?""",
        (win, uid)
    )

    cur.execute(
        "DELETE FROM active_mines WHERE user_id=?",
        (uid,)
    )

    db.commit()

    await cb.message.edit_text(
        f"✅ You collected your winnings!\n\n"
        f"Won: {fmt(win)}⭐\n"
        f"Multiplier: {mult}x",
        reply_markup=back_kb()
    )

    await cb.answer()


# BACK TO MAIN MENU FROM MINES

@dp.callback_query(F.data == "main")
async def main_from_mines(cb: types.CallbackQuery):
    await cb.message.answer(
        "🏠 Main Menu\n\nChoose an option:",
        reply_markup=main_kb()
    )
    await cb.answer()


# ALREADY OPENED CELL

@dp.callback_query(F.data == "noop")
async def noop(cb: types.CallbackQuery):
    await cb.answer("Already opened!")


async def main():
    print("BOT STARTED!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

