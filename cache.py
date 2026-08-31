"""
Модуль для кеширования ответов LLM.

Кеш позволяет избежать повторных запросов к LLM для одинаковых вопросов,
что экономит время и деньги на API-запросы.
"""

import hashlib
import json
from typing import Optional
from pathlib import Path


class ResponseCache:
    """
    Простой кеш для хранения ответов LLM.
    
    Использует словарь Python для хранения пар (хеш_запроса, ответ).
    При необходимости кеш можно сохранить в файл и загрузить обратно.
    """
    
    def __init__(self, cache_file: str = "cache.json"):
        """
        Инициализация кеша.
        
        Args:
            cache_file: Путь к файлу для сохранения кеша на диск
        """
        self.cache_file = Path(cache_file)
        self.cache = {}
        
        # Загружаем существующий кеш, если файл есть
        self._load_cache()
    
    def _get_cache_key(self, query: str) -> str:
        """
        Создает уникальный ключ (хеш) для запроса.
        
        Используем SHA-256 для создания стабильного хеша текста.
        Одинаковые запросы всегда дадут одинаковый ключ.
        
        Args:
            query: Пользовательский запрос
            
        Returns:
            Хеш-строка для использования как ключ кеша
        """
        # Нормализуем запрос: убираем лишние пробелы и приводим к нижнему регистру
        normalized_query = " ".join(query.lower().split())
        
        # Создаем SHA-256 хеш
        return hashlib.sha256(normalized_query.encode('utf-8')).hexdigest()
    
    def get(self, query: str) -> Optional[str]:
        """
        Получает ответ из кеша, если он есть.
        
        Args:
            query: Пользовательский запрос
            
        Returns:
            Закешированный ответ или None, если ответа нет в кеше
        """
        cache_key = self._get_cache_key(query)
        
        if cache_key in self.cache:
            print(f"✓ Найден ответ в кеше для запроса: '{query[:50]}...'")
            return self.cache[cache_key]
        
        print(f"✗ Ответ не найден в кеше, выполняем RAG поиск...")
        return None
    
    def set(self, query: str, response: str) -> None:
        """
        Сохраняет ответ в кеш.
        
        Args:
            query: Пользовательский запрос
            response: Ответ от LLM
        """
        cache_key = self._get_cache_key(query)
        self.cache[cache_key] = response
        
        # Автоматически сохраняем кеш на диск после каждого добавления
        self._save_cache()
        
        print(f"✓ Ответ сохранен в кеше")
    
    def _save_cache(self) -> None:
        """
        Сохраняет кеш в JSON файл.
        
        Это позволяет сохранить кеш между запусками программы.
        """
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠ Предупреждение: не удалось сохранить кеш: {e}")
    
    def _load_cache(self) -> None:
        """
        Загружает кеш из JSON файла, если он существует.
        """
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.cache = json.load(f)
                print(f"✓ Загружен кеш с {len(self.cache)} записями")
            except Exception as e:
                print(f"⚠ Предупреждение: не удалось загрузить кеш: {e}")
                self.cache = {}
    
    def clear(self) -> None:
        """
        Очищает весь кеш.
        """
        self.cache = {}
        if self.cache_file.exists():
            self.cache_file.unlink()
        print("✓ Кеш очищен")
    
    def size(self) -> int:
        """
        Возвращает количество записей в кеше.
        """
        return len(self.cache)

