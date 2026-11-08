import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# Заглушка для Render, чтобы он видел открытый порт
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

# Запускаем сервер параллельно с ботом
threading.Thread(target=run_server, daemon=True).start()
import asyncio
import logging
import random
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice

# ==================== НАСТРОЙКИ ====================
TOKEN = "9049422974:AAG5svkRpLtL0-OXX6MikuEKNiJHHsEFoao"  # Твой токен от BotFather
ADMIN_ID = 912417066               # Твой Telegram ID разработчика

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ==================== ПУЛЫ КАРТ С СТАТАМИ ====================
def get_card_stats(rarity, char_class):
    base_stats = {
        'SS': {'atk': 120, 'def': 80, 'hp': 500, 'mana': 100},
        'S':  {'atk': 85,  'def': 55, 'hp': 350, 'mana': 75},
        'A':  {'atk': 55,  'def': 35, 'hp': 250, 'mana': 50},
        'B':  {'atk': 35,  'def': 20, 'hp': 170, 'mana': 30},
        'C':  {'atk': 20,  'def': 10, 'hp': 100, 'mana': 15}
    }
    stat = base_stats.get(rarity, base_stats['C']).copy()
    
    if char_class == "ДД":
        stat['atk'] = int(stat['atk'] * 1.3)
    elif char_class == "Танк":
        stat['def'] = int(stat['def'] * 1.4)
        stat['hp'] = int(stat['hp'] * 1.3)
    elif char_class == "Саппорт":
        stat['mana'] = int(stat['mana'] * 1.5)
    
    return stat['atk'], stat['def'], stat['hp'], stat['mana']

