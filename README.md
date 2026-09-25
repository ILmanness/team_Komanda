# Арена переговоров

Окружение разработки MVP AI-симулятора переговоров. План демонстрации — 30 сентября 2026 года.

## Что сейчас реализовано

| Часть | Состояние |
|---|---|
| БД | 9 таблиц, миграции, ограничения, автоматическая очистка старых сессий |
| Backend | FastAPI: авторизация, каталог, игровые сессии, движок, ходы через WebSocket и защищённый редактор контента |
| Frontend | React-интерфейс: тренировки, сюжетные миссии, свой диалог, история разговоров, база знаний, авторизация и админка |
| AI | Игровой движок с оценкой и ответом собеседника. По умолчанию `AI_PROVIDER=mock`: ответы и оценка демонстрационные |

Пароль пользователя представлен полем **users.password_hash** (миграция 0002), а отдельный логин — полем **users.login** (миграция 0003).
В нём хранится хеш, не исходный пароль. Endpoint'ы авторизации доступны в Swagger.
Весь data design: [docs/data_architecture.md](docs/data_architecture.md).
Связь экранов с API и недостающие контракты: [docs/frontend_api_gaps.md](docs/frontend_api_gaps.md).

## 1. Проверить инструменты

Нужны Git, запущенный Docker и Compose v2. На Windows/macOS можно использовать Docker Desktop,
на Linux — Docker Engine с Compose plugin. Проект использует Linux-контейнеры.
Python, Node.js и PostgreSQL на компьютере устанавливать не нужно.

Откройте PowerShell на Windows или терминал Linux/macOS:

~~~sh
git --version
docker version
docker compose version
~~~

У docker version должны быть разделы Client и Server. Если Server недоступен,
запустите Docker и дождитесь его готовности.

## 2. Скачать проект

Если локальной копии нет:

~~~sh
git clone --branch main https://github.com/ILmanness/team_Komanda.git
cd team_Komanda
~~~

Если проект уже скачан, перейдите в его папку, выполните git status и сохраните свою
незакоммиченную работу перед переключением ветки. Затем:

~~~sh
git fetch origin
git switch main
git pull --ff-only
~~~

**Все дальнейшие команды выполняются из корня проекта, где лежит compose.yaml.**
Инструкция относится к объединённому main.

## 3. Создать настройки

Только если файла .env ещё нет, скопируйте пример. Существующий .env не перезаписывайте.

В PowerShell:

~~~powershell
Copy-Item .env.example .env
~~~

В Linux/macOS/Git Bash:

~~~sh
cp .env.example .env
~~~

Откройте .env в редакторе. До первого запуска замените POSTGRES_PASSWORD своим паролем.
Это пароль подключения к PostgreSQL, **не пароль игрового пользователя**.
Остальные настройки для первого запуска можно оставить как в примере.

Также замените AUTH_SECRET_KEY случайным секретом для подписи JWT. Если .env уже существовал,
добавьте эту переменную: без неё backend и миграции не запустятся. Сгенерировать значение
после создания .env можно командой ниже (скопируйте результат в AUTH_SECRET_KEY):

~~~sh
docker compose run --rm --build --no-deps migrate python -c "import secrets; print(secrets.token_hex(32))"
~~~

| Переменная | Значение / назначение |
|---|---|
| POSTGRES_DB | arena — имя базы |
| POSTGRES_USER | arena — пользователь PostgreSQL |
| POSTGRES_PASSWORD | Ваш пароль БД |
| DB_PORT | 5432 — порт БД на компьютере |
| BACKEND_PORT | 8000 — порт API |
| FRONTEND_PORT | 5173 — порт интерфейса |
| AI_PROVIDER | mock — запуск без ключей и запросов к платному API |
| AUTH_SECRET_KEY | Собственный случайный секрет подписи JWT; не публиковать |

.env исключён из Git. Не коммитьте пароли и API-ключи.
`DB_PORT` задаёт только порт на компьютере для DBeaver и других локальных клиентов.
Внутри контейнеров адрес БД автоматически задан как `db:5432`, поэтому отдельный
`POSTGRES_PORT` в `.env` для запуска через Docker Compose не нужен.

## 4. Запустить окружение

