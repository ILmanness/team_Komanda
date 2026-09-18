# DATA-02 — Модели уровня, персонажа и PAEI

> Проект: **«Арена переговоров»**  
> Задача: **[DATA-02] Реализовать модели уровня, персонажа и PAEI #43**  
> Версия документа: **0.1 / MVP**  
> Статус: **DRAFT**

## 1. Назначение

Документ является проектным контрактом для реализации трёх доменных сущностей:

- `Level`;
- `Character`;
- `PAEIProfile`.

Модель должна быть независимой от UI и пригодной для использования из:

```text
StoryVersion
    ↓
Level
    ↓
Character
    ↓
PAEIProfile
    ↓
Evaluator / Game Engine / Reaction Model
```

Основная задача DATA-02 — обеспечить проверяемую и воспроизводимую конфигурацию уровня и персонажа.

---

## 2. Границы DATA-02

### 2.1. Входит в DATA-02

- описание уровня;
- связь уровня с `StoryVersion`;
- связь уровня с персонажем;
- описание персонажа;
- публичные и скрытые поля персонажа;
- reusable PAEI profiles P/A/E/I;
- character-specific PAEI mix;
- механическая конфигурация уровня;
- ссылка на difficulty profile;
- валидация сущностей;
- DB constraints;
- Pydantic schemas;
- SQLAlchemy models;
- Alembic migration;
- repository/service слой;
- тесты модели.

### 2.2. Не входит в DATA-02

Следующие объекты принадлежат другим задачам:

| Область | Ответственная задача |
|---|---|
| `Story` | DATA-01 |
| `StoryVersion` | DATA-01 |
| `Session` | DATA-03 |
| `GameState` | DATA-03 |
| `Turn` | DATA-04 |
| `Result` | DATA-04 |
| базовая таблица scoring | Scoring / Game State |
| настройки Easy/Normal/Hard | `docs/level_difficulty_design.md` |
| конкретная реакция NPC | Reaction Model |
| генерация ответа NPC | AI Opponent |

DATA-02 может ссылаться на эти объекты, но не должен дублировать их хранилище.

---

## 3. Базовые принципы

1. Backend является источником истины для доменных данных.
2. UI не хранит PAEI, difficulty или скрытые условия локально как источник истины.
3. Опубликованный контент не редактируется «на месте».
4. `Level` принадлежит конкретному `StoryVersion`.
5. `Character` может переиспользоваться в нескольких уровнях.
6. `PAEIProfile` является версионируемым шаблоном.
7. Character-specific PAEI mix хранится отдельно от шаблона PAEI.
8. PAEI не хранит trust, tension, BATNA, эмоции или текущий Game State.
9. Числовые настройки сложности не копируются в `Level`.
10. Все JSON-конфигурации валидируются схемой до публикации.
11. Публичный DTO никогда не возвращает скрытые поля.
12. Идентификаторы и version identifiers имеют стабильный формат.
13. Сущности можно создать в `draft`, но запуск игры разрешается только с опубликованными валидными зависимостями.

---

# 4. Доменная модель

## 4.1. Связи

```text
Story
  │
  └── 1:N StoryVersion
           │
           └── 1:N Level
                    │
                    ├── N:1 Character
                    │       │
                    │       └── N:1 PAEIProfile
                    │
                    └── difficulty_profile
```

Для MVP один `Level` имеет одного `primary_character`.

Если позже потребуется несколько NPC на одном уровне, вводится:

```text
Level N:M Character
       via LevelCharacter
```

Эта возможность не требуется для DATA-02 MVP.

---

# 5. Level

## 5.1. Назначение

`Level` — отдельный игровой сценарный уровень внутри конкретной `StoryVersion`.

Он определяет:

- что увидит игрок;
- какой персонаж участвует в переговорах;
- публичную структуру уровня;
- скрытые игровые ограничения;
- механическую конфигурацию;
- ключ используемого профиля сложности.

`Level` не содержит динамическое состояние текущей игры.

---

## 5.2. Поля Level

