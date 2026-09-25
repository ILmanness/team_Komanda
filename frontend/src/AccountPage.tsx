import { FormEvent, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AccountStats, api, GameSessionSummary } from './api';
import { useAuth } from './auth-context';

const dateFormat = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' });
type Filter = 'all' | 'story' | 'method_training' | 'custom';

function resultLabel(dialog: GameSessionSummary) {
  if (dialog.status === 'active') return 'В процессе';
  if (dialog.final_result?.result === 'success') return 'Пройдено';
  if (dialog.status === 'failed' || dialog.final_result?.result === 'failure') return 'Не пройдено';
  return 'Завершено';
}

export function AccountPage() {
  const { user, checking, openAuth, updateUser } = useAuth();
  const [stats, setStats] = useState<AccountStats | null>(null);
  const [dialogs, setDialogs] = useState<GameSessionSummary[]>([]);
  const [filter, setFilter] = useState<Filter>('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [name, setName] = useState(user?.display_name || '');
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState('');

  useEffect(() => { setName(user?.display_name || ''); }, [user?.display_name]);
  useEffect(() => {
    if (!user) { setLoading(false); return; }
    const token = sessionStorage.getItem('arena_token');
    if (!token) { setLoading(false); return; }
    const controller = new AbortController();
    setLoading(true);
    Promise.all([api.accountStats(token, controller.signal), api.sessions(token, controller.signal)])
      .then(([nextStats, nextDialogs]) => { setStats(nextStats); setDialogs(nextDialogs); setError(''); })
      .catch(cause => { if (cause.name !== 'AbortError') setError('Не удалось загрузить кабинет. Попробуйте обновить страницу.'); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [user?.id]);

  async function saveName(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = sessionStorage.getItem('arena_token');
    if (!token) return;
    setSaving(true); setNotice(''); setError('');
    try { updateUser(await api.updateProfile(token, name.trim())); setNotice('Имя обновлено.'); }
    catch { setError('Не удалось изменить имя. Попробуйте ещё раз.'); }
    finally { setSaving(false); }
  }

  if (checking) return <div className="section-wrap content-section"><div className="notice">Открываем кабинет…</div></div>;
  if (!user) return <div className="section-wrap content-section"><div className="notice"><h1>Ваш кабинет</h1><p>Войдите, чтобы увидеть историю и результаты разговоров.</p><button className="button primary" onClick={openAuth}>Войти</button></div></div>;
  const visible = filter === 'all' ? dialogs : dialogs.filter(dialog => dialog.mode === filter);
  return <div className="section-wrap account-page">
    <header className="account-heading"><span className="eyebrow">Личное пространство</span><h1>Ваш кабинет</h1><p>Разговоры, результаты и ваш игровой профиль в одном месте.</p></header>
    <div className="account-grid">
      <section className="account-profile"><div className="account-portrait"><img src="/images/player-faceless.png" alt="Нарисованный персонаж игрока без черт лица" /></div><div className="account-profile-body"><span className="eyebrow">Профиль игрока</span><h2>{user.display_name}</h2><dl><dt>Логин</dt><dd>{user.login}</dd><dt>Почта</dt><dd>{user.email || 'Не указана'}</dd><dt>С нами с</dt><dd>{dateFormat.format(new Date(user.created_at))}</dd></dl><form onSubmit={saveName}><label>Отображаемое имя<input value={name} onChange={event => setName(event.target.value)} minLength={2} maxLength={120} required /></label><button type="submit" className="button outline" disabled={saving || name.trim() === user.display_name}>{saving ? 'Сохраняем…' : 'Сохранить имя'}</button></form>{notice && <p role="status" className="admin-success">{notice}</p>}</div></section>
      <section className="account-overview"><div className="account-section-title"><span className="eyebrow">Статистика</span><h2>Ваш путь</h2></div>{loading ? <div className="notice">Загружаем результаты…</div> : <div className="account-stats"><div><strong>{stats?.conversations ?? 0}</strong><span>разговоров</span></div><div><strong>{stats?.successful ?? 0}</strong><span>успешных</span></div><div><strong>{stats?.story_successes ?? 0}</strong><span>сюжетных побед</span></div><div><strong>{stats?.trainings ?? 0}</strong><span>тренировок</span></div></div>}<p>История разговоров хранится ограниченное время. Пройденные сюжетные сцены сохраняются.</p><Link className="text-link" to="/story">Продолжить сюжет ↗</Link></section>
    </div>
    {error && <div className="notice error" role="alert">{error}</div>}
    <section className="account-history"><div className="account-section-title"><span className="eyebrow">История</span><h2>Ваши разговоры</h2></div><div className="account-filters" role="group" aria-label="Фильтр разговоров">{([['all', 'Все'], ['story', 'Сюжет'], ['method_training', 'Тренировки'], ['custom', 'Свои']] as const).map(([value, label]) => <button key={value} className={filter === value ? 'active' : ''} onClick={() => setFilter(value)} aria-pressed={filter === value}>{label}</button>)}</div>
      {loading ? <div className="notice">Загружаем разговоры…</div> : visible.length ? <div className="saved-dialog-list">{visible.map(dialog => <Link className="saved-dialog" to={`/session/${dialog.id}`} key={dialog.id}><div><span className="eyebrow">{dialog.mode === 'story' ? 'Сюжет' : dialog.mode === 'method_training' ? 'Тренировка' : 'Свой диалог'} · {resultLabel(dialog)}</span><h3>{dialog.mission_title || dialog.custom_context?.opponent_name || dialog.custom_context?.opponent_role || 'Свой диалог'}</h3><p>{dateFormat.format(new Date(dialog.started_at))}</p></div><span className="saved-dialog-progress">{dialog.state.turn || 0} реплик <span aria-hidden="true">↗</span></span></Link>)}</div> : <div className="notice">{filter === 'all' ? 'Вы ещё не начинали разговоров.' : 'В этом разделе пока нет разговоров.'}</div>}
    </section>
  </div>;
}
