"""
Модуль для логирования взаимодействий с ассистентом в базу данных.

Логирует все запросы пользователей и ответы ассистента для последующего анализа.
"""

import sqlite3
from datetime import datetime
from typing import Optional
from pathlib import Path
import csv
import io


class DatabaseLogger:
    """
    Класс для логирования взаимодействий в SQLite базу данных.
    
    Хранит:
    - Вопросы пользователей
    - Ответы ассистента
    - Метаданные (время, источник, user_id для Telegram)
    - Статус (из кеша или новый запрос)
    """
    
    def __init__(self, db_path: str = "logs.db"):
        """
        Инициализация логгера базы данных.
        
        Args:
            db_path: Путь к файлу базы данных SQLite
        """
        self.db_path = Path(db_path)
        self._init_database()
    
    def _init_database(self) -> None:
        """
        Создает таблицу для логов, если она не существует.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                user_id TEXT,
                username TEXT,
                source TEXT NOT NULL,
                query TEXT NOT NULL,
                response TEXT NOT NULL,
                from_cache INTEGER DEFAULT 0,
                response_time_ms INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Создаем индексы для быстрого поиска
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp ON logs(timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_id ON logs(user_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_source ON logs(source)
        """)
        
        conn.commit()
        conn.close()
    
    def log_interaction(
        self,
        query: str,
        response: str,
        source: str = "console",
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        from_cache: bool = False,
        response_time_ms: Optional[int] = None
    ) -> None:
        """
        Логирует взаимодействие пользователя с ассистентом.
        
        Args:
            query: Вопрос пользователя
            response: Ответ ассистента
            source: Источник запроса (console, telegram, api и т.д.)
            user_id: ID пользователя (для Telegram)
            username: Имя пользователя
            from_cache: Был ли ответ взят из кеша
            response_time_ms: Время ответа в миллисекундах
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        timestamp = datetime.now().isoformat()
        
        cursor.execute("""
            INSERT INTO logs (
                timestamp, user_id, username, source, query, response, 
                from_cache, response_time_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp,
            user_id,
            username,
            source,
            query,
            response,
            1 if from_cache else 0,
            response_time_ms
        ))
        
        conn.commit()
        conn.close()
    
    def get_logs(
        self,
        limit: Optional[int] = None,
        user_id: Optional[str] = None,
        source: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> list:
        """
        Получает логи из базы данных с фильтрацией.
        
        Args:
            limit: Максимальное количество записей
            user_id: Фильтр по ID пользователя
            source: Фильтр по источнику
            start_date: Начальная дата (ISO format)
            end_date: Конечная дата (ISO format)
            
        Returns:
            Список словарей с логами
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Для доступа к колонкам по имени
        cursor = conn.cursor()
        
        query = "SELECT * FROM logs WHERE 1=1"
        params = []
        
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        
        if source:
            query += " AND source = ?"
            params.append(source)
        
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)
        
        query += " ORDER BY timestamp DESC"
        
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        # Преобразуем Row объекты в словари
        logs = [dict(row) for row in rows]
        
        conn.close()
        return logs
    
    def export_to_csv(
        self,
        output_path: Optional[str] = None,
        user_id: Optional[str] = None,
        source: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> str:
        """
        Экспортирует логи в CSV файл.
        
        Args:
            output_path: Путь к выходному файлу (если None, возвращает строку)
            user_id: Фильтр по ID пользователя
            source: Фильтр по источнику
            start_date: Начальная дата
            end_date: Конечная дата
            
        Returns:
            Путь к созданному файлу или содержимое CSV как строка
        """
        logs = self.get_logs(
            user_id=user_id,
            source=source,
            start_date=start_date,
            end_date=end_date
        )
        
        if not logs:
            return ""
        
        # Определяем колонки
        fieldnames = [
            'id', 'timestamp', 'user_id', 'username', 'source', 
            'query', 'response', 'from_cache', 'response_time_ms', 'created_at'
        ]
        
        # utf-8-sig (BOM) — Excel на Windows открывает кириллицу корректно.
        # Разделитель ";" — стандарт для русской локали Excel.
        csv_kwargs = {
            "fieldnames": fieldnames,
            "delimiter": ";",
            "quoting": csv.QUOTE_MINIMAL,
            "extrasaction": "ignore",
        }

        if output_path:
            with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, **csv_kwargs)
                writer.writeheader()
                writer.writerows(logs)
            return output_path

        output = io.StringIO()
        writer = csv.DictWriter(output, **csv_kwargs)
        writer.writeheader()
        writer.writerows(logs)
        return output.getvalue()
    
    def get_stats(self) -> dict:
        """
        Получает статистику по логам.
        
        Returns:
            Словарь со статистикой
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Общее количество запросов
        cursor.execute("SELECT COUNT(*) FROM logs")
        total_requests = cursor.fetchone()[0]
        
        # Запросов из кеша
        cursor.execute("SELECT COUNT(*) FROM logs WHERE from_cache = 1")
        cached_requests = cursor.fetchone()[0]
        
        # Уникальных пользователей
        cursor.execute("SELECT COUNT(DISTINCT user_id) FROM logs WHERE user_id IS NOT NULL")
        unique_users = cursor.fetchone()[0]
        
        # По источникам
        cursor.execute("SELECT source, COUNT(*) FROM logs GROUP BY source")
        by_source = dict(cursor.fetchall())
        
        # Среднее время ответа
        cursor.execute("SELECT AVG(response_time_ms) FROM logs WHERE response_time_ms IS NOT NULL")
        avg_response_time = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_requests': total_requests,
            'cached_requests': cached_requests,
            'unique_users': unique_users,
            'by_source': by_source,
            'avg_response_time_ms': avg_response_time if avg_response_time else 0
        }

