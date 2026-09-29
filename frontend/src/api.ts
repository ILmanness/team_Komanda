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

export type KnowledgeProgress = {
  completed_ids: string[];
  latest_quizzes: { knowledge_item_id: string; score: number; question_count: number; created_at: string }[];
};
export type KnowledgeQuiz = {
  id: string; title: string;
  questions: { number: number; prompt: string; material_id: string | null; choices: { id: string; text: string }[] }[];
};
export type KnowledgeQuizResult = {
  score: number; total: number; completed: boolean;
  results: { number: number; material_id: string | null; selected: string; correct: string; is_correct: boolean; explanation: string }[];
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
  status: 'active' | 'completed' | 'failed' | 'abandoned' | 'needs_review';
  mission_id: string | null;
  character_id: string | null;
  mission_title?: string | null;
  mission_task?: string | null;
  mission_situation?: string | null;
  mission_public_context?: string | null;
  character_name?: string | null;
  character_slug?: string | null;
  character_role_title?: string | null;
  character_description?: string | null;
  character_paei_description?: string | null;
  character_behavior_description?: string | null;
  custom_context: CustomSessionSettings | null;
  state: { turn?: number; contact?: number; tension?: number; progress?: number; score?: number; node_id?: string; goal_state?: { status: 'unresolved' | 'advancing' | 'achieved' | 'blocked'; review_available?: boolean } };
  final_result: { result?: string; reason?: string; score?: number } | null;
  ai_mode: 'none' | 'mock' | 'compatible';
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

export type GameMessage = { id: string; sequence_number: number; role: 'user' | 'assistant' | 'system'; content: string; emotion?: 'neutral' | 'warm' | 'tense' | 'angry'; processing_status: string };

export type CharacterOption = { id: string; slug: string; name: string; role_title: string; description: string;
  paei_profile_id: string | null; paei_code: string | null; paei_leading_letter: string | null;
  paei_description: string; behavior_description: string; portrait_url: string };
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
  situation: string;
  public_context: string;
  character: CharacterOption | null;
  choices: { id: string; text: string }[];
  hints: string[];
};

export type GuidedEvent = {
  sequence_no: number; node_id: string; base_node_id: string; choice_id: string;
  choice_text: string; assessment: 'correct' | 'partial' | 'incorrect';
  effect: string | null; feedback_text: string; transition_notice: string | null;
  attempt_stage: 'first' | 'retry'; resolution: string;
};
export type GuidedTraining = {
  session_id: string; status: GameSession['status']; training_id: string; title: string;
  node: { id: string; speaker: string; text: string; type: 'decision' | 'knowledge' | 'retry' | 'free_text'; goal: string };
  choices: { id: 'a' | 'b' | 'c'; text: string }[];
  events: GuidedEvent[];
  criteria: { criterion_id: string; criterion: string }[];
  example_answer: string | null;
  final_result: { result?: string; answer?: string; criteria?: { criterion_id: string; status: string; evidence_quote: string; reason: string }[] } | null;
  material_id: string;
};

