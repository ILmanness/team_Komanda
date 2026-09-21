№№1. Общая архитектура проекта

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