| Поле | Тип | Null | Public/Hidden | Назначение |
|---|---|---|---|---|
| `id` | UUID | no | public-id | PK |
| `story_version_id` | UUID | no | public | ссылка на DATA-01 |
| `slug` | varchar(80) | no | public | стабильный ключ |
| `title` | varchar(160) | no | public | название |
| `short_description` | text | no | public | описание |
| `description` | text | yes | public | расширенное описание |
| `display_order` | integer | no | public | порядок отображения |
| `status` | enum | no | internal/public | `draft/published/archived` |
| `primary_character_id` | UUID | no | hidden/internal | NPC уровня |
| `difficulty_profile` | enum | no | player-visible | `training/easy/normal/hard` |
| `difficulty_version` | varchar(20) | no | internal | версия difficulty config |
| `mechanics_config` | JSONB | no | hidden | условия и настройки уровня |
| `public_config` | JSONB | no | public | безопасные UI-параметры |
| `version` | integer | no | internal | ревизия записи |
| `created_at` | timestamptz | no | internal | дата создания |
| `updated_at` | timestamptz | no | internal | дата изменения |

---

## 5.3. Ограничения Level

```text
display_order >= 0

slug matches:
^[a-z0-9]+(?:-[a-z0-9]+)*$

difficulty_profile ∈ {
    training,
    easy,
    normal,
    hard
}

status ∈ {
    draft,
    published,
    archived
}
```

Дополнительные DB constraints:

```text
UNIQUE(story_version_id, slug)

UNIQUE(story_version_id, display_order)
```

`primary_character_id` должен ссылаться на активного персонажа.

Для `published`:

```text
story_version.status == published
character.status == active
character.paei_profile_id IS NOT NULL
difficulty_version IS NOT NULL
mechanics_config IS valid
```

---

# 6. Level mechanics_config

## 6.1. Принцип

`mechanics_config` содержит только правила конкретного уровня.

Численные параметры сложности туда не копируются.

Пример:

```yaml
goal:
  threshold: 80
  mandatory_conditions:
    - confirm_deadline
    - agree_next_step

critical_errors:
  - DEADLINE_LIE
  - CONFIDENTIALITY_BREACH
  - AGGRESSIVE_ESCALATION

allowed_hint_types:
  - direction
  - context
  - communication
  - mistake
  - strategy

recovery:
  enabled: true

optional_goals:
  - id: preserve_relationship
    bonus: 5
```

Если `goal.threshold` должен зависеть от сложности, он не хранится здесь как число, а заменяется ссылкой:

```yaml
goal:
  threshold_ref: difficulty.goal_threshold
```

Таким образом:

```text
Level mechanics
       +
Difficulty config
       ↓
Effective Level Config
```

---

# 7. Публичная модель Level

Публичный ответ:

```json
{
  "id": "uuid",
  "slug": "deadline-negotiation",
  "title": "Срыв сроков",
  "short_description": "Необходимо пересогласовать сроки проекта.",
  "description": "Переговоры с руководителем проекта.",
  "display_order": 1,
  "status": "published",
  "difficulty_profile": "normal",
  "character": {
    "id": "uuid",
    "name": "Алексей",
    "role": "Руководитель проекта"
  }
}
```

Никогда не отдаётся:

```text
mechanics_config
critical_error_codes
secret_conditions
character.paei_weights
character.internal_notes
character.hidden_config
```

---

# 8. Character

## 8.1. Назначение

`Character` — переиспользуемый NPC, участвующий в одном или нескольких уровнях.

Модель разделяется на:

```text
Character Public
+
Character Hidden
+
PAEI configuration
```

PAEI задаёт фильтр восприятия и признаки, значимые для NPC; он не определяет эмоции, доверие, BATNA или конкретную реакцию. Это соответствует методологии проекта.

---

## 8.2. Публичные поля Character

| Поле | Тип | Null | Назначение |
|---|---|---|---|
| `id` | UUID | no | PK |
| `slug` | varchar(80) | no | стабильный ключ |
| `name` | varchar(120) | no | отображаемое имя |
| `role` | varchar(160) | no | роль персонажа |
| `short_bio` | text | yes | краткая биография |
| `avatar_url` | varchar(500) | yes | изображение |
| `status` | enum | no | `draft/active/archived` |
| `metadata` | JSONB | no | разрешённые UI-метаданные |

---

## 8.3. Скрытые поля Character

