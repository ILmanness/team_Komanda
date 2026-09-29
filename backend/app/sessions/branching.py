"""Authored branching trainings. No LLM calls are made in this mode."""

import hashlib
import random
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.auth.dependencies import get_current_user
from app.db import engine
from .branching_v3 import apply_choice as apply_v3_choice

router = APIRouter(prefix='/api/v1/sessions', tags=['branching training'])
CurrentUser = Annotated[dict, Depends(get_current_user)]


class BranchingChoice(BaseModel):
    node_id: str = Field(min_length=1, max_length=80)
    option_id: str = Field(min_length=1, max_length=100)
    event_id: UUID | None = None


class BranchingAid(BaseModel):
    kind: Literal['intro', 'card', 'hint']
    node_id: str | None = None


async def _load(connection, session_id, user_id, lock=False):
    row = (await connection.execute(text(f'''
        SELECT id, status, state, config_snapshot, final_result
        FROM game_sessions WHERE id=:id AND user_id=:user_id
        {'FOR UPDATE' if lock else ''}
    '''), {'id': session_id, 'user_id': user_id})).mappings().first()
    if row is None:
        raise HTTPException(404, 'Session not found')
    session = dict(row)
    tool = (((session['config_snapshot'] or {}).get('mission') or {}).get('config') or {}).get('branching')
    if not tool or tool.get('category') not in ('methods', 'principles'):
        raise HTTPException(400, 'Session is not a branching training')
    scenario = next((item for item in tool['scenarios'] if item['id'] == (session['state'] or {}).get('scenario_id')), None)
    if scenario is None:
        raise HTTPException(409, 'Training scenario is unavailable')
    return session, tool, scenario


def _view(session, tool, scenario):
    if tool.get('version') == '3.0':
        return _view_v3(session, tool, scenario)
    state = session['state'] or {}
    node = scenario['nodes'][state['node_id']]
    choices = [{'id': item['id'], 'text': item['text']} for item in node['options']]
    if choices:
        seed = hashlib.sha256(f"{session['id']}:{node['node_id']}".encode()).digest()
        random.Random(seed).shuffle(choices)
    events = [{key: value for key, value in event.items() if key != 'flag' and
               (key != 'feedback' or session['status'] != 'active')}
              for event in state.get('events', [])]
    return {
        'session_id': session['id'], 'status': session['status'],
        'mission_id': ((session['config_snapshot'] or {}).get('mission') or {}).get('id'),
        'tool_id': tool['id'], 'tool_title': tool['title'],
        'tool_description': tool['description'], 'category': tool['category'],
        'scenario_id': scenario['id'], 'scenario_title': scenario['title'],
        'goal': scenario['goal'],
        'node': {key: node[key] for key in ('node_id', 'type', 'speaker', 'text', 'outcome')},
        'choices': choices if session['status'] == 'active' else [],
        'events': events, 'final_result': session['final_result'],
    }


def _view_v3(session, tool, scenario):
    state = session['state'] or {}
    node = scenario['nodes'][state['node_id']]
    finished = session['status'] != 'active'
    learning = state['mode'] == 'learning'
    choices = [{'id': item['id'], 'text': item['text']} for item in node['options']]
    if choices:
        seed = hashlib.sha256(f"{session['id']}:{node['node_id']}".encode()).digest()
        random.Random(seed).shuffle(choices)
    events = []
    for event in state['history']:
        visible = {key: value for key, value in event.items()
                   if key not in ('flag', 'event_id', 'debrief', 'feedback')}
        if learning or finished:
            visible['feedback'] = event['feedback']
        if finished:
            visible['debrief'] = event['debrief']
        events.append(visible)
    hint_visible = learning or node['node_id'] in state['hint_revealed'] or finished
    return {
        'content_version': '3.0', 'session_id': session['id'],
        'mission_id': ((session['config_snapshot'] or {}).get('mission') or {}).get('id'),
        'status': session['status'], 'mode': state['mode'],
        'tool_id': tool['id'], 'tool_title': tool['title'],
        'tool_description': tool['description'], 'category': tool['category'],
        'card': tool['card'], 'card_seen': state['card_seen'],
        'scenario_id': scenario['id'], 'scenario_title': scenario['title'],
        'goal': scenario['goal'], 'level': scenario.get('level'),
        'node': {
            'node_id': node['node_id'], 'type': node['type'],
            'speaker': node['speaker'], 'text': node['text'],
            'outcome': None,
            'skill_step': node['skill_step'] if learning or finished else None,
            'hint': node['hint'] if hint_visible else None,
        },
        'choices': choices if not finished else [], 'events': events,
        'step_results': state['step_results'],
        'consequences': state['consequences'],
        'error_count': state['error_count'],
        'correction_count': state['correction_count'],
        'hint_used': state['hint_used'], 'final_result': session['final_result'],
    }


@router.get('/{session_id}/branching')
async def get_branching(session_id: UUID, current_user: CurrentUser):
    async with engine.connect() as connection:
        session, tool, scenario = await _load(connection, session_id, current_user['id'])
    return _view(session, tool, scenario)


