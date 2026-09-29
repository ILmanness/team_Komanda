"""Check every authored route in the v3 method and principle catalog."""

import json
from pathlib import Path

from app.admin.import_editorial import validate_branching
from app.sessions.branching_v3 import apply_choice, initial_state


def test_all_v3_routes_are_playable():
    catalog = json.loads((Path(__file__).parents[1] / 'content' / 'branching_trainings.json').read_text(encoding='utf-8'))
    validate_branching(catalog)
    paths = 0
    for tool in catalog['tools']:
        for scenario in tool['scenarios']:
            pending = [initial_state(scenario, 'practice')]
            while pending:
                state = pending.pop()
                node = scenario['nodes'][state['node_id']]
                for option in node['options']:
                    updated, result = apply_choice(state, scenario, option, f'event-{paths}-{state["turn"]}')
                    assert updated['turn'] == state['turn'] + 1
                    assert updated['history'][-1]['option_id'] == option['id']
                    assert updated['error_count'] >= state['error_count']
                    assert updated['correction_count'] >= state['correction_count']
                    assert updated['consequences'][:len(state['consequences'])] == state['consequences']
                    if result is None:
                        assert not updated['finished']
                        pending.append(updated)
                    else:
                        paths += 1
                        assert updated['finished']
                        assert result['result'] in ('completed', 'stopped')
                        assert result['step_results'].keys() == set(scenario['step_order'])
                        if result['result'] == 'stopped':
                            assert result['application'] == 'Попытка завершена'
    assert paths > 1000
