# Шпаргалка по GitHub (чтобы не искать)

Репозиторий: https://github.com/tashis-ai/fl_support_demo_bot

GitHub часто двигает кнопки. Ниже — **прямые ссылки** и куда что делось.

---

## Прямые ссылки (сохраните в закладки)

| Что нужно | Ссылка |
| --- | --- |
| Код | https://github.com/tashis-ai/fl_support_demo_bot |
| **Settings** | https://github.com/tashis-ai/fl_support_demo_bot/settings |
| Collaborators | https://github.com/tashis-ai/fl_support_demo_bot/settings/access |
| Secrets (Actions) | https://github.com/tashis-ai/fl_support_demo_bot/settings/secrets/actions |
| Danger Zone (удалить / private) | https://github.com/tashis-ai/fl_support_demo_bot/settings#danger-zone |

Вкладка Settings в меню часто **не видна** (уезжает вправо). Открывайте по ссылке выше.

---

## Description и Topics (метки)

**В Settings их больше нет.** Только так:

1. Открыть вкладку **Code** (главная страница репо).
2. Справа блок **About**.
3. Нажать ⚙️.
4. Заполнить Description и Topics → Save.

Если блока About не видно — расширьте окно или прокрутите страницу; у пустого репозитория вёрстка иногда странная.

Через терминал (один раз настроили — и не нужно лазить по UI):

```powershell
gh auth login

gh repo edit tashis-ai/fl_support_demo_bot `
  --description "RAG Telegram-бот поддержки онлайн-школы: ответы по базе знаний (ProxyAPI + ChromaDB)" `
  --add-topic telegram-bot `
  --add-topic rag `
  --add-topic python `
  --add-topic chromadb
```

---

## Залить код с компьютера

В папке проекта:

```powershell
cd "D:\WBCODE\PEcf09 logs"

git remote add origin https://github.com/tashis-ai/fl_support_demo_bot.git
# если remote уже есть: git remote set-url origin https://github.com/tashis-ai/fl_support_demo_bot.git

git branch -M main
git push -u origin main
```

`.env` в git не попадёт (он в `.gitignore`).

---

## Что где искать (кратко)

| Хочу… | Где |
| --- | --- |
| Описание репо | Code → About → ⚙️ |
| Метки (topics) | туда же |
| Settings | прямая ссылка `/settings` |
| Сделать private | Settings → вниз → Danger Zone |
| Секреты CI | Settings → Secrets and variables → Actions |

---

Если снова «пропало» — не вы сломали: GitHub переставил интерфейс. Открывайте **прямую ссылку** из таблицы выше.
