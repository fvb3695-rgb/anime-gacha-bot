import os
import logging
import random
from datetime import datetime, timedelta, date
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import asyncio

import aiosqlite
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ==================== ВЕБ-СЕРВЕР ДЛЯ RENDER ====================
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

threading.Thread(target=run_server, daemon=True).start()

# ==================== НАСТРОЙКИ И ИНИЦИАЛИЗАЦИЯ ====================
logging.basicConfig(level=logging.INFO)

TOKEN = "9049422974:AAG5svkRpLtL0-OXX6MikuEKNiJHHsEFoao"
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Пулы персонажей для гачи
ICARDS_POOL = [
    {"name": "Наруто Узумаки", "anime": "Naruto", "rarity": "SSR", "class": "Боец"},
    {"name": "Саске Учиха", "anime": "Naruto", "rarity": "SSR", "class": "Убийца"},
    {"name": "Луффи", "anime": "One Piece", "rarity": "SSR", "class": "Боец"},
    {"name": "Зоро", "anime": "One Piece", "rarity": "SR", "class": "Воин"},
    {"name": "Танджиро Камадо", "anime": "Kimetsu no Yaiba", "rarity": "SR", "class": "Мечник"}
]

SS_CARDS_POOL = [
    {"name": "Гоку", "anime": "Dragon Ball", "rarity": "UR", "class": "Легенда"},
    {"name": "Сатору Годжо", "anime": "Jujutsu Kaisen", "rarity": "UR", "class": "Маг"}
]

BOSS_TITLES = [
    ("Дракон Бездны", "🐉"),
    ("Архидемон Хаоса", "🔥"),
    ("Король Личей", "💀"),
    ("Титан Бури", "⚡"),
    ("Древний Бог Разрушения", "👑"),
    ("Гидра Опустошения", "🐍"),
    ("Теневой Страж", "👥"),
    ("Повелитель Кошмаров", "👁️"),
    ("Ледяной Колосс", "🧊"),
    ("Механический Разрушитель", "⚙️")
]

def get_boss_info(level: int):
    title_idx = (level - 1) % len(BOSS_TITLES)
    base_name, emoji = BOSS_TITLES[title_idx]
    suffix = ""
    if level > 50:
        suffix = f" [Легендарный ⭐{level}]"
    elif level > 20:
        suffix = f" [Элитный V-{level}]"
    elif level > 10:
        suffix = f" [Уровень {level}]"
        
    full_name = f"{emoji} {base_name}{suffix}"
    max_hp = 100 + (level - 1) * 75
    required_hits = 10 + ((level - 1) // 3) * 2
    return full_name, max_hp, required_hits


# ==================== АСИНХРОННАЯ БАЗА ДАННЫХ ====================
async def init_db():
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    nickname TEXT DEFAULT NULL,
                    rolls INTEGER DEFAULT 5,
                    books INTEGER DEFAULT 5,
                    rating INTEGER DEFAULT 1000,
                    guild TEXT DEFAULT 'Нет',
                    invited_by INTEGER DEFAULT NULL,
                    referral_count INTEGER DEFAULT 0,
                    last_claim TEXT,
                    is_donator INTEGER DEFAULT 0
                )
            """)
            
            for col, col_type in [("is_donator", "INTEGER DEFAULT 0"), ("nickname", "TEXT DEFAULT NULL")]:
                try:
                    await cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")
                except Exception:
                    pass
            
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS inventory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    character_name TEXT,
                    universe TEXT,
                    tier TEXT,
                    atk INTEGER,
                    def INTEGER,
                    hp INTEGER,
                    mana INTEGER
                )
            """)
            
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS characters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    universe TEXT,
                    tier TEXT,
                    class TEXT
                )
            """)
            
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS guilds (
                    guild_name TEXT PRIMARY KEY,
                    leader_id INTEGER,
                    members_count INTEGER DEFAULT 0
                )
            """)

            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_quests (
                    user_id INTEGER,
                    quest_id TEXT,
                    PRIMARY KEY (user_id, quest_id)
                )
            """)

            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS guild_boss (
                    guild_name TEXT PRIMARY KEY,
                    boss_name TEXT DEFAULT '🐉 Дракон Бездны',
                    boss_hp INTEGER DEFAULT 100,
                    max_hp INTEGER DEFAULT 100,
                    killers_count INTEGER DEFAULT 0,
                    is_defeated INTEGER DEFAULT 0,
                    boss_level INTEGER DEFAULT 1
                )
            """)

            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS guild_boss_hits (
                    user_id INTEGER,
                    guild_name TEXT,
                    hit_date TEXT,
                    PRIMARY KEY (user_id, guild_name)
                )
            """)

            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_upgrades (
                    user_id INTEGER PRIMARY KEY,
                    extra_atk INTEGER DEFAULT 0,
                    extra_def INTEGER DEFAULT 0,
                    extra_mana INTEGER DEFAULT 0
                )
            """)
            
            await cursor.execute("SELECT COUNT(*) FROM guilds")
            if (await cursor.fetchone())[0] == 0:
                await cursor.executemany("INSERT INTO guilds (guild_name, members_count) VALUES (?, ?)", [
                    ("Акацуки", 0),
                    ("Убийцы Драконов", 0),
                    ("Стражи Галактики", 0)
                ])
                await conn.commit()

            await cursor.execute("SELECT COUNT(*) FROM characters")
            row = await cursor.fetchone()
            if row and row[0] == 0:
                all_to_insert = []
                for c in ICARDS_POOL + SS_CARDS_POOL:
                    all_to_insert.append((c["name"], c["anime"], c["rarity"], c["class"]))
                await cursor.executemany("INSERT INTO characters (name, universe, tier, class) VALUES (?, ?, ?, ?)", all_to_insert)
                await conn.commit()
                
        await conn.commit()


