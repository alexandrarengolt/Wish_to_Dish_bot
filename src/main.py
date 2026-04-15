import asyncio
import logging
import os
import sys
import ssl
import aiohttp
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F # Важно: импортируем F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from api_client import search_recipes
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()
BOT_TOKEN = "8792816956:AAGia1B4_ThRsgHzf9Yy-SzCZ9NPGFRnAG4"

dp = Dispatcher()

user_history = {}
user_sessions = {}
messages_to_delete = {}

# 1. Кнопки (Reply Keyboard)
def get_yes_no_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Да, давай еще!"), KeyboardButton(text="Нет, спасибо")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

# 1. Обработчик команды /start
@dp.message(Command("start"))
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("Привет! Я ИИ-повар. Пришли мне список продуктов через запятую.")

@dp.message(F.text == "Да, давай еще!")
async def handle_more(message: Message, bot: Bot):
    user_id = message.from_user.id
    session = user_sessions.get(user_id)
    
    if not session:
        await message.answer("Сначала введите список продуктов.")
        return

    session["limit"] += 3
    current_limit = session["limit"]

    try:
        await bot.delete_message(chat_id=user_id, message_id=message.message_id)
    except: pass

    await message.answer(f"🔄 Уже обновляю список рецептов!")
    
    # Запрашиваем новое количество
    data = await search_recipes(session["ingredients"], number=current_limit)
    await show_recipes(message, data, bot)

@dp.message(F.text == "Нет, спасибо")
async def handle_no(message: Message, bot: Bot):
    user_id = message.from_user.id
    
    # 1. Удаляем только ПОСЛЕДНЕЕ сообщение бота (там, где был вопрос и кнопки)
    # Чтобы в чате не висел вопрос "Хотите еще?", на который уже ответили
    if user_id in messages_to_delete:
        try:
            # Последний ID в списке — это обычно сообщение с вопросом и кнопками
            last_msg_id = messages_to_delete[user_id][-1]
            await bot.delete_message(chat_id=user_id, message_id=last_msg_id)
        except Exception:
            pass
        
        # Очищаем список ID, так как сессия поиска завершена
        messages_to_delete[user_id] = []

    # 2. Удаляем сообщение пользователя "Нет, спасибо" для чистоты (по желанию)
    try:
        await bot.delete_message(chat_id=user_id, message_id=message.message_id)
    except:
        pass

    # 3. Отправляем финальный текст и скрываем клавиатуру
    await message.answer(
        "Приятного аппетита! 👨‍🍳\nРецепты выше сохранены в истории чата.",
        reply_markup=ReplyKeyboardRemove()
    )
    
    # Сбрасываем сессию, чтобы следующий поиск начался с 3 блюд
    if user_id in user_sessions:
        del user_sessions[user_id]

@dp.message()
async def handle_ingredients(message: Message, bot: Bot):
    user_id = message.from_user.id
    # Инициализируем сессию: ставим лимит 3
    user_sessions[user_id] = {"ingredients": message.text, "limit": 3}
    
    await message.answer(f"🔍 Ищу рецепты для: {message.text}...")
    
    # Запрашиваем 3 штуки
    data = await search_recipes(message.text, number=3)
    await show_recipes(message, data, bot)

async def clear_previous_messages(bot: Bot, user_id: int):
    if user_id in messages_to_delete:
        for msg_id in messages_to_delete[user_id]:
            try:
                await bot.delete_message(chat_id=user_id, message_id=msg_id)
            except Exception:
                # Игнорируем ошибки (например, если сообщение уже удалено вручную)
                pass
        messages_to_delete[user_id] = [] # Очищаем список после удаления

# Вспомогательная функция для вывода рецептов
async def show_recipes(message: Message, data, bot: Bot):
    user_id = message.from_user.id
    
    # Сначала удаляем всё старое
    await clear_previous_messages(bot, user_id)
    
    if not data or not data.get("results"):
        msg = await message.answer("Ничего не нашлось.")
        messages_to_delete[user_id] = [msg.message_id]
        return

    new_ids = []
    for recipe in data["results"]:
        title = recipe.get("title_ru", recipe.get("title", "Без названия"))
        caption = f"🍴 *{title}*\n⏱ {recipe.get('readyInMinutes', '??')} мин.\n🔗 [Рецепт]({recipe.get('sourceUrl', '#')})"
        
        try:
            if recipe.get("image"):
                res = await message.answer_photo(photo=recipe.get("image"), caption=caption, parse_mode="Markdown")
            else:
                res = await message.answer(caption, parse_mode="Markdown")
            new_ids.append(res.message_id) # Запоминаем ID сообщения
        except Exception as e:
            logging.error(f"Ошибка отправки сообщения: {e}")

    # Добавляем вопрос с кнопками и сохраняем его ID
    question = await message.answer("Хотите посмотреть другие рецепты?", reply_markup=get_yes_no_kb())
    new_ids.append(question.message_id)
    
    # Сохраняем все новые ID для следующей очистки
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
    print("🚀 Бот запущен и готов к работе!")
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен")