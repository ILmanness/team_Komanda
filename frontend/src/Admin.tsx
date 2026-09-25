import { FormEvent, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AdminChoice, AdminMission, AdminMissionWrite, AdminOverview, api, ApiError } from './api';
import { useAuth } from './auth-context';

type Section = 'storylines' | 'missions' | 'training' | 'characters' | 'knowledge';
type BasicKind = 'storylines' | 'characters' | 'knowledge';
const sections: { key: Section; label: string; create: string }[] = [
  { key: 'storylines', label: 'Сюжетные ветки', create: 'Новая ветка' },
  { key: 'missions', label: 'Сюжетные миссии', create: 'Новая миссия' },
  { key: 'training', label: 'Тренировки', create: 'Новая тренировка' },
  { key: 'characters', label: 'Персонажи', create: 'Новый персонаж' },
  { key: 'knowledge', label: 'Темы знаний', create: 'Новая тема' },
];
const statusLabel: Record<string, string> = { draft: 'Черновик', published: 'Опубликовано', archived: 'Архив' };

function textError(cause: unknown) {
  return cause instanceof ApiError ? cause.message : 'Не удалось сохранить. Проверьте соединение с сервером.';
}

function BasicEditor({ kind, id, overview, saved }: { kind: BasicKind; id: string | null; overview: AdminOverview; saved: (id: string) => void }) {
  const token = sessionStorage.getItem('arena_token') || '';
  const item = overview[kind].find(value => value.id === id);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const value = (name: string) => String(form.get(name) || '').trim();
    const base = { slug: value('slug'), title: value('title') };
    const body = kind === 'storylines' ? { ...base, description: value('description'), cover_url: value('cover_url') || null }
      : kind === 'characters' ? { slug: base.slug, name: value('name'), role_title: value('role_title'), description: value('description'), base_prompt: value('base_prompt') }
        : { ...base, item_type: value('item_type'), summary: value('summary'), body: value('body'), parent_id: value('parent_id') || null };
    setPending(true); setError(''); setNotice('');
    try { const result = await api.adminSave(token, kind, body, id || undefined); saved(result.id); setNotice(id ? 'Изменения сохранены.' : 'Черновик создан.'); }
    catch (cause) { setError(textError(cause)); }
    finally { setPending(false); }
  }
  async function changeStatus(status: 'draft' | 'published' | 'archived') {
    if (!id || kind === 'characters') return;
    setPending(true); setError(''); setNotice('');
    try { await api.adminStatus(token, kind, id, status); saved(id); setNotice(status === 'published' ? 'Опубликовано.' : status === 'archived' ? 'Перенесено в архив.' : 'Вернули в черновики.'); }
    catch (cause) { setError(textError(cause)); }
    finally { setPending(false); }
  }
  return <div className="admin-editor"><div className="admin-editor-heading"><span className="eyebrow">{id ? 'Редактирование' : 'Создание'}</span><h2>{kind === 'storylines' ? 'Сюжетная ветка' : kind === 'characters' ? 'Персонаж' : 'Тема знаний'}</h2></div>
    <form className="admin-form" onSubmit={submit} key={`${kind}:${id || 'new'}`}>
      <div className="admin-fields two"><label>Адресное имя<input name="slug" defaultValue={item?.slug || ''} required pattern="[a-z0-9]+(-[a-z0-9]+)*" maxLength={120} placeholder="example-story" /></label>
        {kind === 'characters' ? <label>Имя персонажа<input name="name" defaultValue={item && 'name' in item ? item.name : ''} required maxLength={160} /></label>
          : <label>Название<input name="title" defaultValue={item && 'title' in item ? item.title : ''} required maxLength={kind === 'storylines' ? 200 : 240} /></label>}</div>
      {kind === 'storylines' && <><label>Описание<textarea name="description" defaultValue={item && 'description' in item ? item.description : ''} rows={4} /></label><label>Ссылка на обложку, если есть<input name="cover_url" defaultValue={item && 'cover_url' in item ? item.cover_url || '' : ''} /></label></>}
      {kind === 'characters' && <><label>Роль в истории<input name="role_title" defaultValue={item && 'role_title' in item ? item.role_title : ''} /></label><label>Описание<textarea name="description" rows={3} defaultValue={item && 'description' in item ? item.description : ''} /></label><label>Поведение для игрового движка<textarea name="base_prompt" rows={4} defaultValue={item && 'base_prompt' in item ? item.base_prompt : ''} /></label></>}
      {kind === 'knowledge' && <><div className="admin-fields two"><label>Тип<select name="item_type" defaultValue={item && 'item_type' in item ? item.item_type : 'topic'}><option value="topic">Тема</option><option value="method">Метод</option><option value="article">Статья</option></select></label><label>Родительская тема<select name="parent_id" defaultValue={item && 'parent_id' in item ? item.parent_id || '' : ''}><option value="">Без родителя</option>{overview.knowledge.filter(value => value.id !== id).map(value => <option value={value.id} key={value.id}>{value.title}</option>)}</select></label></div><label>Краткое описание<textarea name="summary" rows={2} defaultValue={item && 'summary' in item ? item.summary : ''} /></label><label>Материал<textarea name="body" rows={5} defaultValue={item && 'body' in item ? item.body : ''} /></label></>}
      {error && <p className="form-error" role="alert">{error}</p>}{notice && <p className="admin-success" role="status">{notice}</p>}
      <div className="admin-form-actions"><button className="button primary" disabled={pending} type="submit">{pending ? 'Сохраняем…' : id ? 'Сохранить изменения' : 'Создать черновик'} <span>→</span></button>
        {id && kind !== 'characters' && <><button className="button outline" type="button" disabled={pending} onClick={() => changeStatus('published')}>Опубликовать</button><button className="button outline" type="button" disabled={pending} onClick={() => changeStatus('archived')}>В архив</button></>}</div>
    </form></div>;
}

