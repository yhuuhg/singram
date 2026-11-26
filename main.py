import asyncio
import sqlite3
import time
import random
from datetime import datetime, timedelta
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

# ====================== TABLES ======================
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
    waiting_mode = State()

class RouletteStates(StatesGroup):
    waiting_bet = State()
    waiting_color = State()

# ====================== TRANSLATIONS ======================
TEXTS = {
    "ru": {
        "main": "Главное меню\n\nВыбери раздел:",
        "btn_games": "🎮 Игры",
        "btn_profile": "👤 Профиль",
        "btn_mining": "⛏ Майнинг",
        "btn_top": "🏆 Рейтинг",
        "btn_exchange": "💱 Обменник",
        "games": "🎮 Игры",
        "profile": "👤 Профиль",
        "mining": "⛏ Майнинг",
        "top": "🏆 Рейтинг",
        "mines": "💣 Мины",
        "rocket": "🚀 Ракета",
        "dice": "🎲 Кости",
        "roulette": "🎰 Рулетка",
        "back": "🔙 Главное меню",
        "farm": "⛏ Фарм",
        "choose_lang": "Выбери язык / Choose language / 选择语言:",
        "lang_changed": "✅ Язык изменён на Русский",
        "admin": "Администратор",
        "player": "Игрок",
        "premium": "⭐ Premium",
        "not_enough": "Недостаточно звёзд!",
        "wait": "Подожди 1 секунду!",
        "boom": "💥 БУМ! Ты попал на мину.\nСтавка {bet}⭐ сгорела.",
        "win_all": "✅ Ты открыл все безопасные клетки!\nВыиграл {win}⭐ (Множитель {mult}x)",
        "cashed": "✅ Ты забрал выигрыш: {win}⭐ (Множитель {mult}x)",
        "rocket_fly": "🚀 РАКЕТА ЛЕТИТ...\n\nТекущий множитель: {mult}x\n\nСтавка: {bet} ⭐\nПотенциальный выигрыш: {win} ⭐",
        "rocket_crash": "💥 РАКЕТА ВЗОРВАЛАСЬ!\n\nТочка краша: {crash}x\nТвоя ставка: {bet} ⭐\n\nТы потерял {bet} ⭐",
        "rocket_win": "✅ ТЫ ЗАБРАЛ!\n\nМножитель: {mult}x\nСтавка: {bet} ⭐\nВыигрыш: {win} ⭐\nЧистая прибыль: +{profit} ⭐",
        "already_rocket": "У тебя уже есть активная ракета!",
        "choose_bet": "🚀 Ракета\n\nТвой баланс: {bal} ⭐\n\nВыбери ставку:",
        "profile_text": "👤 Профиль\n\nИмя: {name}\n⭐ Звезды: {stars}\nУровень майнинга: {level}\nМесто в рейтинге: #{rank}\nСыграно игр: {games}\nРанг: {rank_name}\nPremium: {premium}\nНомер: {number}",
        "top_title": "🏆 Топ 10 игроков:\n\n",
        "mining_text": "Майнинг\n\n⭐ Всего: {stars}\nУровень: {level}\n\nЖми кнопку ниже:",
        "games_text": "🎮 Игры\n\nВыбери игру:",
        "mines_text": "💣 Мины\n\nВведи сумму ставки (от 100 до 1 000 000 ⭐):",
        "mines_count": "💣 Теперь введи количество мин (от 1 до 24):",
        "give_ok": "✅ Выдано {amount}⭐ пользователю @{user}",
        "give_fail": "❌ Пользователь не найден",
        "news_ok": "✅ Рассылка отправлена",
        "no_access": "❌ Нет доступа",
        "invalid_bet": "❌ Неверная сумма. Введи число от 100 до 1 000 000",
        "invalid_mines": "❌ Неверное количество. Введи число от 1 до 24",
        "exchange_text": "💱 Обменник\n\nКурс: 1 TON = 200 ⭐\n\nВведи количество TON которое хочешь обменять:",
        "shop": "🛒 Магазин",
        "buy_premium": "⭐ Купить Premium (10 000 000 ⭐ / 30 дней)",
        "buy_888": "📱 Номер +888 (10 000 000 ⭐)",
        "buy_7": "📱 Номер +7 (1 000 000 ⭐)",
        "buy_380": "📱 Номер +380 (1 000 000 ⭐)",
    },
    "en": {
        "main": "Main menu\n\nChoose a section:",
        "btn_games": "🎮 Games",
        "btn_profile": "👤 Profile",
        "btn_mining": "⛏ Mining",
        "btn_top": "🏆 Leaderboard",
        "btn_exchange": "💱 Exchange",
        "games": "🎮 Games",
        "profile": "👤 Profile",
        "mining": "⛏ Mining",
        "top": "🏆 Leaderboard",
        "mines": "💣 Mines",
        "rocket": "🚀 Rocket",
        "dice": "🎲 Dice",
        "roulette": "🎰 Roulette",
        "back": "🔙 Main menu",
        "farm": "⛏ Farm",
        "choose_lang": "Выбери язык / Choose language / 选择语言:",
        "lang_changed": "✅ Language changed to English",
        "admin": "Administrator",
        "player": "Player",
        "premium": "⭐ Premium",
        "not_enough": "Not enough stars!",
        "wait": "Wait 1 second!",
        "boom": "💥 BOOM! You hit a mine.\nBet {bet}⭐ is lost.",
        "win_all": "✅ You opened all safe cells!\nWon {win}⭐ (Multiplier {mult}x)",
        "cashed": "✅ You cashed out: {win}⭐ (Multiplier {mult}x)",
        "rocket_fly": "🚀 ROCKET IS FLYING...\n\nCurrent multiplier: {mult}x\n\nBet: {bet} ⭐\nPotential win: {win} ⭐",
        "rocket_crash": "💥 ROCKET EXPLODED!\n\nCrash point: {crash}x\nYour bet: {bet} ⭐\n\nYou lost {bet} ⭐",
        "rocket_win": "✅ CASHED OUT!\n\nMultiplier: {mult}x\nBet: {bet} ⭐\nWin: {win} ⭐\nProfit: +{profit} ⭐",
        "already_rocket": "You already have an active rocket!",
        "choose_bet": "🚀 Rocket\n\nYour balance: {bal} ⭐\n\nChoose bet:",
        "profile_text": "👤 Profile\n\nName: {name}\n⭐ Stars: {stars}\nMining level: {level}\nRank position: #{rank}\nGames played: {games}\nRank: {rank_name}\nPremium: {premium}\nNumber: {number}",
        "top_title": "🏆 Top 10 players:\n\n",
        "mining_text": "Mining\n\n⭐ Total: {stars}\nLevel: {level}\n\nPress the button below:",
        "games_text": "🎮 Games\n\nChoose a game:",
        "mines_text": "💣 Mines\n\nEnter bet amount (from 100 to 1 000 000 ⭐):",
        "mines_count": "💣 Now enter number of mines (from 1 to 24):",
        "give_ok": "✅ Gave {amount}⭐ to @{user}",
        "give_fail": "❌ User not found",
        "news_ok": "✅ Broadcast sent",
        "no_access": "❌ No access",
        "invalid_bet": "❌ Invalid amount. Enter a number from 100 to 1 000 000",
        "invalid_mines": "❌ Invalid number. Enter from 1 to 24",
        "exchange_text": "💱 Exchange\n\nRate: 1 TON = 200 ⭐\n\nEnter amount of TON to exchange:",
        "shop": "🛒 Shop",
        "buy_premium": "⭐ Buy Premium (10 000 000 ⭐ / 30 days)",
        "buy_888": "📱 Number +888 (10 000 000 ⭐)",
        "buy_7": "📱 Number +7 (1 000 000 ⭐)",
        "buy_380": "📱 Number +380 (1 000 000 ⭐)",
    },
    "zh": {
        "main": "主菜单\n\n请选择:",
        "btn_games": "🎮 游戏",
        "btn_profile": "👤 个人资料",
        "btn_mining": "⛏ 挖矿",
        "btn_top": "🏆 排行榜",
        "btn_exchange": "💱 兑换",
        "games": "🎮 游戏",
        "profile": "👤 个人资料",
        "mining": "⛏ 挖矿",
        "top": "🏆 排行榜",
        "mines": "💣 地雷",
        "rocket": "🚀 火箭",
        "dice": "🎲 骰子",
        "roulette": "🎰 轮盘",
        "back": "🔙 主菜单",
        "farm": "⛏ 收获",
        "choose_lang": "Выбери язык / Choose language / 选择语言:",
        "lang_changed": "✅ 语言已更改为中文",
        "admin": "管理员",
        "player": "玩家",
        "premium": "⭐ Premium",
        "not_enough": "星星不足!",
        "wait": "请等待1秒!",
        "boom": "💥 爆炸! 你踩到了地雷。\n下注 {bet}⭐ 已丢失。",
        "win_all": "✅ 你打开了所有安全格子!\n赢得 {win}⭐ (倍数 {mult}x)",
        "cashed": "✅ 你已兑现: {win}⭐ (倍数 {mult}x)",
        "rocket_fly": "🚀 火箭飞行中...\n\n当前倍数: {mult}x\n\n下注: {bet} ⭐\n潜在奖金: {win} ⭐",
        "rocket_crash": "💥 火箭爆炸!\n\n崩溃点: {crash}x\n你的下注: {bet} ⭐\n\n你失去了 {bet} ⭐",
        "rocket_win": "✅ 已兑现!\n\n倍数: {mult}x\n下注: {bet} ⭐\n奖金: {win} ⭐\n利润: +{profit} ⭐",
        "already_rocket": "你已经有一个活跃的火箭!",
        "choose_bet": "🚀 火箭\n\n你的余额: {bal} ⭐\n\n选择下注:",
        "profile_text": "👤 个人资料\n\n名字: {name}\n⭐ 星星: {stars}\n挖矿等级: {level}\n排名: #{rank}\n游戏次数: {games}\n等级: {rank_name}\nPremium: {premium}\n号码: {number}",
        "top_title": "🏆 前10名玩家:\n\n",
        "mining_text": "挖矿\n\n⭐ 总计: {stars}\n等级: {level}\n\n点击下方按钮:",
        "games_text": "🎮 游戏\n\n选择游戏:",
        "mines_text": "💣 地雷\n\n输入下注金额 (100 到 1 000 000 ⭐):",
        "mines_count": "💣 现在输入地雷数量 (1 到 24):",
        "give_ok": "✅ 已给予 {amount}⭐ 给 @{user}",
        "give_fail": "❌ 用户未找到",
        "news_ok": "✅ 广播已发送",
        "no_access": "❌ 无权限",
        "invalid_bet": "❌ 无效金额。请输入 100 到 1 000 000 的数字",
        "invalid_mines": "❌ 无效数量。请输入 1 到 24",
        "exchange_text": "💱 兑换\n\n汇率: 1 TON = 200 ⭐\n\n输入要兑换的 TON 数量:",
        "shop": "🛒 商店",
        "buy_premium": "⭐ 购买 Premium (10 000 000 ⭐ / 30天)",
        "buy_888": "📱 号码 +888 (10 000 000 ⭐)",
        "buy_7": "📱 号码 +7 (1 000 000 ⭐)",
        "buy_380": "📱 号码 +380 (1 000 000 ⭐)",
    }
}

