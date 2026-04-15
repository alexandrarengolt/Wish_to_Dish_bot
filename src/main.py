import asyncio
import logging
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
from api_client import search_recipes

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)

# Инициализируем бота и диспетчер
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я бот-помощник для поиска рецептов. 👨‍🍳\n"
        "Пришлите мне список продуктов через запятую, и я найду рецепт!\n\n"
    )

@dp.message()
async def handle_ingredients(message: Message):
    # Уведомляем пользователя, что процесс пошел
    await message.answer(f"Ищу лучшие рецепты, где есть: {message.text}...")
    
    # Вызываем нашу функцию из api_client.py
    data = await search_recipes(message.text)
    
    if not data or not data.get("results"):
        await message.answer("К сожалению, ничего не нашлось. Попробуйте изменить список продуктов.")
        return

    # Перебираем полученные рецепты (мы просили 3 штуки)
    for recipe in data["results"]:
        title = recipe["title"]
        source_url = recipe["sourceUrl"]
        image = recipe["image"]
        ready_in = recipe["readyInMinutes"]
        
        caption = (
            f"🍴 {title}\n"
            f"⏱ Время: {ready_in} мин.\n"
            f"🔗 [Ссылка на рецепт]({source_url})"
        )
        
        await message.answer_photo(photo=image, caption=caption, parse_mode="Markdown")
        
async def main():
    print("Бот запущен и готов к работе...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот выключен")