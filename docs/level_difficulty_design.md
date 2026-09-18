# Level Difficulty Design

## 1. Назначение

Документ является единственным источником правды для параметров, режимов и настройки уровней сложности проекта **«Арена переговоров»**.

Документ определяет:

- уровни `Easy`, `Normal`, `Hard`;
- тренировочную конфигурацию;
- стартовые значения;
- лимиты;
- пороги;
- интенсивность негативных последствий;
- сложность восстановления контакта;
- диапазоны допустимых значений;
- правила тюнинга;
- версионирование конфигурации;
- требования к тестированию.

`Scoring and Game State` не должен дублировать численные значения уровней сложности. Он получает их из активной versioned-конфигурации.

---

## 2. Принципы настройки

1. Сложность изменяет **параметры игры**, а не базовую формулу scoring.
2. Одинаковое действие должно классифицироваться одинаково во всех режимах; меняется сила последствий и доступные ресурсы.
3. Переход между уровнями должен быть предсказуемым и воспроизводимым.
4. Все значения должны быть ограничены допустимым диапазоном.
5. Каждое изменение параметра должно быть зафиксировано в версии конфигурации.
6. UI не хранит правила сложности.
7. AI/NPC не должен самовольно менять параметры сложности.
8. Difficulty profile выбирается один раз в начале сценария и не меняется до завершения текущей игры.
9. Внутри одного сценария нельзя скрыто повышать или понижать сложность.
10. Баланс сложности проверяется через набор одинаковых контрольных сценариев.

---

## 3. Модель режимов

### 3.1. Training

`training` — отдельный игровой режим для обучения. Он не является уровнем сложности.

Тренировочная конфигурация:

```yaml
difficulty_profile: training
hint_limit: 5
turn_limit: 15
critical_error_limit: 4
initial_contact: 80
initial_resistance: 20
goal_threshold: 80
recovery_attempt_limit: 1
negative_action_strength: 4
recovery_difficulty: 0
```

Особенности:

- пользователь может перезапускать сценарий;
- подсказок больше, чем в обычной игре;
- последствия ошибок мягче;
- уровень PAEI и базовая таблица scoring не меняются;
- результаты training не используются для сравнения с результатами Scenario.

---

### 3.2. Scenario / Easy

Цель — дать пользователю возможность познакомиться с полным циклом переговоров без жёсткого дефицита ресурсов.

```yaml
difficulty_profile: easy
initial_contact: 80
initial_resistance: 20
goal_threshold: 80
hint_limit: 5
turn_limit: 15
critical_error_limit: 4
negative_action_strength: 4
recovery_difficulty: 0
recovery_attempt_limit: 1
contact_loss_threshold: 20
```

Recovery:

- достаточно одного корректирующего действия;
- `weighted_paei_fit >= 0`;
- после успеха: `contact +15`, `resistance -10`, `progress +5`.

---

### 3.3. Scenario / Normal

Основной баланс для MVP.

```yaml
difficulty_profile: normal
initial_contact: 70
initial_resistance: 40
goal_threshold: 80
hint_limit: 3
turn_limit: 12
critical_error_limit: 3
negative_action_strength: 6
recovery_difficulty: 1
recovery_attempt_limit: 1
contact_loss_threshold: 20
```

Recovery:

- требуется корректирующее действие с положительным результатом;
- `weighted_paei_fit >= 0`;
- после успеха: `contact +15`, `resistance -10`, `progress +5`.

---

### 3.4. Scenario / Hard

Цель — повышенное давление на пользователя за счёт меньшего запаса времени, меньшего количества подсказок, меньшего числа допустимых критических ошибок и более сильных негативных последствий.

```yaml
difficulty_profile: hard
initial_contact: 60
initial_resistance: 60
goal_threshold: 80
hint_limit: 2
turn_limit: 10
critical_error_limit: 2
negative_action_strength: 8
recovery_difficulty: 2
recovery_attempt_limit: 1
contact_loss_threshold: 20
```

Recovery:

- требуется корректирующее действие;
- `conversation_progress = forward`;
- `actionability = high`;
- `weighted_paei_fit >= +1`;
- после успеха: `contact +15`, `resistance -10`, `progress +5`.

---

## 4. Мастер-таблица параметров

| Параметр | Диапазон MVP | Training | Easy | Normal | Hard |
|---|---:|---:|---:|---:|---:|
| `initial_contact` | 40–90 | 80 | 80 | 70 | 60 |
| `initial_resistance` | 10–70 | 20 | 20 | 40 | 60 |
| `contact_loss_threshold` | 10–30 | 20 | 20 | 20 | 20 |
| `goal_threshold` | 70–90 | 80 | 80 | 80 | 80 |
| `hint_limit` | 0–5 | 5 | 5 | 3 | 2 |
| `turn_limit` | 8–15 | 15 | 15 | 12 | 10 |
| `critical_error_limit` | 2–5 | 4 | 4 | 3 | 2 |
| `negative_action_strength` | 2–10 | 4 | 4 | 6 | 8 |
| `recovery_difficulty` | 0–2 | 0 | 0 | 1 | 2 |
| `recovery_attempt_limit` | 1 | 1 | 1 | 1 | 1 |