# ==================== КНОПКИ ГЛАВНОГО МЕНЮ ====================
def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎰 Крутить гачу", callback_data="action_roll"),
            InlineKeyboardButton(text="👤 Профиль", callback_data="action_profile")
        ],
        [
            InlineKeyboardButton(text="🏰 Гильдии", callback_data="action_guilds"),
            InlineKeyboardButton(text="🏆 Топ по силе", callback_data="action_power_top")
        ],
        [
            InlineKeyboardButton(text="🎯 Задания", callback_data="action_quests"),
            InlineKeyboardButton(text="📚 Библиотека", callback_data="action_books_farm")
        ],
        [
            InlineKeyboardButton(text="💎 Донат", callback_data="action_donate_shop"),
            InlineKeyboardButton(text="✏️ Сменить ник", callback_data="action_change_nick")
        ]
    ])


# ==================== СТАРТ И НИКНЕЙМЫ ====================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    args = message.text.split()
    inviter_id = None

    if len(args) > 1 and args[1].startswith("ref"):
        try:
            inviter_id = int(args[1].replace("ref", ""))
        except ValueError:
            pass

    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
            user = await cursor.fetchone()

            if not user:
                default_nick = message.from_user.first_name or f"Герой_{user_id}"
                actual_inviter = inviter_id if (inviter_id and inviter_id != user_id) else None
                if actual_inviter:
                    await cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (actual_inviter,))
                    if await cursor.fetchone():
                        await cursor.execute(
                            "INSERT INTO users (user_id, nickname, rolls, books, rating, guild, invited_by) VALUES (?, ?, 5, 5, 1000, 'Нет', ?)",
                            (user_id, default_nick, actual_inviter)
                        )
                        await cursor.execute("UPDATE users SET referral_count = referral_count + 1, rolls = rolls + 2 WHERE user_id = ?", (actual_inviter,))
                    else:
                        await cursor.execute("INSERT INTO users (user_id, nickname, rolls, books, rating, guild) VALUES (?, ?, 5, 5, 1000, 'Нет')", (user_id, default_nick))
                else:
                    await cursor.execute("INSERT INTO users (user_id, nickname, rolls, books, rating, guild) VALUES (?, ?, 5, 5, 1000, 'Нет')", (user_id, default_nick))
                await conn.commit()

    text = (
        "✨ **Добро пожаловать в Аниме Гачу!** ✨\n\n"
        "Собирайте персонажей, вступайте в гильдии, сражайтесь с боссами и поднимайтесь в Топе по силе!"
    )
    await message.answer(text, reply_markup=get_main_keyboard(), parse_mode="Markdown")

@dp.callback_query(F.data == "action_main_menu")
async def back_to_main_menu(callback: types.CallbackQuery):
    text = "🏠 **Главное меню:**"
    await callback.message.edit_text(text, reply_markup=get_main_keyboard(), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "action_change_nick")
async def ask_nickname(callback: types.CallbackQuery):
    text = (
        "✏️ **Смена никнейма**\n\n"
        "Отправьте в чат команду вместе с вашим новым ником в таком формате:\n"
        "`/setnick МоеИмя`"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="action_main_menu")]])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

@dp.message(Command("setnick"))
async def set_nickname_cmd(message: types.Message):
    user_id = message.from_user.id
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("⚠️ Укажите ник после команды. Пример: `/setnick Саске`", parse_mode="Markdown")
        return
    
    new_nick = parts[1].strip()[:20]
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("UPDATE users SET nickname = ? WHERE user_id = ?", (new_nick, user_id))
            await conn.commit()
            
    await message.answer(f"✅ Ваш ник успешно изменен на: **{new_nick}**!", parse_mode="Markdown")


