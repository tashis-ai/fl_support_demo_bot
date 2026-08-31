# RAG-ассистент онлайн-школы

Telegram-бот поддержки на базе **RAG** (поиск по базе знаний + генерация ответа).  
Отвечает на вопросы о курсах, сертификации и программах онлайн-школы.

- LLM и эмбеддинги: [ProxyAPI](https://proxyapi.ru/) (OpenAI-совместимый API)
- Векторное хранилище: ChromaDB (локально)
- Интерфейс: Telegram (`python-telegram-bot`)
- Логи: SQLite (`logs.db`)

---

## Быстрый старт

### 1. Клонирование и окружение

```bash
git clone <url-вашего-репозитория>
cd <папка-проекта>

python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Настройка `.env`

```bash
cp env.example .env
```

Заполните как минимум:

| Переменная | Описание |
| --- | --- |
| `PROXYAPI_API_KEY` | Ключ ProxyAPI |
| `PROXYAPI_BASE_URL` | `https://api.proxyapi.ru/openai/v1` |
| `PROXYAPI_MODEL` | Например `gpt-4o-mini` |
| `TELEGRAM_BOT_TOKEN` | Токен от [@BotFather](https://t.me/BotFather) |
| `APP_MODE` | `3` — Telegram (по умолчанию) |

Опционально:

- `TELEGRAM_PROXY` — прокси **только** для Telegram (на VPS обычно не нужен)
- `EMBEDDING_MODEL` — по умолчанию `text-embedding-3-small`

**Не коммитьте `.env`** — файл уже в `.gitignore`.

### 3. Запуск

```bash
python main.py
```

Режим задаётся в `.env` (`APP_MODE`), в консоли режим не спрашивается:

- `3` / `telegram` — Telegram-бот
- `1` / `interactive` — консоль
- `2` / `demo` — демо-вопросы

Остановка: `Ctrl+C`.

---

## Как это работает

1. Пользователь задаёт вопрос в Telegram.
2. Проверяется кеш ответов (`cache.json`).
3. Если ответа нет — семантический поиск по фрагментам базы знаний (ChromaDB).
4. Контекст + вопрос отправляются в LLM через ProxyAPI.
5. Ответ кешируется и пишется в `logs.db`.

Прокси Telegram **не** используется для запросов к ProxyAPI.

---

## База знаний

Тексты лежат в `docs/*.txt`. Список в коде указывать не нужно: при **пустой** ChromaDB файлы подхватываются автоматически.

| Файл | Содержание |
| --- | --- |
| `docs/progs.txt` | Курсы для специалистов |
| `docs/sert.txt` | Сертификация |
| `docs/rk.txt` | Курсы для родителей |

После изменения `.txt`:

1. Остановите бота.
2. Удалите `chroma_db/` (и при необходимости `cache.json`).
3. Запустите снова.

---

## Команды бота

| Команда | Описание |
| --- | --- |
| `/start` | Приветствие |
| `/help` | Справка и примеры вопросов |
| `/stats` | Статистика: документы, кеш, логи |
| `/logs` | CSV со **всеми** логами |

Обычное текстовое сообщение обрабатывается как вопрос к базе знаний.

---

## Структура проекта

```
.
├── main.py              # Точка входа
├── telegram_bot.py      # Telegram-бот
├── rag.py               # RAG: поиск + генерация
├── embeddings.py        # Эмбеддинги и ChromaDB
├── cache.py             # Кеш ответов
├── db_logger.py         # Логи в SQLite
├── docs/                # База знаний (.txt)
├── env.example          # Шаблон настроек
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── ИНСТРУКЦИЯ.md        # Расширенная шпаргалка
```

Runtime (не в git): `.env`, `chroma_db/`, `cache.json`, `logs.db`, `data/`.

---

## Docker

```bash
cp env.example .env
# заполните PROXYAPI_API_KEY и TELEGRAM_BOT_TOKEN

mkdir -p data
echo '{}' > data/cache.json
touch data/logs.db

docker compose up -d --build
docker compose logs -f
```

Тома: `docs/` (только чтение), `data/chroma_db`, `data/cache.json`, `data/logs.db`.

Long polling — наружные порты не нужны.

---

## Типичные проблемы

| Симптом | Что проверить |
| --- | --- |
| `ConnectError` / обрыв Telegram | Сеть или `TELEGRAM_PROXY` (локально в РФ) |
| Нет ответов / ошибка API | `PROXYAPI_API_KEY`, `PROXYAPI_BASE_URL` |
| База не видит новые `.txt` | Удалить `chroma_db/` и перезапустить |
| Кириллица в CSV «ломается» | Открывать в Excel; экспорт идёт с UTF-8 BOM и `;` |

---

## Лицензия

Учебный / демонстрационный проект. Используйте и модифицируйте свободно под свои задачи.