def t(uid, key, **kwargs):
    cur.execute("SELECT lang FROM users WHERE id=?", (uid,))
    row = cur.fetchone()
    lang = row[0] if row else "ru"
    text = TEXTS.get(lang, TEXTS["ru"]).get(key, key)
    return text.format(**kwargs) if kwargs else text

def get_user(uid):
    cur.execute("SELECT name, stars, level, last_click, games_played, is_admin, lang, premium_until, number FROM users WHERE id=?", (uid,))
    return cur.fetchone()

def get_rank(uid):
    cur.execute("SELECT COUNT(*) FROM users WHERE stars > (SELECT stars FROM users WHERE id=?)", (uid,))
    return cur.fetchone()[0] + 1

def fmt(num):
    return f"{num:,}".replace(",", " ")

def generate_crash_point():
    r = random.random()
    if r < 0.38:
        return round(random.uniform(1.00, 1.99), 2)
    elif r < 0.72:
        return round(random.uniform(2.00, 4.99), 2)
    elif r < 0.90:
        return round(random.uniform(5.00, 9.99), 2)
    else:
        return round(random.uniform(10.00, 80.00), 2)

def main_reply_kb(uid):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(uid, "btn_games")), KeyboardButton(text=t(uid, "btn_profile"))],
            [KeyboardButton(text=t(uid, "btn_mining")), KeyboardButton(text=t(uid, "btn_top"))],
            [KeyboardButton(text=t(uid, "btn_exchange")), KeyboardButton(text="🛒 Shop")]
        ],
        resize_keyboard=True
    )

