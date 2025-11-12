# Умный FAQ — RAG-сервис

Мини-сервис для ответов на вопросы пользователей поверх базы знаний компании. Бэкенд написан на FastAPI, использует Redis, Qdrant и поставляется с простым веб-интерфейсом.

- **PostgreSQL** хранит историю запросов (вопрос, ответ, токены, время, источники).
- **Redis** кэширует ответы на 1 час, снижая нагрузку.
- **Qdrant** обеспечивают векторный поиск по чанкам документов.
- **LLM Service** работает с Anthropic/OpenAI, а при отсутствии ключей возвращает детерминированный оффлайн ответ.

## Быстрый старт в Docker Compose
1. Скопируйте переменные окружения:
   ```bash
   cp .env.example .env
   ```
   Укажите ключи `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`, если нужны ответы от LLM.
2. Соберите и запустите сервисы:
   ```bash
   docker compose up --build
   ```
   (альтернатива: `make up`, см. `makefile`).
3. После запуска:
   - API: http://localhost:8000
   - Swagger: http://localhost:8000/docs
   - Веб-интерфейс: http://localhost:8000/

## API

 `POST` | `/api/ask` | принимает запрос (`question`) и возвращает ответ LLM и источники 

 `POST` | `/api/documents` | загружает `.txt`/`.md`/`.pdf` файл в базу знаний

 `GET` | `/api/health` | healthcheck для внешних систем

 `GET` | `/api/metrics` | агрегированная статистика запросов

## Документы и RAG
- Сложите исходные материалы в каталог `documents/` (пример — `documents/*.
- Выполните `make init-docs` или `python scripts/init_documents.py`, чтобы загрузить их в Qdrant/Memory.
- Скрипт `scripts/eval_quality.py` выполняет проверку качества ответов (keyword recall) и выводит JSON-отчет.

## Тесты
- Локально: `pytest -q`
- В контейнере: `make test`

## Структура `.env`
См. `./.env.example` — перечислены обязательные и опциональные переменные

## Cкриншоты AI
<img width="1920" height="1243" alt="Screenshot" src="https://github.com/user-attachments/assets/f13ed8b1-8ddc-4801-a0d5-0b0114be7983" />
