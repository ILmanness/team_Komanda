"""Validate and import the real knowledge base and guided trainings.

Run inside the backend container: python -m app.admin.import_editorial --apply
The default command validates and prints a dry-run summary.
"""

import argparse
import json
from collections import Counter
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from psycopg.types.json import Jsonb
from sqlalchemy import create_engine, text

from app.config import get_settings

# The editorial importer is a standalone CLI, so it uses a synchronous connection.
engine = create_engine(get_settings().database_url, pool_pre_ping=True)

CONTENT = Path(__file__).resolve().parents[2] / 'content'


def stable_id(key):
    return uuid5(NAMESPACE_URL, f'negotiation-arena-editorial:{key}')


def load_data():
    knowledge = json.loads((CONTENT / 'knowledge.json').read_text(encoding='utf-8'))
    trainings = json.loads((CONTENT / 'trainings.json').read_text(encoding='utf-8'))
    if knowledge['schema_version'] != 1 or trainings['schema_version'] != '2.0':
        raise ValueError('Unknown editorial content version')
    if len(knowledge['items']) != 37 or len(trainings['definitions']) != 8:
        raise ValueError('Incomplete editorial content')
    validate_trainings(trainings)
    return knowledge, trainings


def validate_trainings(data):
    flags = {row['feedback_flag'] for row in data['feedback_flags']}
    if len(flags) != len(data['feedback_flags']):
        raise ValueError('Duplicate feedback flag')
    for training in data['definitions']:
        training_id = training['training_id']
        nodes = {node['node_id']: node for node in training['nodes']}
        if len(nodes) != len(training['nodes']):
            raise ValueError(f'{training_id}: duplicate node ID')
        if training['mode'] != 'guided_choice_then_free_text':
            raise ValueError(f'{training_id}: unsupported mode')
        if training['start_node_id'] not in nodes or training['transfer_node_id'] not in nodes:
            raise ValueError(f'{training_id}: missing start or transfer node')
        finals = [node for node in nodes.values() if node['node_type'] == 'free_text']
        if len(finals) != 1 or finals[0]['node_id'] != training['transfer_node_id'] or finals[0]['is_final'] is not True:
            raise ValueError(f'{training_id}: expected one free-text final')
        criteria = training['criteria']
        if len(criteria) != 4 or len({row['criterion_id'] for row in criteria}) != 4:
            raise ValueError(f'{training_id}: expected four unique criteria')
        assessments = {(row['node_id'], row['choice_id']): row for row in training['assessments']}
        if len(assessments) != len(training['assessments']) or len(assessments) != 3 * (len(nodes) - 1):
            raise ValueError(f'{training_id}: incomplete or duplicate assessment matrix')
        edges = {}
        for node in nodes.values():
            node_id = node['node_id']
            if node['max_visits'] != 1:
                raise ValueError(f'{training_id}/{node_id}: max_visits must be one')
            if node['node_type'] == 'free_text':
                if any(node[f'option_{letter}'] or node[f'next_{letter}'] for letter in 'abc'):
                    raise ValueError(f'{training_id}/{node_id}: final has choices')
                continue
            edges[node_id] = []
            for letter in 'abc':
                assessment = assessments.get((node_id, letter))
                target = node[f'next_{letter}']
                if not node[f'option_{letter}'] or not assessment or not target:
                    raise ValueError(f'{training_id}/{node_id}: missing choice/assessment/target')
                if assessment['next_node_id'] != target or target not in nodes:
                    raise ValueError(f'{training_id}/{node_id}: invalid transition')
                if node[f'flag_{letter}'] not in flags:
                    raise ValueError(f'{training_id}/{node_id}: unknown feedback flag')
                if assessment['assessment'] not in ('correct', 'partial', 'incorrect'):
                    raise ValueError(f'{training_id}/{node_id}: invalid assessment')
                if assessment['attempt_stage'] not in ('first', 'retry'):
                    raise ValueError(f'{training_id}/{node_id}: invalid attempt stage')
                edges[node_id].append(target)
        visited, visiting = set(), set()

        def walk(node_id):
            if node_id in visiting:
                raise ValueError(f'{training_id}: graph cycle at {node_id}')
            if node_id in visited:
                return
            visiting.add(node_id)
            for target in edges.get(node_id, []):
                walk(target)
            visiting.remove(node_id)
            visited.add(node_id)

        walk(training['start_node_id'])
        if set(nodes) != visited:
            raise ValueError(f'{training_id}: unreachable nodes: {set(nodes) - visited}')