~~~sh
docker compose config --quiet
docker compose up --build -d
docker compose ps -a
~~~

Первая команда проверяет настройки; отсутствие вывода означает успех.
Вторая скачивает образы, устанавливает зависимости и запускает окружение в фоне.
Первый запуск требует интернета и может занять несколько минут.
Третья показывает состояние контейнеров; повторяйте её, пока они запускаются.

| Сервис | Ожидаемый статус | Назначение |
|---|---|---|
| db | Up / healthy | PostgreSQL и постоянное хранение данных |
| migrate | Exited (0) | Успешно применил миграции 0001–0003 и завершился |
| backend | Up / healthy | FastAPI |
| cleanup | Up | Периодическая очистка |
| frontend | Up / healthy | React/Vite |

**Exited (0) у migrate — нормально.** Другой код означает ошибку.
Игровой контент и пользователи автоматически не создаются. Для локальной проверки можно отдельно загрузить демоданные и создать администратора (раздел 5).

Если нужны только БД и таблицы, вместо полного запуска выполните:

~~~sh
docker compose up -d db
docker compose run --rm --build migrate
~~~

Этот вариант не запускает frontend, API и автоматическую очистку.
При необходимости очистку включите отдельно: docker compose up -d cleanup.

## 5. Проверить результат

Откройте в браузере следующие адреса. Если меняли порты в .env, подставьте свои значения.

| Адрес | Ожидаемый результат |
|---|---|
| http://localhost:5173 | Главный экран с переходами в тренировку, сюжет, PvP и базу знаний |
| http://localhost:8000/docs | Swagger с существующими API |
| http://localhost:8000/health/live | JSON со статусом ok |
| http://localhost:8000/health/ready | status=ok, database=ready, ai_provider=mock |

Проверьте схему:

~~~sh
docker compose run --rm migrate alembic current
~~~

Ожидается **0003 (head)**. В users должны быть поля password_hash и login.
Readiness не вызывает модель и не проверяет ключ внешнего AI.

Для локальной проверки можно загрузить опубликованные демосюжет, две миссии, тренировку с вариантами ответа, персонажей и тему знаний:

~~~sh
docker compose exec backend python -m app.admin.seed_demo --apply
~~~

Повторный запуск не создаёт дубликаты и не меняет уже существующие материалы. Данные помечены словом «Демо».
Для доступа к редактору создайте или повысьте конкретную учётную запись. Команда запрашивает пароль в терминале без вывода введённых символов:

~~~sh
docker compose exec backend python -m app.admin.bootstrap --login admin --email admin@example.com --display-name admin
~~~

После входа откройте `/admin`. Публикуйте сначала тему знаний или сюжетную ветку, затем связанную тренировку или миссию. Новая регистрация требует логин, почту, отображаемое имя и пароль. Войти можно по логину или почте.

## 6. Обновить существующую БД без потери данных

Если БД уже запускалась на миграции 0001, удалять её не нужно.
Сначала сохраните свою работу в Git и сделайте резервную копию по разделу 11.
После переключения на эту ветку выполните:

~~~sh
git pull --ff-only
docker compose stop backend frontend cleanup
docker compose build
docker compose up -d db
docker compose run --rm migrate
docker compose run --rm migrate alembic current
docker compose up -d
docker compose ps -a
~~~

Если миграция завершилась с ошибкой, остановитесь до запуска приложений и прочитайте её вывод.
0002 и 0003 добавляют колонки к существующей таблице, сохраняя пользователей.
У старых пользователей password_hash остаётся NULL: пароль ещё не задан.
Для старых записей 0003 создаёт уникальный технический логин вида `user-<uuid>`.
Вход по паролю для таких записей недоступен.
Миграция не назначает общий пароль и не создаёт фиктивные хеши.

Этот же порядок используйте при следующих обновлениях проекта.
Не изменяйте уже применённые миграции; добавляйте новые.

## 7. Работать с кодом и контейнерами

Редактируйте backend/ и frontend/ в своей IDE. Эти папки примонтированы в контейнеры:
FastAPI перезапускается при изменении Python-кода, Vite обновляет frontend.
Обычные изменения исходников не требуют пересборки.

Просмотр логов:

