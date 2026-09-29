"""Build a playable deterministic training from the admin's step editor."""

from app.admin.schemas import MissionWrite


def build_guided(data: MissionWrite) -> dict:
    authoring = data.guided
    assert authoring is not None
    material_id = str(data.knowledge_item_id)
    nodes: dict[str, dict] = {}
    assessments: dict[str, dict] = {}
    training_id = f'ADMIN_{data.title[:24]}'
    for index, step in enumerate(authoring.steps, 1):
        node_id = f'STEP_{index}'
        retry_id = f'{node_id}_RETRY'
        next_id = f'STEP_{index + 1}' if index < len(authoring.steps) else 'TRANSFER'
        for retry in (False, True):
            current_id = retry_id if retry else node_id
            node = {
                'node_id': current_id, 'base_node_id': node_id,
                'node_type': 'retry' if retry else 'decision',
                'speaker': 'Старшая коллега' if retry else step.speaker,
                'text': f'{step.hint}\n\n{step.text}' if retry else step.text,
                'node_goal': step.hint if retry else step.goal,
                'material_id': material_id, 'max_visits': 1,
            }
            for letter, option in zip('abc', step.options):
                target = next_id if retry or option.assessment == 'correct' else retry_id
                node[f'option_{letter}'] = option.text
                node[f'effect_{letter}'] = option.effect or None
                node[f'next_{letter}'] = target
                assessments[f'{current_id}:{letter}'] = {
                    'node_id': current_id, 'choice_id': letter, 'next_node_id': target,
                    'assessment': option.assessment, 'feedback_flag': f'{current_id}_{letter}',
                    'feedback_text': option.feedback, 'pattern_category': 'practice',
                    'evidence_type': 'choice', 'attempt_stage': 'retry' if retry else 'first',
                    'resolution': 'continue' if target == next_id else 'retry',
                    'transition_notice': None if target == next_id else
                        'Попробуй ещё раз. Если не знаешь, спроси — я расскажу.',
                }
            nodes[current_id] = node
    nodes['TRANSFER'] = {
        'node_id': 'TRANSFER', 'base_node_id': 'TRANSFER', 'node_type': 'free_text',
        'speaker': 'Старшая коллега', 'text': authoring.final_situation,
        'node_goal': authoring.final_goal, 'material_id': material_id,
    }
    return {
        'version': '2.0', 'source': 'admin', 'authoring': authoring.model_dump(),
        'training_id': training_id, 'principle': data.title,
        'start_node_id': 'STEP_1', 'transfer_node_id': 'TRANSFER',
        'material_id': material_id, 'shuffle_options': True,
        'example_answer': authoring.example_answer,
        'criteria': [{'criterion_id': f'criterion_{index}', 'criterion': criterion}
                     for index, criterion in enumerate(authoring.criteria, 1)],
        'nodes': nodes, 'assessments': assessments,
    }
