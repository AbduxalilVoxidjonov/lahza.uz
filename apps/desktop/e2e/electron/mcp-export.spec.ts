import { test, expect } from '@playwright/test';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js';
import { readFileSync, writeFileSync, statSync } from 'node:fs';
import path from 'node:path';
import { launchApp, invokeCmd, tmpDir } from './helpers/driver';

test('MCP export reconnects, reports the actual renamed file, and retries publication through the shared UI', async ({ }, testInfo) => {
  test.setTimeout(180_000);
  const { app, page } = await launchApp({ locale: 'zh-CN' });
  let client: Client | undefined;
  try {
    const info = await page.evaluate(() => window.api.mcp.getInfo());
    const connect = async () => {
      const next = new Client({ name: 'export-e2e', version: '1' }, { capabilities: {} });
      await next.connect(new StreamableHTTPClientTransport(new URL(info.url), { requestInit: { headers: { Authorization: `Bearer ${info.bearer_token}` } } }));
      return next;
    };
    client = await connect();
    const created = await client.callTool({name:'create_project',arguments:{parent_folder:tmpDir('weftcut-mcp-export-project-'),name:'MCP export',width:640,height:360,fps_num:30,fps_den:1}});
    expect(created.isError,JSON.stringify(created)).toBeFalsy();
    // No UI navigation or readiness wait: a cold MCP-created project must be
    // able to admit an export while the editor initializes.
    const trackId = await invokeCmd<string>(page, 'add_track', {});
    await invokeCmd(page, 'add_text_layer', { trackId, content: 'Shared export', tStartUs: 0, durationUs: 1_000_000 });
    const call = async (name: string, args: Record<string, unknown> = {}) => {
      const result = await client!.callTool({ name, arguments: args });
      expect(result.isError, JSON.stringify(result)).toBeFalsy();
      return result.structuredContent as Record<string, any>;
    };
    const output = path.join(tmpDir('weftcut-mcp-export-output-'), 'clip.mp4');
    writeFileSync(output, 'original');
    const options = await call('get_export_options');
    expect(options.settings_schema.properties.encoder_engine).toBeTruthy();
    const request = { request_id: 'first-export', output_path: output, settings: { encoder_engine: 'native', hw_accel: 'software', include_audio: false } };
    const started = await call('start_export', request);
    expect(started.state).toBe('preparing');
    await client.close(); client = await connect();
    const duplicate = await call('start_export', request);
    expect(duplicate.job_id).toBe(started.job_id);
    await expect.poll(async () => (await call('get_export_status', { job_id: started.job_id })).state, { timeout: 120_000 }).toBe('completed');
    const completed = await call('get_export_status', { job_id: started.job_id });
    expect(completed.output_path).toBe(path.join(path.dirname(output), 'clip (1).mp4'));
    expect(readFileSync(output, 'utf8')).toBe('original');
    expect(statSync(completed.output_path).size).toBeGreaterThan(100);
    await expect(page.locator('.export-progress-panel')).toContainText('clip (1).mp4');
    await testInfo.attach('export-result', { body: JSON.stringify(completed), contentType: 'application/json' });
    // A publication failure retains the completed staged file. UI retry uses
    // the same job and must not open another encoder or rerun the mux.
    await app.evaluate(({ ipcMain }) => {
      const handler = ipcMain._invokeHandlers.get('backend:invoke')!;
      const trace = { encodes: 0, muxes: 0, publishes: 0 };
      (globalThis as any).__exportTrace = trace;
      ipcMain._invokeHandlers.set('backend:invoke', (event: any, request: any) => {
        if (request.channel === 'export_video_sink_start') trace.encodes++;
        if (request.channel === 'mux_export') trace.muxes++;
        if (request.channel === 'export_job_publish' && ++trace.publishes === 1) throw new Error('Injected publication failure');
        return handler(event, request);
      });
    });
    const second = await call('start_export', { ...request, request_id: 'second-export' });
    await expect.poll(async () => (await call('get_export_status', { job_id: second.job_id })).state, { timeout: 120_000 }).toBe('awaiting_retry');
    const refused = await client.callTool({ name: 'add_track', arguments: {} });
    expect(refused.isError).toBe(true);
    // Declining quit must leave the job and application services usable.
    await app.evaluate(({ app, dialog }) => {
      const show = dialog.showMessageBox;
      dialog.showMessageBox = (async () => { dialog.showMessageBox = show; return { response: 0, checkboxChecked: false }; }) as typeof show;
      app.quit();
    });
    expect((await call('get_export_status', { job_id: second.job_id })).state).toBe('awaiting_retry');
    await page.locator('.export-progress-panel').getByRole('button', { name: '重试完成导出' }).click();
    await expect.poll(async () => (await call('get_export_status', { job_id: second.job_id })).state, { timeout: 30_000 }).toBe('completed');
    expect(await app.evaluate(() => (globalThis as any).__exportTrace)).toEqual({ encodes: 1, muxes: 1, publishes: 2 });
    // A UI job is discoverable and cancellable through MCP. Hold a mux IPC
    // before native entry to prove that cancellation does not release the edit
    // gate while a renderer stage is still outstanding.
    await app.evaluate(({ ipcMain }) => {
      const handler = ipcMain._invokeHandlers.get('backend:invoke')!;
      let release!: () => void;
      const barrier = new Promise<void>(resolve => { release = resolve; });
      (globalThis as any).__releaseExportMux = release;
      (globalThis as any).__exportMuxHeld = false;
      ipcMain._invokeHandlers.set('backend:invoke', async (event: any, request: any) => {
        if (request.channel === 'mux_export') { (globalThis as any).__exportMuxHeld = true; await barrier; }
        return handler(event, request);
      });
    });
    const cancelledOutput = path.join(path.dirname(output), 'cancelled.mp4');
    const ui = await invokeCmd<{ job_id: string }>(page, 'export_job_start', { output_path: cancelledOutput, on_conflict: 'fail' });
    await expect.poll(() => app.evaluate(() => (globalThis as any).__exportMuxHeld), { timeout: 60_000 }).toBe(true);
    expect((await call('get_export_status')).job_id).toBe(ui.job_id);
    expect((await call('get_export_status')).agent).toBe(false);
    await call('cancel_export', { job_id: ui.job_id });
    expect((await call('get_export_status')).phase).toBe('cancelling');
    const whileDraining = await client.callTool({ name: 'add_track', arguments: {} });
    expect(whileDraining.isError).toBe(true);
    await app.evaluate(() => (globalThis as any).__releaseExportMux());
    await expect.poll(async () => (await call('get_export_status', { job_id: ui.job_id })).state, { timeout: 30_000 }).toBe('cancelled');
    expect((await client.callTool({ name: 'add_track', arguments: {} })).isError).toBeFalsy();
  } finally {
    await app.evaluate(() => (globalThis as any).__releaseExportMux?.()).catch(() => { });
    if (client) {
      const result = await client.callTool({ name: 'get_export_status', arguments: {} }).catch(() => null);
      const job = result?.structuredContent as { job_id?: string } | undefined;
      if (job?.job_id) await client.callTool({ name: 'cancel_export', arguments: { job_id: job.job_id } }).catch(() => { });
      await client.close();
    }
    await app.close();
  }
});
