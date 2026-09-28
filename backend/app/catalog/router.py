from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from psycopg.types.json import Jsonb
from sqlalchemy import text

from app.auth.dependencies import get_current_user
from app.db import engine
from app.story_progress import get_story_progress

from .schemas import (
    GameOptions,
    KnowledgeDetail,
    KnowledgeListItem,
    MissionBriefing,
    MissionListItem,
    StorylineDetail,
    StorylineListItem,
)

router = APIRouter(
    prefix="/api/v1",
    tags=["catalog"]
)


class QuizSubmission(BaseModel):
    answers: dict[str, str] = Field(min_length=3, max_length=3)


async def _fetch_all(
    sql: str,
    params: dict | None = None
):
    async with engine.connect() as connection:
        return [
            dict(row)
            for row in (await connection.execute(
                text(sql),
                params or {}
            )).mappings().all()
        ]


async def _fetch_one(
    sql: str,
    params: dict
):
    async with engine.connect() as connection:
        row = (await connection.execute(
            text(sql),
            params
        )).mappings().first()

        return dict(row) if row else None


@router.get(
    "/storylines",
    response_model=list[StorylineListItem]
)
async def list_storylines():

    return await _fetch_all("""
        SELECT
            id,
            slug,
            title,
            description,
            cover_url,
            status,
            created_at,
            updated_at

        FROM storylines

        WHERE status = 'published'

        ORDER BY created_at DESC
    """)


@router.get(
    "/storylines/{storyline_id}",
    response_model=StorylineDetail
)
async def get_storyline(
    storyline_id: UUID
):

    item = await _fetch_one("""
        SELECT
            id,
            slug,
            title,
            description,
            cover_url,
            status,
            created_at,
            updated_at

        FROM storylines

        WHERE id = :id
          AND status = 'published'
    """, {
        "id": storyline_id
    })

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Storyline not found"
        )

    item["missions"] = await _fetch_all("""
        SELECT
            id,
            storyline_id,
            knowledge_item_id,
            mission_type,
            interaction_type,
            branch_key,
            order_index,
            title,
            status

        FROM missions

        WHERE storyline_id = :id
          AND mission_type = 'story'
          AND status = 'published'

        ORDER BY branch_key, order_index
    """, {
        "id": storyline_id
    })

    return item


@router.get('/storylines/{storyline_id}/progress')
async def storyline_progress(storyline_id: UUID, current_user: Annotated[dict, Depends(get_current_user)]):
    async with engine.connect() as connection:
        exists = (await connection.execute(text('''
            SELECT 1 FROM storylines WHERE id=:id AND status='published'
        '''), {'id': storyline_id})).scalar_one_or_none()
        if exists is None:
            raise HTTPException(status_code=404, detail='Storyline not found')
        return {'missions': await get_story_progress(connection, storyline_id, current_user['id'])}


@router.get(
    "/missions",
    response_model=list[MissionListItem]
)
async def list_missions(

    mission_type: str | None = Query(
        None,
        pattern="^(story|method_training)$"
    ),

    storyline_id: UUID | None = None,

    knowledge_item_id: UUID | None = None

):

    return await _fetch_all("""
        SELECT
            id,
            storyline_id,
            knowledge_item_id,
            mission_type,
            interaction_type,
            branch_key,
            order_index,
            title,
            status

        FROM missions

        WHERE status = 'published'

          AND (
              CAST(:mission_type AS text) IS NULL
              OR mission_type = :mission_type
          )

          AND (
              CAST(:storyline_id AS uuid) IS NULL
              OR storyline_id = :storyline_id
          )

          AND (
              CAST(:knowledge_item_id AS uuid) IS NULL
              OR knowledge_item_id = :knowledge_item_id
          )

        ORDER BY
            storyline_id NULLS LAST,
            branch_key,
            order_index,
            title

    """, {

        "mission_type": mission_type,

        "storyline_id": storyline_id,

        "knowledge_item_id": knowledge_item_id

    })


