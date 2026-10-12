import { expect, test } from '@playwright/test';
import path from 'node:path';
import { launchApp, invokeCmd, newProject, importAndPlaceMedia, tmpDir, waitForHook } from './helpers/driver';
import type { AppSettings } from '../../src/shared/app-settings';

test('Linux hardware inventory and explicit probes remain separate from preferences', async ({}, testInfo) => {
  test.skip(process.platform !== 'linux', 'Linux hardware providers');
  test.setTimeout(120_000);
  const { app, page } = await launchApp({ locale: 'zh-CN' });
  try {
    const before = await invokeCmd<AppSettings>(page, 'app_settings_get');
    const snapshot = await page.evaluate(() => window.api.performanceResources.info());
    expect(snapshot.hardware?.platform).toBe('linux');
    expect(snapshot.hardware?.acceleration.status).toBe('idle');
    expect(snapshot.gpu_buffer_transport).toBe('copy-back');
    for (const device of snapshot.hardware!.devices) {
      expect(device.name).not.toBe('');
      if (device.memory.kind === 'shared') expect(device.memory.total_mib).toBeNull();
      if (device.memory.total_mib === null) expect(device.memory.used_mib).toBeNull();
    }
    await page.locator('.startup-settings-toggle').click();
    await page.getByRole('tab', { name: '性能', exact: true }).click();
    const pane = page.locator('#settings-panel-performance');
    await expect(pane.getByTestId('performance-gpu-usage')).toHaveCount(0);
    await expect(pane.getByRole('button', { name: '进行基准测试', exact: true })).toHaveCount(0);
    await expect(pane.getByText('WebGPU', { exact: true })).toHaveCount(0);
    await expect(pane.getByText('驱动', { exact: true })).toHaveCount(0);
    const reserved = (await page.evaluate(() => window.api.resources.status())).reserved_mib;
    await expect(pane.getByRole('heading').first()).toHaveText('此计算机');
    await expect(pane.getByTestId('current-decode-devices')).toHaveText('暂无解码会话');
    await expect(pane.getByRole('button', { name: '检测加速能力', exact: true })).toHaveCount(0);
    const diagnosticsButton = pane.getByRole('button', { name: '硬件诊断', exact: true });
    await diagnosticsButton.click();
    const dialog = page.getByRole('dialog', { name: '硬件诊断', exact: true });
    await dialog.getByRole('button', { name: '检测加速能力', exact: true }).click();
    await expect(dialog.getByRole('button', { name: '检测加速能力', exact: true })).toBeEnabled({ timeout: 100_000 });
    const tested = await page.evaluate(() => window.api.performanceResources.info());
    // A GPU-less host completes with negative per-backend verdicts. A failed
    // host/IPC/packaging lifecycle must fail this test, rather than look healthy.
    expect(tested.hardware!.acceleration.status).toBe('complete');
    expect(tested.hardware!.acceleration.decode.length).toBeGreaterThan(0);
    expect(tested.hardware!.acceleration.encode.length).toBeGreaterThan(0);
    await expect(pane.getByTestId('hardware-codec-group')).toHaveCount(0);
    await expect(dialog).toBeVisible();
    await expect(dialog.getByText('WebGPU', { exact: true })).toBeVisible();
    const groups = dialog.getByTestId('hardware-codec-group');
    const diagnostics = tested.hardware!.acceleration;
    const expectedGroups = [diagnostics.decode, diagnostics.encode].reduce((count, rows) => count
      + new Set(rows.map(row => JSON.stringify([row.backend.split('_').at(-1), row.device_id, row.device_path]))).size, 0);
    await expect(groups).toHaveCount(expectedGroups);
    for (const group of await groups.all()) {
      await expect(group.locator('h5')).toHaveCount(1);
      await expect(group.locator(':scope > .settings-toggle-hint')).toHaveCount(1);
    }
    expect(await dialog.evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath('hardware-diagnostics.png'), animations: 'disabled' });
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
    await expect(diagnosticsButton).toBeFocused();
    await expect(pane).toBeVisible();
    await expect(pane.getByTestId('current-decode-devices')).toHaveText('暂无解码会话');
    await page.screenshot({ path: testInfo.outputPath('hardware-summary.png'), animations: 'disabled' });
    expect(await pane.evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
    await expect.poll(async () => (await page.evaluate(() => window.api.resources.status())).reserved_mib).toBe(reserved);
    const after = await invokeCmd<AppSettings>(page, 'app_settings_get');
    expect(after.resource_policy).toEqual(before.resource_policy);
    expect(after.performance).toEqual(before.performance);
    expect(after.decode_engine).toBe(before.decode_engine);
  } finally { await app.close(); }
});

test('performance device display follows the actual preview decoder and clears when its clip is removed', async ({}, testInfo) => {
  test.setTimeout(90_000);
  const { app, page } = await launchApp({ locale: 'zh-CN' });
  try {
    await newProject(page, { parentFolder: tmpDir('weftcut-decode-status-'), name: 'Decode status',
      canvas: { width: 1920, height: 1080, fpsNum: 30, fpsDen: 1 } });
    await invokeCmd(page, 'app_settings_set', { patch: { decode_engine: 'ffmpeg' } });
    const { layerId } = await importAndPlaceMedia(page, { mediaAbsPath: path.resolve('e2e/fixtures/media/test_1080p_h264.mp4') });
    await waitForHook(page, 'activeClipProbe');
    await page.waitForFunction(() => {
      try { (window as any).__weftcutTest.activeClipProbe(); return true; } catch { return false; }
    });
    await page.evaluate(() => (window as any).__weftcutTest.weftcutSeekUs(500_000));
    await expect.poll(async () => (await page.evaluate(id => (window as any).__weftcutTest.activeClipProbe(id), layerId))?.spriteBound).toBe(true);
    const clip = await page.evaluate(id => (window as any).__weftcutTest.activeClipProbe(id), layerId);
    const inventory = (await page.evaluate(() => window.api.performanceResources.info())).hardware?.devices ?? [];
    await page.keyboard.press(process.platform === 'darwin' ? 'Meta+Comma' : 'Control+Comma');
    await page.getByRole('tab', { name: '性能', exact: true }).click();
    const pane = page.locator('#settings-panel-performance');
    const device = pane.getByTestId('current-decode-devices');
    await expect(pane.getByRole('heading').first()).toHaveText('此计算机');
    if (clip.sourceKind === 'sw') await expect(device).toHaveText('CPU（软件解码）');
    else {
      expect(clip.sourceKind).toBe('native-gpu');
      const nvidia = inventory.filter(d => d.vendor_id === 0x10de);
      if (clip.hwLane === 'nvdec' && nvidia.length === 1) await expect(device).toHaveText(nvidia[0]!.name);
      else await expect(device).not.toHaveText('暂无解码会话');
    }
    await page.screenshot({ path: testInfo.outputPath('current-decoder.png'), animations: 'disabled' });
    await invokeCmd(page, 'delete_layers', { layerIds: [layerId] });
    await expect(device).toHaveText('暂无解码会话');
  } finally { await app.close(); }
});