def back_kb(uid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(uid, "back"), callback_data="main")]
    ])

def mining_kb(uid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(uid, "farm"), callback_data="farm")],
        [InlineKeyboardButton(text=t(uid, "back"), callback_data="main")]
    ])

def mines_grid(uid, mines_count, opened_list):
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
    kb.append([InlineKeyboardButton(text="💰 Cash Out", callback_data="cashout")])
    kb.append([InlineKeyboardButton(text=t(uid, "back"), callback_data="main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

# ====================== START ======================
@dp.message(CommandStart())
async def start(msg: types.Message):
    uid = msg.from_user.id
    username = msg.from_user.username or ""
    is_admin = 1 if username.lower() == ADMIN_USERNAME.lower() else 0

    cur.execute("""
        INSERT OR IGNORE INTO users(id, name, username, join_date, is_admin)
        VALUES(?,?,?,?,?)
    """, (uid, msg.from_user.first_name, username, time.time(), is_admin))

    if is_admin:
        cur.execute("UPDATE users SET is_admin=1, username=? WHERE id=?", (username, uid))
    db.commit()

    await msg.answer(t(uid, "main"), reply_markup=main_reply_kb(uid))

# ====================== LANGUAGE ======================
@dp.message(Command("language"))
@dp.message(Command("lang"))
async def language_cmd(msg: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="setlang_ru")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="setlang_en")],
        [InlineKeyboardButton(text="🇨🇳 中文", callback_data="setlang_zh")]
    ])
    await msg.answer(t(msg.from_user.id, "choose_lang"), reply_markup=kb)

