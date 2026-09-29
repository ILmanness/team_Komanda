"""Pure state transitions for authored training content version 3."""

from copy import deepcopy
from datetime import UTC, datetime


def initial_state(scenario, mode):
    return {
        'content_version': '3.0', 'scenario_id': scenario['id'], 'mode': mode,
        'node_id': scenario['start_node_id'], 'flags': [], 'step_results': {},
        'consequences': [], 'error_count': 0, 'correction_count': 0,
        'hint_used': False, 'hint_revealed': [], 'card_seen': False,
        'history': [], 'finished': False, 'turn': 0,
    }


def apply_choice(state, scenario, option, event_id):
    """Apply only the whitelisted changes supplied by the validated catalog."""
    updated = deepcopy(state)
    node = scenario['nodes'][state['node_id']]
    changes = option.get('state_changes') or {}
    if node.get('required_flags') and node['required_flags'] not in state['flags']:
        raise ValueError('Required context is missing for this scene')
    for flag in changes.get('add_flags', []):
        if flag not in updated['flags']:
            updated['flags'].append(flag)
    updated['step_results'].update(changes.get('step_results', {}))
    updated['error_count'] += changes.get('error_count_delta', 0)
    updated['correction_count'] += changes.get('correction_count_delta', 0)
    if changes.get('append_consequence'):
        updated['consequences'].append(changes['append_consequence'])
    updated['finished'] = bool(changes.get('finished', False))
    updated['node_id'] = option['next_node']
    updated['turn'] += 1
    updated['history'].append({
        'event_id': event_id, 'sequence_no': updated['turn'],
        'node_id': node['node_id'], 'option_id': option['id'],
        'choice_text': option['text'], 'effect': option['effect'],
        'flag': option['flag'], 'feedback': option['feedback'],
        'debrief': option['debrief'], 'result_type': option['result_type'],
        'timestamp': datetime.now(UTC).isoformat(),
    })
    target = scenario['nodes'][updated['node_id']]
    if target['type'] != 'terminal':
        return updated, None
    outcome = scenario['outcomes'][target['outcome_id']]
    if outcome['status'] == 'completed' and updated['error_count'] == 0:
        application = 'Применено самостоятельно'
    elif outcome['status'] == 'completed':
        application = 'Применено после исправлений'
    else:
        application = 'Попытка завершена'
    if updated['hint_used']:
        application += ' · с подсказкой'
    result = {
        'result': outcome['status'], 'outcome_id': outcome['id'],
        'outcome_text': outcome['text'], 'application': application,
        'scenario_id': scenario['id'], 'consequences': updated['consequences'],
        'error_count': updated['error_count'],
        'correction_count': updated['correction_count'],
        'hint_used': updated['hint_used'], 'step_results': {
            node_id: updated['step_results'].get(node_id, 'not_checked')
            for node_id in scenario['step_order']
        }, 'repeat': outcome['repeat'],
    }
    updated['finished'] = True
    return updated, result
