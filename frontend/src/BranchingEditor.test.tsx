import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { BranchingEditor } from './BranchingEditor';
import { AdminBranchingTool, AdminMission, AdminMissionWrite, AdminOverview, api } from './api';

afterEach(() => { cleanup(); vi.restoreAllMocks(); sessionStorage.clear(); });

it('edits an imported method as a branching training', async () => {
  const tool: AdminBranchingTool = {
    id: 'METHOD_1', category: 'methods', title: 'Метод вопросов', description: 'Узнать потребность собеседника', order: 1,
    scenarios: [{ id: 'METHOD_1_A', title: 'Срок поставки', goal: 'Согласовать срок', start_node_id: 'start', weight: 1, status: 'active', nodes: {
      start: { node_id: 'start', type: 'decision', speaker: 'Клиент', text: 'Нужно доставить заказ завтра.', outcome: null, options: [
        { id: 'ask', text: 'Почему именно завтра?', effect: null, flag: null, feedback: 'Уточнили причину.', next_node: 'end' },
        { id: 'deny', text: 'Это невозможно.', effect: null, flag: null, feedback: 'Не уточнили причину.', next_node: 'end' },
      ] },
      end: { node_id: 'end', type: 'terminal', speaker: 'Итог', text: 'Разговор закончен.', outcome: 'partial', options: [] },
    } }],
  };
  const mission = { id: 'mission-1', mission_type: 'method_training', interaction_type: 'branching_training', title: tool.title,
    storyline_id: null, knowledge_item_id: 'topic-1', character_id: 'mentor-1', branch_key: 'methods', order_index: 1,
    status: 'published', task: tool.description, context: { situation: tool.scenarios[0].nodes.start.text }, config: { branching: tool } } as AdminMission;
  const overview = { knowledge: [{ id: 'topic-1', slug: 'topic-3', title: 'Переговоры', status: 'published' }],
    characters: [{ id: 'mentor-1', slug: 'training-mentor', name: 'Наставник' }], missions: [mission], storylines: [] } as unknown as AdminOverview;
  vi.spyOn(api, 'adminMission').mockResolvedValue(mission);
  const save = vi.spyOn(api, 'adminSave').mockResolvedValue({ id: 'mission-1', status: 'published' });
  sessionStorage.setItem('arena_token', 'test-token');
  render(<MemoryRouter><BranchingEditor id="mission-1" overview={overview} saved={vi.fn()} /></MemoryRouter>);
  expect(await screen.findByDisplayValue('Нужно доставить заказ завтра.')).toBeTruthy();
  fireEvent.change(screen.getByRole('textbox', { name: 'Текст сцены' }), { target: { value: 'Нужно доставить заказ к пятнице.' } });
  fireEvent.click(screen.getByRole('button', { name: 'Сохранить тренировку →' }));
  await waitFor(() => expect(save).toHaveBeenCalled());
  const body = save.mock.calls[0][2] as AdminMissionWrite;
  expect(body.interaction_type).toBe('branching_training');
  expect(body.branch_key).toBe('methods');
  expect(body.branching?.scenarios[0].nodes.start.text).toBe('Нужно доставить заказ к пятнице.');
});