@dp.callback_query(F.data.startswith("setlang_"))
async def set_language(cb: types.CallbackQuery):
    lang = cb.data.split("_")[1]
    uid = cb.from_user.id
    cur.execute("UPDATE users SET lang=? WHERE id=?", (lang, uid))
    db.commit()
    await cb.message.edit_text(t(uid, "lang_changed"))
    await cb.message.answer(t(uid, "main"), reply_markup=main_reply_kb(uid))

# ====================== REPLY KEYBOARD ======================
@dp.message(F.text.in_(["🎮 Игры", "🎮 Games", "🎮 游戏"]))
async def reply_games(msg: types.Message):
    uid = msg.from_user.id
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(uid, "mines"), callback_data="mines_menu")],
        [InlineKeyboardButton(text=t(uid, "rocket"), callback_data="rocket_menu")],
        [InlineKeyboardButton(text=t(uid, "dice"), callback_data="dice_menu")],
        [InlineKeyboardButton(text=t(uid, "roulette"), callback_data="roulette_menu")],
        [InlineKeyboardButton(text=t(uid, "back"), callback_data="main")]
    ])
    await msg.answer(t(uid, "games_text"), reply_markup=kb)

@dp.message(F.text.in_(["👤 Профиль", "👤 Profile", "👤 个人资料"]))
async def reply_profile(msg: types.Message):
    uid = msg.from_user.id
    u = get_user(uid)
    rank = get_rank(uid)
    rank_name = t(uid, "admin") if u[5] else t(uid, "player")
    
    premium_status = "❌"
    if u[7] and u[7] > time.time():
        left = int((u[7] - time.time()) / 86400)
        premium_status = f"✅ ещё {left} дн."
    
    number = u[8] if u[8] else "—"
    
    text = t(uid, "profile_text",
             name=u[0], stars=fmt(u[1]), level=u[2],
             rank=rank, games=u[4], rank_name=rank_name,
             premium=premium_status, number=number)
    await msg.answer(text, reply_markup=main_reply_kb(uid))

@dp.message(F.text.in_(["⛏ Майнинг", "⛏ Mining", "⛏ 挖矿"]))
async def reply_mining(msg: types.Message):
    uid = msg.from_user.id
    u = get_user(uid)
    text = t(uid, "mining_text", stars=fmt(u[1]), level=u[2])
    await msg.answer(text, reply_markup=mining_kb(uid))

@dp.message(F.text.in_(["🏆 Рейтинг", "🏆 Leaderboard", "🏆 排行榜"]))
async def reply_top(msg: types.Message):
    uid = msg.from_user.id
    cur.execute("SELECT name, stars FROM users ORDER BY stars DESC LIMIT 10")
    rows = cur.fetchall()
    text = t(uid, "top_title")
    for i, row in enumerate(rows, 1):
        text += f"{i}. {row[0]} — {fmt(row[1])}⭐\n"
    await msg.answer(text, reply_markup=main_reply_kb(uid))

@dp.message(F.text.in_(["💱 Обменник", "💱 Exchange", "💱 兑换"]))
async def reply_exchange(msg: types.Message, state: FSMContext):
    uid = msg.from_user.id
    await msg.answer(t(uid, "exchange_text"))
    await state.set_state("exchange_ton")

@dp.message(F.text == "🛒 Shop")
async def reply_shop(msg: types.Message):
    uid = msg.from_user.id
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(uid, "buy_premium"), callback_data="buy_premium")],
        [InlineKeyboardButton(text=t(uid, "buy_888"), callback_data="buy_number_888")],
        [InlineKeyboardButton(text=t(uid, "buy_7"), callback_data="buy_number_7")],
        [InlineKeyboardButton(text=t(uid, "buy_380"), callback_data="buy_number_380")],
        [InlineKeyboardButton(text=t(uid, "back"), callback_data="main")]
    ])
    await msg.answer("🛒 Магазин", reply_markup=kb)

# ====================== EXCHANGE ======================
@dp.message(F.state == "exchange_ton")
async def process_exchange(msg: types.Message, state: FSMContext):
    uid = msg.from_user.id
    try:
        ton = float(msg.text.replace(",", "."))
        if ton <= 0:
            raise ValueError
    except:
        await state.clear()
        return await msg.answer("❌ Неверное число")

    stars = int(ton * 200)
    cur.execute("UPDATE users SET stars = stars + ? WHERE id=?", (stars, uid))
    db.commit()
    await state.clear()
    await msg.answer(f"✅ Обменяно!\n+{fmt(stars)} ⭐", reply_markup=main_reply_kb(uid))

# ====================== SHOP ======================
@dp.callback_query(F.data == "buy_premium")
async def buy_premium(cb: types.CallbackQuery):
    uid = cb.from_user.id
    u = get_user(uid)
    if u[1] < 10000000:
        return await cb.answer(t(uid, "not_enough"), show_alert=True)
    
    cur.execute("UPDATE users SET stars = stars - 10000000, premium_until = ? WHERE id=?", 
                (time.time() + 30*86400, uid))
    db.commit()
    await cb.message.edit_text("✅ Premium куплен на 30 дней!", reply_markup=back_kb(uid))