def apply(knowledge, trainings):
    counts = Counter()
    with engine.begin() as connection:
        for item in knowledge['items']:
            item_id = stable_id(f"knowledge:{item['slug']}")
            parent_id = stable_id(f"knowledge:{item['parent_slug']}") if item['parent_slug'] else None
            connection.execute(text("""
                INSERT INTO knowledge_items
                    (id, parent_id, item_type, slug, title, summary, body, metadata, status, sort_order)
                VALUES (:id, :parent_id, :item_type, :slug, :title, :summary, :body,
                        :metadata, 'published', :sort_order)
                ON CONFLICT (slug) DO UPDATE SET
                    parent_id=EXCLUDED.parent_id, item_type=EXCLUDED.item_type,
                    title=EXCLUDED.title, summary=EXCLUDED.summary, body=EXCLUDED.body,
                    metadata=EXCLUDED.metadata, sort_order=EXCLUDED.sort_order,
                    updated_at=now()
            """), {
                'id': item_id, 'parent_id': parent_id, 'item_type': item['type'],
                'slug': item['slug'], 'title': item['title'], 'summary': item['summary'],
                'body': item['body'], 'metadata': Jsonb({'source': 'editorial-workbook',
                    'number': item['number'], 'kind': item['kind'],
                    'answer_key': item.get('answer_key'), 'sections': item.get('sections', []),
                    'quiz': item.get('quiz')}), 'sort_order': item['sort_order'],
            })
            counts[item['kind']] += 1

        mentor_id = stable_id('character:training-mentor')
        connection.execute(text("""
            INSERT INTO characters (id, slug, name, role_title, description, base_prompt)
            VALUES (:id, 'training-mentor', 'Наставник', 'Ведущий тренировки',
                    'Помогает разобрать решение и перейти к следующей ситуации.', '')
            ON CONFLICT (slug) DO NOTHING
        """), {'id': mentor_id})

        for item in trainings['definitions']:
            training_id = item['training_id']
            material_slug = 'material-' + item['material_id'].replace('.', '-')
            nodes = {node['node_id']: node for node in item['nodes']}
            assessments = {f"{row['node_id']}:{row['choice_id']}": row
                           for row in item['assessments']}
            guided = {
                'version': '2.0', 'training_id': training_id,
                'principle': item['principle'],
                'start_node_id': item['start_node_id'],
                'transfer_node_id': item['transfer_node_id'],
                'material_id': item['material_id'],
                'shuffle_options': item['shuffle_options'],
                'example_answer': item['example_answer'],
                'example_visibility': item['example_visibility'],
                'nodes': nodes, 'assessments': assessments, 'criteria': item['criteria'],
            }
            connection.execute(text("""
                INSERT INTO missions (id, knowledge_item_id, character_id, mission_type,
                    interaction_type, title, task, context, config, status)
                VALUES (:id, :knowledge_id, :character_id, 'method_training',
                    'guided_training', :title, :task, :context, :config, 'published')
                ON CONFLICT (id) DO UPDATE SET title=EXCLUDED.title, task=EXCLUDED.task,
                    context=EXCLUDED.context, config=EXCLUDED.config, updated_at=now()
            """), {
                'id': stable_id(f'mission:{training_id}'),
                'knowledge_id': stable_id(f'knowledge:{material_slug}'),
                'character_id': mentor_id,
                'title': item['principle'],
                'task': nodes[item['start_node_id']]['text'],
                'context': Jsonb({'situation': nodes[item['start_node_id']]['text']}),
                'config': Jsonb({'guided': guided}),
            })
            counts['training'] += 1

        # Retain rows referenced by old sessions but remove mock catalog entries.
        connection.execute(text("UPDATE missions SET status='archived' WHERE title LIKE 'Демо · %'"))
        connection.execute(text("UPDATE storylines SET status='archived' WHERE slug LIKE 'demo-%'"))
        connection.execute(text("UPDATE knowledge_items SET status='archived' WHERE slug LIKE 'demo-%'"))
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    knowledge, trainings = load_data()
    print(f"Validated: {len(knowledge['items'])} knowledge items, "
          f"{len(trainings['definitions'])} trainings")
    if args.apply:
        print(dict(apply(knowledge, trainings)))
    else:
        print('Dry run; pass --apply to import.')


if __name__ == '__main__':
    main()