| Поле | Тип | Null | Назначение |
|---|---|---|---|
| `internal_notes` | text | yes | заметки для команды |
| `paei_profile_id` | UUID | no | шаблон PAEI |
| `paei_weights` | JSONB | no | character-specific PAEI mix |
| `paei_config` | JSONB | no | дополнительные overrides |
| `hidden_config` | JSONB | no | внутренние параметры |
| `content_tags` | JSONB | no | технические теги |

Не следует помещать сюда:

```text
trust
tension
BATNA
current_emotion
current_aggression
current_state
session-specific data
```

Эти значения относятся к другим слоям.

---

# 9. Character-specific PAEI mix

Для MVP вводится четырёхкомпонентный вектор:

```text
P
A
E
I
```

Каждая компонента:

```text
0..100
```

Сумма:

```text
P + A + E + I = 100
```

Пример:

```json
{
  "P": 55,
  "A": 25,
  "E": 10,
  "I": 10
}
```

Это означает, что персонаж преимущественно P с заметной A-составляющей.

PAEI mix не равен `communication_fit`.

---

# 10. PAEIProfile

## 10.1. Назначение

`PAEIProfile` — версионируемый методологический шаблон отдельной функции:

```text
P — Producing
A — Administrating
E — Entrepreneurial
I — Integrating
```

Профиль хранит:

- формализованные признаки;
- их допустимые значения;
- вес признака;
- описание того, что функция замечает;
- правила вычисления fit.

---

## 10.2. Поля PAEIProfile

| Поле | Тип | Null | Назначение |
|---|---|---|---|
| `id` | UUID | no | PK |
| `code` | enum | no | `P/A/E/I` |
| `version` | varchar(20) | no | версия методологии |
| `name` | varchar(120) | no | название |
| `description` | text | no | назначение |
| `core_question` | text | no | основной вопрос профиля |
| `feature_schema` | JSONB | no | признаки |
| `feature_weights` | JSONB | no | веса признаков |
| `positive_patterns` | JSONB | no | признаки высокого fit |
| `negative_patterns` | JSONB | no | признаки mismatch |
| `status` | enum | no | `draft/published/archived` |
| `created_at` | timestamptz | no | дата создания |
| `updated_at` | timestamptz | no | дата изменения |

Constraint:

```text
UNIQUE(code, version)
```

Для активной версии:

```text
at most one published P
at most one published A
at most one published E
at most one published I
```

---

# 11. PAEI feature schemas

Ниже используются признаки из методологии проекта.

## P

```yaml
result_clarity:
deadline_clarity:
actionability:
ownership:
solution_orientation:
alternative_present:
result_impact_explained:
priority_clarity:
specificity:
relevance:
early_warning:
commitment:
practical_evidence:
conversation_progress:
conflict_productivity:
```

Для P ключевыми являются результат, действие, конкретика, срок и исполнение.

## A

```yaml
process_clarity:
sequence_clarity:
evidence_quality:
risk_identification:
risk_mitigation:
role_clarity:
criteria_clarity:
documentation_present:
consistency:
constraint_awareness:
change_impact_explained:
contingency_present:
deadline_feasibility:
information_completeness:
process_compliance:
```

Для A ключевыми являются порядок, доказательность, точность, риски, критерии и контроль процесса.

## E

```yaml
optionality:
alternative_present:
future_value:
scalability:
assumption_challenge:
constraint_reasoning:
experimentability:
risk_upside_balance:
change_value_explained:
scenario_thinking:
strategic_horizon:
novelty_relevance:
learning_potential:
decision_reversibility:
opportunity_preservation:
```

Для E ключевыми являются варианты, будущее, возможности, экспериментируемость и ценность изменений.

## I

```yaml
interest_acknowledgement:
common_ground:
perspective_taking:
inclusive_language:
respectfulness:
face_preservation:
buy_in_check:
stakeholder_awareness:
fairness_balance:
shared_ownership:
conflict_clarity:
listening_evidence:
relationship_impact:
unilateral_pressure:
exclusion_risk:
```

Для I ключевыми являются интересы сторон, общее основание, слушание, уважение, поддержка решения и совместная ответственность.

Эти признаки являются наблюдаемыми характеристиками сообщения, а не скрытой оценкой личности пользователя.

---

# 12. Значения feature_schema

Допустимые типы признаков:

```text
boolean
enum
ordinal
numeric
```

Пример:

