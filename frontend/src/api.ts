export type User = {
  id: string;
  email: string | null;
  login: string;
  display_name: string;
  role: string;
  created_at: string;
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
export type StoryProgress = { missions: { mission_id: string; unlocked: boolean; completed: boolean }[] };

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
  final_result: GameSession['final_result'];
  started_at: string;
  last_activity_at: string;
};

export type AccountStats = {
  conversations: number; active: number; finished: number; successful: number;
  story_successes: number; trainings: number;
};

export type GameMessage = { id: string; sequence_number: number; role: 'user' | 'assistant' | 'system'; content: string; payload: { emotion?: string }; processing_status: string };

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
  choices: { id: string; text: string }[];
  hints: string[];
};

export type AdminStoryline = Storyline & { status: string };
export type AdminCharacter = CharacterOption & { slug: string; base_prompt: string };
export type AdminKnowledge = { id: string; slug: string; item_type: 'topic' | 'article' | 'method'; title: string; summary: string; body: string; parent_id: string | null; status: string };
export type AdminMissionSummary = Mission & { character_id: string | null };
export type AdminOverview = {
  storylines: AdminStoryline[];
  missions: AdminMissionSummary[];
  characters: AdminCharacter[];
  knowledge: AdminKnowledge[];
  paei_profiles: GameOptions['paei_profiles'];
  difficulty_profiles: GameOptions['difficulty_profiles'];
};
export type AdminChoice = { id: string; text: string; feedback: string; quality: number; contact: number; tension: number; progress: number; critical_error: boolean };
export type AdminMission = AdminMissionSummary & {
  task: string;
  context: { situation?: string; opening_message?: string };
  config: { max_turns?: number; training?: { choices: AdminChoice[]; hints: string[] } };
};
export type AdminMissionWrite = {
  mission_type: Mission['mission_type']; interaction_type: 'ai_dialogue' | 'single_choice';
  storyline_id: string | null; knowledge_item_id: string | null; character_id: string;
  branch_key: string | null; order_index: number | null; title: string; situation: string;
  task: string; opening_message: string; max_turns: number; choices: AdminChoice[]; hints: string[];
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
    const detail = Array.isArray(payload.detail)
      ? payload.detail.map((item: { msg?: string }) => item.msg).filter(Boolean).join('; ')
      : payload.detail;
    throw new ApiError(response.status, typeof detail === 'string' ? detail : 'Сервис временно недоступен');
  }
  return response.json() as Promise<T>;
}

export const api = {
  storylines: (signal?: AbortSignal) => request<Storyline[]>('/v1/storylines', { signal }),
  storyline: (id: string, signal?: AbortSignal) => request<StorylineDetail>(`/v1/storylines/${encodeURIComponent(id)}`, { signal }),
  storyProgress: (token: string, id: string, signal?: AbortSignal) => request<StoryProgress>(`/v1/storylines/${encodeURIComponent(id)}/progress`, {
    signal, headers: { Authorization: `Bearer ${token}` },
  }),
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
  accountStats: (token: string, signal?: AbortSignal) => request<AccountStats>('/v1/users/me/stats', {
    signal, headers: { Authorization: `Bearer ${token}` },
  }),
  updateProfile: (token: string, display_name: string) => request<User>('/v1/users/me', {
    method: 'PATCH', headers: { Authorization: `Bearer ${token}` }, body: JSON.stringify({ display_name }),
  }),
  login: (login: string, password: string) => request<AuthResponse>('/v1/auth/login', {
    method: 'POST', body: JSON.stringify({ login, password }),
  }),
  register: (email: string, password: string, display_name: string, login: string) => request<AuthResponse>('/v1/auth/register', {
    method: 'POST', body: JSON.stringify({ email, password, display_name, login }),
  }),
  logout: () => request<{ message: string }>('/v1/auth/logout', { method: 'POST' }),
  adminOverview: (token: string) => request<AdminOverview>('/v1/admin/overview', { headers: { Authorization: `Bearer ${token}` } }),
  adminMission: (token: string, id: string) => request<AdminMission>(`/v1/admin/missions/${encodeURIComponent(id)}`, { headers: { Authorization: `Bearer ${token}` } }),
  adminSave: (token: string, kind: 'storylines' | 'missions' | 'characters' | 'knowledge', body: unknown, id?: string) => request<{ id: string; status?: string }>(`/v1/admin/${kind}${id ? `/${encodeURIComponent(id)}` : ''}`, {
    method: id ? 'PUT' : 'POST', headers: { Authorization: `Bearer ${token}` }, body: JSON.stringify(body),
  }),
  adminStatus: (token: string, kind: 'storylines' | 'missions' | 'knowledge', id: string, status: 'draft' | 'published' | 'archived') => request<{ id: string; status: string }>(`/v1/admin/${kind}/${encodeURIComponent(id)}/status`, {
    method: 'PUT', headers: { Authorization: `Bearer ${token}` }, body: JSON.stringify({ status }),
  }),
};

export function sessionSocketUrl(token: string, id: string) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}/api/v1/ws/sessions/${encodeURIComponent(id)}?token=${encodeURIComponent(token)}`;
}
