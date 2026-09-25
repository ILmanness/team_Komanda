"""Idempotent published demo content; never overwrites editorial content."""
import argparse
from uuid import NAMESPACE_URL, uuid5

from psycopg.types.json import Jsonb
from sqlalchemy import text

from app.db import engine


def demo_id(key: str):
    return uuid5(NAMESPACE_URL, f'negotiation-arena-demo:{key}')


def insert(connection, sql: str, params: dict) -> bool:
    return connection.execute(text(sql), params).scalar_one_or_none() is not None


def seed() -> dict[str, int]:
    counts = {'knowledge': 0, 'characters': 0, 'profiles': 0, 'storylines': 0, 'missions': 0}
    with engine.begin() as connection:
        topic = demo_id('knowledge:negotiation')
        counts['knowledge'] += insert(connection, '''
            INSERT INTO knowledge_items(id, slug, item_type, title, summary, body, status)
            VALUES (:id, 'demo-negotiation', 'topic', 'Демо · Основы переговоров',
                    'Вопросы, интересы и варианты решения.',
                    'Сначала выясните интересы собеседника. Затем предложите проверяемое решение.',
                    'published') ON CONFLICT DO NOTHING RETURNING id
        ''', {'id': topic})

        anna = demo_id('character:anna')
        igor = demo_id('character:igor')
        for character_id, slug, name, role, description in [
            (anna, 'demo-anna', 'Анна', 'Руководитель проекта', 'Спокойно уточняет причины задержки.'),
            (igor, 'demo-igor', 'Игорь', 'Заказчик', 'Ценит конкретные сроки и прозрачность.'),
        ]:
            counts['characters'] += insert(connection, '''
                INSERT INTO characters(id, slug, name, role_title, description, base_prompt)
                VALUES (:id, :slug, :name, :role, :description, :prompt)
                ON CONFLICT DO NOTHING RETURNING id
            ''', {'id': character_id, 'slug': slug, 'name': name, 'role': role,
                  'description': description, 'prompt': f'Отвечай от лица {name}: {description}'})

        paei = demo_id('paei:balanced')
        difficulty = demo_id('difficulty:normal')
        counts['profiles'] += insert(connection, '''
            INSERT INTO paei_profiles(id, code, leading_letter, p_value, a_value, e_value, i_value,
                                      prompt_rules)
            VALUES (:id, 'DEMO_P', 'P', 65, 55, 45, 50, 'Предпочитает конкретные действия.')
            ON CONFLICT DO NOTHING RETURNING id
        ''', {'id': paei})
        counts['profiles'] += insert(connection, '''
            INSERT INTO difficulty_profiles(id, code, title, prompt_rules, settings)
            VALUES (:id, 'DEMO_NORMAL', 'Демо · Обычная', 'Реагируй естественно.', :settings)
            ON CONFLICT DO NOTHING RETURNING id
        ''', {'id': difficulty, 'settings': Jsonb({'max_turns': 20})})

        storyline = demo_id('storyline:first-week')
        counts['storylines'] += insert(connection, '''
            INSERT INTO storylines(id, slug, title, description, status)
            VALUES (:id, 'demo-first-week', 'Демо · Первая неделя',
                    'Два разговора о сроках и доверии в новой команде.', 'published')
            ON CONFLICT DO NOTHING RETURNING id
        ''', {'id': storyline})

        missions = [
            {
                'id': demo_id('mission:story:first'), 'type': 'story', 'interaction': 'ai_dialogue',
                'storyline': storyline, 'knowledge': None, 'character': anna,
                'branch': 'main', 'order': 1, 'title': 'Демо · Первый разговор',
                'task': 'Обсудите новый срок с Анной и сохраните доверие.',
                'context': {'situation': 'Команда не успевает подготовить релиз.',
                            'opening_message': 'Мы снова не укладываемся. Что предлагаешь?'},
                'config': {'max_turns': 20},
            },
            {
                'id': demo_id('mission:story:second'), 'type': 'story', 'interaction': 'ai_dialogue',
                'storyline': storyline, 'knowledge': None, 'character': igor,
                'branch': 'main', 'order': 2, 'title': 'Демо · Разговор с заказчиком',
                'task': 'Объясните ситуацию Игорю и договоритесь о следующем шаге.',
                'context': {'situation': 'Заказчик ожидает демонстрацию в пятницу.',
                            'opening_message': 'Я рассчитывал увидеть готовый результат в пятницу.'},
                'config': {'max_turns': 20},
            },
            {
                'id': demo_id('mission:training:choice'), 'type': 'method_training',
                'interaction': 'single_choice', 'storyline': None, 'knowledge': topic,
                'character': anna, 'branch': None, 'order': None,
                'title': 'Демо · Сорванный срок',
                'task': 'Выберите ответ, который поможет начать конструктивный разговор.',
                'context': {'situation': 'Команда не успевает закончить задачу.',
                            'opening_message': 'Почему я узнаю о задержке только сейчас?'},
                'config': {'max_turns': 1, 'training': {
                    'hints': ['Признайте проблему без оправданий.', 'Предложите конкретный следующий шаг.'],
                    'choices': [
                        {'id': 'clarify', 'text': 'Вы правы, я должен был предупредить раньше. Давайте покажу план и новый срок.',
                         'feedback': 'Анна соглашается обсудить план. Вы взяли ответственность и предложили действие.',
                         'quality': 0.9, 'contact': 12, 'tension': -8, 'progress': 70, 'critical_error': False},
                        {'id': 'blame', 'text': 'Это команда подвела, я ничего не мог сделать.',
                         'feedback': 'Анна не принимает перекладывание ответственности.',
                         'quality': 0.1, 'contact': -12, 'tension': 15, 'progress': 5, 'critical_error': False},
                        {'id': 'hide', 'text': 'Проблемы нет, всё успеем.',
                         'feedback': 'Анна просит не скрывать риски и назвать реальный срок.',
                         'quality': 0.2, 'contact': -8, 'tension': 10, 'progress': 10, 'critical_error': False},
                    ],
                }},
            },
        ]
        for mission in missions:
            counts['missions'] += insert(connection, '''
                INSERT INTO missions(id, storyline_id, knowledge_item_id, character_id,
                                     mission_type, interaction_type, branch_key, order_index,
                                     title, task, context, config, status)
                VALUES (:id, :storyline, :knowledge, :character, :type, :interaction,
                        :branch, :order, :title, :task, :context, :config, 'published')
                ON CONFLICT DO NOTHING RETURNING id
            ''', {**mission, 'context': Jsonb(mission['context']), 'config': Jsonb(mission['config'])})
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description='Seed clearly labelled demo game content')
    parser.add_argument('--apply', action='store_true', help='Insert only missing demo rows')
    args = parser.parse_args()
    if not args.apply:
        print('Dry run. Pass --apply to insert demo content.')
        return
    print(seed())


if __name__ == '__main__':
    main()
