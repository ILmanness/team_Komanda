import { useEffect, useState } from 'react';
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

  useEffect(() => {
    const token = sessionStorage.getItem('arena_token');
    if (!token || !user) return;
    const controller = new AbortController();
    api.branching(token, id, controller.signal).then(value => {
      setTraining(value);
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
      const next = await api.branchingChoice(token, id, training.node.node_id, optionId);
      setTraining(next);
      setFeedback(next.events.at(-1) || null);
    } catch (cause) { setError(cause instanceof ApiError ? cause.message : 'Ответ не сохранился. Попробуйте ещё раз.'); }
    finally { setPending(false); }
  }

  function continueStory() {
    if (feedback) sessionStorage.setItem(`branching-seen-${id}`, String(feedback.sequence_no));
    setFeedback(null);
  }

  if (checking) return <div className="section-wrap content-section"><div className="notice">Открываем тренировку…</div></div>;
  if (!user) return <div className="section-wrap content-section"><div className="notice"><h1>Войдите, чтобы продолжить</h1><button className="button primary" onClick={openAuth}>Войти →</button></div></div>;
  if (!training) return <div className="section-wrap content-section"><div className="notice" role="status">{error || 'Загружаем ситуацию…'}</div></div>;

  const finished = training.status !== 'active';
  const corrected = training.events.some(event => event.option_id.endsWith('_START_B') || event.option_id.endsWith('_START_C'));
  const outcome = training.node.outcome || training.final_result?.result || '';
  const resultLabel = outcome === 'success' && corrected ? 'Применено после корректировки' : resultLabels[outcome] || 'Тренировка завершена';
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
      <dt>Цель</dt><dd>{training.goal}</dd><dt>Подсказка</dt><dd>{training.tool_description}</dd>
    </dl></div></details>
    <NovelStage lines={lines} name="Старшая коллега" playerName={user.display_name} character="mentor" waiting={pending} />
    <div className="guided-layout"><section className="guided-actions">
      {feedback && <div className="guided-continue"><p>{feedback.effect || 'Ваш выбор повлиял на ход ситуации.'}</p><button className="button primary" onClick={continueStory}>{finished ? 'Посмотреть итог' : 'Продолжить'} →</button></div>}
      {!feedback && !finished && <><span className="eyebrow">Ваш выбор</span><h2>Как поступите?</h2><div className="guided-options">{training.choices.map(choice => <button type="button" key={choice.id} disabled={pending} onClick={() => choose(choice.id)}>{choice.text}<span>↗</span></button>)}</div></>}
      {!feedback && finished && <div className="guided-result"><span className="eyebrow">Итог</span><h2>{resultLabel}</h2><p>{training.node.text}</p><h3>Разбор ваших решений</h3><ol>{training.events.map(event => <li key={event.sequence_no}>{event.feedback}</li>)}</ol><p>{training.tool_description}</p><div className="guided-result-links"><Link className="button primary" to={`/training/mission/${training.mission_id}`}>Новая попытка →</Link><Link className="button outline" to="/training">К тренировкам</Link></div></div>}
      {error && <p className="form-error" role="alert">{error}</p>}
    </section></div>
    {training.events.length > 0 && <details className="guided-history"><summary>Ваши решения ({training.events.length})</summary><ol>{training.events.map(event => <li key={event.sequence_no}><strong>{event.choice_text}</strong>{finished && !feedback && event.feedback && <p>{event.feedback}</p>}</li>)}</ol></details>}
  </div>;
}
