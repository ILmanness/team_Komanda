from datetime import datetime
from typing import Any
from uuid import UUID

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


class CharacterOption(BaseModel):
    id: UUID
    name: str
    role_title: str
    description: str


class PaeiOption(BaseModel):
    id: UUID
    code: str
    leading_letter: str


class DifficultyOption(BaseModel):
    id: UUID
    code: str
    title: str


class GameOptions(BaseModel):
    characters: list[CharacterOption]
    paei_profiles: list[PaeiOption]
    difficulty_profiles: list[DifficultyOption]


class MissionBriefing(BaseModel):
    id: UUID
    storyline_id: UUID | None
    mission_type: str
    interaction_type: str
    title: str
    task: str
    character: CharacterOption | None


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
