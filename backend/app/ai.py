"""Provider adapter only. Game evaluator/engine are separate future work."""
import asyncio

import httpx

from app.config import get_settings


async def complete(messages: list[dict[str, str]]) -> str:
    settings = get_settings()
    if settings.ai_provider == 'mock':
        return '[MOCK] Давайте уточним интересы обеих сторон.'
    async with httpx.AsyncClient(timeout=settings.ai_timeout_seconds) as client:
        response = await client.post(
            settings.ai_base_url.rstrip('/') + '/chat/completions',
            headers={'Authorization': f'Bearer {settings.ai_api_key}'},
            json={'model': settings.ai_model, 'messages': messages},
        )
        response.raise_for_status()
        content = response.json()['choices'][0]['message']['content']
        if not isinstance(content, str) or not content.strip():
            raise ValueError('Provider returned no text')
        return content


if __name__ == '__main__':
    print(asyncio.run(complete([{'role': 'user', 'content': 'Скажи привет'}])))
