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
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice

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

# Пулы персонажей с рангами S, A, B, C, D
ICARDS_POOL = [
    {"name": "Наруто Узумаки", "anime": "Naruto", "rarity": "S", "class": "Боец"},
    {"name": "Саске Учиха", "anime": "Naruto", "rarity": "S", "class": "Убийца"},
    {"name": "Луффи", "anime": "One Piece", "rarity": "A", "class": "Боец"},
    {"name": "Зоро", "anime": "One Piece", "rarity": "B", "class": "Воин"},
    {"name": "Танджиро Камадо", "anime": "Kimetsu no Yaiba", "rarity": "C", "class": "Мечник"},
    {"name": "Сакура Харуно", "anime": "Naruto", "rarity": "D", "class": "Медик"}
]

SS_CARDS_POOL = [
    {"name": "Гоку", "anime": "Dragon Ball", "rarity": "S", "class": "Легенда"},
    {"name": "Сатору Годжо", "anime": "Jujutsu Kaisen", "rarity": "S", "class": "Маг"}
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

BOT_NAMES = [
    ("Теневой Ассасин 🥷", 1050),
    ("Берсерк Пустоши ⚔️", 1100),
    ("Магический Страж 🔮", 1150),
    ("Элитный Киборг 🤖", 1200),
    ("Повелитель Марионеток 🎭", 1250)
]

def get_boss_info(level: int):
    title_idx = (level - 1) % len(BOSS_TITLES)
    base_name, emoji = BOSS_TITLES[title_idx]
    suffix = f" [Уровень {level}]" if level <= 10 else f" [Элитный V-{level}]"
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
            
            columns = [
                ("nickname", "TEXT DEFAULT NULL"),
                ("rolls", "INTEGER DEFAULT 5"),
                ("books", "INTEGER DEFAULT 5"),
                ("rating", "INTEGER DEFAULT 1000"),
                ("guild", "TEXT DEFAULT 'Нет'"),
                ("invited_by", "INTEGER DEFAULT NULL"),
                ("referral_count", "INTEGER DEFAULT 0"),
                ("last_claim", "TEXT"),
                ("is_donator", "INTEGER DEFAULT 0")
            ]
            for col_name, col_type in columns:
                try:
                    await cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
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
                CREATE TABLE IF NOT EXISTS user_deck (
                    user_id INTEGER,
                    slot_num INTEGER,
                    card_id INTEGER,
                    PRIMARY KEY (user_id, slot_num)
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
                    members_count INTEGER DEFAULT 0,
                    total_bosses_defeated INTEGER DEFAULT 0
                )
            """)
            
            try:
                await cursor.execute("ALTER TABLE guilds ADD COLUMN total_bosses_defeated INTEGER DEFAULT 0")
            except Exception:
                pass

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
                await cursor.executemany("INSERT INTO guilds (guild_name, members_count, total_bosses_defeated) VALUES (?, ?, ?)", [
                    ("Акацуки", 0, 0),
                    ("Убийцы Драконов", 0, 0),
                    ("Стражи Галактики", 0, 0)
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
            InlineKeyboardButton(text="📦 Инвентарь & Колода (5 мест)", callback_data="action_inventory"),
            InlineKeyboardButton(text="⚔️ Арена (PvP)", callback_data="action_arena")
        ],
        [
            InlineKeyboardButton(text="🏰 Гильдии", callback_data="action_guilds"),
            InlineKeyboardButton(text="🏆 Топ гильдий", callback_data="action_guilds_top")
        ],
        [
            InlineKeyboardButton(text="🎯 Задания", callback_data="action_quests"),
            InlineKeyboardButton(text="📚 Библиотека", callback_data="action_books_farm")
        ],
        [
            InlineKeyboardButton(text="⭐ Магазин Звезд", callback_data="action_donate_shop")
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
        "Собирайте бойцов рангов S-D, соберите колоду из 5 карт и побеждайте на Арене!"
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
        "Отправьте в чат команду вместе с вашим новым ником:\n"
        "`/setnick МоеИмя`"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ В профиль", callback_data="action_profile")]])
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


# ==================== ИНВЕНТАРЬ И КОЛОДА ИЗ 5 КАРТ ====================
@dp.callback_query(F.data == "action_inventory")
async def show_inventory(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
                SELECT id, character_name, tier, atk, def, hp, mana 
                FROM inventory 
                WHERE user_id = ? 
                ORDER BY 
                    CASE tier 
                        WHEN 'S' THEN 1 
                        WHEN 'A' THEN 2 
                        WHEN 'B' THEN 3 
                        WHEN 'C' THEN 4 
                        WHEN 'D' THEN 5 
                        ELSE 6 
                    END ASC, 
                    (atk + def + hp + mana) DESC
            """, (user_id,))
            cards = await cursor.fetchall()

    if not cards:
        text = "📦 **Ваш инвентарь пуст.**\n\nИспользуйте крутки в разделе «🎰 Крутить гачу»!"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎰 Крутить гачу", callback_data="action_roll")],
            [InlineKeyboardButton(text="◀️ Назад в профиль", callback_data="action_profile")]
        ])
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        await callback.answer()
        return

    text = "📦 **Ваша коллекция (ранги S-D):**\nВыберите карточку для назначения в **5 слотов колоды** ⚔️\n\n"
    for idx, (c_id, c_name, c_tier, c_atk, c_def, c_hp, c_mana) in enumerate(cards[:10], 1):
        text += f"{idx}. **{c_name}** (`Ранг {c_tier}`)\n   ⚔️ {c_atk} | 🛡 {c_def} | ❤️ {c_hp} | 💧 {c_mana}\n\n"

    kb_buttons = []
    for c_id, c_name, c_tier, _, _, _, _ in cards[:6]:
        kb_buttons.append([InlineKeyboardButton(text=f"📌 В колоду [Ранг {c_tier}]: {c_name}", callback_data=f"pick_slot_{c_id}")])

    kb_buttons.append([InlineKeyboardButton(text="🛡 Посмотреть мою колоду (5 карт)", callback_data="view_my_deck")])
    kb_buttons.append([InlineKeyboardButton(text="◀️ Назад в профиль", callback_data="action_profile")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data.startswith("pick_slot_"))
async def pick_slot_for_card(callback: types.CallbackQuery):
    card_id = int(callback.data.replace("pick_slot_", ""))
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Слот 1 🥇", callback_data=f"assign_deck_{card_id}_1"),
         InlineKeyboardButton(text="Слот 2 🥈", callback_data=f"assign_deck_{card_id}_2")],
        [InlineKeyboardButton(text="Слот 3 🥉", callback_data=f"assign_deck_{card_id}_3"),
         InlineKeyboardButton(text="Слот 4 🏅", callback_data=f"assign_deck_{card_id}_4")],
        [InlineKeyboardButton(text="Слот 5 🎖", callback_data=f"assign_deck_{card_id}_5")],
        [InlineKeyboardButton(text="◀️ К инвентарю", callback_data="action_inventory")]
    ])
    await callback.message.edit_text("🎯 **Выберите слот для карточки в колоде (от 1 до 5):**", reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data.startswith("assign_deck_"))