@dp.callback_query(F.data.startswith("buy_number_"))
async def buy_number(cb: types.CallbackQuery):
    uid = cb.from_user.id
    code = cb.data.split("_")[2]
    u = get_user(uid)
    
    prices = {"888": 10000000, "7": 1000000, "380": 1000000}
    price = prices.get(code, 1000000)
    
    if u[1] < price:
        return await cb.answer(t(uid, "not_enough"), show_alert=True)
    
    if code == "888":
        number = f"+888{random.randint(10000000, 99999999)}"
    elif code == "7":
        number = f"+7{random.randint(9000000000, 9999999999)}"
    else:
        number = f"+380{random.randint(100000000, 999999999)}"
    
    cur.execute("UPDATE users SET stars = stars - ?, number = ? WHERE id=?", (price, number, uid))
    db.commit()
    await cb.message.edit_text(f"✅ Номер получен!\n\n`{number}`", reply_markup=back_kb(uid), parse_mode="Markdown")

# ====================== ADMIN ======================
@dp.message(Command("give"))
async def give_cmd(msg: types.Message):
    uid = msg.from_user.id
    u = get_user(uid)
    if not u or not u[5]:
        return await msg.answer(t(uid, "no_access"))

    try:
        parts = msg.text.split()
        amount = int(parts[1])
        username = parts[2].replace("@", "").lower()
    except:
        return await msg.answer("Usage: /give amount username")

    cur.execute("SELECT id FROM users WHERE LOWER(username)=?", (username,))
    row = cur.fetchone()
    if not row:
        return await msg.answer(t(uid, "give_fail"))

    cur.execute("UPDATE users SET stars = stars + ? WHERE id=?", (amount, row[0]))
    db.commit()
    await msg.answer(t(uid, "give_ok", amount=fmt(amount), user=username))

@dp.message(Command("news"))
async def news_cmd(msg: types.Message):
    uid = msg.from_user.id
    u = get_user(uid)
    if not u or not u[5]:
        return await msg.answer(t(uid, "no_access"))

    text = msg.text[6:].strip()
    if not text:
        return await msg.answer("Usage: /news text")

    cur.execute("SELECT id FROM users")
    users = cur.fetchall()
    success = 0
    for (user_id,) in users:
        try:
            await bot.send_message(user_id, f"📢 {text}")
            success += 1
        except:
            pass
    await msg.answer(f"{t(uid, 'news_ok')} ({success})")

# ====================== INLINE MAIN ======================
@dp.callback_query(F.data == "main")
async def main_menu(cb: types.CallbackQuery):
    uid = cb.from_user.id
    await cb.message.answer(t(uid, "main"), reply_markup=main_reply_kb(uid))

@dp.callback_query(F.data == "farm")
async def farm(cb: types.CallbackQuery):
    uid = cb.from_user.id
    now = time.time()
    u = get_user(uid)

    if now - u[3] < 1.0:
        return await cb.answer(t(uid, "wait"), show_alert=True)

    income = LEVELS.get(u[2], 1)
    # Premium boost
    if u[7] and u[7] > time.time():
        income = int(income * 1.5)

    cur.execute("UPDATE users SET stars = stars + ?, last_click = ? WHERE id=?", (income, now, uid))
    db.commit()

    u = get_user(uid)
    text = t(uid, "mining_text", stars=fmt(u[1]), level=u[2])
    await cb.message.edit_text(text, reply_markup=mining_kb(uid))
    await cb.answer(f"+{income}⭐")

# ====================== MINES ======================
@dp.callback_query(F.data == "mines_menu")
async def mines_menu(cb: types.CallbackQuery, state: FSMContext):
    uid = cb.from_user.id
    await state.set_state(MinesStates.waiting_bet)
    await cb.message.edit_text(t(uid, "mines_text"))

@dp.message(MinesStates.waiting_bet)
async def mines_bet_input(msg: types.Message, state: FSMContext):
    uid = msg.from_user.id
    try:
        bet = int(msg.text.replace(" ", "").replace(",", ""))
        if bet < 100 or bet > 1000000:
            return await msg.answer(t(uid, "invalid_bet"))
    except:
        return await msg.answer(t(uid, "invalid_bet"))

    u = get_user(uid)
    if u[1] < bet:
        await state.clear()
        return await msg.answer(t(uid, "not_enough"))

    await state.update_data(bet=bet)
    await state.set_state(MinesStates.waiting_mines)
    await msg.answer(t(uid, "mines_count"))