# ==================== ТОП ПО СИЛЕ ====================
@dp.callback_query(F.data == "action_power_top")
async def show_power_top(callback: types.CallbackQuery):
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            # Получаем всех пользователей
            await cursor.execute("SELECT user_id, nickname, is_donator FROM users")
            users = await cursor.fetchall()

            leaderboard = []
            for u_id, nick, is_donator in users:
                # Считаем силу карт (сумма atk + def + hp + mana)
                await cursor.execute("SELECT SUM(atk + def + hp + mana) FROM inventory WHERE user_id = ?", (u_id,))
                cards_sum = (await cursor.fetchone())[0] or 0

                # Считаем статы от книг/доната
                await cursor.execute("SELECT extra_atk, extra_def, extra_mana FROM user_upgrades WHERE user_id = ?", (u_id,))
                up = await cursor.fetchone()
                up_sum = sum(up) if up else 0

                total_power = cards_sum + (up_sum * 10)
                leaderboard.append((nick, total_power, is_donator))

            # Сортируем по убыванию силы
            leaderboard.sort(key=lambda x: x[1], reverse=True)

    top_text = "🏆 **Топ-10 Сильнейших Игроков** 🏆\n\n"
    for idx, (nick, power, is_don) in enumerate(leaderboard[:10], 1):
        medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"{idx}."
        vip = " ⭐" if is_don else ""
        top_text += f"{medal} **{nick}**{vip} — `⚡ {power} силы`\n"

    if not leaderboard:
        top_text += "Список лидеров пока пуст."

    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Главное меню", callback_data="action_main_menu")]])
    await callback.message.edit_text(top_text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


# ==================== ДОНАТ МАГАЗИН И VIP-СТАТУС ====================
@dp.callback_query(F.data == "action_donate_shop")
async def show_donate_shop(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎫 Пакет «Малый» (+5 круток)", callback_data="buy_donate_rolls_5")],
        [InlineKeyboardButton(text="🎫 Пакет «Большой» (+15 круток)", callback_data="buy_donate_rolls_15")],
        [InlineKeyboardButton(text="📚 Набор книг мудрости (+10 книг)", callback_data="buy_donate_books_10")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="action_main_menu")]
    ])
    text = (
        "💎 **Магазин Доната и VIP-статуса**\n\n"
        "Покупка любого пакета навсегда активирует статус **⭐ VIP-Донатер** (подсветка в профиле, гильдиях, плюс бонус к урону по боссам)!\n\n"
        "⚠️ *Демо-режим: в тестовой среде пополнение зачисляется мгновенно бесплатно.*"
    )
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data.startswith("buy_donate_"))
async def process_donate_purchase(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    action = callback.data.replace("buy_donate_", "")
    
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("UPDATE users SET is_donator = 1 WHERE user_id = ?", (user_id,))
            
            if action == "rolls_5":
                await cursor.execute("UPDATE users SET rolls = rolls + 5 WHERE user_id = ?", (user_id,))
                msg = "💎 Успешно! +5 круток и статус ⭐ VIP-Донатер!"
            elif action == "rolls_15":
                await cursor.execute("UPDATE users SET rolls = rolls + 15 WHERE user_id = ?", (user_id,))
                msg = "💎 Успешно! +15 круток и статус ⭐ VIP-Донатер!"
            elif action == "books_10":
                await cursor.execute("UPDATE users SET books = books + 10 WHERE user_id = ?", (user_id,))
                msg = "💎 Успешно! +10 книг и статус ⭐ VIP-Донатер!"
            else:
                msg = "✅ Покупка оформлена!"
            await conn.commit()

    await callback.answer(msg, show_alert=True)
    await show_donate_shop(callback)


# ==================== ПРОФИЛЬ И РЕФЕРАЛЫ ====================
@dp.callback_query(F.data == "action_profile")
async def show_profile(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT nickname, rolls, books, rating, guild, referral_count, is_donator FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            nick, rolls, books, rating, guild, ref_count, is_donator = row if row else ("Герой", 0, 0, 1000, 'Нет', 0, 0)
            
            await cursor.execute("SELECT COUNT(*) FROM inventory WHERE user_id = ?", (user_id,))
            inv_count = (await cursor.fetchone())[0]

            await cursor.execute("SELECT extra_atk, extra_def, extra_mana FROM user_upgrades WHERE user_id = ?", (user_id,))
            up = await cursor.fetchone()
            atk, defs, mana = up if up else (0, 0, 0)

    vip_badge = " ⭐ [VIP-Донатер]" if is_donator else ""

    text = (
        f"👤 **Профиль: {nick}**{vip_badge}\n\n"
        f"🎫 Крутки: `{rolls}`\n"
        f"📚 Книги (баффы): `{books}`\n"
        f"🏆 Рейтинг: `{rating}`\n"
        f"🏰 Гильдия: `{guild}`\n"
        f"📦 Карток в инвентаре: `{inv_count}`\n"
        f"👥 Приглашено друзей: `{ref_count}`\n\n"
        f"📈 **Бонусы статов:** Атака +{atk} | Защита +{defs} | Мана +{mana}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Сменить ник", callback_data="action_change_nick")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="action_main_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "action_referral")
async def referral_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT referral_count FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
    
    ref_count = row[0] if row and row[0] is not None else 0
    ref_link = f"https://t.me/my_anime_gacha_bot?start=ref{user_id}"
    
    text = (
        "🤝 **Реферальная программа**\n\n"
        "Зовите друзей и получайте крутки!\n"
        "• За друга: +2 крутки 🎫\n"
        "• Новому игроку: 5 круток + 5 книг 🎁\n\n"
        f"👥 Приглашено друзей: `{ref_count}`\n\n"
        f"🔗 Ваша ссылка:\n`{ref_link}`"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="action_main_menu")]])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