const newChoice = (index: number): AdminChoice => ({ id: `answer_${index}`, text: '', feedback: '', quality: index === 1 ? 0.9 : 0.2, contact: 0, tension: 0, progress: index === 1 ? 70 : 5, critical_error: false });

function MissionEditor({ kind, id, overview, saved }: { kind: 'missions' | 'training'; id: string | null; overview: AdminOverview; saved: (id: string) => void }) {
  const token = sessionStorage.getItem('arena_token') || '';
  const [mission, setMission] = useState<AdminMission | null>(null);
  const [interaction, setInteraction] = useState<'ai_dialogue' | 'single_choice'>(kind === 'training' ? 'single_choice' : 'ai_dialogue');
  const [choices, setChoices] = useState<AdminChoice[]>([newChoice(1), newChoice(2)]);
  const [hints, setHints] = useState<string[]>(['']);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  useEffect(() => {
    setMission(null); setError(''); setNotice('');
    if (!id) { setInteraction(kind === 'training' ? 'single_choice' : 'ai_dialogue'); setChoices([newChoice(1), newChoice(2)]); setHints(['']); return; }
    let active = true;
    api.adminMission(token, id).then(value => { if (active) { setMission(value); setInteraction(value.interaction_type as 'ai_dialogue' | 'single_choice'); setChoices(value.config.training?.choices || [newChoice(1), newChoice(2)]); setHints(value.config.training?.hints || ['']); } })
      .catch(cause => { if (active) setError(textError(cause)); });
    return () => { active = false; };
  }, [id, kind]);

  function updateChoice(index: number, patch: Partial<AdminChoice>) { setChoices(values => values.map((choice, position) => position === index ? { ...choice, ...patch } : choice)); }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const value = (name: string) => String(form.get(name) || '').trim();
    const body: AdminMissionWrite = {
      mission_type: kind === 'training' ? 'method_training' : 'story', interaction_type: interaction,
      storyline_id: kind === 'missions' ? value('storyline_id') || null : null,
      knowledge_item_id: kind === 'training' ? value('knowledge_item_id') || null : null,
      character_id: value('character_id'), branch_key: kind === 'missions' ? value('branch_key') : null,
      order_index: kind === 'missions' ? Number(value('order_index')) : null,
      title: value('title'), situation: value('situation'), task: value('task'),
      opening_message: value('opening_message'), max_turns: interaction === 'single_choice' ? 1 : Number(value('max_turns')),
      choices: interaction === 'single_choice' ? choices.map(choice => ({ ...choice, id: choice.id.trim(), text: choice.text.trim(), feedback: choice.feedback.trim() })) : [],
      hints: kind === 'training' ? hints.map(hint => hint.trim()).filter(Boolean) : [],
    };
    setPending(true); setError(''); setNotice('');
    try { const result = await api.adminSave(token, 'missions', body, id || undefined); saved(result.id); setNotice('Сценарий сохранён.'); }
    catch (cause) { setError(textError(cause)); }
    finally { setPending(false); }
  }
  async function changeStatus(status: 'published' | 'archived') {
    if (!id) return;
    setPending(true); setError(''); setNotice('');
    try { await api.adminStatus(token, 'missions', id, status); saved(id); setNotice(status === 'published' ? 'Сценарий опубликован.' : 'Сценарий архивирован.'); }
    catch (cause) { setError(textError(cause)); }
    finally { setPending(false); }
  }
  if (id && !mission) return <div className="admin-editor"><div className="notice">{error || 'Загружаем сценарий…'}</div></div>;
  return <div className="admin-editor"><div className="admin-editor-heading"><span className="eyebrow">{id ? 'Редактирование' : 'Создание'}</span><h2>{kind === 'training' ? 'Тренировка' : 'Сюжетная миссия'}</h2></div>
    <form className="admin-form" onSubmit={submit} key={id || kind}>
      <label>Название<input name="title" defaultValue={mission?.title || ''} required maxLength={200} placeholder="Например, разговор о сроках" /></label>
      <div className="admin-fields two"><label>{kind === 'missions' ? 'Сюжетная ветка' : 'Тема знаний'}<select name={kind === 'missions' ? 'storyline_id' : 'knowledge_item_id'} defaultValue={kind === 'missions' ? mission?.storyline_id || '' : mission?.knowledge_item_id || ''} required><option value="">Выберите</option>{(kind === 'missions' ? overview.storylines : overview.knowledge).map(value => <option key={value.id} value={value.id}>{value.title} · {value.status}</option>)}</select></label>
        <label>Собеседник<select name="character_id" defaultValue={mission?.character_id || ''} required><option value="">Выберите</option>{overview.characters.map(value => <option key={value.id} value={value.id}>{value.name} · {value.role_title}</option>)}</select></label></div>
      {kind === 'missions' && <div className="admin-fields two"><label>Ключ ветки<input name="branch_key" defaultValue={mission?.branch_key || 'main'} required maxLength={80} /></label><label>Порядок<input name="order_index" type="number" min={1} defaultValue={mission?.order_index || 1} required /></label></div>}
      <label>Ситуация<textarea name="situation" defaultValue={mission?.context.situation || ''} required minLength={10} rows={3} placeholder="Что происходит в сцене" /></label>
      <label>Задача игрока<textarea name="task" defaultValue={mission?.task || ''} required minLength={5} rows={2} /></label>
      <label>Первая реплика собеседника<textarea name="opening_message" defaultValue={mission?.context.opening_message || ''} required minLength={2} rows={2} /></label>
      {kind === 'training' && <label>Формат<select value={interaction} onChange={event => setInteraction(event.target.value as 'ai_dialogue' | 'single_choice')}><option value="single_choice">Выбор ответа</option><option value="ai_dialogue">Свободный диалог</option></select></label>}
      {interaction === 'ai_dialogue' && <label>Лимит реплик<input name="max_turns" type="number" min={1} max={50} defaultValue={mission?.config.max_turns || 20} required /></label>}
      {kind === 'training' && <div className="admin-nested"><div className="admin-nested-head"><h3>Подсказки</h3><button type="button" className="button outline small" onClick={() => setHints(values => [...values, ''])} disabled={hints.length >= 5}>Добавить</button></div>{hints.map((hint, index) => <div className="admin-inline" key={index}><input value={hint} maxLength={500} onChange={event => setHints(values => values.map((item, position) => position === index ? event.target.value : item))} placeholder={`Подсказка ${index + 1}`} /><button type="button" onClick={() => setHints(values => values.filter((_, position) => position !== index))} aria-label={`Удалить подсказку ${index + 1}`}>×</button></div>)}</div>}
      {interaction === 'single_choice' && <div className="admin-nested"><div className="admin-nested-head"><div><h3>Варианты ответа</h3><p>Один ответ должен давать минимум 50 прогресса: это условие успеха в короткой тренировке.</p></div><button className="button outline small" type="button" disabled={choices.length >= 12} onClick={() => setChoices(values => [...values, newChoice(values.length + 1)])}>Добавить</button></div>
        {choices.map((choice, index) => <div className="admin-choice" key={index}><div className="admin-nested-head"><strong>Ответ {index + 1}</strong><button type="button" onClick={() => setChoices(values => values.filter((_, position) => position !== index))} disabled={choices.length <= 2}>Удалить</button></div>
          <div className="admin-fields two"><label>ID<input value={choice.id} pattern="[a-z0-9_-]+" maxLength={40} onChange={event => updateChoice(index, { id: event.target.value })} required /></label><label>Качество, от 0 до 1<input type="number" min={0} max={1} step={0.1} value={choice.quality} onChange={event => updateChoice(index, { quality: Number(event.target.value) })} required /></label></div>
          <label>Текст ответа<textarea rows={2} value={choice.text} onChange={event => updateChoice(index, { text: event.target.value })} required /></label><label>Реакция собеседника<textarea rows={2} value={choice.feedback} onChange={event => updateChoice(index, { feedback: event.target.value })} required /></label>
          <div className="admin-fields three"><label>Прогресс<input type="number" min={-100} max={100} value={choice.progress} onChange={event => updateChoice(index, { progress: Number(event.target.value) })} /></label><label>Контакт<input type="number" min={-100} max={100} value={choice.contact} onChange={event => updateChoice(index, { contact: Number(event.target.value) })} /></label><label>Напряжение<input type="number" min={-100} max={100} value={choice.tension} onChange={event => updateChoice(index, { tension: Number(event.target.value) })} /></label></div>
          <label className="admin-check"><input type="checkbox" checked={choice.critical_error} onChange={event => updateChoice(index, { critical_error: event.target.checked })} />Критическая ошибка</label>
        </div>)}</div>}
      {error && <p className="form-error" role="alert">{error}</p>}{notice && <p className="admin-success" role="status">{notice}</p>}
      <div className="admin-form-actions"><button type="submit" className="button primary" disabled={pending}>Сохранить сценарий <span>→</span></button>{id && <><button type="button" className="button outline" disabled={pending} onClick={() => changeStatus('published')}>Опубликовать</button><button type="button" className="button outline" disabled={pending} onClick={() => changeStatus('archived')}>В архив</button></>}</div>
      {id && mission?.status === 'published' && <Link className="text-link" to={kind === 'training' ? `/training/mission/${id}` : `/story/mission/${id}`}>Посмотреть как игрок ↗</Link>}
    </form></div>;
}

