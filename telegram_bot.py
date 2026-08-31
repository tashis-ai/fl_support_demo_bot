"""
Модуль для Telegram бота, интегрированного с RAG-ассистентом.

Бот позволяет пользователям задавать вопросы ассистенту через Telegram
и получать ответы на основе векторного поиска и LLM.
"""

import asyncio
import os
import time
from io import BytesIO
from typing import Optional
from telegram import Update
from telegram.error import NetworkError, TimedOut
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from telegram.request import HTTPXRequest
from rag import RAGAssistant
from cache import ResponseCache
from db_logger import DatabaseLogger

# Long poll: короткий timeout у Telegram, чуть больший read у httpx
_POLL_TIMEOUT = 10


class TelegramRAGBot:
    """
    Telegram бот для RAG-ассистента.
    
    Обрабатывает команды и сообщения от пользователей,
    логирует все взаимодействия в базу данных.
    """
    
    def __init__(
        self,
        token: str,
        rag_assistant: RAGAssistant,
        cache: ResponseCache,
        logger: DatabaseLogger,
        proxy: Optional[str] = None,
    ):
        """
        Инициализация Telegram бота.
        
        Args:
            token: Токен Telegram бота от @BotFather
            rag_assistant: Экземпляр RAG-ассистента
            cache: Экземпляр кеша ответов
            logger: Экземпляр логгера базы данных
            proxy: URL прокси из TELEGRAM_PROXY (пусто = подключение напрямую)
        """
        self.rag_assistant = rag_assistant
        self.cache = cache
        self.logger = logger
        
        # Пустая строка / None → без прокси (типичный деплой на VPS)
        proxy_url = (proxy if proxy is not None else os.getenv("TELEGRAM_PROXY") or "").strip() or None
        
        builder = (
            Application.builder()
            .token(token)
            .request(self._http_request(proxy_url, for_get_updates=False))
            .get_updates_request(self._http_request(proxy_url, for_get_updates=True))
        )
        if proxy_url:
            print(f"✓ Telegram через прокси: {proxy_url}")
        else:
            print("✓ Telegram напрямую (TELEGRAM_PROXY не задан)")
        self.application = builder.build()
        
        # Регистрируем обработчики команд
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(CommandHandler("logs", self.logs_command))
        
        # Регистрируем обработчик текстовых сообщений
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )
        self.application.add_error_handler(self.error_handler)

    @staticmethod
    def _http_request(proxy_url: Optional[str], for_get_updates: bool) -> HTTPXRequest:
        return HTTPXRequest(
            proxy=proxy_url,
            connect_timeout=20.0,
            read_timeout=(_POLL_TIMEOUT + 15) if for_get_updates else 30.0,
            write_timeout=60.0,
            pool_timeout=10.0,
            media_write_timeout=60.0,
            http_version="1.1",
        )

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Сетевые обрывы при polling не считаем критическими."""
        err = context.error
        if isinstance(err, (NetworkError, TimedOut)):
            print(f"⚠ Сеть Telegram (повторная попытка): {err}")
            return
        print(f"❌ Ошибка бота: {err}")
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        welcome_message = """
🤖 Добро пожаловать в RAG-ассистента онлайн-школы!

Я отвечаю на вопросы о курсах, сертификации и программах школы, используя базу знаний.

Доступные команды:
/help - показать справку
/stats - статистика системы
/logs - получить все логи в CSV формате

Просто напишите мне вопрос, и я постараюсь на него ответить!
        """
        await update.message.reply_text(welcome_message.strip())
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = """
📚 Справка по использованию бота онлайн-школы:

• Просто напишите вопрос — я отвечу на основе базы знаний школы
• Могу рассказать о курсах для специалистов и родителей, сертификации и требованиях
• Ответы кешируются для быстрой работы

Команды:
/start - начать работу с ботом
/help - показать эту справку
/stats - статистика системы (документы, кеш)
/logs - получить все логи взаимодействий в CSV формате

