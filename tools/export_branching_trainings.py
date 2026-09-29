"""Export the method and principle workbooks to the playable v3 catalog.

Usage: python tools/export_branching_trainings.py METHODS.xlsx PRINCIPLES.xlsx
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

from openpyxl import load_workbook


CARD_FIELDS = {
    'Суть': 'essence', 'Когда применять': 'when_to_apply',
    'Шаги применения': 'steps', 'Типичная ошибка': 'typical_error',
    'Пример': 'example', 'Граница применения': 'limit',
}
DEBRIEF_FIELDS = {
    'Шаг инструмента': 'step', 'Ваш выбор': 'choice',
    'Что это даёт / почему не хватает': 'explanation',
    'Как улучшить или повторить': 'improvement', 'Тип': 'type',
}
OUTCOME_FIELDS = {
    'Результат ситуации': 'text', 'Статус попытки': 'status',
    'Правило оценки применения': 'application_rule',
    'Правило последствий': 'consequence_rule', 'Что повторить': 'repeat',
}


def rows(sheet):
    iterator = iter(sheet.values)
    headers = next(iterator)
    return [dict(zip(headers, row)) for row in iterator if any(value is not None for value in row)]


def read_workbook(path, category):
    book = load_workbook(path, read_only=True, data_only=True)
    catalog = rows(book['Каталог'])
    cards = {row['tool_id']: row for row in rows(book['Карточки'])}
    debrief = {row['flag']: {key: row[source] for source, key in DEBRIEF_FIELDS.items()}
               for row in rows(book['Разбор'])}
    outcomes, nodes, options = defaultdict(dict), defaultdict(dict), defaultdict(list)
    for row in rows(book['Итоги']):
        outcomes[row['scenario_id']][row['outcome_id']] = {
            'id': row['outcome_id'],
            **{key: row[source] for source, key in OUTCOME_FIELDS.items()},
        }
    for row in rows(book['Узлы']):
        node = {key: row[key] for key in ('node_id', 'type', 'speaker', 'text', 'skill_step',
                                          'hint', 'required_flags', 'outcome_id')}
        node['options'] = []
        if node['node_id'] in nodes[row['scenario_id']]:
            raise ValueError(f"Duplicate node: {node['node_id']}")
        nodes[row['scenario_id']][node['node_id']] = node
    for row in rows(book['Варианты']):
        if row['flag'] not in debrief:
            raise ValueError(f"Missing debrief: {row['flag']}")
        try:
            changes = json.loads(row['state_changes'])
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid state_changes: {row['option_id']}") from exc
        options[(row['scenario_id'], row['node_id'])].append({
            'id': row['option_id'], 'text': row['text'], 'effect': row['effect'],
            'flag': row['flag'], 'feedback': debrief[row['flag']]['explanation'],
            'debrief': debrief[row['flag']], 'next_node': row['next_node'],
            'state_changes': changes, 'result_type': row['result_type'],
        })
    tools = {}
    for row in catalog:
        tool_id, scenario_id = str(row['tool_id']), str(row['scenario_id'])
        if tool_id not in cards:
            raise ValueError(f'{tool_id}: missing card')
        if tool_id not in tools:
            card = cards[tool_id]
            tools[tool_id] = {
                'version': '3.0', 'id': tool_id, 'category': category, 'title': row['Инструмент'],
                'description': card['Суть'], 'order': len(tools) + 1,
                'card': {key: card[source] for source, key in CARD_FIELDS.items()},
                'scenarios': [],
            }
        scenario_nodes = nodes[scenario_id]
        if row['start_node_id'] not in scenario_nodes:
            raise ValueError(f'{scenario_id}: start node missing')
        for node_id, node in scenario_nodes.items():
            node['options'] = options[(scenario_id, node_id)]
            if node['type'] == 'terminal':
                if node['options'] or node['outcome_id'] not in outcomes[scenario_id]:
                    raise ValueError(f'{scenario_id}/{node_id}: invalid terminal')
            elif len(node['options']) < 2:
                raise ValueError(f'{scenario_id}/{node_id}: missing choices')
            for option in node['options']:
                if option['next_node'] not in scenario_nodes:
                    raise ValueError(f'{scenario_id}: missing target {option["next_node"]}')
        tools[tool_id]['scenarios'].append({
            'id': scenario_id, 'title': row['Ситуация'], 'goal': row['Цель тренировки'],
            'start_node_id': row['start_node_id'], 'weight': row['weight'],
            'status': row['status'], 'level': row['Уровень'],
            'clean_steps': row['Шагов без исправлений'],
            'transfer_focus': row['Фокус второй ситуации'],
            'nodes': scenario_nodes, 'outcomes': outcomes[scenario_id],
            'step_order': [node_id for node_id, node in scenario_nodes.items()
                           if node['type'] == 'decision'],
        })
    book.close()
    return list(tools.values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('methods', type=Path)
    parser.add_argument('principles', type=Path)
    parser.add_argument('--output', type=Path, default=Path('backend/content/branching_trainings.json'))
    args = parser.parse_args()
    tools = read_workbook(args.methods, 'methods') + read_workbook(args.principles, 'principles')
    if len(tools) != 17 or sum(len(tool['scenarios']) for tool in tools) != 34:
        raise ValueError('Expected 17 tools and 34 scenarios')
    args.output.write_text(json.dumps({'version': '3.0', 'tools': tools}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Exported {len(tools)} tools and 34 scenarios to {args.output}')


if __name__ == '__main__':
    main()