export function AdminPage() {
  const { user, checking, openAuth } = useAuth();
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [section, setSection] = useState<Section>('storylines');
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState('');
  const token = sessionStorage.getItem('arena_token') || '';
  async function refresh() { try { setOverview(await api.adminOverview(token)); setError(''); } catch (cause) { setError(textError(cause)); } }
  useEffect(() => { if (user?.role === 'admin') refresh(); }, [user?.id]);
  if (checking) return <div className="section-wrap content-section"><div className="notice">Проверяем доступ…</div></div>;
  if (!user) return <div className="section-wrap content-section"><div className="notice"><h1>Войдите для работы с контентом</h1><button className="button primary" onClick={openAuth}>Войти</button></div></div>;
  if (user.role !== 'admin') return <div className="section-wrap content-section"><div className="notice error">Этот раздел доступен только администратору.</div></div>;
  const active = sections.find(item => item.key === section)!;
  const list = section === 'missions' ? overview?.missions.filter(item => item.mission_type === 'story')
    : section === 'training' ? overview?.missions.filter(item => item.mission_type === 'method_training')
      : overview?.[section];
  function choose(next: Section) { setSection(next); setSelected(null); }
  function saved(id: string) { setSelected(id); refresh(); }
  return <div className="section-wrap admin-page"><div className="admin-title"><span className="eyebrow">Управление игрой</span><h1>Редактор контента</h1><p>Создавайте черновики, проверяйте их и публикуйте для игроков. Демо-материалы помечены в названии.</p></div>
    <div className="admin-tabs" role="tablist" aria-label="Разделы админки">{sections.map(item => <button key={item.key} role="tab" aria-selected={section === item.key} className={section === item.key ? 'active' : ''} onClick={() => choose(item.key)}>{item.label}</button>)}</div>
    {error && <div className="notice error" role="alert">{error}</div>}
    <div className="admin-layout"><aside className="admin-list"><div className="admin-list-head"><h2>{active.label}</h2><button className="button outline small" onClick={() => setSelected(null)}>{active.create} +</button></div>
      {!overview ? <div className="notice">Загружаем контент…</div> : list?.length ? list.map(item => <button className={`admin-list-item ${selected === item.id ? 'active' : ''}`} key={item.id} onClick={() => setSelected(item.id)}><strong>{'name' in item ? item.name : item.title}</strong><span>{'status' in item ? statusLabel[item.status] || item.status : 'Персонаж'}</span></button>) : <div className="notice">В этом разделе пока нет материалов.</div>}
    </aside>
      {overview && (section === 'missions' || section === 'training'
        ? <MissionEditor key={`${section}:${selected || 'new'}`} kind={section} id={selected} overview={overview} saved={saved} />
        : <BasicEditor key={`${section}:${selected || 'new'}`} kind={section} id={selected} overview={overview} saved={saved} />)}
    </div>
  </div>;
}
