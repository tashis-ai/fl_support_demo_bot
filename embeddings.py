"""
Модуль для работы с эмбеддингами и векторным хранилищем ChromaDB.

Здесь мы создаем векторные представления текстов используя OpenAI API
и сохраняем их в ChromaDB для быстрого семантического поиска.
"""

import chromadb
from chromadb.config import Settings
from openai import OpenAI
from typing import List, Tuple
import os
from pathlib import Path


class EmbeddingStore:
    """
    Класс для работы с векторным хранилищем ChromaDB.
    
    Использует OpenAI API для создания эмбеддингов
    и ChromaDB для их хранения и поиска.
    """
    
    def __init__(
        self, 
        collection_name: str = "documents",
        persist_directory: str = "./chroma_db",
        embedding_model: str = "text-embedding-3-small",
        api_key: str = None,
        base_url: str = None
    ):
        """
        Инициализация хранилища эмбеддингов.
        
        Args:
            collection_name: Имя коллекции в ChromaDB
            persist_directory: Директория для сохранения данных ChromaDB
            embedding_model: Название модели для эмбеддингов
            api_key: API ключ ProxyAPI (если None, берется из PROXYAPI_API_KEY)
            base_url: Базовый URL ProxyAPI (если None, берется из PROXYAPI_BASE_URL)
        """
        print(f"Инициализация ChromaDB в директории: {persist_directory}")
        
        # Создаем клиент ChromaDB с персистентным хранилищем
        # Данные будут сохраняться на диск и загружаться при перезапуске
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False  # Отключаем телеметрию
            )
        )
        
        # OpenAI-совместимый клиент через ProxyAPI
        self.openai_client = OpenAI(
            api_key=api_key or os.getenv("PROXYAPI_API_KEY"),
            base_url=base_url or os.getenv("PROXYAPI_BASE_URL")
        )
        self.embedding_model = embedding_model
        
        print(f"Модель эмбеддингов: {embedding_model} (ProxyAPI)")
        
        # Получаем или создаем коллекцию в ChromaDB
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "Документы для RAG-ассистента"}
        )
        
        print(f"✓ ChromaDB инициализирована. Документов в коллекции: {self.collection.count()}")
    
    def _create_chunks(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """
        Разбивает текст на чанки (фрагменты) с перекрытием.
        
        Перекрытие важно, чтобы не потерять контекст на границах чанков.
        
        Args:
            text: Исходный текст
            chunk_size: Размер чанка в символах
            overlap: Размер перекрытия между чанками
            
        Returns:
            Список чанков текста
        """
        chunks = []
        start = 0
        
        while start < len(text):
            # Вычисляем конец текущего чанка
            end = start + chunk_size
            
            # Добавляем чанк в список
            chunk = text[start:end].strip()
            if chunk:  # Пропускаем пустые чанки
                chunks.append(chunk)
            
            # Сдвигаемся вперед с учетом перекрытия
            start = end - overlap
        
        return chunks
    
    def _create_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Создает эмбеддинги для списка текстов используя OpenAI API.
        
        Args:
            texts: Список текстов для создания эмбеддингов
            
        Returns:
            Список векторов эмбеддингов
        """
        try:
            # Отправляем запрос к OpenAI API для создания эмбеддингов
            # API автоматически обрабатывает батчи текстов
            response = self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=texts,
                encoding_format="float"  # Получаем векторы в формате float
            )
            
            # Извлекаем векторы эмбеддингов из ответа
            embeddings = [item.embedding for item in response.data]
            
            return embeddings
            
        except Exception as e:
            print(f"❌ Ошибка при создании эмбеддингов: {str(e)}")
            raise
    
    def add_documents(self, documents: List[Tuple[str, str]]) -> None:
        """
        Добавляет документы в векторное хранилище.
        
        Каждый документ разбивается на чанки, для каждого чанка создается
        эмбеддинг через OpenAI API, и все сохраняется в ChromaDB.
        
        Args:
            documents: Список кортежей (название_документа, текст_документа)
        """
        all_chunks = []
        all_metadatas = []
        all_ids = []
        
        chunk_id = self.collection.count()  # Начинаем нумерацию с текущего количества
        
        print(f"\nДобавление {len(documents)} документов в ChromaDB...")
        
        for doc_name, doc_text in documents:
            # Разбиваем документ на чанки
            chunks = self._create_chunks(doc_text)
            
            print(f"  • {doc_name}: {len(chunks)} чанков")
            
            for chunk in chunks:
                all_chunks.append(chunk)
                all_metadatas.append({
                    "source": doc_name,
                    "chunk_length": len(chunk)
                })
                all_ids.append(f"chunk_{chunk_id}")
                chunk_id += 1
        
        # Создаем эмбеддинги через OpenAI API
        print(f"\nСоздание эмбеддингов для {len(all_chunks)} чанков через OpenAI API...")
        print(f"(Модель: {self.embedding_model})")
        
        # OpenAI API имеет ограничение на размер батча, поэтому обрабатываем по частям
        batch_size = 100  # Максимум 100 текстов за раз для безопасности
        all_embeddings = []
        
        for i in range(0, len(all_chunks), batch_size):
            batch = all_chunks[i:i + batch_size]
            print(f"  Обработка чанков {i+1}-{min(i+batch_size, len(all_chunks))} из {len(all_chunks)}...")
            
            batch_embeddings = self._create_embeddings(batch)
            all_embeddings.extend(batch_embeddings)
        
        # Добавляем все данные в ChromaDB одним батчем
        print("Сохранение в ChromaDB...")
        self.collection.add(
            embeddings=all_embeddings,
            documents=all_chunks,
            metadatas=all_metadatas,
            ids=all_ids
        )
        
        print(f"✓ Добавлено {len(all_chunks)} чанков. Всего в базе: {self.collection.count()}")
    
    def search(self, query: str, top_k: int = 3) -> List[Tuple[str, str, float]]:
        """
        Выполняет семантический поиск по векторному хранилищу.
        
        Находит top_k наиболее релевантных чанков для запроса.
        
        Args:
            query: Поисковый запрос пользователя
            top_k: Количество результатов для возврата
            
        Returns:
            Список кортежей (текст_чанка, источник, расстояние)
            Расстояние: чем меньше, тем более релевантен результат
        """
        # Проверяем, есть ли документы в коллекции
        if self.collection.count() == 0:
            print("⚠ Предупреждение: коллекция пуста, нет документов для поиска")
            return []
        
        # Создаем эмбеддинг для запроса через OpenAI API
        query_embeddings = self._create_embeddings([query])
        query_embedding = query_embeddings[0]
        
        # Выполняем поиск в ChromaDB
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self.collection.count())
        )
        
        # Форматируем результаты
        formatted_results = []
        
        if results['documents'] and len(results['documents'][0]) > 0:
            for i in range(len(results['documents'][0])):
                chunk_text = results['documents'][0][i]
                source = results['metadatas'][0][i]['source']
                distance = results['distances'][0][i]
                
                formatted_results.append((chunk_text, source, distance))
        
        return formatted_results
    
    def clear_collection(self) -> None:
        """
        Очищает коллекцию (удаляет все документы).
        """
        # Удаляем коллекцию и создаем заново
        self.client.delete_collection(self.collection.name)
        self.collection = self.client.get_or_create_collection(
            name=self.collection.name,
            metadata={"description": "Документы для RAG-ассистента"}
        )
        print("✓ Коллекция очищена")


def load_documents_from_folder(folder_path: str = "docs") -> List[Tuple[str, str]]:
    """
    Загружает документы из папки с txt файлами.
    
    Читает все .txt файлы из указанной папки и возвращает их содержимое
    в формате списка кортежей (имя_файла, содержимое).
    
    Args:
        folder_path: Путь к папке с документами
        
    Returns:
        Список кортежей (название_файла, текст_документа)
    """
    docs_path = Path(folder_path)
    documents = []
    
    if not docs_path.exists():
        print(f"⚠ Предупреждение: папка {folder_path} не найдена")
        return documents
    
    if not docs_path.is_dir():
        print(f"⚠ Предупреждение: {folder_path} не является папкой")
        return documents
    
    # Ищем все .txt файлы в папке
    txt_files = list(docs_path.glob("*.txt"))
    
    if not txt_files:
        print(f"⚠ Предупреждение: в папке {folder_path} не найдено .txt файлов")
        return documents
    
    print(f"📂 Найдено {len(txt_files)} файлов в папке {folder_path}")
    
    for txt_file in txt_files:
        try:
            # Читаем содержимое файла
            with open(txt_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            if content:
                # Используем имя файла (без расширения) как название документа
                doc_name = txt_file.stem
                documents.append((doc_name, content))
                print(f"  ✓ Загружен: {txt_file.name}")
            else:
                print(f"  ⚠ Пропущен (пустой): {txt_file.name}")
                
        except Exception as e:
            print(f"  ❌ Ошибка при чтении {txt_file.name}: {str(e)}")
    
    return documents


def get_sample_documents() -> List[Tuple[str, str]]:
    """
    Возвращает примеры документов для демонстрации RAG.
    
    Сначала пытается загрузить документы из папки docs/,
    если папка пуста или не существует, возвращает встроенные примеры.
    
    Returns:
        Список кортежей (название, текст)
    """
    # Пытаемся загрузить документы из папки
    documents = load_documents_from_folder("docs")
    
    # Если документы не найдены, используем встроенные примеры
    if not documents:
        print("📝 Используются встроенные примеры документов")
        documents = [
            (
                "Python Основы",
                """
                Python - это высокоуровневый язык программирования общего назначения. 
                Он был создан Гвидо ван Россумом и впервые выпущен в 1991 году.
                
                Python известен своей простотой и читаемостью кода. Философия языка 
                подчеркивает важность читаемости кода и позволяет программистам 
                выражать концепции в меньшем количестве строк кода, чем это было бы 
                возможно в других языках.
                
                Основные возможности Python включают:
                - Динамическую типизацию
                - Автоматическое управление памятью
                - Обширную стандартную библиотеку
                - Поддержку множественных парадигм программирования
                
                Python широко используется в веб-разработке, анализе данных, 
                машинном обучении, автоматизации и научных вычислениях.
                """
            ),
            (
                "Машинное обучение и AI",
                """
                Машинное обучение (Machine Learning) - это подраздел искусственного 
                интеллекта, который изучает алгоритмы и статистические модели, 
                позволяющие компьютерам выполнять задачи без явного программирования.
                
                Основные типы машинного обучения:
                
                1. Обучение с учителем (Supervised Learning)
                В этом подходе модель обучается на размеченных данных, где каждый 
                пример имеет известный правильный ответ. Примеры: классификация 
                изображений, предсказание цен на недвижимость.
                
                2. Обучение без учителя (Unsupervised Learning)
                Модель ищет закономерности в неразмеченных данных. Примеры: 
                кластеризация клиентов, обнаружение аномалий.
                
                3. Обучение с подкреплением (Reinforcement Learning)
                Агент обучается принимать решения, взаимодействуя со средой и 
                получая награды или штрафы.
                
                RAG (Retrieval-Augmented Generation) - это техника, которая улучшает 
                качество ответов языковых моделей, дополняя их внешними знаниями из 
                базы данных. Это позволяет модели давать более точные и актуальные 
                ответы, основанные на конкретных документах.
                """
            ),
            (
                "Векторные базы данных",
                """
                Векторные базы данных - это специализированные системы хранения данных, 
                оптимизированные для хранения и поиска векторных эмбеддингов.
                
                Что такое эмбеддинги?
                Эмбеддинги - это векторные представления данных (текста, изображений, 
                аудио) в многомерном пространстве. Семантически похожие объекты 
                располагаются близко друг к другу в этом пространстве.
                
                ChromaDB - это открытая векторная база данных, разработанная специально 
                для работы с эмбеддингами в приложениях с искусственным интеллектом.
                
                Преимущества ChromaDB:
                - Простота использования и встраивания в приложения
                - Поддержка персистентного хранения данных
                - Встроенная поддержка различных моделей эмбеддингов
                - Быстрый семантический поиск
                - Возможность работы как локально, так и в клиент-серверном режиме
                
                Векторные базы данных критически важны для RAG-систем, так как они 
                позволяют быстро находить релевантные документы на основе семантического 
                сходства запроса с содержимым базы данных.
                
                OpenAI предоставляет мощные модели для создания эмбеддингов, такие как 
                text-embedding-3-small и text-embedding-3-large. Эти модели создают 
                высококачественные векторные представления текста, которые отлично 
                работают для семантического поиска в различных языках, включая русский.
                """
            )
        ]
    
    return documents
