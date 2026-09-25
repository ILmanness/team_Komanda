from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

from app.db import engine

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


def _fetch_all(
    sql: str,
    params: dict | None = None
):
    with engine.connect() as connection:
        return [
            dict(row)
            for row in connection.execute(
                text(sql),
                params or {}
            ).mappings().all()
        ]


def _fetch_one(
    sql: str,
    params: dict
):
    with engine.connect() as connection:
        row = connection.execute(
            text(sql),
            params
        ).mappings().first()

        return dict(row) if row else None


@router.get(
    "/storylines",
    response_model=list[StorylineListItem]
)
def list_storylines():

    return _fetch_all("""
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
def get_storyline(
    storyline_id: UUID
):

    item = _fetch_one("""
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

    item["missions"] = _fetch_all("""
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


@router.get(
    "/missions",
    response_model=list[MissionListItem]
)
def list_missions(

    mission_type: str | None = Query(
        None,
        pattern="^(story|method_training)$"
    ),

    storyline_id: UUID | None = None,

    knowledge_item_id: UUID | None = None

):

    return _fetch_all("""
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
def get_game_options():
    return GameOptions(
        characters=_fetch_all('SELECT id, name, role_title, description FROM characters ORDER BY name'),
        paei_profiles=_fetch_all('SELECT id, code, leading_letter FROM paei_profiles ORDER BY code'),
        difficulty_profiles=_fetch_all('SELECT id, code, title FROM difficulty_profiles ORDER BY title'),
    )


@router.get('/missions/{mission_id}/briefing', response_model=MissionBriefing)
def get_mission_briefing(mission_id: UUID):
    mission = _fetch_one('''
        SELECT m.id, m.storyline_id, m.mission_type, m.interaction_type,
               m.title, m.task, m.config, c.id AS character_id, c.name AS character_name,
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
            'id': mission['character_id'], 'name': mission['character_name'],
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
def get_mission(
    mission_id: UUID
):
    return get_mission_briefing(mission_id)


@router.get(
    "/knowledge",
    response_model=list[KnowledgeListItem]
)
def list_knowledge(

    parent_id: UUID | None = None

):

    return _fetch_all("""
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


@router.get(
    "/knowledge/{knowledge_id}",
    response_model=KnowledgeDetail
)
def get_knowledge(

    knowledge_id: UUID

):

    item = _fetch_one("""
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

    item["children"] = _fetch_all("""
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
