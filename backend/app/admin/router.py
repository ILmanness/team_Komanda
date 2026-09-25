from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from psycopg.types.json import Jsonb
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.admin.schemas import CharacterWrite, KnowledgeWrite, MissionWrite, StorylineWrite
from app.auth.dependencies import get_current_user
from app.db import engine

router = APIRouter(prefix='/api/v1/admin', tags=['admin'])


def require_admin(current_user: Annotated[dict, Depends(get_current_user)]) -> dict:
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail='Administrator access required')
    return current_user


AdminUser = Annotated[dict, Depends(require_admin)]


class StatusChange(BaseModel):
    status: Literal['draft', 'published', 'archived']


def _one(sql: str, params: dict) -> dict:
    with engine.connect() as connection:
        row = connection.execute(text(sql), params).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail='Content not found')
    return dict(row)


def _write(sql: str, params: dict) -> dict:
    try:
        with engine.begin() as connection:
            row = connection.execute(text(sql), params).mappings().first()
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail='Slug, order or reference conflicts with existing content') from exc
    if row is None:
        raise HTTPException(status_code=404, detail='Content not found')
    return dict(row)


@router.get('/overview')
def overview(_admin: AdminUser):
    queries = {
        'storylines': 'SELECT id, slug, title, description, cover_url, status FROM storylines ORDER BY created_at DESC',
        'missions': '''SELECT m.id, m.title, m.mission_type, m.interaction_type, m.status,
                             m.storyline_id, m.knowledge_item_id, m.character_id,
                             m.branch_key, m.order_index FROM missions m ORDER BY m.created_at DESC''',
        'characters': '''SELECT id, slug, name, role_title, description, base_prompt
                         FROM characters ORDER BY name''',
        'knowledge': '''SELECT id, slug, item_type, title, summary, body, parent_id, status
                        FROM knowledge_items ORDER BY title''',
        'paei_profiles': 'SELECT id, code, leading_letter FROM paei_profiles ORDER BY code',
        'difficulty_profiles': 'SELECT id, code, title FROM difficulty_profiles ORDER BY title',
    }
    with engine.connect() as connection:
        return {
            key: [dict(row) for row in connection.execute(text(sql)).mappings()]
            for key, sql in queries.items()
        }


@router.post('/storylines', status_code=201)
def create_storyline(data: StorylineWrite, admin: AdminUser):
    return _write('''INSERT INTO storylines(slug, title, description, cover_url, created_by_user_id)
                     VALUES (:slug, :title, :description, :cover_url, :admin_id)
                     RETURNING id, status''', {**data.model_dump(), 'admin_id': admin['id']})


@router.put('/storylines/{item_id}')
def update_storyline(item_id: UUID, data: StorylineWrite, _admin: AdminUser):
    return _write('''UPDATE storylines SET slug=:slug, title=:title, description=:description,
                     cover_url=:cover_url, updated_at=now() WHERE id=:id RETURNING id, status''',
                  {**data.model_dump(), 'id': item_id})


@router.post('/characters', status_code=201)
def create_character(data: CharacterWrite, _admin: AdminUser):
    return _write('''INSERT INTO characters(slug, name, role_title, description, base_prompt)
                     VALUES (:slug, :name, :role_title, :description, :base_prompt)
                     RETURNING id''', data.model_dump())


@router.put('/characters/{item_id}')
def update_character(item_id: UUID, data: CharacterWrite, _admin: AdminUser):
    return _write('''UPDATE characters SET slug=:slug, name=:name, role_title=:role_title,
                     description=:description, base_prompt=:base_prompt, updated_at=now()
                     WHERE id=:id RETURNING id''', {**data.model_dump(), 'id': item_id})


@router.post('/knowledge', status_code=201)
def create_knowledge(data: KnowledgeWrite, _admin: AdminUser):
    return _write('''INSERT INTO knowledge_items(slug, item_type, title, summary, body, parent_id)
                     VALUES (:slug, :item_type, :title, :summary, :body, :parent_id)
                     RETURNING id, status''', data.model_dump())


@router.put('/knowledge/{item_id}')
def update_knowledge(item_id: UUID, data: KnowledgeWrite, _admin: AdminUser):
    if data.parent_id == item_id:
        raise HTTPException(status_code=422, detail='A topic cannot be its own parent')
    return _write('''UPDATE knowledge_items SET slug=:slug, item_type=:item_type,
                     title=:title, summary=:summary, body=:body, parent_id=:parent_id,
                     updated_at=now() WHERE id=:id RETURNING id, status''',
                  {**data.model_dump(), 'id': item_id})


