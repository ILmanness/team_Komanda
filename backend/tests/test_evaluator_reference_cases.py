"""MVP-05 fixture checks. These draft labels are not a live model accuracy score."""

import json
import unittest
from pathlib import Path

from app.game.evaluator_contract import EvaluatorOutput

REFERENCE_PATH = Path(__file__).resolve().parents[2] / 'content' / 'evaluator_reference_cases.json'
REFERENCE = json.loads(REFERENCE_PATH.read_text(encoding='utf-8'))

# The provisional state transitions in docs/scoring_and_game_state.md §10.1.
DRAFT_STATE_DELTAS = {
    'strong_positive': (8, -8, 12, 12, 0),
    'positive': (5, -5, 8, 8, 0),
    'neutral': (0, 0, 2, 0, 0),
    'negative': (-6, 6, 0, -7, 0),
    'critical_error': (-15, 12, -5, -15, 1),
    'recovery_action': (15, -10, 5, 5, 0),
}
DELTA_FIELDS = ('contact', 'resistance', 'progress', 'quality', 'critical_errors')


def matches_reference(case: dict, evaluation: dict) -> bool:
    """Compare an AI-04-style result to required and admissible draft labels."""
    try:
        result = EvaluatorOutput.model_validate(evaluation)
        result.validate_evidence(case['input']['player_message'])
    except ValueError:
        return False

    expected = case['expected']
    required = expected['required']
    allowed = expected['allowed']
    if result.proposed_event.action_type not in allowed['action_types']:
        return False
    if sorted(result.proposed_event.critical_flags) != sorted(required['critical_flags']):
        return False
    if not set(required['observation_codes']).issubset(
        {item.code for item in result.observations.features}
    ):
        return False
    return all(
        allowed['profile_fit'][letter][0]
        <= getattr(result.profile_fit, letter)
        <= allowed['profile_fit'][letter][1]
        for letter in 'PAEI'
    )


class ReferenceCaseFixtureTests(unittest.TestCase):
    def test_set_covers_requested_behaviors_and_is_marked_unapproved(self):
        self.assertEqual(REFERENCE['review_status'], 'pending_poliy01')
        cases = REFERENCE['cases']
        self.assertEqual(len({case['id'] for case in cases}), len(cases))
        tags = {tag for case in cases for tag in case['tags']}
        self.assertTrue(
            {
                'strong', 'weak', 'clarification', 'interest_discovery',
                'argumentation', 'pressure', 'premature_proposal', 'agreement',
                'critical_error', 'boundary', 'ambiguous',
            }.issubset(tags)
        )

    def test_every_case_can_be_compared_to_the_draft_contract(self):
        for case in REFERENCE['cases']:
            with self.subTest(case=case['id']):
                self.assertTrue(case['input']['player_message'].strip())
                self.assertTrue(case['expected']['review_note'].strip())
                required = case['expected']['required']
                allowed = case['expected']['allowed']
                self.assertTrue(required['observation_codes'])
                self.assertEqual(len(set(required['observation_codes'])), len(required['observation_codes']))
                self.assertEqual(set(allowed['profile_fit']), set('PAEI'))
                self.assertEqual(
                    set(allowed['action_types']),
                    set(case['expected']['state_delta_by_action']),
                )
                state_before = case['input'].get(
                    'state_before', REFERENCE['scenario']['default_state_before']
                )
                self.assertEqual(
                    set(state_before),
                    {'contact', 'resistance', 'progress', 'critical_errors', 'game_status'},
                )
                for action in allowed['action_types']:
                    self.assertIn(action, DRAFT_STATE_DELTAS)
                    self.assertEqual(
                        action == 'critical_error', bool(required['critical_flags'])
                    )
                    delta = case['expected']['state_delta_by_action'][action]
                    self.assertEqual(tuple(delta), DELTA_FIELDS)
                    self.assertEqual(tuple(delta.values()), DRAFT_STATE_DELTAS[action])
                    for name in ('contact', 'resistance', 'progress'):
                        self.assertLessEqual(0, state_before[name] + delta[name])
                        self.assertLessEqual(state_before[name] + delta[name], 100)
                    self.assertGreaterEqual(
                        state_before['critical_errors'] + delta['critical_errors'], 0
                    )
                for lower, upper in allowed['profile_fit'].values():
                    self.assertLessEqual(-2, lower)
                    self.assertLessEqual(lower, upper)
                    self.assertLessEqual(upper, 2)

                sample = {
                    'schema_version': 'ai04-v1',
                    'observations': {
                        'conversation_progress': (
                            'forward' if allowed['action_types'][0]
                            in ('strong_positive', 'positive', 'recovery_action')
                            else 'backward' if allowed['action_types'][0] == 'negative'
                            else 'neutral'
                        ),
                        'features': [
                            {'code': code, 'evidence': case['input']['player_message']}
                            for code in required['observation_codes']
                        ],
                    },
                    'profile_fit': {
                        letter: bounds[0] for letter, bounds in allowed['profile_fit'].items()
                    },
                    'proposed_event': {
                        'action_type': allowed['action_types'][0],
                        'critical_flags': required['critical_flags'],
                    },
                    'explanation': {'reason': case['expected']['review_note']},
                }
                self.assertTrue(matches_reference(case, sample))
                sample['observations']['features'][0]['evidence'] = 'Несуществующая цитата'
                self.assertFalse(matches_reference(case, sample))
                sample['observations']['features'][0]['evidence'] = case['input']['player_message']
                sample['profile_fit']['P'] = 3
                self.assertFalse(matches_reference(case, sample))

    def test_comparison_rejects_wrong_action_and_missing_observation(self):
        case = next(case for case in REFERENCE['cases'] if case['id'] == 'critical_personal_attack')
        candidate = {
            'schema_version': 'ai04-v1',
            'observations': {
                'conversation_progress': 'backward',
                'features': [
                    {'code': 'personal_attack', 'evidence': case['input']['player_message']}
                ],
            },
            'profile_fit': {'P': -1, 'A': -1, 'E': -1, 'I': -2},
            'proposed_event': {
                'action_type': 'neutral',
                'critical_flags': ['PERSONAL_ATTACK'],
            },
            'explanation': {'reason': 'Прямое оскорбление.'},
        }
        self.assertFalse(matches_reference(case, candidate))
        candidate['proposed_event']['action_type'] = 'critical_error'
        candidate['observations']['features'] = []
        self.assertFalse(matches_reference(case, candidate))


if __name__ == '__main__':
    unittest.main()
