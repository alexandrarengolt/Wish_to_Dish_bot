import asyncio
import logging
import aiohttp
import os
import sys
import ssl
from aiogram.client.session.aiohttp import AiohttpSession
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from api_client import search_recipes

# 1. Фикс для Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# 2. Настройка безопасного соединения (пропускаем проверку сертификатов для Win)
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

connector = aiohttp.TCPConnector(ssl=ssl_context)
# Инициализируем сессию и бота правильно
session = AiohttpSession(connector=connector)
bot = Bot(token=BOT_TOKEN, session=session)
dp = Dispatcher()

# 3. Инициализация сессии и бота (ТОЛЬКО ОДИН РАЗ)
session = AiohttpSession(api_kwargs={"ssl": ssl_context})
bot = Bot(token=BOT_TOKEN, session=session)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я бот-помощник для поиска рецептов. 👨‍🍳\n"
        "Пришлите мне список продуктов через запятую, и я найду рецепт!\n"
    )

@dp.message()
async def handle_ingredients(message: Message):
    await message.answer(f"Ищу лучшие рецепты, где есть: {message.text}...")
    
    data = await search_recipes(message.text)
    
    if not data or not data.get("results"):
        await message.answer("К сожалению, ничего не нашлось. Попробуйте изменить список продуктов.")
        return

    for recipe in data["results"]:
        # Используем наше новое поле с русским названием
            title = recipe.get("title_ru", "Без названия")
        
        # Ссылка на рецепт
            source_url = recipe.get("sourceUrl", "#")
            image = recipe.get("image")
            ready_in = recipe.get("readyInMinutes", "??")
        
            caption = (
                f"🍴 *{title}*\n"
                f"⏱ Время приготовления: {ready_in} мин.\n"
                f"🔗 [Открыть рецепт]({source_url})")
        
            if image:
                await message.answer_photo(photo=image, caption=caption, parse_mode="Markdown")
            else:
                await message.answer(caption, parse_mode="Markdown")

async def main():
    print("Бот запущен и готов к работе...")
    # Удаляем вебхуки, чтобы бот не читал старые сообщения при запуске
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот выключен")