ICARDS_POOL = [
    {"name": "Ями Сукехиро (Капитан)", "rarity": "S", "anime": "Черный Клевер", "class": "ДД"},
    {"name": "Люмьер Сильвамисион (Первый Король)", "rarity": "S", "anime": "Черный Клевер", "class": "ДД"},
    {"name": "Ноэль Сильва (Валькирия)", "rarity": "S", "anime": "Черный Клевер", "class": "Танк"},
    {"name": "Ванесса Энотека (Судьба ведьмы)", "rarity": "A", "anime": "Черный Клевер", "class": "Саппорт"},
    {"name": "Магна Свинг", "rarity": "C", "anime": "Черный Клевер", "class": "ДД"},
    {"name": "Лаки Вольт", "rarity": "C", "anime": "Черный Клевер", "class": "ДД"},
    {"name": "Гордон Агриппа", "rarity": "C", "anime": "Черный Клевер", "class": "Саппорт"},
    {"name": "Грей", "rarity": "B", "anime": "Черный Клевер", "class": "Саппорт"},
    {"name": "Неро (Запечатывающая магия)", "rarity": "A", "anime": "Черный Клевер", "class": "Скрытый"},
    {"name": "Зора Идеале", "rarity": "A", "anime": "Черный Клевер", "class": "Скрытый"},
    {"name": "Генри Леголта", "rarity": "C", "anime": "Черный Клевер", "class": "Танк"},
    {"name": "Чарми Паппитсон", "rarity": "A", "anime": "Черный Клевер", "class": "Саппорт"},
    {"name": "Уильям Вьенджанс (Капитан)", "rarity": "S", "anime": "Черный Клевер", "class": "Саппорт"},
    {"name": "Лангир Воде", "rarity": "A", "anime": "Черный Клевер", "class": "ДД"},
    {"name": "Клаус Люнетт", "rarity": "C", "anime": "Черный Клевер", "class": "Танк"},
    {"name": "Мимоза Вермилион", "rarity": "A", "anime": "Черный Клевер", "class": "Саппорт"},
    {"name": "Нозель Сильва (Капитан)", "rarity": "S", "anime": "Черный Клевер", "class": "ДД"},
    {"name": "Солид Сильва", "rarity": "C", "anime": "Черный Клевер", "class": "ДД"},
    {"name": "Мереолео Вермилион", "rarity": "S", "anime": "Черный Клевер", "class": "ДД"},
    {"name": "Фуэголеон Вермилион (Капитан)", "rarity": "A", "anime": "Черный Клевер", "class": "Танк"},
    {"name": "Леопольд Вермилион", "rarity": "A", "anime": "Черный Клевер", "class": "ДД"},
    {"name": "Шарлотта Роузли (Капитан)", "rarity": "A", "anime": "Черный Клевер", "class": "Саппорт"},
    {"name": "Соланж Лаон", "rarity": "C", "anime": "Черный Клевер", "class": "Танк"},
    {"name": "Джек Потрошитель (Капитан)", "rarity": "A", "anime": "Черный Клевер", "class": "ДД"},
    {"name": "Секе Бронзазза", "rarity": "C", "anime": "Черный Клевер", "class": "Танк"},
    {"name": "Кайзер Грандранка (Капитан)", "rarity": "A", "anime": "Черный Клевер", "class": "Танк"},
    {"name": "Дороти Уэйнот (Капитан)", "rarity": "A", "anime": "Черный Клевер", "class": "Скрытый"},
    {"name": "Кирш Вермилион", "rarity": "A", "anime": "Черный Клевер", "class": "Саппорт"},
    {"name": "Рил Буамортье (Капитан)", "rarity": "A", "anime": "Черный Клевер", "class": "Саппорт"},
    {"name": "Данте Зогратис", "rarity": "S", "anime": "Черный Клевер", "class": "Танк"},
    {"name": "Зинон Зогратис", "rarity": "S", "anime": "Черный Клевер", "class": "Скрытый"},
    {"name": "Ваника Зогратис", "rarity": "S", "anime": "Черный Клевер", "class": "ДД"},
    {"name": "Нахт Фауст", "rarity": "S", "anime": "Черный Клевер", "class": "Скрытый"},
    {"name": "Лихт (Лидер эльфов)", "rarity": "S", "anime": "Черный Клевер", "class": "Скрытый"},
    {"name": "Патл (Патри)", "rarity": "S", "anime": "Черный Клевер", "class": "ДД"},
    {"name": "Загра (Демон слова)", "rarity": "S", "anime": "Черный Клевер", "class": "Скрытый"},
    {"name": "Мегикула (Высший демон)", "rarity": "S", "anime": "Черный Клевер", "class": "Скрытый"},
    {"name": "Моррис (Ученый Триады)", "rarity": "B", "anime": "Черный Клевер", "class": "Саппорт"},
    {"name": "Салли (Безумный ученый)", "rarity": "B", "anime": "Черный Клевер", "class": "Саппорт"},
    {"name": "Ралт / Рю (Жители Хинока)", "rarity": "C", "anime": "Черный Клевер", "class": "ДД"},
    {"name": "Аделина (Мать церкви)", "rarity": "C", "anime": "Черный Клевер", "class": "Саппорт"},
    {"name": "Бато / Охотник на магов", "rarity": "C", "anime": "Черный Клевер", "class": "ДД"},
    {"name": "Фанзель Кругер", "rarity": "B", "anime": "Черный Клевер", "class": "ДД"},
    {"name": "Доминанта Код", "rarity": "C", "anime": "Черный Клевер", "class": "Саппорт"},
    {"name": "Марк (Рыцарь-чародей)", "rarity": "C", "anime": "Черный Клевер", "class": "Танк"},
    {"name": "Брокс (Наемник)", "rarity": "C", "anime": "Черный Клевер", "class": "ДД"},
    {"name": "Лифыр (Младший эльф)", "rarity": "C", "anime": "Черный Клевер", "class": "Саппорт"},
    {"name": "Эльфийский страж", "rarity": "C", "anime": "Черный Клевер", "class": "Танк"},
    {"name": "Храм Подводного Царя (Страж)", "rarity": "C", "anime": "Черный Клевер", "class": "Танк"},
    {"name": "Гончая Ведьминого Леса", "rarity": "C", "anime": "Черный Клевер", "class": "ДД"},
    {"name": "Юта Оккоцу (Особый класс)", "rarity": "S", "anime": "Магическая битва", "class": "ДД"},
    {"name": "Годжо Сатору (Сильнейший)", "rarity": "SS", "anime": "Магическая битва", "class": "ДД"},
    {"name": "Рёмен Сукуна", "rarity": "SS", "anime": "Магическая битва", "class": "ДД"},
    {"name": "Айнз Оал Гоун (Момонга)", "rarity": "S", "anime": "Оверлорд", "class": "ДД"},
    {"name": "Альбедо", "rarity": "S", "anime": "Оверлорд", "class": "Танк"},
    {"name": "Ичиго Куросаки (Банкай)", "rarity": "S", "anime": "Блич", "class": "ДД"},
    {"name": "Сон Джин-Ву (Монарх)", "rarity": "SS", "anime": "Соло Левелинг", "class": "Скрытый"},
    {"name": "Игрис (Маршал Теней)", "rarity": "S", "anime": "Соло Левелинг", "class": "Танк"},
    {"name": "Бер (Муравей)", "rarity": "S", "anime": "Соло Левелинг", "class": "ДД"}
]

SS_CARDS_POOL = [
    {"name": "Юлиус Нова Хронохро", "rarity": "SS", "anime": "Черный Клевер", "class": "Скрытый"},
    {"name": "Годжо Сатору (Бесконечность)", "rarity": "SS", "anime": "Магическая битва", "class": "ДД"},
    {"name": "Рёмен Сукуна (Хэйан)", "rarity": "SS", "anime": "Магическая битва", "class": "ДД"},
    {"name": "Сон Джин-Ву (Монарх Теней)", "rarity": "SS", "anime": "Соло Левелинг", "class": "Скрытый"},
    {"name": "Айнз Оал Гоун (Истинная мощь)", "rarity": "SS", "anime": "Оверлорд", "class": "ДД"},
    {"name": "Яхве (Квинси)", "rarity": "SS", "anime": "Блич", "class": "ДД"}
]

