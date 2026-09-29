import React from 'react';
import { expect, it } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { NovelStage } from './NovelStage';

it('focuses a newly started reply and waits for a click between existing lines', async () => {
  const first = { key: 'first', role: 'assistant' as const, content: 'Первая реплика.' };
  const second = { key: 'second', role: 'user' as const, content: 'Вторая реплика.' };
  const view = render(<NovelStage lines={[first]} name="Анна" playerName="Игрок" />);
  await waitFor(() => expect(screen.getByText('Первая реплика.')).toBeTruthy());
  view.rerender(<NovelStage lines={[first, second]} name="Анна" playerName="Игрок" />);
  await new Promise(resolve => setTimeout(resolve, 500));
  await waitFor(() => expect(screen.getByText('Вторая реплика.')).toBeTruthy());
  expect(screen.getByText('2 / 2')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '← Назад' }));
  await waitFor(() => expect(screen.getByText('Первая реплика.')).toBeTruthy());
  await new Promise(resolve => setTimeout(resolve, 500));
  expect(screen.getByText('1 / 2')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Далее →' }));
  await waitFor(() => expect(screen.getByText('Вторая реплика.')).toBeTruthy());
});
