import { FormEvent, useEffect, useState } from 'react';
import { Link, NavLink, Route, Routes, useLocation, useParams } from 'react-router-dom';
import { api, ApiError, Mission, Storyline, StorylineDetail, StoryProgress, User } from './api';
import { AuthContext, useAuth } from './auth-context';
import { CustomTrainingForm } from './CustomTraining';
import { GameDialog, MissionSetup } from './GameSession';
import GuidedTrainingPage from './GuidedTraining';
import { AdminPage } from './Admin';
import { AccountPage } from './AccountPage';
import { KnowledgeLibrary, KnowledgePage, KnowledgeQuizPage } from './KnowledgePages';
import './styles.css';

type Resource<T> = { data: T | null; loading: boolean; error: string | null };

function useResource<T>(key: string, load: (signal: AbortSignal) => Promise<T>): Resource<T> {
  const [state, setState] = useState<Resource<T>>({ data: null, loading: true, error: null });
  useEffect(() => {
    const controller = new AbortController();
    setState({ data: null, loading: true, error: null });
    load(controller.signal).then(data => setState({ data, loading: false, error: null }))
      .catch(error => {
        if (error.name !== 'AbortError') setState({ data: null, loading: false, error: 'Не удалось загрузить данные. Обновите страницу и попробуйте снова.' });
      });
    return () => controller.abort();
  }, [key]);
  return state;
}

function ResourceView<T>({ resource, empty, children }: { resource: Resource<T>; empty: string; children: (data: T) => React.ReactNode }) {
  if (resource.loading) return <div className="notice" role="status">Загружаем материалы…</div>;
  if (resource.error) return <div className="notice error" role="alert">{resource.error}</div>;
  if (!resource.data || (Array.isArray(resource.data) && resource.data.length === 0)) return <div className="notice">{empty}</div>;
  return <>{children(resource.data)}</>;
}

function AuthDialog({ close, signedIn }: { close: () => void; signedIn: (token: string, user: User) => void }) {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [error, setError] = useState('');
  const [pending, setPending] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const email = String(form.get('email') || '');
    const password = String(form.get('password') || '');
    setError('');
    setPending(true);
    try {
      const result = mode === 'login'
        ? await api.login(String(form.get('login') || ''), password)
        : await api.register(email, password, String(form.get('display_name') || ''), String(form.get('login') || ''));
      signedIn(result.access_token, result.user);
      close();
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) setError('Неверный логин, почта или пароль.');
      else if (cause instanceof ApiError && cause.status === 409) setError('Такой логин или почта уже зарегистрированы.');
      else setError(cause instanceof ApiError ? cause.message : 'Нет связи с сервером.');
    } finally { setPending(false); }
  }
  return <div className="modal-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) close(); }}>
    <section className="auth-dialog" role="dialog" aria-modal="true" aria-labelledby="auth-title">
      <button className="close" onClick={close} aria-label="Закрыть">×</button>
      <span className="eyebrow">Личный кабинет</span>
      <h2 id="auth-title">{mode === 'login' ? 'Вход' : 'Регистрация'}</h2>
      <p>Сохраните свои тренировки и возвращайтесь к ним позже.</p>
      <div className="segmented" role="tablist" aria-label="Режим авторизации">
        <button role="tab" aria-selected={mode === 'login'} className={mode === 'login' ? 'active' : ''} onClick={() => { setMode('login'); setError(''); }}>Вход</button>
        <button role="tab" aria-selected={mode === 'register'} className={mode === 'register' ? 'active' : ''} onClick={() => { setMode('register'); setError(''); }}>Регистрация</button>
      </div>
      <form className="auth-form" onSubmit={submit}>
        {mode === 'register' && <label>Имя<input name="display_name" required maxLength={120} autoComplete="name" placeholder="Как к вам обращаться" /></label>}
        <label>Логин{mode === 'login' ? ' или email' : ''}<input name="login" required minLength={mode === 'register' ? 3 : 1} maxLength={mode === 'register' ? 40 : 320} autoComplete="username" placeholder="Ваш логин" /></label>
        {mode === 'register' && <label>Электронная почта<input name="email" type="email" required autoComplete="email" placeholder="you@example.com" /></label>}
        <label>Пароль<input name="password" type="password" required minLength={mode === 'register' ? 8 : 1} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} placeholder="Ваш пароль" /></label>
        {error && <p className="form-error" role="alert">{error}</p>}
        <button className="button primary full" disabled={pending}>{pending ? 'Подождите…' : mode === 'login' ? 'Войти' : 'Создать аккаунт'} <span>↗</span></button>
      </form>
    </section>
  </div>;
}

