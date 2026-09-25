from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

Slug = str


class StorylineWrite(BaseModel):
    slug: Slug = Field(pattern=r'^[a-z0-9]+(?:-[a-z0-9]+)*$', max_length=120)
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(default='', max_length=5000)
    cover_url: str | None = Field(default=None, max_length=2000)


class CharacterWrite(BaseModel):
    slug: Slug = Field(pattern=r'^[a-z0-9]+(?:-[a-z0-9]+)*$', max_length=120)
    name: str = Field(min_length=2, max_length=160)
    role_title: str = Field(default='', max_length=200)
    description: str = Field(default='', max_length=3000)
    base_prompt: str = Field(default='', max_length=10000)


class KnowledgeWrite(BaseModel):
    slug: Slug = Field(pattern=r'^[a-z0-9]+(?:-[a-z0-9]+)*$', max_length=120)
    item_type: Literal['topic', 'article', 'method'] = 'topic'
    title: str = Field(min_length=2, max_length=240)
    summary: str = Field(default='', max_length=2000)
    body: str = Field(default='', max_length=30000)
    parent_id: UUID | None = None


class TrainingChoice(BaseModel):
    id: str = Field(pattern=r'^[a-z0-9_-]{1,40}$')
    text: str = Field(min_length=2, max_length=1000)
    feedback: str = Field(min_length=2, max_length=2000)
    quality: float = Field(ge=0, le=1, allow_inf_nan=False)
    contact: int = Field(default=0, ge=-100, le=100)
    tension: int = Field(default=0, ge=-100, le=100)
    progress: int = Field(default=0, ge=-100, le=100)
    critical_error: bool = False


class MissionWrite(BaseModel):
    mission_type: Literal['story', 'method_training']
    interaction_type: Literal['ai_dialogue', 'single_choice'] = 'ai_dialogue'
    storyline_id: UUID | None = None
    knowledge_item_id: UUID | None = None
    character_id: UUID
    branch_key: str | None = Field(default=None, max_length=80)
    order_index: int | None = Field(default=None, ge=1, le=32767)
    title: str = Field(min_length=2, max_length=200)
    situation: str = Field(min_length=10, max_length=5000)
    task: str = Field(min_length=5, max_length=5000)
    opening_message: str = Field(min_length=2, max_length=3000)
    max_turns: int = Field(default=10, ge=1, le=50)
    choices: list[TrainingChoice] = Field(default_factory=list, max_length=12)
    hints: list[str] = Field(default_factory=list, max_length=5)

    @model_validator(mode='after')
    def validate_mode(self):
        if self.mission_type == 'story':
            if not self.storyline_id or not self.branch_key or not self.order_index:
                raise ValueError('Для сюжета нужны ветка, ключ эпизода и порядок')
            if self.interaction_type != 'ai_dialogue':
                raise ValueError('Сюжет пока поддерживает только свободный диалог')
        elif not self.knowledge_item_id:
            raise ValueError('Для тренировки нужна тема базы знаний')
        if self.interaction_type == 'single_choice':
            if self.mission_type != 'method_training' or len(self.choices) < 2:
                raise ValueError('Для тренировки с выбором нужны минимум два ответа')
            if not any(choice.progress >= 50 for choice in self.choices):
                raise ValueError('Хотя бы один ответ должен давать 50 очков прогресса')
        elif self.choices:
            raise ValueError('Варианты ответа доступны только для тренировки с выбором')
        if len({choice.id for choice in self.choices}) != len(self.choices):
            raise ValueError('Идентификаторы вариантов должны быть уникальными')
        if any(not hint.strip() or len(hint) > 500 for hint in self.hints):
            raise ValueError('Подсказка должна содержать от 1 до 500 символов')
        return self
