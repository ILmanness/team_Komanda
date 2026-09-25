import { FormEvent, useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api, ApiError, GameMessage, GameOptions, GameSession, MissionBriefing, sessionSocketUrl } from './api';
import { useAuth } from './auth-context';

function errorText(cause: unknown) {
  if (cause instanceof ApiError && cause.status === 401) return 'Срок входа истёк. Войдите снова.';
  if (cause instanceof ApiError && cause.status === 404) return 'Этот разговор не найден.';
  return cause instanceof ApiError ? cause.message : 'Не удалось связаться с сервером. Попробуйте ещё раз.';
}

export function MissionSetup({ mode }: { mode: 'story' | 'method_training' }) {
  const { id = '' } = useParams();
  const navigate = useNavigate();
  const { user, checking, openAuth } = useAuth();
  const [briefing, setBriefing] = useState<MissionBriefing | null>(null);
  const [options, setOptions] = useState<GameOptions | null>(null);
  const [error, setError] = useState('');
  const [pending, setPending] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([api.missionBriefing(id, controller.signal), api.gameOptions(controller.signal)])
      .then(([mission, available]) => {
        if (mission.mission_type !== mode) throw new Error('Неверный режим миссии');
        setBriefing(mission);
        setOptions(available);
      })
      .catch(cause => { if (cause.name !== 'AbortError') setError(errorText(cause)); });
    return () => controller.abort();
  }, [id, mode]);

  async function start(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = sessionStorage.getItem('arena_token');
    if (!token || !user) { openAuth(); setError('Войдите, чтобы начать миссию.'); return; }
    const form = new FormData(event.currentTarget);
    setPending(true);
    setError('');
    try {
      const created = await api.createSession(token, {
        mode, mission_id: id,
        paei_profile_id: String(form.get('paei_profile_id')),
        difficulty_profile_id: String(form.get('difficulty_profile_id')),
      });
      navigate(`/session/${created.id}`);
    } catch (cause) { setError(errorText(cause)); }
    finally { setPending(false); }
  }

  const back = mode === 'story' ? '/story' : '/training';
  if (!briefing || !options) return <section className="section-wrap content-section custom-loading"><Link className="back-link" to={back}>← Назад</Link><div className="notice" role="status">{error || 'Загружаем сценарий…'}</div></section>;
  const ready = options.paei_profiles.length > 0 && options.difficulty_profiles.length > 0 && briefing.character !== null;
  return <div className="section-wrap custom-page mission-setup">
    <Link className="back-link" to={back}>← Назад</Link>
    <div className="custom-page-heading"><span className="eyebrow">{mode === 'story' ? 'Сюжетная сцена' : 'Тренировка'}</span><h1>{briefing.title}</h1><p>{briefing.task}</p></div>
    <div className="mission-setup-layout"><aside className="mission-character"><img src={mode === 'story' ? '/images/office-story-scene.png' : '/images/office-training-scene.png'} alt="Персонажи в офисе" /><div><span className="eyebrow">Собеседник</span><h2>{briefing.character?.name || 'Пока не назначен'}</h2><p>{briefing.character?.role_title}</p><p>{briefing.character?.description}</p></div></aside>
      <form className="custom-form" onSubmit={start}><span className="form-section-name">Перед разговором</span>
        <label>Профиль PAEI<select name="paei_profile_id" required>{options.paei_profiles.map(profile => <option value={profile.id} key={profile.id}>{profile.code} · {profile.leading_letter}</option>)}</select></label>
        <label>Сложность<select name="difficulty_profile_id" required>{options.difficulty_profiles.map(profile => <option value={profile.id} key={profile.id}>{profile.title}</option>)}</select></label>
        {!ready && <p className="form-note">Миссию можно будет начать, когда для неё добавят персонажа и профили игры.</p>}
        {error && <p className="form-error" role="alert">{error}</p>}
        {!user && !checking && <p className="form-note">Для сохранения результата нужен аккаунт.</p>}
        <button className="button primary" type="submit" disabled={!ready || pending || checking}>{pending ? 'Начинаем…' : 'Начать разговор'} <span>→</span></button>
      </form>
    </div>
  </div>;
}