~~~sh
docker compose logs --tail=100 backend
docker compose logs --tail=100 migrate
docker compose logs -f frontend backend
~~~

Ctrl+C завершает просмотр логов, но не останавливает контейнеры.

Войти в терминал нужного контейнера:

~~~sh
docker compose exec backend sh
docker compose exec frontend sh
~~~

Внутри контейнера рабочая папка — /app; exit возвращает в терминал компьютера.
Там запускайте обычные pytest, alembic current, npm test без префикса docker compose.
Из терминала компьютера тот же вызов выглядит так:

~~~sh
docker compose exec backend pytest -q
~~~

Точные зависимости зафиксированы в backend/requirements.lock и frontend/package-lock.json.
При изменении зависимостей обновите соответствующий lock-файл и пересоберите окружение по разделу 6.
Новая миграция создаётся так:

~~~sh
docker compose exec backend alembic revision -m "describe change"
~~~

Заполните upgrade/downgrade в созданном файле и примените через сервис migrate.
ORM-моделей для autogenerate пока нет.

## 8. Посмотреть таблицы и пользователей

Для стандартных POSTGRES_USER=arena и POSTGRES_DB=arena:

~~~sh
docker compose exec db psql -U arena -d arena
~~~

Если меняли эти настройки, подставьте свои значения вместо arena.
Внутри psql выполните по очереди:

~~~sql
\dt
\d users
SELECT version_num FROM alembic_version;
SELECT id, login, display_name, email, role, password_hash IS NOT NULL AS has_password FROM users;
\q
~~~

Первая команда показывает таблицы, вторая — колонки users, последняя — выход.
Будет 9 таблиц приложения и служебная alembic_version.

Не записывайте исходный пароль в password_hash. Поле предназначено для результата
стойкого алгоритма хеширования паролей с солью. Используйте endpoint регистрации в Swagger.
Хеш не возвращают в API, не показывают на frontend и не пишут в логи.

Для DBeaver/pgAdmin используйте host localhost, port из DB_PORT и реквизиты из .env.
Адрес db:5432 работает между контейнерами, а не в SQL-клиенте на компьютере.

## 9. Подключить AI при необходимости

С AI_PROVIDER=mock ключ не нужен: клиент возвращает фиксированную реплику.
Для провайдера с endpoint /chat/completions измените .env:

~~~dotenv
AI_PROVIDER=compatible
AI_BASE_URL=https://your-provider.example/v1
AI_API_KEY=your-private-key
AI_MODEL=provider-model-id
AI_TIMEOUT_SECONDS=30
~~~

Замените URL, ключ и модель реальными значениями провайдера. Затем:

~~~sh
docker compose up -d --force-recreate backend cleanup
docker compose exec backend python -m app.ai
~~~

Последняя команда делает пробный запрос, который провайдер может тарифицировать.
Она проверяет клиент, а не игровой процесс. Не переносите ключ в переменные VITE_*.

## 10. Настроить хранение истории

При полном запуске cleanup автоматически удаляет истёкшие данные.

| Переменная .env | По умолчанию | Поведение |
|---|---:|---|
| HISTORY_RETENTION_DAYS | 7 | Через столько дней после завершения удалить сообщения, state, memory_summary, custom_context и config_snapshot |
| SESSION_RETENTION_DAYS | 30 | Через столько дней после завершения удалить сессию и final_result |
| ACTIVE_SESSION_IDLE_DAYS | 30 | После такого простоя пометить активную игру abandoned; с этого момента идут сроки хранения |
| RETENTION_INTERVAL_SECONDS | 3600 | Пауза между проходами очистки |

Срок сессии должен быть не меньше срока истории. Значение 0 у срока сессии/истории означает
удаление на ближайшем проходе после завершения. Один проход обрабатывает до 200 записей каждого типа.
После изменения .env выполните docker compose up -d --force-recreate backend cleanup.

Посмотреть кандидатов на очистку без сохранения изменений:

~~~sh
docker compose exec backend python -m app.retention
~~~

Фактически удалить данные:

~~~sh
docker compose exec backend python -m app.retention --apply
~~~

После удаления сессии исчезает её результат. Долговременный прогресс сюжетки пока не реализован.
final_result может содержать текст до удаления сессии. Резервные копии очищаются отдельно.