---

## 5. Что именно меняет сложность

### 5.1. Initial contact

`initial_contact` задаёт запас контакта в начале переговоров.

Чем ниже значение, тем меньше ошибок пользователь может допустить до перехода в `contact_lost`.

```text
contact_start = initial_contact
```

Изменяет только начальное состояние.

---

### 5.2. Initial resistance

`initial_resistance` задаёт стартовое сопротивление достижению цели.

```text
resistance_start = initial_resistance
```

Высокое значение означает, что пользователю требуется больше качественных действий для достижения результата.

---

### 5.3. Contact loss threshold

```text
contact <= contact_loss_threshold
```

Переход в `contact_lost` не зависит от формулы итогового результата.

Для MVP значение одинаково для всех режимов: `20`.

Причина фиксированного порога: сравнение поведения между режимами должно происходить за счёт стартового запаса и последствий действий, а не за счёт скрытого изменения определения потери контакта.

---

### 5.4. Goal threshold

```text
progress >= goal_threshold
```

MVP использует `80` для всех режимов.

Сложность не должна искусственно поднимать требуемый процент цели; иначе пользователю будет сложнее понять, какое именно поведение изменило результат.

---

### 5.5. Hint limit

Количество доступных подсказок:

```text
Training = 5
Easy = 5
Normal = 3
Hard = 2
```

За каждую использованную подсказку:

```text
negotiation_quality -= 3
```

Подсказки не меняют `goal_result` и `paei_result` напрямую.

---

### 5.6. Turn limit

Ограничивает число обычных ходов:

```text
Training = 15
Easy = 15
Normal = 12
Hard = 10
```

Последний допустимый ход может привести к `success`. Поэтому проверка `success_condition` должна идти раньше `turn_limit` согласно правилам terminal priority.

---

### 5.7. Critical error limit

Количество критических ошибок до поражения:

```text
Training = 4
Easy = 4
Normal = 3
Hard = 2
```

При:

```text
critical_errors >= critical_error_limit
```

игра переходит в `failure`, если более высокий приоритет не имеет `cancel_action`.

---

### 5.8. Negative action strength

`negative_action_strength` задаёт интенсивность негативных последствий.

Базовое значение Normal:

```text
S_normal = 6
```

Режимы:

```text
Easy = 4
Normal = 6
Hard = 8
```

Для негативных действий используется коэффициент:

```text
negative_multiplier = negative_action_strength / 6
```

Пример базовой негативной реакции Normal:

```text
contact: -6
resistance: +6
quality: -7
progress: 0
```

При другом уровне сложности интенсивность масштабируется коэффициентом, после чего применяется `clamp`.

Рекомендуемая реализация:

```text
contact_delta' =
    round(-6 * negative_multiplier)

resistance_delta' =
    round(+6 * negative_multiplier)

quality_delta' =
    round(-7 * negative_multiplier)
```

Критическая ошибка не должна автоматически масштабироваться этим коэффициентом: она остаётся отдельным терминальным механизмом.

---

### 5.9. Recovery difficulty

Сложность восстановления кодируется:

```text
0 = Easy
1 = Normal
2 = Hard
```

Проверки:

```text
difficulty 0:
    conversation_progress == forward
    AND actionability == high
    AND weighted_paei_fit >= 0

difficulty 1:
    difficulty 0 conditions

difficulty 2:
    difficulty 0 conditions
    AND weighted_paei_fit >= +1
```

Сам бонус успешного recovery одинаков:

```text
contact +15
resistance -10
progress +5
```

Меняется только требование к качеству восстановления.

---

## 6. Почему базовая таблица scoring не меняется

Базовые действия:

| Действие | Contact | Resistance | Progress | Quality |
|---|---:|---:|---:|---:|
| `strong_positive` | +8 | −8 | +12 | +12 |
| `positive` | +5 | −5 | +8 | +8 |
| `neutral` | 0 | 0 | +2 | 0 |
| `negative` | −6 | +6 | 0 | −7 |
| `critical_error` | −15 | +12 | −5 | −15 |
| `recovery_action` | +15 | −10 | +5 | +5 |

Эта таблица должна оставаться одинаковой между Easy/Normal/Hard.

Исключение: сила негативного действия может быть параметризована через `negative_action_strength`, как описано в разделе 5.8.

---

## 7. Настройка баланса

### 7.1. Цель настройки

Уровни должны отличаться по **ресурсному давлению**, но не по смыслу действий.

Нельзя делать Hard таким, чтобы успешная переговорная реплика переставала быть успешной только из-за названия режима.

### 7.2. Порядок тюнинга

Рекомендуемый порядок:

```text
1. Проверить базовый scoring на Normal.
2. Зафиксировать ожидаемое число ходов до достижения progress 80.
3. Проверить частоту contact_lost.
4. Проверить влияние hint_limit.
5. Настроить turn_limit.
6. Настроить critical_error_limit.
7. Настроить negative_action_strength.
8. Проверить recovery.
9. Сравнить Easy и Hard на тех же сценариях.
```

### 7.3. Что менять при дисбалансе