export function GameDialog() {
  const { id = '' } = useParams();
  const { user, checking, openAuth } = useAuth();
  const [session, setSession] = useState<GameSession | null>(null);
  const [messages, setMessages] = useState<GameMessage[]>([]);
  const [briefing, setBriefing] = useState<MissionBriefing | null>(null);
  const [loading, setLoading] = useState(true);
  const [connection, setConnection] = useState<'connecting' | 'ready' | 'disconnected'>('connecting');
  const [reconnect, setReconnect] = useState(0);
  const [pending, setPending] = useState(false);
  const [text, setText] = useState('');
  const [error, setError] = useState('');
  const socketRef = useRef<WebSocket | null>(null);
  const pendingKey = useRef<{ text: string; key: string } | null>(null);

  useEffect(() => {
    const token = sessionStorage.getItem('arena_token');
    if (!token || !user) { setLoading(false); return; }
    const controller = new AbortController();
    setLoading(true);
    Promise.all([api.session(token, id, controller.signal), api.sessionMessages(token, id, controller.signal)])
      .then(([details, history]) => { setSession(details); setMessages(history.messages); setError(''); })
      .catch(cause => { if (cause.name !== 'AbortError') setError(errorText(cause)); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [id, user?.id]);

  useEffect(() => {
    if (!session?.mission_id) { setBriefing(null); return; }
    const controller = new AbortController();
    api.missionBriefing(session.mission_id, controller.signal).then(setBriefing).catch(() => undefined);
    return () => controller.abort();
  }, [session?.mission_id]);

  useEffect(() => {
    if (!user || session?.status !== 'active') return;
    const token = sessionStorage.getItem('arena_token');
    if (!token) return;
    const socket = new WebSocket(sessionSocketUrl(token, id));
    socketRef.current = socket;
    setConnection('connecting');
    socket.onopen = () => setConnection('ready');
    socket.onmessage = async message => {
      let event: { type?: string; code?: string; message?: string };
      try { event = JSON.parse(message.data); } catch { return; }
      if (event.type === 'state.update' || event.type === 'message.duplicate' || event.type === 'error') {
        try {
          const [details, history] = await Promise.all([api.session(token, id), api.sessionMessages(token, id)]);
          setSession(details);
          setMessages(history.messages);
          if (event.type !== 'error') { setText(''); pendingKey.current = null; }
        } catch (cause) { setError(errorText(cause)); }
        setPending(false);
      }
      if (event.type === 'error') setError(event.message || 'Не удалось обработать реплику.');
    };
    socket.onerror = () => setError('Связь с игрой прервалась. Подключитесь снова.');
    socket.onclose = () => { if (socketRef.current === socket) { socketRef.current = null; setConnection('disconnected'); setPending(false); } };
    return () => { socketRef.current = null; socket.close(); };
  }, [id, user?.id, session?.status, reconnect]);

  function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = text.trim();
    const socket = socketRef.current;
    if (!content || !socket || socket.readyState !== WebSocket.OPEN) { setError('Нет соединения с игрой. Подключитесь снова.'); return; }
    const key = pendingKey.current?.text === content ? pendingKey.current.key : crypto.randomUUID();
    pendingKey.current = { text: content, key };
    setPending(true);
    setError('');
    socket.send(JSON.stringify({ type: 'player.message', idempotency_key: key, content }));
  }

  async function finish() {
    const token = sessionStorage.getItem('arena_token');
    if (!token || !session) return;
    setPending(true);
    try {
      await api.finishSession(token, session.id);
      setSession(await api.session(token, session.id));
      setError('');
    } catch (cause) { setError(errorText(cause)); }
    finally { setPending(false); }
  }

  if (checking || loading) return <section className="section-wrap content-section custom-loading"><div className="notice" role="status">Открываем разговор…</div></section>;
  if (!user) return <section className="section-wrap content-section custom-loading"><div className="notice"><h1>Войдите, чтобы открыть разговор</h1><p>Он доступен только в аккаунте, где был начат.</p><button className="button primary" onClick={openAuth}>Войти <span>→</span></button></div></section>;
  if (!session) return <section className="section-wrap content-section custom-loading"><div className="notice error" role="alert">{error || 'Разговор не найден.'}</div><Link className="back-link" to="/training">← К тренировкам</Link></section>;

  const custom = session.custom_context;
  const back = session.mode === 'story' ? '/story' : '/training';
  const name = briefing?.character?.name || custom?.opponent_name || custom?.opponent_role || briefing?.title || 'Разговор';
  const goal = briefing?.task || custom?.goal || 'Продолжайте разговор и пробуйте разные решения.';
  const active = session.status === 'active';
  return <div className="section-wrap dialog-page">
    <Link className="back-link" to={back}>← Назад</Link>
    <div className="dialog-heading"><div><span className="eyebrow">{session.mode === 'story' ? 'Сюжет' : 'Тренировка'}</span><h1>{name}</h1><p>{briefing?.title || custom?.situation}</p></div><span className="pill">{session.state.turn || 0} реплик</span></div>
    <div className="dialog-layout"><aside className="dialog-brief"><span className="eyebrow">Ваша задача</span><h2>{goal}</h2>
      {custom && <dl><dt>Ваша роль</dt><dd>{custom.player_role}</dd><dt>Собеседник</dt><dd>{custom.opponent_role}</dd></dl>}
      {session.ai_mode !== 'mock' && <div className="game-state"><span>Контакт {session.state.contact ?? 0}</span><span>Напряжение {session.state.tension ?? 0}</span><span>Прогресс {session.state.progress ?? 0}</span></div>}
      <Link to="/training/custom" className="text-link">Новый диалог ↗</Link></aside>
      <section className="dialog-main" aria-label="Диалог"><div className="dialog-messages" aria-live="polite">
        {messages.filter(item => item.role !== 'system' && item.processing_status === 'completed').length === 0 && <p className="dialog-empty">Вы начинаете разговор. Напишите первую реплику собеседнику.</p>}
        {messages.filter(item => item.role !== 'system' && item.processing_status === 'completed').map(message => <div className={`dialog-message ${message.role}`} key={message.id}><span>{message.role === 'user' ? 'Вы' : name}</span><p>{message.content}</p></div>)}
      </div>
        {session.ai_mode === 'mock' && <p className="dialog-demo-note">Демо-режим: ответы собеседника заготовлены. Игровая оценка здесь не отражает качество переговоров.</p>}
        {active ? <form className="dialog-compose" onSubmit={send}><label htmlFor="dialog-text">Ваш ответ</label><textarea id="dialog-text" value={text} onChange={event => setText(event.target.value)} rows={3} maxLength={10000} required placeholder="Напишите, что вы скажете собеседнику…" disabled={pending} />
          {error && <p className="form-error" role="alert">{error}</p>}
          {connection === 'disconnected' && <button className="button outline" type="button" onClick={() => setReconnect(value => value + 1)}>Подключиться снова</button>}
          <div><button className="button outline" type="button" onClick={finish} disabled={pending}>Завершить</button><button className="button primary" type="submit" disabled={pending || connection !== 'ready' || !text.trim()}>{pending ? 'Ждём ответа…' : connection === 'connecting' ? 'Подключаемся…' : 'Отправить'} <span>→</span></button></div></form>
          : <div className="dialog-complete"><strong>Разговор завершён</strong><p>{session.final_result?.result === 'success' ? 'Цель достигнута.' : 'Вы можете перечитать разговор или начать новый.'}</p><Link to="/training/custom" className="button primary">Создать новый <span>↗</span></Link></div>}
      </section>
    </div>
  </div>;
}
