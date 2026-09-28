import React from 'react';
import { expect, it } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { NovelStage } from './NovelStage';

it('waits for a click before moving to a new line', async () => {
  const first = { key: 'first', role: 'assistant' as const, content: 'Первая реплика.' };
  const second = { key: 'second', role: 'user' as const, content: 'Вторая реплика.' };
  const view = render(<NovelStage lines={[first]} name="Анна" playerName="Игрок" />);
  await waitFor(() => expect(screen.getByText('Первая реплика.')).toBeTruthy());
  view.rerender(<NovelStage lines={[first, second]} name="Анна" playerName="Игрок" />);
  await new Promise(resolve => setTimeout(resolve, 500));
  expect(screen.getByText('1 / 2')).toBeTruthy();
  expect(screen.queryByText('Вторая реплика.')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: 'Далее →' }));
  await waitFor(() => expect(screen.getByText('Вторая реплика.')).toBeTruthy());
});