@dp.message(MinesStates.waiting_mines)
async def mines_count_input(msg: types.Message, state: FSMContext):
    uid = msg.from_user.id
    try:
        mines_count = int(msg.text)
        if mines_count < 1 or mines_count > 24:
            return await msg.answer(t(uid, "invalid_mines"))
    except:
        return await msg.answer(t(uid, "invalid_mines"))

    data = await state.get_data()
    bet = data["bet"]
    await state.clear()

    u = get_user(uid)
    if u[1] < bet:
        return await msg.answer(t(uid, "not_enough"))

    cur.execute("UPDATE users SET stars = stars - ? WHERE id=?", (bet, uid))
    positions = random.sample(range(25), mines_count)
    positions_str = ",".join(map(str, positions))

    cur.execute("""
        INSERT OR REPLACE INTO active_mines(user_id, bet, mines_count, opened, mine_positions, multiplier)
        VALUES(?,?,?,?,?,?)
    """, (uid, bet, mines_count, "", positions_str, 1.0))
    db.commit()

    await msg.answer(
        f"💣 Mines ({mines_count})\n\nBet: {fmt(bet)}⭐\nMult: 1.0x\nWin: 0⭐",
        reply_markup=mines_grid(uid, mines_count, [])
    )

@dp.callback_query(F.data.startswith("open_"))
async def open_cell(cb: types.CallbackQuery):
    uid = cb.from_user.id
    cell = int(cb.data.split("_")[1])

    cur.execute("SELECT bet, mines_count, opened, mine_positions FROM active_mines WHERE user_id=?", (uid,))
    session = cur.fetchone()
    if not session:
        return await cb.answer("No game", show_alert=True)

    bet, mines_count, opened_str, mine_pos_str = session
    opened = [int(x) for x in opened_str.split(",")] if opened_str else []
    mine_pos = [int(x) for x in mine_pos_str.split(",")]

    if cell in opened:
        return await cb.answer("Already")

    if cell in mine_pos:
        cur.execute("DELETE FROM active_mines WHERE user_id=?", (uid,))
        cur.execute("UPDATE users SET games_played = games_played + 1 WHERE id=?", (uid,))
        db.commit()
        await cb.message.edit_text(t(uid, "boom", bet=fmt(bet)), reply_markup=back_kb(uid))
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
        await cb.message.edit_text(t(uid, "win_all", win=fmt(win), mult=multiplier), reply_markup=back_kb(uid))
        return

    await cb.message.edit_text(
        f"💣 Mines ({mines_count})\n\nBet: {fmt(bet)}⭐\nMult: {multiplier}x\nWin: {fmt(win)}⭐",
        reply_markup=mines_grid(uid, mines_count, opened)
    )

@dp.callback_query(F.data == "cashout")
async def cashout_mines(cb: types.CallbackQuery):
    uid = cb.from_user.id
    cur.execute("SELECT bet, multiplier FROM active_mines WHERE user_id=?", (uid,))
    session = cur.fetchone()
    if not session:
        return await cb.answer("No game", show_alert=True)

    bet, mult = session
    win = int(bet * mult)

    cur.execute("UPDATE users SET stars = stars + ?, games_played = games_played + 1 WHERE id=?", (win, uid))
    cur.execute("DELETE FROM active_mines WHERE user_id=?", (uid,))
    db.commit()

    await cb.message.edit_text(t(uid, "cashed", win=fmt(win), mult=mult), reply_markup=back_kb(uid))

# ====================== ROCKET ======================
@dp.callback_query(F.data == "rocket_menu")
async def rocket_menu(cb: types.CallbackQuery):
    uid = cb.from_user.id
    u = get_user(uid)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="100 ⭐", callback_data="rocket_bet_100"),
         InlineKeyboardButton(text="500 ⭐", callback_data="rocket_bet_500")],
        [InlineKeyboardButton(text="1 000 ⭐", callback_data="rocket_bet_1000"),
         InlineKeyboardButton(text="5 000 ⭐", callback_data="rocket_bet_5000")],
        [InlineKeyboardButton(text="10 000 ⭐", callback_data="rocket_bet_10000"),
         InlineKeyboardButton(text="50 000 ⭐", callback_data="rocket_bet_50000")],
        [InlineKeyboardButton(text="100 000 ⭐", callback_data="rocket_bet_100000"),
         InlineKeyboardButton(text="1 000 000 ⭐", callback_data="rocket_bet_1000000")],
        [InlineKeyboardButton(text=t(uid, "back"), callback_data="main")]
    ])
    await cb.message.edit_text(t(uid, "choose_bet", bal=fmt(u[1])), reply_markup=kb)

