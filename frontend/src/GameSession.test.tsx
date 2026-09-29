import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AuthContext } from './auth-context';
import { GameDialog } from './GameSession';
import { DialogueFeedback, GameSession, User, api } from './api';

afterEach(() => { cleanup(); vi.restoreAllMocks(); sessionStorage.clear(); });

it('automatically displays a saved AI review after a completed dialogue', async () => {
  const feedback: DialogueFeedback = {
    summary: 'Вы уточнили задачу и обсудили варианты.',
    strengths: [{ point: 'Задали вопрос', quote: 'Что для вас важно?' }],
    improvements: [{ point: 'Уточните срок', quote: 'Что для вас важно?', try_instead: 'Какой срок нужен?' }],
    next_step: 'Потренируйте уточнение сроков.',
  };
  const session = { id: 'session-1', mode: 'custom', status: 'completed', mission_id: null,
    ai_mode: 'compatible', custom_context: { situation: 'Рабочий разговор', goal: 'Согласовать срок' },
    state: { turn: 1 }, final_result: { result: 'finished' },
  } as GameSession;
  vi.spyOn(api, 'session').mockResolvedValue(session);
  vi.spyOn(api, 'sessionMessages').mockResolvedValue({ session_id: 'session-1', messages: [] });
  const review = vi.spyOn(api, 'sessionFeedback').mockResolvedValue(feedback);
  sessionStorage.setItem('arena_token', 'token');
  render(<AuthContext.Provider value={{ user: { id: 'user-1', display_name: 'Игрок' } as User, checking: false,
    openAuth: vi.fn(), updateUser: vi.fn() }}><MemoryRouter initialEntries={['/session/session-1']}>
    <Routes><Route path="/session/:id" element={<GameDialog />} /></Routes>
  </MemoryRouter></AuthContext.Provider>);
  expect(await screen.findByText('Вы уточнили задачу и обсудили варианты.')).toBeTruthy();
  expect(screen.getByRole('region', { name: 'Разбор разговора' })).toBeTruthy();
  expect(screen.getByText(/Какой срок нужен\?/)).toBeTruthy();
  await waitFor(() => expect(review).toHaveBeenCalledTimes(1));
});
