# blanks_checker

Веб-приложение для автоматического чтения бланков ответов (тестовых форм). Выравнивает отсканированный бланк по чёрным маркерам, бинаризует страницу, вырезает области (вариант, дата, регистрационный номер, строки ответов/замен) и распознаёт символы в ячейках с помощью нейросети (OCR). Результаты хранятся в БД, доступны веб-интерфейс и экспорт в Excel.

## Архитектура

- **Backend**: FastAPI, пайплайн обработки (PDF → выравнивание → вырезка ячеек → OCR), PostgreSQL, Redis, S3-совместимое хранилище (MinIO).
- **Frontend**: React 19, Vite, TypeScript, React Router, shadcn/ui.
- **Развёртывание**: Docker Compose (backend, frontend через nginx, PostgreSQL, MinIO, Redis).

## Структура проекта

```
blanks_checker/
├── backend/                    # API и пайплайн обработки
│   ├── app/
│   │   ├── main.py             # FastAPI-приложение, роуты под /api
│   │   ├── pipeline.py         # CLI: выравнивание + вырезка (для обратной совместимости)
│   │   ├── alignment/          # Выравнивание по маркерам
│   │   │   ├── align.py        # align_form_from_image, align_pdf_form
│   │   │   ├── markers.py      # detect_black_square_markers, order_points
│   │   │   └── warp.py         # warp_keep_full_page
│   │   ├── rows/               # Поиск строк и вырезка ячеек
│   │   │   ├── extract.py      # extract_cells_to_result, extract_cells
│   │   │   ├── cells.py        # split_cells, сохранение вырезок
│   │   │   ├── grid.py         # detect_rows_by_grid
│   │   │   ├── header.py       # crop_to_grid_only (заголовочные ROI)
│   │   │   ├── morphology.py  # Адаптивная бинаризация, линии сетки
│   │   │   └── line_clean.py  # remove_grid_lines
│   │   ├── ocr/                # Распознавание символов в ячейках
│   │   │   ├── cell_ocr.py     # recognize_cell (нейросеть)
│   │   │   └── resnet18_mnist.pth
│   │   ├── services/
│   │   │   ├── pipeline.py     # run_blanks_pipeline (in-memory: PDF bytes → результат)
│   │   │   ├── pdf_loader.py   # pdf_bytes_to_bgr, pdf_page_count
│   │   │   ├── recognized_blanks.py
│   │   │   ├── auth.py
│   │   │   ├── export_blanks.py
│   │   │   └── number_validation.py
│   │   ├── api/                # Роуты: auth, blank-check, blanks CRUD, export
│   │   ├── db/                 # SQLAlchemy, модели, сессии
│   │   ├── storage/            # S3-клиент (загрузка выровненных изображений)
│   │   ├── preprocessing/
│   │   │   └── image_utils.py  # Бинаризация, crop_rel
│   │   └── schemas/
│   ├── alembic/                # Миграции БД
│   ├── pyproject.toml
│   └── uv.lock
├── frontend/
│   ├── src/
│   │   ├── pages/              # UploadPage, ListPage, EditPage, AuthPage, UsersPage
│   │   ├── components/         # CorrectionForm, ProtectedRoute, UI (shadcn)
│   │   └── api/                # blankCheck, auth, backendHealth
│   ├── package.json
│   └── Dockerfile              # Сборка статики + nginx
├── docker-compose.yml          # backend, db, minio, redis, nginx
├── .env.example
└── README.md
```

## Запуск

### Через Docker Compose (рекомендуется)

1. Скопируйте `.env.example` в `.env` и при необходимости отредактируйте (пароли, JWT_SECRET и т.д.).
2. Запустите сервисы:

```bash
docker compose up -d
```

Приложение будет доступно по адресу **http://localhost** (порт 80). Фронтенд — `/`, API — `/api/`.

### Локально (разработка)

**Backend** (из корня репозитория):