@dp.callback_query(F.data.startswith("rocket_bet_"))
async def rocket_place_bet(cb: types.CallbackQuery):
    uid = cb.from_user.id
    bet = int(cb.data.split("_")[2])
    u = get_user(uid)

    cur.execute("SELECT 1 FROM active_rocket WHERE user_id=?", (uid,))
    if cur.fetchone():
        return await cb.answer(t(uid, "already_rocket"), show_alert=True)

    if u[1] < bet:
        return await cb.answer(t(uid, "not_enough"), show_alert=True)

    cur.execute("UPDATE users SET stars = stars - ? WHERE id=?", (bet, uid))
    crash_point = generate_crash_point()
    start_time = time.time()

    cur.execute("INSERT INTO active_rocket (user_id, bet, crash_point, start_time, status) VALUES (?, ?, ?, ?, 'flying')",
                (uid, bet, crash_point, start_time))
    db.commit()

    asyncio.create_task(rocket_flight(cb.message, uid, bet, crash_point))

async def rocket_flight(message: types.Message, uid: int, bet: int, crash_point: float):
    cashout_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 CASH OUT", callback_data="rocket_cashout")]
    ])

    try:
        while True:
            cur.execute("SELECT status, start_time FROM active_rocket WHERE user_id=?", (uid,))
            row = cur.fetchone()
            if not row or row[0] != "flying":
                break

            start_time = row[1]
            elapsed = time.time() - start_time

            if elapsed < 7:
                multiplier = 1.00 + elapsed * 0.14
            else:
                multiplier = 2.00 + (elapsed - 7) * 0.35
            multiplier = round(multiplier, 2)

            if multiplier >= crash_point:
                cur.execute("DELETE FROM active_rocket WHERE user_id=?", (uid,))
                cur.execute("UPDATE users SET games_played = games_played + 1 WHERE id=?", (uid,))
                db.commit()
                await message.edit_text(t(uid, "rocket_crash", crash=crash_point, bet=fmt(bet)), reply_markup=back_kb(uid))
                break

            win = int(bet * multiplier)
            text = t(uid, "rocket_fly", mult=multiplier, bet=fmt(bet), win=fmt(win))
            try:
                await message.edit_text(text, reply_markup=cashout_kb, parse_mode="HTML")
            except:
                pass
            await asyncio.sleep(0.7)
    except Exception as e:
        print("Rocket error:", e)
        cur.execute("DELETE FROM active_rocket WHERE user_id=?", (uid,))
        db.commit()

@dp.callback_query(F.data == "rocket_cashout")
async def rocket_cashout(cb: types.CallbackQuery):
    uid = cb.from_user.id
    cur.execute("SELECT bet, crash_point, start_time, status FROM active_rocket WHERE user_id=?", (uid,))
    row = cur.fetchone()
    if not row or row[3] != "flying":
        return await cb.answer("Already finished", show_alert=True)

    bet, crash_point, start_time, status = row
    elapsed = time.time() - start_time
    if elapsed < 7:
        multiplier = 1.00 + elapsed * 0.14
    else:
        multiplier = 2.00 + (elapsed - 7) * 0.35
    multiplier = round(multiplier, 2)

    if multiplier >= crash_point:
        return await cb.answer("Too late!", show_alert=True)

    win = int(bet * multiplier)
    cur.execute("UPDATE users SET stars = stars + ?, games_played = games_played + 1 WHERE id=?", (win, uid))
    cur.execute("DELETE FROM active_rocket WHERE user_id=?", (uid,))
    db.commit()

    await cb.message.edit_text(
        t(uid, "rocket_win", mult=multiplier, bet=fmt(bet), win=fmt(win), profit=fmt(win - bet)),
        reply_markup=back_kb(uid)
    )

# ====================== DICE ======================
@dp.callback_query(F.data == "dice_menu")
async def dice_menu(cb: types.CallbackQuery, state: FSMContext):
    uid = cb.from_user.id
    await state.set_state(DiceStates.waiting_bet)
    await cb.message.edit_text("🎲 Кости\n\nВведи сумму ставки (100 — 1 000 000):")

@dp.message(DiceStates.waiting_bet)
async def dice_bet(msg: types.Message, state: FSMContext):
    uid = msg.from_user.id
    try:
        bet = int(msg.text.replace(" ", ""))
        if bet < 100 or bet > 1000000:
            return await msg.answer(t(uid, "invalid_bet"))
    except:
        return await msg.answer(t(uid, "invalid_bet"))

    u = get_user(uid)
    if u[1] < bet:
        await state.clear()
        return await msg.answer(t(uid, "not_enough"))

    await state.update_data(bet=bet)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Normal (больше побеждает)", callback_data="dice_normal")],
        [InlineKeyboardButton(text="Cursed (меньше побеждает)", callback_data="dice_cursed")],
        [InlineKeyboardButton(text=t(uid, "back"), callback_data="main")]
    ])
    await state.set_state(DiceStates.waiting_mode)
    await msg.answer("Выбери режим:", reply_markup=kb)

