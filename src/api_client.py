import httpx
import os
from dotenv import load_dotenv
from deep_translator import GoogleTranslator

load_dotenv()

API_KEY = os.getenv("FOOD_API_KEY")
BASE_URL = "https://api.spoonacular.com/recipes/complexSearch"

# Инициализируем переводчики
ru_to_en = GoogleTranslator(source='ru', target='en')
en_to_ru = GoogleTranslator(source='en', target='ru')

async def search_recipes(ingredients: str, diet: str = None, max_time: int = None):
    try:
        # 1. Перевод ввода
        try:
            translated_query = ru_to_en.translate(ingredients)
        except Exception as e:
            print(f"Ошибка перевода ввода: {e}")
            translated_query = ingredients

        params = {
            "apiKey": API_KEY,
            "query": translated_query, 
            "addRecipeInformation": True,
            "fillIngredients": True,
            "number": 3
                }
        
        if diet: params["diet"] = diet
        if max_time: params["maxReadyTime"] = max_time

        async with httpx.AsyncClient() as client:
            response = await client.get(BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
            
            # 2. Обработка результатов
            if "results" in data and data["results"]:
                for recipe in data["results"]:
                    # Безопасное получение названия
                    original_title = recipe.get("title", "Unknown Recipe")
                    try:
                        # Пытаемся перевести название на русский
                        recipe["title_ru"] = en_to_ru.translate(original_title)
                    except Exception as translate_err:
                        print(f"Не удалось перевести название '{original_title}': {translate_err}")
                        recipe["title_ru"] = original_title # Оставляем оригинал
                
                return data
            else:
                print("API вернул пустой список результатов.")
                return {"results": []}

    except Exception as e:
        # ВАЖНО: это покажет нам реальную причину ошибки
        print(f"Критическая ошибка в api_client: {e}")
        import traceback
        traceback.print_exc() # Выведет номер строки, где всё упало
        return None