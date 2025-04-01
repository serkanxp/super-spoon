import os
import logging
import sqlite3
import asyncio
from pathlib import Path
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode, ContentType
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

# Config
load_dotenv(Path('.')/'.env')
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 7945724174  # YOUR TELEGRAM ID HERE
BOT_USERNAME = "@kreditbozori07"

# Init
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# DB Setup
def init_db():
    conn = sqlite3.connect("credit_bot.db", check_same_thread=False)
    cursor = conn.cursor()
    
    # Create users table with username column
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        full_name TEXT,
        username TEXT,
        phone TEXT,
        language TEXT DEFAULT 'uz',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Create applications table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        financing_type TEXT,
        amount TEXT,
        applicant_type TEXT,
        collateral_type TEXT,
        collateral_details TEXT,
        status TEXT DEFAULT 'pending',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    )
    """)
    
    # Try to add username column if it doesn't exist (for existing databases)
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN username TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    conn.commit()
    return conn, cursor

conn, cursor = init_db()

# States
class Form(StatesGroup):
    language = State()
    full_name = State()
    financing_type = State()
    amount = State()
    amount_input = State()
    applicant_type = State()
    collateral_type = State()
    collateral_details = State()
    phone = State()

# Texts
TEXTS = {
    "uz": {
        "welcome": "👋 Assalomu alaykum! Kredit botiga xush kelibsiz. Tilni tanlang:",
        "full_name": "📝 Familiya va ismingizni kiriting:",
        "financing_type": "💵 Qanday turdagi moliyalashtirishni xohlaysiz?",
        "amount": "💰 Qancha miqdorda mablag' kerak?",
        "applicant_type": "👤 Kim uchun moliyalashtirish kerak?",
        "collateral_type": "🏠 Qanday garov kafolati berasiz?",
        "collateral_house": "🏡 Ko'chmas mulk haqida ma'lumot kiriting (manzil, maydoni, qimmatligi):",
        "collateral_car": "🚗 Transport vositasi haqida ma'lumot kiriting (markasi, modeli, yili, qimmatligi):",
        "phone": "📱 Telefon raqamingizni kiriting yoki 'Raqamni yuborish' tugmasini bosing:",
        "phone_button": "📱 Raqamni yuborish",
        "finish": f"✅ Ushbu xizmat bepul, bank xodimi tez orada siz bilan bog'lanadi. Rahmat! {BOT_USERNAME}",
        "large_amount": "💼 10 mlrd so'mdan ortiq kreditlar uchun korporativ kreditlash bo'yicha menejer siz bilan shaxsan bog'lanadi.",
        "contact_shared": "✅ Telefon raqamingiz qabul qilindi!",
        "admin_panel": "⚙️ Admin paneli",
        "applications": "📄 Barcha arizalar",
        "back": "🔙 Orqaga",
        "fin_types": {
            "fin_1": "🕌 Islomiy moliyalashtirish 300 000,0 AQSh dollardan",
            "fin_2": "💵 Naqd pul krediti 300 mln so'mgacha",
            "fin_3": "🏦 300 mln so'mdan ortiq kredit"
        },
        "amount_types": {
            "amt_1": "💵 Naqd pul krediti 300 mln so'mgacha",
            "amt_3": "🏢 Aylanma mablag'larni to'ldirish yoki asosiy vositalarni sotib olish uchun 10 mlrd so'mgacha",
            "amt_4": "🕌 Islomiy moliyalashtirish 300 000,0 AQSh dollardan",
            "amt_5": "🏦 Turli maqsadlar uchun 10 mlrd so'mdan ortiq moliyalashtirish"
        },
        "app_types": {
            "app_1": "👤 O'zim uchun (jismoniy shaxs)",
            "app_2": "📝 Patent, mening yakka tartibdagi tadbirkorligim bor",
            "app_3": "🏢 Firma uchun"
        },
        "col_types": {
            "col_1": "🏠 Ko'chmas mulk",
            "col_2": "🚗 Transport vositalari"
        }
    },
    "ru": {
        "welcome": "👋 Здравствуйте! Добро пожаловать в кредитного бота. Выберите язык:",
        "full_name": "📝 Введите вашу фамилию и имя:",
        "financing_type": "💵 Какой вид финансирования вы хотите?",
        "amount": "💰 Сколько вы хотите?",
        "applicant_type": "👤 На физическое лицо или на фирму хотите?",
        "collateral_type": "🏠 В залог что хотите предоставить?",
        "collateral_house": "🏡 Введите информацию о недвижимости (адрес, площадь, стоимость):",
        "collateral_car": "🚗 Введите информацию о транспортном средстве (марка, модель, год, стоимость):",
        "phone": "📱 Введите ваш телефонный номер или нажмите кнопку 'Отправить номер':",
        "phone_button": "📱 Отправить номер",
        "finish": f"✅ Данная услуга бесплатно, сотрудник банка свяжется с Вами в ближайшее время для консультации, спасибо Вам! {BOT_USERNAME}",
        "large_amount": "💼 Для кредитов свыше 10 млрд сум: С Вами лично свяжется руководитель по корпоративному кредитованию.",
        "contact_shared": "✅ Ваш номер телефона принят!",
        "admin_panel": "⚙️ Админ панель",
        "applications": "📄 Все заявки",
        "back": "🔙 Назад",
        "fin_types": {
            "fin_1": "🕌 Исламское финансирование от 300 000,0 Долл США",
            "fin_2": "💵 Кредит наличными до 300 млн сум",
            "fin_3": "🏦 Кредит свыше 300 млн сум"
        },
        "amount_types": {
            "amt_1": "💵 Кредит наличными до 300 млн сумм",
            "amt_3": "🏢 Кредит на пополнение оборотных средств, или на приобретение основных средств до 10 млрд сумм",
            "amt_4": "🕌 Исламское финансирование от 300 000,0 Долл США",
            "amt_5": "🏦 Финансирование свыше 10 млрд сумм на разные цели"
        },
        "app_types": {
            "app_1": "👤 На Себя как физ лицо",
            "app_2": "📝 На Патент, у меня частное предпринимательство",
            "app_3": "🏢 На фирму хочу"
        },
        "col_types": {
            "col_1": "🏠 Недвижимость",
            "col_2": "🚗 Транспортные средства"
        }
    }
}

# Keyboards
def get_language_keyboard():
    kb = InlineKeyboardBuilder()
    kb.add(
        InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang_uz"),
        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")
    )
    return kb.as_markup()

def get_phone_keyboard(lang: str):
    kb = ReplyKeyboardBuilder()
    kb.add(types.KeyboardButton(
        text=TEXTS[lang]["phone_button"],
        request_contact=True
    ))
    kb.adjust(1)
    return kb.as_markup(resize_keyboard=True)

def get_options_keyboard(options: dict, lang: str, include_back=True):
    kb = InlineKeyboardBuilder()
    for key, text in options.items():
        kb.add(InlineKeyboardButton(text=text, callback_data=key))
    if include_back:
        kb.add(InlineKeyboardButton(text=TEXTS[lang]["back"], callback_data="back"))
    kb.adjust(1)
    return kb.as_markup()

def get_admin_keyboard(lang: str):
    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text=TEXTS[lang]["applications"], callback_data="admin_applications"))
    kb.adjust(1)
    return kb.as_markup()

def get_back_keyboard(lang: str):
    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text=TEXTS[lang]["back"], callback_data="admin_back"))
    return kb.as_markup()

# Handlers
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    cursor.execute("SELECT language FROM users WHERE user_id = ?", (message.from_user.id,))
    user = cursor.fetchone()
    
    if user:
        lang = user[0]
        if message.from_user.id == ADMIN_ID:
            await message.answer(TEXTS[lang]["admin_panel"], reply_markup=get_admin_keyboard(lang))
            return
        
        await message.answer(TEXTS[lang]["full_name"], reply_markup=ReplyKeyboardRemove())
        await state.set_state(Form.full_name)
    else:
        # Store username when user first starts the bot
        cursor.execute(
            "INSERT INTO users (user_id, username, language) VALUES (?, ?, ?)",
            (message.from_user.id, message.from_user.username, 'uz')
        )
        conn.commit()
        await message.answer(TEXTS["uz"]["welcome"], reply_markup=get_language_keyboard())
        await state.set_state(Form.language)

@dp.callback_query(F.data.startswith("lang_"))
async def process_language(callback: CallbackQuery, state: FSMContext):
    lang = callback.data.split("_")[1]
    
    # Update username when setting language
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, username, language) VALUES (?, ?, ?)",
        (callback.from_user.id, callback.from_user.username, lang)
    )
    cursor.execute(
        "UPDATE users SET username = ?, language = ? WHERE user_id = ?",
        (callback.from_user.username, lang, callback.from_user.id)
    )
    conn.commit()
    
    await callback.message.edit_text(TEXTS[lang]["full_name"])
    await state.set_state(Form.full_name)
    await callback.answer()

@dp.message(Form.full_name)
async def process_full_name(message: Message, state: FSMContext):
    cursor.execute("SELECT language FROM users WHERE user_id = ?", (message.from_user.id,))
    lang = cursor.fetchone()[0]
    
    cursor.execute(
        "UPDATE users SET full_name = ? WHERE user_id = ?",
        (message.text, message.from_user.id)
    )
    conn.commit()
    
    await message.answer(
        TEXTS[lang]["financing_type"],
        reply_markup=get_options_keyboard(TEXTS[lang]["fin_types"], lang)
    )
    await state.set_state(Form.financing_type)

@dp.callback_query(Form.financing_type, F.data == "back")
async def back_from_financing_type(callback: CallbackQuery, state: FSMContext):
    cursor.execute("SELECT language FROM users WHERE user_id = ?", (callback.from_user.id,))
    lang = cursor.fetchone()[0]
    
    await callback.message.edit_text(TEXTS[lang]["full_name"])
    await state.set_state(Form.full_name)
    await callback.answer()

@dp.callback_query(Form.financing_type)
async def process_financing_type(callback: CallbackQuery, state: FSMContext):
    cursor.execute("SELECT language FROM users WHERE user_id = ?", (callback.from_user.id,))
    lang = cursor.fetchone()[0]
    
    await state.update_data(financing_type=callback.data)
    
    # For all financing types, show both options and manual input
    kb = InlineKeyboardBuilder()
    
    # Add predefined amount options
    for key, text in TEXTS[lang]["amount_types"].items():
        if callback.data == "fin_1" and key != "amt_4":
            continue  # Only show Islamic financing amount for fin_1
        if callback.data == "fin_2" and key not in ["amt_1", "amt_2"]:
            continue  # Only show cash credit amounts for fin_2
        if callback.data == "fin_3" and key not in ["amt_3", "amt_5"]:
            continue  # Only show large amounts for fin_3
            
        kb.add(InlineKeyboardButton(text=text, callback_data=key))
    
    # Add manual input option
    kb.add(InlineKeyboardButton(
        text="Ввести сумму вручную" if lang == "ru" else "Summani qo'lda kiriting",
        callback_data="enter_amount"
    ))
    
    # Add back button
    kb.add(InlineKeyboardButton(
        text=TEXTS[lang]["back"],
        callback_data="back"
    ))
    
    kb.adjust(1)
    
    await callback.message.edit_text(
        TEXTS[lang]["amount"],
        reply_markup=kb.as_markup()
    )
    await state.set_state(Form.amount)
    await callback.answer()

@dp.callback_query(Form.amount, F.data == "enter_amount")
async def enter_amount_manually(callback: CallbackQuery, state: FSMContext):
    cursor.execute("SELECT language FROM users WHERE user_id = ?", (callback.from_user.id,))
    lang = cursor.fetchone()[0]
    
    data = await state.get_data()
    financing_type = data.get('financing_type', '')
    
    # Set different minimum amounts based on financing type
    if financing_type == "fin_1":
        min_amount = 300000
        instruction = ("Введите сумму в долларах США (минимум 300,000):" 
                      if lang == "ru" 
                      else "AQSh dollarida summani kiriting (kamida 300,000):")
    elif financing_type == "fin_2":
        min_amount = 1
        instruction = ("Введите сумму в сумах или долларах:" 
                      if lang == "ru" 
                      else "So'm yoki dollar miqdorini kiriting:")
    else:  # fin_3
        min_amount = 300000000
        instruction = ("Введите сумму в сумах (минимум 300 млн):" 
                      if lang == "ru" 
                      else "So'mda summani kiriting (kamida 300 mln):")
    
    await state.update_data(min_amount=min_amount)
    await callback.message.edit_text(instruction)
    await state.set_state(Form.amount_input)
    await callback.answer()

@dp.message(Form.amount_input)
async def process_amount_input(message: Message, state: FSMContext):
    cursor.execute("SELECT language FROM users WHERE user_id = ?", (message.from_user.id,))
    lang = cursor.fetchone()[0]
    
    data = await state.get_data()
    min_amount = data.get('min_amount', 0)
    financing_type = data.get('financing_type', '')
    
    try:
        # Parse the entered amount
        amount = float(message.text.replace(",", "."))
        
        # Validate based on financing type
        if financing_type == "fin_1" and amount < 300000:
            error_msg = ("❌ Минимальная сумма для исламского финансирования - 300,000 USD. Пожалуйста, введите корректную сумму:" 
                        if lang == "ru" 
                        else "❌ Islomiy moliyalashtirish uchun minimal summa 300,000 AQSh dollar. Iltimos, to'g'ri summani kiriting:")
        elif financing_type == "fin_2" and amount <= 0:
            error_msg = ("❌ Сумма должна быть больше 0. Пожалуйста, введите корректную сумму:" 
                        if lang == "ru" 
                        else "❌ Summa 0 dan katta bo'lishi kerak. Iltimos, to'g'ri summani kiriting:")
        elif financing_type == "fin_3" and amount < 300000000:
            error_msg = ("❌ Минимальная сумма для этого типа кредита - 300 млн сум. Пожалуйста, введите корректную сумму:" 
                        if lang == "ru" 
                        else "❌ Ushbu turdagi kredit uchun minimal summa 300 mln so'm. Iltimos, to'g'ri summani kiriting:")
        else:
            # Amount is valid
            await state.update_data(amount=f"{amount}")
            
            # Determine which applicant types to show
            if financing_type in ["fin_1", "fin_3"] or amount >= 10000000000:  # 10 billion
                filtered_app_types = {
                    "app_3": TEXTS[lang]["app_types"]["app_3"]
                }
            else:
                filtered_app_types = TEXTS[lang]["app_types"]
            
            await message.answer(
                TEXTS[lang]["applicant_type"],
                reply_markup=get_options_keyboard(filtered_app_types, lang)
            )
            await state.set_state(Form.applicant_type)
            return
        
        await message.answer(error_msg)
        return
        
    except ValueError:
        error_msg = ("❌ Пожалуйста, введите числовое значение (например: 300000 или 350000.50):" 
                    if lang == "ru" 
                    else "❌ Iltimos, raqamli qiymat kiriting (masalan: 300000 yoki 350000.50):")
        await message.answer(error_msg)

@dp.callback_query(Form.amount, F.data == "back")
async def back_from_amount(callback: CallbackQuery, state: FSMContext):
    cursor.execute("SELECT language FROM users WHERE user_id = ?", (callback.from_user.id,))
    lang = cursor.fetchone()[0]
    
    await callback.message.edit_text(
        TEXTS[lang]["financing_type"],
        reply_markup=get_options_keyboard(TEXTS[lang]["fin_types"], lang)
    )
    await state.set_state(Form.financing_type)
    await callback.answer()

@dp.callback_query(Form.amount)
async def process_amount(callback: CallbackQuery, state: FSMContext):
    cursor.execute("SELECT language FROM users WHERE user_id = ?", (callback.from_user.id,))
    lang = cursor.fetchone()[0]
    
    await state.update_data(amount=callback.data)
    
    data = await state.get_data()
    financing_type = data.get('financing_type', '')
    
    # For Islamic financing or large amounts, only show "For firm" option
    if financing_type == "fin_1" or callback.data in ["amt_3", "amt_5", "fin_3"]:
        kb = InlineKeyboardBuilder()
        kb.add(InlineKeyboardButton(
            text=TEXTS[lang]["app_types"]["app_3"],
            callback_data="app_3"
        ))
        kb.add(InlineKeyboardButton(
            text=TEXTS[lang]["back"],
            callback_data="back"
        ))
        await callback.message.edit_text(
            TEXTS[lang]["applicant_type"],
            reply_markup=kb.as_markup()
        )
    else:
        await callback.message.edit_text(
            TEXTS[lang]["applicant_type"],
            reply_markup=get_options_keyboard(TEXTS[lang]["app_types"], lang)
        )
    await state.set_state(Form.applicant_type)
    await callback.answer()

@dp.callback_query(Form.applicant_type, F.data == "back")
async def back_from_applicant_type(callback: CallbackQuery, state: FSMContext):
    cursor.execute("SELECT language FROM users WHERE user_id = ?", (callback.from_user.id,))
    lang = cursor.fetchone()[0]
    
    await callback.message.edit_text(
        TEXTS[lang]["amount"],
        reply_markup=get_options_keyboard(TEXTS[lang]["amount_types"], lang)
    )
    await state.set_state(Form.amount)
    await callback.answer()

@dp.callback_query(Form.applicant_type)
async def process_applicant_type(callback: CallbackQuery, state: FSMContext):
    cursor.execute("SELECT language FROM users WHERE user_id = ?", (callback.from_user.id,))
    lang = cursor.fetchone()[0]
    
    await state.update_data(applicant_type=callback.data)
    await callback.message.edit_text(
        TEXTS[lang]["collateral_type"],
        reply_markup=get_options_keyboard(TEXTS[lang]["col_types"], lang)
    )
    await state.set_state(Form.collateral_type)
    await callback.answer()

@dp.callback_query(Form.collateral_type, F.data == "back")
async def back_from_collateral_type(callback: CallbackQuery, state: FSMContext):
    cursor.execute("SELECT language FROM users WHERE user_id = ?", (callback.from_user.id,))
    lang = cursor.fetchone()[0]
    
    # Get current data to determine if we need to show limited options
    data = await state.get_data()
    financing_type = data.get('financing_type', '')
    amount = data.get('amount', '')
    
    special_cases = ["fin_1", "fin_3", "amt_3", "amt_5"]
    
    if financing_type in special_cases or amount in special_cases:
        filtered_app_types = {
            "app_3": TEXTS[lang]["app_types"]["app_3"]
        }
    else:
        filtered_app_types = TEXTS[lang]["app_types"]
    
    await callback.message.edit_text(
        TEXTS[lang]["applicant_type"],
        reply_markup=get_options_keyboard(filtered_app_types, lang)
    )
    await state.set_state(Form.applicant_type)
    await callback.answer()

@dp.callback_query(Form.collateral_type)
async def process_collateral_type(callback: CallbackQuery, state: FSMContext):
    cursor.execute("SELECT language FROM users WHERE user_id = ?", (callback.from_user.id,))
    lang = cursor.fetchone()[0]
    
    collateral_type = callback.data
    await state.update_data(collateral_type=collateral_type)
    
    if collateral_type == "col_1":
        await callback.message.answer(TEXTS[lang]["collateral_house"])
    else:
        await callback.message.answer(TEXTS[lang]["collateral_car"])
    
    await state.set_state(Form.collateral_details)
    await callback.answer()

@dp.message(Form.collateral_details, F.text == TEXTS["uz"]["back"] or F.text == TEXTS["ru"]["back"])
async def back_from_collateral_details(message: Message, state: FSMContext):
    cursor.execute("SELECT language FROM users WHERE user_id = ?", (message.from_user.id,))
    lang = cursor.fetchone()[0]
    
    await message.answer(
        TEXTS[lang]["collateral_type"],
        reply_markup=get_options_keyboard(TEXTS[lang]["col_types"], lang)
    )
    await state.set_state(Form.collateral_type)

@dp.message(Form.collateral_details)
async def process_collateral_details(message: Message, state: FSMContext):
    cursor.execute("SELECT language FROM users WHERE user_id = ?", (message.from_user.id,))
    lang = cursor.fetchone()[0]
    
    await state.update_data(collateral_details=message.text)
    await message.answer(
        TEXTS[lang]["phone"],
        reply_markup=get_phone_keyboard(lang)
    )
    await state.set_state(Form.phone)

@dp.message(Form.phone, F.content_type == ContentType.TEXT)
async def prevent_manual_phone(message: Message):
    cursor.execute("SELECT language FROM users WHERE user_id = ?", (message.from_user.id,))
    lang = cursor.fetchone()[0]
    
    if message.text == TEXTS[lang]["back"]:
        await message.answer(
            TEXTS[lang]["collateral_type"],
            reply_markup=get_options_keyboard(TEXTS[lang]["col_types"], lang)
        )
        await Form.collateral_type.set()
    else:
        await message.answer(
            "⚠️ Iltimos, telefon raqamingizni 'Raqamni yuborish' tugmasi orqali yuboring!" if lang == "uz" 
            else "⚠️ Пожалуйста, отправьте номер телефона с помощью кнопки 'Отправить номер'!",
            reply_markup=get_phone_keyboard(lang)
        )

@dp.message(Form.phone, F.content_type == ContentType.CONTACT)
async def process_phone(message: Message, state: FSMContext):
    cursor.execute("SELECT language FROM users WHERE user_id = ?", (message.from_user.id,))
    lang = cursor.fetchone()[0]
    
    phone = message.contact.phone_number
    
    try:
        # Update user phone
        cursor.execute(
            "UPDATE users SET phone = ? WHERE user_id = ?",
            (phone, message.from_user.id)
        )
        
        # Get all data
        data = await state.get_data()
        
        # Save application
        cursor.execute(
            """INSERT INTO applications 
            (user_id, financing_type, amount, applicant_type, collateral_type, collateral_details, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (message.from_user.id, data['financing_type'], data['amount'], 
             data['applicant_type'], data['collateral_type'], data['collateral_details'], 'pending')
        )
        conn.commit()
        
        # Send confirmation to user
        await message.answer(TEXTS[lang]["contact_shared"], reply_markup=ReplyKeyboardRemove())
        await message.answer(TEXTS[lang]["finish"])
        
        if data['amount'] in ['amt_5', 'fin_3']:
            await message.answer(TEXTS[lang]["large_amount"])
        
        # Prepare admin notification
        user_data = cursor.execute(
            "SELECT full_name, phone, language FROM users WHERE user_id = ?", 
            (message.from_user.id,)
        ).fetchone()
        
        collateral_type_text = TEXTS[user_data[2]]['col_types'].get(data['collateral_type'], data['collateral_type'])
        
        app_text = (
            "📌 Yangi ariza!\n\n" if user_data[2] == "uz" else "📌 Новая заявка!\n\n"
            f"👤 Ism: {user_data[0]}\n"
            f"📞 Tel: {user_data[1]}\n"
            f"💳 Tur: {TEXTS[user_data[2]]['fin_types'].get(data['financing_type'], data['financing_type'])}\n"
            f"💰 Summa: {TEXTS[user_data[2]]['amount_types'].get(data['amount'], data['amount'])}\n"
            f"🏛 Tur: {TEXTS[user_data[2]]['app_types'].get(data['applicant_type'], data['applicant_type'])}\n"
            f"🏠 Garov turi: {collateral_type_text}\n"
            f"📝 Garov haqida: {data['collateral_details']}"
        )
        
        await bot.send_message(ADMIN_ID, app_text)
        
    except Exception as e:
        logging.error(f"Database error: {e}")
        await message.answer(
            "❌ Xatolik yuz berdi! Iltimos, qaytadan urinib ko'ring." if lang == "uz" 
            else "❌ Произошла ошибка! Пожалуйста, попробуйте снова."
        )
    finally:
        await state.clear()

