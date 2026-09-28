"""AI-12 hints use validated events, stay generic and obey documented limits."""

import asyncio

import pytest

from app.ai import MockLLMProvider
from app.game.evaluator import Evaluator
from app.game.hints import HintGenerator, hint_limit


def evaluate(message: str) -> dict:
    return asyncio.run(Evaluator(MockLLMProvider(demo_evaluation=True)).evaluate(
        context={}, player_message=message,
    ))


@pytest.mark.parametrize('level', [1, 2, 3])
def test_hint_never_repeats_goal_or_hidden_interest(level):
    secret = 'необъявленная уступка по бюджету'
    hint = HintGenerator().generate(
        goal=f'Согласовать план, не раскрывая: {secret}',
        evaluation=evaluate('Давайте обсудим, как можем найти решение.'),
        state={'tension': 10, 'progress': 30},
        level=level,
    )
    assert hint.level == level
    assert secret not in hint.text + hint.explanation
    assert hint.hint_type == 'strategy'
    assert len(hint.text) < 500


def test_critical_error_gets_mistake_hint_without_repeating_attack():
    message = 'Ты идиот, замолчи.'
    hint = HintGenerator().generate(
        goal='',
        evaluation=evaluate(message),
        state={'tension': 10, 'progress': 0},
        level=1,
    )
    assert hint.hint_type == 'mistake'
    assert message not in hint.text
    assert 'идиот' not in hint.text


def test_high_tension_prioritizes_contact():
    hint = HintGenerator().generate(
        goal='Достичь согласия',
        evaluation=evaluate('Давайте обсудим, как можем найти решение.'),
        state={'tension': 60, 'progress': 30},
        level=2,
    )
    assert hint.hint_type == 'communication'


def test_documented_difficulty_limits_and_invalid_level():
    assert hint_limit('Easy') == 5
    assert hint_limit('Normal') == 3
    assert hint_limit('Hard') == 2
    with pytest.raises(ValueError):
        HintGenerator().generate(
            goal='', evaluation=evaluate('ок'), state={}, level=4,
        )
