import asyncio
import json
from uuid import uuid4

from app.ai import MockLLMProvider
from app.game.evaluator import Evaluator
from app.game.game_engine import GameEngine
from app.game.goal_tracker import GoalTracker
from app.game.memory import TurnMemory
from app.game.service import GameService


def review(goal, player, opponent, status, evidence, previous=None, sequence=2, progress=None):
    if progress is None:
        progress = {'unresolved': 0, 'advancing': 25, 'achieved': 100, 'blocked': 0}[status]
    tracker = GoalTracker(MockLLMProvider(structured_response={
        'status': status,
        'progress': progress,
        'reason': 'Оценка текущего хода.',
        'evidence': evidence,
    }))
    return asyncio.run(tracker.review(
        goal=goal, previous=previous, player_message=player,
        opponent_message=opponent, sequence_number=sequence,
    ))


def test_agreement_goal_advances_then_succeeds_on_both_speakers():
    goal = 'Согласовать новый срок с заказчиком.'
    pending = review(
        goal, 'Предлагаю перенести срок на пятницу.', 'Мне нужно подумать.',
        'advancing', [{'speaker': 'player', 'quote': 'перенести срок на пятницу'}],
    )
    assert pending['status'] == 'advancing'
    assert pending['progress'] == 25
    assert pending['goal'] == goal
    accepted = review(
        goal, 'Оставляем пятницу?', 'Да, согласен на пятницу.',
        'achieved', [
            {'speaker': 'player', 'quote': 'Оставляем пятницу?'},
            {'speaker': 'opponent', 'quote': 'Да, согласен на пятницу.'},
        ], previous=pending, sequence=4,
    )
    assert accepted['status'] == 'achieved'
    assert accepted['progress'] == 100
    assert [item['sequence_number'] for item in accepted['evidence']] == [1, 3, 4]


def test_goal_can_be_deescalation_without_an_agreement():
    state = review(
        'Снизить напряжение и выяснить опасения собеседника.',
        'Понимаю ваше беспокойство. Что вас тревожит?',
        'Боюсь потерять контроль над бюджетом.',
        'advancing', [{'speaker': 'opponent', 'quote': 'Боюсь потерять контроль над бюджетом.'}],
    )
    assert state['status'] == 'advancing'
    assert state['evidence'][0]['speaker'] == 'opponent'


def test_review_receives_scenario_and_bounded_prior_dialogue():
    class CapturingProvider(MockLLMProvider):
        async def generate_structured(self, messages, response_model):
            self.messages = messages
            return await super().generate_structured(messages, response_model)

    provider = CapturingProvider(structured_response={
        'status': 'unresolved', 'progress': 0,
        'reason': 'Нужны дополнительные сведения.', 'evidence': [],
    })
    tracker = GoalTracker(provider)
    asyncio.run(tracker.review(
        goal='Выяснить причину отказа.', previous=None,
        player_message='Что вас останавливает?', opponent_message='Пока не готов ответить.',
        sequence_number=2,
        scenario_context={'situation': 'Обсуждение бюджета', 'opponent_role': 'Заказчик'},
        recent_history=[{'role': 'user', 'content': 'Ранний разговор ' + 'а' * 500}],
    ))
    payload = json.loads(provider.messages[1]['content'])
    assert payload['scenario']['situation'] == 'Обсуждение бюджета'
    assert payload['scenario']['opponent_role'] == 'Заказчик'
    assert len(payload['recent_dialogue'][0]['text']) == 360


def test_ungrounded_claim_cannot_change_goal_state():
    state = review(
        'Получить ответ о бюджете.', 'Какой у вас бюджет?', 'Обсудим позже.',
        'achieved', [{'speaker': 'opponent', 'quote': 'Бюджет утверждён.'}],
    )
    assert state['status'] == 'unresolved'
    assert state['progress'] == 0
    assert state['evidence'] == []


def test_progress_changes_only_with_grounded_goal_evidence():
    goal = 'Выяснить ограничения проекта.'
    prior = review(
        goal, 'Какие ограничения есть?', 'Бюджет пока не утверждён.',
        'advancing', [{'speaker': 'opponent', 'quote': 'Бюджет пока не утверждён.'}],
        progress=25,
    )
    repeated = review(
        goal, 'Я всё понял.', 'Хорошо.', 'advancing', [],
        previous=prior, sequence=4, progress=50,
    )
    assert repeated['progress'] == 25
    assert repeated['review_available'] is False


def test_provider_failure_keeps_previous_state_and_goal_is_in_prompt_memory():
    prior = GoalTracker.initial('Вежливо отказаться от невыгодного условия.')
    tracker = GoalTracker(MockLLMProvider())
    state = asyncio.run(tracker.review(
        goal=prior['goal'], previous=prior,
        player_message='Это условие не подходит.',
        opponent_message='Я услышал.', sequence_number=2,
    ))
    assert state['status'] == prior['status']
    assert state['review_available'] is False
    prompt_memory = TurnMemory.for_prompt({'goal_state': state}, [])
    assert prompt_memory['goal_state'] == prior


def test_goal_evidence_stays_bounded_across_many_turns():
    goal = 'Выяснить ограничения проекта.'
    state = None
    for turn in range(15):
        quote = f'Ограничение номер {turn}: ' + 'подробность ' * 30
        state = review(
            goal, 'Поясните ограничения.', quote, 'advancing',
            [{'speaker': 'opponent', 'quote': quote}],
            previous=state, sequence=2 * (turn + 1),
        )
    assert len(state['evidence']) == GoalTracker.MAX_EVIDENCE
    assert all(len(item['quote']) <= 300 for item in state['evidence'])


