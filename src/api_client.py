import httpx
import os
from dotenv import load_dotenv
from deep_translator import GoogleTranslator

load_dotenv()

API_KEY = os.getenv("FOOD_API_KEY")
BASE_URL = "https://api.spoonacular.com/recipes/complexSearch"

# Переводчики
ru_to_en = GoogleTranslator(source='ru', target='en')
en_to_ru = GoogleTranslator(source='en', target='ru')

async def search_recipes(ingredients: str, diet: str = None, max_time: int = None):
    # 1. Переводим ингредиенты на английский для поиска
    try:
        translated_query = ru_to_en.translate(ingredients)
    except Exception as e:
        print(f"Ошибка перевода (ввод): {e}")
        translated_query = ingredients

    params = {
        "apiKey": API_KEY,
        "includeIngredients": translated_query,
        "addRecipeInformation": True,
        "fillIngredients": True,
        "number": 3
    }
    
    if diet: params["diet"] = diet
    if max_time: params["maxReadyTime"] = max_time

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
            
            # 2. ПЕРЕВОД ОТВЕТОВ: проходим по каждому рецепту и переводим название
            if data.get("results"):
                for recipe in data["results"]:
                    original_title = recipe.get("title", "")
                    try:
                        # Переводим название блюда на русский
                        recipe["title_ru"] = en_to_ru.translate(original_title)
                    except Exception as e:
                        print(f"Ошибка перевода (вывод): {e}")
                        recipe["title_ru"] = original_title
            
            return data
        except Exception as e:
            print(f"Ошибка API: {e}")
            return None