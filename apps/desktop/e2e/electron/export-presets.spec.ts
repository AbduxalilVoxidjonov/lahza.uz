import { test, expect } from '@playwright/test';
import { launchApp, invokeCmd, newProject, tmpDir } from './helpers/driver';
import type { AppSettings } from '../../src/shared/app-settings';

test('export presets can be managed in the export dialog and reused after restart', async ({}, testInfo) => {
  test.setTimeout(120_000);
  const longName = '审阅交付版本_'.padEnd(40, 'W');
  const userDataDir = tmpDir('weftcut-preset-profile-');
  const parentFolder = tmpDir('weftcut-preset-projects-');
  const first = await launchApp({ userDataDir });
  try {
    const { page } = first;
    await page.locator('.startup-settings-toggle').click();
    await expect(page.getByRole('tab', { name: 'Export presets', exact: true })).toHaveCount(0);
    await page.getByRole('dialog', { name: 'Settings', exact: true }).getByRole('button', { name: 'Close', exact: true }).click();
    await newProject(page, { parentFolder, name: 'First preset project', canvas: { width: 1920, height: 1080, fpsNum: 30000, fpsDen: 1001 } });
    const trackId = await invokeCmd<string>(page, 'add_track', {});
    await invokeCmd(page, 'add_text_layer', { trackId, content: 'Preset preview', tStartUs: 0, durationUs: 1_000_000 });
    await page.keyboard.press('Control+e');
    await page.getByRole('button', { name: 'Preset', exact: true }).click();
    await page.getByRole('menuitemradio', { name: /^1080p Full HD Landscape/ }).click();
    expect((await invokeCmd<AppSettings>(page, 'app_settings_get')).default_export_preset_id).toBe('builtin:match');
    await page.getByRole('button', { name: 'Preset', exact: true }).click();
    await page.getByRole('menuitem', { name: 'Save as preset…', exact: true }).click();
    await page.getByRole('textbox', { name: 'Preset name', exact: true }).fill(longName);
    await expect(page.getByText('40/40', { exact: true })).toBeVisible();
    await expect(page.getByRole('textbox', { name: 'Preset name', exact: true })).toHaveAttribute('maxlength', '40');
    await page.getByRole('button', { name: 'Save', exact: true }).click();
    await page.getByRole('tab', { name: 'Video', exact: true }).click();
    await page.getByLabel('Target bitrate', { exact: true }).fill('10');
    await expect(page.locator('.export-preset-modified')).toBeVisible();
    await expect(page.locator('.export-preset-label')).toHaveText(longName);
    expect(await page.locator('.export-preset-label').evaluate(el => el.scrollWidth > el.clientWidth)).toBe(true);
    const trigger = page.getByRole('button', { name: 'Preset', exact: true });
    await trigger.hover();
    await expect(page.getByRole('tooltip')).toHaveText(longName);
    await page.screenshot({ path: testInfo.outputPath('long-name-modified.png') });
    await page.getByRole('tab', { name: 'Video', exact: true }).hover();
    await expect(page.getByRole('tooltip')).not.toBeVisible();
    // Keyboard focus also exposes the full name, without an extra tab stop.
    await page.keyboard.press('Tab');
    await trigger.focus();
    await expect(page.getByRole('tooltip')).toHaveText(longName);
    await page.getByRole('button', { name: 'Preset', exact: true }).click();
    await expect(page.getByRole('menuitem', { name: 'Edit…', exact: true })).toHaveCount(0);
    await page.getByRole('menuitem', { name: 'Update preset', exact: true }).click();
    await expect.poll(async () => (await invokeCmd<AppSettings>(page, 'app_settings_get')).export_presets?.[0]?.values.customBitrate).toBe(10_000_000);
    await page.getByRole('button', { name: 'Preset', exact: true }).click();
    await page.getByRole('menuitem', { name: 'Set as default', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Preset', exact: true })).toContainText(longName);
    await page.getByRole('tab', { name: 'Video', exact: true }).click();
    await expect(page.getByRole('combobox', { name: 'Frame rate', exact: true })).toContainText('29.97');
    await expect(page.getByLabel('Target bitrate', { exact: true })).toHaveValue('10');
    await expect(page.getByRole('button', { name: 'Export', exact: true })).toBeEnabled();
    // Number fields keep an empty live region mounted for accessibility.
    await expect(page.getByRole('dialog', { name: 'Export settings', exact: true }).getByRole('alert').filter({ hasText: /\S/ })).toHaveCount(0);
    await invokeCmd(page, 'app_settings_set', { patch: { language: 'zh-CN' } });
    await expect(page.getByRole('tab', { name: '视频', exact: true })).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath('export-preset.png') });
    await page.getByRole('button', { name: '预设', exact: true }).click();
    const selected = page.getByRole('menuitemradio').filter({ hasText: longName });
    expect(await selected.locator('.app-menu-item-label').evaluate(el => el.scrollWidth > el.clientWidth)).toBe(true);
    await expect(selected.locator('.export-preset-default')).toBeVisible();
    await selected.hover();
    await expect(page.getByRole('tooltip')).toHaveText(longName);
    const menu = page.locator('.export-preset-menu');
    expect(await menu.evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath('preset-menu.png') });
    await page.getByRole('menuitem', { name: '重命名…', exact: true }).click();
    await expect(page.getByRole('textbox', { name: '预设名称', exact: true })).toHaveValue(longName);
    await page.getByRole('dialog', { name: '预设名称', exact: true }).getByRole('button', { name: '取消', exact: true }).click();
    await expect(page.getByRole('menu')).not.toBeVisible();
    await expect(page.getByRole('dialog', { name: '导出设置', exact: true })).toBeVisible();
    await page.getByRole('button', { name: '取消', exact: true }).click();
  } finally { await first.app.close(); }
  const second = await launchApp({ userDataDir });
  try {
    await invokeCmd(second.page, 'app_settings_set', { patch: { language: 'en-US' } });
    const prefs = await invokeCmd<AppSettings>(second.page, 'app_settings_get');
    expect(prefs.default_export_preset_id).toBe(prefs.export_presets![0]!.id);
    await newProject(second.page, { parentFolder, name: 'Second preset project', canvas: { width: 1920, height: 1080, fpsNum: 60, fpsDen: 1 } });
    await second.page.keyboard.press('Control+e');
    await expect(second.page.getByRole('button', { name: 'Preset', exact: true })).toContainText(longName);
    await second.page.getByRole('tab', { name: 'Video', exact: true }).click();
    await expect(second.page.getByLabel('Target bitrate', { exact: true })).toHaveValue('10');
    await second.page.getByRole('button', { name: 'Cancel', exact: true }).click();
  } finally { await second.app.close(); }
});
