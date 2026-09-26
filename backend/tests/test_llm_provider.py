import asyncio
import json
from typing import Literal

import httpx
import pytest
from pydantic import BaseModel, ConfigDict

from app import ai
from app.config import Settings
from app.game.service import GameService

MESSAGES = [{'role': 'user', 'content': 'Какой срок вам подходит?'}]
REAL_ASYNC_CLIENT = httpx.AsyncClient


class TurnLabel(BaseModel):
    model_config = ConfigDict(extra='forbid')

    action: Literal['question', 'proposal']
    has_question: bool


def mock_http(monkeypatch, handler):
    monkeypatch.setattr(
        ai.httpx,
        'AsyncClient',
        lambda **kwargs: REAL_ASYNC_CLIENT(transport=httpx.MockTransport(handler), **kwargs),
    )


def compatible_provider():
    return ai.CompatibleLLMProvider(
        base_url='https://provider.example/v1/',
        api_key='private-test-key',
        model='test-model',
    )


async def collect_stream(provider, messages=MESSAGES):
    return [chunk async for chunk in provider.stream(messages)]


def test_mock_implements_contract_and_validates_structured_response():
    provider: ai.LLMProvider = ai.MockLLMProvider(
        text_response='Здравствуйте',
        structured_response={'action': 'question', 'has_question': True},
    )
    assert isinstance(provider, ai.LLMProvider)
    assert asyncio.run(provider.generate(MESSAGES)) == 'Здравствуйте'
    assert asyncio.run(collect_stream(provider)) == ['Здравствуйте']
    assert asyncio.run(provider.generate_structured(MESSAGES, TurnLabel)) == TurnLabel(
        action='question', has_question=True
    )


def test_mock_reports_missing_or_invalid_structured_fixture():
    with pytest.raises(ai.LLMResponseError, match='not configured'):
        asyncio.run(ai.MockLLMProvider().generate_structured(MESSAGES, TurnLabel))
    with pytest.raises(ai.LLMResponseError, match='schema'):
        asyncio.run(
            ai.MockLLMProvider(structured_response={'action': 'unknown'}).generate_structured(
                MESSAGES, TurnLabel
            )
        )


def test_compatible_provider_sends_json_schema_and_validates_answer(monkeypatch):
    def handler(request):
        assert request.url.path == '/v1/chat/completions'
        assert request.headers['Authorization'] == 'Bearer private-test-key'
        body = json.loads(request.content)
        assert body['model'] == 'test-model'
        assert body['messages'] == MESSAGES
        format_spec = body['response_format']
        assert format_spec['type'] == 'json_schema'
        assert format_spec['json_schema']['strict'] is True
        assert format_spec['json_schema']['schema']['required'] == ['action', 'has_question']
        return httpx.Response(
            200,
            json={'choices': [{'message': {'content': '{"action":"question","has_question":true}'}}]},
        )

    mock_http(monkeypatch, handler)
    assert asyncio.run(compatible_provider().generate_structured(MESSAGES, TurnLabel)) == TurnLabel(
        action='question', has_question=True
    )


def test_compatible_provider_rejects_invalid_structured_answer(monkeypatch):
    mock_http(
        monkeypatch,
        lambda request: httpx.Response(
            200,
            json={'choices': [{'message': {'content': '{"action":"unknown","has_question":true}'}}]},
        ),
    )
    with pytest.raises(ai.LLMResponseError, match='schema'):
        asyncio.run(compatible_provider().generate_structured(MESSAGES, TurnLabel))


def test_compatible_provider_streams_text_chunks(monkeypatch):
    def handler(request):
        assert request.headers['Accept'] == 'text/event-stream'
        body = json.loads(request.content)
        assert body == {'model': 'test-model', 'messages': MESSAGES, 'stream': True}
        return httpx.Response(
            200,
            text=(
                ': keep-alive\n\n'
                'data: {"choices":[{"delta":{"content":"Привет"}}]}\n\n'
                'data: {"choices":[{"delta":{"content":", мир"}}]}\n\n'
                'data: {"choices":[],"usage":{"total_tokens":5}}\n\n'
                'data: [DONE]\n\n'
            ),
            headers={'content-type': 'text/event-stream'},
        )

    mock_http(monkeypatch, handler)
    assert asyncio.run(collect_stream(compatible_provider())) == ['Привет', ', мир']


@pytest.mark.parametrize(
    ('body', 'message'),
    [
        ('data: {broken}\n\ndata: [DONE]\n\n', 'malformed'),
        ('data: {"choices":[{"delta":{"content":"часть"}}]}\n\n', 'incomplete'),
    ],
)
def test_compatible_provider_rejects_broken_stream(monkeypatch, body, message):
    mock_http(monkeypatch, lambda request: httpx.Response(200, text=body))
    with pytest.raises(ai.LLMResponseError, match=message):
        asyncio.run(collect_stream(compatible_provider()))


def test_stream_maps_http_errors_without_exposing_key(monkeypatch):
    mock_http(monkeypatch, lambda request: httpx.Response(429))
    with pytest.raises(ai.LLMRateLimitError) as failure:
        asyncio.run(collect_stream(compatible_provider()))
    assert 'private-test-key' not in str(failure.value)


@pytest.mark.parametrize(
    ('status', 'error_type'),
    [
        (401, ai.LLMAuthenticationError),
        (403, ai.LLMAuthenticationError),
        (429, ai.LLMRateLimitError),
        (503, ai.LLMHTTPError),
    ],
)
def test_http_errors_are_typed_and_do_not_expose_key(monkeypatch, status, error_type):
    mock_http(monkeypatch, lambda request: httpx.Response(status))
    with pytest.raises(error_type) as failure:
        asyncio.run(compatible_provider().generate(MESSAGES))
    assert 'private-test-key' not in str(failure.value)
    if status == 503:
        assert failure.value.status_code == 503


def test_timeout_and_transport_errors_are_distinct(monkeypatch):
    def timeout(request):
        raise httpx.ReadTimeout('late', request=request)

    mock_http(monkeypatch, timeout)
    with pytest.raises(ai.LLMTimeoutError):
        asyncio.run(compatible_provider().generate(MESSAGES))

    def unreachable(request):
        raise httpx.ConnectError('unreachable', request=request)

    mock_http(monkeypatch, unreachable)
    with pytest.raises(ai.LLMTransportError):
        asyncio.run(compatible_provider().generate(MESSAGES))


def test_malformed_provider_payload_is_typed(monkeypatch):
    mock_http(monkeypatch, lambda request: httpx.Response(200, json={'choices': []}))
    with pytest.raises(ai.LLMResponseError, match='malformed'):
        asyncio.run(compatible_provider().generate(MESSAGES))


def test_existing_complete_call_switches_to_mock_without_use_case_change(monkeypatch):
    monkeypatch.setattr(ai, 'get_settings', lambda: Settings(_env_file=None, ai_provider='mock'))
    assert isinstance(ai.get_provider(), ai.MockLLMProvider)
    assert '[MOCK]' in asyncio.run(ai.complete(MESSAGES))


def test_game_use_case_accepts_mock_provider_without_external_request():
    provider = ai.MockLLMProvider(
        text_response=json.dumps({
            'intent': 'question',
            'quality': 0.75,
            'critical_error': False,
            'reason': 'Уточнение интересов',
            'effects': {'contact': 1, 'tension': 0, 'progress': 1},
        }),
    )
    service = GameService(provider=provider)
    assert service.evaluator.provider is provider
    result = asyncio.run(service._evaluate(context={}, player_message='Что для вас важно?'))
    assert result['intent'] == 'question'
    assert result['effects']['contact'] == 1