async def assign_card_to_slot(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    parts = callback.data.split("_")
    card_id = int(parts[2])
    slot_num = int(parts[3])

    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT character_name, tier FROM inventory WHERE id = ? AND user_id = ?", (card_id, user_id))
            card = await cursor.fetchone()
            if not card:
                await callback.answer("❌ Карточка не найдена!", show_alert=True)
                return
            c_name, c_tier = card

            await cursor.execute("""
                INSERT INTO user_deck (user_id, slot_num, card_id) VALUES (?, ?, ?)
                ON CONFLICT(user_id, slot_num) DO UPDATE SET card_id = ?
            """, (user_id, slot_num, card_id, card_id))
            await conn.commit()

    await callback.answer(f"✅ Успешно! [{c_tier}] {c_name} в слоте №{slot_num}.", show_alert=True)
    await show_inventory(callback)

@dp.callback_query(F.data == "view_my_deck")
async def view_my_deck(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
                SELECT d.slot_num, i.character_name, i.tier, i.atk, i.def, i.hp, i.mana
                FROM user_deck d
                JOIN inventory i ON d.card_id = i.id
                WHERE d.user_id = ?
                ORDER BY d.slot_num ASC
            """, (user_id,))
            deck_cards = await cursor.fetchall()

    text = "🛡 **Ваша боевая колода (5 слотов):**\n\n"
    if not deck_cards:
        text += "Колода пока пуста. Выберите карты из инвентаря!"
    else:
        for slot, name, tier, atk, defs, hp, mana in deck_cards:
            text += f"🔹 **Слот {slot}**: [{tier}] {name}\n   ⚔️ АТК: {atk} | 🛡 ЗАЩ: {defs} | ❤️ HP: {hp}\n\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ К инвентарю", callback_data="action_inventory")]])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


# ==================== ПРОФИЛЬ ====================
@dp.callback_query(F.data == "action_profile")
async def show_profile(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT nickname, books, rating, guild, referral_count, is_donator, rolls FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            nick, books, rating, guild, ref_count, is_donator, rolls = row if row else ("Герой", 0, 1000, 'Нет', 0, 0, 0)
            
            await cursor.execute("SELECT COUNT(*) FROM inventory WHERE user_id = ?", (user_id,))
            inv_count = (await cursor.fetchone())[0]

            await cursor.execute("SELECT COUNT(*) FROM user_deck WHERE user_id = ?", (user_id,))
            deck_count = (await cursor.fetchone())[0]

            await cursor.execute("SELECT extra_atk, extra_def, extra_mana FROM user_upgrades WHERE user_id = ?", (user_id,))
            up = await cursor.fetchone()
            atk, defs, mana = up if up else (0, 0, 0)

    vip_badge = " ⭐ [VIP-Донатер]" if is_donator else ""

    text = (
        f"👤 **Профиль: {nick}**{vip_badge}\n\n"
        f"🛡 **Колода:** заполнено слотов `{deck_count}/5`\n"
        f"🎫 Доступно круток: `{rolls}` шт.\n"
        f"📚 Книги баффов: `{books}` шт.\n"
        f"🏆 Рейтинг PvP: `{rating}` PTS\n"
        f"🏰 Гильдия: `{guild}`\n"
        f"📦 Карток в инвентаре: `{inv_count}` шт.\n\n"
        f"📈 **Бонусы статов:** Атака +{atk} | Защита +{defs} | Мана +{mana}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📦 Инвентарь & Колода", callback_data="action_inventory"),
            InlineKeyboardButton(text="✏️ Сменить ник", callback_data="action_change_nick")
        ],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="action_main_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


# ==================== ТОП ГИЛЬДИЙ ПО СУММАРНОЙ СИЛЕ ====================
@dp.callback_query(F.data == "action_guilds_top")
async def show_guilds_top(callback: types.CallbackQuery):
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT guild_name, total_bosses_defeated FROM guilds")
            guilds = await cursor.fetchall()
            
            guild_leaderboard = []
            for g_name, b_defeated in guilds:
                await cursor.execute("SELECT user_id, is_donator FROM users WHERE guild = ?", (g_name,))
                members = await cursor.fetchall()
                
                total_guild_power = 0
                for u_id, is_don in members:
                    await cursor.execute("SELECT SUM(atk + def + hp + mana) FROM inventory WHERE user_id = ?", (u_id,))
                    cards_sum = (await cursor.fetchone())[0] or 0
                    
                    await cursor.execute("SELECT extra_atk, extra_def, extra_mana FROM user_upgrades WHERE user_id = ?", (u_id,))
                    up = await cursor.fetchone()
                    books_bonus = (sum(up) * 10) if up else 0
                    
                    vip_bonus = 150 if is_don else 0
                    total_guild_power += (cards_sum + books_bonus + vip_bonus)
                
                asta_rank = "Обычный"
                if b_defeated >= 100:
                    asta_rank = "🔥 SS Аста"
                elif b_defeated >= 50:
                    asta_rank = "⭐ Аста"
                
                guild_leaderboard.append((g_name, total_guild_power, len(members), b_defeated, asta_rank))
            
            guild_leaderboard.sort(key=lambda x: x[1], reverse=True)

    top_text = "🏆 **Рейтинг и Сила Гильдий** 🏆\n\n"
    for idx, (g_name, power, members_count, b_defeated, asta) in enumerate(guild_leaderboard, 1):
        medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"{idx}."
        top_text += (
            f"{medal} **{g_name}**\n"
            f"   ⚡ Суммарная сила: `{power}`\n"
            f"   👥 Участников: `{members_count}` | 🐉 Боссов побеждено: `{b_defeated}`\n"
            f"   🎁 Статус: [{asta}]\n\n"
        )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏰 Меню гильдий", callback_data="action_guilds")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="action_main_menu")]
    ])
    await callback.message.edit_text(top_text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


# ==================== АРЕНА (ПРЕДБОЕВОЕ СРАВНЕНИЕ КОЛОД) ====================
@dp.callback_query(F.data == "action_arena")
async def show_arena(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT rating FROM users WHERE user_id = ?", (user_id,))
            rating = (await cursor.fetchone())[0]

            await cursor.execute("SELECT user_id, nickname, rating, is_donator FROM users WHERE user_id != ? ORDER BY RANDOM() LIMIT 1", (user_id,))
            opp = await cursor.fetchone()

    if opp:
        opp_id, opp_nick, opp_rating, opp_don = opp
        opp_vip = " ⭐" if opp_don else ""
        target_callback = f"preview_player_{opp_id}"
    else:
        b_name, b_rating = random.choice(BOT_NAMES)
        opp_nick = b_name
        opp_rating = b_rating + random.randint(-20, 20)
        opp_vip = " 🤖"
        target_callback = f"preview_bot_{opp_rating}_{opp_nick.replace(' ', '_')}"

    text = (
        f"⚔️ **PvP Арена**\n\n"
        f"Ваш рейтинг: `{rating}` PTS\n\n"
        f"🎯 **Найден соперник:** {opp_nick}{opp_vip} (`{opp_rating}` PTS)\n"
        f"💡 *Нажмите «Посмотреть составы и в бой», чтобы изучить колоду соперника перед схваткой!*"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🔍 Посмотреть составы и в бой", callback_data=target_callback)],
        [InlineKeyboardButton(text="🔄 Найти другого", callback_data="action_arena")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="action_main_menu")]
    ])

    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

# --- ПРЕДБОЕВОЙ ЭКРАН СРАВНЕНИЯ (ИГРОК) ---
@dp.callback_query(F.data.startswith("preview_player_"))
async def preview_player_fight(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    opp_id = int(callback.data.replace("preview_player_", ""))

    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT nickname FROM users WHERE user_id = ?", (user_id,))
            u1_nick = (await cursor.fetchone())[0]
            await cursor.execute("SELECT i.character_name, i.tier, i.atk, i.def, i.hp FROM user_deck d JOIN inventory i ON d.card_id = i.id WHERE d.user_id = ?", (user_id,))
            u1_cards = await cursor.fetchall()
            await cursor.execute("SELECT extra_atk, extra_def, extra_mana FROM user_upgrades WHERE user_id = ?", (user_id,))
            u1_up = await cursor.fetchone()
            u1_books = sum(u1_up) * 5 if u1_up else 0

            await cursor.execute("SELECT nickname FROM users WHERE user_id = ?", (opp_id,))
            u2_nick = (await cursor.fetchone())[0]
            await cursor.execute("SELECT i.character_name, i.tier, i.atk, i.def, i.hp FROM user_deck d JOIN inventory i ON d.card_id = i.id WHERE d.user_id = ?", (opp_id,))
            u2_cards = await cursor.fetchall()
            await cursor.execute("SELECT extra_atk, extra_def, extra_mana FROM user_upgrades WHERE user_id = ?", (opp_id,))
            u2_up = await cursor.fetchone()
            u2_books = sum(u2_up) * 5 if u2_up else 0

    u1_cards_str = "\n".join([f"• [{c[1]}] {c[0]} (⚔️{c[2]} 🛡{c[3]} ❤️{c[4]})" for c in u1_cards]) or "• Пустая колода (база 40)"
    u2_cards_str = "\n".join([f"• [{c[1]}] {c[0]} (⚔️{c[2]} 🛡{c[3]} ❤️{c[4]})" for c in u2_cards]) or "• Стандартный набор"

    text = (
        f"📊 **ПРЕДБОЕВОЙ АНАЛИЗ СОСТАВОВ** 📊\n\n"
        f"👤 **Ваш отряд ({u1_nick}):**\n{u1_cards_str}\n"
        f"📚 Баффы книг мудрости: `+{u1_books}`\n\n"
        f"⚔️ **Отряд противника ({u2_nick}):**\n{u2_cards_str}\n"
        f"📚 Баффы книг противника: `+{u2_books}`\n\n"
        f"👇 *Нажмите кнопку ниже, чтобы начать симуляцию боя!*"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ СРАЗИТЬСЯ С ЭТИМ СОСТАВОМ!", callback_data=f"exec_player_{opp_id}")],
        [InlineKeyboardButton(text="◀️ Назад на арену", callback_data="action_arena")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

SyntaxError: closing parenthesis ')' does not match opening parenthesis '[' on line 643[cite: 3]
```[cite: 3]

В функции предбоевого экрана для бота (где создается клавиатура `kb = InlineKeyboardMarkup(...)`) в конце списка снова перепутаны закрывающие скобки. 

Вот этот точный фрагмент функции `preview_bot_fight` (примерно 630–650 строки). Замени у себя в `bot.py` всю эту функцию целиком на этот рабочий вариант:

```python
# --- ПРЕДБОЕВОЙ ЭКРАН СРАВНЕНИЯ (БОТ) ---
@dp.callback_query(F.data.startswith("preview_bot_"))
async def preview_bot_fight(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    parts = callback.data.split("_")
    bot_rating = int(parts[2])
    bot_name = parts[3].replace("_", " ")

    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT nickname FROM users WHERE user_id = ?", (user_id,))
            u1_nick = (await cursor.fetchone())[0]
            await cursor.execute("SELECT i.character_name, i.tier, i.atk, i.def, i.hp FROM user_deck d JOIN inventory i ON d.card_id = i.id WHERE d.user_id = ?", (user_id,))
            u1_cards = await cursor.fetchall()
            await cursor.execute("SELECT extra_atk, extra_def, extra_mana FROM user_upgrades WHERE user_id = ?", (user_id,))
            u1_up = await cursor.fetchone()
            u1_books = sum(u1_up) * 5 if u1_up else 0

    u1_cards_str = "\n".join([f"• [{c[1]}] {c[0]} (⚔️{c[2]} 🛡{c[3]} ❤️{c[4]})" for c in u1_cards]) or "• Пустая колода"

    text = (
        f"📊 **ПРЕДБОЕВОЙ АНАЛИЗ СОСТАВОВ** 📊\n\n"
        f"👤 **Ваш отряд ({u1_nick}):**\n{u1_cards_str}\n"
        f"📚 Баффы книг мудрости: `+{u1_books}`\n\n"
        f"🤖 **Боевой ИИ противника ({bot_name}):**\n"
        f"• Элитный босс арены (Сила соразмерна рейтингу `{bot_rating}` PTS)\n\n"
        f"👇 *Нажмите кнопку ниже, чтобы начать схватку!*"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ СРАЗИТЬСЯ С БОТОМ!", callback_data=f"exec_bot_{bot_rating}_{bot_name.replace(' ', '_')}")],
        [InlineKeyboardButton(text="◀️ Назад на арену", callback_data="action_arena")]
    ]]
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

# --- СИМУЛЯЦИЯ И РЕЗУЛЬТАТ (ИГРОК) ---
@dp.callback_query(F.data.startswith("exec_player_"))
async def process_pvp_fight(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    opp_id = int(callback.data.replace("exec_player_", ""))

    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT nickname, is_donator FROM users WHERE user_id = ?", (user_id,))
            u1_nick, u1_don = await cursor.fetchone()

            await cursor.execute("SELECT SUM(atk + def + hp + mana) FROM user_deck d JOIN inventory i ON d.card_id = i.id WHERE d.user_id = ?", (user_id,))
            deck_sum = (await cursor.fetchone())[0]
            u1_cards_power = deck_sum if deck_sum else 40

            await cursor.execute("SELECT extra_atk, extra_def, extra_mana FROM user_upgrades WHERE user_id = ?", (user_id,))
            u1_up = await cursor.fetchone()
            u1_books_bonus = sum(u1_up) * 10 if u1_up else 0
            u1_total_power = u1_cards_power + u1_books_bonus + (150 if u1_don else 0)

            await cursor.execute("SELECT nickname, is_donator FROM users WHERE user_id = ?", (opp_id,))
            u2_nick, u2_don = await cursor.fetchone()

            await cursor.execute("SELECT SUM(atk + def + hp + mana) FROM user_deck d JOIN inventory i ON d.card_id = i.id WHERE d.user_id = ?", (opp_id,))
            deck_sum_2 = (await cursor.fetchone())[0]
            u2_cards_power = deck_sum_2 if deck_sum_2 else 40

            await cursor.execute("SELECT extra_atk, extra_def, extra_mana FROM user_upgrades WHERE user_id = ?", (opp_id,))
            u2_up = await cursor.fetchone()
            u2_books_bonus = sum(u2_up) * 10 if u2_up else 0
            u2_total_power = u2_cards_power + u2_books_bonus + (150 if u2_don else 0)

            u1_score = u1_total_power + random.randint(0, 100)
            u2_score = u2_total_power + random.randint(0, 100)

            if u1_score >= u2_score:
                win = True
                await cursor.execute("UPDATE users SET rating = rating + 25 WHERE user_id = ?", (user_id,))
                await cursor.execute("UPDATE users SET rating = MAX(0, rating - 15) WHERE user_id = ?", (opp_id,))
            else:
                win = False
                await cursor.execute("UPDATE users SET rating = MAX(0, rating - 15) WHERE user_id = ?", (user_id,))
                await cursor.execute("UPDATE users SET rating = rating + 25 WHERE user_id = ?", (opp_id,))
            await conn.commit()

    res_text = (
        f"🎉 **ПОБЕДА!** Ваш отряд разгромил колоду игрока **{u2_nick}**!\n\n"
        f"📊 **Итоги калькуляции:**\n"
        f"• Мощь вашей колоды: `{u1_total_power}` (карты: {u1_cards_power} + книги: {u1_books_bonus})\n"
        f"• Мощь отряда противника: `{u2_total_power}`\n\n"
        f"🏆 Рейтинг: `+25` PTS"
    ) if win else (
        f"💀 **ПОРАЖЕНИЕ!** Колода игрока **{u2_nick}** оказалась сильнее вашего отряда.\n\n"
        f"📊 **Итоги калькуляции:**\n"
        f"• Мощь вашей колоды: `{u1_total_power}` (карты: {u1_cards_power} + книги: {u1_books_bonus})\n"
        f"• Мощь отряда противника: `{u2_total_power}`\n\n"
        f"🏆 Рейтинг: `-15` PTS"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ Новый бой", callback_data="action_arena")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="action_main_menu")]
    ])
    await callback.message.edit_text(res_text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

# --- СИМУЛЯЦИЯ И РЕЗУЛЬТАТ (БОТ) ---
@dp.callback_query(F.data.startswith("exec_bot_"))
async def process_bot_fight(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    parts = callback.data.split("_")
    bot_rating = int(parts[2])
    bot_name = parts[3].replace("_", " ")

    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT nickname, is_donator FROM users WHERE user_id = ?", (user_id,))
            u1_nick, u1_don = await cursor.fetchone()

            await cursor.execute("SELECT SUM(atk + def + hp + mana) FROM user_deck d JOIN inventory i ON d.card_id = i.id WHERE d.user_id = ?", (user_id,))
            deck_sum = (await cursor.fetchone())[0]
            u1_cards_power = deck_sum if deck_sum else 40

            await cursor.execute("SELECT extra_atk, extra_def, extra_mana FROM user_upgrades WHERE user_id = ?", (user_id,))
            u1_up = await cursor.fetchone()
            u1_books_bonus = sum(u1_up) * 10 if u1_up else 0
            u1_total_power = u1_cards_power + u1_books_bonus + (150 if u1_don else 0)

            bot_power = bot_rating * 0.8
            u1_score = u1_total_power + random.randint(0, 80)
            bot_score = bot_power + random.randint(0, 80)

            if u1_score >= bot_score:
                win = True
                await cursor.execute("UPDATE users SET rating = rating + 20 WHERE user_id = ?", (user_id,))
            else:
                win = False
                await cursor.execute("UPDATE users SET rating = MAX(0, rating - 10) WHERE user_id = ?", (user_id,))
            await conn.commit()

    res_text = (
        f"🎉 **ПОБЕДА над ботом!** Вы одолели **{bot_name}**!\n\n"
        f"📊 **Итоги калькуляции:**\n"
        f"• Мощь вашей колоды: `{u1_total_power}` (карты: {u1_cards_power} + книги: {u1_books_bonus})\n"
        f"• Сила ИИ бота: `{int(bot_power)}`\n\n"
        f"🏆 Рейтинг: `+20` PTS"
    ) if win else (
        f"💀 **ПОРАЖЕНИЕ!** ИИ-бот **{bot_name}** переиграл вашу колоду.\n\n"
        f"📊 **Итоги калькуляции:**\n"
        f"• Мощь вашей колоды: `{u1_total_power}` (карты: {u1_cards_power} + книги: {u1_books_bonus})\n"
        f"• Сила ИИ бота: `{int(bot_power)}`\n\n"
        f"🏆 Рейтинг: `-10` PTS"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ Новый бой", callback_data="action_arena")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="action_main_menu")]
    ])
    await callback.message.edit_text(res_text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


# ==================== МАГАЗИН ЗВЕЗД (TELEGRAM STARS) ====================
@dp.callback_query(F.data == "action_donate_shop")
async def show_donate_shop(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Набор «Малый» (5 Звезд)", callback_data="pay_star_small")],
        [InlineKeyboardButton(text="⭐ Набор «Большой» (15 Звезд)", callback_data="pay_star_large")],
        [InlineKeyboardButton(text="📚 Набор книг (10 Звезд)", callback_data="pay_star_books")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="action_main_menu")]
    ])
    text = (
        "⭐ **Магазин Telegram Stars (Донат)**\n\n"
        "Поддержите проект официальными Звездами Telegram (`⭐ XTR`).\n"
        "• Покупка активирует статус **⭐ VIP-Донатер** (бонус к силе колоды)."
    )
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data.startswith("pay_star_"))
async def send_star_invoice(callback: types.CallbackQuery):
    action = callback.data.replace("pay_star_", "")
    if action == "small":
        title, desc, payload, amount = "Набор «Малый» (+5 круток)", "Пакет круток", "payload_rolls_5", 5
    elif action == "large":
        title, desc, payload, amount = "Набор «Большой» (+15 круток)", "Запас круток + VIP", "payload_rolls_15", 15
    elif action == "books":
        title, desc, payload, amount = "Набор книг мудрости", "10 книг баффов", "payload_books_10", 10
    else:
        await callback.answer("Ошибка", show_alert=True)
        return

    await callback.message.answer_invoice(
        title=title, description=desc, prices=[LabeledPrice(label="Звезды Telegram", amount=amount)],
        provider_token="", currency="XTR", payload=payload
    )
    await callback.answer()

@dp.pre_checkout_query()
async def pre_checkout_query_handler(pre_checkout_query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.successful_payment)
async def successful_payment_handler(message: types.Message):
    user_id = message.from_user.id
    payload = message.successful_payment.invoice_payload
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("UPDATE users SET is_donator = 1 WHERE user_id = ?", (user_id,))
            if payload == "payload_rolls_5":
                await cursor.execute("UPDATE users SET rolls = rolls + 5 WHERE user_id = ?", (user_id,))
                r_text = "+5 круток 🎫"
            elif payload == "payload_rolls_15":
                await cursor.execute("UPDATE users SET rolls = rolls + 15 WHERE user_id = ?", (user_id,))
                r_text = "+15 круток 🎫"
            elif payload == "payload_books_10":
                await cursor.execute("UPDATE users SET books = books + 10 WHERE user_id = ?", (user_id,))
                r_text = "+10 книг 📚"
            await conn.commit()
    await message.answer(f"🎉 **Оплата прошла успешно!** Статус ⭐ **VIP-Донатер** активирован, {r_text}", parse_mode="Markdown")


# ==================== ТОП ПО СИЛЕ ====================
@dp.callback_query(F.data == "action_power_top")
async def show_power_top(callback: types.CallbackQuery):
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT user_id, nickname, is_donator FROM users")
            users = await cursor.fetchall()
            leaderboard = []
            for u_id, nick, is_donator in users:
                await cursor.execute("SELECT SUM(atk + def + hp + mana) FROM inventory WHERE user_id = ?", (u_id,))
                cards_sum = (await cursor.fetchone())[0] or 0
                await cursor.execute("SELECT extra_atk, extra_def, extra_mana FROM user_upgrades WHERE user_id = ?", (u_id,))
                up = await cursor.fetchone()
                total_power = cards_sum + (sum(up) * 10 if up else 0) + (150 if is_donator else 0)
                leaderboard.append((nick, total_power, is_donator))
            leaderboard.sort(key=lambda x: x[1], reverse=True)

    top_text = "🏆 **Топ-10 Сильнейших Игроков** 🏆\n\n"
    for idx, (nick, power, is_don) in enumerate(leaderboard[:10], 1):
        medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"{idx}."
        vip = " ⭐" if is_don else ""
        top_text += f"{medal} **{nick}**{vip} — `⚡ {power} силы`\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Главное меню", callback_data="action_main_menu")]])
    await callback.message.edit_text(top_text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


# ==================== СИСТЕМА ГАЧИ ====================
@dp.callback_query(F.data == "action_roll")
async def process_roll(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT rolls FROM users WHERE user_id = ?", (user_id,))
            rolls = (await cursor.fetchone())[0]

            if rolls < 1:
                await callback.answer("❌ У вас закончились крутки! Пополните баланс в Магазине Звезд.", show_alert=True)
                return

            await cursor.execute("UPDATE users SET rolls = rolls - 1 WHERE user_id = ?", (user_id,))
            await cursor.execute("SELECT name, universe, tier, class FROM characters")
            chars = await cursor.fetchall()
            chosen = random.choice(chars)
            name, universe, tier, c_class = chosen

            atk, def_val, hp, mana = random.randint(30, 90), random.randint(20, 70), random.randint(100, 300), random.randint(50, 150)
            await cursor.execute("INSERT INTO inventory (user_id, character_name, universe, tier, atk, def, hp, mana) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (user_id, name, universe, tier, atk, def_val, hp, mana))
            await conn.commit()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎰 Крутить еще", callback_data="action_roll")],
        [InlineKeyboardButton(text="📦 Инвентарь", callback_data="action_inventory")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="action_main_menu")]
    ])
    text = f"✨ **Вы совершили призыв!** ✨\n\n🎴 **{name}** (`Ранг {tier}`)\n🌌 Вселенная: {universe}\n⚔️ Атака: {atk} | 🛡 Защита: {def_val}\n❤️ HP: {hp} | 💧 Мана: {mana}\n\n🎫 Осталось круток: `{rolls - 1}`"
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


# ==================== СИСТЕМА ГИЛЬДИЙ ====================
@dp.callback_query(F.data == "action_guilds")
async def show_guilds_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT guild FROM users WHERE user_id = ?", (user_id,))
            user_guild = (await cursor.fetchone())[0]
            await cursor.execute("SELECT guild_name, members_count, leader_id, total_bosses_defeated FROM guilds")
            guilds = await cursor.fetchall()

    keyboard_builder = []
    if user_guild != 'Нет':
        g_info = next((g for g in guilds if g[0] == user_guild), None)
        is_leader = g_info and g_info[2] == user_id
        bosses_count = g_info[3] if g_info else 0
        
        asta_status = "⚔️ Обычный состав"
        if bosses_count >= 100:
            asta_status = "🔥 **Аста (SS-Tier) [Чёрный клевер]** (Максимальный бонус!)"
        elif bosses_count >= 50:
            asta_status = "⭐ **Аста (Standard) [Чёрный клевер]**"

        async with aiosqlite.connect("gacha_bot.db") as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT user_id, nickname, is_donator FROM users WHERE guild = ?", (user_guild,))
                members = await cursor.fetchall()
        members_text = "\n".join([f"• {'⭐ ' if m[2] else ''}{m[1]} {'(Лидер)' if m[0] == g_info[2] else ''}" for m in members])
        
        text = (
            f"🏰 **Ваша гильдия:** `{user_guild}`\n"
            f"🏆 Побеждено боссов: `{bosses_count}`\n"
            f"🎁 Награда гильдии: {asta_status}\n\n"
            f"👥 **Участники:**\n{members_text}"
        )
        keyboard_builder.append([InlineKeyboardButton(text="🐉 Гильд-босс (Рейд)", callback_data="action_guild_boss")])
        if is_leader and len(members) > 1:
            keyboard_builder.append([InlineKeyboardButton(text="👢 Кикнуть игрока", callback_data="manage_kick_menu")])
        keyboard_builder.append([InlineKeyboardButton(text="🚪 Покинуть гильдию", callback_data="leave_guild")])
    else:
        text = "🏰 **Список гильдий**\n\nВыберите гильдию для вступления:"
        for g_name, count, _, b_count in guilds:
            badge = " [SS Аста]" if b_count >= 100 else (" [Аста]" if b_count >= 50 else "")
            keyboard_builder.append([InlineKeyboardButton(text=f"🛡 {g_name} ({count} уч.){badge}", callback_data=f"join_guild_{g_name}")])
            
    keyboard_builder.append([InlineKeyboardButton(text="🏆 Топ гильдий по силе", callback_data="action_guilds_top")])
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
            if (await cursor.fetchone())[0] != 'Нет':
                await callback.answer("❌ Вы уже в гильдии.", show_alert=True)
                return
            await cursor.execute("SELECT leader_id FROM guilds WHERE guild_name = ?", (guild_name,))
            g_row = await cursor.fetchone()
            if g_row and not g_row[0]:
                await cursor.execute("UPDATE guilds SET leader_id = ? WHERE guild_name = ?", (user_id, guild_name))
            await cursor.execute("UPDATE users SET guild = ? WHERE user_id = ?", (guild_name, user_id))
            await cursor.execute("UPDATE guilds SET members_count = members_count + 1 WHERE guild_name = ?", (guild_name,))
            await conn.commit()
    await callback.answer(f"✅ Вы вступили в гильдию **{guild_name}**!", show_alert=True)
    await show_guilds_menu(callback)

@dp.callback_query(F.data == "leave_guild")
async def process_leave_guild(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT guild FROM users WHERE user_id = ?", (user_id,))
            old_guild = (await cursor.fetchone())[0]
            await cursor.execute("SELECT leader_id FROM guilds WHERE guild_name = ?", (old_guild,))
            is_leader = (await cursor.fetchone())[0] == user_id
            await cursor.execute("UPDATE users SET guild = 'Нет' WHERE user_id = ?", (user_id,))
            await cursor.execute("UPDATE guilds SET members_count = MAX(0, members_count - 1) WHERE guild_name = ?", (old_guild,))
            if is_leader:
                await cursor.execute("SELECT user_id FROM users WHERE guild = ? LIMIT 1", (old_guild,))
                next_m = await cursor.fetchone()
                await cursor.execute("UPDATE guilds SET leader_id = ? WHERE guild_name = ?", (next_m[0] if next_m else None, old_guild))
            await conn.commit()
    await callback.answer("🚪 Вы покинули гильдию.", show_alert=True)
    await show_guilds_menu(callback)

@dp.callback_query(F.data == "manage_kick_menu")
async def manage_kick_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT guild FROM users WHERE user_id = ?", (user_id,))
            guild_name = (await cursor.fetchone())[0]
            await cursor.execute("SELECT user_id, nickname FROM users WHERE guild = ? AND user_id != ?", (guild_name, user_id))
            members = await cursor.fetchall()
    kb = [[InlineKeyboardButton(text=f"👢 Кикнуть {m_nick}", callback_data=f"kick_member_{m_id}")] for m_id, m_nick in members]
    kb.append([InlineKeyboardButton(text="◀️ Назад", callback_data="action_guilds")])
    await callback.message.edit_text("👢 **Управление участниками**\nВыберите кого исключить:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data.startswith("kick_member_"))
async def process_kick_member(callback: types.CallbackQuery):
    admin_id = callback.from_user.id
    target_id = int(callback.data.replace("kick_member_", ""))
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT guild FROM users WHERE user_id = ?", (admin_id,))
            admin_guild = (await cursor.fetchone())[0]
            await cursor.execute("UPDATE users SET guild = 'Нет' WHERE user_id = ?", (target_id,))
            await cursor.execute("UPDATE guilds SET members_count = MAX(0, members_count - 1) WHERE guild_name = ?", (admin_guild,))
            await conn.commit()
    await callback.answer("✅ Игрок исключен.", show_alert=True)
    await show_guilds_menu(callback)


# ==================== ЦЕНТР ЗАДАНИЙ (3 КРУТКИ + КНОПКА РАЗРАБА) ====================
@dp.callback_query(F.data == "action_quests")
async def show_quests_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    DEV_ID = 533162381  # Твой Telegram ID
    
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT referral_count, last_claim FROM users WHERE user_id = ?", (user_id,))
            u_row = await cursor.fetchone()
            ref_count, last_claim_str = u_row[0] if u_row else 0, u_row[1] if u_row else None
            can_claim_daily = not last_claim_str or (datetime.now() - datetime.fromisoformat(last_claim_str) >= timedelta(hours=24))

    daily_status = "🎁 Получить (+3 крутки)" if can_claim_daily else "⏳ Через 24ч"
    
    kb = [
        [InlineKeyboardButton(text=f"📅 Ежедневный вход: {daily_status}", callback_data="claim_daily")],
        [InlineKeyboardButton(text=f"🤝 Пригласи друга (+1 крутка) ({ref_count}/1)", callback_data="claim_q_invite")]
    ]
    
    if user_id == DEV_ID:
        kb.append([InlineKeyboardButton(text="🛠 [DEV] Накинуть +5 книг и +5 круток", callback_data="dev_cheat_resources")])
        
    kb.append([InlineKeyboardButton(text="◀️ Главное меню", callback_data="action_main_menu")])

    await callback.message.edit_text("🎯 **Центр Заданий и Наград**\n\nЗа ежедневный вход дается **3 крутки**!", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "claim_daily")
async def process_claim_daily(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    now = datetime.now()
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT last_claim FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            if row and row[0] and now - datetime.fromisoformat(row[0]) < timedelta(hours=24):
                await callback.answer("⏳ Награда еще не доступна!", show_alert=True)
                return
            await cursor.execute("UPDATE users SET rolls = rolls + 3, last_claim = ? WHERE user_id = ?", (now.isoformat(), user_id))
            await conn.commit()
    await callback.answer("🎁 Получено +3 крутки за ежедневный вход!", show_alert=True)
    await show_quests_menu(callback)

@dp.callback_query(F.data == "dev_cheat_resources")
async def process_dev_cheat(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    DEV_ID = 533162381
    
    if user_id != DEV_ID:
        await callback.answer("❌ У вас нет прав!", show_alert=True)
        return

    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("UPDATE users SET rolls = rolls + 5, books = books + 5 WHERE user_id = ?", (user_id,))
            await conn.commit()
            
    await callback.answer("🛠 DEV: Успешно начислено +5 круток и +5 книг мудрости!", show_alert=True)
    await show_quests_menu(callback)


# ==================== СИСТЕМА ГИЛЬД-БОССОВ ====================
@dp.callback_query(F.data == "action_guild_boss")
async def show_guild_boss_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    today_str = str(date.today())
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT guild FROM users WHERE user_id = ?", (user_id,))
            guild_name = (await cursor.fetchone())[0]
            if guild_name == 'Нет' or not guild_name:
                await callback.answer("❌ Сначала вступите в гильдию!", show_alert=True)
                return
            
            await cursor.execute("SELECT total_bosses_defeated FROM guilds WHERE guild_name = ?", (guild_name,))
            total_defeated = (await cursor.fetchone())[0]

            await cursor.execute("SELECT boss_name, boss_hp, max_hp, killers_count, is_defeated, boss_level FROM guild_boss WHERE guild_name = ?", (guild_name,))
            boss_row = await cursor.fetchone()
            if not boss_row:
                b_name, b_hp, _ = get_boss_info(1)
                await cursor.execute("INSERT INTO guild_boss (guild_name, boss_name, boss_hp, max_hp, killers_count, is_defeated, boss_level) VALUES (?, ?, ?, ?, 0, 0, 1)", (guild_name, b_name, b_hp, b_hp))
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
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=hit_btn_text, callback_data="hit_guild_boss")],
        [InlineKeyboardButton(text="◀️ К гильдиям", callback_data="action_guilds")]
    ])
    
    text = (
        f"🏰 **Рейд на Гильд-Босса** (Уровень {boss_level})\n"
        f"🏆 Побеждено боссов гильдией: `{total_defeated}`\n\n"
        f"**{boss_name}**\n"
        f"Здоровье: `{boss_hp}/{max_hp}` HP\n[{bars}] {percent}%\n\n"
        f"👥 Участники: **{killers_count} / {required_hits}**"
    )
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "hit_guild_boss")
async def process_hit_boss(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    today_str = str(date.today())
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT guild FROM users WHERE user_id = ?", (user_id,))
            guild_name = (await cursor.fetchone())[0]
            await cursor.execute("SELECT 1 FROM guild_boss_hits WHERE user_id = ? AND guild_name = ? AND hit_date = ?", (user_id, guild_name, today_str))
            if await cursor.fetchone():
                await callback.answer("⏳ Вы уже атаковали сегодня!", show_alert=True)
                return
            await cursor.execute("SELECT extra_atk FROM user_upgrades WHERE user_id = ?", (user_id,))
            up = await cursor.fetchone()
            extra_atk = up[0] if up else 0
            await cursor.execute("SELECT is_donator FROM users WHERE user_id = ?", (user_id,))
            is_donator = (await cursor.fetchone())[0]
            damage = 15 + (extra_atk // 2) + (10 if is_donator else 0)

            await cursor.execute("SELECT boss_hp, killers_count, is_defeated, boss_level, max_hp FROM guild_boss WHERE guild_name = ?", (guild_name,))
            boss_hp, killers_count, is_defeated, boss_level, max_hp = await cursor.fetchone()
            _, _, required_hits = get_boss_info(boss_level)

            new_hp = max(0, boss_hp - damage)
            new_killers = killers_count + 1
            await cursor.execute("INSERT INTO guild_boss_hits (user_id, guild_name, hit_date) VALUES (?, ?, ?)", (user_id, guild_name, today_str))
            
            if new_hp == 0 or new_killers >= required_hits:
                next_level = boss_level + 1
                next_name, next_hp, _ = get_boss_info(next_level)
                
                await cursor.execute("""
                    UPDATE guild_boss 
                    SET boss_name = ?, boss_hp = ?, max_hp = ?, killers_count = 0, is_defeated = 0, boss_level = ? 
                    WHERE guild_name = ?
                """, (next_name, next_hp, next_hp, next_level, guild_name))
                
                await cursor.execute("UPDATE guilds SET total_bosses_defeated = total_bosses_defeated + 1 WHERE guild_name = ?", (guild_name,))
                await cursor.execute("UPDATE users SET rolls = rolls + 2 WHERE guild = ?", (guild_name,))
                await conn.commit()
                await callback.answer("🎉 Босс побежден! Новый босс призван, всем +2 крутки!", show_alert=True)
            else:
                await cursor.execute("UPDATE guild_boss SET boss_hp = ?, killers_count = ? WHERE guild_name = ?", (new_hp, new_killers, guild_name))
                await conn.commit()
                await callback.answer(f"⚔️ Удар нанесен! (-{damage} HP)", show_alert=True)
                
    await show_guild_boss_menu(callback)


# ==================== БИБЛИОТЕКА И БАФФЫ ====================
@dp.callback_query(F.data == "action_books_farm")
async def show_books_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT books FROM users WHERE user_id = ?", (user_id,))
            books = (await cursor.fetchone())[0]
            await cursor.execute("SELECT extra_atk, extra_def, extra_mana FROM user_upgrades WHERE user_id = ?", (user_id,))
            up = await cursor.fetchone()
            atk, defs, mana = up if up else (0, 0, 0)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ Прокачать +5 Атаки (3 книги)", callback_data="upgrade_stat_atk")],
        [InlineKeyboardButton(text="🛡 Прокачать +5 Защиты (3 книги)", callback_data="upgrade_stat_def")],
        [InlineKeyboardButton(text="💧 Прокачать +5 Маны (3 книги)", callback_data="upgrade_stat_mana")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="action_main_menu")]
    ])
    text = f"📖 **Библиотека Баффов**\n\n📚 Доступно книг: `{books}` шт.\n\n📈 Атака `+{atk}` | Защита `+{defs}` | Мана `+{mana}`"
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

async def upgrade_user_stat(callback: types.CallbackQuery, stat_column: str, stat_name: str):
    user_id = callback.from_user.id
    async with aiosqlite.connect("gacha_bot.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT books FROM users WHERE user_id = ?", (user_id,))
            books = (await cursor.fetchone())[0]
            if books < 3:
                await callback.answer("❌ Нужно минимум 3 книги!", show_alert=True)
                return
            await cursor.execute("UPDATE users SET books = books - 3 WHERE user_id = ?", (user_id,))
            await cursor.execute("INSERT INTO user_upgrades (user_id, extra_atk, extra_def, extra_mana) VALUES (?, 0, 0, 0) ON CONFLICT(user_id) DO NOTHING", (user_id,))
            await cursor.execute(f"UPDATE user_upgrades SET {stat_column} = {stat_column} + 5 WHERE user_id = ?", (user_id,))
            await conn.commit()
    await callback.answer(f"🎉 Успешно! {stat_name} увеличена на +5.", show_alert=True)
    await show_books_menu(callback)

@dp.callback_query(F.data == "upgrade_stat_atk")
async def handle_up_atk(callback: types.CallbackQuery): await upgrade_user_stat(callback, "extra_atk", "Атака")
@dp.callback_query(F.data == "upgrade_stat_mana")
async def handle_up_mana(callback: types.CallbackQuery): await upgrade_user_stat(callback, "extra_mana", "Мана")
@dp.callback_query(F.data == "upgrade_stat_def")
async def handle_up_def(callback: types.CallbackQuery): await upgrade_user_stat(callback, "extra_def", "Защита")


# ==================== ЗАПУСК БОТА ====================
async def main():
    await init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Бот запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