| Симптом | Менять в первую очередь |
|---|---|
| Пользователь почти всегда выигрывает с запасом | `turn_limit`, `hint_limit`, `initial_resistance` |
| Слишком часто теряется контакт в начале | `initial_contact`, затем `initial_resistance` |
| Hard ощущается как случайный | уменьшить силу негативных последствий или увеличить `turn_limit` |
| Hard почти неотличим от Normal | увеличить разницу в `turn_limit` и `hint_limit` |
| Recovery слишком легко | `recovery_difficulty` |
| Recovery почти невозможно | снизить только критерий recovery, не менять его бонус |
| Подсказки дают слишком большой бонус | не увеличивать штрафы; сначала проверить содержание подсказок |
| Критическая ошибка слишком часто мгновенно завершает игру | увеличить `critical_error_limit` только после проверки классификатора ошибок |

---

## 8. Критерии приёмки уровней

### Easy

Ожидается:

- пользователь имеет запас `contact = 80`;
- пользователь получает до 5 подсказок;
- 15 ходов;
- 4 критические ошибки допустимы до поражения;
- recovery доступен при базовом условии качества.

### Normal

Ожидается:

- `contact = 70`;
- 3 подсказки;
- 12 ходов;
- 3 критические ошибки;
- recovery требует положительного результата.

### Hard

Ожидается:

- `contact = 60`;
- `resistance = 60`;
- 2 подсказки;
- 10 ходов;
- 2 критические ошибки;
- более сильные негативные последствия;
- recovery требует `weighted_paei_fit >= +1`.

---

## 9. Формат versioned configuration

Рекомендуемый машинно-читаемый формат:

```yaml
difficulty_version: "1.0"

profiles:
  training:
    initial_contact: 80
    initial_resistance: 20
    contact_loss_threshold: 20
    goal_threshold: 80
    hint_limit: 5
    turn_limit: 15
    critical_error_limit: 4
    negative_action_strength: 4
    recovery_difficulty: 0
    recovery_attempt_limit: 1

  easy:
    initial_contact: 80
    initial_resistance: 20
    contact_loss_threshold: 20
    goal_threshold: 80
    hint_limit: 5
    turn_limit: 15
    critical_error_limit: 4
    negative_action_strength: 4
    recovery_difficulty: 0
    recovery_attempt_limit: 1

  normal:
    initial_contact: 70
    initial_resistance: 40
    contact_loss_threshold: 20
    goal_threshold: 80
    hint_limit: 3
    turn_limit: 12
    critical_error_limit: 3
    negative_action_strength: 6
    recovery_difficulty: 1
    recovery_attempt_limit: 1

  hard:
    initial_contact: 60
    initial_resistance: 60
    contact_loss_threshold: 20
    goal_threshold: 80
    hint_limit: 2
    turn_limit: 10
    critical_error_limit: 2
    negative_action_strength: 8
    recovery_difficulty: 2
    recovery_attempt_limit: 1
```

---

## 10. Технические правила

1. `difficulty_profile` передаётся от Scenario Manager в Game Engine.
2. Game Engine валидирует конфигурацию до запуска сценария.
3. Неизвестный параметр или значение вне диапазона → ошибка конфигурации до начала игры.
4. Нельзя изменить `difficulty_profile` после первого игрового хода.
5. Каждое событие сохраняет `difficulty_version` и `difficulty_profile`.
6. Результат должен воспроизводиться при одинаковых:
   - `scenario_version`;
   - `scoring_version`;
   - `difficulty_version`;
   - `difficulty_profile`;
   - входных сообщениях;
   - начальном состоянии.
7. UI может отображать название уровня, но не должен сам рассчитывать его эффекты.

---

## 11. Тестовая матрица

Минимально необходимо проверить каждый уровень на одном и том же наборе сценариев.

| Проверка | Training | Easy | Normal | Hard |
|---|:---:|:---:|:---:|:---:|
| Загрузка конфигурации | ✓ | ✓ | ✓ | ✓ |
| Начальный contact | ✓ | ✓ | ✓ | ✓ |
| Начальный resistance | ✓ | ✓ | ✓ | ✓ |
| Лимит подсказок | ✓ | ✓ | ✓ | ✓ |
| Лимит ходов | ✓ | ✓ | ✓ | ✓ |
| Лимит critical errors | ✓ | ✓ | ✓ | ✓ |
| Потеря контакта | ✓ | ✓ | ✓ | ✓ |
| Recovery | ✓ | ✓ | ✓ | ✓ |
| Negative scaling | ✓ | ✓ | ✓ | ✓ |
| Success на последнем ходу | ✓ | ✓ | ✓ | ✓ |
| Timeout | ✓ | ✓ | ✓ | ✓ |
| Воспроизводимость | ✓ | ✓ | ✓ | ✓ |

---

## 12. Версионирование

Любое изменение числового значения создаёт новую версию difficulty configuration.

Пример:

```text
1.0 → исходный MVP
1.1 → изменён только hint_limit
1.2 → изменён negative_action_strength
2.0 → изменена структура конфигурации
```

Нельзя перезаписывать старую версию, если по ней уже существуют сохранённые игровые результаты.