# ==================== БАЗА ДАННЫХ ====================
def init_db():
    conn = sqlite3.connect("gacha_bot.db")
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            rolls INTEGER DEFAULT 5,
            books INTEGER DEFAULT 5,
            rating INTEGER DEFAULT 1000,
            guild TEXT DEFAULT 'Нет',
            invited_by INTEGER DEFAULT NULL,
            referral_count INTEGER DEFAULT 0
        )
    """)
    
    cursor.execute("""
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
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            universe TEXT,
            tier TEXT,
            class TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS guilds (
            guild_name TEXT PRIMARY KEY,
            leader_id INTEGER,
            members_count INTEGER DEFAULT 1
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pvp_deck (
            user_id INTEGER,
            card_id INTEGER
        )
    """)
    
    cursor.execute("SELECT COUNT(*) FROM characters")
    if cursor.fetchone()[0] == 0:
        all_to_insert = []
        for c in ICARDS_POOL:
            all_to_insert.append((c["name"], c["anime"], c["rarity"], c["class"]))
        for c in SS_CARDS_POOL:
            all_to_insert.append((c["name"], c["anime"], c["rarity"], c["class"]))
            
        cursor.executemany("INSERT INTO characters (name, universe, tier, class) VALUES (?, ?, ?, ?)", all_to_insert)
        conn.commit()
        
    conn.commit()
    conn.close()

init_db()

# ==================== КНОПКИ МЕНЮ ====================
def get_main_keyboard(is_admin: bool = False):
    keyboard = [
        [
            InlineKeyboardButton(text="🎰 Крутить гачу", callback_data="action_roll"),
            InlineKeyboardButton(text="👤 Профиль", callback_data="action_profile")
        ],
        [
            InlineKeyboardButton(text="📦 Коллекция", callback_data="action_collection"),
            InlineKeyboardButton(text="⚔️ PVP Сетап", callback_data="action_pvp_menu")
        ],
        [
            InlineKeyboardButton(text="🛡 Гильдии", callback_data="action_guild_menu"),
            InlineKeyboardButton(text="💎 Магазин (Stars)", callback_data="action_shop")
        ],
        [
            InlineKeyboardButton(text="🤝 Партнерская программа", callback_data="action_referral"),
        ]
    ]
    if is_admin:
        keyboard.append([InlineKeyboardButton(text="⚡️ [Админ] +50 круток", callback_data="admin_add_rolls")])
        
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_back_keyboard(is_admin: bool = False):
    keyboard = [
        [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="action_menu")]
    ]
    if is_admin:
        keyboard.append([InlineKeyboardButton(text="⚡️ [Админ] +50 круток", callback_data="admin_add_rolls")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# ==================== СТАРТ ====================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    
    # Ловим аргумент после /start (например, ref123456)
    args = message.text.split(maxsplit=1)
    referrer_id = None
    if len(args) > 1 and args[1].startswith("ref"):
        try:
            referrer_id = int(args[1].replace("ref", ""))
        except ValueError:
            pass

    conn = sqlite3.connect("gacha_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()

    if not user:
        if referrer_id and referrer_id != user_id:
            cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (referrer_id,))
            if cursor.fetchone():
                # Новичку даем бонусные крутки при регистрации по рефке (7 вместо дефолтных 5)
                cursor.execute(
                    "INSERT INTO users (user_id, rolls, invited_by) VALUES (?, 7, ?)",
                    (user_id, referrer_id)
                )
                # Пригласившему начисляем +2 крутки и увеличиваем счетчик рефералов
                cursor.execute(
                    "UPDATE users SET rolls = rolls + 2, referral_count = referral_count + 1 WHERE user_id = ?",
                    (referrer_id,)
                )
                conn.commit()
                # Уведомляем пригласившего
                try:
                    await bot.send_message(
                        referrer_id, 
                        "🎉 По вашей реферальной ссылке зарегистрировался новый игрок!\n🎁 Вам начислено **+2 крутки** 🎫"
                    )
                except Exception:
                    pass
            else:
                cursor.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
                conn.commit()
        else:
            cursor.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
            conn.commit()

    conn.close()

    is_admin = (user_id == ADMIN_ID)
    text = (
        "🤖 **Добро пожаловать в Аниме-Гача ТГ-Бот!**\n\n"
        "Выбирай нужный раздел кнопками ниже:"
    )
    await message.answer(text, parse_mode="Markdown", reply_markup=get_main_keyboard(is_admin))

    is_admin = (user_id == ADMIN_ID)
    text = (
        "🔥 **Добро пожаловать в Аниме-Гача ТГ-Бот!**\n\n"
        "Выбирай нужный раздел кнопками ниже:"
    )
    await message.answer(text, parse_mode="Markdown", reply_markup=get_main_keyboard(is_admin))

@dp.message(Command("createguild"))
async def cmd_create_guild(message: types.Message):
    user_id = message.from_user.id
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        await message.answer("⚠️ Укажи название гильдии. Пример:\n`/createguild 9-07`", parse_mode="Markdown")
        return
        
    guild_name = args[1].strip()
    
    conn = sqlite3.connect("gacha_bot.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM guilds WHERE guild_name = ?", (guild_name,))
    if cursor.fetchone():
        conn.close()
        await message.answer(f"❌ Гильдия с именем `{guild_name}` уже существует!", parse_mode="Markdown")
        return
        
    cursor.execute("SELECT guild FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    if res and res[0] != 'Нет' and res[0] is not None:
        conn.close()
        await message.answer(f"❌ Ты уже состоишь в гильдии `{res[0]}`! Сначала покинь её.", parse_mode="Markdown")
        return
        
    cursor.execute("INSERT INTO guilds (guild_name, leader_id, members_count) VALUES (?, ?, 1)", (guild_name, user_id))
    cursor.execute("UPDATE users SET guild = ? WHERE user_id = ?", (guild_name, user_id))
    conn.commit()
    conn.close()
    
    await message.answer(f"🎉 Гильдия **'{guild_name}'** успешно создана! Ты стал её лидером.", parse_mode="Markdown")

@dp.message(Command("leaveguild"))
async def cmd_leave_guild(message: types.Message):
    user_id = message.from_user.id
    
    conn = sqlite3.connect("gacha_bot.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT guild FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    
    if not res or res[0] == 'Нет' or res[0] is None:
        conn.close()
        await message.answer("❌ Ты и так не состоишь ни в какой гильдии!", parse_mode="Markdown")
        return
        
    guild_name = res[0]
    cursor.execute("UPDATE users SET guild = 'Нет' WHERE user_id = ?", (user_id,))
    
    cursor.execute("SELECT COUNT(*) FROM users WHERE guild = ?", (guild_name,))
    members_count = cursor.fetchone()[0]
    
    if members_count == 0:
        cursor.execute("DELETE FROM guilds WHERE guild_name = ?", (guild_name,))
    else:
        cursor.execute("UPDATE guilds SET members_count = ? WHERE guild_name = ?", (members_count, guild_name))
        
    conn.commit()
    conn.close()
    
    await message.answer(f"🚪 Ты успешно покинул гильдию **'{guild_name}'**.", parse_mode="Markdown")

# ==================== ОБРАБОТКА КНОПОК И ДЕЙСТВИЙ ====================
@dp.callback_query(F.data.in_({
    "action_menu", "action_roll", "action_profile", "action_collection", 
    "action_pvp_menu", "action_view_deck", "action_choose_deck", "action_find_pvp", "action_clear_deck",
    "action_guild_menu", "action_guild_list", "action_guild_create_info", "action_leave_guild",
    "action_shop", "buy_10_rolls", "admin_add_rolls"
}))
async def process_callbacks(callback: types.CallbackQuery):
    action = callback.data
    user_id = callback.from_user.id
    is_admin = (user_id == ADMIN_ID)
    
    conn = sqlite3.connect("gacha_bot.db")
    cursor = conn.cursor()
    
    if action == "action_menu":
        conn.close()
        try:
            await callback.message.edit_text(
                "📋 **Главное меню:**", 
                parse_mode="Markdown", 
                reply_markup=get_main_keyboard(is_admin)
            )
        except Exception:
            await callback.message.answer(
                "📋 **Главное меню:**", 
                parse_mode="Markdown", 
                reply_markup=get_main_keyboard(is_admin)
            )
        await callback.answer()
        
    elif action == "admin_add_rolls":
        if not is_admin:
            conn.close()
            await callback.answer("❌ Доступ запрещен!", show_alert=True)
            return

        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO users (user_id, rolls) VALUES (?, ?)", (user_id, 55))
        else:
            cursor.execute("UPDATE users SET rolls = rolls + 50 WHERE user_id = ?", (user_id,))
        conn.commit()
        
        cursor.execute("SELECT rolls FROM users WHERE user_id = ?", (user_id,))
        new_total = cursor.fetchone()[0]
        conn.close()
        
        await callback.answer(f"⚡️ Успешно! Добавлено 50 круток. Всего: {new_total}", show_alert=True)
        
    elif action == "action_roll":
        cursor.execute("SELECT rolls FROM users WHERE user_id = ?", (user_id,))
        res = cursor.fetchone()
        rolls = res[0] if res else 0
        
        if rolls <= 0:
            conn.close()
            await callback.answer("❌ У тебя закончились крутки! Загляни в магазин.", show_alert=True)
            return
            
        cursor.execute("SELECT name, universe, tier, class FROM characters ORDER BY RANDOM() LIMIT 1")
        char_row = cursor.fetchone()
        
        if not char_row:
            conn.close()
            await callback.answer("❌ В базе данных пока нет персонажей!", show_alert=True)
            return
            
        char_name, universe, tier, char_class = char_row
        atk, def_val, hp, mana = get_card_stats(tier, char_class)
        
        cursor.execute("UPDATE users SET rolls = rolls - 1 WHERE user_id = ?", (user_id,))
        cursor.execute("""
            INSERT INTO inventory (user_id, character_name, universe, tier, atk, def, hp, mana) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, char_name, universe, tier, atk, def_val, hp, mana))
        conn.commit()
        
        cursor.execute("SELECT rolls FROM users WHERE user_id = ?", (user_id,))
        new_rolls = cursor.fetchone()[0]
        conn.close()
        
        text = (
            f"🎉 **Тебе выпал персонаж!**\n\n"
            f"👤 **Имя:** {char_name}\n"
            f"🌍 **Вселенная:** {universe}\n"
            f"⭐ **Ранг:** `{tier}` | ⚔️ **Класс:** `{char_class}`\n\n"
            f"📊 **Статы:** ⚔️ `{atk}` | 🛡 `{def_val}` | ❤️ `{hp}`\n\n"
            f"🎟 Осталось круток: {new_rolls}"
        )
        
        await callback.message.answer(
            text, 
            parse_mode="Markdown", 
            reply_markup=get_main_keyboard(is_admin)
        )
        await callback.answer()
        
    elif action == "action_profile":
        cursor.execute("SELECT rolls, books, rating, guild FROM users WHERE user_id = ?", (user_id,))
        user_data = cursor.fetchone()
        
        cursor.execute("SELECT COUNT(*) FROM inventory WHERE user_id = ?", (user_id,))
        chars_count = cursor.fetchone()[0]
        conn.close()

        rolls = user_data[0] if user_data and user_data[0] is not None else 5
        books = user_data[1] if user_data and user_data[1] is not None else 5
        rating = user_data[2] if user_data and user_data[2] is not None else 1000
        guild = user_data[3] if user_data and user_data[3] and user_data[3] != 'Нет' else 'Нет гильдии'
        
        text = (
            f"👤 **Профиль игрока:**\n\n"
            f"🆔 **ID:** `{user_id}`\n"
            f"🎟 Доступные крутки: `{rolls}`\n"
            f"📖 Книжки прокачки: `{books}`\n"
            f"🏆 Рейтинг на арене: `{rating}`\n"
            f"🛡 Гильдия: `{guild}`\n"
            f"📦 Карт в коллекции: `{chars_count}`"
        )
        try:
            await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_back_keyboard(is_admin))
        except Exception:
            await callback.message.answer(text, parse_mode="Markdown", reply_markup=get_back_keyboard(is_admin))
        await callback.answer()
        
    elif action == "action_collection":
        cursor.execute("""
            SELECT character_name, tier, universe, atk, def, hp FROM inventory 
            WHERE user_id = ? 
            ORDER BY CASE tier WHEN 'SS' THEN 1 WHEN 'S' THEN 2 WHEN 'A' THEN 3 WHEN 'B' THEN 4 ELSE 5 END ASC LIMIT 10
        """, (user_id,))
        items = cursor.fetchall()
        
        cursor.execute("SELECT COUNT(*) FROM inventory WHERE user_id = ?", (user_id,))
        total = cursor.fetchone()[0]
        conn.close()
        
        text = f"📦 **Твоя коллекция карт** (всего: {total}):\n\n"
        if items:
            for name, tier, universe, atk, def_val, hp in items:
                text += f"• `[{tier}]` **{name}** (⚔️{atk} | 🛡{def_val} | ❤️{hp})\n"
        else:
            text += "В твоем инвентаре пока пусто."
            
        try:
            await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_back_keyboard(is_admin))
        except Exception:
            await callback.message.answer(text, parse_mode="Markdown", reply_markup=get_back_keyboard(is_admin))
        await callback.answer()

    elif action == "action_pvp_menu":
        conn.close()
        pvp_kb = [
            [InlineKeyboardButton(text="👀 Посмотреть мой сетап (5 карт)", callback_data="action_view_deck")],
            [InlineKeyboardButton(text="🛠 Собрать сетап вручную", callback_data="action_choose_deck")],
            [InlineKeyboardButton(text="⚔️ Найти бой на Арене", callback_data="action_find_pvp")],
            [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="action_menu")]
        ]
        text = (
            "⚔️ **Арена / PVP Меню**\n\n"
            "Собери команду из 5 бойцов со статами и иди в бой!"
        )
        try:
            await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=pvp_kb))
        except Exception:
            await callback.message.answer(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=pvp_kb))
        await callback.answer()

    elif action == "action_view_deck":
        cursor.execute("""
            SELECT c.character_name, c.tier, c.universe, c.atk, c.def, c.hp FROM pvp_deck d
            JOIN inventory c ON d.card_id = c.id
            WHERE d.user_id = ?
            ORDER BY CASE c.tier WHEN 'SS' THEN 1 WHEN 'S' THEN 2 WHEN 'A' THEN 3 WHEN 'B' THEN 4 ELSE 5 END ASC
        """, (user_id,))
        deck = cursor.fetchall()
        conn.close()

        text = "⚔️ **Твой текущий боевой сетап для PVP:**\n\n"
        if deck:
            for i, (name, tier, universe, atk, def_val, hp) in enumerate(deck, 1):
                text += f"{i}. `[{tier}]` **{name}** (⚔️{atk} | 🛡{def_val} | ❤️{hp})\n"
            text += f"\nВ колоде: **{len(deck)} / 5** карт."
        else:
            text += "Твой сетап пуст! Нажми «🛠 Собрать сетап вручную»."

        pvp_kb = [
            [InlineKeyboardButton(text="🗑 Очистить колоду", callback_data="action_clear_deck")],
            [InlineKeyboardButton(text="🛠 Изменить / Собрать", callback_data="action_choose_deck")],
            [InlineKeyboardButton(text="⬅️ Назад в PVP меню", callback_data="action_pvp_menu")]
        ]
        try:
            await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=pvp_kb))
        except Exception:
            await callback.message.answer(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=pvp_kb))
        await callback.answer()

    elif action == "action_clear_deck":
        cursor.execute("DELETE FROM pvp_deck WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        
        pvp_kb = [
            [InlineKeyboardButton(text="🛠 Собрать сетап вручную", callback_data="action_choose_deck")],
            [InlineKeyboardButton(text="⬅️ Назад в PVP меню", callback_data="action_pvp_menu")]
        ]
        text = "⚔️ Твоя колода теперь пуста. Выбери новые карты из инвентаря."
        try:
            await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=pvp_kb))
        except Exception:
            await callback.message.answer(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=pvp_kb))
        await callback.answer("🧹 Колода полностью очищена!", show_alert=True)

    elif action == "action_choose_deck":
        cursor.execute("SELECT COUNT(*) FROM pvp_deck WHERE user_id = ?", (user_id,))
        deck_count = cursor.fetchone()[0]

        if deck_count >= 5:
            conn.close()
            await callback.answer("⚠️ Твоя колода уже заполнена (5/5)!", show_alert=True)
            return

        cursor.execute("""
            SELECT id, character_name, tier, atk FROM inventory 
            WHERE user_id = ? 
            ORDER BY CASE tier WHEN 'SS' THEN 1 WHEN 'S' THEN 2 WHEN 'A' THEN 3 WHEN 'B' THEN 4 ELSE 5 END ASC 
            LIMIT 15
        """, (user_id,))
        inventory_items = cursor.fetchall()
        conn.close()

        if not inventory_items:
            await callback.answer("❌ У тебя пока нет карт! Сначала покрути гачу.", show_alert=True)
            return

        text = f"🛠 **Выбери карту для сетапа ({deck_count}/5):**\nНажми на карту ниже:"
        
        kb_rows = []
        for item_id, name, tier, atk in inventory_items:
            kb_rows.append([InlineKeyboardButton(text=f"[{tier}] {name} (⚔️{atk})", callback_data=f"add_card_{item_id}")])
        
        kb_rows.append([InlineKeyboardButton(text="👀 Посмотреть колоду", callback_data="action_view_deck")])
        kb_rows.append([InlineKeyboardButton(text="⬅️ Назад в PVP меню", callback_data="action_pvp_menu")])

        try:
            await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
        except Exception:
            await callback.message.answer(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
        await callback.answer()

    elif action == "action_find_pvp":
        cursor.execute("SELECT COUNT(*) FROM pvp_deck WHERE user_id = ?", (user_id,))
        deck_count = cursor.fetchone()[0]
        if deck_count < 5:
            conn.close()
            await callback.answer(f"❌ В сетапе должно быть ровно 5 карт! (Сейчас: {deck_count}/5)", show_alert=True)
            return

        cursor.execute("""
            SELECT c.atk, c.def, c.hp FROM pvp_deck d
            JOIN inventory c ON d.card_id = c.id
            WHERE d.user_id = ?
        """, (user_id,))
        user_cards = cursor.fetchall()
        user_power = sum(atk + def_val + (hp // 5) for atk, def_val, hp in user_cards)

        cursor.execute("""
            SELECT DISTINCT user_id FROM pvp_deck 
            WHERE user_id != ? 
            ORDER BY RANDOM() LIMIT 1
        """, (user_id,))
        opp_row = cursor.fetchone()

        opp_cards = []
        opp_id = None
        if opp_row:
            opp_id = opp_row[0]
            cursor.execute("""
                SELECT c.character_name, c.tier, c.atk, c.def, c.hp FROM pvp_deck d
                JOIN inventory c ON d.card_id = c.id
                WHERE d.user_id = ?
            """, (opp_id,))
            opp_cards = cursor.fetchall()

        if opp_cards:
            opp_power = sum(atk + def_val + (hp // 5) for name, tier, atk, def_val, hp in opp_cards)
        else:
            opp_power = random.randint(200, 500)
            opp_id = "Случайный Босс Арены"
            opp_cards = [("Случайный страж", "B", 40, 20, 150)]

        conn.close()

        user_total = user_power + random.randint(-30, 50)
        opp_total = opp_power + random.randint(-30, 50)

        if user_total >= opp_total:
            rating_change = random.randint(20, 45)
            result_header = "🎉 **ПОБЕДА НА АРЕНЕ!**"
        else:
            rating_change = -random.randint(15, 30)
            result_header = "💀 **ПОРАЖЕНИЕ НА АРЕНЕ...**"

        conn = sqlite3.connect("gacha_bot.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET rating = rating + ? WHERE user_id = ?", (rating_change, user_id))
        cursor.execute("SELECT rating FROM users WHERE user_id = ?", (user_id,))
        new_rating = cursor.fetchone()[0]
        conn.commit()
        conn.close()

        text = (
            f"{result_header}\n\n"
            f"👤 **Соперник ID:** `{opp_id}`\n"
            f"🛡 **Колода противника:**\n"
        )
        for name, tier, atk, def_val, hp in opp_cards:
            text += f" • `[{tier}]` {name} (⚔️{atk} | 🛡{def_val})\n"

        text += (
            f"\n⚔️ Твоя мощь: `{user_power}` | Мощь врага: `{opp_power}`\n"
            f"📊 Изменение рейтинга: `{rating_change:+d}`\n"
            f"🏆 Твой новый рейтинг: `{new_rating}`"
        )

        pvp_kb = [
            [InlineKeyboardButton(text="⚔️ Искать еще бой", callback_data="action_find_pvp")],
            [InlineKeyboardButton(text="⬅️ Назад в PVP меню", callback_data="action_pvp_menu")]
        ]
        try:
            await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=pvp_kb))
        except Exception:
            await callback.message.answer(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=pvp_kb))
        await callback.answer()

    elif action == "action_guild_menu":
        cursor.execute("SELECT guild FROM users WHERE user_id = ?", (user_id,))
        res = cursor.fetchone()
        user_guild = res[0] if res and res[0] and res[0] != 'Нет' else "Нет"
        conn.close()
        
        guild_kb = [
            [InlineKeyboardButton(text="📜 Список гильдий", callback_data="action_guild_list")],
            [InlineKeyboardButton(text="🛠 Как создать гильдию", callback_data="action_guild_create_info")],
            [InlineKeyboardButton(text="🚪 Покинуть гильдию", callback_data="action_leave_guild")],
            [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="action_menu")]
        ]
        
        text = (
            f"🛡 **Меню Гильдий**\n\n"
            f"Твоя текущая гильдия: `{user_guild}`\n\n"
            f"Создать гильдию: `/createguild Название`"
        )
        try:
            await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=guild_kb))
        except Exception:
            await callback.message.answer(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=guild_kb))
        await callback.answer()
        
    elif action == "action_guild_list":
        cursor.execute("SELECT guild_name, members_count FROM guilds")
        guilds = cursor.fetchall()
        conn.close()
        
        text = "📜 **Список созданных гильдий:**\n\n"
        if guilds:
            for g_name, members in guilds:
                text += f"• **{g_name}** (Участников: {members})\n"
        else:
            text += "Пока нет ни одной созданной гильдии."
            
        guild_kb = [
            [InlineKeyboardButton(text="⬅️ Назад к гильдиям", callback_data="action_guild_menu")]
        ]
        try:
            await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=guild_kb))
        except Exception:
            await callback.message.answer(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=guild_kb))
        await callback.answer()
        
    elif action == "action_guild_create_info":
        conn.close()
        text = (
            "🛠 **Создание гильдии:**\n\n"
            "Отправь в чат команду:\n"
            "`/createguild ИмяКлана`"
        )
        guild_kb = [
            [InlineKeyboardButton(text="⬅️ Назад к гильдиям", callback_data="action_guild_menu")]
        ]
        try:
            await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=guild_kb))
        except Exception:
            await callback.message.answer(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=guild_kb))
        await callback.answer()

    elif action == "action_leave_guild":
        cursor.execute("SELECT guild FROM users WHERE user_id = ?", (user_id,))
        res = cursor.fetchone()
        
        if not res or res[0] == 'Нет' or res[0] is None:
            conn.close()
            await callback.answer("❌ Ты и так не состоишь ни в какой гильдии!", show_alert=True)
            return
            
        guild_name = res[0]
        cursor.execute("UPDATE users SET guild = 'Нет' WHERE user_id = ?", (user_id,))
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE guild = ?", (guild_name,))
        members_count = cursor.fetchone()[0]
        
        if members_count == 0:
            cursor.execute("DELETE FROM guilds WHERE guild_name = ?", (guild_name,))
        else:
            cursor.execute("UPDATE guilds SET members_count = ? WHERE guild_name = ?", (members_count, guild_name))
            
        conn.commit()
        conn.close()
        
        guild_kb = [
            [InlineKeyboardButton(text="⬅️ Назад к гильдиям", callback_data="action_guild_menu")]
        ]
        text = f"🚪 Ты успешно покинул гильдию **'{guild_name}'**."
        try:
            await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=guild_kb))
        except Exception:
            await callback.message.answer(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=guild_kb))
        await callback.answer("Успешно!", show_alert=False)
        
    elif action == "action_shop":
        conn.close()
        shop_kb = [
            [InlineKeyboardButton(text="🌟 Купить 10 круток (50 Stars)", callback_data="buy_10_rolls")],
            [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="action_menu")]
        ]
        text = (
            "💎 **Донат-магазин (Telegram Stars):**\n\n"
            "Пополни запас круток за звёзды и выбивай легендарных бойцов ранга SS!\n\n"
            "• **Товар:** Набор из 10 круток\n"
            "• **Цена:** 🌟 50 Stars"
        )
        try:
            await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=shop_kb))
        except Exception:
            await callback.message.answer(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=shop_kb))
        await callback.answer()

    elif action == "buy_10_rolls":
        conn.close()
        prices = [LabeledPrice(label="10 круток в гаче", amount=50)]
        await bot.send_invoice(
            chat_id=user_id,
            title="Пак из 10 круток",
            description="Пополнение запаса круток для призыва аниме-персонажей!",
            payload="rolls_10_payload",
            provider_token="",
            currency="XTR",
            prices=prices
        )
        await callback.answer()

