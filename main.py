"""
Главный файл для запуска RAG-ассистента.

Это точка входа в приложение. Здесь происходит:
1. Загрузка конфигурации
2. Инициализация всех компонентов (кеш, векторная база, RAG)
3. Добавление примеров документов (при первом запуске)
4. Интерактивный цикл общения с пользователем
"""

import os
import time
from typing import Optional
from dotenv import load_dotenv
from embeddings import EmbeddingStore, get_sample_documents
from rag import RAGAssistant
from cache import ResponseCache
from db_logger import DatabaseLogger
from telegram_bot import TelegramRAGBot


def initialize_system():
    """
    Инициализирует все компоненты RAG-системы.
    
    Returns:
        Кортеж (embedding_store, rag_assistant, cache, logger)
    """
    print("=" * 70)
    print("🚀 ИНИЦИАЛИЗАЦИЯ RAG-АССИСТЕНТА")
    print("=" * 70)
    
    # Загружаем переменные окружения из .env файла
    load_dotenv()
    
    # Проверяем наличие ключа ProxyAPI
    api_key = os.getenv("PROXYAPI_API_KEY")
    base_url = os.getenv("PROXYAPI_BASE_URL")
    model_name = os.getenv("PROXYAPI_MODEL", "gpt-4o-mini")
    embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    if not api_key:
        print("⚠️  ВНИМАНИЕ: Не найден PROXYAPI_API_KEY в переменных окружения!")
        print("   Создайте файл .env и добавьте PROXYAPI_API_KEY, PROXYAPI_BASE_URL, PROXYAPI_MODEL")
        print()
    
    # 1. Инициализируем кеш для хранения ответов
    print("\n[1/4] Инициализация кеша...")
    cache = ResponseCache(cache_file="cache.json")
    
    # 2. Инициализируем векторное хранилище ChromaDB
    print("\n[2/4] Инициализация векторного хранилища...")
    embedding_store = EmbeddingStore(
        collection_name="rag_documents",
        persist_directory="./chroma_db",
        embedding_model=embedding_model,
        api_key=api_key,
        base_url=base_url
    )
    
    # Проверяем, нужно ли добавить примеры документов
    if embedding_store.collection.count() == 0:
        print("\n📝 База данных пуста. Добавляем примеры документов...")
        sample_docs = get_sample_documents()
        embedding_store.add_documents(sample_docs)
    else:
        print(f"✓ В базе уже есть {embedding_store.collection.count()} документов")
    
    # 3. Инициализируем RAG-ассистента
    print("\n[3/4] Инициализация RAG-ассистента...")
    rag_assistant = RAGAssistant(
        embedding_store=embedding_store,
        api_key=api_key,
        base_url=base_url,
        model=model_name,
        temperature=0.7
    )
    
    # 4. Инициализируем логгер базы данных
    print("\n[4/4] Инициализация логгера базы данных...")
    logger = DatabaseLogger(db_path="logs.db")
    print("✓ Логгер инициализирован")
    
    print("\n" + "=" * 70)
    print("✅ СИСТЕМА ГОТОВА К РАБОТЕ")
    print("=" * 70)
    
    return embedding_store, rag_assistant, cache, logger


def answer_question(
    query: str, 
    rag_assistant: RAGAssistant, 
    cache: ResponseCache,
    logger: DatabaseLogger,
    source: str = "console",
    user_id: Optional[str] = None,
    username: Optional[str] = None
) -> str:
    """
    Отвечает на вопрос пользователя с использованием кеша и RAG.
    
    Логика работы:
    1. Проверяем кеш - если ответ есть, возвращаем его
    2. Если ответа нет, выполняем RAG (поиск + генерация)
    3. Сохраняем новый ответ в кеш
    4. Логируем взаимодействие в базу данных
    5. Возвращаем ответ
    
    Args:
        query: Вопрос пользователя
        rag_assistant: Экземпляр RAG-ассистента
        cache: Экземпляр кеша
        logger: Экземпляр логгера базы данных
        source: Источник запроса (console, telegram и т.д.)
        user_id: ID пользователя (для Telegram)
        username: Имя пользователя
        
    Returns:
        Ответ на вопрос
    """
    print("\n" + "=" * 70)
    print(f"❓ ВОПРОС: {query}")
    print("=" * 70)
    
    start_time = time.time()
    
    # Шаг 1: Проверяем кеш
    print("\n[Шаг 1] Проверка кеша...")
    cached_answer = cache.get(query)
    from_cache = cached_answer is not None
    
    if cached_answer:
        # Ответ найден в кеше - возвращаем его
        print("\n💾 Ответ из кеша:")
        print("-" * 70)
        print(cached_answer)
        print("-" * 70)
        answer = cached_answer
    else:
        # Шаг 2: Ответа нет в кеше - выполняем RAG
        print("\n[Шаг 2] Выполнение RAG (поиск + генерация)...")
        
        try:
            answer, search_results = rag_assistant.generate_response(
                query=query,
                top_k=3,
                verbose=True
            )
            
            # Шаг 3: Сохраняем ответ в кеш
            print("\n[Шаг 3] Сохранение ответа в кеш...")
            cache.set(query, answer)
            
            # Выводим финальный ответ
            print("\n💡 ОТВЕТ:")
            print("-" * 70)
            print(answer)
            print("-" * 70)
            
        except Exception as e:
            error_msg = f"Ошибка при обработке запроса: {str(e)}"
            print(f"\n❌ {error_msg}")
            answer = error_msg
    
    # Шаг 4: Логируем взаимодействие
    response_time_ms = int((time.time() - start_time) * 1000)
    logger.log_interaction(
        query=query,
        response=answer,
        source=source,
        user_id=user_id,
        username=username,
        from_cache=from_cache,
        response_time_ms=response_time_ms
    )
    
    return answer


