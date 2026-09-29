from typing import Any, Literal
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
    paei_profile_id: UUID | None = None
    paei_description: str = Field(default='', max_length=3000)
    behavior_description: str = Field(default='', max_length=3000)
    portrait_url: str = Field(default='', max_length=2000)


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


class GuidedOptionWrite(BaseModel):
    text: str = Field(min_length=2, max_length=1000)
    effect: str = Field(default='', max_length=2000)
    feedback: str = Field(min_length=2, max_length=2000)
    assessment: Literal['correct', 'partial', 'incorrect']


class GuidedStepWrite(BaseModel):
    speaker: str = Field(default='Старшая коллега', min_length=2, max_length=160)
    text: str = Field(min_length=10, max_length=3000)
    goal: str = Field(min_length=5, max_length=1000)
    hint: str = Field(min_length=5, max_length=1000)
    options: list[GuidedOptionWrite] = Field(min_length=3, max_length=3)

    @model_validator(mode='after')
    def has_solution(self):
        if not any(option.assessment == 'correct' for option in self.options):
            raise ValueError('В каждой ситуации нужен хотя бы один верный ответ')
        return self


class GuidedAuthoringWrite(BaseModel):
    steps: list[GuidedStepWrite] = Field(min_length=1, max_length=8)
    final_situation: str = Field(min_length=10, max_length=3000)
    final_goal: str = Field(min_length=5, max_length=1000)
    criteria: list[str] = Field(min_length=1, max_length=6)
    example_answer: str = Field(min_length=10, max_length=5000)

    @model_validator(mode='after')
    def valid_criteria(self):
        if any(len(value.strip()) < 5 or len(value) > 500 for value in self.criteria):
            raise ValueError('Каждый критерий должен содержать от 5 до 500 символов')
        return self


class BranchingOptionWrite(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=2, max_length=1000)
    effect: str | None = Field(default=None, max_length=2000)
    flag: str | None = Field(default=None, max_length=100)
    feedback: str = Field(min_length=2, max_length=2000)
    next_node: str = Field(min_length=1, max_length=100)


class BranchingNodeWrite(BaseModel):
    node_id: str = Field(min_length=1, max_length=100)
    type: Literal['decision', 'consequence', 'terminal']
    speaker: str = Field(min_length=2, max_length=160)
    text: str = Field(min_length=2, max_length=3000)
    outcome: Literal['success', 'partial', 'fail', 'not_applied'] | None = None
    options: list[BranchingOptionWrite] = Field(default_factory=list, max_length=12)


class BranchingScenarioWrite(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=2, max_length=200)
    goal: str = Field(min_length=5, max_length=1000)
    start_node_id: str = Field(min_length=1, max_length=100)
    weight: int = Field(default=1, ge=1, le=100)
    status: Literal['active', 'inactive'] = 'active'
    nodes: dict[str, BranchingNodeWrite] = Field(min_length=2, max_length=80)

    @model_validator(mode='after')
    def valid_graph(self):
        nodes = self.nodes
        if self.start_node_id not in nodes or nodes[self.start_node_id].type == 'terminal':
            raise ValueError('Начальный узел должен существовать и содержать выбор')
        seen_options = set()
        for key, node in nodes.items():
            if node.node_id != key:
                raise ValueError(f'ID узла {key} не совпадает с ключом')
            if node.type == 'terminal':
                if node.options or node.outcome is None:
                    raise ValueError(f'Итог {key} должен иметь результат и не иметь вариантов')
            elif len(node.options) < 2 or node.outcome is not None:
                raise ValueError(f'В узле {key} нужны минимум два ответа и не нужен итог')
            for option in node.options:
                if option.id in seen_options or option.next_node not in nodes:
                    raise ValueError(f'Повторяющийся ответ или неизвестный переход в узле {key}')
                seen_options.add(option.id)
        visited, visiting, terminal_seen = set(), set(), set()

        def walk(node_id):
            if node_id in visiting:
                raise ValueError(f'Цикл переходов в узле {node_id}')
            if node_id in visited:
                return
            visiting.add(node_id)
            node = nodes[node_id]
            if node.type == 'terminal':
                terminal_seen.add(node_id)
            for option in node.options:
                walk(option.next_node)
            visiting.remove(node_id)
            visited.add(node_id)

        walk(self.start_node_id)
        if visited != set(nodes) or not terminal_seen:
            raise ValueError('Все узлы должны быть достижимы, хотя бы один должен завершать сценарий')
        return self