```json
{
  "deadline_clarity": {
    "type": "enum",
    "values": ["none", "vague", "specific"],
    "default": "none"
  }
}
```

Пример ordinal:

```json
{
  "actionability": {
    "type": "enum",
    "values": ["low", "medium", "high"],
    "default": "medium"
  }
}
```

Профиль должен быть самодостаточным: Evaluator может получить его схему без чтения UI-кода.

---

# 13. Расчёт PAEI

## 13.1. Communication fit

Для каждой функции:

```text
fit_X ∈ [-2, +2]
```

где:

```text
X ∈ {P, A, E, I}
```

Интерпретация:

| Значение | Смысл |
|---:|---|
| +2 | сильное соответствие |
| +1 | соответствие |
| 0 | нейтрально |
| −1 | слабое несоответствие |
| −2 | сильное несоответствие |

## 13.2. Взвешенный fit персонажа

```text
weighted_fit =
    P_weight * fit_P
  + A_weight * fit_A
  + E_weight * fit_E
  + I_weight * fit_I
```

где:

```text
P_weight + A_weight + E_weight + I_weight = 1
```

`paei_weights` character:

```json
{
  "P": 55,
  "A": 25,
  "E": 10,
  "I": 10
}
```

нормализуются:

```text
P_weight = 0.55
A_weight = 0.25
E_weight = 0.10
I_weight = 0.10
```

Важное правило:

```text
weighted_fit
    ≠
contact
    ≠
trust
    ≠
goal_result
```

---

# 14. Связь Character → PAEIProfile

Character обязан иметь:

```text
paei_profile_id
```

Для MVP `paei_profile_id` означает основной PAEI-шаблон персонажа.

Дополнительно:

```text
paei_weights
```

задаёт индивидуальную комбинацию функций.

Пример:

```text
profile = P
weights = {P: 55, A: 25, E: 10, I: 10}
```

Это означает:

- P используется как основной шаблон;
- A/E/I остаются частью общей модели персонажа;
- реакционная модель получает weighted relevance всех четырёх функций.

---

# 15. Валидация Character

## 15.1. Slug

```text
^[a-z0-9]+(?:-[a-z0-9]+)*$
```

## 15.2. PAEI weights

Все значения:

```text
0 <= weight <= 100
```

Сумма:

```text
sum(weights) == 100
```

Все ключи обязательны:

```text
P, A, E, I
```

Нельзя:

```json
{
  "P": 40,
  "A": 40,
  "E": 40,
  "I": -20
}
```

или:

```json
{
  "P": 50,
  "A": 20,
  "E": 20
}
```

---

# 16. Связь Level → StoryVersion

`Level.story_version_id` является обязательным FK.

Уровень не существует самостоятельно как публикуемый контент.

Публикация:

```text
Draft StoryVersion
    ↓
validate StoryVersion
    ↓
validate Levels
    ↓
validate Characters
    ↓
validate PAEIProfile versions
    ↓
publish StoryVersion
```

После публикации:

```text
published StoryVersion
    ↓
Level immutable
```

Изменение опубликованного контента должно создавать новую `StoryVersion` в рамках DATA-01.

---

# 17. Состав effective configuration

Перед запуском игры система собирает:

```text
StoryVersion
+
Level
+
Character
+
PAEIProfile
+
DifficultyConfig
```

Результат:

```json
{
  "scenario_version": "1.2",
  "level_id": "uuid",
  "character_id": "uuid",
  "paei_profile": {
    "version": "1.0",
    "code": "P"
  },
  "paei_weights": {
    "P": 55,
    "A": 25,
    "E": 10,
    "I": 10
  },
  "difficulty_profile": "normal",
  "difficulty_version": "1.0"
}
```

Этот effective config передаётся дальше в DATA-03 / Game Engine.

---

# 18. Pydantic-модели

Рекомендуемая структура:

```text
backend/
└── app/
    ├── models/
    │   ├── level.py
    │   ├── character.py
    │   └── paei_profile.py
    ├── schemas/
    │   ├── level.py
    │   ├── character.py
    │   └── paei_profile.py
    ├── repositories/
    │   ├── level.py
    │   ├── character.py
    │   └── paei_profile.py
    ├── services/
    │   └── content_validation.py
    └── api/
        └── routes/
            ├── levels.py
            ├── characters.py
            └── paei_profiles.py
```