def test_goal_outcome_overrides_numeric_progress_and_max_turn_shortcut():
    engine = GameEngine()
    goal = GoalTracker.initial('Получить согласие на новый срок.')
    goal['review_available'] = True
    pending = {'turn': 3, 'progress': 100, 'critical_errors': 0, 'goal_state': goal}
    assert engine.check_end_conditions(state=pending, max_turns=10)['finished'] is False
    goal['status'] = 'achieved'
    achieved = {**pending, 'turn': 4, 'progress': 12}
    assert engine.check_end_conditions(state=achieved, max_turns=10)['reason'] == 'goal_achieved'
    assert engine.build_final_result(state=achieved, reason='goal_achieved')['result'] == 'success'
    goal['status'] = 'advancing'
    expired = {**pending, 'turn': 10, 'progress': 90}
    assert engine.check_end_conditions(state=expired, max_turns=10)['reason'] == 'max_turns'
    assert engine.build_final_result(state=expired, reason='max_turns')['result'] == 'failure'
    goal['review_available'] = False
    assert engine.check_end_conditions(state=expired, max_turns=10)['reason'] == 'goal_unverified'
    expired['critical_errors'] = 3
    assert engine.check_end_conditions(state=expired, max_turns=10)['reason'] == 'critical_errors'
    assert engine.check_end_conditions(state={'turn': 2, 'progress': 100})['reason'] == 'success'


def test_structured_turn_does_not_award_goal_progress_for_action_type():
    engine = GameEngine()
    evaluation = Evaluator._mock_evaluation('Предлагаю обсудить срок.').model_dump()
    assert engine.apply_evaluation(
        state={'progress': 0, 'goal_state': GoalTracker.initial('Согласовать срок.')},
        evaluation=evaluation,
    )['progress'] == 0
    assert engine.apply_evaluation(
        state={'progress': 0}, evaluation=evaluation,
    )['progress'] > 0


def test_service_decides_outcome_after_opponent_reply(monkeypatch):
    goal = 'Получить согласие на пятницу.'
    player = 'Предлагаю согласовать пятницу.'
    opponent = 'Да, согласна на пятницу.'
    provider = MockLLMProvider(structured_response={
        'status': 'achieved', 'progress': 100, 'reason': 'Собеседник согласился.',
        'evidence': [
            {'speaker': 'player', 'quote': player},
            {'speaker': 'opponent', 'quote': opponent},
        ],
    })
    service = GameService(provider=provider)
    user_id, session_id, message_id = uuid4(), uuid4(), uuid4()
    committed = {}

    async def pending(**kwargs):
        return {'kind': 'created', 'message_id': message_id, 'sequence_number': 1}

    async def get_session(**kwargs):
        return {
            'id': session_id, 'mode': 'custom', 'status': 'active',
            'state': {'turn': 0, 'progress': 0, 'contact': 0, 'tension': 0,
                      'critical_errors': 0, 'goal_state': GoalTracker.initial(goal)},
            'memory_summary': {},
            'config_snapshot': {'custom': {'context': {'goal': goal, 'turn_limit': 10}}},
        }

    async def recent(**kwargs):
        return []

    async def commit(**kwargs):
        committed.update(kwargs)
        return {'id': uuid4(), 'sequence_number': 2}

    monkeypatch.setattr(service, '_create_pending_user_message', pending)
    monkeypatch.setattr(service, '_get_session', get_session)
    monkeypatch.setattr(service, '_get_recent_messages', recent)
    monkeypatch.setattr(service, '_commit_turn', commit)
    evaluation = Evaluator._mock_evaluation(player).model_dump()
    result = asyncio.run(service.process_player_message(
        session_id=session_id, user_id=user_id, content=player,
        idempotency_key=uuid4(), evaluation_override=evaluation,
        response_override=opponent,
    ))
    assert result['events'][-1]['type'] == 'game.finished'
    assert result['events'][-1]['final_result']['reason'] == 'goal_achieved'
    assert committed['state']['progress'] == 100
    assert committed['state']['goal_state']['status'] == 'achieved'
    assert committed['session_status'] == 'completed'


def test_service_marks_last_turn_unverified_when_goal_review_fails(monkeypatch):
    service = GameService(provider=MockLLMProvider())
    goal = 'Узнать ограничения проекта.'
    user_id, session_id, message_id = uuid4(), uuid4(), uuid4()
    committed = {}

    async def pending(**kwargs):
        return {'kind': 'created', 'message_id': message_id, 'sequence_number': 1}

    async def get_session(**kwargs):
        return {
            'id': session_id, 'mode': 'custom', 'status': 'active',
            'state': {'turn': 0, 'progress': 100, 'contact': 0, 'tension': 0,
                      'critical_errors': 0, 'goal_state': GoalTracker.initial(goal)},
            'memory_summary': {},
            'config_snapshot': {'custom': {'context': {'goal': goal, 'turn_limit': 1}}},
        }

    async def recent(**kwargs):
        return []

    async def commit(**kwargs):
        committed.update(kwargs)
        return {'id': uuid4(), 'sequence_number': 2}

    monkeypatch.setattr(service, '_create_pending_user_message', pending)
    monkeypatch.setattr(service, '_get_session', get_session)
    monkeypatch.setattr(service, '_get_recent_messages', recent)
    monkeypatch.setattr(service, '_commit_turn', commit)
    player = 'Какие ограничения нужно учесть?'
    result = asyncio.run(service.process_player_message(
        session_id=session_id, user_id=user_id, content=player,
        idempotency_key=uuid4(),
        evaluation_override=Evaluator._mock_evaluation(player).model_dump(),
        response_override='Вернусь с ответом позже.',
    ))
    assert result['events'][-1]['final_result']['reason'] == 'goal_unverified'
    assert result['events'][-1]['final_result']['result'] == 'finished'
    assert committed['session_status'] == 'needs_review'
