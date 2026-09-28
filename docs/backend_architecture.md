##№1. Общая архитектура проекта

Главная идея: REST отвечает за управление ресурсами, WebSocket — за игровой процесс.

                   FRONTEND
                       │
          ┌────────────┴────────────┐
          │                         │
          ▼                         ▼
     REST API                  WebSocket
     HTTP Requests             Real-time Game
          │                         │
          └────────────┬────────────┘
                       │
                       ▼
                BACKEND SERVER
                       │
          ┌────────────┼────────────┐
          │            │            │
          ▼            ▼            ▼
      Auth        Game Service   Catalog
      Service                    Service
                       │
                       ▼
                GAME ENGINE
                       │
          ┌────────────┼────────────┐
          │            │            │
          ▼            ▼            ▼
      Context      Evaluator    AI Opponent
      Builder
                       │
                       ▼
                   PostgreSQL
#Аутентификация
  POST /api/v1/auth/register
  POST /api/v1/auth/login
  POST /api/v1/auth/logout
  GET  /api/v1/users/me
#Каталог игры
  GET /api/v1/storylines
  GET /api/v1/storylines/{id}

  GET /api/v1/missions
  GET /api/v1/missions/{id}

  GET /api/v1/knowledge
  GET /api/v1/knowledge/{id}
#Конфигурация
  GET /api/v1/game-config/characters
  GET /api/v1/game-config/paei-profiles
  GET /api/v1/game-config/difficulty-profiles
#Игровые сессии
  POST /api/v1/sessions
  GET  /api/v1/sessions
  GET  /api/v1/sessions/{id}
  POST /api/v1/sessions/{id}/finish

## Атомарность игрового хода

`GameService` сначала получает структурированную оценку и полный ответ
персонажа. Затем одной транзакцией записывает оценку, статусы сообщений,
новое состояние, память и итог игры. При ошибке модели ожидающая реплика
получает статус `failed`, числовое состояние не меняется. Для временных ошибок
провайдера предусмотрен один повтор; неверный структурированный ответ не
применяется. Это исключает частично применённый ход при сбое AI Opponent.