---

## 18.1. Pydantic Level

```python
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class LevelStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class DifficultyProfile(str, Enum):
    TRAINING = "training"
    EASY = "easy"
    NORMAL = "normal"
    HARD = "hard"


class LevelPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    title: str
    short_description: str
    description: str | None
    display_order: int = Field(ge=0)
    status: LevelStatus
    difficulty_profile: DifficultyProfile


class LevelCreate(LevelPublic):
    story_version_id: UUID
    primary_character_id: UUID
    difficulty_version: str = Field(min_length=1, max_length=20)
    public_config: dict
    mechanics_config: dict
```

---

## 18.2. Pydantic Character

```python
from pydantic import BaseModel, Field, model_validator


class PAEIWeights(BaseModel):
    P: int = Field(ge=0, le=100)
    A: int = Field(ge=0, le=100)
    E: int = Field(ge=0, le=100)
    I: int = Field(ge=0, le=100)

    @model_validator(mode="after")
    def validate_sum(self):
        if self.P + self.A + self.E + self.I != 100:
            raise ValueError("PAEI weights must sum to 100")
        return self


class CharacterPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    name: str
    role: str
    short_bio: str | None
    avatar_url: str | None
    status: str
    metadata: dict


class CharacterCreate(CharacterPublic):
    paei_profile_id: UUID
    paei_weights: PAEIWeights
    paei_config: dict = {}
    hidden_config: dict = {}
    internal_notes: str | None = None
```

---

## 18.3. Pydantic PAEIProfile

```python
class PAEIFunction(str, Enum):
    P = "P"
    A = "A"
    E = "E"
    I = "I"


class PAEIProfileCreate(BaseModel):
    code: PAEIFunction
    version: str = Field(min_length=1, max_length=20)
    name: str
    description: str
    core_question: str
    feature_schema: dict
    feature_weights: dict
    positive_patterns: list[dict]
    negative_patterns: list[dict]
```

---

# 19. SQLAlchemy-модели

## 19.1. Level

```python
class Level(Base):
    __tablename__ = "levels"

    id = mapped_column(UUID(as_uuid=True), primary_key=True)
    story_version_id = mapped_column(
        ForeignKey("story_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )

    slug = mapped_column(String(80), nullable=False)
    title = mapped_column(String(160), nullable=False)
    short_description = mapped_column(Text, nullable=False)
    description = mapped_column(Text)
    display_order = mapped_column(Integer, nullable=False)

    status = mapped_column(
        Enum(LevelStatus),
        nullable=False,
        default=LevelStatus.DRAFT,
    )

    primary_character_id = mapped_column(
        ForeignKey("characters.id", ondelete="RESTRICT"),
        nullable=False,
    )

    difficulty_profile = mapped_column(
        String(32),
        nullable=False,
    )

    difficulty_version = mapped_column(
        String(20),
        nullable=False,
    )

    public_config = mapped_column(JSONB, nullable=False, default=dict)
    mechanics_config = mapped_column(JSONB, nullable=False, default=dict)

    version = mapped_column(Integer, nullable=False, default=1)

    created_at = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "story_version_id",
            "slug",
            name="uq_levels_story_version_slug",
        ),
        UniqueConstraint(
            "story_version_id",
            "display_order",
            name="uq_levels_story_version_order",
        ),
    )
```

## 19.2. Character

```python
class Character(Base):
    __tablename__ = "characters"

    id = mapped_column(UUID(as_uuid=True), primary_key=True)
    slug = mapped_column(String(80), nullable=False, unique=True)
    name = mapped_column(String(120), nullable=False)
    role = mapped_column(String(160), nullable=False)
    short_bio = mapped_column(Text)
    avatar_url = mapped_column(String(500))

    status = mapped_column(
        Enum(CharacterStatus),
        nullable=False,
        default=CharacterStatus.DRAFT,
    )

    metadata_ = mapped_column("metadata", JSONB, nullable=False, default=dict)

    internal_notes = mapped_column(Text)

    paei_profile_id = mapped_column(
        ForeignKey("paei_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )

    paei_weights = mapped_column(JSONB, nullable=False)

    paei_config = mapped_column(JSONB, nullable=False, default=dict)
    hidden_config = mapped_column(JSONB, nullable=False, default=dict)
    content_tags = mapped_column(JSONB, nullable=False, default=dict)
```