@dp.callback_query(F.data.in_(["dice_normal", "dice_cursed"]))
async def dice_play(cb: types.CallbackQuery, state: FSMContext):
    uid = cb.from_user.id
    data = await state.get_data()
    bet = data.get("bet")
    if not bet:
        await state.clear()
        return await cb.answer("Ошибка", show_alert=True)

    mode = "normal" if cb.data == "dice_normal" else "cursed"
    await state.clear()

    u = get_user(uid)
    if u[1] < bet:
        return await cb.answer(t(uid, "not_enough"), show_alert=True)

    cur.execute("UPDATE users SET stars = stars - ? WHERE id=?", (bet, uid))
    db.commit()

    player_dice = random.randint(1, 6)
    bot_dice = random.randint(1, 6)

    if mode == "normal":
        win = player_dice > bot_dice
    else:
        win = player_dice < bot_dice

    if player_dice == bot_dice:
        cur.execute("UPDATE users SET stars = stars + ? WHERE id=?", (bet, uid))
        db.commit()
        result = f"🤝 Ничья!\n\nТы: {player_dice} | Бот: {bot_dice}\nСтавка возвращена."
    elif win:
        cur.execute("UPDATE users SET stars = stars + ? WHERE id=?", (bet * 2, uid))
        db.commit()
        result = f"✅ Победа!\n\nТы: {player_dice} | Бот: {bot_dice}\n+{fmt(bet)} ⭐"
    else:
        result = f"❌ Поражение\n\nТы: {player_dice} | Бот: {bot_dice}\n-{fmt(bet)} ⭐"

    cur.execute("UPDATE users SET games_played = games_played + 1 WHERE id=?", (uid,))
    db.commit()
    await cb.message.edit_text(result, reply_markup=back_kb(uid))

# ====================== ROULETTE ======================
@dp.callback_query(F.data == "roulette_menu")
async def roulette_menu(cb: types.CallbackQuery, state: FSMContext):
    uid = cb.from_user.id
    await state.set_state(RouletteStates.waiting_bet)
    await cb.message.edit_text("🎰 Рулетка\n\nВведи сумму ставки (100 — 1 000 000):")

@dp.message(RouletteStates.waiting_bet)
async def roulette_bet(msg: types.Message, state: FSMContext):
    uid = msg.from_user.id
    try:
        bet = int(msg.text.replace(" ", ""))
        if bet < 100 or bet > 1000000:
            return await msg.answer(t(uid, "invalid_bet"))
    except:
        return await msg.answer(t(uid, "invalid_bet"))

    u = get_user(uid)
    if u[1] < bet:
        await state.clear()
        return await msg.answer(t(uid, "not_enough"))

    await state.update_data(bet=bet)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔴 Красный", callback_data="roulette_red")],
        [InlineKeyboardButton(text="⚫ Чёрный", callback_data="roulette_black")],
        [InlineKeyboardButton(text="⚪ Белый", callback_data="roulette_white")],
        [InlineKeyboardButton(text=t(uid, "back"), callback_data="main")]
    ])
    await state.set_state(RouletteStates.waiting_color)
    await msg.answer("Выбери цвет:", reply_markup=kb)

@dp.callback_query(F.data.startswith("roulette_"))
async def roulette_play(cb: types.CallbackQuery, state: FSMContext):
    uid = cb.from_user.id
    data = await state.get_data()
    bet = data.get("bet")
    if not bet:
        await state.clear()
        return

    color = cb.data.split("_")[1]
    await state.clear()

    u = get_user(uid)
    if u[1] < bet:
        return await cb.answer(t(uid, "not_enough"), show_alert=True)

    cur.execute("UPDATE users SET stars = stars - ? WHERE id=?", (bet, uid))
    db.commit()

    # Анимация
    colors = ["🔴", "⚫", "⚪", "🔴", "⚫", "⚪", "🔴", "⚫"]
    msg = await cb.message.edit_text("🎰 Крутим...\n\n" + " | ".join(colors))

    for i in range(8):
        random.shuffle(colors)
        try:
            await msg.edit_text(f"🎰 Крутим...\n\n{' | '.join(colors)}\n\n⬇️")
        except:
            pass
        await asyncio.sleep(0.35)

    # Результат (с небольшим house edge)
    r = random.random()
    if r < 0.32:
        result_color = "red"
        result_emoji = "🔴"
    elif r < 0.64:
        result_color = "black"
        result_emoji = "⚫"
    else:
        result_color = "white"
        result_emoji = "⚪"

    if color == result_color:
        win = bet * 2
        cur.execute("UPDATE users SET stars = stars + ? WHERE id=?", (win, uid))
        text = f"✅ Победа!\n\nВыпало: {result_emoji}\n+{fmt(bet)} ⭐"
    else:
        text = f"❌ Проигрыш\n\nВыпало: {result_emoji}\n-{fmt(bet)} ⭐"

    cur.execute("UPDATE users SET games_played = games_played + 1 WHERE id=?", (uid,))
    db.commit()
    await msg.edit_text(text, reply_markup=back_kb(uid))

@dp.callback_query(F.data == "noop")
async def noop(cb: types.CallbackQuery):
    await cb.answer()

async def main():
    print("BOT STARTED!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())


