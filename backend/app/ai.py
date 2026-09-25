"""Provider-independent interface for text and structured LLM responses."""

import asyncio
import json
from collections.abc import AsyncIterator, Sequence
from typing import Any, Protocol, TypeVar, runtime_checkable

import httpx
from pydantic import BaseModel, ValidationError

from app.config import get_settings

Message = dict[str, str]
StructuredResponse = TypeVar('StructuredResponse', bound=BaseModel)


class LLMProviderError(Exception):
    """Base class for failures callers may handle without knowing the provider."""


class LLMAuthenticationError(LLMProviderError):
    """The provider rejected the configured credentials."""


class LLMRateLimitError(LLMProviderError):
    """The provider rejected a request because of a rate or quota limit."""


class LLMTimeoutError(LLMProviderError):
    """The provider did not answer before the configured timeout."""


class LLMTransportError(LLMProviderError):
    """The provider could not be reached."""


class LLMHTTPError(LLMProviderError):
    """The provider returned an HTTP error other than auth or rate limiting."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f'LLM provider returned HTTP {status_code}')


class LLMResponseError(LLMProviderError):
    """The provider returned an empty, malformed or schema-invalid response."""


@runtime_checkable
class LLMProvider(Protocol):
    """Contract used by application code, independent of a model vendor."""

    async def generate(self, messages: Sequence[Message]) -> str:
        """Return a non-empty text answer."""

    async def generate_structured(
        self,
        messages: Sequence[Message],
        response_model: type[StructuredResponse],
    ) -> StructuredResponse:
        """Return an answer validated against a Pydantic model."""

    def stream(self, messages: Sequence[Message]) -> AsyncIterator[str]:
        """Yield text chunks from a streamed answer."""


class MockLLMProvider:
    """Deterministic substitute for local development and tests."""

    def __init__(
        self,
        *,
        text_response: str = '[MOCK] Давайте уточним интересы обеих сторон.',
        structured_response: BaseModel | dict[str, Any] | str | None = None,
    ) -> None:
        self.text_response = text_response
        self.structured_response = structured_response

    async def generate(self, messages: Sequence[Message]) -> str:
        if not self.text_response.strip():
            raise LLMResponseError('Mock LLM response is empty')
        return self.text_response

    async def stream(self, messages: Sequence[Message]) -> AsyncIterator[str]:
        yield await self.generate(messages)

    async def generate_structured(
        self,
        messages: Sequence[Message],
        response_model: type[StructuredResponse],
    ) -> StructuredResponse:
        if self.structured_response is None:
            raise LLMResponseError('Mock LLM structured response is not configured')
        try:
            if isinstance(self.structured_response, str):
                return response_model.model_validate_json(self.structured_response)
            if isinstance(self.structured_response, BaseModel):
                return response_model.model_validate(self.structured_response.model_dump())
            return response_model.model_validate(self.structured_response)
        except ValidationError as exc:
            raise LLMResponseError('Mock LLM response does not match the schema') from exc


class CompatibleLLMProvider:
    """Client for an OpenAI-compatible chat/completions endpoint."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float = 30,
    ) -> None:
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    async def generate(self, messages: Sequence[Message]) -> str:
        return await self._request(messages)

    async def stream(self, messages: Sequence[Message]) -> AsyncIterator[str]:
        """Read OpenAI-compatible SSE chunks without exposing raw provider data."""
        completed = False
        saw_text = False
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client, client.stream(
                'POST',
                self.base_url + '/chat/completions',
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Accept': 'text/event-stream',
                },
                json={'model': self.model, 'messages': list(messages), 'stream': True},
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith('data:'):
                        continue
                    data = line[5:].strip()
                    if data == '[DONE]':
                        completed = True
                        break
                    try:
                        chunk = json.loads(data)
                        choices = chunk['choices']
                        if not isinstance(choices, list):
                            raise TypeError
                        if not choices:
                            continue
                        content = choices[0]['delta'].get('content')
                        if content is None:
                            continue
                        if not isinstance(content, str):
                            raise TypeError
                    except (ValueError, KeyError, IndexError, TypeError) as exc:
                        raise LLMResponseError('LLM provider returned a malformed stream') from exc
                    if content:
                        saw_text = True
                        yield content
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError('LLM provider timed out') from exc
        except httpx.HTTPStatusError as exc:
            raise self._status_error(exc.response.status_code) from exc
        except httpx.RequestError as exc:
            raise LLMTransportError('LLM provider could not be reached') from exc

        if not completed or not saw_text:
            raise LLMResponseError('LLM provider returned an incomplete stream')

    async def generate_structured(
        self,
        messages: Sequence[Message],
        response_model: type[StructuredResponse],
    ) -> StructuredResponse:
        content = await self._request(
            messages,
            response_format={
                'type': 'json_schema',
                'json_schema': {
                    'name': response_model.__name__,
                    'strict': True,
                    'schema': response_model.model_json_schema(),
                },
            },
        )
        try:
            return response_model.model_validate_json(content)
        except ValidationError as exc:
            raise LLMResponseError('LLM response does not match the schema') from exc

    async def _request(
        self,
        messages: Sequence[Message],
        *,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        payload: dict[str, Any] = {'model': self.model, 'messages': list(messages)}
        if response_format is not None:
            payload['response_format'] = response_format

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    self.base_url + '/chat/completions',
                    headers={'Authorization': f'Bearer {self.api_key}'},
                    json=payload,
                )
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError('LLM provider timed out') from exc
        except httpx.HTTPStatusError as exc:
            raise self._status_error(exc.response.status_code) from exc
        except httpx.RequestError as exc:
            raise LLMTransportError('LLM provider could not be reached') from exc

        try:
            content = response.json()['choices'][0]['message']['content']
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMResponseError('LLM provider returned a malformed response') from exc
        if not isinstance(content, str) or not content.strip():
            raise LLMResponseError('LLM provider returned no text')
        return content

    @staticmethod
    def _status_error(status_code: int) -> LLMProviderError:
        if status_code in (401, 403):
            return LLMAuthenticationError('LLM provider rejected credentials')
        if status_code == 429:
            return LLMRateLimitError('LLM provider rate or quota limit reached')
        return LLMHTTPError(status_code)


def get_provider() -> LLMProvider:
    """Choose an implementation from configuration without changing callers."""
    settings = get_settings()
    if settings.ai_provider == 'mock':
        return MockLLMProvider()
    return CompatibleLLMProvider(
        base_url=settings.ai_base_url,
        api_key=settings.ai_api_key,
        model=settings.ai_model,
        timeout_seconds=settings.ai_timeout_seconds,
    )


async def complete(messages: Sequence[Message]) -> str:
    """Keep the existing game integration working while it adopts LLMProvider."""
    return await get_provider().generate(messages)


async def complete_structured[ResponseModel: BaseModel](
    messages: Sequence[Message],
    response_model: type[ResponseModel],
) -> ResponseModel:
    return await get_provider().generate_structured(messages, response_model)


if __name__ == '__main__':
    print(asyncio.run(complete([{'role': 'user', 'content': 'Скажи привет'}])))