## 19.3. PAEIProfile

```python
class PAEIProfile(Base):
    __tablename__ = "paei_profiles"

    id = mapped_column(UUID(as_uuid=True), primary_key=True)

    code = mapped_column(
        Enum(PAEIFunction),
        nullable=False,
    )

    version = mapped_column(
        String(20),
        nullable=False,
    )

    name = mapped_column(String(120), nullable=False)
    description = mapped_column(Text, nullable=False)
    core_question = mapped_column(Text, nullable=False)

    feature_schema = mapped_column(JSONB, nullable=False)
    feature_weights = mapped_column(JSONB, nullable=False)

    positive_patterns = mapped_column(JSONB, nullable=False)
    negative_patterns = mapped_column(JSONB, nullable=False)

    status = mapped_column(
        Enum(PAEIProfileStatus),
        nullable=False,
        default=PAEIProfileStatus.DRAFT,
    )

    created_at = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "code",
            "version",
            name="uq_paei_profiles_code_version",
        ),
    )
```

---

# 20. DB constraints и индексы

Обязательные индексы:

```text
levels(story_version_id, display_order)
levels(story_version_id, status)
levels(primary_character_id)

characters(status)
characters(paei_profile_id)

paei_profiles(code, status)
paei_profiles(code, version)
```

Обязательные FK:

```text
levels.story_version_id
    → story_versions.id

levels.primary_character_id
    → characters.id

characters.paei_profile_id
    → paei_profiles.id
```

Удаление опубликованного объекта каскадом запрещено.

Рекомендуемый режим:

```text
ON DELETE RESTRICT
```

---

# 21. Валидация публикации

Публикация Level запрещается, если хотя бы одно условие не выполнено:

```text
StoryVersion exists
Character exists
Character.status == active
PAEIProfile exists
PAEIProfile.status == published
PAEIProfile version is valid
PAEI weights sum to 100
difficulty_profile is valid
difficulty_version exists
mechanics_config passes schema
public_config passes schema
slug is unique
display_order is unique inside StoryVersion
```

Публикация Character запрещается, если:

```text
PAEIProfile.status != published
```

Публикация PAEIProfile запрещается, если:

```text
feature_schema is invalid
feature_weights is invalid
positive_patterns are invalid
negative_patterns are invalid
```

---

# 22. API

Для DATA-02 достаточно read API и административного CRUD.

## Public

```http
GET /api/v1/levels
GET /api/v1/levels/{level_id}
GET /api/v1/characters/{character_id}
GET /api/v1/paei-profiles/{code}
```

Public API никогда не возвращает hidden-поля.

## Admin

```http
POST   /api/v1/admin/levels
PATCH  /api/v1/admin/levels/{level_id}
POST   /api/v1/admin/characters
PATCH  /api/v1/admin/characters/{character_id}
POST   /api/v1/admin/paei-profiles
PATCH  /api/v1/admin/paei-profiles/{profile_id}
```

Публикация отдельным действием:

```http
POST /api/v1/admin/levels/{level_id}/publish
POST /api/v1/admin/characters/{character_id}/publish
POST /api/v1/admin/paei-profiles/{profile_id}/publish
```

Это позволяет не смешивать draft/update и publish.

---

# 23. Repository / Service

Предлагается разделить:

```text
Repository
    ↓
работа с БД

Service
    ↓
валидация бизнес-правил

API
    ↓
Pydantic DTO
```

Примеры сервисов:

```text
LevelService
CharacterService
PAEIProfileService
ContentValidationService
EffectiveConfigService
```

`EffectiveConfigService` собирает:

```text
StoryVersion
+
Level
+
Character
+
PAEIProfile
+
difficulty config
```

и возвращает immutable runtime config.

---

# 24. Alembic migration

DATA-02 требует миграцию:

```text
create paei_profiles
create characters
create levels
add indexes
add foreign keys
add uniqueness constraints
```

Порядок:

```text
paei_profiles
      ↓
characters
      ↓
levels
```

Перед применением миграции должен существовать `story_versions`.

Поэтому DATA-02 зависит от DATA-01.

---

