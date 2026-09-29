import { useEffect, useRef, useState } from 'react';

export type NovelLine = { key: string; role: 'user' | 'assistant'; content: string; emotion?: string; speaker?: string };

const emotions: Record<string, string> = {
  neutral: 'Спокойно', warm: 'Доброжелательно', tense: 'Напряжённо', angry: 'Раздражённо',
};
const frames: Record<string, string> = { neutral: '0% 0%', warm: '100% 0%', tense: '0% 100%', angry: '100% 100%' };

export function NovelStage({ lines, name, playerName, character = 'anna', waiting = false }: {
  lines: NovelLine[]; name: string; playerName: string; character?: 'anna' | 'igor' | 'mentor'; waiting?: boolean;
}) {
  const [page, setPage] = useState(() => Math.max(0, lines.length - 1));
  const [shown, setShown] = useState(0);
  const previousKeys = useRef(lines.map(line => line.key));
  const current = lines[Math.min(page, lines.length - 1)];
  const content = current?.content || '';
  const complete = shown >= content.length;
  const emotion = current?.role === 'assistant' && current.emotion && current.emotion in frames ? current.emotion : 'neutral';

  useEffect(() => {
    const keys = lines.map(line => line.key);
    const oldKeys = previousKeys.current;
    // A new speaker starts at the first newly added line. Existing lines stay on
    // the page selected by the player, including while their text streams in.
    const firstNew = keys.findIndex(key => !oldKeys.includes(key));
    if (firstNew >= 0 && oldKeys.length > 0) setPage(firstNew);
    else setPage(value => Math.min(value, Math.max(0, lines.length - 1)));
    previousKeys.current = keys;
  }, [lines]);

  useEffect(() => { setShown(0); }, [current?.key]);
  useEffect(() => {
    if (!current || complete) return;
    const timer = window.setTimeout(() => setShown(value => Math.min(content.length, value + 2)), 24);
    return () => window.clearTimeout(timer);
  }, [content, shown, complete, current?.key]);

  function advance() {
    if (!complete) setShown(content.length);
    else if (page < lines.length - 1) setPage(value => value + 1);
  }

  return <section className="novel-stage" data-speaking={current?.role === 'user' ? 'player' : 'opponent'} data-character={character} aria-label="Сцена разговора">
    <div className="novel-scenery" aria-hidden="true" />
    <div className="novel-player" aria-label="Персонаж игрока"><img src="/images/player-faceless.png" alt="" /><span className="novel-character-caption">Вы</span></div>
    <div className="novel-opponent" aria-label={`Собеседник ${name}`}><div className="novel-sprite" style={{ backgroundImage: `url('/images/${character}-frames.png')`, backgroundPosition: frames[emotion] }} /><span className="novel-character-caption">{name}</span></div>
    <div className="novel-dialogue" aria-live="polite" onClick={event => { if (!(event.target as HTMLElement).closest('button')) advance(); }}><div className="novel-dialogue-head"><div><span className="novel-speaker">{current?.speaker || (current?.role === 'user' ? playerName : name)}</span>{current?.role === 'assistant' && <span className="novel-emotion">{emotions[emotion]}</span>}</div><span className="novel-count">{lines.length ? `${page + 1} / ${lines.length}` : 'Начало сцены'}</span></div>
      <p>{current ? content.slice(0, shown) : waiting ? 'Собеседник готовит ответ…' : 'Собеседник ждёт вашего первого ответа.'}{current && !complete && <span className="novel-caret" aria-hidden="true">▍</span>}</p>
      {current && <div className="novel-pages"><button type="button" onClick={() => { setPage(value => Math.max(0, value - 1)); }} disabled={page === 0}>← Назад</button><button type="button" onClick={advance} disabled={complete && page === lines.length - 1}>{complete ? 'Далее →' : 'Показать целиком →'}</button></div>}
    </div>
  </section>;
}
