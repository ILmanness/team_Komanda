"""Opt-in live Cloud.ru smoke test; never runs during ordinary pytest."""

import asyncio
import os
import re
from time import perf_counter
from typing import Literal

import pytest
from pydantic import BaseModel, ConfigDict

from app.ai import get_provider
from app.config import get_settings

pytestmark = pytest.mark.skipif(
    os.getenv('RUN_LLM_SMOKE') != '1',
    reason='Set RUN_LLM_SMOKE=1 to make two real, billable LLM requests',
)


class TurnProbe(BaseModel):
    model_config = ConfigDict(extra='forbid')

    action: Literal['question', 'proposal', 'other']
    has_question: bool


def test_russian_text_and_structured_output():
    settings = get_settings()
    assert settings.ai_provider == 'compatible', 'Live smoke requires AI_PROVIDER=compatible'
    assert settings.ai_api_key, 'Live smoke requires AI_API_KEY'
    provider = get_provider()

    started = perf_counter()
    reply = asyncio.run(provider.generate([
        {'role': 'system', 'content': 'Ответь только по-русски одним коротким предложением.'},
        {'role': 'user', 'content': 'Зачем в переговорах выяснять интересы собеседника?'},
    ]))
    text_ms = round((perf_counter() - started) * 1000)
    assert re.search(r'[А-Яа-яЁё]', reply), 'Expected a Russian text reply'

    started = perf_counter()
    result = asyncio.run(provider.generate_structured([
        {'role': 'system', 'content': 'Определи форму реплики. Верни только JSON по заданной схеме.'},
        {'role': 'user', 'content': 'Какой срок поставки вам подходит?'},
    ], TurnProbe))
    structured_ms = round((perf_counter() - started) * 1000)
    assert result.action == 'question', 'Expected the question action'
    assert result.has_question is True, 'Expected the question flag'

    print(f'LLM smoke latency: text_ms={text_ms} structured_ms={structured_ms}')