# 25. Seed-данные PAEI

MVP обязан иметь четыре опубликованных профиля:

```text
P v1.0
A v1.0
E v1.0
I v1.0
```

Источник семантики:

- P — результат, действие, конкретика, срок, исполнение;
- A — порядок, последовательность, данные, критерии, риски;
- E — варианты, будущее, возможности, эксперимент;
- I — интересы сторон, совместность, слушание, уважение, buy-in.

Семантика этих профилей не должна быть сведена к стереотипам вроде:

```text
P = грубый
A = бюрократ
E = хаотичный
I = мягкий
```

Крайние дисфункциональные проявления в методологии отдельно оговорены и не должны автоматически переноситься на профиль.

---

# 26. Пример seed P

```json
{
  "code": "P",
  "version": "1.0",
  "name": "Producing",
  "core_question": "Что в итоге будет сделано?",
  "feature_schema": {
    "result_clarity": {
      "type": "enum",
      "values": ["none", "partial", "clear"]
    },
    "deadline_clarity": {
      "type": "enum",
      "values": ["none", "vague", "specific"]
    },
    "actionability": {
      "type": "enum",
      "values": ["low", "medium", "high"]
    }
  },
  "status": "published"
}
```

Аналогично создаются A/E/I из проектных методологических файлов.

---

# 27. Тестирование

## 27.1. Level

Минимальные unit/integration tests:

```text
create valid level
reject invalid slug
reject negative display_order
reject duplicate slug in StoryVersion
reject duplicate display_order in StoryVersion
reject invalid difficulty_profile
reject missing Character
reject missing StoryVersion
reject publish without valid PAEI
reject invalid mechanics_config
public DTO hides hidden fields
```

## 27.2. Character

```text
create character
reject invalid slug
reject missing PAEIProfile
reject invalid PAEI weights
reject weights sum != 100
reject negative weights
reject weights > 100
public DTO hides paei_weights
public DTO hides internal_notes
public DTO hides hidden_config
```

## 27.3. PAEIProfile

```text
create P
create A
create E
create I

reject duplicate code/version
reject invalid feature schema
reject invalid feature values
reject missing core_question
publish valid profile
reject publish invalid profile
```

## 27.4. Publication chain

Главный интеграционный тест:

```text
create StoryVersion draft
create PAEI profile
create Character
create Level
validate all
publish PAEI
publish Character
publish Level
```

Отдельно:

```text
published StoryVersion
    + published Level
    + active Character
    + published PAEI
```

должен успешно формировать effective runtime config.

---

# 28. Acceptance Criteria DATA-02

Задача считается готовой, когда:

### Level

- существует SQLAlchemy model;
- существует Pydantic schema;
- есть FK на `StoryVersion`;
- есть `primary_character`;
- есть difficulty profile/version;
- есть mechanics config;
- работает draft/published/archived;
- есть constraints и индексы.

### Character

- существует SQLAlchemy model;
- существует Pydantic schema;
- public/hidden поля разделены;
- есть обязательный PAEIProfile;
- PAEI weights проходят валидацию;
- публичный API не выдаёт hidden fields.

### PAEI

- существуют P/A/E/I;
- профили версионируются;
- существует feature schema;
- существуют positive/negative patterns;
- активная версия уникальна для каждого кода;
- profile можно использовать из Character.

### Интеграция

- Level связан с StoryVersion;
- Level связан с валидным Character;
- Character связан с валидным PAEIProfile;
- effective config собирается без чтения UI;
- difficulty settings не дублируются в БД как Easy/Normal/Hard numbers.

---

# 29. Рекомендуемые файлы PR

```text
backend/app/models/level.py
backend/app/models/character.py
backend/app/models/paei_profile.py

backend/app/schemas/level.py
backend/app/schemas/character.py
backend/app/schemas/paei_profile.py

backend/app/repositories/level.py
backend/app/repositories/character.py
backend/app/repositories/paei_profile.py

backend/app/services/content_validation.py
backend/app/services/effective_config.py

backend/app/api/routes/levels.py
backend/app/api/routes/characters.py
backend/app/api/routes/paei_profiles.py

backend/alembic/versions/<revision>_data_02.py

backend/tests/models/test_level.py
backend/tests/models/test_character.py
backend/tests/models/test_paei_profile.py
backend/tests/integration/test_data_02_publication.py

docs/database_architecture.md
docs/api_contracts.md
```