@router.get('/game/options', response_model=GameOptions)
async def get_game_options():
    return GameOptions(
        characters=await _fetch_all('SELECT id, slug, name, role_title, description FROM characters ORDER BY name'),
        paei_profiles=await _fetch_all('SELECT id, code, leading_letter FROM paei_profiles ORDER BY code'),
        difficulty_profiles=await _fetch_all('SELECT id, code, title FROM difficulty_profiles ORDER BY title'),
    )


@router.get('/missions/{mission_id}/briefing', response_model=MissionBriefing)
async def get_mission_briefing(mission_id: UUID):
    mission = await _fetch_one('''
        SELECT m.id, m.storyline_id, m.mission_type, m.interaction_type,
               m.title, m.task, m.config, c.id AS character_id, c.slug AS character_slug, c.name AS character_name,
               c.role_title AS character_role_title, c.description AS character_description
        FROM missions AS m
        LEFT JOIN characters AS c ON c.id = m.character_id
        WHERE m.id = :id AND m.status = 'published'
    ''', {'id': mission_id})
    if mission is None:
        raise HTTPException(status_code=404, detail='Mission not found')
    character = None
    if mission['character_id'] is not None:
        character = {
            'id': mission['character_id'], 'slug': mission['character_slug'], 'name': mission['character_name'],
            'role_title': mission['character_role_title'],
            'description': mission['character_description'],
        }
    training = (mission['config'] or {}).get('training') or {}
    return MissionBriefing(**{
        key: mission[key] for key in ('id', 'storyline_id', 'mission_type', 'interaction_type', 'title', 'task')
    }, character=character,
        choices=[{'id': item['id'], 'text': item['text']} for item in training.get('choices', [])],
        hints=training.get('hints', []))


@router.get(
    "/missions/{mission_id}",
    response_model=MissionBriefing
)
async def get_mission(
    mission_id: UUID
):
    return await get_mission_briefing(mission_id)


@router.get(
    "/knowledge",
    response_model=list[KnowledgeListItem]
)
async def list_knowledge(

    parent_id: UUID | None = None

):

    return await _fetch_all("""
        SELECT
            id,
            parent_id,
            item_type,
            slug,
            title,
            summary,
            status,
            sort_order,
            created_at,
            updated_at

        FROM knowledge_items

        WHERE status = 'published'

          AND (
              CAST(:parent_id AS uuid) IS NULL
              OR parent_id = :parent_id
          )

        ORDER BY sort_order, title

    """, {
        "parent_id": parent_id
    })


@router.get('/knowledge/progress')
async def knowledge_progress(current_user: Annotated[dict, Depends(get_current_user)]):
    async with engine.connect() as connection:
        completed = (await connection.execute(text("""
            SELECT knowledge_item_id FROM knowledge_progress WHERE user_id=:user_id
        """), {'user_id': current_user['id']})).scalars().all()
        attempts = (await connection.execute(text("""
            SELECT DISTINCT ON (knowledge_item_id)
                   knowledge_item_id, score, question_count, created_at
            FROM knowledge_quiz_attempts WHERE user_id=:user_id
            ORDER BY knowledge_item_id, created_at DESC
        """), {'user_id': current_user['id']})).mappings().all()
    return {'completed_ids': completed, 'latest_quizzes': [dict(row) for row in attempts]}


@router.get('/knowledge/{knowledge_id}/quiz')
async def get_knowledge_quiz(knowledge_id: UUID):
    item = await _fetch_one("""
        SELECT id, title, metadata FROM knowledge_items
        WHERE id=:id AND status='published'
    """, {'id': knowledge_id})
    if item is None or (item['metadata'] or {}).get('kind') != 'test':
        raise HTTPException(status_code=404, detail='Knowledge quiz not found')
    quiz = item['metadata']['quiz']
    selected = set(quiz['short_question_numbers'])
    return {'id': item['id'], 'title': item['title'],
            'questions': [
                {key: question[key] for key in ('number', 'prompt', 'choices', 'material_id')}
                for question in quiz['questions'] if question['number'] in selected
            ]}