## 11. Создать резервную копию

Для стандартных имени пользователя и БД arena (замените их, если меняли .env):

~~~sh
docker compose exec db pg_dump -U arena -d arena -Fc -f /tmp/arena-backup.dump
docker compose cp db:/tmp/arena-backup.dump ./arena-backup.dump
~~~

Команды одинаковы для PowerShell и Bash: дамп создаётся внутри контейнера, затем копируется на компьютер.
Проверьте, что файл появился и имеет ненулевой размер. Сохраните отдельную датированную копию:
повторный запуск использует то же имя. Дамп содержит данные и хеши; не публикуйте его.

Проверить восстановление в отдельной, ещё не существующей БД:

~~~sh
docker compose cp ./arena-backup.dump db:/tmp/arena-restore.dump
docker compose exec db createdb -U arena arena_restore_check
docker compose exec db pg_restore -U arena -d arena_restore_check --exit-on-error /tmp/arena-restore.dump
docker compose exec db psql -U arena -d arena_restore_check -c "SELECT version_num FROM alembic_version;"
~~~

Рабочая БД не подменяется. Если arena_restore_check уже существует, используйте другое имя.

## 12. Запустить проверки

Окружение должно быть запущено. Из корня проекта:

~~~sh
docker compose exec backend pytest -q
docker compose exec backend ruff check app tests migrations
docker compose exec -e RUN_DB_TESTS=1 backend pytest -q
docker compose exec frontend npm run build
docker compose exec frontend npm test
~~~

Первый вызов пропускает DB-тесты (skipped). Третий запускает также интеграционные тесты БД:
миграции, сохранение пользователей, хранение хеша, ограничения и очистку.
Каждый тест создаёт отдельную схему arena_test_* и удаляет только её.
Используйте dev-БД, не production-реквизиты.

В Bash/Git Bash полный набор можно запустить через sh infrastructure/smoke.sh.
Скрипт оставляет контейнеры работающими.

## 13. Остановить и запустить повторно

Приостановить с сохранением данных:

~~~sh
docker compose stop
~~~

Продолжить после stop:

~~~sh
docker compose start
~~~

Удалить контейнеры и сеть, сохранив PostgreSQL-volume:

~~~sh
docker compose down
~~~

После down запускайте через docker compose up -d.
**Не добавляйте -v к down, если хотите сохранить БД:** этот флаг удаляет volumes.
Для обновления схемы он не нужен.

## Если что-то не работает

| Симптом | Что делать |
|---|---|
| Cannot connect to Docker daemon | Запустить Docker, проверить раздел Server в docker version |
| .env не найден | Выполнить шаг 3 из корня проекта |
| Port is already allocated | Изменить соответствующий DB_PORT/BACKEND_PORT/FRONTEND_PORT и повторить docker compose up -d |
| migrate завершился с ошибкой | Посмотреть docker compose logs --tail=100 migrate; повторить docker compose run --rm migrate и прочитать ошибку |
| password_hash не найден | Выполнить docker compose run --rm --build migrate, проверить alembic current |
| Backend unhealthy / readiness 503 | Проверить логи backend, готовность db и миграции до 0003 |
| Frontend не соединяется с API | Проверить backend/ready и docker compose logs --tail=100 frontend backend |
| Неверный пароль БД после изменения .env | .env не меняет пароль существующего PostgreSQL-volume. Вернуть прежнее значение либо отдельно изменить пароль роли в БД и согласовать .env; volume не удалять |
| Зависимости не обновились | Проверить lock-файлы и пересобрать по разделу 6 |
| Ошибка AI compatible | Проверить URL, ключ и модель; для инфраструктуры вернуть mock |

Это локальное dev-окружение: порты опубликованы на 127.0.0.1, приложение использует
реквизиты с правами миграции. Перед публичным развёртыванием нужны проверка авторизации,
TLS, разграничение прав и production-настройки.

## Документация проекта

- [Данные, таблицы и сессии](docs/data_architecture.md)
- [Продукт и игровой процесс](docs/product_and_game_design.md)
- [Scoring и состояние игры](docs/scoring_and_game_state.md)
- [Сложность уровней](docs/level_difficulty_design.md)
- [План разработки и roadmap MVP](docs/development_plan.md)