def _mission_params(data: MissionWrite) -> dict:
    training = None
    if data.mission_type == 'method_training':
        training = {
            'hints': data.hints,
            'choices': [choice.model_dump() for choice in data.choices],
        }
    return {
        'mission_type': data.mission_type,
        'interaction_type': data.interaction_type,
        'storyline_id': data.storyline_id,
        'knowledge_item_id': data.knowledge_item_id,
        'character_id': data.character_id,
        'branch_key': data.branch_key if data.mission_type == 'story' else None,
        'order_index': data.order_index if data.mission_type == 'story' else None,
        'title': data.title,
        'task': data.task,
        'context': Jsonb({'situation': data.situation, 'opening_message': data.opening_message}),
        'config': Jsonb({'max_turns': 1 if data.interaction_type == 'single_choice' else data.max_turns,
                         'training': training}),
    }


@router.get('/missions/{item_id}')
def get_mission(item_id: UUID, _admin: AdminUser):
    return _one('''SELECT id, storyline_id, knowledge_item_id, character_id, mission_type,
                  interaction_type, branch_key, order_index, title, task, context, config, status
                  FROM missions WHERE id=:id''', {'id': item_id})


@router.post('/missions', status_code=201)
def create_mission(data: MissionWrite, _admin: AdminUser):
    return _write('''INSERT INTO missions(storyline_id, knowledge_item_id, character_id,
                     mission_type, interaction_type, branch_key, order_index, title, task, context, config)
                     VALUES (:storyline_id, :knowledge_item_id, :character_id, :mission_type,
                             :interaction_type, :branch_key, :order_index, :title, :task, :context, :config)
                     RETURNING id, status''', _mission_params(data))


@router.put('/missions/{item_id}')
def update_mission(item_id: UUID, data: MissionWrite, _admin: AdminUser):
    existing = _one('SELECT mission_type FROM missions WHERE id=:id', {'id': item_id})
    if existing['mission_type'] != data.mission_type:
        raise HTTPException(status_code=422, detail='Mission mode cannot be changed after creation')
    return _write('''UPDATE missions SET storyline_id=:storyline_id,
                     knowledge_item_id=:knowledge_item_id, character_id=:character_id,
                     interaction_type=:interaction_type, branch_key=:branch_key,
                     order_index=:order_index, title=:title, task=:task,
                     context=:context, config=:config, updated_at=now()
                     WHERE id=:id RETURNING id, status''', {**_mission_params(data), 'id': item_id})


@router.put('/{kind}/{item_id}/status')
def set_status(kind: Literal['storylines', 'missions', 'knowledge'], item_id: UUID,
               data: StatusChange, _admin: AdminUser):
    table = {'storylines': 'storylines', 'missions': 'missions', 'knowledge': 'knowledge_items'}[kind]
    if kind == 'missions' and data.status == 'published':
        mission = _one('''SELECT m.mission_type, m.interaction_type, m.config,
                         m.character_id, s.status AS storyline_status, k.status AS knowledge_status
                         FROM missions m
                         LEFT JOIN storylines s ON s.id=m.storyline_id
                         LEFT JOIN knowledge_items k ON k.id=m.knowledge_item_id
                         WHERE m.id=:id''', {'id': item_id})
        if not mission['character_id']:
            raise HTTPException(status_code=422, detail='Assign a character before publication')
        if mission['mission_type'] == 'story' and mission['storyline_status'] != 'published':
            raise HTTPException(status_code=422, detail='Publish the storyline first')
        if mission['mission_type'] == 'method_training' and mission['knowledge_status'] != 'published':
            raise HTTPException(status_code=422, detail='Publish the knowledge topic first')
        if mission['interaction_type'] == 'single_choice':
            choices = ((mission['config'] or {}).get('training') or {}).get('choices', [])
            if len(choices) < 2:
                raise HTTPException(status_code=422, detail='Add at least two answers')
    return _write(f'''UPDATE {table} SET status=:status, updated_at=now()
                      WHERE id=:id RETURNING id, status''',
                  {'id': item_id, 'status': data.status})
