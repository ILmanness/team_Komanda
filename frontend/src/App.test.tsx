import React from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import App from './App';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('shows readiness received from the backend', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ai_provider: 'mock' }) }));
  render(<App />);
  expect(await screen.findByText(/PostgreSQL готовы/)).toBeTruthy();
});

it('shows a useful error when the backend is unavailable', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
  render(<App />);
  expect(await screen.findByText(/Backend недоступен/)).toBeTruthy();
});
