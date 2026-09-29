import { useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api, ApiError, BranchingEvent, BranchingTraining } from './api';
import { useAuth } from './auth-context';
import { NovelLine, NovelStage } from './NovelStage';

const resultLabels: Record<string, string> = {
  success: 'Применено с первого прохода', partial: 'Применено частично',
  fail: 'Применение не завершено', not_applied: 'Применение не завершено',
};

export default function BranchingTrainingPage() {
  const { id = '' } = useParams();
  const { user, checking, openAuth } = useAuth();
  const [training, setTraining] = useState<BranchingTraining | null>(null);
  const [feedback, setFeedback] = useState<BranchingEvent | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [showCard, setShowCard] = useState(false);
  const [showHint, setShowHint] = useState(false);
  const retryKey = useRef<{ node: string; option: string; id: string } | null>(null);

  useEffect(() => {
    const token = sessionStorage.getItem('arena_token');
    if (!token || !user) return;
    const controller = new AbortController();
    api.branching(token, id, controller.signal).then(value => {
      setTraining(value);
      setShowCard(value.content_version === '3.0' && !value.card_seen);
      const last = value.events.at(-1);
      if (last && Number(sessionStorage.getItem(`branching-seen-${id}`) || 0) < last.sequence_no) setFeedback(last);
    }).catch(cause => { if (cause.name !== 'AbortError') setError(cause instanceof ApiError ? cause.message : 'Не удалось открыть тренировку.'); });
    return () => controller.abort();
  }, [id, user?.id]);

  async function choose(optionId: string) {
    if (!training || pending) return;
    const token = sessionStorage.getItem('arena_token');
    if (!token) return;
    setPending(true);
    setError('');
    try {
      const eventId = training.content_version === '3.0'
        ? (retryKey.current?.node === training.node.node_id && retryKey.current?.option === optionId
          ? retryKey.current.id : crypto.randomUUID()) : undefined;
      if (eventId) retryKey.current = { node: training.node.node_id, option: optionId, id: eventId };
      const next = await api.branchingChoice(token, id, training.node.node_id, optionId, eventId);
      setTraining(next);
      setFeedback(next.events.at(-1) || null);
      setShowHint(false);
      retryKey.current = null;
    } catch (cause) { setError(cause instanceof ApiError ? cause.message : 'Ответ не сохранился. Попробуйте ещё раз.'); }
    finally { setPending(false); }
  }

  async function aid(kind: 'intro' | 'card' | 'hint') {
    const token = sessionStorage.getItem('arena_token');
    if (!token || pending || !training) return;
    setPending(true); setError('');
    try {
      const next = await api.branchingAid(token, id, kind, kind === 'hint' ? training.node.node_id : undefined);
      setTraining(next);
      if (kind === 'intro') setShowCard(false);
      if (kind === 'card') setShowCard(true);
      if (kind === 'hint') setShowHint(true);
    } catch (cause) { setError(cause instanceof ApiError ? cause.message : 'Не удалось открыть подсказку.'); }
    finally { setPending(false); }
  }

  function continueStory() {
    if (feedback) sessionStorage.setItem(`branching-seen-${id}`, String(feedback.sequence_no));
    setFeedback(null);
    setShowHint(false);
  }

  if (checking) return <div className="section-wrap content-section"><div className="notice">Открываем тренировку…</div></div>;
  if (!user) return <div className="section-wrap content-section"><div className="notice"><h1>Войдите, чтобы продолжить</h1><button className="button primary" onClick={openAuth}>Войти →</button></div></div>;
  if (!training) return <div className="section-wrap content-section"><div className="notice" role="status">{error || 'Загружаем ситуацию…'}</div></div>;

  const finished = training.status !== 'active';
  const isV3 = training.content_version === '3.0';
  const corrected = training.events.some(event => event.option_id.endsWith('_START_B') || event.option_id.endsWith('_START_C'));
  const outcome = training.node.outcome || training.final_result?.result || '';
  const resultLabel = isV3 ? training.final_result?.application || 'Тренировка завершена'
    : outcome === 'success' && corrected ? 'Применено после корректировки' : resultLabels[outcome] || 'Тренировка завершена';
  const lines: NovelLine[] = training.events.flatMap(event => {
    const result: NovelLine[] = [{ key: `choice-${event.sequence_no}`, role: 'user', content: event.choice_text }];
    if (event.effect) result.push({ key: `effect-${event.sequence_no}`, role: 'assistant', content: event.effect, emotion: 'neutral' });
    if (finished && !feedback && event.feedback) result.push({ key: `feedback-${event.sequence_no}`, role: 'assistant', content: event.feedback, emotion: 'warm' });
    return result;
  });
  if (!feedback) lines.push({ key: `node-${training.node.node_id}`, role: 'assistant', content: training.node.text, emotion: 'neutral' });

  return <div className="section-wrap guided-page">
    <Link className="back-link" to="/training">← Все тренировки</Link>
    <header className="guided-heading"><div><span className="eyebrow">{training.category === 'methods' ? 'Метод' : 'Принцип'} · {training.tool_title}</span>
      <h1>{finished && !feedback ? resultLabel : training.scenario_title}</h1>
      <p>{finished && !feedback ? 'Посмотрите, к чему привели ваши решения.' : 'Читайте последствия и выбирайте следующий шаг в разговоре.'}</p>
    </div><span className="guided-counter">{training.events.length} решений</span></header>
    <details className="dialog-info guided-info"><summary>Информация о тренировке <span>↗</span></summary><div className="dialog-info-content"><dl>
      <dt>Инструмент</dt><dd>{training.tool_title}</dd><dt>Ситуация</dt><dd>{training.scenario_title}</dd>
      <dt>Цель</dt><dd>{training.goal}</dd><dt>Режим</dt><dd>{training.mode === 'practice' ? 'Практика' : 'Обучение'}</dd>
    </dl></div></details>
    {isV3 && !showCard && <button type="button" className="button outline small" onClick={() => void aid('card')} disabled={pending}>Карточка инструмента</button>}
    {showCard && training.card ? <section className="training-card" aria-label="Карточка инструмента">
      <span className="eyebrow">Перед тренировкой</span><h2>{training.tool_title}</h2>
      <dl><dt>Суть</dt><dd>{training.card.essence}</dd><dt>Когда применять</dt><dd>{training.card.when_to_apply}</dd>
        <dt>Шаги применения</dt><dd>{training.card.steps}</dd><dt>Типичная ошибка</dt><dd>{training.card.typical_error}</dd>
        <dt>Пример</dt><dd>{training.card.example}</dd><dt>Граница применения</dt><dd>{training.card.limit}</dd></dl>
      <button type="button" className="button primary" disabled={pending}
        onClick={() => training.card_seen ? setShowCard(false) : void aid('intro')}>{training.card_seen ? 'Вернуться к ситуации' : 'Начать тренировку'} →</button>
      {!training.card_seen && <button type="button" className="button outline" disabled={pending} onClick={() => void aid('intro')}>Пропустить карточку</button>}
      {error && <p className="form-error" role="alert">{error}</p>}
    </section> : <>
    <NovelStage lines={lines} name="Старшая коллега" playerName={user.display_name} character="mentor" waiting={pending} />
    <div className="guided-layout"><section className="guided-actions">
      {feedback && <div className="guided-continue">
        <p>{feedback.effect || 'Последствие этого выбора появилось в следующей сцене.'}</p>
        {isV3 && training.mode === 'learning' && feedback.feedback && <p><strong>Разбор наставницы:</strong> {feedback.feedback}</p>}
        <button className="button primary" onClick={continueStory}>{finished ? 'Посмотреть итог' : 'Продолжить'} →</button>
      </div>}
      {!feedback && !finished && <>
        {isV3 && training.mode === 'learning' && training.node.skill_step && <p className="training-step"><strong>Шаг:</strong> {training.node.skill_step}</p>}
        {isV3 && <div className="training-hint">
          <button type="button" className="button outline small" onClick={() => void aid('hint')} disabled={pending}>Попросить подсказку</button>
          {showHint && training.node.hint && <p>{training.node.hint}</p>}
        </div>}
        <span className="eyebrow">Ваш выбор</span><h2>Как поступите?</h2>
        <div className="guided-options">{training.choices.map(choice => <button type="button" key={choice.id} disabled={pending} onClick={() => choose(choice.id)}>{choice.text}<span>↗</span></button>)}</div>
      </>}
      {!feedback && finished && <div className="guided-result"><span className="eyebrow">Итог</span><h2>{resultLabel}</h2>
        <p>{isV3 ? training.final_result?.outcome_text : training.node.text}</p>
        {isV3 ? <>
          <h3>Последствия ваших решений</h3>
          {training.final_result?.consequences?.length
            ? <ol>{training.final_result.consequences.map((item, index) => <li key={index}>{item}</li>)}</ol>
            : <p>Дополнительных последствий в этой попытке не зафиксировано.</p>}
          <h3>Шаги инструмента</h3>
          <ol>{Object.entries(training.final_result?.step_results || {}).map(([step, status]) =>
            <li key={step}>{step.replace(/^.*?_N(\d+)$/, 'Шаг $1')}: {{
              independent: 'применено самостоятельно', corrected: 'после исправления',
              not_yet_applied: 'не завершён', not_checked: 'не проверено',
            }[status] || status}</li>)}</ol>
          <h3>Персональный разбор</h3>
          <ol>{training.events.map(event => <li key={event.sequence_no}><strong>{event.debrief?.step || 'Ваш выбор'}:</strong> {event.choice_text}
            <p>{event.debrief?.explanation || event.feedback}</p>{event.debrief?.improvement && <p>Как попробовать иначе: {event.debrief.improvement}</p>}</li>)}</ol>
          {training.final_result?.repeat && <p>{training.final_result.repeat}</p>}
        </> : <><h3>Разбор ваших решений</h3><ol>{training.events.map(event => <li key={event.sequence_no}>{event.feedback}</li>)}</ol><p>{training.tool_description}</p></>}
        <div className="guided-result-links"><Link className="button primary" to={`/training/mission/${training.mission_id}`}>Новая попытка →</Link><Link className="button outline" to="/training">К тренировкам</Link></div>
      </div>}
      {error && <p className="form-error" role="alert">{error}</p>}
    </section></div>
    {training.events.length > 0 && <details className="guided-history"><summary>Ваши решения ({training.events.length})</summary><ol>{training.events.map(event => <li key={event.sequence_no}><strong>{event.choice_text}</strong>{finished && !feedback && event.feedback && <p>{event.feedback}</p>}</li>)}</ol></details>}
    </>}
  </div>;
}