# ==================== СИСТЕМА ГАЧИ ====================
@dp.callback_query(F.data == "action_roll")
async def process_roll(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT rolls FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            rolls = row[0] if row else 0

            if rolls < 1:
                await callback.answer("❌ У вас закончились крутки! Посетите магазин доната или задания.", show_alert=True)
                return

            await cursor.execute("UPDATE users SET rolls = rolls - 1 WHERE user_id = ?", (user_id,))

            await cursor.execute("SELECT name, universe, tier, class FROM characters")
            chars = await cursor.fetchall()
            if not chars:
                await callback.answer("⚠️ Ошибка: база персонажей пуста.", show_alert=True)
                return

            chosen = random.choice(chars)
            name, universe, tier, c_class = chosen

            atk = random.randint(30, 90)
            def_val = random.randint(20, 70)
            hp = random.randint(100, 300)
            mana = random.randint(50, 150)

            await cursor.execute(
                "INSERT INTO inventory (user_id, character_name, universe, tier, atk, def, hp, mana) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, name, universe, tier, atk, def_val, hp, mana)
            )
            await conn.commit()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎰 Крутить еще", callback_data="action_roll")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="action_main_menu")]
    ])

    text = (
        "✨ **Вы совершили призыв!** ✨\n\n"
        f"🎴 **{name}** (`{tier}`)\n"
        f"🌌 Вселенная: {universe}\n"
        f"⚔️ Атака: {atk} | 🛡 Защита: {def_val}\n"
        f"❤️ HP: {hp} | 💧 Мана: {mana}"
    )
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


# ==================== СИСТЕМА ГИЛЬДИЙ ====================
@dp.callback_query(F.data == "action_guilds")
async def show_guilds_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT guild FROM users WHERE user_id = ?", (user_id,))
            user_row = await cursor.fetchone()
            user_guild = user_row[0] if user_row else 'Нет'
            
            await cursor.execute("SELECT guild_name, members_count, leader_id FROM guilds")
            guilds = await cursor.fetchall()

    keyboard_builder = []
    if user_guild != 'Нет':
        g_info = next((g for g in guilds if g[0] == user_guild), None)
        is_leader = g_info and g_info[2] == user_id
        
        async with aiosqlite.connect("gacha_bot.db") as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT user_id, nickname, is_donator FROM users WHERE guild = ?", (user_guild,))
                members = await cursor.fetchall()

        members_text = "\n".join([f"• {'⭐ ' if m[2] else ''}{m[1]} {'(Лидер)' if m[0] == g_info[2] else ''}" for m in members])

        text = (
            f"🏰 **Ваша гильдия:** `{user_guild}`\n\n"
            f"👥 **Состав участников:**\n{members_text}\n\n"
            "Доступные функции:"
        )
        keyboard_builder.append([InlineKeyboardButton(text="🐉 Гильд-босс (Рейд)", callback_data="action_guild_boss")])
        
        if is_leader and len(members) > 1:
            keyboard_builder.append([InlineKeyboardButton(text="👢 Кикнуть игрока", callback_data="manage_kick_menu")])
            
        keyboard_builder.append([InlineKeyboardButton(text="🚪 Покинуть гильдию", callback_data="leave_guild")])
    else:
        text = "🏰 **Список гильдий**\n\nВыберите гильдию для вступления:"
        if guilds:
            for g_name, count, _ in guilds:
                keyboard_builder.append([InlineKeyboardButton(text=f"🛡 {g_name} ({count} уч.)", callback_data=f"join_guild_{g_name}")])

    keyboard_builder.append([InlineKeyboardButton(text="◀️ Главное меню", callback_data="action_main_menu")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_builder), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data.startswith("join_guild_"))
