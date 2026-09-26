"""Opt-in, one-request check of streaming for the configured Cloud.ru model."""

import asyncio
import os
import re
from time import perf_counter

import pytest

from app.ai import get_provider
from app.config import get_settings

pytestmark = pytest.mark.skipif(
    os.getenv('RUN_LLM_STREAM_SMOKE') != '1',
    reason='Set RUN_LLM_STREAM_SMOKE=1 for one real, billable streaming request',
)


async def receive_chunks() -> list[str]:
    return [
        chunk async for chunk in get_provider().stream([
            {'role': 'system', 'content': 'Ответь только по-русски, одним коротким предложением.'},
            {'role': 'user', 'content': 'Поздоровайся.'},
        ])
    ]


def test_live_russian_stream():
    settings = get_settings()
    assert settings.ai_provider == 'compatible', 'Live smoke requires AI_PROVIDER=compatible'
    assert settings.ai_api_key, 'Live smoke requires AI_API_KEY'

    started = perf_counter()
    chunks = asyncio.run(receive_chunks())
    elapsed_ms = round((perf_counter() - started) * 1000)
    assert chunks, 'Expected at least one streamed text chunk'
    assert re.search(r'[А-Яа-яЁё]', ''.join(chunks)), 'Expected Russian streamed text'
    print(f'LLM stream smoke: chunks={len(chunks)} elapsed_ms={elapsed_ms}')