---

# 30. Зависимости

```text
METH-02
   ↓
METH-05
   ↓
DATA-01
   ↓
DATA-02
   ↓
DATA-03
   ↓
DATA-04
```

Прямая зависимость DATA-02 от DATA-01 необходима, потому что Level принадлежит StoryVersion.

DATA-03 использует DATA-02 для фиксации:

```text
level_id
character_id
paei_profile_id
difficulty_profile
difficulty_version
```

DATA-04 использует DATA-03 и дальше работает с Game State и Turn.

---

# 31. Важные архитектурные решения

### Решение 1. PAEI — справочник, а не состояние

`PAEIProfile` нельзя изменять во время игровой сессии.

Меняется только:

```text
communication_fit
weighted_fit
```

в runtime-истории хода.

### Решение 2. Character переиспользуемый

Один Character может использоваться в нескольких уровнях.

При этом его immutable content version должен быть однозначно определён через используемую StoryVersion.

### Решение 3. Difficulty не копируется

Level хранит:

```text
difficulty_profile
difficulty_version
```

но не хранит:

```text
hint_limit = 3
turn_limit = 12
critical_error_limit = 3
...
```

Источник этих значений:

```text
docs/level_difficulty_design.md
```

### Решение 4. Публичный API отделён от внутренней модели

ORM-модель нельзя сериализовать напрямую в public response.

Всегда используется:

```text
ORM → Public Pydantic DTO
```

### Решение 5. Draft и Published — разные состояния одного контента

Draft можно менять.

Published content для конкретной `StoryVersion` считается immutable.

---

# 32. Что сознательно добавлено в проект по решению команды

Следующие решения не были детально заданы исходным issue и выбраны для того, чтобы модель была реализуема без дополнительных блокеров:

| Решение | Почему |
|---|---|
| UUID для PK | безопасные внешние идентификаторы |
| JSONB для feature/config | PAEI и mechanics расширяются без постоянных миграций |
| PAEI weights 0..100 | простой и проверяемый character mix |
| сумма PAEI = 100 | однозначная нормализация |
| versioned PAEI profiles | воспроизводимость старых сценариев |
| primary_character | минимальная MVP-модель без N:M |
| separate publish endpoint | нельзя случайно опубликовать draft |
| `difficulty_version` | воспроизводимость сессий |
| `ON DELETE RESTRICT` | защита исторических связей |
| public/private DTO | защита скрытой игровой логики |

---

# 33. Финальный runtime-поток

```text
GET/START SCENARIO
        ↓
StoryVersion
        ↓
Level
        ↓
Character
        ↓
PAEIProfile
        ↓
DifficultyConfig
        ↓
EffectiveConfig
        ↓
Session / Game State
        ↓
Evaluator
        ↓
P/A/E/I fit
        ↓
Game Engine
```

При этом:

```text
PAEIProfile
    └── определяет:
        что персонажу важно
        что он замечает
        какие признаки сообщения релевантны

Game Engine
    └── определяет:
        изменение contact
        изменение resistance
        изменение progress
        завершение

Reaction Model
    └── определяет:
        реакцию NPC

AI Opponent
    └── формулирует:
        текст ответа NPC
```

Такое разделение сохраняет границы, заданные в методологии PAEI.

---

# 34. Статус

| Область | Статус |
|---|---|
| Level model | `DRAFT` |
| Character model | `DRAFT` |
| PAEIProfile | `DRAFT` |
| Public/hidden separation | `DRAFT` |
| Validation | `DRAFT` |
| DB constraints | `DRAFT` |
| Pydantic | `DRAFT` |
| SQLAlchemy | `DRAFT` |
| API | `DRAFT` |
| Alembic | `DRAFT` |
| Seed P/A/E/I | `DRAFT` |
| Tests | `DRAFT` |
| Integration with DATA-01 | `DRAFT` |
| Integration with DATA-03 | `DRAFT` |

---

# 35. Связанные документы

```text
docs/database_architecture.md
docs/content_and_admin_design.md
docs/scoring_and_game_state.md
docs/level_difficulty_design.md
```

Источник методологической части:

```text
product_and_game_design.md
```