async def process_join_guild(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    guild_name = callback.data.replace("join_guild_", "", 1)
    
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT guild FROM users WHERE user_id = ?", (user_id,))
            user_row = await cursor.fetchone()
            
            if user_row and user_row[0] and user_row[0] != 'Нет':
                await callback.answer(f"❌ Вы уже состоите в гильдии '{user_row[0]}'. Сначала покиньте её.", show_alert=True)
                return
            
            await cursor.execute("SELECT leader_id FROM guilds WHERE guild_name = ?", (guild_name,))
            g_row = await cursor.fetchone()
            if g_row and not g_row[0]:
                await cursor.execute("UPDATE guilds SET leader_id = ? WHERE guild_name = ?", (user_id, guild_name))

            await cursor.execute("UPDATE users SET guild = ? WHERE user_id = ?", (guild_name, user_id))
            await cursor.execute("UPDATE guilds SET members_count = members_count + 1 WHERE guild_name = ?", (guild_name,))
            await conn.commit()

    await callback.answer(f"✅ Вы успешно вступили в гильдию **{guild_name}**!", show_alert=True)
    await show_guilds_menu(callback)

@dp.callback_query(F.data == "leave_guild")
async def process_leave_guild(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT guild FROM users WHERE user_id = ?", (user_id,))
            user_row = await cursor.fetchone()
            if not user_row or user_row[0] == 'Нет':
                await callback.answer("❌ Вы нигде не состоите.", show_alert=True)
                return
            
            old_guild = user_row[0]
            
            await cursor.execute("SELECT leader_id FROM guilds WHERE guild_name = ?", (old_guild,))
            g_row = await cursor.fetchone()
            is_leader = g_row and g_row[0] == user_id

            await cursor.execute("UPDATE users SET guild = 'Нет' WHERE user_id = ?", (user_id,))
            await cursor.execute("UPDATE guilds SET members_count = MAX(0, members_count - 1) WHERE guild_name = ?", (old_guild,))
            
            if is_leader:
                await cursor.execute("SELECT user_id FROM users WHERE guild = ? LIMIT 1", (old_guild,))
                next_member = await cursor.fetchone()
                new_leader_id = next_member[0] if next_member else None
                await cursor.execute("UPDATE guilds SET leader_id = ? WHERE guild_name = ?", (new_leader_id, old_guild))

            await conn.commit()

    await callback.answer(f"🚪 Вы покинули гильдию '{old_guild}'.", show_alert=True)
    await show_guilds_menu(callback)

@dp.callback_query(F.data == "manage_kick_menu")
async def manage_kick_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT guild FROM users WHERE user_id = ?", (user_id,))
            u_row = await cursor.fetchone()
            guild_name = u_row[0] if u_row else 'Нет'
            
            await cursor.execute("SELECT leader_id FROM guilds WHERE guild_name = ?", (guild_name,))
            g_row = await cursor.fetchone()
            if not g_row or g_row[0] != user_id:
                await callback.answer("❌ Только лидер может кикать участников!", show_alert=True)
                return

            await cursor.execute("SELECT user_id, nickname FROM users WHERE guild = ? AND user_id != ?", (guild_name, user_id))
            members = await cursor.fetchall()

    kb = []
    for m_id, m_nick in members:
        kb.append([InlineKeyboardButton(text=f"👢 Кикнуть {m_nick}", callback_data=f"kick_member_{m_id}")])
    kb.append([InlineKeyboardButton(text="◀️ Назад в гильдию", callback_data="action_guilds")])

    text = "👢 **Управление участниками**\n\nВыберите игрока, которого хотите исключить из гильдии:"
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data.startswith("kick_member_"))
async def process_kick_member(callback: types.CallbackQuery):
    admin_id = callback.from_user.id
    target_id = int(callback.data.replace("kick_member_", ""))

    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT guild FROM users WHERE user_id = ?", (admin_id,))
            admin_guild = (await cursor.fetchone())[0]

            await cursor.execute("SELECT guild, nickname FROM users WHERE user_id = ?", (target_id,))
            target_row = await cursor.fetchone()

            if not target_row or target_row[0] != admin_guild:
                await callback.answer("❌ Игрок не найден в вашей гильдии.", show_alert=True)
                return

            target_nick = target_row[1]
            await cursor.execute("UPDATE users SET guild = 'Нет' WHERE user_id = ?", (target_id,))
            await cursor.execute("UPDATE guilds SET members_count = MAX(0, members_count - 1) WHERE guild_name = ?", (admin_guild,))
            await conn.commit()

    await callback.answer(f"✅ Игрок {target_nick} был исключен из гильдии.", show_alert=True)
    await show_guilds_menu(callback)


# ==================== ЦЕНТР ЗАДАНИЙ ====================
@dp.callback_query(F.data == "action_quests")
async def show_quests_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT quest_id FROM user_quests WHERE user_id = ?", (user_id,))
            completed = [r[0] for r in await cursor.fetchall()]
            
            await cursor.execute("SELECT referral_count, last_claim FROM users WHERE user_id = ?", (user_id,))
            u_row = await cursor.fetchone()
            ref_count = u_row[0] if u_row else 0
            last_claim_str = u_row[1] if u_row else None
            
            can_claim_daily = True
            if last_claim_str:
                if datetime.now() - datetime.fromisoformat(last_claim_str) < timedelta(hours=24):
                    can_claim_daily = False

            await cursor.execute("SELECT COUNT(*) FROM inventory WHERE user_id = ?", (user_id,))
            rolls_done = (await cursor.fetchone())[0]

    daily_status = "🎁 Получить (+1 крутка)" if can_claim_daily else "⏳ Через 24ч"
    ref_status = " ✅" if ref_count >= 1 or "invite_friend" in completed else f" ({ref_count}/1)"
    gacha_status = " ✅" if rolls_done >= 3 or "gacha_3" in completed else f" ({rolls_done}/3)"
    books_status = " ✅" if "books_farm_q" in completed else ""
    
    kb = [
        [InlineKeyboardButton(text=f"📅 Ежедневный вход: {daily_status}", callback_data="claim_daily")],
        [InlineKeyboardButton(text=f"🤝 Пригласи друга (+1 крутка){ref_status}", callback_data="claim_q_invite")],
        [InlineKeyboardButton(text=f"🎰 Сделай 3 крутки гачи (+1 крутка){gacha_status}", callback_data="claim_q_gacha")],
        [InlineKeyboardButton(text=f"📚 Изучи архивы 1 раз (+1 книга){books_status}", callback_data="claim_q_books")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="action_main_menu")]
    ]

    text = (
        "🎯 **Центр Заданий и Наград**\n\n"
        "Заданий немного, бонусы сбалансированы (+1 крутка/книга). Основные ресурсы получаются на старте, от рефералов или через донат-магазин!"
    )

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "claim_daily")
async def process_claim_daily(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    now = datetime.now()
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT last_claim FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            if row and row[0]:
                if now - datetime.fromisoformat(row[0]) < timedelta(hours=24):
                    await callback.answer("⏳ Награда еще не доступна!", show_alert=True)
                    return
            await cursor.execute("UPDATE users SET rolls = rolls + 1, last_claim = ? WHERE user_id = ?", (now.isoformat(), user_id))
            await conn.commit()
    await callback.answer("🎁 Получено +1 крутка за вход!", show_alert=True)
    await show_quests_menu(callback)

@dp.callback_query(F.data == "claim_q_invite")
async def quest_invite(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT 1 FROM user_quests WHERE user_id = ? AND quest_id = ?", (user_id, "invite_friend"))
            if await cursor.fetchone():
                await callback.answer("⚠️ Награда уже получена!", show_alert=True)
                return
            
            await cursor.execute("SELECT referral_count FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            if not row or row[0] < 1:
                await callback.answer("❌ Вы еще никого не пригласили!", show_alert=True)
                return
            
            await cursor.execute("INSERT INTO user_quests (user_id, quest_id) VALUES (?, ?)", (user_id, "invite_friend"))
            await cursor.execute("UPDATE users SET rolls = rolls + 1 WHERE user_id = ?", (user_id,))
            await conn.commit()
            
    await callback.answer("🎉 Начислено +1 крутка за реферала!", show_alert=True)
    await show_quests_menu(callback)

@dp.callback_query(F.data == "claim_q_gacha")
async def quest_gacha(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT 1 FROM user_quests WHERE user_id = ? AND quest_id = ?", (user_id, "gacha_3"))
            if await cursor.fetchone():
                await callback.answer("⚠️ Награда уже получена!", show_alert=True)
                return
            
            await cursor.execute("SELECT COUNT(*) FROM inventory WHERE user_id = ?", (user_id,))
            count = (await cursor.fetchone())[0]
            if count < 3:
                await callback.answer(f"❌ Нужно сделать минимум 3 крутки (у вас: {count}/3).", show_alert=True)
                return
            
            await cursor.execute("INSERT INTO user_quests (user_id, quest_id) VALUES (?, ?)", (user_id, "gacha_3"))
            await cursor.execute("UPDATE users SET rolls = rolls + 1 WHERE user_id = ?", (user_id,))
            await conn.commit()
            
    await callback.answer("🎉 Получено +1 крутка за активность!", show_alert=True)
    await show_quests_menu(callback)

@dp.callback_query(F.data == "claim_q_books")
async def quest_books(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT 1 FROM user_quests WHERE user_id = ? AND quest_id = ?", (user_id, "books_farm_q"))
            if await cursor.fetchone():
                await callback.answer("⚠️ Квест на книги уже выполнен!", show_alert=True)
                return
            
            await cursor.execute("INSERT INTO user_quests (user_id, quest_id) VALUES (?, ?)", (user_id, "books_farm_q"))
            await cursor.execute("UPDATE users SET books = books + 1 WHERE user_id = ?", (user_id,))
            await conn.commit()
            
    await callback.answer("🎉 Получена +1 книга за квест архивов!", show_alert=True)
    await show_quests_menu(callback)


# ==================== СИСТЕМА ГИЛЬД-БОССОВ ====================
@dp.callback_query(F.data == "action_guild_boss")
async def show_guild_boss_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    today_str = str(date.today())
    
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT guild FROM users WHERE user_id = ?", (user_id,))
            user_row = await cursor.fetchone()
            guild_name = user_row[0] if user_row else 'Нет'
            
            if guild_name == 'Нет' or not guild_name:
                await callback.answer("❌ Сначала вступите в гильдию!", show_alert=True)
                return
            
            await cursor.execute("SELECT boss_name, boss_hp, max_hp, killers_count, is_defeated, boss_level FROM guild_boss WHERE guild_name = ?", (guild_name,))
            boss_row = await cursor.fetchone()
            
            if not boss_row:
                b_name, b_hp, _ = get_boss_info(1)
                await cursor.execute(
                    "INSERT INTO guild_boss (guild_name, boss_name, boss_hp, max_hp, killers_count, is_defeated, boss_level) VALUES (?, ?, ?, ?, 0, 0, 1)",
                    (guild_name, b_name, b_hp, b_hp)
                )
                await conn.commit()
                boss_name, boss_hp, max_hp, killers_count, is_defeated, boss_level = b_name, b_hp, b_hp, 0, 0, 1
            else:
                boss_name, boss_hp, max_hp, killers_count, is_defeated, boss_level = boss_row

            _, _, required_hits = get_boss_info(boss_level)

    percent = max(0, min(100, int((boss_hp / max_hp) * 100)))
    bars = "█" * (percent // 10) + "░" * (10 - (percent // 10))

    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT 1 FROM guild_boss_hits WHERE user_id = ? AND guild_name = ? AND hit_date = ?", (user_id, guild_name, today_str))
            already_hit = await cursor.fetchone() is not None

    hit_btn_text = "⚔️ Нанести удар" if not already_hit else "⏳ Удар уже совершен"
    
    kb = [
        [InlineKeyboardButton(text=hit_btn_text, callback_data="hit_guild_boss")],
        [InlineKeyboardButton(text="◀️ К гильдиям", callback_data="action_guilds")]
    ]

    text = (
        f"🏰 **Рейд на Гильд-Босса** (Уровень {boss_level}/100+)\n\n"
        f"**{boss_name}**\n"
        f"Здоровье: `{boss_hp}/{max_hp}` HP\n"
        f"[{bars}] {percent}%\n\n"
        f"👥 Участники: **{killers_count} / {required_hits}**\n\n"
        "💡 *Урон учитывает ваши баффы книг и VIP-бонус донатеров!*"
    )
    if is_defeated:
        text += "\n\n🎉 **Босс повержен! Нажмите удар, чтобы призвать следующего!**"

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "hit_guild_boss")
async def process_hit_boss(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    today_str = str(date.today())
    
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT guild FROM users WHERE user_id = ?", (user_id,))
            user_row = await cursor.fetchone()
            guild_name = user_row[0] if user_row else 'Нет'
            
            if guild_name == 'Нет' or not guild_name:
                await callback.answer("❌ Вы не в гильдии!", show_alert=True)
                return
            
            await cursor.execute("SELECT 1 FROM guild_boss_hits WHERE user_id = ? AND guild_name = ? AND hit_date = ?", (user_id, guild_name, today_str))
            if await cursor.fetchone():
                await callback.answer("⏳ Вы уже атаковали сегодня!", show_alert=True)
                return
            
            await cursor.execute("SELECT extra_atk FROM user_upgrades WHERE user_id = ?", (user_id,))
            up = await cursor.fetchone()
            extra_atk = up[0] if up else 0

            await cursor.execute("SELECT is_donator FROM users WHERE user_id = ?", (user_id,))
            d_row = await cursor.fetchone()
            is_donator = d_row[0] if d_row else 0

            damage = 15 + (extra_atk // 2) + (10 if is_donator else 0)

            await cursor.execute("SELECT boss_hp, killers_count, is_defeated, boss_level, max_hp FROM guild_boss WHERE guild_name = ?", (guild_name,))
            boss_row = await cursor.fetchone()
            boss_hp, killers_count, is_defeated, boss_level, max_hp = boss_row
            _, _, required_hits = get_boss_info(boss_level)
            
            if is_defeated:
                next_level = min(100, boss_level + 1)
                next_name, next_hp, _ = get_boss_info(next_level)
                await cursor.execute(
                    "UPDATE guild_boss SET boss_name = ?, boss_hp = ?, max_hp = ?, killers_count = 0, is_defeated = 0, boss_level = ? WHERE guild_name = ?",
                    (next_name, next_hp, next_hp, next_level, guild_name)
                )
                await conn.commit()
                await callback.answer(f"🔄 Новый босс: {next_name} (Уровень {next_level})!", show_alert=True)
                await show_guild_boss_menu(callback)
                return

            new_hp = max(0, boss_hp - damage)
            new_killers = killers_count + 1
            
            await cursor.execute("INSERT INTO guild_boss_hits (user_id, guild_name, hit_date) VALUES (?, ?, ?)", (user_id, guild_name, today_str))
            
            if new_hp == 0 or new_killers >= required_hits:
                await cursor.execute("UPDATE guild_boss SET boss_hp = 0, killers_count = ?, is_defeated = 1 WHERE guild_name = ?", (required_hits, guild_name))
                await cursor.execute("UPDATE users SET rolls = rolls + 2 WHERE guild = ?", (guild_name,))
                await conn.commit()
                await callback.answer("🎉 Босс побежден! Начислено +2 крутки каждому!", show_alert=True)
                await show_guild_boss_menu(callback)
                return
            else:
                await cursor.execute("UPDATE guild_boss SET boss_hp = ?, killers_count = ? WHERE guild_name = ?", (new_hp, new_killers, guild_name))
                await conn.commit()

    await callback.answer(f"⚔️ Удар нанесен! (-{damage} HP с учетом баффов и VIP)", show_alert=True)
    await show_guild_boss_menu(callback)


# ==================== БИБЛИОТЕКА И БАФФЫ ====================
@dp.callback_query(F.data == "action_books_farm")
async def show_books_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT books FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            books = row[0] if row else 0
            
            await cursor.execute("SELECT extra_atk, extra_def, extra_mana FROM user_upgrades WHERE user_id = ?", (user_id,))
            up = await cursor.fetchone()
            atk, defs, mana = up if up else (0, 0, 0)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ Прокачать +5 Атаки (🧥 3 книги)", callback_data="upgrade_stat_atk")],
        [InlineKeyboardButton(text="🛡 Прокачать +5 Защиты (🧥 3 книги)", callback_data="upgrade_stat_def")],
        [InlineKeyboardButton(text="💧 Прокачать +5 Маны (🧥 3 книги)", callback_data="upgrade_stat_mana")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="action_main_menu")]
    ])

    text = (
        "📖 **Библиотека и Баффы Аккаунта**\n\n"
        "Используйте книги мудрости для перманентного усиления параметров вашего аккаунта.\n\n"
        f"📚 Доступно книг: `{books}` шт.\n\n"
        f"📈 Ваши баффы: Атака `+{atk}` | Защита `+{defs}` | Мана `+{mana}`"
    )
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

async def upgrade_user_stat(callback: types.CallbackQuery, stat_column: str, stat_name: str):
    user_id = callback.from_user.id
    cost = 3
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT books FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            books = row[0] if row else 0

            if books < cost:
                await callback.answer(f"❌ Нужно минимум {cost} книги для улучшения!", show_alert=True)
                return

            await cursor.execute("UPDATE users SET books = books - ? WHERE user_id = ?", (cost, user_id))
            
            await cursor.execute("SELECT 1 FROM user_upgrades WHERE user_id = ?", (user_id,))
            if not await cursor.fetchone():
                await cursor.execute("INSERT INTO user_upgrades (user_id, extra_atk, extra_def, extra_mana) VALUES (?, 0, 0, 0)", (user_id,))

            await cursor.execute(f"UPDATE user_upgrades SET {stat_column} = {stat_column} + 5 WHERE user_id = ?", (user_id,))
            await conn.commit()

    await callback.answer(f"🎉 Успешно! {stat_name} увеличена на +5 (книги списаны).", show_alert=True)
    await show_books_menu(callback)

@dp.callback_query(F.data == "upgrade_stat_atk")
async def handle_up_atk(callback: types.CallbackQuery):
    await upgrade_user_stat(callback, "extra_atk", "Атака")

@dp.callback_query(F.data == "upgrade_stat_mana")
async def handle_up_mana(callback: types.CallbackQuery):
    await upgrade_user_stat(callback, "extra_mana", "Мана")

@dp.callback_query(F.data == "upgrade_stat_def")
async def handle_up_def(callback: types.CallbackQuery):
    await upgrade_user_stat(callback, "extra_def", "Защита")


# ==================== ЗАПУСК БОТА ====================
async def main():
    await init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Бот запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
if __name__ == "__main__":
    asyncio.run(main())
    asyncio.run(main())
