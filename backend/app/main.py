from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.db import engine
from app.users.router import router as users_router
from app.auth.router import router as auth_router
from app.catalog.router import router as catalog_router

app = FastAPI(
    title='Арена переговоров', version='0.1.0',
    description='Инфраструктурная заглушка: только healthcheck. Игровые API ещё не реализованы.',
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(catalog_router)

@app.get('/health/live')
def live():
    return {'status': '123'}


@app.get('/health/ready')
def ready():
    try:
        with engine.connect() as connection:
            connection.execute(text('SELECT 1 FROM alembic_version')).scalar_one()
            connection.execute(text('SELECT id FROM game_sessions LIMIT 0'))
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail='Database is not ready') from None
    return {'status': 'ok', 'database': 'ready', 'ai_provider': get_settings().ai_provider}
