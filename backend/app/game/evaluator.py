import json
from typing import Any

from app.ai import complete
from app.config import get_settings


class Evaluator:


    async def evaluate(
        self,
        *,
        context: dict[str, Any],
        player_message: str,
    ) -> dict[str, Any]:
        """
        Анализирует сообщение игрока через LLM.
        """

        if get_settings().ai_provider == 'mock':
            return self._mock_evaluation(player_message)

        prompt = self._build_prompt(
            context=context,
            player_message=player_message,
        )

        response = await complete([{"role": "system", "content": prompt}])

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
progress от -12 до +12
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
            -12,
            12,
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
    def _mock_evaluation(message: str) -> dict[str, Any]:
        """Predictable local demo rules; never used with an AI provider."""
        lower = message.casefold()
        hostile = any(word in lower for word in ('дурак', 'заткни', 'идиот', 'уволю', 'угрожаю'))
        constructive = len(message.strip()) >= 20 and any(
            word in lower for word in (
                'давайте', 'предлагаю', 'можем', 'соглас', 'понима', 'обсуд', 'решени',
                'какие', 'как ', 'что ', 'почему', 'важно', 'помог',
            )
        )
        if hostile:
            return {'intent': 'refusal', 'quality': 0.1, 'critical_error': False,
                    'reason': 'Демонстрационная оценка: агрессивная реплика.',
                    'effects': {'contact': -2, 'tension': 3, 'progress': 0}}
        if constructive:
            return {'intent': 'negotiation', 'quality': 0.8, 'critical_error': False,
                    'reason': 'Демонстрационная оценка: конструктивная реплика.',
                    'effects': {'contact': 2, 'tension': -1, 'progress': 12}}
        return {'intent': 'unknown', 'quality': 0.4, 'critical_error': False,
                'reason': 'Демонстрационная оценка: требуется более конкретный ответ.',
                'effects': {'contact': 0, 'tension': 0, 'progress': 2}}

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
