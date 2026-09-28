import { FormEvent, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api, ApiError, GuidedEvent, GuidedTraining } from './api';
import { useAuth } from './auth-context';

function describeError(error: unknown) {
  return error instanceof ApiError ? error.message : 'Не удалось связаться с сервером.';
}

export default function GuidedTrainingPage() {
  const { id = '' } = useParams();
  const { user, checking, openAuth } = useAuth();
  const [training, setTraining] = useState<GuidedTraining | null>(null);
  const [feedback, setFeedback] = useState<GuidedEvent | null>(null);
  const [answer, setAnswer] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');

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
    setError('');
    try {
      const next = await api.guidedChoice(token, id, training.node.id, choiceId);
      setTraining(next);
      setFeedback(next.events.at(-1) || null);
    } catch (cause) { setError(describeError(cause)); }
    finally { setPending(false); }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!training || !answer.trim()) return;
    const token = sessionStorage.getItem('arena_token');
    if (!token) return;
    setPending(true);
    setError('');
    try {
      setTraining(await api.guidedAnswer(token, id, training.node.id, answer.trim()));
    } catch (cause) { setError(describeError(cause)); }
    finally { setPending(false); }
  }

  async function retryEvaluation() {
    if (!training?.final_result?.answer) return;
    const token = sessionStorage.getItem('arena_token');
    if (!token) return;
    setPending(true);
    try { setTraining(await api.guidedAnswer(token, id, training.node.id, training.final_result.answer)); }
    catch (cause) { setError(describeError(cause)); }
    finally { setPending(false); }
  }

  function continueAfterFeedback() {
    if (feedback) sessionStorage.setItem(`guided-seen-${id}`, String(feedback.sequence_no));
    setFeedback(null);
  }

  if (checking) return <div className="section-wrap content-section"><div className="notice">Открываем тренировку…</div></div>;
  if (!user) return <div className="section-wrap content-section"><div className="notice"><h1>Войдите, чтобы продолжить</h1><button className="button primary" onClick={openAuth}>Войти →</button></div></div>;
  if (!training) return <div className="section-wrap content-section"><div className="notice" role="status">{error || 'Загружаем ситуацию…'}</div></div>;

  const last = training.events.at(-1);
  const finished = training.status !== 'active';
  const result = training.final_result;
  return <div className="section-wrap guided-page">
    <Link className="back-link" to="/training">← Все тренировки</Link>
    <header className="guided-heading"><div><span className="eyebrow">Тренировка · {training.title}</span>
      <h1>{finished ? 'Разбор тренировки' : training.node.type === 'free_text' ? 'Новая ситуация' : 'Рабочая ситуация'}</h1>
      <p>{training.node.type === 'free_text' ? 'Ответьте своими словами. Пример появится после отправки.' : 'Выберите действие. После ответа увидите, как оно повлияло на разговор.'}</p>
    </div><span className="guided-counter">{training.events.length} решений</span></header>

    {feedback && !finished && <section className="guided-feedback" aria-live="polite">
      <span className="eyebrow">После вашего выбора</span>
      <p className="guided-choice-quote">«{feedback.choice_text}»</p>
      {feedback.effect && <div className="guided-reaction"><strong>Собеседник</strong><p>{feedback.effect}</p></div>}
      <div className="guided-mentor"><strong>Наставник</strong><p>{feedback.feedback_text}</p></div>
      {feedback.transition_notice && <p className="guided-transition">{feedback.transition_notice}</p>}
      <button className="button primary" onClick={continueAfterFeedback}>Продолжить →</button>
    </section>}

    {!feedback && <div className="guided-layout"><article className="guided-scene">
      <div className="guided-scene-top"><span>{training.node.speaker}</span><span>{training.node.type === 'retry' ? 'Ещё одна попытка' : training.node.type === 'free_text' ? 'Новый эпизод' : 'Эпизод'}</span></div>
      <p>{training.node.text}</p>
      {finished && result && <div className="guided-outcome"><strong>{result.result === 'success' ? 'Все критерии выполнены' : result.result === 'needs_review' ? 'Ответ сохранён, нужна проверка' : 'Есть условия для доработки'}</strong>
        <p>Ваш ответ: {result.answer}</p></div>}
    </article>
      <section className="guided-actions">
        {!finished && training.node.type !== 'free_text' && <>
          <span className="eyebrow">Ваш ответ</span>
          <h2>Как поступите?</h2>
          <div className="guided-options">{training.choices.map(choice => <button type="button" key={choice.id} disabled={pending} onClick={() => choose(choice.id)}>{choice.text}<span>↗</span></button>)}</div>
        </>}
        {!finished && training.node.type === 'free_text' && <form onSubmit={submit} className="guided-answer">
          <label htmlFor="guided-answer">Ваше решение</label>
          <textarea id="guided-answer" rows={7} maxLength={10000} value={answer} onChange={event => setAnswer(event.target.value)} placeholder="Что вы предложите и почему?" required />
          <button className="button primary" disabled={pending || !answer.trim()}>{pending ? 'Проверяем…' : 'Отправить ответ →'}</button>
        </form>}
        {finished && <div className="guided-result">
          <span className="eyebrow">Проверка новой ситуации</span>
          {result?.criteria?.length ? <ul>{training.criteria.map(criterion => {
            const grade = result.criteria?.find(item => item.criterion_id === criterion.criterion_id);
            return <li key={criterion.criterion_id}><strong>{criterion.criterion}</strong><span>{grade?.status === 'met' ? 'Выполнено' : grade?.status === 'unclear' ? 'Нужно уточнить' : 'Не найдено в ответе'}</span>{grade?.evidence_quote && <blockquote>«{grade.evidence_quote}»</blockquote>}{grade?.reason && <p>{grade.reason}</p>}</li>;
          })}</ul> : <p>Автоматическая проверка сейчас недоступна. Ответ сохранён; результат не засчитан автоматически.</p>}
          {training.status === 'needs_review' && <button className="button outline" disabled={pending} onClick={retryEvaluation}>Повторить проверку</button>}
          {training.example_answer && <details><summary>Посмотреть пример ответа</summary><p>{training.example_answer}</p></details>}
          <div className="guided-result-links"><Link className="button primary" to="/training">К тренировкам →</Link><Link className="button outline" to="/knowledge">Повторить материал {training.material_id}</Link></div>
        </div>}
        {error && <p className="form-error" role="alert">{error}</p>}
      </section></div>}
    {training.events.length > 0 && <details className="guided-history"><summary>Ваши решения ({training.events.length})</summary><ol>{training.events.map(event => <li key={event.sequence_no}><strong>{event.choice_text}</strong><p>{event.feedback_text}</p></li>)}</ol></details>}
    {!finished && !feedback && last?.attempt_stage === 'retry' && <p className="guided-footnote">Первая попытка сохранена. Наставник показал разбор, и вы продолжаете тренировку.</p>}
  </div>;
}
