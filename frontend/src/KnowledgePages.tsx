import { useEffect, useMemo, useState } from 'react';
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom';
import { api, ApiError, type KnowledgeDetail, type KnowledgeItem, type KnowledgeProgress, type KnowledgeQuiz, type KnowledgeQuizResult } from './api';
import { useAuth } from './auth-context';

type Section = { title: string; paragraphs: string[] };
const emptyProgress: KnowledgeProgress = { completed_ids: [], latest_quizzes: [] };

function useLibrary() {
  const { user } = useAuth();
  const [items, setItems] = useState<KnowledgeItem[]>([]);
  const [progress, setProgress] = useState<KnowledgeProgress>(emptyProgress);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    const token = sessionStorage.getItem('arena_token');
    setLoading(true);
    Promise.all([api.knowledge(controller.signal), token && user ? api.knowledgeProgress(token, controller.signal) : Promise.resolve(emptyProgress)])
      .then(([list, state]) => { setItems(list); setProgress(state); setError(''); })
      .catch(cause => { if (cause.name !== 'AbortError') setError('Не удалось загрузить базу знаний. Попробуйте обновить страницу.'); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [user?.id]);
  return { items, progress, loading, error };
}

function useItem(id: string) {
  const [item, setItem] = useState<KnowledgeDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    api.knowledgeItem(id, controller.signal).then(value => { setItem(value); setError(''); })
      .catch(cause => { if (cause.name !== 'AbortError') setError('Материал не найден или временно недоступен.'); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [id]);
  return { item, loading, error };
}

function sections(item: KnowledgeDetail): Section[] {
  const saved = item.metadata.sections;
  if (Array.isArray(saved)) {
    const clean = saved.filter((section): section is Section =>
      typeof section === 'object' && section !== null && typeof section.title === 'string' &&
      Array.isArray(section.paragraphs) && section.paragraphs.every((paragraph: unknown) => typeof paragraph === 'string'));
    if (clean.length) return clean;
  }
  return (item.body || '').split(/\n\s*\n/).filter(Boolean).map((paragraph, index) => ({ title: index === 0 ? 'О материале' : `Часть ${index + 1}`, paragraphs: [paragraph] }));
}

function ProgressBar({ value, label }: { value: number; label: string }) {
  return <div className="knowledge-progress" role="progressbar" aria-label={label} aria-valuenow={value} aria-valuemin={0} aria-valuemax={100}>
    <span style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
  </div>;
}

function Loading({ error }: { error?: string }) {
  return <div className={`knowledge-loading${error ? ' error' : ''}`} role={error ? 'alert' : 'status'}>{error || 'Открываем материалы…'}</div>;
}

function itemPath(item: KnowledgeItem) {
  return item.slug.startsWith('test-') ? `/knowledge/${item.id}/quiz` : `/knowledge/${item.id}`;
}

function topicName(title: string) {
  return title.replace(/^Тема\s+\d+\.\s*/i, '');
}

export function KnowledgeLibrary() {
  const { user } = useAuth();
  const { items, progress, loading, error } = useLibrary();
  const topics = items.filter(item => !item.parent_id);
  const materials = items.filter(item => item.parent_id);
  const completed = new Set(progress.completed_ids);
  const completedCount = materials.filter(item => completed.has(item.id)).length;
  const percent = materials.length ? Math.round(completedCount / materials.length * 100) : 0;
  const next = materials.find(item => !completed.has(item.id));
  return <main className="knowledge-page section-wrap">
    <div className="knowledge-heading"><div><span className="eyebrow">База знаний</span><h1>Разберём по полочкам</h1><p>Короткие материалы о рабочих переговорах. Читайте в своём темпе и проверяйте себя после темы.</p></div>
      <div className="knowledge-index-stamp" aria-hidden="true">Дело<br /><strong>№ 01</strong></div></div>
    {loading ? <Loading /> : error ? <Loading error={error} /> : <>
      <section className="knowledge-overview" aria-label="Прогресс изучения"><div><span className="eyebrow">Ваш маршрут</span><h2>{user ? `${completedCount} из ${materials.length} материалов` : 'Начните с любой темы'}</h2><p>{user ? 'Прогресс сохраняется в вашем кабинете.' : 'Войдите, чтобы сохранять прочитанное и результаты самопроверки.'}</p></div>
        <div className="knowledge-overview-action"><span>{user ? `${percent}%` : `${topics.length} темы`}</span>{user && <ProgressBar value={percent} label="Общий прогресс базы знаний" />}{next && <Link className="button primary" to={itemPath(next)}>{completedCount ? 'Продолжить' : 'Начать читать'} <span>→</span></Link>}</div></section>
      <div className="knowledge-section-label"><span className="eyebrow">Содержание</span><span>{topics.length} темы</span></div>
      <div className="knowledge-topic-list">{topics.map((topic, index) => {
        const children = materials.filter(item => item.parent_id === topic.id);
        const done = children.filter(item => completed.has(item.id)).length;
        const topicPercent = children.length ? Math.round(done / children.length * 100) : 0;
        return <Link to={`/knowledge/${topic.id}`} className="knowledge-topic-card" key={topic.id}>
          <span className="knowledge-topic-number">{String(index + 1).padStart(2, '0')}</span><div className="knowledge-topic-copy"><span className="eyebrow">Тема {index + 1}</span><h2>{topicName(topic.title)}</h2><p>{topic.summary || 'Материалы и вопросы для самопроверки.'}</p><ProgressBar value={topicPercent} label={`Прогресс темы ${index + 1}`} /></div>
          <div className="knowledge-topic-meta"><span>{user ? `${done} / ${children.length}` : `${children.length} материалов`}</span><b aria-hidden="true">↗</b></div></Link>;
      })}</div>
    </>}
  </main>;
}

function TopicPage({ item }: { item: KnowledgeDetail }) {
  const { user } = useAuth();
  const { progress } = useLibrary();
  const completed = new Set(progress.completed_ids);
  const children = item.children;
  const done = children.filter(child => completed.has(child.id)).length;
  const intro = sections(item).filter(section => !/материалы темы|самопроверка|содержание/i.test(section.title)).slice(0, 1);
  return <main className="knowledge-page knowledge-topic-page section-wrap">
    <Link className="knowledge-back" to="/knowledge">← Все темы</Link>
    <header className="knowledge-heading"><div><span className="eyebrow">База знаний / тема</span><h1>{topicName(item.title)}</h1><p>{item.summary}</p></div><div className="knowledge-index-stamp" aria-hidden="true">Тема<br /><strong>{String(item.sort_order / 100).padStart(2, '0')}</strong></div></header>
    <section className="knowledge-topic-overview"><div><span className="eyebrow">О чём эта тема</span>{intro.flatMap(section => section.paragraphs).filter(paragraph => paragraph !== item.summary).slice(0, 1).map((paragraph, index) => <p key={index}>{paragraph}</p>)}</div>
      <div className="knowledge-topic-count"><strong>{user ? `${done} / ${children.length}` : `${children.length}`}</strong><span>{user ? 'пройдено' : 'материалов'}</span><ProgressBar value={children.length ? Math.round(done / children.length * 100) : 0} label="Прогресс темы" /></div></section>
    <div className="knowledge-section-label"><span className="eyebrow">Материалы темы</span><span>Читайте по порядку или выберите нужное</span></div>
    <div className="knowledge-lesson-list">{children.map((child, index) => {
      const isTest = child.slug.startsWith('test-');
      const doneItem = completed.has(child.id);
      return <Link className={`knowledge-lesson${doneItem ? ' completed' : ''}`} key={child.id} to={itemPath(child)}>
        <span className="knowledge-lesson-number">{isTest ? '?' : String(index + 1).padStart(2, '0')}</span><span className="knowledge-lesson-title"><small>{isTest ? 'Самопроверка' : 'Материал'}</small><strong>{child.title}</strong></span>
        <span className="knowledge-lesson-status">{user ? doneItem ? 'Пройдено' : 'Открыть' : 'Читать'}</span><span className="knowledge-lesson-arrow" aria-hidden="true">→</span></Link>;
    })}</div>
  </main>;
}

function ArticlePage({ item }: { item: KnowledgeDetail }) {
  const { user, openAuth } = useAuth();
  const navigate = useNavigate();
  const { items } = useLibrary();
  const [step, setStep] = useState(0);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const chunks = useMemo(() => sections(item), [item]);
  useEffect(() => { setStep(0); setError(''); }, [item.id]);
  const siblings = items.filter(sibling => sibling.parent_id === item.parent_id);
  const next = siblings[siblings.findIndex(sibling => sibling.id === item.id) + 1];
  const last = step === chunks.length - 1;
  function changeStep(value: number) {
    setStep(value);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
  async function forward() {
    if (!last) { changeStep(step + 1); return; }
    const token = sessionStorage.getItem('arena_token');
    if (!user || !token) { openAuth(); return; }
    setPending(true); setError('');
    try {
      await api.completeKnowledge(token, item.id);
      navigate(next ? itemPath(next) : `/knowledge/${item.parent_id || ''}`);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Не удалось сохранить прогресс. Повторите попытку.');
    } finally { setPending(false); }
  }
  const current = chunks[step];
  return <main className="knowledge-page knowledge-reader section-wrap">
    <Link className="knowledge-back" to={item.parent_id ? `/knowledge/${item.parent_id}` : '/knowledge'}>← К материалам темы</Link>
    <header className="knowledge-reader-heading"><span className="eyebrow">Материал {String(item.metadata.number || '')}</span><h1>{item.title}</h1><p>{item.summary}</p></header>
    {chunks.length ? <><div className="knowledge-step-head"><span>Шаг {step + 1} из {chunks.length}</span><span>{Math.round((step + 1) / chunks.length * 100)}%</span></div><ProgressBar value={(step + 1) / chunks.length * 100} label="Прогресс чтения материала" />
      <article className="knowledge-reading-card" key={`${item.id}-${step}`}><span className="eyebrow">{step === 0 ? 'Начнём' : `Часть ${step + 1}`}</span><h2>{current.title}</h2><div className="knowledge-reading-text">{current.paragraphs.map((paragraph, index) => <p key={index}>{paragraph}</p>)}</div></article>
      {error && <p className="knowledge-error" role="alert">{error}</p>}
      <nav className="knowledge-reader-nav" aria-label="Навигация по материалу"><button className="button outline" onClick={() => changeStep(step - 1)} disabled={step === 0}>← Назад</button><span className="knowledge-step-dots" aria-hidden="true">{chunks.map((_, index) => <i className={index === step ? 'active' : ''} key={index} />)}</span>
        <button className="button primary" onClick={forward} disabled={pending}>{pending ? 'Сохраняем…' : last ? user ? next ? 'К следующему' : 'Завершить' : 'Войти и сохранить' : 'Далее'} <span>→</span></button></nav>
      {!user && <p className="knowledge-save-note">Читать можно без аккаунта. Для сохранения прогресса понадобится вход.</p>}
    </> : <Loading error="В этом материале пока нет текста." />}
  </main>;
}

export function KnowledgePage() {
  const { id = '' } = useParams();
  const { item, loading, error } = useItem(id);
  if (loading) return <div className="section-wrap knowledge-page"><Loading /></div>;
  if (error || !item) return <div className="section-wrap knowledge-page"><Loading error={error} /></div>;
  if (item.metadata.kind === 'test') return <Navigate to={`/knowledge/${item.id}/quiz`} replace />;
  return item.item_type === 'topic' ? <TopicPage item={item} /> : <ArticlePage item={item} />;
}

export function KnowledgeQuizPage() {
  const { id = '' } = useParams();
  const { user, openAuth } = useAuth();
  const { item } = useItem(id);
  const { items } = useLibrary();
  const [quiz, setQuiz] = useState<KnowledgeQuiz | null>(null);
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [result, setResult] = useState<KnowledgeQuizResult | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    api.knowledgeQuiz(id, controller.signal).then(setQuiz)
      .catch(cause => { if (cause.name !== 'AbortError') setError('Не удалось открыть самопроверку.'); });
    return () => controller.abort();
  }, [id]);
  const questions = quiz?.questions || [];
  const current = questions[step];
  const topic = item?.parent_id || '';
  async function advance() {
    if (step < questions.length - 1) { setStep(step + 1); window.scrollTo({ top: 0, behavior: 'smooth' }); return; }
    const token = sessionStorage.getItem('arena_token');
    if (!user || !token) { openAuth(); return; }
    setPending(true); setError('');
    try { setResult(await api.submitKnowledgeQuiz(token, id, answers)); window.scrollTo({ top: 0, behavior: 'smooth' }); }
    catch (cause) { setError(cause instanceof ApiError ? cause.message : 'Не удалось проверить ответы. Попробуйте ещё раз.'); }
    finally { setPending(false); }
  }
  function restart() { setStep(0); setAnswers({}); setResult(null); setError(''); }
  const currentTopic = items.find(candidate => candidate.id === topic);
  const nextTopic = items.find(candidate => !candidate.parent_id && currentTopic && candidate.sort_order > currentTopic.sort_order);
  const materialLink = (number: string | null) => {
    const material = items.find(candidate => candidate.parent_id === topic && candidate.title.startsWith(`${number}.`));
    return material ? `/knowledge/${material.id}` : `/knowledge/${topic}`;
  };
  return <main className="knowledge-page knowledge-quiz-page section-wrap">
    <Link className="knowledge-back" to={topic ? `/knowledge/${topic}` : '/knowledge'}>← К материалам темы</Link>
    <header className="knowledge-reader-heading"><span className="eyebrow">База знаний / самопроверка</span><h1>Проверим себя</h1><p>{quiz?.title || 'Три вопроса из материалов темы.'} Выберите один ответ в каждом.</p></header>
    {error && <p className="knowledge-error" role="alert">{error}</p>}
    {!quiz ? !error && <Loading /> : result ? <section className="knowledge-result"><span className="eyebrow">Результат самопроверки</span><h2>{result.completed ? 'Все ответы верны' : 'Есть что повторить'}</h2><p className="knowledge-result-score">{result.score} / {result.total}</p><p>Это короткая проверка по нескольким вопросам, а не оценка всей темы. Ниже — разбор каждого ответа.</p>
      <div className="knowledge-result-list">{result.results.map((answer, index) => <div className={`knowledge-result-item${answer.is_correct ? ' right' : ''}`} key={answer.number}><strong>{index + 1}. {answer.is_correct ? 'Верно' : 'Стоит повторить'}</strong><p>{answer.explanation}</p>{!answer.is_correct && <Link to={materialLink(answer.material_id)}>Вернуться к материалу {answer.material_id} →</Link>}</div>)}</div>
      <div className="knowledge-result-actions"><button className="button outline" onClick={restart}>Пройти ещё раз</button>{nextTopic && result.completed && <Link className="button primary" to={`/knowledge/${nextTopic.id}`}>Следующая тема <span>→</span></Link>}<Link className="text-link" to={topic ? `/knowledge/${topic}` : '/knowledge'}>К теме ↗</Link></div></section>
      : questions.length ? <><div className="knowledge-step-head"><span>Вопрос {step + 1} из {questions.length}</span><span>{Math.round((step + 1) / questions.length * 100)}%</span></div><ProgressBar value={(step + 1) / questions.length * 100} label="Прогресс самопроверки" />
        <section className="knowledge-question-card"><span className="eyebrow">Вопрос {step + 1}</span><h2>{current.prompt}</h2><div className="knowledge-choices" role="radiogroup" aria-label="Варианты ответа">{current.choices.map(choice => <button type="button" role="radio" aria-checked={answers[String(current.number)] === choice.id} className={`knowledge-choice${answers[String(current.number)] === choice.id ? ' selected' : ''}`} key={choice.id} onClick={() => setAnswers(previous => ({ ...previous, [current.number]: choice.id }))}><span>{choice.id}</span><strong>{choice.text}</strong></button>)}</div></section>
        <nav className="knowledge-reader-nav" aria-label="Навигация по вопросам"><button className="button outline" disabled={step === 0} onClick={() => setStep(step - 1)}>← Назад</button><span className="knowledge-step-dots" aria-hidden="true">{questions.map((question, index) => <i className={answers[String(question.number)] ? 'answered' : index === step ? 'active' : ''} key={question.number} />)}</span>
          <button className="button primary" disabled={!answers[String(current.number)] || pending} onClick={advance}>{pending ? 'Проверяем…' : step === questions.length - 1 ? user ? 'Проверить ответы' : 'Войти и проверить' : 'Следующий вопрос'} <span>→</span></button></nav>
        {!user && <p className="knowledge-save-note">Ответить можно без аккаунта. Для проверки и сохранения результата понадобится вход.</p>}</> : <Loading error="Вопросы пока не опубликованы." />}
  </main>;
}