function Shell({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const [user, setUser] = useState<User | null>(null);
  const [authOpen, setAuthOpen] = useState(false);
  const [checkingAuth, setCheckingAuth] = useState(Boolean(sessionStorage.getItem('arena_token')));
  useEffect(() => {
    const token = sessionStorage.getItem('arena_token');
    if (token) api.me(token).then(setUser).catch(() => sessionStorage.removeItem('arena_token')).finally(() => setCheckingAuth(false));
  }, []);
  useEffect(() => { window.scrollTo(0, 0); }, [location.pathname]);
  function logout() {
    api.logout().catch(() => undefined);
    sessionStorage.removeItem('arena_token');
    setUser(null);
  }
  return <AuthContext.Provider value={{ user, checking: checkingAuth, openAuth: () => setAuthOpen(true), updateUser: setUser }}><div className="app-shell">
    <header className="site-header">
      <Link className="brand" to="/" aria-label="Корпоративная крыса — на главную"><span>КОРПОРАТИВНАЯ<br /><strong>КРЫСА</strong></span></Link>
      <nav className="main-nav" aria-label="Главная навигация"><NavLink to="/training">Тренировка</NavLink><NavLink to="/story">Сюжет</NavLink><NavLink to="/knowledge">База знаний</NavLink>{user?.role === 'admin' && <NavLink to="/admin">Админка</NavLink>}</nav>
      <div className="header-actions">{user ? <><Link className="user-name" to="/account"><span className="user-name-display">{user.display_name} · </span>Кабинет</Link><button className="button outline small" onClick={logout}>Выйти</button></> : <button className="button outline small" onClick={() => setAuthOpen(true)}>Войти <span>↗</span></button>}</div>
    </header>
    <main id="main-content">{children}</main>
    <footer className="site-footer"><span>© Корпоративная крыса</span></footer>
    {authOpen && <AuthDialog close={() => setAuthOpen(false)} signedIn={(token, value) => { sessionStorage.setItem('arena_token', token); setUser(value); }} />}
  </div></AuthContext.Provider>;
}

function Home() {
  return <>
    <section className="hero">
      <div className="hero-copy"><span className="eyebrow">Игра о переговорах</span>
        <h1>Зайдите в кабинет.<br /><em>Начните разговор.</em></h1>
        <p>Коллега уже ждёт вашего ответа. Пробуйте разные подходы, ошибайтесь без последствий и находите слова, которые работают.</p>
        <div className="hero-actions"><Link className="button primary" to="/training">Выбрать тренировку <span>→</span></Link><Link className="text-link" to="/story">Исследовать сюжет <span>↗</span></Link></div>
      </div>
      <div className="hero-art"><img src="/images/office-training-scene.png" alt="Нарисованная переговорная: собеседница ждёт игрока у стола" /></div>
    </section>
    <section className="section-wrap home-sections">
      <div className="section-heading"><div><span className="eyebrow">Что сегодня?</span><h2>Выберите свою игру</h2></div></div>
      <div className="module-grid">
        <Link to="/story" className="module-card story"><span className="card-kicker">Офисная история</span><h3>Сюжет</h3><p>Разные люди, решения и последствия. Здесь каждый разговор двигает историю.</p><span className="module-action">Смотреть истории <span>↗</span></span></Link>
        <Link to="/training" className="module-card training"><span className="card-kicker">Один на один</span><h3>Тренировка</h3><p>Один собеседник, одна ситуация — и сколько угодно попыток найти верный тон.</p><span className="module-action">Открыть тренировки <span>↗</span></span></Link>
        <Link to="/knowledge" className="module-card knowledge"><span className="card-kicker">Шпаргалка</span><h3>База знаний</h3><p>Приёмы и идеи, к которым можно вернуться перед следующим разговором.</p><span className="module-action">Листать материалы <span>↗</span></span></Link>
        <Link to="/pvp" className="module-card pvp"><span className="card-kicker">Скоро</span><h3>PvP</h3><p>Переговорный поединок с другим игроком. Готовим площадку.</p><span className="module-action">О режиме <span>↗</span></span></Link>
      </div>
    </section>
  </>;
}

function PageIntro({ eyebrow, title, text, back }: { eyebrow: string; title: string; text: string; back?: string }) {
  return <div className="page-intro section-wrap"><div>{back && <Link className="back-link" to={back}>← Назад</Link>}<span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{text}</p></div></div>;
}

function Training() {
  const missions = useResource('training', signal => api.missions('method_training', signal));
  return <><section className="training-banner section-wrap"><div><span className="eyebrow">Один на один</span><h1>Тренировка</h1><p>В каждой тренировке вы разговариваете с одним собеседником. Выбирайте ситуацию и пробуйте новые решения.</p></div><img src="/images/office-training-scene.png" alt="Собеседница в переговорной" /></section>
    <section className="section-wrap custom-entry"><div><span className="eyebrow">Ваш сценарий</span><h2>Разговор на ваших условиях</h2><p>Опишите ситуацию, задайте цель и характер собеседника. После этого можно сразу начать диалог.</p></div><Link className="button primary" to="/training/custom">Создать свой диалог <span>↗</span></Link></section>
    <section className="section-wrap content-section"><div className="content-toolbar"><div><span className="eyebrow">Каталог тренировок</span><h2>Выберите сценарий</h2></div><span className="pill">{missions.data?.length ?? 0} доступно</span></div>
      <ResourceView resource={missions} empty="Опубликованных тренировок пока нет. Как только появятся сценарии, они будут показаны здесь.">{items => <div className="list-grid">{items.map((mission: Mission) => <Link className="list-card" to={`/training/mission/${mission.id}`} key={mission.id}><div><span className="eyebrow">{mission.interaction_type === 'guided_training' ? 'Практика решений' : mission.interaction_type === 'single_choice' ? 'Выбор ответа' : 'Диалог'}</span><h3>{mission.title}</h3><p>{mission.interaction_type === 'guided_training' ? 'Несколько ситуаций, подсказки и ответ своими словами.' : 'Откройте сценарий и настройте разговор.'}</p></div><span className="round-arrow">↗</span></Link>)}</div>}</ResourceView>
    </section></>;
}

function Story() {
  const stories = useResource('storylines', api.storylines);
  return <><section className="training-banner story-banner section-wrap"><div><span className="eyebrow">Офисная история</span><h1>Сюжет</h1><p>Здесь разговор не всегда один на один. Знакомьтесь с разными героями, принимайте решения и смотрите, как меняются отношения.</p></div><img src="/images/office-story-scene.png" alt="Трое коллег обсуждают решение в переговорной" /></section>
    <section className="section-wrap content-section"><div className="content-toolbar"><div><span className="eyebrow">Сюжетные линии</span><h2>Карта историй</h2></div></div>
      <ResourceView resource={stories} empty="Сюжетных линий пока нет. Они появятся здесь, когда будут готовы.">{items => <div className="story-grid">{items.map((story: Storyline) => <Link className="story-card" to={`/story/${story.id}`} key={story.id}><div><span className="eyebrow">Сюжетная линия</span><h3>{story.title}</h3><p>{story.description}</p></div><span className="round-arrow">↗</span></Link>)}</div>}</ResourceView>
    </section></>;
}

function StoryDetailPage() {
  const { id = '' } = useParams();
  const { user } = useAuth();
  const resource = useResource(`story-${id}`, signal => api.storyline(id, signal));
  const [progress, setProgress] = useState<StoryProgress | null>(null);
  useEffect(() => {
    const token = sessionStorage.getItem('arena_token');
    if (!token || !user) { setProgress(null); return; }
    const controller = new AbortController();
    api.storyProgress(token, id, controller.signal).then(setProgress).catch(() => setProgress(null));
    return () => controller.abort();
  }, [id, user?.id]);
  return <><PageIntro eyebrow="Карта сюжета" title={resource.data?.title || 'Сюжетная линия'} text={resource.data?.description || 'Изучаем доступные миссии и порядок прохождения.'} back="/story" />
    <section className="section-wrap content-section"><ResourceView resource={resource} empty="Сюжет не найден.">{(story: StorylineDetail) => <StoryMap story={story} progress={progress} />}</ResourceView></section></>;
}

function StoryMap({ story, progress }: { story: StorylineDetail; progress: StoryProgress | null }) {
  const branches = Array.from(story.missions.reduce((groups, mission) => {
    const key = mission.branch_key || 'main';
    groups.set(key, [...(groups.get(key) || []), mission]);
    return groups;
  }, new Map<string, Mission[]>()).entries());
  const completed = progress?.missions.filter(mission => mission.completed).length || 0;
  const branchTitle = (key: string) => ({ main: 'Основная линия', novice: 'Новичок', experienced: 'Опытный сотрудник', manager: 'Руководитель' }[key] || key.replace(/[_-]/g, ' '));
  return <div className="story-map-layout"><div className="story-map-tracks"><div className="content-toolbar"><div><span className="eyebrow">Карта линии</span><h2>Выберите эпизод</h2></div><span className="pill">Миссий: {story.missions.length}</span></div>
    {branches.length ? branches.map(([key, missions]) => <section className="story-branch" key={key} aria-label={branchTitle(key)}><h3>{branchTitle(key)}</h3><div className="story-branch-track">{missions.map((mission, index) => {
      const state = progress?.missions.find(item => item.mission_id === mission.id);
      const unlocked = state?.unlocked ?? index === 0;
      const status = state?.completed ? 'Пройдено' : unlocked ? 'Доступно' : 'Закрыто';
      const inner = <><span className="story-map-node">{String(index + 1).padStart(2, '0')}</span><strong>{mission.title}</strong><small>{status}</small></>;
      return unlocked ? <Link className={`story-map-mission${state?.completed ? ' completed' : ''}`} title={mission.title} aria-label={`${mission.title} — ${status}`} to={`/story/mission/${mission.id}`} key={mission.id}>{inner}</Link>
        : <div className="story-map-mission locked" title={mission.title} aria-label={`${mission.title} — ${status}`} key={mission.id}>{inner}</div>;
    })}</div></section>) : <div className="notice">В этой линии пока нет опубликованных миссий.</div>}
  </div><aside className="story-map-status"><span className="eyebrow">Статус линии</span><h2>{completed ? `${completed} из ${story.missions.length} пройдено` : 'Начните историю'}</h2><p>{completed ? 'Пройденные эпизоды можно открыть повторно. Новые становятся доступны после успешного разговора.' : 'Выберите доступный эпизод на карте. Следующие миссии открываются после успешного разговора.'}</p><div className="story-map-legend"><span><i className="available" /> Доступно</span><span><i className="done" /> Пройдено</span><span><i className="closed" /> Закрыто</span></div><Link className="button outline" to="/knowledge">База знаний <span>↗</span></Link></aside></div>;
}

function PvpSoon() {
  return <section className="pvp-page section-wrap"><div className="pvp-panel"><span className="eyebrow">Скоро</span><h1>PvP арена</h1><p>Переговорные поединки с другими игроками появятся позже.</p><Link className="button primary" to="/">На главный экран <span>→</span></Link></div></section>;
}

export default function App() {
  return <Shell><Routes>
    <Route path="/" element={<Home />} />
    <Route path="/training" element={<Training />} />
    <Route path="/training/custom" element={<CustomTrainingForm />} />
    <Route path="/training/mission/:id" element={<MissionSetup mode="method_training" />} />
    <Route path="/training/guided/:id" element={<GuidedTrainingPage />} />
    <Route path="/training/session/:id" element={<GameDialog />} />
    <Route path="/session/:id" element={<GameDialog />} />
    <Route path="/story" element={<Story />} />
    <Route path="/story/:id" element={<StoryDetailPage />} />
    <Route path="/story/mission/:id" element={<MissionSetup mode="story" />} />
    <Route path="/pvp" element={<PvpSoon />} />
    <Route path="/knowledge" element={<KnowledgeLibrary />} />
    <Route path="/knowledge/:id" element={<KnowledgePage />} />
    <Route path="/knowledge/:id/quiz" element={<KnowledgeQuizPage />} />
    <Route path="/admin" element={<AdminPage />} />
    <Route path="/account" element={<AccountPage />} />
    <Route path="*" element={<section className="section-wrap not-found"><span className="eyebrow">404 / Не найдено</span><h1>Похоже, здесь пока пусто.</h1><Link className="button primary" to="/">На главную <span>↗</span></Link></section>} />
  </Routes></Shell>;
}
