// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import i18n from '../i18n';
import { PreviewContextMenu } from './PreviewContextMenu';

const state = vi.hoisted(() => ({ scale: true, crop: false, run: vi.fn() }));
vi.mock('../commands/scaleCommands', () => ({
  SCALE_MENU_COMMAND_IDS: ['fitLayerToFrame', 'fillLayerFrame', 'restoreLayerSize'],
  useCanScaleLayer: () => state.scale,
}));
vi.mock('../commands/cropCommands', () => ({
  CROP_MENU_COMMAND_IDS: ['editCrop', 'resetCrop'], useCanEditCrop: () => state.crop,
}));
vi.mock('../commands/registry', () => ({ getCommand: (id: string) => ({
  id, labelKey: ({ fitLayerToFrame: 'layer_scale.fit', fillLayerFrame: 'layer_scale.fill',
    restoreLayerSize: 'layer_scale.original', editCrop: 'crop.edit', resetCrop: 'crop.reset' } as Record<string, string>)[id],
  run: () => state.run(id),
}) }));

beforeEach(async () => {
  await i18n.changeLanguage('en-US');
  state.scale = true;
  state.crop = false;
  state.run.mockReset();
});
afterEach(cleanup);

describe('PreviewContextMenu', () => {
  it('offers the three size commands for images and dispatches the chosen action', async () => {
    const onClose = vi.fn();
    render(<PreviewContextMenu x={100} y={100} onClose={onClose} />);
    expect(await screen.findByRole('menu', { name: 'Preview actions' })).toBeTruthy();
    expect(screen.getAllByRole('menuitem').map(item => item.textContent)).toEqual([
      'Fit to frame', 'Fill frame', 'Restore original size',
    ]);
    await userEvent.click(screen.getByRole('menuitem', { name: 'Fill frame' }));
    expect(state.run).toHaveBeenCalledWith('fillLayerFrame');
    expect(onClose).toHaveBeenCalled();
  });

  it('retains the video crop actions in a separate group', async () => {
    state.crop = true;
    render(<PreviewContextMenu x={100} y={100} onClose={() => {}} />);
    expect(await screen.findByRole('menuitem', { name: 'Crop in preview' })).toBeTruthy();
    expect(screen.getByRole('menuitem', { name: 'Reset crop' })).toBeTruthy();
    expect(screen.getAllByRole('menuitem')).toHaveLength(5);
    expect(screen.getAllByRole('separator')).toHaveLength(1);
  });

  it('uses the agreed Chinese labels', async () => {
    await i18n.changeLanguage('zh-CN');
    render(<PreviewContextMenu x={100} y={100} onClose={() => {}} />);
    expect(await screen.findByRole('menuitem', { name: '适配画面' })).toBeTruthy();
    expect(screen.getByRole('menuitem', { name: '填充画面' })).toBeTruthy();
    expect(screen.getByRole('menuitem', { name: '恢复原始大小' })).toBeTruthy();
  });
});
