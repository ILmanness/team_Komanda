import json
from typing import Any

from app.ai import LLMProvider, get_provider


class Evaluator:
    def __init__(self, provider: LLMProvider | None = None) -> None:
        self.provider = provider if provider is not None else get_provider()

    async def evaluate(
        self,
        *,
        context: dict[str, Any],
        player_message: str,
    ) -> dict[str, Any]:
        """
        Анализирует сообщение игрока через LLM.
        """

        prompt = self._build_prompt(
            context=context,
            player_message=player_message,
        )

        response = await self.provider.generate([{"role": "system", "content": prompt}])

        return self._parse_response(response)

    def _build_prompt(
        self,
        *,
        context: dict[str, Any],
        player_message: str,
    ) -> str:
        """
        Формирует prompt для Evaluator.
        """

        mission = context.get("mission", {})
        character = context.get("character", {})
        state = context.get("state", {})
        difficulty = context.get("difficulty_profile", {})
        custom_context = context.get("custom_context", {})

        return f"""
Ты являешься Evaluator в переговорной игре.

Твоя задача — проанализировать сообщение игрока
и определить его игровой эффект.

ВАЖНО:
- Не придумывай события, которых нет в сообщении.
- Не изменяй состояние игры напрямую.
- Верни ТОЛЬКО JSON.
- Числовые изменения должны быть умеренными.
- critical_error = true только при действительно серьёзной ошибке.

Текущая миссия:
{json.dumps(mission, ensure_ascii=False, default=str)}

Пользовательская ситуация (если задана):
{json.dumps(custom_context, ensure_ascii=False, default=str)}

Персонаж оппонента:
{json.dumps(character, ensure_ascii=False, default=str)}

Текущая сложность:
{json.dumps(difficulty, ensure_ascii=False, default=str)}

Текущее состояние:
{json.dumps(state, ensure_ascii=False, default=str)}

Сообщение игрока:
{player_message}

Верни JSON строго следующего формата:

{{
    "intent": "string",
    "quality": 0.0,
    "critical_error": false,
    "reason": "string",
    "effects": {{
        "contact": 0,
        "tension": 0,
        "progress": 0
    }}
}}

Где:

intent:
- greeting
- question
- proposal
- negotiation
- argument
- clarification
- agreement
- refusal
- unknown

quality:
число от 0.0 до 1.0.

critical_error:
true или false.

reason:
краткое объяснение оценки.

effects:
предполагаемые изменения:
contact от -3 до +3
tension от -3 до +3
progress от -3 до +3
"""

    def _parse_response(self, response: Any) -> dict[str, Any]:
        """
        Преобразует ответ LLM в безопасный словарь.

        Если LLM вернул некорректный JSON,
        используется безопасное значение по умолчанию.
        """

        if isinstance(response, dict):
            data = response
        else:
            try:
                data = json.loads(str(response))
            except (json.JSONDecodeError, TypeError, ValueError):
                return self._fallback_evaluation(
                    reason="Evaluator returned invalid JSON"
                )

        return self._normalize(data)

    def _normalize(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Нормализует и ограничивает значения Evaluator.
        """

        intent = data.get("intent", "unknown")

        allowed_intents = {
            "greeting",
            "question",
            "proposal",
            "negotiation",
            "argument",
            "clarification",
            "agreement",
            "refusal",
            "unknown",
        }

        if intent not in allowed_intents:
            intent = "unknown"

        try:
            quality = float(data.get("quality", 0.5))
        except (TypeError, ValueError):
            quality = 0.5

        quality = max(0.0, min(1.0, quality))

        effects = data.get("effects") or {}

        contact = self._clamp_int(
            effects.get("contact", 0),
            -3,
            3,
        )

        tension = self._clamp_int(
            effects.get("tension", 0),
            -3,
            3,
        )

        progress = self._clamp_int(
            effects.get("progress", 0),
            -3,
            3,
        )

        return {
            "intent": intent,
            "quality": quality,
            "critical_error": bool(
                data.get("critical_error", False)
            ),
            "reason": str(
                data.get("reason", "")
            ),
            "effects": {
                "contact": contact,
                "tension": tension,
                "progress": progress,
            },
        }

    @staticmethod
    def _clamp_int(
        value: Any,
        minimum: int,
        maximum: int,
    ) -> int:
        try:
            value = int(value)
        except (TypeError, ValueError):
            value = 0

        return max(minimum, min(maximum, value))

    @staticmethod
    def _fallback_evaluation(
        *,
        reason: str,
    ) -> dict[str, Any]:
        """
        Безопасный результат при ошибке Evaluator.
        """

        return {
            "intent": "unknown",
            "quality": 0.0,
            "critical_error": False,
            "reason": reason,
            "effects": {
                "contact": 0,
                "tension": 0,
                "progress": 0,
            },
        }
