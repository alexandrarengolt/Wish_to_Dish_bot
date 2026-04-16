import asyncio
import logging
import os
import sys
import ssl
import aiohttp
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F, types # Важно: импортируем F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from api_client import search_recipes, get_nutrition_estimate
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

# Импортируем вашу функцию поиска
from api_client import search_recipes

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()
# Рекомендуется использовать os.getenv("BOT_TOKEN") для безопасности
BOT_TOKEN = "8792816956:AAGia1B4_ThRsgHzf9Yy-SzCZ9NPGFRnAG4"

dp = Dispatcher()

# Хранилища данных
user_history = {}
user_sessions = {}
messages_to_delete = {}
user_diet = {}  # Для хранения выбранной диеты {user_id: "diet_name"}

# --- КЛАВИАТУРЫ ---

def get_yes_no_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Да, давай еще!"), KeyboardButton(text="Нет, спасибо")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_diet_keyboard():
    builder = InlineKeyboardBuilder()
    diets = {
        "Vegetarian": "Вегетарианская",
        "Vegan": "Веганская",
        "Gluten Free": "Без глютена",
        "Ketogenic": "Кето",
        "Paleo": "Палео"
    }
    for callback_data, display_name in diets.items():
        builder.row(types.InlineKeyboardButton(
            text=display_name, 
            callback_data=f"diet_{callback_data}")
        )
    builder.row(types.InlineKeyboardButton(text="❌ Сбросить фильтр", callback_data="diet_none"))
    return builder.as_markup()

# --- ОБРАБОТЧИКИ ---

@dp.callback_query(lambda c: c.data.startswith('diet_'))
async def process_diet_selection(callback_query: types.CallbackQuery):
    selected_diet = callback_query.data.split('_')[1]
    user_id = callback_query.from_user.id
    
    if selected_diet == "none":
        user_diet[user_id] = None
        text = "Фильтр диет сброшен. Пришлите список продуктов."
    else:
        user_diet[user_id] = selected_diet
        text = f"Выбрана диета: {selected_diet}. Пришлите список продуктов."
    
    await callback_query.message.edit_text(text)
    await callback_query.answer()

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я ваш ИИ-повар. 👨‍🍳\n"
        "Сначала выбери диету (если нужно), а затем пришли список продуктов через запятую.",
        reply_markup=get_diet_keyboard()
    )

@dp.message(F.text == "Да, давай еще!")
async def handle_more(message: Message, bot: Bot):
    user_id = message.from_user.id
    session = user_sessions.get(user_id)
    
    if not session:
        await message.answer("Сначала введите список продуктов.")
        return

    session["limit"] += 3
    current_limit = session["limit"]
    selected_diet = user_diet.get(user_id)

    try:
        await bot.delete_message(chat_id=user_id, message_id=message.message_id)
    except: pass

    await message.answer(f"🔄 Обновляю список рецептов...")
    
    # Передаем и ингредиенты, и диету, и лимит
    data = await search_recipes(session["ingredients"], diet=selected_diet, number=current_limit)
    await show_recipes(message, data, bot)

@dp.message(F.text == "Нет, спасибо")
async def handle_no(message: Message, bot: Bot):
    user_id = message.from_user.id
    if user_id in messages_to_delete:
        try:
            last_msg_id = messages_to_delete[user_id][-1]
            await bot.delete_message(chat_id=user_id, message_id=last_msg_id)
        except: pass
        messages_to_delete[user_id] = []

    try:
        await bot.delete_message(chat_id=user_id, message_id=message.message_id)
    except: pass

    await message.answer(
        "Приятного аппетита! 👨‍🍳\nРецепты выше сохранены. Для нового поиска просто пришли продукты.",
        reply_markup=ReplyKeyboardRemove()
    )
    if user_id in user_sessions:
        del user_sessions[user_id]

@dp.message()
async def handle_ingredients(message: Message, bot: Bot):
    user_id = message.from_user.id
    selected_diet = user_diet.get(user_id)
    
    # Инициализируем сессию
    user_sessions[user_id] = {"ingredients": message.text, "limit": 3}
    
    diet_text = f" (Диета: {selected_diet})" if selected_diet else ""
    await message.answer(f"🔍 Ищу рецепты для: {message.text}{diet_text}...")
    
    # Вызываем поиск с учетом диеты
    data = await search_recipes(message.text, diet=selected_diet, number=3)
    await show_recipes(message, data, bot)

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

async def clear_previous_messages(bot: Bot, user_id: int):
    if user_id in messages_to_delete:
        for msg_id in messages_to_delete[user_id]:
            try:
                await bot.delete_message(chat_id=user_id, message_id=msg_id)
            except: pass
        messages_to_delete[user_id] = []

async def show_recipes(message: Message, data, bot: Bot):
    user_id = message.from_user.id
    await clear_previous_messages(bot, user_id)
    
    if not data or not data.get("results"):
        msg = await message.answer("Ничего не нашлось. Попробуйте изменить продукты или сбросить диету.", 
                                   reply_markup=get_diet_keyboard())
        messages_to_delete[user_id] = [msg.message_id]
        return

    new_ids = []
    for recipe in data["results"]:
        ingredients_raw = recipe.get("extendedIngredients", [])
        ingredients_text = ", ".join([i.get("original", "") for i in ingredients_raw])
        title = recipe.get("title_ru", recipe.get("title", "Без названия"))
        nutrition = await get_nutrition_estimate(title, ingredients_text)
        caption = f"🍴 *{title}*\n" f"📊 {nutrition}\n" f"⏱ {recipe.get('readyInMinutes', '??')} мин.\n🔗 [Рецепт]({recipe.get('sourceUrl', '#')})"
        
        try:
            if recipe.get("image"):
                res = await message.answer_photo(photo=recipe.get("image"), caption=caption, parse_mode="Markdown")
            else:
                res = await message.answer(caption, parse_mode="Markdown")
            new_ids.append(res.message_id)
        except Exception as e:
            logging.error(f"Ошибка отправки: {e}")

    question = await message.answer("Хотите посмотреть другие рецепты?", reply_markup=get_yes_no_kb())
    new_ids.append(question.message_id)
    messages_to_delete[user_id] = new_ids

async def main():
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    session = AiohttpSession()
    session.connector = aiohttp.TCPConnector(ssl=ssl_context)
    
    bot = Bot(
        token=BOT_TOKEN, 
        session=session,
        default=DefaultBotProperties(parse_mode="Markdown")
    )

    logging.basicConfig(level=logging.INFO)
    print("🚀 Бот запущен!")
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен")