import asyncio
import logging
import os
import sys
import ssl
import aiohttp
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from api_client import search_recipes

# 1. Фикс для Windows (пропускаем предупреждения)
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

dp = Dispatcher()

# Обработчики
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("Привет! Я ваш ИИ-повар. Пришли мне список продуктов")

@dp.message()
async def handle_ingredients(message: Message):
    await message.answer(f"Ищу рецепты для: {message.text}...")
    data = await search_recipes(message.text)
    if not data or not data.get("results"):
        await message.answer("Ничего не нашлось.")
        return

    for recipe in data["results"]:
        title = recipe.get("title_ru", recipe.get("title", "Без названия"))
        caption = f"🍴 *{title}*\n⏱ {recipe.get('readyInMinutes', '??')} мин.\n🔗 [Рецепт]({recipe.get('sourceUrl', '#')})"
        await message.answer_photo(photo=recipe.get("image"), caption=caption, parse_mode="Markdown")

async def main():
    # 1. Настраиваем SSL (фикс для Windows/VPN)
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    # 2. Создаем сессию БЕЗ аргументов в конструкторе
    session = AiohttpSession()
    
    # 3. Ручная настройка коннектора внутри сессии
    # Это обходит ошибку TypeError
    session.connector = aiohttp.TCPConnector(ssl=ssl_context)
    
    # 4. Инициализируем бота
    bot = Bot(
        token=BOT_TOKEN, 
        session=session,
        default=DefaultBotProperties(parse_mode="Markdown")
    )

    logging.basicConfig(level=logging.INFO)
    print("Бот запущен! Ошибка TypeError побеждена.")
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен")