import os
import httpx
import logging
from gigachat import GigaChat
from deep_translator import GoogleTranslator
from dotenv import load_dotenv

load_dotenv()

# --- КОНФИГУРАЦИЯ ---
API_KEY = os.getenv("FOOD_API_KEY")
BASE_URL = "https://api.spoonacular.com/recipes/complexSearch"

# Инициализация переводчиков
ru_to_en = GoogleTranslator(source='ru', target='en')
en_to_ru = GoogleTranslator(source='en', target='ru')

# Инициализация GigaChat
# credentials — это ваши AuthData из личного кабинета Сбера
giga_client = GigaChat(
    credentials=os.getenv("GIGACHAT_CREDENTIALS"), 
    verify_ssl_certs=False
)

# --- ФУНКЦИИ ---

async def get_nutrition_estimate(recipe_title, ingredients_list):
    """Запрашивает расчет КБЖУ у GigaChat"""
    if not ingredients_list:
        return "КБЖУ не определено"
    
    try:
        prompt = (
            f"Ты диетолог. Рассчитай примерное КБЖУ для рецепта '{recipe_title}' на 1 порцию. "
            f"Ингредиенты: {ingredients_list}. "
            f"Ответь строго одной строкой: 🔥 Калории: X ккал | 🥩 Белки: X г | 🥑 Жиры: X г | 🍞 Углеводы: X г. "
            f"Не пиши лишнего текста."
        )
        
        # Библиотека GigaChat работает синхронно, вызываем её напрямую
        response = giga_client.chat(prompt)
        return response.choices[0].message.content
    except Exception as e:
        logging.error(f"Ошибка GigaChat: {e}")
        return "📊 КБЖУ: сервис временно недоступен"

async def search_recipes(ingredients: str, diet: str = None, max_time: int = None, number: int = 3):
    """Ищет рецепты в Spoonacular"""
    try:
        # 1. Перевод запроса на английский
        try:
            # Убираем запятые и переводим
            clean_ingredients = ingredients.replace(",", " ")
            translated_query = ru_to_en.translate(clean_ingredients)
        except Exception as e:
            logging.error(f"Ошибка перевода ввода: {e}")
            translated_query = ingredients

        # 2. Параметры для Spoonacular
        params = {
            "apiKey": API_KEY,
            "query": translated_query, 
            "instructionsRequired": True,
            "addRecipeInformation": True, # Нужно для времени приготовления
            "fillIngredients": True,      # Нужно для списка продуктов для GigaChat
            "sort": "max-used-ingredients",
            "number": number
        }
        
        if diet and diet != "None": 
            params["diet"] = diet
        if max_time: 
            params["maxReadyTime"] = max_time

        # 3. Запрос к API
        async with httpx.AsyncClient() as client:
            response = await client.get(BASE_URL, params=params, timeout=15.0)
            response.raise_for_status()
            data = response.json()
            
            if "results" in data and data["results"]:
                for recipe in data["results"]:
                    # Перевод названия каждого рецепта на русский
                    original_title = recipe.get("title", "Unknown Recipe")
                    try:
                        recipe["title_ru"] = en_to_ru.translate(original_title)
                    except Exception:
                        recipe["title_ru"] = original_title
                
                return data
            else:
                return {"results": []}

    except Exception as e:
        logging.error(f"Критическая ошибка в api_client: {e}")
        return None