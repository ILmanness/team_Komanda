import { useEffect, useState } from 'react';

export default function App() {
  const [status, setStatus] = useState('Проверяем backend и БД…');
  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/health/ready', { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error('Backend не готов');
        const data = await response.json();
        setStatus(`Backend и PostgreSQL готовы. AI: ${data.ai_provider}`);
      })
      .catch((error: Error) => {
        if (error.name !== 'AbortError') setStatus('Backend недоступен. Проверьте docker compose logs backend.');
      });
    return () => controller.abort();
  }, []);
  return <main style={{ maxWidth: 760, margin: '80px auto', padding: 24, fontFamily: 'system-ui' }}>
    <h1>Арена переговоров</h1>
    <p role="status">{status}</p>
    <p>Окружение разработки готово. Игровой интерфейс и обработчик ходов ещё предстоит реализовать.</p>
    <a href="/api/docs">Документация backend API</a>
  </main>;
}