@router.post('/{session_id}/branching/choice')
async def choose_branching(session_id: UUID, choice: BranchingChoice, current_user: CurrentUser):
    async with engine.begin() as connection:
        session, tool, scenario = await _load(connection, session_id, current_user['id'], lock=True)
        state = session['state'] or {}
        if tool.get('version') == '3.0':
            return await _choose_v3(connection, session, tool, scenario, choice)
        events = state.get('events', [])
        previous = next((event for event in events if event['node_id'] == choice.node_id), None)
        if previous:
            if previous['option_id'] != choice.option_id:
                raise HTTPException(409, 'This choice was already made')
            return _view(session, tool, scenario)
        if session['status'] != 'active' or state['node_id'] != choice.node_id:
            raise HTTPException(409, 'This node is no longer active')
        node = scenario['nodes'][choice.node_id]
        option = next((item for item in node['options'] if item['id'] == choice.option_id), None)
        if option is None:
            raise HTTPException(422, 'Unknown option for this node')
        target = scenario['nodes'][option['next_node']]
        event = {'sequence_no': len(events) + 1, 'node_id': choice.node_id,
                 'option_id': option['id'], 'choice_text': option['text'],
                 'effect': option['effect'], 'feedback': option['feedback'],
                 'flag': option['flag'], 'timestamp': datetime.now(UTC).isoformat()}
        state = {**state, 'node_id': target['node_id'], 'events': [*events, event],
                 'turn': len(events) + 1}
        terminal = target['type'] == 'terminal'
        outcome = target['outcome'] if terminal else None
        status = ('completed' if outcome in ('success', 'partial') else 'failed') if terminal else 'active'
        result = {'result': outcome, 'scenario_id': scenario['id'],
                  'tool_id': tool['id']} if terminal else None
        await connection.execute(text('''
            UPDATE game_sessions SET state=:state, status=:status, final_result=:result,
                completed_at=CASE WHEN :terminal THEN now() ELSE completed_at END,
                last_activity_at=now(), lock_version=lock_version+1 WHERE id=:id
        '''), {'id': session_id, 'state': Jsonb(state), 'status': status,
               'result': Jsonb(result) if result is not None else None, 'terminal': terminal})
        session['state'], session['status'], session['final_result'] = state, status, result
    return _view(session, tool, scenario)


async def _choose_v3(connection, session, tool, scenario, choice):
    state = session['state']
    if choice.event_id is None:
        raise HTTPException(422, 'event_id is required')
    event_id = str(choice.event_id)
    previous = next((event for event in state['history'] if event['event_id'] == event_id), None)
    if previous:
        if previous['node_id'] != choice.node_id or previous['option_id'] != choice.option_id:
            raise HTTPException(409, 'Event ID was used for another choice')
        return _view(session, tool, scenario)
    if not state['card_seen']:
        raise HTTPException(409, 'Open or skip the method card first')
    if session['status'] != 'active' or state['node_id'] != choice.node_id:
        raise HTTPException(409, 'This scene is no longer active')
    node = scenario['nodes'][choice.node_id]
    option = next((item for item in node['options'] if item['id'] == choice.option_id), None)
    if option is None:
        raise HTTPException(422, 'Unknown option for this scene')
    try:
        updated, result = apply_v3_choice(state, scenario, option, event_id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    status = 'active' if result is None else 'completed' if result['result'] == 'completed' else 'abandoned'
    await connection.execute(text('''
        UPDATE game_sessions SET state=:state, status=:status, final_result=:result,
            completed_at=CASE WHEN :finished THEN now() ELSE completed_at END,
            last_activity_at=now(), lock_version=lock_version+1 WHERE id=:id
    '''), {'id': session['id'], 'state': Jsonb(updated), 'status': status,
           'result': Jsonb(result) if result else None, 'finished': result is not None})
    session['state'], session['status'], session['final_result'] = updated, status, result
    return _view(session, tool, scenario)


@router.post('/{session_id}/branching/aid')
async def branching_aid(session_id: UUID, aid: BranchingAid, current_user: CurrentUser):
    async with engine.begin() as connection:
        session, tool, scenario = await _load(connection, session_id, current_user['id'], lock=True)
        if tool.get('version') != '3.0':
            raise HTTPException(400, 'Aid is unavailable for this training')
        if session['status'] != 'active':
            raise HTTPException(409, 'Training has finished')
        state = {**session['state']}
        if aid.kind == 'intro':
            state['card_seen'] = True
        elif aid.kind == 'card':
            state['card_seen'] = True
        else:
            if aid.node_id != state['node_id']:
                raise HTTPException(409, 'This scene is no longer active')
            state['hint_used'] = True
            state['hint_revealed'] = list(set([*state['hint_revealed'], aid.node_id]))
        await connection.execute(text('''
            UPDATE game_sessions SET state=:state, last_activity_at=now(),
                lock_version=lock_version+1 WHERE id=:id
        '''), {'id': session_id, 'state': Jsonb(state)})
        session['state'] = state
    return _view(session, tool, scenario)
