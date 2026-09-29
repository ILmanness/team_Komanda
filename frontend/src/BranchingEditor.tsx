import { FormEvent, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AdminBranchingNode, AdminBranchingOption, AdminBranchingScenario, AdminBranchingTool, AdminMission, AdminMissionWrite, AdminOverview, api, ApiError } from './api';

const uid = () => crypto.randomUUID().slice(0, 8);
const blankOption = (target: string): AdminBranchingOption => ({ id: `answer_${uid()}`, text: '', effect: null, flag: null, feedback: '', next_node: target });
function blankScenario(): AdminBranchingScenario {
  const start = `scene_${uid()}`;
  const success = `ending_${uid()}`;
  const failure = `ending_${uid()}`;
  return { id: `scenario_${uid()}`, title: '', goal: '', start_node_id: start, weight: 1, status: 'active', nodes: {
    [start]: { node_id: start, type: 'decision', speaker: 'Старшая коллега', text: '', outcome: null, options: [blankOption(success), blankOption(failure)] },
    [success]: { node_id: success, type: 'terminal', speaker: 'Итог', text: '', outcome: 'success', options: [] },
    [failure]: { node_id: failure, type: 'terminal', speaker: 'Итог', text: '', outcome: 'fail', options: [] },
  } };
}
const blankTool = (): AdminBranchingTool => ({ id: `custom_${uid()}`, category: 'methods', title: '', description: '', order: 1, scenarios: [blankScenario()] });
const message = (cause: unknown) => cause instanceof ApiError ? cause.message : 'Не удалось сохранить тренировку. Проверьте соединение с сервером.';

