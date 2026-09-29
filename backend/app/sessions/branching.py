"""Authored branching trainings. No LLM calls are made in this mode."""

import hashlib
import random
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.auth.dependencies import get_current_user
from app.db import engine

router = APIRouter(prefix='/api/v1/sessions', tags=['branching training'])
CurrentUser = Annotated[dict, Depends(get_current_user)]


class BranchingChoice(BaseModel):
    node_id: str = Field(min_length=1, max_length=80)
    option_id: str = Field(min_length=1, max_length=100)


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
