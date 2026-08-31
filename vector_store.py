"""
Модуль для работы с векторным хранилищем.

Этот модуль предоставляет интерфейс для работы с векторной базой данных,
используя ChromaDB и OpenAI эмбеддинги.
"""

from embeddings import EmbeddingStore
from typing import List, Tuple, Optional
import os


class VectorStore:
    """
    Обертка над EmbeddingStore для более удобной работы с векторным хранилищем.
    
    Предоставляет методы для:
    - Добавления документов
    - Поиска релевантных документов
    - Управления коллекцией
    """
    
    def __init__(
        self,
        collection_name: str = "rag_documents",
        persist_directory: str = "./chroma_db",
        embedding_model: str = "text-embedding-3-small",
        api_key: Optional[str] = None
    ):
        """
        Инициализация векторного хранилища.
        
        Args:
            collection_name: Имя коллекции в ChromaDB
            persist_directory: Директория для сохранения данных
            embedding_model: Модель для создания эмбеддингов
            api_key: API ключ OpenAI
        """
        self.embedding_store = EmbeddingStore(
            collection_name=collection_name,
            persist_directory=persist_directory,
            embedding_model=embedding_model,
            api_key=api_key or os.getenv("OPENAI_API_KEY")
        )
    
    def add_documents(self, documents: List[Tuple[str, str]]) -> None:
        """
        Добавляет документы в векторное хранилище.
        
        Args:
            documents: Список кортежей (название, текст)
        """
        self.embedding_store.add_documents(documents)
    
    def search(self, query: str, top_k: int = 3) -> List[Tuple[str, str, float]]:
        """
        Выполняет семантический поиск по векторному хранилищу.
        
        Args:
            query: Поисковый запрос
            top_k: Количество результатов
            
        Returns:
            Список кортежей (текст, источник, расстояние)
        """
        return self.embedding_store.search(query, top_k=top_k)
    
    def get_document_count(self) -> int:
        """
        Возвращает количество документов в хранилище.
        
        Returns:
            Количество документов
        """
        return self.embedding_store.collection.count()
    
    def clear(self) -> None:
        """
        Очищает векторное хранилище.
        """
        self.embedding_store.clear_collection()
    
    def get_collection_info(self) -> dict:
        """
        Возвращает информацию о коллекции.
        
        Returns:
            Словарь с информацией о коллекции
        """
        return {
            'name': self.embedding_store.collection.name,
            'count': self.embedding_store.collection.count(),
            'model': self.embedding_store.embedding_model
        }

