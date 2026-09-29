import { FormEvent, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api, ApiError, GuidedEvent, GuidedTraining } from './api';
import { useAuth } from './auth-context';
import { NovelLine, NovelStage } from './NovelStage';

function describeError(error: unknown) {
  return error instanceof ApiError ? error.message : 'Не удалось связаться с сервером.';
}

function friendlyNotice(value: string | null) {
  return value === 'Теперь можно пересмотреть выбор с подсказкой. Первоначальный ответ сохранён.'
    ? 'Попробуй ещё раз. Если не знаешь, спроси — я расскажу.' : value;
}

export default function GuidedTrainingPage() {
  const { id = '' } = useParams();
  const { user, checking, openAuth } = useAuth();
  const [training, setTraining] = useState<GuidedTraining | null>(null);
  const [feedback, setFeedback] = useState<GuidedEvent | null>(null);
  const [answer, setAnswer] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [hintOpen, setHintOpen] = useState(false);
  const [draftChoice, setDraftChoice] = useState('');

  useEffect(() => {
    const token = sessionStorage.getItem('arena_token');
    if (!token || !user) return;
    const controller = new AbortController();
    api.guided(token, id, controller.signal).then(value => {
      setTraining(value);
      const last = value.events.at(-1);
      if (last && value.status === 'active' && Number(sessionStorage.getItem(`guided-seen-${id}`) || 0) < last.sequence_no) setFeedback(last);
    })
      .catch(cause => { if (cause.name !== 'AbortError') setError(describeError(cause)); });
    return () => controller.abort();
  }, [id, user?.id]);

  async function choose(choiceId: string) {
    if (!training || pending) return;
    const token = sessionStorage.getItem('arena_token');
    if (!token) return;
    setPending(true);
    setDraftChoice(training.choices.find(choice => choice.id === choiceId)?.text || '');
    setError('');
    try {
      const next = await api.guidedChoice(token, id, training.node.id, choiceId);
      setTraining(next);
      setFeedback(next.events.at(-1) || null);
    } catch (cause) { setError(describeError(cause)); }
    finally { setDraftChoice(''); setPending(false); }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!training || !answer.trim()) return;
    const token = sessionStorage.getItem('arena_token');
    if (!token) return;
    setPending(true);
    setDraftChoice(answer.trim());
    setError('');
    try {
      setTraining(await api.guidedAnswer(token, id, training.node.id, answer.trim()));
    } catch (cause) { setError(describeError(cause)); }
    finally { setDraftChoice(''); setPending(false); }
  }

  function continueAfterFeedback() {
    if (feedback) sessionStorage.setItem(`guided-seen-${id}`, String(feedback.sequence_no));
    setFeedback(null);
    setHintOpen(false);
  }

  if (checking) return <div className="section-wrap content-section"><div className="notice">Открываем тренировку…</div></div>;
  if (!user) return <div className="section-wrap content-section"><div className="notice"><h1>Войдите, чтобы продолжить</h1><button className="button primary" onClick={openAuth}>Войти →</button></div></div>;
  if (!training) return <div className="section-wrap content-section"><div className="notice" role="status">{error || 'Загружаем ситуацию…'}</div></div>;

  const last = training.events.at(-1);
  const finished = training.status !== 'active';
  const result = training.final_result;
  const lines: NovelLine[] = training.events.flatMap(event => {
    const exchange: NovelLine[] = [{ key: `choice-${event.sequence_no}`, role: 'user', content: event.choice_text }];
    if (event.effect) exchange.push({ key: `effect-${event.sequence_no}`, role: 'assistant', content: `Представим ответ собеседника: «${event.effect}»`, emotion: event.assessment === 'correct' ? 'warm' : 'tense' });
    exchange.push({ key: `feedback-${event.sequence_no}`, role: 'assistant', content: event.feedback_text, emotion: event.assessment === 'correct' ? 'warm' : event.assessment === 'incorrect' ? 'tense' : 'neutral' });
    if (event.transition_notice) exchange.push({ key: `transition-${event.sequence_no}`, role: 'assistant', content: friendlyNotice(event.transition_notice) || '', emotion: 'neutral' });
    return exchange;
  });
  if (draftChoice) lines.push({ key: `choice-${training.events.length + 1}`, role: 'user', content: draftChoice });
  if (!feedback && !draftChoice && !finished) {
    lines.push({ key: `node-${training.node.id}`, role: 'assistant', content: training.node.text, emotion: 'neutral' });
    if (hintOpen && training.node.goal) lines.push({ key: `hint-${training.node.id}`, role: 'assistant', content: `Подсказка: ${training.node.goal}`, emotion: 'warm' });
  }
  if (finished && result?.answer) lines.push({ key: 'final-answer', role: 'user', content: result.answer });
  return <div className="section-wrap guided-page">
    <Link className="back-link" to="/training">← Все тренировки</Link>
    <header className="guided-heading"><div><span className="eyebrow">Тренировка · {training.title}</span>
      <h1>{finished ? 'Разбор тренировки' : training.node.type === 'free_text' ? 'Новая ситуация' : 'Рабочая ситуация'}</h1>
      <p>{finished ? 'Сравните своё решение с критериями и примером.' : training.node.type === 'free_text' ? 'Ответьте своими словами. После отправки откроются критерии для самопроверки.' : 'Выберите действие. Наставница объяснит результат и даст подсказку.'}</p>
    </div><span className="guided-counter">{training.events.length} решений</span></header>

    <details className="dialog-info guided-info"><summary>Информация о тренировке <span>↗</span></summary><div className="dialog-info-content"><dl>
      <dt>Тема</dt><dd>{training.title}</dd>
      <dt>Ситуация</dt><dd>{training.node.text}</dd>
      <dt>Цель</dt><dd>{training.node.goal || 'Изучите ситуацию и выберите решение, которое учитывает интересы сторон.'}</dd>
      <dt>Наставница</dt><dd>Старшая коллега объяснит последствия выбранного ответа и подскажет, что можно улучшить.</dd>
    </dl></div></details>
    <NovelStage lines={lines} name="Старшая коллега" playerName={user.display_name} character="mentor" waiting={pending} />
    <div className={`guided-layout${finished ? ' is-finished' : ''}`}>
      <section className="guided-actions">
        {feedback && !finished && <div className="guided-continue"><p>Наставница разобрала ваш ответ. Можно переходить к следующей ситуации.</p><button className="button primary" onClick={continueAfterFeedback}>Продолжить →</button></div>}
        {!feedback && !finished && training.node.goal && <button type="button" className="guided-hint-button" aria-expanded={hintOpen} onClick={() => setHintOpen(value => !value)}>{hintOpen ? 'Убрать подсказку из сцены' : 'Попросить подсказку'} →</button>}
        {!feedback && !finished && training.node.type !== 'free_text' && <>
          <span className="eyebrow">Ваш ответ</span>
          <h2>Как поступите?</h2>
          <div className="guided-options">{training.choices.map(choice => <button type="button" key={choice.id} disabled={pending} onClick={() => choose(choice.id)}>{choice.text}<span>↗</span></button>)}</div>
        </>}
        {!feedback && !finished && training.node.type === 'free_text' && <form onSubmit={submit} className="guided-answer">
          <label htmlFor="guided-answer">Ваше решение</label>
          <textarea id="guided-answer" rows={7} maxLength={10000} value={answer} onChange={event => setAnswer(event.target.value)} placeholder="Что вы предложите и почему?" required />
          <button className="button primary" disabled={pending || !answer.trim()}>{pending ? 'Проверяем…' : 'Отправить ответ →'}</button>
        </form>}
        {finished && <div className="guided-result">
          <span className="eyebrow">Самопроверка</span>
          <p>Ответ сохранён. Тренировка использует подготовленные варианты и объяснения наставницы; нейросеть здесь не оценивает вас.</p>
          {training.criteria.length > 0 && <ul>{training.criteria.map(criterion => <li key={criterion.criterion_id}><strong>{criterion.criterion}</strong></li>)}</ul>}
          {training.example_answer && <details><summary>Посмотреть пример ответа</summary><p>{training.example_answer}</p></details>}
          <div className="guided-result-links"><Link className="button primary" to="/training">К тренировкам →</Link><Link className="button outline" to="/knowledge">Повторить материал</Link></div>
        </div>}
        {error && <p className="form-error" role="alert">{error}</p>}
      </section></div>
    {training.events.length > 0 && <details className="guided-history"><summary>Ваши решения ({training.events.length})</summary><ol>{training.events.map(event => <li key={event.sequence_no}><strong>{event.choice_text}</strong><p>{event.feedback_text}</p></li>)}</ol></details>}
    {!finished && !feedback && last?.attempt_stage === 'retry' && <p className="guided-footnote">Первая попытка сохранена. Наставник показал разбор, и вы продолжаете тренировку.</p>}
  </div>;
}
