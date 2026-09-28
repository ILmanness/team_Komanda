import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, CharacterOption } from './api';

const paeiNames: Record<string, string> = {
  P: 'Результат', A: 'Порядок', E: 'Идеи', I: 'Люди',
};

export function CharactersPage() {
  const [characters, setCharacters] = useState<CharacterOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    api.characters(controller.signal).then(setCharacters)
      .catch(cause => { if (cause.name !== 'AbortError') setError(true); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, []);
  return <div className="section-wrap characters-page">
    <header className="characters-heading"><span className="eyebrow">Люди офиса</span><h1>Персонажи</h1><p>Познакомьтесь с коллегами до разговора: какую роль они играют, что для них важно и как они реагируют на ваши решения.</p></header>
    {loading ? <div className="notice" role="status">Знакомимся с командой…</div>
      : error ? <div className="notice error" role="alert">Не удалось загрузить персонажей. Обновите страницу.</div>
        : !characters.length ? <div className="notice">Персонажи появятся здесь после публикации.</div>
          : <div className="characters-grid">{characters.map(character => <article className="character-card" key={character.id}>
            <div className="character-portrait">{character.portrait_url
              ? <div className="character-portrait-sprite" style={{ backgroundImage: `url(${JSON.stringify(character.portrait_url)})` }} role="img" aria-label={`Портрет: ${character.name}`} />
              : <span aria-hidden="true">{character.name.slice(0, 1)}</span>}</div>
            <div className="character-card-body"><span className="eyebrow">{character.role_title || 'Персонаж'}</span><h2>{character.name}</h2>
              <p>{character.description || 'Описание появится позже.'}</p>
              {character.paei_leading_letter && <div className="character-paei"><strong>PAEI · {character.paei_leading_letter}</strong><span>{paeiNames[character.paei_leading_letter]}</span></div>}
              {character.paei_description && <p>{character.paei_description}</p>}
              {character.behavior_description && <><h3>В разговоре</h3><p>{character.behavior_description}</p></>}
            </div>
          </article>)}</div>}
    <Link className="back-link" to="/story">← К сюжету</Link>
  </div>;
}