def interactive_mode(rag_assistant: RAGAssistant, cache: ResponseCache, logger: DatabaseLogger):
    """
    Интерактивный режим общения с ассистентом.
    
    Пользователь может задавать вопросы в цикле до тех пор,
    пока не введет команду выхода.
    """
    print("\n" + "=" * 70)
    print("💬 ИНТЕРАКТИВНЫЙ РЕЖИМ")
    print("=" * 70)
    print("\nВы можете задавать вопросы ассистенту.")
    print("Для выхода введите: exit, quit, выход или q")
    print("\nДоступные команды:")
    print("  • cache - показать информацию о кеше")
    print("  • clear_cache - очистить кеш")
    print("  • stats - показать статистику системы")
    print("  • logs - экспортировать логи в CSV")
    print()
    
    while True:
        try:
            # Получаем ввод от пользователя
            user_input = input("\n👤 Вы: ").strip()
            
            # Проверяем команды выхода
            if user_input.lower() in ['exit', 'quit', 'выход', 'q', '']:
                print("\n👋 До свидания!")
                break
            
            # Обрабатываем специальные команды
            if user_input.lower() == 'cache':
                print(f"\n📊 Кеш содержит {cache.size()} записей")
                continue
            
            if user_input.lower() == 'clear_cache':
                cache.clear()
                print("\n✓ Кеш очищен")
                continue
            
            if user_input.lower() == 'stats':
                print(f"\n📊 СТАТИСТИКА СИСТЕМЫ:")
                print(f"  • Документов в ChromaDB: {rag_assistant.embedding_store.collection.count()}")
                print(f"  • Записей в кеше: {cache.size()}")
                print(f"  • Модель LLM: {rag_assistant.model}")
                
                # Показываем статистику из логов
                log_stats = logger.get_stats()
                print(f"\n📝 ЛОГИ:")
                print(f"  • Всего запросов: {log_stats['total_requests']}")
                print(f"  • Из кеша: {log_stats['cached_requests']}")
                print(f"  • Среднее время ответа: {log_stats['avg_response_time_ms']:.0f} мс")
                continue
            
            if user_input.lower() == 'logs':
                filename = f"logs_console_{int(time.time())}.csv"
                logger.export_to_csv(output_path=filename, source="console")
                print(f"\n✓ Логи экспортированы в файл: {filename}")
                continue
            
            # Обрабатываем вопрос пользователя
            answer_question(user_input, rag_assistant, cache, logger, source="console")
            
        except KeyboardInterrupt:
            print("\n\n👋 Прервано пользователем. До свидания!")
            break
        except Exception as e:
            print(f"\n❌ Ошибка: {str(e)}")


def demo_mode(rag_assistant: RAGAssistant, cache: ResponseCache, logger: DatabaseLogger):
    """
    Демонстрационный режим с заранее заготовленными вопросами.
    
    Показывает работу системы на примерах, включая использование кеша.
    """
    print("\n" + "=" * 70)
    print("🎬 ДЕМОНСТРАЦИОННЫЙ РЕЖИМ")
    print("=" * 70)
    print("\nСейчас будет продемонстрирована работа RAG-ассистента")
    print("на нескольких примерах вопросов.\n")
    
    # Список демо-вопросов
    demo_questions = [
        "Что такое Python и для чего он используется?",
        "Расскажи про RAG и как он работает",
        "Что такое векторные базы данных?",
        "Что такое Python и для чего он используется?"  # Повторный вопрос для демонстрации кеша
    ]
    
    for i, question in enumerate(demo_questions, 1):
        print(f"\n\n{'#' * 70}")
        print(f"ВОПРОС {i} из {len(demo_questions)}")
        print(f"{'#' * 70}")
        
        answer_question(question, rag_assistant, cache, logger, source="console")
        
        # Пауза между вопросами (кроме последнего)
        if i < len(demo_questions):
            input("\n[Нажмите Enter для следующего вопроса...]")
    
    print("\n\n" + "=" * 70)
    print("✅ ДЕМОНСТРАЦИЯ ЗАВЕРШЕНА")
    print("=" * 70)


def main():
    """
    Главная функция приложения.
    Режим задаётся в .env: APP_MODE=1 (консоль), 2 (демо), 3 (Telegram, по умолчанию).
    """
    try:
        # Инициализируем систему
        embedding_store, rag_assistant, cache, logger = initialize_system()
        
        telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        mode = (os.getenv("APP_MODE") or "3").strip().lower()
        mode_aliases = {
            "1": "1", "interactive": "1", "console": "1",
            "2": "2", "demo": "2",
            "3": "3", "telegram": "3", "bot": "3",
        }
        mode = mode_aliases.get(mode, "3")
        
        print("\n" + "=" * 70)
        print(f"РЕЖИМ РАБОТЫ: {mode} (из APP_MODE)")
        print("=" * 70)
        
        if mode == "2":
            demo_mode(rag_assistant, cache, logger)
        elif mode == "3":
            if not telegram_token:
                print("\n❌ APP_MODE=3, но TELEGRAM_BOT_TOKEN не задан в .env")
                return
            print("\n🤖 ЗАПУСК TELEGRAM БОТА")
            bot = TelegramRAGBot(
                token=telegram_token,
                rag_assistant=rag_assistant,
                cache=cache,
                logger=logger,
                proxy=os.getenv("TELEGRAM_PROXY"),
            )
            bot.run()
        else:
            interactive_mode(rag_assistant, cache, logger)
        
    except KeyboardInterrupt:
        print("\n👋 Остановлено.")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

