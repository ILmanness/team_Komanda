"""Export the two editorial training workbooks to the bundled game catalog.

Usage: python tools/export_branching_trainings.py METHODS.xlsx PRINCIPLES.xlsx
Requires openpyxl only when the editorial files are updated.
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

from openpyxl import load_workbook


def rows(sheet):
    iterator = iter(sheet.values)
    headers = next(iterator)
    return [dict(zip(headers, row)) for row in iterator if any(value is not None for value in row)]


def read_workbook(path, category):
    book = load_workbook(path, read_only=True, data_only=True)
    catalog = rows(book['Каталог'])
    nodes = defaultdict(dict)
    options = defaultdict(list)
    feedback = {row['flag']: row['feedback_text'] for row in rows(book['Разбор'])}
    for row in rows(book['Узлы']):
        node = {key: row[key] for key in ('node_id', 'type', 'speaker', 'text', 'outcome')}
        node['options'] = []
        if node['node_id'] in nodes[row['scenario_id']]:
            raise ValueError(f"Duplicate node: {node['node_id']}")
        nodes[row['scenario_id']][node['node_id']] = node
    for row in rows(book['Варианты']):
        if row['flag'] not in feedback:
            raise ValueError(f"Missing feedback: {row['flag']}")
        options[(row['scenario_id'], row['node_id'])].append({
            'id': row['option_id'], 'text': row['text'], 'effect': row['effect'],
            'flag': row['flag'], 'feedback': feedback[row['flag']], 'next_node': row['next_node'],
        })

    tools = {}
    for row in catalog:
        tool_id = str(row['tool_id'])
        scenario_id = str(row['scenario_id'])
        if tool_id not in tools:
            tools[tool_id] = {'id': tool_id, 'category': category, 'title': row['Инструмент'],
                              'description': row['Карточка инструмента'], 'order': len(tools) + 1,
                              'scenarios': []}
        scenario_nodes = nodes[scenario_id]
        if row['start_node_id'] not in scenario_nodes:
            raise ValueError(f'{scenario_id}: start node missing')
        for node_id, node in scenario_nodes.items():
            node['options'] = options[(scenario_id, node_id)]
            if node['type'] == 'terminal' and node['options']:
                raise ValueError(f'{scenario_id}: terminal has options')
            if node['type'] != 'terminal' and len(node['options']) < 2:
                raise ValueError(f'{scenario_id}: missing choices at {node_id}')
            for option in node['options']:
                if option['next_node'] not in scenario_nodes:
                    raise ValueError(f'{scenario_id}: missing target {option["next_node"]}')
        tools[tool_id]['scenarios'].append({
            'id': scenario_id, 'title': row['Ситуация'], 'goal': row['Цель тренировки'],
            'start_node_id': row['start_node_id'], 'weight': row['weight'],
            'status': row['status'], 'nodes': scenario_nodes,
        })
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
    args.output.write_text(json.dumps({'version': '2.0', 'tools': tools}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Exported {len(tools)} tools and 34 scenarios to {args.output}')


if __name__ == '__main__':
    main()
