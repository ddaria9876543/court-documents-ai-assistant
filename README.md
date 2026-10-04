# Помощник для анализа судебных и исполнительных документов

## Система для автоматической обработки судебных и исполнительных документов. 
Принимаются документы в следующих форматах:
1. PDF с текстовым слоем;
2. сканированные PDF;
3. XML ФССП.

## Задачи системы
1. определяет тип документа;
2. распознаёт текст в сканированных документах;
3. извлекает реквизиты;
4. валидирует поля;
5. помечает документы, требующие проверки или работы юриста;
6. позволяет подтвердить или исправить данные;
7. экспортирует в XLSX/CSV;
8. отправляет документ ответственному по e-mail.

## Ограничения
1. качество OCR зависит от качества скана;
2. часть неоднозначных полей требует ручной проверки;
3. LLM работает локально;
4. MVP ориентирован только на предоставленные типы документов

## Поддерживаемые типы документов
1. судебный приказ;
2. исполнительный лист;
3. постановление ФССП.

## Архитектура:
1. frontend - интерфейс пользователя;
2. backend - API, БД, загрузка документов, экспорт, e-mail, взаимодействие с document_processing;
3. document_processing - PDF/XML обработка, OCR, LLM-извлечение, валидация.

Пользователь
↓
React Frontend
↓
FastAPI Backend
↓
Document Processing 
|-- PDF/XML 
|-- PyMuPDF 
|-- Tesseract OCR 
|-- OpenCV 
|-- XML parser 
|-- Qwen3 4B через Ollama
↓
PostgreSQL
↓
XLSX / CSV / e-mail

## Стек
### Backend:
- Python
- FastAPI
- uvicorn[standard]
- SQLAlchemy
- Alembic
- PostgreSQL

### Document processing:
- Tesseract OCR
- lxml
- OpenCV
- PyMuPDF
- Qwen3 4B через Ollama

### Frontend:
- React
- TypeScript
- Vite
- Ant Design

## Системные зависимости
- Python 3.10+
- PostgreSQL через Docker Compose
- Node.js + npm
- Docker Desktop
- Tesseract OCR
- rus.traineddata
- Ollama
- qwen3:4b

## Переменные окружения

Создайте файл `.env` на основе `.env.example`.

Пример:
```env
POSTGRES_DB=court_docs
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:55432/court_docs

SMTP_HOST=
SMTP_PORT=465
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM=
SMTP_RECIPIENT=
SMTP_USE_TLS=false
SMTP_USE_SSL=true
```

## Запуск системы с локального устройства производится по следующей схеме:
1. С помощью любой среды в терминал PowerShell копируется репозиторий проекта следующим кодом:
```git clone https://git.codenrock.com/codenrock/ii-assistenty/ii-sestry/pomoshchnik-dlya-analiza-dokumentov-iz-sudov-ocr-i-izvlechenie-dannykh.git
cd pomoshchnik-dlya-analiza-dokumentov-iz-sudov-ocr-i-izvlechenie-dannykh
```
2. Создаётся окружение
```python -m venv .venv
.\.venv\Scripts\Activate.ps1
```
3. Устанавливаются зависимости, подключается Ollama, PostgreSQL. 
Перед docker compose up необходимо открыть docker desktop
```pip install -r backend\requirements.txt
pip install -r document_processing\requirements.txt
ollama pull qwen3:4b
cd backend
docker compose up -d
```
4. Проводятся миграции. В нынешнем окне запускаем backend.
```python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```
5. Открывается новое окно терминала PowerShell для запуска frontend
```.\.venv\Scripts\Activate.ps1
cd frontend
npm install
npm run dev
```
6. После активации frontend производится переход по ссылке,
указанной в терминале после Local. В проекте используются следующие адреса:
Frontend: http://127.0.0.1:5173
Backend: http://127.0.0.1:8000
Ollama: http://localhost:11434

## Быстрая проверка

После запуска:
1. откройте http://127.0.0.1:5173;
2. загрузите PDF или XML;
3. дождитесь обработки;
4. откройте карточку документа;
5. проверьте извлечённые поля;
6. при необходимости подтвердите или исправьте данные;
7. сформируйте XLSX/CSV.