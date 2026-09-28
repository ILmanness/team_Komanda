"""Deterministic, non-revealing hints based on the validated turn result."""

from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.game.evaluator_contract import TurnEvaluation

HintType = Literal['direction', 'context', 'communication', 'mistake', 'strategy']


class Hint(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    level: int = Field(ge=1, le=3)
    hint_type: HintType
    text: str = Field(min_length=1, max_length=500)
    explanation: str = Field(min_length=1, max_length=500)


class HintGenerator:
    """Use public goal presence, the event and state; never include private interests."""

    _TEXT: ClassVar[dict[str, tuple[str, str, str]]] = {
        'communication': (
            'Обратите внимание на состояние контакта в переговорах.',
            'Проясните, что вызвало напряжение, прежде чем продвигать решение.',
            'Сначала восстановите контакт, затем уточните один критерий решения.',
        ),
        'mistake': (
            'Проверьте, не противоречит ли предыдущий шаг ограничениям ситуации.',
            'Найдите в предыдущем ходе действие, которое мешает договорённости.',
            'Назовите для себя риск предыдущего шага и выберите способ его исправить.',
        ),
        'strategy': (
            'Сверьте следующий шаг с целью переговоров.',
            'Сопоставьте доступные варианты с целью и ограничениями.',
            'Выберите один проверяемый следующий шаг, не обещая неподтверждённых условий.',
        ),
        'direction': (
            'Уточните, чего пока не хватает для продвижения разговора.',
            'Проверьте критерии решения до нового предложения.',
            'Задайте один вопрос о критерии решения и используйте ответ для следующего шага.',
        ),
        'context': (
            'Вернитесь к условиям текущей ситуации.',
            'Проверьте известные ограничения перед продолжением.',
            'Сопоставьте следующий шаг с известными фактами и обязательными ограничениями.',
        ),
    }
    _EXPLANATION: ClassVar[dict[str, str]] = {
        'communication': 'Напряжение требует внимания к контакту.',
        'mistake': 'Предыдущий ход мог ухудшить переговоры.',
        'strategy': 'Есть цель, но следующий шаг ещё нужно проверить.',
        'direction': 'Для продвижения не хватает ясного критерия.',
        'context': 'Сначала полезно свериться с известными условиями.',
    }

    def generate(
        self,
        *,
        goal: str,
        evaluation: dict[str, Any],
        state: dict[str, Any],
        level: int,
    ) -> Hint:
        result = TurnEvaluation.model_validate(evaluation)
        if not 1 <= level <= 3:
            raise ValueError('hint level must be from 1 to 3')

        action = result.proposed_event.action_type
        if state.get('tension', 0) >= 35:
            kind: HintType = 'communication'
        elif action in ('negative', 'critical_error'):
            kind = 'mistake'
        elif not result.observations.features:
            kind = 'direction'
        elif goal.strip() and state.get('progress', 0) < 80:
            kind = 'strategy'
        else:
            kind = 'context'

        return Hint(
            level=level,
            hint_type=kind,
            text=self._TEXT[kind][level - 1],
            explanation=self._EXPLANATION[kind],
        )


def hint_limit(difficulty_code: str | None) -> int:
    """Limits from scoring_and_game_state.md §12."""
    return {'easy': 5, 'normal': 3, 'hard': 2}.get(
        (difficulty_code or 'normal').casefold(), 3,
    )
