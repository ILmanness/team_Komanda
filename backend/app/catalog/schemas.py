from datetime import datetime
from uuid import UUID
from typing import Any

from pydantic import BaseModel, ConfigDict


class CatalogBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    title: str
    status: str
    created_at: datetime
    updated_at: datetime


class StorylineListItem(CatalogBase):
    description: str
    cover_url: str | None = None


class StorylineDetail(StorylineListItem):
    missions: list["MissionListItem"] = []


class MissionListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    storyline_id: UUID | None = None
    knowledge_item_id: UUID | None = None

    mission_type: str
    interaction_type: str

    branch_key: str | None = None
    order_index: int | None = None

    title: str
    status: str


class MissionDetail(MissionListItem):
    character_id: UUID | None = None

    context: dict[str, Any]
    task: str
    config: dict[str, Any]

    created_at: datetime
    updated_at: datetime


class KnowledgeListItem(CatalogBase):
    parent_id: UUID | None = None

    item_type: str
    summary: str | None = None
    sort_order: int


class KnowledgeDetail(KnowledgeListItem):
    body: str | None = None
    metadata: dict[str, Any]

    children: list[KnowledgeListItem] = []


StorylineDetail.model_rebuild()
KnowledgeDetail.model_rebuild()