class BranchingToolWrite(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    category: Literal['methods', 'principles']
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(min_length=5, max_length=5000)
    order: int = Field(ge=1, le=32767)
    scenarios: list[BranchingScenarioWrite] = Field(min_length=1, max_length=20)

    @model_validator(mode='after')
    def valid_scenarios(self):
        if len({scenario.id for scenario in self.scenarios}) != len(self.scenarios):
            raise ValueError('Идентификаторы сценариев должны быть уникальными')
        if not any(scenario.status == 'active' for scenario in self.scenarios):
            raise ValueError('Нужен хотя бы один активный сценарий')
        return self


class BranchingToolV3Write(BaseModel):
    version: Literal['3.0']
    id: str = Field(min_length=1, max_length=100)
    category: Literal['methods', 'principles']
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(min_length=5, max_length=5000)
    order: int = Field(ge=1, le=32767)
    card: dict[str, str]
    scenarios: list[dict[str, Any]] = Field(min_length=1, max_length=20)

    @model_validator(mode='after')
    def valid_catalog(self):
        from app.admin.import_editorial import validate_branching_v3

        if not any(scenario.get('status') == 'active' for scenario in self.scenarios):
            raise ValueError('Нужен хотя бы один активный сценарий')
        try:
            validate_branching_v3({'tools': [self.model_dump()]}, strict_catalog=False)
        except (KeyError, TypeError, AttributeError) as exc:
            raise ValueError('Неполный сценарий версии 3.0') from exc
        return self


class MissionWrite(BaseModel):
    mission_type: Literal['story', 'method_training']
    interaction_type: Literal['ai_dialogue', 'single_choice', 'guided_training', 'branching_training'] = 'ai_dialogue'
    storyline_id: UUID | None = None
    knowledge_item_id: UUID | None = None
    character_id: UUID
    branch_key: str | None = Field(default=None, max_length=80)
    order_index: int | None = Field(default=None, ge=1, le=32767)
    title: str = Field(min_length=2, max_length=200)
    situation: str = Field(min_length=10, max_length=5000)
    public_context: str = Field(default='', max_length=5000)
    task: str = Field(min_length=5, max_length=5000)
    opening_message: str = Field(min_length=2, max_length=3000)
    max_turns: int = Field(default=10, ge=1, le=50)
    choices: list[TrainingChoice] = Field(default_factory=list, max_length=12)
    hints: list[str] = Field(default_factory=list, max_length=5)
    guided: GuidedAuthoringWrite | None = None
    branching: BranchingToolV3Write | BranchingToolWrite | None = None

    @model_validator(mode='after')
    def validate_mode(self):
        if self.mission_type == 'story':
            if not self.storyline_id or not self.branch_key or not self.order_index:
                raise ValueError('Для сюжета нужны ветка, ключ эпизода и порядок')
            if self.interaction_type != 'ai_dialogue':
                raise ValueError('Сюжет пока поддерживает только свободный диалог')
        elif not self.knowledge_item_id:
            raise ValueError('Для тренировки нужна тема базы знаний')
        elif self.interaction_type not in ('single_choice', 'guided_training', 'branching_training'):
            raise ValueError('Тренировка использует подготовленные ответы, без AI-диалога')
        if self.interaction_type == 'single_choice':
            if self.mission_type != 'method_training' or len(self.choices) < 2:
                raise ValueError('Для тренировки с выбором нужны минимум два ответа')
            if not any(choice.progress >= 50 for choice in self.choices):
                raise ValueError('Хотя бы один ответ должен давать 50 очков прогресса')
        elif self.choices:
            raise ValueError('Варианты ответа доступны только для тренировки с выбором')
        if self.interaction_type == 'guided_training' and not self.guided:
            raise ValueError('Добавьте ситуации и финальную проверку')
        if self.interaction_type != 'guided_training' and self.guided:
            raise ValueError('Пошаговый сценарий доступен только для пошаговой тренировки')
        if self.interaction_type == 'branching_training':
            if not self.branching:
                raise ValueError('Добавьте сценарии с вариантами и итогами')
            if (self.branch_key != self.branching.category or
                    self.order_index != self.branching.order or
                    self.title != self.branching.title or self.task != self.branching.description):
                raise ValueError('Раздел, порядок, название и описание должны совпадать с тренажёром')
        elif self.branching:
            raise ValueError('Развилки доступны только для новой тренировки')
        if len({choice.id for choice in self.choices}) != len(self.choices):
            raise ValueError('Идентификаторы вариантов должны быть уникальными')
        if any(not hint.strip() or len(hint) > 500 for hint in self.hints):
            raise ValueError('Подсказка должна содержать от 1 до 500 символов')
        return self
