import httpx
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("FOOD_API_KEY")
BASE_URL = "https://api.spoonacular.com/recipes/complexSearch"

async def search_recipes(ingredients: str, diet: str = None, max_time: int = None):
    """
    Ищет рецепты по ингредиентам с учетом фильтров.
    """
    params = {
        "apiKey": API_KEY,
        "includeIngredients": ingredients, # Список продуктов через запятую
        "addRecipeInformation": True,      # Получить детальное описание
        "fillIngredients": True,           # Названия всех продуктов в рецепте
        "addRecipeNutrition": True,         # Включает КБЖУ в ответ
        "number": 3                        # Вернуть 3 варианта
    }
    
    # Добавляем фильтры, если они переданы пользователем
    if diet:
        params["diet"] = diet
    if max_time:
        params["maxReadyTime"] = max_time

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(BASE_URL, params=params)
            response.raise_for_status() # Вызовет ошибку, если API ключ неверный
            return response.json()
        except Exception as e:
            print(f"Ошибка при запросе к API: {e}")
            return None