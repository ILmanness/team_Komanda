CREATE TABLE users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email varchar(320) UNIQUE,
    display_name varchar(120) NOT NULL,
    role varchar(20) NOT NULL DEFAULT 'player' CHECK (role IN ('player', 'admin')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE knowledge_items (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_id uuid REFERENCES knowledge_items(id) ON DELETE RESTRICT,
    item_type varchar(20) NOT NULL CHECK (item_type IN ('topic', 'article', 'method')),
    slug varchar(120) NOT NULL UNIQUE,
    title varchar(240) NOT NULL,
    summary text,
    body text,
    metadata jsonb NOT NULL DEFAULT '{}',
    status varchar(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'archived')),
    sort_order smallint NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (parent_id IS DISTINCT FROM id)
);

CREATE TABLE storylines (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug varchar(120) NOT NULL UNIQUE,
    title varchar(200) NOT NULL,
    description text NOT NULL DEFAULT '',
    cover_url text,
    status varchar(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'archived')),
    created_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE characters (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug varchar(120) NOT NULL UNIQUE,
    name varchar(160) NOT NULL,
    role_title varchar(200) NOT NULL DEFAULT '',
    description text NOT NULL DEFAULT '',
    base_prompt text NOT NULL DEFAULT '',
    behavior jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE paei_profiles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code varchar(32) NOT NULL UNIQUE,
    leading_letter char(1) NOT NULL CHECK (leading_letter IN ('P', 'A', 'E', 'I')),
    p_value smallint NOT NULL CHECK (p_value BETWEEN 0 AND 100),
    a_value smallint NOT NULL CHECK (a_value BETWEEN 0 AND 100),
    e_value smallint NOT NULL CHECK (e_value BETWEEN 0 AND 100),
    i_value smallint NOT NULL CHECK (i_value BETWEEN 0 AND 100),
    prompt_rules text NOT NULL DEFAULT '',
    behavior jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE difficulty_profiles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code varchar(40) NOT NULL UNIQUE,
    title varchar(120) NOT NULL,
    prompt_rules text NOT NULL DEFAULT '',
    settings jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE missions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    storyline_id uuid REFERENCES storylines(id) ON DELETE RESTRICT,
    character_id uuid REFERENCES characters(id) ON DELETE RESTRICT,
    knowledge_item_id uuid REFERENCES knowledge_items(id) ON DELETE RESTRICT,
    mission_type varchar(30) NOT NULL CHECK (mission_type IN ('story', 'method_training')),
    interaction_type varchar(30) NOT NULL CHECK (interaction_type IN ('ai_dialogue', 'scripted_dialogue', 'single_choice')),
    branch_key varchar(80),
    order_index smallint CHECK (order_index > 0),
    title varchar(200) NOT NULL,
    context jsonb NOT NULL DEFAULT '{}',
    task text NOT NULL,
    config jsonb NOT NULL DEFAULT '{}',
    status varchar(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'archived')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (storyline_id, branch_key, order_index),
    UNIQUE (id, mission_type),
    CHECK (mission_type <> 'story' OR (storyline_id IS NOT NULL AND branch_key IS NOT NULL AND order_index IS NOT NULL)),
    CHECK (mission_type <> 'method_training' OR knowledge_item_id IS NOT NULL)
);

CREATE TABLE game_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    mission_id uuid,
    character_id uuid REFERENCES characters(id) ON DELETE RESTRICT,
    paei_profile_id uuid REFERENCES paei_profiles(id) ON DELETE RESTRICT,
    difficulty_profile_id uuid REFERENCES difficulty_profiles(id) ON DELETE RESTRICT,
    mode varchar(20) NOT NULL CHECK (mode IN ('story', 'method_training', 'custom')),
    status varchar(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'failed', 'abandoned')),
    custom_context jsonb,
    state jsonb NOT NULL DEFAULT '{}',
    memory_summary jsonb NOT NULL DEFAULT '{}',
    config_snapshot jsonb NOT NULL DEFAULT '{}',
    prompt_version varchar(40) NOT NULL DEFAULT 'v1',
    lock_version integer NOT NULL DEFAULT 0 CHECK (lock_version >= 0),
    last_processed_sequence integer NOT NULL DEFAULT 0 CHECK (last_processed_sequence >= 0),
    final_result jsonb,
    started_at timestamptz NOT NULL DEFAULT now(),
    last_activity_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    history_purged_at timestamptz,
    FOREIGN KEY (mission_id, mode) REFERENCES missions(id, mission_type) ON DELETE RESTRICT,
    CHECK ((mode IN ('story', 'method_training') AND mission_id IS NOT NULL)
        OR (mode = 'custom' AND mission_id IS NULL AND custom_context IS NOT NULL)),
    CHECK ((status = 'active' AND completed_at IS NULL)
        OR (status <> 'active' AND completed_at IS NOT NULL)),
    CHECK (completed_at IS NULL OR completed_at >= started_at),
    CHECK (history_purged_at IS NULL OR status <> 'active')
);

CREATE TABLE session_messages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id uuid NOT NULL REFERENCES game_sessions(id) ON DELETE CASCADE,
    sequence_number integer NOT NULL CHECK (sequence_number > 0),
    role varchar(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content text NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}',
    evaluation jsonb,
    idempotency_key uuid,
    processing_status varchar(20) NOT NULL DEFAULT 'pending' CHECK (processing_status IN ('pending', 'completed', 'failed')),
    state_applied_at timestamptz,
    reply_to_message_id uuid,
    error_code varchar(80),
    model varchar(120),
    token_count integer CHECK (token_count >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (session_id, sequence_number),
    UNIQUE (session_id, idempotency_key),
    UNIQUE (session_id, id),
    UNIQUE (reply_to_message_id),
    FOREIGN KEY (session_id, reply_to_message_id) REFERENCES session_messages(session_id, id),
    CHECK (role <> 'user' OR idempotency_key IS NOT NULL),
    CHECK (state_applied_at IS NULL OR evaluation IS NOT NULL),
    CHECK (reply_to_message_id IS NULL OR role = 'assistant')
);

CREATE INDEX ix_knowledge_tree ON knowledge_items(parent_id, sort_order);
CREATE INDEX ix_missions_training ON missions(mission_type, knowledge_item_id);
CREATE INDEX ix_sessions_user ON game_sessions(user_id, started_at DESC);
CREATE INDEX ix_sessions_retention ON game_sessions(completed_at) WHERE status <> 'active';
CREATE INDEX ix_sessions_activity ON game_sessions(last_activity_at) WHERE status = 'active';
CREATE UNIQUE INDEX ix_one_pending_turn ON session_messages(session_id) WHERE role = 'user' AND processing_status = 'pending';
