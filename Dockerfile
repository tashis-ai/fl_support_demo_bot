# RAG Telegram-бот поддержки онлайн-школы
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_MODE=3

WORKDIR /app

# Системные зависимости для chromadb / сборки колёс
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY *.py ./
COPY docs/ ./docs/

# Данные создаются при первом запуске; тома монтируются снаружи
RUN mkdir -p /app/chroma_db

CMD ["python", "main.py"]
