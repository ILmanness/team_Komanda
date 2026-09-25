import { FormEvent, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api, ApiError, CustomSessionSettings } from './api';
import { useAuth } from './auth-context';

export function CustomTrainingForm() {
  const navigate = useNavigate();
  const { user, checking, openAuth } = useAuth();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = sessionStorage.getItem('arena_token');
    if (!token || !user) {
      openAuth();
      setError('Войдите, чтобы начать и сохранить свой диалог.');
      return;
    }
    const form = new FormData(event.currentTarget);
    const settings: CustomSessionSettings = {
      situation: String(form.get('situation') || '').trim(),
      player_role: String(form.get('player_role') || '').trim(),
      opponent_role: String(form.get('opponent_role') || '').trim(),
      opponent_name: String(form.get('opponent_name') || '').trim() || null,
      goal: String(form.get('goal') || '').trim(),
      tone: String(form.get('tone')) as CustomSessionSettings['tone'],
      turn_limit: Number(form.get('turn_limit')) as CustomSessionSettings['turn_limit'],
    };
    setPending(true);
    setError('');
    try {
      const session = await api.createSession(token, { mode: 'custom', custom_context: settings });
      navigate(`/session/${session.id}`);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Не удалось создать диалог. Попробуйте ещё раз.');
    } finally { setPending(false); }
  }

  return <div className="section-wrap custom-page">
    <Link className="back-link" to="/training">← К тренировкам</Link>
    <div className="custom-page-heading"><span className="eyebrow">Свой сценарий</span><h1>Создать диалог</h1><p>Задайте ситуацию и собеседника. Настройки останутся в вашем разговоре.</p></div>
    <div className="custom-layout">
      <form className="custom-form" onSubmit={submit}>
        <div className="form-section"><span className="form-section-name">Ситуация</span>
          <label>Что происходит?<textarea name="situation" required minLength={10} maxLength={2000} rows={4} placeholder="Например: команда не успевает к сроку, а руководитель просит выпустить проект без проверки." /></label>
          <div className="form-pair">
            <label>Ваша роль<input name="player_role" required minLength={2} maxLength={120} placeholder="Руководитель команды" /></label>
            <label>Роль собеседника<input name="opponent_role" required minLength={2} maxLength={120} placeholder="Заказчик проекта" /></label>
          </div>
          <label>Чего вы хотите добиться?<textarea name="goal" required minLength={10} maxLength={500} rows={2} placeholder="Согласовать новый срок и сохранить доверие заказчика." /></label>
        </div>
        <div className="form-section"><span className="form-section-name">Собеседник</span>
          <div className="form-pair">
            <label>Имя, если хотите<input name="opponent_name" maxLength={80} placeholder="Например, Анна" /></label>
            <label>Манера общения<select name="tone" defaultValue="calm"><option value="calm">Спокойная</option><option value="direct">Прямая</option><option value="resistant">Скептичная</option></select></label>
          </div>
          <label>Длина разговора<select name="turn_limit" defaultValue="10"><option value="6">Короткий · до 6 ваших реплик</option><option value="10">Обычный · до 10 реплик</option><option value="15">Длинный · до 15 реплик</option></select></label>
        </div>
        {error && <p className="form-error" role="alert">{error}</p>}
        {!user && !checking && <p className="form-note">Для начала разговора понадобится аккаунт. Поля можно заполнить до входа.</p>}
        <button className="button primary" type="submit" disabled={pending || checking}>{pending ? 'Создаём диалог…' : 'Начать разговор'} <span>→</span></button>
      </form>
      <aside className="custom-preview"><img src="/images/office-training-scene.png" alt="Собеседница в офисной переговорной" /><div><span className="eyebrow">Один на один</span><h2>Сцену задаёте вы</h2><p>Разговор сохранится в вашем аккаунте.</p></div></aside>
    </div>
  </div>;
}