export function BranchingEditor({ id, overview, saved }: { id: string | null; overview: AdminOverview; saved: (id: string) => void }) {
  const token = sessionStorage.getItem('arena_token') || '';
  const [mission, setMission] = useState<AdminMission | null>(null);
  const [tool, setTool] = useState<AdminBranchingTool>(blankTool);
  const [knowledgeId, setKnowledgeId] = useState('');
  const [characterId, setCharacterId] = useState('');
  const [activeScenario, setActiveScenario] = useState(0);
  const [activeNode, setActiveNode] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  useEffect(() => {
    let active = true;
    setMission(null); setError(''); setNotice('');
    if (!id) {
      const draft = blankTool();
      draft.order = Math.max(0, ...overview.missions.filter(item => item.branch_key === 'methods').map(item => item.order_index || 0)) + 1;
      setTool(draft);
      setActiveScenario(0); setActiveNode(draft.scenarios[0].start_node_id);
      setKnowledgeId(overview.knowledge.find(item => item.slug === 'topic-3')?.id || '');
      setCharacterId(overview.characters.find(item => item.slug === 'training-mentor')?.id || '');
    } else {
      api.adminMission(token, id).then(value => {
        if (!active) return;
        setMission(value);
        if (value.config.branching) { setTool(value.config.branching); setActiveScenario(0); setActiveNode(value.config.branching.scenarios[0].start_node_id); }
        setKnowledgeId(value.knowledge_item_id || '');
        setCharacterId(value.character_id || '');
      }).catch(cause => { if (active) setError(message(cause)); });
    }
    return () => { active = false; };
  }, [id, overview]);

  function change(update: (value: AdminBranchingTool) => void) {
    setTool(previous => { const next = structuredClone(previous); update(next); return next; });
    setNotice('');
  }
  function scenario(index: number, update: (value: AdminBranchingScenario) => void) {
    change(value => update(value.scenarios[index]));
  }
  function node(scenarioIndex: number, nodeId: string, update: (value: AdminBranchingNode) => void) {
    scenario(scenarioIndex, value => update(value.nodes[nodeId]));
  }
  function option(scenarioIndex: number, nodeId: string, optionIndex: number, update: (value: AdminBranchingOption) => void) {
    node(scenarioIndex, nodeId, value => update(value.options[optionIndex]));
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(''); setNotice('');
    const first = tool.scenarios[0]?.nodes[tool.scenarios[0]?.start_node_id];
    const body: AdminMissionWrite = {
      mission_type: 'method_training', interaction_type: 'branching_training', storyline_id: null,
      knowledge_item_id: knowledgeId, character_id: characterId, branch_key: tool.category,
      order_index: tool.order, title: tool.title.trim(), task: tool.description.trim(),
      situation: first?.text.trim() || '', public_context: first?.text.trim() || '',
      opening_message: first?.text.trim() || '', max_turns: 1, choices: [], hints: [], guided: null,
      branching: { ...tool, title: tool.title.trim(), description: tool.description.trim(),
        scenarios: tool.scenarios.map(item => ({ ...item, title: item.title.trim(), goal: item.goal.trim(),
          nodes: Object.fromEntries(Object.entries(item.nodes).map(([key, value]) => [key, {
            ...value, speaker: value.speaker.trim(), text: value.text.trim(),
            options: value.options.map(answer => ({ ...answer, text: answer.text.trim(), feedback: answer.feedback.trim(), effect: answer.effect?.trim() || null, flag: answer.flag?.trim() || null })),
          }])) })) },
    };
    setPending(true);
    try {
      const result = await api.adminSave(token, 'missions', body, id || undefined);
      saved(result.id); setNotice('Тренировка сохранена.');
    } catch (cause) { setError(message(cause)); }
    finally { setPending(false); }
  }
  async function status(next: 'published' | 'archived') {
    if (!id) return;
    setPending(true); setError(''); setNotice('');
    try { await api.adminStatus(token, 'missions', id, next); saved(id); setNotice(next === 'published' ? 'Тренировка опубликована.' : 'Тренировка архивирована.'); }
    catch (cause) { setError(message(cause)); }
    finally { setPending(false); }
  }
  if (id && !mission) return <div className="admin-editor"><div className="notice">{error || 'Загружаем тренировку…'}</div></div>;
  return <div className="admin-editor branching-editor"><div className="admin-editor-heading"><span className="eyebrow">{id ? 'Редактирование' : 'Создание'}</span><h2>Тренировка: методы и принципы</h2><p>Составьте ситуации, ответы и последствия. Игрок увидит один активный сценарий за запуск.</p></div>
    <form className="admin-form" onSubmit={submit}>
      <div className="admin-fields two"><label>Раздел<select value={tool.category} onChange={event => {
        const category = event.target.value as AdminBranchingTool['category'];
        change(value => { value.category = category; value.order = Math.max(0, ...overview.missions.filter(item => item.branch_key === category && item.id !== id).map(item => item.order_index || 0)) + 1; });
        setKnowledgeId(overview.knowledge.find(item => item.slug === (category === 'methods' ? 'topic-3' : 'topic-2'))?.id || '');
      }}><option value="methods">Методы</option><option value="principles">Принципы</option></select></label>
        <label>Порядок в разделе<input type="number" min={1} max={32767} value={tool.order} onChange={event => change(value => { value.order = Number(event.target.value); })} required /></label></div>
      <label>Название метода или принципа<input value={tool.title} onChange={event => change(value => { value.title = event.target.value; })} required minLength={2} maxLength={200} /></label>
      <label>Описание для каталога<textarea value={tool.description} onChange={event => change(value => { value.description = event.target.value; })} required minLength={5} maxLength={5000} rows={2} /></label>
      <div className="admin-fields two"><label>Тема базы знаний<select value={knowledgeId} onChange={event => setKnowledgeId(event.target.value)} required><option value="">Выберите тему</option>{overview.knowledge.map(item => <option key={item.id} value={item.id}>{item.title} · {item.status}</option>)}</select></label>
        <label>Персонаж<select value={characterId} onChange={event => setCharacterId(event.target.value)} required><option value="">Выберите персонажа</option>{overview.characters.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label></div>
      <div className="admin-nested-head"><div><h3>Сценарии</h3><p>Для разных запусков можно задать несколько ситуаций. Вес определяет частоту выбора.</p></div><button type="button" className="button outline small" onClick={() => { const draft = blankScenario(); change(value => { value.scenarios.push(draft); }); setActiveScenario(tool.scenarios.length); setActiveNode(draft.start_node_id); }}>Добавить ситуацию</button></div>
      <div className="branching-tabs" role="group" aria-label="Сценарии тренировки">{tool.scenarios.map((item, index) => <button type="button" key={item.id} className={activeScenario === index ? 'active' : ''} onClick={() => { setActiveScenario(index); setActiveNode(item.start_node_id); }}>{index + 1}. {item.title || 'Новая ситуация'}</button>)}</div>
      {tool.scenarios.map((item, scenarioIndex) => scenarioIndex === activeScenario ? <section className="admin-choice branching-scenario" key={item.id}>
        <div className="admin-nested-head"><h3>Ситуация {scenarioIndex + 1}</h3><button type="button" disabled={tool.scenarios.length === 1} onClick={() => { change(value => { value.scenarios.splice(scenarioIndex, 1); }); setActiveScenario(0); setActiveNode(tool.scenarios[scenarioIndex === 0 ? 1 : 0].start_node_id); }}>Удалить</button></div>
        <div className="admin-fields two"><label>Название<input value={item.title} onChange={event => scenario(scenarioIndex, value => { value.title = event.target.value; })} required minLength={2} maxLength={200} /></label>
          <label>Цель игрока<input value={item.goal} onChange={event => scenario(scenarioIndex, value => { value.goal = event.target.value; })} required minLength={5} maxLength={1000} /></label></div>
        <div className="admin-fields three"><label>Начальная сцена<select value={item.start_node_id} onChange={event => scenario(scenarioIndex, value => { value.start_node_id = event.target.value; })}>{Object.values(item.nodes).filter(value => value.type !== 'terminal').map(value => <option key={value.node_id} value={value.node_id}>{value.node_id} · {value.text.slice(0, 35)}</option>)}</select></label>
          <label>Частота<input type="number" min={1} max={100} value={item.weight} onChange={event => scenario(scenarioIndex, value => { value.weight = Number(event.target.value); })} required /></label>
          <label>Доступность<select value={item.status} onChange={event => scenario(scenarioIndex, value => { value.status = event.target.value as 'active' | 'inactive'; })}><option value="active">Активна</option><option value="inactive">Скрыта</option></select></label></div>
        <div className="admin-nested-head"><h3>Сцены и развилки</h3><div className="admin-inline"><button type="button" className="button outline small" onClick={() => { const key = `scene_${uid()}`; scenario(scenarioIndex, value => { const target = Object.values(value.nodes).find(node => node.type === 'terminal')?.node_id || value.start_node_id; value.nodes[key] = { node_id: key, type: 'consequence', speaker: 'Собеседник', text: '', outcome: null, options: [blankOption(target), blankOption(target)] }; }); setActiveNode(key); }}>Добавить развилку</button><button type="button" className="button outline small" onClick={() => { const key = `ending_${uid()}`; scenario(scenarioIndex, value => { value.nodes[key] = { node_id: key, type: 'terminal', speaker: 'Итог', text: '', outcome: 'partial', options: [] }; }); setActiveNode(key); }}>Добавить итог</button></div></div>
        <div className="branching-tabs" role="group" aria-label="Сцены сценария">{Object.values(item.nodes).map((scene, index) => <button type="button" key={scene.node_id} className={activeNode === scene.node_id ? 'active' : ''} onClick={() => setActiveNode(scene.node_id)}>{index + 1}. {scene.type === 'terminal' ? 'Итог' : scene.text.slice(0, 40) || 'Новая сцена'}</button>)}</div>
        {Object.values(item.nodes).map((scene, sceneIndex) => scene.node_id === activeNode ? <div className="admin-choice branching-node" key={scene.node_id}>
          <div className="admin-nested-head"><h4>{scene.type === 'terminal' ? 'Итог' : 'Развилка'} {sceneIndex + 1} <small>{scene.node_id}</small></h4><button type="button" disabled={scene.node_id === item.start_node_id || Object.values(item.nodes).some(other => other.options.some(answer => answer.next_node === scene.node_id))} onClick={() => { scenario(scenarioIndex, value => { delete value.nodes[scene.node_id]; }); setActiveNode(item.start_node_id); }}>Удалить</button></div>
          <div className="admin-fields two"><label>Тип сцены<select value={scene.type} onChange={event => node(scenarioIndex, scene.node_id, value => { const type = event.target.value as AdminBranchingNode['type']; value.type = type; value.outcome = type === 'terminal' ? 'partial' : null; const target = Object.values(item.nodes).find(target => target.type === 'terminal' && target.node_id !== scene.node_id)?.node_id || item.start_node_id; value.options = type === 'terminal' ? [] : [blankOption(target), blankOption(target)]; })}><option value="decision">Выбор</option><option value="consequence">Последствие</option><option value="terminal">Итог</option></select></label>
            <label>Говорящий<input value={scene.speaker} onChange={event => node(scenarioIndex, scene.node_id, value => { value.speaker = event.target.value; })} required minLength={2} maxLength={160} /></label></div>
          <label>Текст сцены<textarea value={scene.text} onChange={event => node(scenarioIndex, scene.node_id, value => { value.text = event.target.value; })} required minLength={2} maxLength={3000} rows={3} /></label>
          {scene.type === 'terminal' ? <label>Результат<select value={scene.outcome || 'partial'} onChange={event => node(scenarioIndex, scene.node_id, value => { value.outcome = event.target.value as AdminBranchingNode['outcome']; })}><option value="success">Успех</option><option value="partial">Частичный успех</option><option value="fail">Неудача</option><option value="not_applied">Метод не применён</option></select></label> : <>
            <div className="admin-nested-head"><h4>Ответы игрока</h4><button type="button" disabled={scene.options.length >= 12} onClick={() => node(scenarioIndex, scene.node_id, value => { value.options.push(blankOption(Object.values(item.nodes).find(target => target.type === 'terminal')?.node_id || item.start_node_id)); })}>Добавить ответ</button></div>
            {scene.options.map((answer, answerIndex) => <div className="admin-choice branching-answer" key={answer.id}><div className="admin-nested-head"><strong>Ответ {answerIndex + 1}</strong><button type="button" disabled={scene.options.length <= 2} onClick={() => node(scenarioIndex, scene.node_id, value => { value.options.splice(answerIndex, 1); })}>Удалить</button></div>
              <label>Реплика игрока<textarea value={answer.text} onChange={event => option(scenarioIndex, scene.node_id, answerIndex, value => { value.text = event.target.value; })} required minLength={2} maxLength={1000} rows={2} /></label>
              <label>Реакция собеседника<textarea value={answer.effect || ''} onChange={event => option(scenarioIndex, scene.node_id, answerIndex, value => { value.effect = event.target.value; })} maxLength={2000} rows={2} /></label>
              <label>Разбор после завершения<textarea value={answer.feedback} onChange={event => option(scenarioIndex, scene.node_id, answerIndex, value => { value.feedback = event.target.value; })} required minLength={2} maxLength={2000} rows={2} /></label>
              <div className="admin-fields two"><label>Следующая сцена<select value={answer.next_node} onChange={event => option(scenarioIndex, scene.node_id, answerIndex, value => { value.next_node = event.target.value; })}>{Object.values(item.nodes).filter(target => target.node_id !== scene.node_id).map(target => <option key={target.node_id} value={target.node_id}>{target.node_id} · {target.text.slice(0, 45)}</option>)}</select></label>
                <label>Метка для аналитики<input value={answer.flag || ''} onChange={event => option(scenarioIndex, scene.node_id, answerIndex, value => { value.flag = event.target.value; })} maxLength={100} /></label></div>
            </div>)}
          </>}
        </div> : null)}
      </section> : null)}
      <p className="form-note">Все сцены должны быть достижимы из начальной; переходы не должны образовывать цикл. Разбор ответов игрок увидит в конце сценария.</p>
      {error && <p className="form-error" role="alert">{error}</p>}{notice && <p className="admin-success" role="status">{notice}</p>}
      <div className="admin-form-actions"><button className="button primary" disabled={pending} type="submit">Сохранить тренировку →</button>{id && <><button type="button" className="button outline" disabled={pending} onClick={() => status('published')}>Опубликовать</button><button type="button" className="button outline" disabled={pending} onClick={() => status('archived')}>В архив</button></>}</div>
      {id && mission?.status === 'published' && <Link className="text-link" to={`/training/mission/${id}`}>Посмотреть как игрок ↗</Link>}
    </form></div>;
}
