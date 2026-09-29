import React from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import App from './App';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); sessionStorage.clear(); });

function renderAt(path: string) {
  vi.stubGlobal('scrollTo', vi.fn());
  return render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
}

it('shows four independent modes without icons or step numbers', () => {
  renderAt('/');
  expect(screen.getByRole('heading', { name: /Зайдите в кабинет.*Начните разговор/ })).toBeTruthy();
  const cards = document.querySelectorAll('.module-card');
  expect(cards).toHaveLength(4);
  expect(Array.from(cards).map(card => card.querySelector('h3')?.textContent)).toEqual(['Сюжет', 'Тренировка', 'База знаний', 'PvP']);
  expect(document.querySelector('.module-icon')).toBeNull();
  expect(document.querySelector('.module-number')).toBeNull();
});

it('keeps the home page available when the backend is unavailable', () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
  renderAt('/');
  expect(screen.getByRole('heading', { name: 'Выберите свою игру' })).toBeTruthy();
});

it('loads training missions from the catalog and explains an empty response', async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => [] });
  vi.stubGlobal('fetch', fetchMock);
  renderAt('/training');
  expect(await screen.findByText(/Опубликованных тренировок пока нет/)).toBeTruthy();
  expect(fetchMock).toHaveBeenCalledWith('/api/v1/missions?mission_type=method_training', expect.anything());
});

it('shows methods and principles in their editorial order', async () => {
  const missions = [
    { id: 'batna', title: 'BATNA', interaction_type: 'branching_training', branch_key: 'methods', order_index: 2 },
    { id: 'pareto', title: 'Принцип Парето', interaction_type: 'branching_training', branch_key: 'principles', order_index: 1 },
    { id: 'harvard', title: 'Гарвардский метод', interaction_type: 'branching_training', branch_key: 'methods', order_index: 1 },
  ];
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => missions }));
  renderAt('/training');
  const methods = await screen.findByRole('region', { name: 'Методы' });
  const principles = screen.getByRole('region', { name: 'Принципы' });
  expect(within(methods).getAllByRole('link').map(link => link.textContent)).toEqual(['Гарвардский метод↗', 'BATNA↗']);
  expect(within(principles).getAllByRole('link').map(link => link.textContent)).toEqual(['Принцип Парето↗']);
});

it('opens sign-in after an anonymous player fills a custom dialog', () => {
  renderAt('/training/custom');
  fireEvent.change(screen.getByRole('textbox', { name: 'Что происходит?' }), { target: { value: 'Команда обсуждает перенос срока проекта.' } });
  fireEvent.change(screen.getByRole('textbox', { name: 'Ваша роль' }), { target: { value: 'Руководитель проекта' } });
  fireEvent.change(screen.getByRole('textbox', { name: 'Роль собеседника' }), { target: { value: 'Заказчик' } });
  fireEvent.change(screen.getByRole('textbox', { name: 'Чего вы хотите добиться?' }), { target: { value: 'Согласовать новый срок сдачи.' } });
  fireEvent.click(screen.getByRole('button', { name: /Начать разговор/ }));
  expect(screen.getByRole('dialog', { name: 'Вход' })).toBeTruthy();
});

it('signs in through the auth endpoint and shows the user', async () => {
  const fetchMock = vi.fn().mockImplementation((path: string) => Promise.resolve({
    ok: true,
    json: async () => path === '/api/v1/auth/login'
      ? { access_token: 'test-token', user: { id: '1', email: 'test@example.com', display_name: 'Тестовый игрок', role: 'player' } }
      : { status: 'ok', database: 'ready', ai_provider: 'mock' },
  }));
  vi.stubGlobal('fetch', fetchMock);
  renderAt('/');
  fireEvent.click(screen.getByRole('button', { name: /Войти/ }));
  fireEvent.change(screen.getByPlaceholderText('Ваш логин'), { target: { value: 'test' } });
  fireEvent.change(screen.getByPlaceholderText('Ваш пароль'), { target: { value: 'password123' } });
  fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: /Войти/ }));
  expect(await screen.findByRole('link', { name: /Тестовый игрок · Кабинет/ })).toBeTruthy();
  expect(fetchMock).toHaveBeenCalledWith('/api/v1/auth/login', expect.objectContaining({ method: 'POST' }));
});

it('sends login and display name during registration', async () => {
  const fetchMock = vi.fn().mockImplementation((path: string) => Promise.resolve({
    ok: true,
    json: async () => path === '/api/v1/auth/register'
      ? { access_token: 'registered-token', user: { id: '2', login: 'captain', email: 'captain@example.com', display_name: 'Капитан', role: 'player' } }
      : { status: 'ok', database: 'ready', ai_provider: 'mock' },
  }));
  vi.stubGlobal('fetch', fetchMock);
  renderAt('/');
  fireEvent.click(screen.getByRole('button', { name: /Войти/ }));
  fireEvent.click(screen.getByRole('tab', { name: 'Регистрация' }));
  fireEvent.change(screen.getByPlaceholderText('Как к вам обращаться'), { target: { value: 'Капитан' } });
  fireEvent.change(screen.getByPlaceholderText('Ваш логин'), { target: { value: 'captain' } });
  fireEvent.change(screen.getByPlaceholderText('you@example.com'), { target: { value: 'captain@example.com' } });
  fireEvent.change(screen.getByPlaceholderText('Ваш пароль'), { target: { value: 'long-password-123' } });
  fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: /Создать аккаунт/ }));
  expect(await screen.findByRole('link', { name: /Капитан · Кабинет/ })).toBeTruthy();
  const request = fetchMock.mock.calls.find(([path]) => path === '/api/v1/auth/register');
  expect(JSON.parse(request?.[1].body)).toEqual({
    email: 'captain@example.com', password: 'long-password-123', display_name: 'Капитан', login: 'captain',
  });
});

it('revokes the saved token when leaving the account', async () => {
  const fetchMock = vi.fn().mockImplementation((path: string) => Promise.resolve({
    ok: true,
    json: async () => path === '/api/v1/auth/login'
      ? { access_token: 'test-token', user: { id: '1', login: 'player', email: 'test@example.com', display_name: 'Игрок', role: 'player' } }
      : { message: 'Successfully logged out' },
  }));
  vi.stubGlobal('fetch', fetchMock);
  renderAt('/');
  fireEvent.click(screen.getByRole('button', { name: /Войти/ }));
  fireEvent.change(screen.getByPlaceholderText('Ваш логин'), { target: { value: 'player' } });
  fireEvent.change(screen.getByPlaceholderText('Ваш пароль'), { target: { value: 'password123' } });
  fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: /Войти/ }));
  await screen.findByRole('button', { name: 'Выйти' });
  fireEvent.click(screen.getByRole('button', { name: 'Выйти' }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/v1/auth/logout', expect.objectContaining({
    method: 'POST', headers: expect.objectContaining({ Authorization: 'Bearer test-token' }),
  })));
  expect(sessionStorage.getItem('arena_token')).toBeNull();
});