Примеры вопросов:
• "Какие есть курсы для специалистов?"
• "Как получить сертификацию IBP?"
• "Сколько стоит курс для родителей?"
        """
        await update.message.reply_text(help_text.strip())
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /stats"""
        try:
            # Получаем статистику системы
            doc_count = self.rag_assistant.embedding_store.collection.count()
            cache_size = self.cache.size()
            model = self.rag_assistant.model
            
            # Получаем статистику из логов
            log_stats = self.logger.get_stats()
            
            stats_message = f"""
📊 СТАТИСТИКА СИСТЕМЫ:

📚 База знаний:
  • Документов в ChromaDB: {doc_count}
  • Модель LLM: {model}

💾 Кеш:
  • Записей в кеше: {cache_size}

📝 Логи:
  • Всего запросов: {log_stats['total_requests']}
  • Из кеша: {log_stats['cached_requests']}
  • Уникальных пользователей: {log_stats['unique_users']}
  • Среднее время ответа: {log_stats['avg_response_time_ms']:.0f} мс
            """
            
            await update.message.reply_text(stats_message.strip())
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка при получении статистики: {str(e)}")
    
    async def logs_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /logs - экспорт логов в CSV"""
        try:
            await update.message.chat.send_action(action="upload_document")

            csv_content = await asyncio.to_thread(self.logger.export_to_csv)

            if not csv_content:
                await update.message.reply_text("📝 Логов пока нет.")
                return

            buffer = BytesIO(csv_content.encode("utf-8-sig"))
            filename = f"logs_all_{int(time.time())}.csv"
            buffer.name = filename
            await update.message.reply_document(
                document=buffer,
                filename=filename,
                caption="📊 Все логи взаимодействий с ботом",
                write_timeout=60,
                connect_timeout=20,
                read_timeout=30,
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка при экспорте логов: {str(e)}")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений от пользователей"""
        user_message = update.message.text
        user = update.effective_user
        user_id = str(user.id)
        username = user.username or user.first_name or "Unknown"
        
        # Показываем, что бот печатает
        await update.message.chat.send_action(action="typing")
        
        start_time = time.time()
        
        try:
            # Проверяем кеш
            cached_answer = self.cache.get(user_message)
            from_cache = cached_answer is not None
            
            if cached_answer:
                answer = cached_answer
            else:
                # Выполняем RAG запрос
                answer, _ = self.rag_assistant.generate_response(
                    query=user_message,
                    top_k=3,
                    verbose=False
                )
                
                # Сохраняем в кеш
                self.cache.set(user_message, answer)
            
            # Вычисляем время ответа
            response_time_ms = int((time.time() - start_time) * 1000)
            
            # Логируем взаимодействие
            self.logger.log_interaction(
                query=user_message,
                response=answer,
                source="telegram",
                user_id=user_id,
                username=username,
                from_cache=from_cache,
                response_time_ms=response_time_ms
            )
            
            # Отправляем ответ пользователю
            # Разбиваем длинные ответы на части (Telegram имеет лимит 4096 символов)
            max_length = 4000
            if len(answer) <= max_length:
                await update.message.reply_text(answer)
            else:
                # Отправляем частями
                parts = [answer[i:i+max_length] for i in range(0, len(answer), max_length)]
                for i, part in enumerate(parts):
                    if i == 0:
                        await update.message.reply_text(part)
                    else:
                        await update.message.reply_text(part)
            
            # Добавляем индикатор, если ответ из кеша
            if from_cache:
                await update.message.reply_text("💾 (ответ из кеша)", do_quote=False)
        
        except Exception as e:
            error_message = f"❌ Произошла ошибка при обработке запроса: {str(e)}"
            await update.message.reply_text(error_message)
            
            # Логируем ошибку
            self.logger.log_interaction(
                query=user_message,
                response=error_message,
                source="telegram",
                user_id=user_id,
                username=username,
                from_cache=False,
                response_time_ms=int((time.time() - start_time) * 1000)
            )
    
    def run(self):
        """Запускает бота"""
        print("🤖 Запуск Telegram бота...")
        print("Бот готов к работе! Нажмите Ctrl+C для остановки.")
        try:
            self.application.run_polling(
                poll_interval=2.0,
                timeout=_POLL_TIMEOUT,
                bootstrap_retries=-1,
            )
        except KeyboardInterrupt:
            print("\n👋 Бот остановлен.")

