import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import ai
from app.config import Settings
from app.game.evaluator import Evaluator
from app.game.game_engine import GameEngine
from app.main import app


def test_liveness():
    assert TestClient(app).get('/health/live').json() == {'status': 'ok'}


def test_retention_validation():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, history_retention_days=10, session_retention_days=2)


def test_ai_configuration_requires_credentials():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ai_provider='compatible', ai_api_key='', ai_model='')


def test_database_password_is_not_url_interpolated():
    settings = Settings(_env_file=None, postgres_password='a@b:/%c')
    assert settings.database_url.password == 'a@b:/%c'


def test_mock_ai(monkeypatch):
    monkeypatch.setattr(ai, 'get_settings', lambda: Settings(_env_file=None, ai_provider='mock'))
    assert '[MOCK]' in asyncio.run(ai.complete([{'role': 'user', 'content': 'hello'}]))


def test_mock_story_can_succeed_but_short_answers_do_not(monkeypatch):
    monkeypatch.setattr(ai, 'get_settings', lambda: Settings(_env_file=None, ai_provider='mock'))
    evaluator = Evaluator()
    engine = GameEngine()
    state = {'turn': 0, 'contact': 0, 'tension': 0, 'progress': 0, 'critical_errors': 0}
    for _ in range(9):
        score = asyncio.run(evaluator.evaluate(
            context={}, player_message='Давайте обсудим, как мы можем найти решение.',
        ))
        state = engine.apply_evaluation(state=state, evaluation=score)
    assert engine.check_end_conditions(state=state)['reason'] == 'success'
    assert engine.build_final_result(state=state, reason='success')['result'] == 'success'
    assert asyncio.run(evaluator.evaluate(context={}, player_message='ок'))['effects']['progress'] == 2


def test_compatible_ai(monkeypatch):
    settings = Settings(_env_file=None, ai_provider='compatible', ai_api_key='test', ai_model='test-model')
    monkeypatch.setattr(ai, 'get_settings', lambda: settings)
    real_client = httpx.AsyncClient

    def handler(request):
        assert request.headers['Authorization'] == 'Bearer test'
        assert request.url.path == '/v1/chat/completions'
        return httpx.Response(200, json={'choices': [{'message': {'content': 'Ответ'}}]})

    monkeypatch.setattr(ai.httpx, 'AsyncClient', lambda **kwargs: real_client(
        transport=httpx.MockTransport(handler), **kwargs))
    assert asyncio.run(ai.complete([{'role': 'user', 'content': 'hello'}])) == 'Ответ'
