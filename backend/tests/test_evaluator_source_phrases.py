"""Validate the supplied-source catalog without requiring the original downloads."""

import json
import re
import unittest
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATASET = json.loads((ROOT / 'content/evaluator_reference_cases.json').read_text(encoding='utf-8'))
CATALOG = DATASET['source_catalog']


class SourcePhraseTests(unittest.TestCase):
    def test_source_locations_contexts_and_deduplication(self):
        self.assertEqual(CATALOG['schema_version'], 'mvp05-source-v1')
        sources = {source['id']: source for source in CATALOG['sources']}
        self.assertEqual(set(sources), {'training', 'knowledge', 'paei_design'})
        for source in sources.values():
            self.assertRegex(source['sha256'], r'^[0-9a-f]{64}$')
        normalized = [re.sub(r'\s+', ' ', p['text']).strip() for p in CATALOG['phrases']]
        self.assertEqual(len(set(normalized)), len(normalized))
        self.assertEqual(len({p['id'] for p in CATALOG['phrases']}), len(normalized))
        count = Counter()
        for phrase in CATALOG['phrases']:
            self.assertTrue(phrase['uses'])
            for use in phrase['uses']:
                with self.subTest(phrase=phrase['id'], location=use['location']):
                    self.assertIn(use['source_id'], sources)
                    context = CATALOG['contexts'][use['context_id']]
                    self.assertEqual(context['source_id'], use['source_id'])
                    self.assertEqual(re.sub(r'\s+', ' ', use['source_text']).strip(),
                                     re.sub(r'\s+', ' ', phrase['text']).strip())
                    location = use['location']
                    if use['source_id'] == 'paei_design':
                        self.assertLessEqual(1, location['line'])
                        self.assertLessEqual(location['line'], sources['paei_design']['line_count'])
                        self.assertIn(use['profile_focus'], 'PAEI')
                        self.assertIn(use['source_text'], context['text'])
                    else:
                        self.assertIn(location['sheet'], sources[use['source_id']]['worksheets'])
                        self.assertRegex(location['cell'], r'^[A-Z]+[1-9][0-9]*$')
                    self.assertFalse(
                        {'action_type', 'state_delta', 'profile_fit'}
                        & use.get('source_expected', {}).keys()
                    )
                    count[use['kind']] += 1
        self.assertEqual(dict(count), CATALOG['summary']['uses_by_kind'])
        self.assertEqual(sum(count.values()), CATALOG['summary']['source_uses'])
        self.assertEqual(len(normalized), CATALOG['summary']['unique_phrases'])

    def test_training_options_keep_labels_and_attempt_context(self):
        choices = defaultdict(dict)
        criteria = defaultdict(set)
        final_examples = []
        for phrase in CATALOG['phrases']:
            for use in phrase['uses']:
                expected = use.get('source_expected', {})
                if use['kind'] == 'training_choice':
                    self.assertIn(expected['assessment'], {'correct', 'partial', 'incorrect'})
                    self.assertIn(expected['attempt_stage'], {'first', 'retry'})
                    self.assertTrue(expected['feedback_text'])
                    self.assertNotIn(use['choice_id'], choices[use['context_id']])
                    choices[use['context_id']][use['choice_id']] = expected
                elif use['kind'] == 'criterion_fragment':
                    criteria[expected['criterion_id']].add(expected['criterion_status'])
                elif use['kind'] == 'free_answer_example':
                    final_examples.append(use)
                    self.assertEqual(len(set(use['rubric_ids'])), 4)
        self.assertEqual(len(choices), 78)
        self.assertTrue(all(set(options) == set('abc') for options in choices.values()))
        self.assertEqual(len(criteria), 32)
        self.assertTrue(all(statuses == {'met', 'not_met'} for statuses in criteria.values()))
        self.assertEqual(len(final_examples), 8)
        for use in final_examples:
            self.assertTrue(set(use['rubric_ids']).issubset(criteria.keys()))

    def test_quiz_keys_remain_question_specific(self):
        questions = defaultdict(list)
        for phrase in CATALOG['phrases']:
            for use in phrase['uses']:
                if use['kind'] == 'quiz_option':
                    questions[use['context_id']].append(use)
        self.assertEqual(len(questions), 29)
        for options in questions.values():
            self.assertEqual({option['choice_id'] for option in options}, set('ABCD'))
            self.assertEqual(sum(option['source_expected']['is_key_answer'] for option in options), 1)


if __name__ == '__main__':
    unittest.main()
