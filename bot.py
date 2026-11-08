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

# ==================== ЗАГЛУШКА ДЛЯ RENDER ====================
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

# Запускаем сервер параллельно с ботом для поддержания активности на Render
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
                    rolls INTEGER DEFAULT 5,
                    books INTEGER DEFAULT 5,
                    rating INTEGER DEFAULT 1000,
                    guild TEXT DEFAULT 'Нет',
                    invited_by INTEGER DEFAULT NULL,
                    referral_count INTEGER DEFAULT 0,
                    last_claim TEXT
                )
            """)
            
            for col, col_type in [("invited_by", "INTEGER"), ("referral_count", "INTEGER DEFAULT 0"), ("last_claim", "TEXT")]:
                try:
                    await cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")
                except Exception:
                    pass
            
            # Инвентарь хранит ВСЕХ персонажей игрока навсегда
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
            
            # PvP колода хранит только ссылки (ID) на карты из инвентаря
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS pvp_deck (
                    user_id INTEGER,
                    card_id INTEGER
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
                    members_count INTEGER DEFAULT 1
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
            InlineKeyboardButton(text="🤝 Рефералы", callback_data="action_referral")
        ],
        [
            InlineKeyboardButton(text="🎯 Задания / Фарм", callback_data="action_quests"),
            InlineKeyboardButton(text="📚 Библиотека (Книги)", callback_data="action_books_farm")
        ]
    ])


# ==================== СТАРТ И ГЛАВНОЕ МЕНЮ ====================
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
            await cursor.execute("SELECT user_id, rolls FROM users WHERE user_id = ?", (user_id,))
            user = await cursor.fetchone()

            if not user:
                actual_inviter = inviter_id if (inviter_id and inviter_id != user_id) else None
                if actual_inviter:
                    await cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (actual_inviter,))
                    if await cursor.fetchone():
                        await cursor.execute(
                            "INSERT INTO users (user_id, rolls, books, rating, guild, invited_by) VALUES (?, 7, 5, 1000, 'Нет', ?)",
                            (user_id, actual_inviter)
                        )
                        await cursor.execute("UPDATE users SET referral_count = referral_count + 1, rolls = rolls + 2 WHERE user_id = ?", (actual_inviter,))
                    else:
                        await cursor.execute("INSERT INTO users (user_id, rolls, books, rating, guild) VALUES (?, 5, 5, 1000, 'Нет')", (user_id,))
                else:
                    await cursor.execute("INSERT INTO users (user_id, rolls, books, rating, guild) VALUES (?, 5, 5, 1000, 'Нет')", (user_id,))
                await conn.commit()

    text = (
        "✨ **Добро пожаловать в Аниме Гачу!** ✨\n\n"
        "Собирайте редких персонажей, вступайте в гильдии, сражайтесь с боссами и прокачивайте свой отряд!"
    )
    await message.answer(text, reply_markup=get_main_keyboard(), parse_mode="Markdown")

@dp.callback_query(F.data == "action_main_menu")
async def back_to_main_menu(callback: types.CallbackQuery):
    text = "🏠 **Главное меню:**"
    await callback.message.edit_text(text, reply_markup=get_main_keyboard(), parse_mode="Markdown")
    await callback.answer()


# ==================== ПРОФИЛЬ И РЕФЕРАЛЫ ====================
@dp.callback_query(F.data == "action_profile")
async def show_profile(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT rolls, books, rating, guild, referral_count FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            rolls, books, rating, guild, ref_count = row if row else (0, 0, 1000, 'Нет', 0)
            
            await cursor.execute("SELECT COUNT(*) FROM inventory WHERE user_id = ?", (user_id,))
            inv_count = (await cursor.fetchone())[0]

            await cursor.execute("SELECT extra_atk, extra_def, extra_mana FROM user_upgrades WHERE user_id = ?", (user_id,))
            up = await cursor.fetchone()
            atk, defs, mana = up if up else (0, 0, 0)

    text = (
        f"👤 **Ваш профиль:**\n\n"
        f"🎫 Крутки: `{rolls}`\n"
        f"📚 Книги: `{books}`\n"
        f"🏆 Рейтинг: `{rating}`\n"
        f"🏰 Гильдия: `{guild}`\n"
        f"📦 Карток в инвентаре: `{inv_count}`\n"
        f"👥 Приглашено друзей: `{ref_count}`\n\n"
        f"📈 **Бонусы статов:** Атака +{atk} | Защита +{defs} | Мана +{mana}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="action_main_menu")]])
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
        "• Другу бонус: +7 круток 🎁\n\n"
        f"👥 Приглашено: `{ref_count}`\n\n"
        f"🔗 Ссылка:\n`{ref_link}`"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="action_main_menu")]])
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
            
            await cursor.execute("SELECT guild_name, members_count FROM guilds")
            guilds = await cursor.fetchall()

    keyboard_builder = []
    if user_guild != 'Нет':
        text = f"🏰 **Ваша гильдия:** `{user_guild}`\n\nДоступные функции:"
        keyboard_builder.append([InlineKeyboardButton(text="🐉 Гильд-босс (Рейд)", callback_data="action_guild_boss")])
    else:
        text = "🏰 **Список гильдий**\n\nВыберите гильдию для вступления:"

    if guilds:
        for g_name, count in guilds:
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
                if user_row[0] == guild_name:
                    await callback.answer("⚠️ Вы уже в этой гильдии!", show_alert=True)
                else:
                    await callback.answer(f"❌ Вы уже состоите в гильдии '{user_row[0]}'.", show_alert=True)
                return
            
            await cursor.execute("SELECT guild_name FROM guilds WHERE guild_name = ?", (guild_name,))
            if not await cursor.fetchone():
                await callback.answer("❌ Такой гильдии не существует.", show_alert=True)
                return
            
            await cursor.execute("UPDATE users SET guild = ? WHERE user_id = ?", (guild_name, user_id))
            await cursor.execute("UPDATE guilds SET members_count = members_count + 1 WHERE guild_name = ?", (guild_name,))
            await conn.commit()

    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏰 К гильдиям", callback_data="action_guilds")]])
    await callback.message.edit_text(f"✅ Вы успешно вступили в гильдию **{guild_name}**!", reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


# ==================== ЦЕНТР ЗАДАНИЙ И НАГРАД ====================
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

    daily_status = "🎁 Получить (+3)" if can_claim_daily else "⏳ Через 24ч"
    ref_status = " ✅" if ref_count >= 1 or "invite_friend" in completed else f" ({ref_count}/1)"
    gacha_status = " ✅" if rolls_done >= 5 or "gacha_5" in completed else f" ({rolls_done}/5)"
    
    kb = [
        [InlineKeyboardButton(text=f"📅 Ежедневная награда: {daily_status}", callback_data="claim_daily")],
        [InlineKeyboardButton(text=f"🤝 Пригласи друга (+2 крутки){ref_status}", callback_data="claim_q_invite")],
        [InlineKeyboardButton(text=f"🎰 Сделай 5 круток гачи (+3 крутки){gacha_status}", callback_data="claim_q_gacha")],
        [InlineKeyboardButton(text="📚 Изучи архивы 3 раза (+2 книги)" + (" ✅" if "books_3" in completed else ""), callback_data="claim_q_books")],
        [InlineKeyboardButton(text="🛡 Вступи в гильдию (+2 крутки)" + (" ✅" if "join_guild_q" in completed else ""), callback_data="claim_q_guild")],
        [InlineKeyboardButton(text="🐉 Ударь гильд-босса (+2 крутки)" + (" ✅" if "boss_hit_q" in completed else ""), callback_data="claim_q_boss")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="action_main_menu")]
    ]

    text = (
        "🎯 **Центр Заданий и Наград**\n\n"
        "Выполняйте активности, объединяйтесь с игроками и получайте ресурсы бесплатно, либо ждите обновления таймеров!\n\n"
        "💡 *Хотите всё и сразу? Поддержите проект донатом или ускорьте прогресс друзей.*"
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
            await cursor.execute("UPDATE users SET rolls = rolls + 3, last_claim = ? WHERE user_id = ?", (now.isoformat(), user_id))
            await conn.commit()
    await callback.answer("🎁 Получено +3 крутки!", show_alert=True)
    await show_quests_menu(callback)

@dp.callback_query(F.data == "claim_q_invite")
async def quest_invite(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT 1 FROM user_quests WHERE user_id = ? AND quest_id = ?", (user_id, "invite_friend"))
            if await cursor.fetchone():
                await callback.answer("⚠️ Награда за это задание уже получена!", show_alert=True)
                return
            
            await cursor.execute("SELECT referral_count FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            if not row or row[0] < 1:
                await callback.answer("❌ Вы еще никого не пригласили! Ссылка в разделе 'Рефералы'.", show_alert=True)
                return
            
            await cursor.execute("INSERT INTO user_quests (user_id, quest_id) VALUES (?, ?)", (user_id, "invite_friend"))
            await cursor.execute("UPDATE users SET rolls = rolls + 2 WHERE user_id = ?", (user_id,))
            await conn.commit()
            
    await callback.answer("🎉 Задание выполнено! Начислено +2 крутки!", show_alert=True)
    await show_quests_menu(callback)

@dp.callback_query(F.data == "claim_q_gacha")
async def quest_gacha(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT 1 FROM user_quests WHERE user_id = ? AND quest_id = ?", (user_id, "gacha_5"))
            if await cursor.fetchone():
                await callback.answer("⚠️ Награда уже получена!", show_alert=True)
                return
            
            await cursor.execute("SELECT COUNT(*) FROM inventory WHERE user_id = ?", (user_id,))
            count = (await cursor.fetchone())[0]
            if count < 5:
                await callback.answer(f"❌ Нужно сделать минимум 5 круток (у вас: {count}/5).", show_alert=True)
                return
            
            await cursor.execute("INSERT INTO user_quests (user_id, quest_id) VALUES (?, ?)", (user_id, "gacha_5"))
            await cursor.execute("UPDATE users SET rolls = rolls + 3 WHERE user_id = ?", (user_id,))
            await conn.commit()
            
    await callback.answer("🎉 Отлично! Получено +3 крутки за активность в гаче!", show_alert=True)
    await show_quests_menu(callback)

@dp.callback_query(F.data == "claim_q_guild")
async def quest_guild(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT 1 FROM user_quests WHERE user_id = ? AND quest_id = ?", (user_id, "join_guild_q"))
            if await cursor.fetchone():
                await callback.answer("⚠️ Награда уже получена!", show_alert=True)
                return
            
            await cursor.execute("SELECT guild FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            if not row or row[0] == 'Нет':
                await callback.answer("❌ Сначала вступите в любую гильдию!", show_alert=True)
                return
            
            await cursor.execute("INSERT INTO user_quests (user_id, quest_id) VALUES (?, ?)", (user_id, "join_guild_q"))
            await cursor.execute("UPDATE users SET rolls = rolls + 2 WHERE user_id = ?", (user_id,))
            await conn.commit()
            
    await callback.answer("🎉 Вы в гильдии! Начислено +2 крутки!", show_alert=True)
    await show_quests_menu(callback)

@dp.callback_query(F.data == "claim_q_boss")
async def quest_boss_hit(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT 1 FROM user_quests WHERE user_id = ? AND quest_id = ?", (user_id, "boss_hit_q"))
            if await cursor.fetchone():
                await callback.answer("⚠️ Награда за этот квест уже получена!", show_alert=True)
                return
            
            await cursor.execute("SELECT guild FROM users WHERE user_id = ?", (user_id,))
            u_row = await cursor.fetchone()
            guild_name = u_row[0] if u_row else 'Нет'
            
            if guild_name == 'Нет':
                await callback.answer("❌ Вы не состоите в гильдии.", show_alert=True)
                return
                
            await cursor.execute("SELECT 1 FROM guild_boss_hits WHERE user_id = ? AND guild_name = ?", (user_id, guild_name))
            if not await cursor.fetchone():
                await callback.answer("❌ Вы еще не ударили гильд-босса сегодня!", show_alert=True)
                return
            
            await cursor.execute("INSERT INTO user_quests (user_id, quest_id) VALUES (?, ?)", (user_id, "boss_hit_q"))
            await cursor.execute("UPDATE users SET rolls = rolls + 2 WHERE user_id = ?", (user_id,))
            await conn.commit()
            
    await callback.answer("🎉 Удар по боссу зачтен! Получено +2 крутки!", show_alert=True)
    await show_quests_menu(callback)


# ==================== СИСТЕМА 100+ ГИЛЬД-БОССОВ ====================
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

    hit_btn_text = "⚔️ Нанести удар (+1)" if not already_hit else "⏳ Удар уже совершен"
    
    kb = [
        [InlineKeyboardButton(text=hit_btn_text, callback_data="hit_guild_boss")],
        [InlineKeyboardButton(text="◀️ К списку гильдий", callback_data="action_guilds")]
    ]

    text = (
        f"🏰 **Рейд на Гильд-Босса** (Уровень {boss_level}/100+)\n\n"
        f"**{boss_name}**\n"
        f"Здоровье: `{boss_hp}/{max_hp}` HP\n"
        f"[{bars}] {percent}%\n\n"
        f"👥 Участники: **{killers_count} / {required_hits}**\n\n"
        "💡 *Побеждайте боссов совместными силами и получайте по +2 крутки!*"
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

            damage = 15
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

    await callback.answer(f"⚔️ Удар нанесен! (-{damage} HP)", show_alert=True)
    await show_guild_boss_menu(callback)


# ==================== БИБЛИОТЕКА И ПРОКАЧКА СТАТОВ ЗА КНИГИ ====================
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
        [InlineKeyboardButton(text="📚 Изучать архивы (Фарм книг)", callback_data="farm_books_action")],
        [InlineKeyboardButton(text="⚔️ Прокачать +5 Атаки (🧥 3 книги)", callback_data="upgrade_stat_atk")],
        [InlineKeyboardButton(text="🛡 Прокачать +5 Защиты (🧥 3 книги)", callback_data="upgrade_stat_def")],
        [InlineKeyboardButton(text="💧 Прокачать +5 Маны (🧥 3 книги)", callback_data="upgrade_stat_mana")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="action_main_menu")]
    ])

    text = (
        "📖 **Библиотека и Академия Навыков**\n\n"
        f"📚 Книги мудрости: `{books}` шт.\n\n"
        f"📈 Улучшения: Атака `+{atk}` | Защита `+{defs}` | Мана `+{mana}`"
    )
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "farm_books_action")
async def process_farm_books(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    found = random.randint(1, 3)
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("UPDATE users SET books = books + ? WHERE user_id = ?", (found, user_id))
            await conn.commit()
    await callback.answer(f"📚 Найдено книг: +{found}!", show_alert=True)
    await show_books_menu(callback)

async def upgrade_user_stat(callback: types.CallbackQuery, stat_column: str, stat_name: str):
    user_id = callback.from_user.id
    cost = 3
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT books FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            books = row[0] if row else 0

            if books < cost:
                await callback.answer(f"❌ Нужно минимум {cost} книги!", show_alert=True)
                return

            await cursor.execute("UPDATE users SET books = books - ? WHERE user_id = ?", (cost, user_id))
            await cursor.execute("SELECT 1 FROM user_upgrades WHERE user_id = ?", (user_id,))
            if not await cursor.fetchone():
                await cursor.execute("INSERT INTO user_upgrades (user_id, extra_atk, extra_def, extra_mana) VALUES (?, 0, 0, 0)", (user_id,))

            await cursor.execute(f"UPDATE user_upgrades SET {stat_column} = {stat_column} + 5 WHERE user_id = ?", (user_id,))
            await conn.commit()

    await callback.answer(f"🎉 {stat_name} увеличена на +5!", show_alert=True)
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
    logging.info("Бот запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

if __name__ == "__main__":
    asyncio.run(main())