# ==================== ОБРАБОТКА ОПЛАТЫ ЗВЁЗДАМИ ====================
@dp.pre_checkout_query()
async def pre_checkout_query_handler(pre_checkout_query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.successful_payment)
async def successful_payment_handler(message: types.Message):
    payment_info = message.successful_payment
    user_id = message.from_user.id
    
    if payment_info.invoice_payload == "rolls_10_payload":
        conn = sqlite3.connect("gacha_bot.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET rolls = rolls + 10 WHERE user_id = ?", (user_id,))
        conn.commit()
        
        cursor.execute("SELECT rolls FROM users WHERE user_id = ?", (user_id,))
        new_rolls = cursor.fetchone()[0]
        conn.close()
        
        await message.answer(
            f"✅ **Оплата прошла успешно!** 🎉\n\n"
            f"Тебе зачислено **+10 круток**.\n"
            f"🎟 Твой текущий баланс круток: `{new_rolls}`",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(user_id == ADMIN_ID)
        )

# ==================== РУЧНОЕ ДОБАВЛЕНИЕ КАРТЫ В КОЛОДУ ====================
@dp.callback_query(F.data.startswith("add_card_"))
async def process_add_card_to_deck(callback: types.CallbackQuery):
    card_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id

    conn = sqlite3.connect("gacha_bot.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM pvp_deck WHERE user_id = ?", (user_id,))
    deck_count = cursor.fetchone()[0]

    if deck_count >= 5:
        conn.close()
        await callback.answer("⚠️ В колоде максимум карт (5/5)!", show_alert=True)
        return

    cursor.execute("SELECT * FROM pvp_deck WHERE user_id = ? AND card_id = ?", (user_id, card_id))
    if cursor.fetchone():
        conn.close()
        await callback.answer("⚠️ Эта карта уже в сетапе!", show_alert=True)
        return

    cursor.execute("INSERT INTO pvp_deck (user_id, card_id) VALUES (?, ?)", (user_id, card_id))
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM pvp_deck WHERE user_id = ?", (user_id,))
    new_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT id, character_name, tier, atk FROM inventory 
        WHERE user_id = ? 
        ORDER BY CASE tier WHEN 'SS' THEN 1 WHEN 'S' THEN 2 WHEN 'A' THEN 3 WHEN 'B' THEN 4 ELSE 5 END ASC 
        LIMIT 15
    """, (user_id,))
    inventory_items = cursor.fetchall()
    conn.close()

    if new_count >= 5:
        await callback.answer("✅ Колода полностью укомплектована (5/5)!", show_alert=True)
    else:
        await callback.answer(f"✅ Добавлено! В колоде: {new_count}/5", show_alert=False)

    text = f"🛠 **Выбери карту для сетапа ({new_count}/5):**\nНажми на карту ниже:"
    kb_rows = []
    for item_id, name, tier, atk in inventory_items:
        kb_rows.append([InlineKeyboardButton(text=f"[{tier}] {name} (⚔️{atk})", callback_data=f"add_card_{item_id}")])
    
    kb_rows.append([InlineKeyboardButton(text="👀 Посмотреть колоду", callback_data="action_view_deck")])
    kb_rows.append([InlineKeyboardButton(text="⬅️ Назад в PVP меню", callback_data="action_pvp_menu")])

    try:
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    except Exception:
        pass
# ==================== ПАРТНЕРСКАЯ ПРОГРАММА ====================
@router.callback_query(F.data == "action_referral")
async def referral_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    bot_info = await bot.get_me()
    
    conn = sqlite3.connect("gacha_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT referral_count FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    ref_count = row[0] if row and row[0] is not None else 0
    ref_link = f"https://t.me/{bot_info.username}?start=ref{user_id}"
    
    text = (
        f"🤝 **Партнерская программа**\n\n"
        f"Зовите друзей в гачу и получайте крутки для призыва!\n"
        f"• За каждого друга: **+2 крутки** 🎫\n"
        f"• Друг тоже получает бонус: **+7 круток** 🎁\n\n"
        f"👥 Приглашено друзей: **{ref_count}**\n\n"
        f"🔗 Ваша реферальная ссылка:\n`{ref_link}`"
    )
    
    await callback.message.edit_text(text, parse_mode="Markdown")
    await callback.answer()

# ==================== ЗАПУСК БОТА ====================
async def main():
    print("🚀 Гача-бот со всеми фичами (арена, противники, звезды, кнопка выхода из гильдии) запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