@router.post('/knowledge/{knowledge_id}/complete')
async def complete_knowledge(knowledge_id: UUID,
                       current_user: Annotated[dict, Depends(get_current_user)]):
    item = await _fetch_one("""
        SELECT id, metadata FROM knowledge_items
        WHERE id=:id AND status='published'
    """, {'id': knowledge_id})
    if item is None or (item['metadata'] or {}).get('kind') != 'material':
        raise HTTPException(status_code=404, detail='Knowledge material not found')
    async with engine.begin() as connection:
        await connection.execute(text("""
            INSERT INTO knowledge_progress(user_id, knowledge_item_id)
            VALUES (:user_id, :item_id) ON CONFLICT DO NOTHING
        """), {'user_id': current_user['id'], 'item_id': knowledge_id})
    return {'knowledge_item_id': knowledge_id, 'completed': True}


@router.post('/knowledge/{knowledge_id}/quiz')
async def submit_knowledge_quiz(knowledge_id: UUID, data: QuizSubmission,
                          current_user: Annotated[dict, Depends(get_current_user)]):
    item = await _fetch_one("""
        SELECT id, metadata FROM knowledge_items
        WHERE id=:id AND status='published'
    """, {'id': knowledge_id})
    if item is None or (item['metadata'] or {}).get('kind') != 'test':
        raise HTTPException(status_code=404, detail='Knowledge quiz not found')
    quiz = item['metadata']['quiz']
    selected = set(quiz['short_question_numbers'])
    if set(data.answers) != {str(number) for number in selected} or any(
        answer not in ('A', 'B', 'C', 'D') for answer in data.answers.values()
    ):
        raise HTTPException(status_code=422, detail='Answer all short-check questions using A, B, C or D')
    results = []
    for question in quiz['questions']:
        if question['number'] not in selected:
            continue
        choice = data.answers[str(question['number'])]
        results.append({
            'number': question['number'], 'material_id': question['material_id'],
            'selected': choice, 'correct': question['correct'],
            'is_correct': choice == question['correct'],
            'explanation': question['explanation'],
        })
    score = sum(result['is_correct'] for result in results)
    async with engine.begin() as connection:
        await connection.execute(text("""
            INSERT INTO knowledge_quiz_attempts
                (user_id, knowledge_item_id, answers, score, question_count)
            VALUES (:user_id, :item_id, :answers, :score, :count)
        """), {'user_id': current_user['id'], 'item_id': knowledge_id,
              'answers': Jsonb(data.answers), 'score': score, 'count': len(results)})
        if score == len(results):
            await connection.execute(text("""
                INSERT INTO knowledge_progress(user_id, knowledge_item_id)
                VALUES (:user_id, :item_id) ON CONFLICT DO NOTHING
            """), {'user_id': current_user['id'], 'item_id': knowledge_id})
    return {'score': score, 'total': len(results), 'results': results,
            'completed': score == len(results)}


@router.get(
    "/knowledge/{knowledge_id}",
    response_model=KnowledgeDetail
)
async def get_knowledge(

    knowledge_id: UUID

):

    item = await _fetch_one("""
        SELECT
            id,
            parent_id,
            item_type,
            slug,
            title,
            summary,
            body,
            metadata,
            status,
            sort_order,
            created_at,
            updated_at

        FROM knowledge_items

        WHERE id = :id
          AND status = 'published'

    """, {
        "id": knowledge_id
    })

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Knowledge item not found"
        )

    if (item['metadata'] or {}).get('kind') == 'test':
        item['metadata'] = {key: value for key, value in item['metadata'].items()
                            if key not in ('quiz', 'answer_key')}

    item["children"] = await _fetch_all("""
        SELECT
            id,
            parent_id,
            item_type,
            slug,
            title,
            summary,
            status,
            sort_order,
            created_at,
            updated_at

        FROM knowledge_items

        WHERE parent_id = :id
          AND status = 'published'

        ORDER BY sort_order, title

    """, {
        "id": knowledge_id
    })

    return item
