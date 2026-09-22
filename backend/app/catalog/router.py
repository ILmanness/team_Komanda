from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

from app.db import engine

from .schemas import (
    StorylineListItem,
    StorylineDetail,
    MissionListItem,
    MissionDetail,
    KnowledgeListItem,
    KnowledgeDetail,
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
              :mission_type IS NULL
              OR mission_type = :mission_type
          )

          AND (
              :storyline_id IS NULL
              OR storyline_id = :storyline_id
          )

          AND (
              :knowledge_item_id IS NULL
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


@router.get(
    "/missions/{mission_id}",
    response_model=MissionDetail
)
def get_mission(
    mission_id: UUID
):

    item = _fetch_one("""
        SELECT
            id,
            storyline_id,
            knowledge_item_id,
            mission_type,
            interaction_type,
            branch_key,
            order_index,
            title,
            status,
            character_id,
            context,
            task,
            config,
            created_at,
            updated_at

        FROM missions

        WHERE id = :id
          AND status = 'published'

    """, {
        "id": mission_id
    })

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Mission not found"
        )

    return item


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
              :parent_id IS NULL
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