```bash
cd backend
uv sync
# Поднять PostgreSQL, MinIO, Redis (или через docker compose up -d db minio redis)
# Заполнить .env (DB_HOST=localhost и т.д., S3_ENDPOINT_URL=http://localhost:9000)
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend**:

```bash
cd frontend
npm install
npm run dev
```

После этого фронт обычно на http://localhost:5173; API — на http://localhost:8000 (нужно настроить прокси или `VITE_API_URL` при необходимости).

### CLI-пайплайн (без веб-сервера)

Из каталога `backend`:

```bash
uv run python -m app.pipeline
```

По умолчанию читается `examples/1410.pdf` (или другой путь в коде), результат выравнивания и вырезки можно сохранять, передавая `aligned_path` и `rows_out_dir`. Для полного in-memory пайплайна с OCR используйте `app.services.pipeline.run_blanks_pipeline`.

## Переменные окружения

Основные переменные (см. `.env.example`):

| Переменная | Описание |
|------------|----------|
| `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` | PostgreSQL |
| `ADMIN_LOGIN`, `ADMIN_PASSWORD` | Учётные данные первого админа (bootstrap) |
| `JWT_SECRET` | Секрет для JWT (обязательно сменить в продакшене) |
| `S3_ENDPOINT_URL`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_BUCKET_NAME` | S3/MinIO |
| `REDIS_HOST`, `REDIS_PORT` | Redis |

## API (кратко)

- `GET /api/ready` — healthcheck.
- `POST /api/auth/login` — вход (login, password) → JWT.
- `GET /api/auth/me` — текущий пользователь (нужен Bearer token).
- `POST /api/blank-check`, `POST /api/v1/blank-check` — загрузка PDF, указание страницы → распознавание бланка (вариант, дата, рег. номер, ответы, замена).
- `POST /api/v1/blank-check/multi` — обработка всех страниц PDF; при ошибках по страницам возвращается 422 с данными для ручной проверки.
- `POST /api/v1/blank-check/corrections` — сохранение исправлений после ручной проверки.
- `GET /api/v1/blanks` — список распознанных бланков (фильтры: поиск, только не проверенные).
- `GET /api/v1/blanks/{id}` — один бланк для редактирования.
- `PATCH /api/v1/blanks/{id}/verified` — установка флага «проверено».
- `DELETE /api/v1/blanks/{id}` — удаление бланка.
- `GET /api/v1/export` — скачивание всех бланков в виде Excel.
- `GET /api/files/{object_key}` — прокси к S3 (только для авторизованных).

## Модули backend (кратко)

- **alignment**: поиск чёрных угловых маркеров (`markers`), упорядочивание точек, перспективное преобразование (`warp`), выравнивание по PDF или по изображению (`align`).
- **rows**: относительные ROI заголовка (вариант, дата, рег. номер), поиск строк ответов/замен по сетке (`grid`, `morphology`), разбиение на ячейки (`cells`), вырезка в результат или в файлы (`extract`).
- **ocr**: распознавание символа в одной ячейке (E, -, 0–9, S) через нейросеть.
- **services/pipeline**: `run_blanks_pipeline(pdf_bytes, ...)` — загрузка страницы, выравнивание, вырезка ячеек, OCR по всем полям; возвращает структурированный словарь и опционально PNG выровненной страницы.

## Отладочные изображения (debug)

При `debug=True` пайплайн может сохранять отладочные картинки. Основные места:

- **alignment**: `debug_dir/debug_bw_*.png` (бинаризованные ROI углов), `debug_dir/aligned_raw.png`.
- **rows**: `rows_out/_debug_header/` (вариант, дата, рег. номер — roi_raw, roi_bw_inv, линии сетки, grid_bbox), `rows_out/_debug_grid/` (left/right — table_roi_raw, table_bw_inv, линии, проекции, rows_bbox_full).

## Зависимости

- **Backend**: Python ≥ 3.10, OpenCV, NumPy, PyMuPDF, PyTorch (CPU), FastAPI, SQLAlchemy, asyncpg, aioboto3, Alembic, bcrypt, python-jose, openpyxl и др. (см. `backend/pyproject.toml`). Установка: `cd backend && uv sync`.
- **Frontend**: Node.js, React 19, Vite, TypeScript, Tailwind, shadcn/ui, axios, react-router-dom, zod и др. (см. `frontend/package.json`). Установка: `cd frontend && npm install`.