export type BranchingEvent = {
  sequence_no: number; node_id: string; option_id: string; choice_text: string;
  effect: string | null; feedback?: string;
};
export type BranchingTraining = {
  session_id: string; mission_id: string; status: GameSession['status']; tool_id: string; tool_title: string;
  tool_description: string; category: 'methods' | 'principles';
  scenario_id: string; scenario_title: string; goal: string;
  node: { node_id: string; type: 'decision' | 'consequence' | 'terminal'; speaker: string; text: string; outcome: string | null };
  choices: { id: string; text: string }[]; events: BranchingEvent[];
  final_result: { result?: string; scenario_id?: string; tool_id?: string } | null;
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
export type AdminGuidedOption = { text: string; effect: string; feedback: string; assessment: 'correct' | 'partial' | 'incorrect' };
export type AdminGuidedStep = { speaker: string; text: string; goal: string; hint: string; options: AdminGuidedOption[] };
export type AdminGuidedAuthoring = { steps: AdminGuidedStep[]; final_situation: string; final_goal: string; criteria: string[]; example_answer: string };
export type AdminBranchingOption = { id: string; text: string; effect: string | null; flag: string | null; feedback: string; next_node: string };
export type AdminBranchingNode = { node_id: string; type: 'decision' | 'consequence' | 'terminal'; speaker: string; text: string; outcome: 'success' | 'partial' | 'fail' | 'not_applied' | null; options: AdminBranchingOption[] };
export type AdminBranchingScenario = { id: string; title: string; goal: string; start_node_id: string; weight: number; status: 'active' | 'inactive'; nodes: Record<string, AdminBranchingNode> };
export type AdminBranchingTool = { id: string; category: 'methods' | 'principles'; title: string; description: string; order: number; scenarios: AdminBranchingScenario[]; source?: string };
export type AdminMission = AdminMissionSummary & {
  task: string;
  context: { situation?: string; public_context?: string; opening_message?: string };
  config: { max_turns?: number; training?: { choices: AdminChoice[]; hints: string[] }; guided?: { source?: string; authoring?: AdminGuidedAuthoring }; branching?: AdminBranchingTool };
};
export type AdminMissionWrite = {
  mission_type: Mission['mission_type']; interaction_type: 'ai_dialogue' | 'single_choice' | 'guided_training' | 'branching_training';
  storyline_id: string | null; knowledge_item_id: string | null; character_id: string;
  branch_key: string | null; order_index: number | null; title: string; situation: string; public_context: string;
  task: string; opening_message: string; max_turns: number; choices: AdminChoice[]; hints: string[]; guided: AdminGuidedAuthoring | null; branching?: AdminBranchingTool | null;
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
  knowledgeProgress: (token: string, signal?: AbortSignal) => request<KnowledgeProgress>('/v1/knowledge/progress', {
    signal, headers: { Authorization: `Bearer ${token}` },
  }),
  knowledgeQuiz: (id: string, signal?: AbortSignal) => request<KnowledgeQuiz>(`/v1/knowledge/${encodeURIComponent(id)}/quiz`, { signal }),
  completeKnowledge: (token: string, id: string) => request<{ completed: boolean }>(`/v1/knowledge/${encodeURIComponent(id)}/complete`, {
    method: 'POST', headers: { Authorization: `Bearer ${token}` },
  }),
  submitKnowledgeQuiz: (token: string, id: string, answers: Record<string, string>) =>
    request<KnowledgeQuizResult>(`/v1/knowledge/${encodeURIComponent(id)}/quiz`, {
      method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: JSON.stringify({ answers }),
    }),
  gameOptions: (signal?: AbortSignal) => request<GameOptions>('/v1/game/options', { signal }),
  characters: (signal?: AbortSignal) => request<CharacterOption[]>('/v1/characters', { signal }),
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
  guided: (token: string, id: string, signal?: AbortSignal) => request<GuidedTraining>(`/v1/sessions/${encodeURIComponent(id)}/guided`, {
    signal, headers: { Authorization: `Bearer ${token}` },
  }),
  guidedChoice: (token: string, id: string, node_id: string, choice_id: string) => request<GuidedTraining>(`/v1/sessions/${encodeURIComponent(id)}/guided/choice`, {
    method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: JSON.stringify({ node_id, choice_id }),
  }),
  guidedAnswer: (token: string, id: string, node_id: string, text: string) => request<GuidedTraining>(`/v1/sessions/${encodeURIComponent(id)}/guided/answer`, {
    method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: JSON.stringify({ node_id, text }),
  }),
  branching: (token: string, id: string, signal?: AbortSignal) => request<BranchingTraining>(`/v1/sessions/${encodeURIComponent(id)}/branching`, {
    signal, headers: { Authorization: `Bearer ${token}` },
  }),
  branchingChoice: (token: string, id: string, node_id: string, option_id: string) => request<BranchingTraining>(`/v1/sessions/${encodeURIComponent(id)}/branching/choice`, {
    method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: JSON.stringify({ node_id, option_id }),
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
  logout: (token: string) => request<{ message: string }>('/v1/auth/logout', { method: 'POST', keepalive: true, headers: { Authorization: `Bearer ${token}` } }),
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