@dp.callback_query(F.data == "admin_applications")
async def admin_applications(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⚠️ Ruxsat yo'q!", show_alert=True)
        return
    
    cursor.execute("SELECT language FROM users WHERE user_id = ?", (callback.from_user.id,))
    row = cursor.fetchone()
    lang = row[0] if row else "uz"
    
    # Query now includes username
    cursor.execute("""
    SELECT a.id, u.full_name, u.username, a.financing_type, a.amount, a.applicant_type, 
           a.collateral_type, a.collateral_details, a.status, a.created_at 
    FROM applications a
    JOIN users u ON a.user_id = u.user_id
    ORDER BY a.created_at DESC
    """)
    applications = cursor.fetchall()
    
    if not applications:
        await callback.message.edit_text(
            "🙅‍♂️ Hozircha arizalar mavjud emas!" if lang == "uz" 
            else "🙅‍♂️ Нет доступных заявок!",
            reply_markup=get_back_keyboard(lang)
        )
        return
    
    apps_text = "📄 Barcha arizalar:\n\n" if lang == "uz" else "📄 Все заявки:\n\n"
    
    for app in applications:
        (app_id, full_name, username, financing_type, amount, applicant_type, 
         collateral_type, collateral_details, status, created_at) = app
        
        status_emoji = "✅" if status == "approved" else "❌" if status == "rejected" else "🕒"
        
        financing_text = TEXTS[lang]["fin_types"].get(financing_type, financing_type)
        amount_text = TEXTS[lang]["amount_types"].get(amount, amount)
        applicant_text = TEXTS[lang]["app_types"].get(applicant_type, applicant_type)
        collateral_text = TEXTS[lang]["col_types"].get(collateral_type, collateral_type)
        
        username_display = f"@{username}" if username else "Yo'q" if lang == "uz" else "Нет"
        
        apps_text += (
            f"🆔 ID: {app_id}\n"
            f"👤 Ism: {full_name}\n"
            f"📱 Username: {username_display}\n"
            f"💳 Tur: {financing_text}\n"
            f"💰 Summa: {amount_text}\n"
            f"👥 Arizachi: {applicant_text}\n"
            f"📅 Sana: {created_at}\n\n"
        )
    
    await callback.message.edit_text(
        apps_text,
        reply_markup=get_back_keyboard(lang)
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⚠️ Ruxsat yo'q!", show_alert=True)
        return
    
    cursor.execute("SELECT language FROM users WHERE user_id = ?", (callback.from_user.id,))
    row = cursor.fetchone()
    lang = row[0] if row else "uz"
    
    await callback.message.edit_text(
        TEXTS[lang]["admin_panel"],
        reply_markup=get_admin_keyboard(lang)
    )
    await callback.answer()

# Start
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())