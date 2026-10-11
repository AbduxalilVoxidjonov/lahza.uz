import { EXPORT_SETTINGS_SCHEMA } from '../../shared/exportValidation';
import { exportWire } from '../../shared/exportJob';
import type { CatalogTool } from './mcpCatalog';

const HELP: Record<string, string> = {
  includeVideo: 'Include video.', includeAudio: 'Include audio; must agree with audio.include if both are set.',
  resolutionHeight: 'Output height in pixels, downscale only. Null follows composition; omission keeps saved setting.',
  fps: 'Integer output fps, no upsampling. Null follows composition.', codec: 'Output codec.', quality: 'Target bitrate preset; custom uses custom_bitrate.',
  customBitrate: 'Custom target bitrate in bits/second; null clears the saved target.', rateMode: 'Rate control; quality requires native software encoding.',
  maxBitrate: 'Native VBR peak ceiling in bits/second; null removes the cap.', bufferSize: 'Native VBV buffer in bits; null derives it from rate.',
  proresProfile: 'Profile for ProRes output.', dnxhrProfile: 'Profile for DNxHR output.', crf: 'Native constant quality value; null uses codec default.',
  preset: 'Native software encoder speed preset.', keyframeIntervalSec: 'Seconds between keyframes.', hwAccel: 'Auto prefers native hardware candidates; software forces CPU encoding.',
  encoderEngine: 'Auto selects native. MCP never prompts for or automatically switches to WebCodecs.', decodeEngine: 'Source decoding engine for this job.',
  bitDepth: 'Output bit depth. Delivery-codec 10-bit needs explicit experimental opt-in.', container: 'Video container; audio-only uses m4a or mka.',
  audio: 'Audio settings overrides.', include: 'Include audio; must agree with include_audio if both are set.', bitrate: 'Audio bitrate in bits/second.',
  sampleRate: 'Audio sample rate in Hz; null follows composition.', channels: 'Audio channels, mono or stereo; null follows composition.',
};
export function exportSettingsSchema(): Record<string, unknown> {
  const visit = (schema: Record<string, unknown>): Record<string, unknown> => Object.fromEntries(Object.entries(schema).map(([k, v]) =>
    [k, k === 'properties' ? Object.fromEntries(Object.entries(v as Record<string, Record<string, unknown>>).map(([name, rule]) =>
      [Object.keys(exportWire({ [name]: null }, true) as object)[0]!, { ...visit(rule), description: HELP[name] }])) : v]));
  return visit(EXPORT_SETTINGS_SCHEMA);
}
const schema = (properties: Record<string, unknown>, required: string[] = []) => ({ type: 'object', properties, required, additionalProperties: false });
const id = { type: 'string', minLength: 1, description: 'Application-session export job id.' };
const definition = (name: string, description: string, inputSchema: Record<string, unknown>, readOnlyHint: boolean, idempotentHint: boolean): CatalogTool & { description: string; inputSchema: Record<string, unknown> } => ({
  name, description, inputSchema, annotations: readOnlyHint ? { readOnlyHint: true } : { readOnlyHint: false, destructiveHint: false, idempotentHint },
});
export const EXPORT_TOOL_DEFS = [
  definition('get_export_options', 'Read saved export defaults, valid settings and composition limits before exporting.', schema({}), true, true),
  definition('start_export', 'Start an asynchronous export in the editor. Use one request_id per intent; reuse it when reconnecting. Poll get_export_status for the actual completed path. Default conflicts add a numeric suffix.', schema({
    request_id: { ...id, maxLength: 200, description: 'Unique export intent id. Reuse with identical arguments after reconnecting.' },
    output_path: { ...id, description: 'Absolute candidate file path. Omit for project/output/project-name.ext; explicit parent must exist.' },
    on_conflict: { enum: ['rename', 'fail'], description: 'Default rename adds a number. Fail requires the exact name. Neither overwrites.' },
    settings: { ...exportSettingsSchema(), description: 'Partial per-job overrides; omitted fields use saved project defaults.' },
    range: { ...schema({ start_us: { type: 'integer', minimum: 0, description: 'Inclusive start in microseconds.' }, end_us: { type: 'integer', minimum: 1, description: 'Exclusive end in microseconds.' } }, ['start_us', 'end_us']), description: 'Span inside the root composition, snapped to its frame grid. Omit for the whole composition.' },
    allow_experimental_10bit: { type: 'boolean', description: 'Explicit opt-in for experimental HEVC/AV1 10-bit export.' },
  }), false, false),
  definition('get_export_status', 'Read an export job. Omit job_id to discover the current UI or MCP job. Records survive MCP reconnects until the app exits.', schema({ job_id: id }), true, true),
  definition('retry_export', 'Retry only finalization of an awaiting_retry job. Optional filename changes the basename in the same directory; keep its extension.', schema({ job_id: id, filename: { ...id, description: 'New basename including matching extension. Directory and encoded settings cannot change.' } }, ['job_id']), false, false),
  definition('cancel_export', 'Cancel or discard an export from either entry point. Cancellation drains active work before releasing the project edit lock; poll status until terminal.', schema({ job_id: id }, ['job_id']), false, true),
];
export const EXPORT_TOOLS = new Set(EXPORT_TOOL_DEFS.map(d => d.name));
