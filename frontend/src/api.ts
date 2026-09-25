export type User = {
  id: string;
  email: string | null;
  display_name: string;
  role: string;
};

export type AuthResponse = { access_token: string; user: User };

export type Storyline = {
  id: string;
  slug: string;
  title: string;
  description: string;
  cover_url: string | null;
};

export type Mission = {
  id: string;
  storyline_id: string | null;
  knowledge_item_id: string | null;
  mission_type: 'story' | 'method_training';
  interaction_type: string;
  branch_key: string | null;
  order_index: number | null;
  title: string;
  status: string;
};

export type StorylineDetail = Storyline & { missions: Mission[] };

export type KnowledgeItem = {
  id: string;
  parent_id: string | null;
  item_type: 'topic' | 'article' | 'method';
  slug: string;
  title: string;
  summary: string | null;
  sort_order: number;
};

export type KnowledgeDetail = KnowledgeItem & {
  body: string | null;
  metadata: Record<string, unknown>;
  children: KnowledgeItem[];
};

export type CustomSessionSettings = {
  situation: string;
  player_role: string;
  opponent_role: string;
  opponent_name: string | null;
  goal: string;
  tone: 'calm' | 'direct' | 'resistant';
  turn_limit: 6 | 10 | 15;
};

export type SessionMode = 'custom' | 'story' | 'method_training';

export type GameSession = {
  id: string;
  mode: SessionMode;
  status: 'active' | 'completed' | 'failed' | 'abandoned';
  mission_id: string | null;
  character_id: string | null;
  custom_context: CustomSessionSettings | null;
  state: { turn?: number; contact?: number; tension?: number; progress?: number; score?: number };
  final_result: { result?: string; reason?: string; score?: number } | null;
  ai_mode: 'mock' | 'compatible';
};

export type GameSessionSummary = Pick<GameSession, 'id' | 'mode' | 'status' | 'mission_id' | 'custom_context' | 'state'> & {
  mission_title: string | null;
  started_at: string;
  last_activity_at: string;
};

export type GameMessage = { id: string; sequence_number: number; role: 'user' | 'assistant' | 'system'; content: string; processing_status: string };

export type CharacterOption = { id: string; name: string; role_title: string; description: string };
export type GameOptions = {
  characters: CharacterOption[];
  paei_profiles: { id: string; code: string; leading_letter: string }[];
  difficulty_profiles: { id: string; code: string; title: string }[];
};
export type MissionBriefing = {
  id: string;
  storyline_id: string | null;
  mission_type: 'story' | 'method_training';
  interaction_type: string;
  title: string;
  task: string;
  character: CharacterOption | null;
};

export type CreateSessionRequest = {
  mode: SessionMode;
  mission_id?: string;
  paei_profile_id?: string;
  difficulty_profile_id?: string;
  character_id?: string;
  custom_context?: CustomSessionSettings;
};

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options.headers },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new ApiError(response.status, typeof payload.detail === 'string' ? payload.detail : 'Сервис временно недоступен');
  }
  return response.json() as Promise<T>;
}

export const api = {
  storylines: (signal?: AbortSignal) => request<Storyline[]>('/v1/storylines', { signal }),
  storyline: (id: string, signal?: AbortSignal) => request<StorylineDetail>(`/v1/storylines/${encodeURIComponent(id)}`, { signal }),
  missions: (type: Mission['mission_type'], signal?: AbortSignal) =>
    request<Mission[]>(`/v1/missions?mission_type=${type}`, { signal }),
  knowledge: (signal?: AbortSignal) => request<KnowledgeItem[]>('/v1/knowledge', { signal }),
  knowledgeItem: (id: string, signal?: AbortSignal) => request<KnowledgeDetail>(`/v1/knowledge/${encodeURIComponent(id)}`, { signal }),
  gameOptions: (signal?: AbortSignal) => request<GameOptions>('/v1/game/options', { signal }),
  missionBriefing: (id: string, signal?: AbortSignal) => request<MissionBriefing>(`/v1/missions/${encodeURIComponent(id)}/briefing`, { signal }),
  sessions: (token: string, signal?: AbortSignal) => request<GameSessionSummary[]>('/v1/sessions', {
    signal, headers: { Authorization: `Bearer ${token}` },
  }),
  createSession: (token: string, settings: CreateSessionRequest) => request<{ id: string }>('/v1/sessions', {
    method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: JSON.stringify(settings),
  }),
  session: (token: string, id: string, signal?: AbortSignal) => request<GameSession>(`/v1/sessions/${encodeURIComponent(id)}`, {
    signal, headers: { Authorization: `Bearer ${token}` },
  }),
  sessionMessages: (token: string, id: string, signal?: AbortSignal) => request<{ session_id: string; messages: GameMessage[] }>(`/v1/sessions/${encodeURIComponent(id)}/messages`, {
    signal, headers: { Authorization: `Bearer ${token}` },
  }),
  finishSession: (token: string, id: string) => request<{ status: GameSession['status'] }>(`/v1/sessions/${encodeURIComponent(id)}/finish`, {
    method: 'POST', headers: { Authorization: `Bearer ${token}` },
  }),
  me: (token: string) => request<User>('/v1/users/me', { headers: { Authorization: `Bearer ${token}` } }),
  login: (email: string, password: string) => request<AuthResponse>('/v1/auth/login', {
    method: 'POST', body: JSON.stringify({ email, password }),
  }),
  register: (email: string, password: string, display_name: string) => request<AuthResponse>('/v1/auth/register', {
    method: 'POST', body: JSON.stringify({ email, password, display_name }),
  }),
  logout: () => request<{ message: string }>('/v1/auth/logout', { method: 'POST' }),
};

export function sessionSocketUrl(token: string, id: string) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}/api/v1/ws/sessions/${encodeURIComponent(id)}?token=${encodeURIComponent(token)}`;
}
