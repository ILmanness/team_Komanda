"""Technical validation for the draft AI-04 schema, without an LLM request."""

import json

import pytest
from pydantic import ValidationError

from app.game.evaluator_contract import EvaluatorOutput

VALID = {
    'schema_version': 'ai04-v1',
    'observations': {
        'conversation_progress': 'forward',
        'features': [
            {'code': 'result_clarity', 'evidence': 'Нам нужен готовый план к пятнице.'},
        ],
    },
    'profile_fit': {'P': 2, 'A': 0, 'E': 0, 'I': 0},
    'proposed_event': {'action_type': 'positive', 'critical_flags': []},
    'explanation': {'reason': 'Названы результат и срок.'},
}


def test_valid_example_has_separate_observation_event_and_explanation():
    result = EvaluatorOutput.model_validate_json(json.dumps(VALID, ensure_ascii=False))
    assert result.observations.features[0].code == 'result_clarity'
    assert result.proposed_event.action_type == 'positive'
    assert result.explanation.reason == 'Названы результат и срок.'
    result.validate_evidence('Нам нужен готовый план к пятнице.')


@pytest.mark.parametrize(
    'change',
    [
        lambda data: data['profile_fit'].update(P=3),
        lambda data: data['proposed_event'].update(action_type='critical_error'),
        lambda data: data['proposed_event'].update(critical_flags=['PERSONAL_ATTACK']),
        lambda data: data['observations'].update(conversation_progress='sideways'),
        lambda data: data.update(schema_version='ai04-v2'),
        lambda data: data['proposed_event'].update(action_type='unknown'),
        lambda data: data.update(state_delta={'contact': 5}),
        lambda data: data.pop('explanation'),
        lambda data: data['observations']['features'][0].update(evidence=''),
    ],
)
def test_invalid_examples_are_rejected(change):
    candidate = json.loads(json.dumps(VALID, ensure_ascii=False))
    change(candidate)
    with pytest.raises(ValidationError):
        EvaluatorOutput.model_validate(candidate)


def test_evidence_must_appear_in_the_player_message():
    result = EvaluatorOutput.model_validate(VALID)
    with pytest.raises(ValueError, match='must quote'):
        result.validate_evidence('Совсем другая реплика')
