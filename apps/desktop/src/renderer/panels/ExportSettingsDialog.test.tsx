// @vitest-environment jsdom
import { changeExportPresets, exportPresetValues } from '../../shared/export-presets';
import { mergeSettings } from '../../shared/exportSettings';

//
// Covers the export dialog's rate-control group: which bitrate fields each
// rate mode exposes, and what actually leaves the dialog in `onConfirm`'s
// settings. The point of these tests is the *reachability* invariant — the
// bitrate an export runs at must always be on screen and editable, in every
// rate mode — plus the peak/target ordering the encoder seam rejects.
//
// `ipc` and the bridges are stubbed at the module boundary; the stores the
// dialog reads are stubbed to their empty state (no project summary ⇒ the
// decode-routing readout is skipped, which is not what these tests are about).
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { invoke } from '@/bridge/ipc';

const ipc = vi.hoisted(() => ({
  exportSettingsGet: vi.fn(),
  exportSettingsSet: vi.fn(),
  workspaceDir: vi.fn(),
  appSettingsSet: vi.fn(),
}));

vi.mock("../ipc", async (importActual) => {
  const actual = await importActual<typeof import("../ipc")>();
  return { ...actual, ...ipc };
});
vi.mock("@/bridge/ipc", () => ({ invoke: vi.fn(async () => false) }));
vi.mock("@/bridge/dialog", () => ({ open: vi.fn() }));
vi.mock("@/bridge/path", () => ({
  documentDir: vi.fn().mockResolvedValue("C:/docs"),
  join: vi.fn((...parts: string[]) => Promise.resolve(parts.join("/"))),
}));
// The WebCodecs probe only gates an explicit WebCodecs pin; these tests run on
// the default (native) engine, where it is never consulted.
vi.mock("../render/exportCodecProbe", () => ({
  smokeEncode: vi.fn().mockResolvedValue(true),
}));
vi.mock("../state/projectStore", () => ({
  useProjectStore: (select: (s: unknown) => unknown) =>
    select({ summary: null, mediaById: new Map() }),
}));
vi.mock("../settings/decodeComponentStore", () => ({
  useDecodeComponentAvailable: () => true,
  useDecodeComponentReason: () => null,
}));

import i18n from "../i18n";
import type { ExportSettings } from "../render/exportSettings";
import { ExportSettingsDialog } from "./ExportSettingsDialog";
import { APP_SETTINGS_DEFAULTS } from '../../shared/app-settings';
import { useAppSettingsStore } from '../settings/appSettingsStore';

// jsdom has no PointerEvent; Base UI's Select reads MouseEvent's client coords.
(window as unknown as { PointerEvent: unknown }).PointerEvent = window.MouseEvent;

const COMP = { width: 1920, height: 1080, fps_num: 30, fps_den: 1 };
const DURATION_US = 10_000_000;
/// Medium H.264 at 1080p30: 1920×1080×30×0.129 = 8_024_832 bps, the bpp
/// heuristic's value, displayed rounded to 10 kbps.
const MEDIUM_MBPS = "8.02";

const onConfirm = vi.fn();
const onCancel = vi.fn();

/// Mount the dialog and wait for its async mount work (saved settings + the
/// default output location) to land, then switch to the Video pane where the
/// rate-control rows live. Panes are `hidden`, not unmounted, so a query before
/// the switch would find nothing by role.
async function renderDialog(user: ReturnType<typeof userEvent.setup>) {
  render(
    <ExportSettingsDialog
      comp={COMP}
      durationUs={DURATION_US}
      hasTenBitSource={false}
      onCancel={onCancel}
      onConfirm={onConfirm}
    />,
  );
  await waitFor(() =>
    expect(screen.getByRole("tab", { name: "Video" })).toBeTruthy(),
  );
  await user.click(screen.getByRole("tab", { name: "Video" }));
  // Export enablement waits on the output location resolving through the
  // path bridge; assertions on the button would otherwise race it.
  await waitFor(() =>
    expect(
      (screen.getByRole("button", { name: "Export" }) as HTMLButtonElement)
        .disabled,
    ).toBe(false),
  );
}

/// Open a Base UI Select by keyboard, NOT `user.click`: a click on the trigger
/// opens the popup only for the first Select touched in a given test file — see
/// CanvasSection.test.tsx, where the same landmine is documented.
async function openSelect(user: ReturnType<typeof userEvent.setup>, name: string) {
  const trigger = screen.getByRole("combobox", { name });
  trigger.focus();
  await user.keyboard("{Enter}");
  await waitFor(() => expect(trigger.getAttribute("aria-expanded")).toBe("true"));
  return trigger;
}

async function pickOption(user: ReturnType<typeof userEvent.setup>, label: string | RegExp) {
  await user.pointer({
    target: screen.getByRole("option", { name: label }),
    keys: "[MouseLeft]",
  });
}

async function setRateMode(
  user: ReturnType<typeof userEvent.setup>,
  label: string,
) {
  await openSelect(user, "Rate control");
  await pickOption(user, label);
}

/// Base UI's NumberField appends to whatever is there, so every edit clears
/// first. The dialog's rate fields commit live (onValueChange), so no blur.
async function typeNumber(
  user: ReturnType<typeof userEvent.setup>,
  label: string,
  value: string,
) {
  const field = screen.getByLabelText(label);
  await user.clear(field);
  await user.type(field, value);
  return field;
}

function exportButton() {
  return screen.getByRole("button", { name: "Export" }) as HTMLButtonElement;
}

/// The settings object the dialog handed to `onConfirm` — what the export
/// pipeline actually receives.
function confirmedSettings(): ExportSettings {
  expect(onConfirm).toHaveBeenCalledTimes(1);
  return onConfirm.mock.calls[0]![0] as ExportSettings;
}

// Base UI portals its popups outside the render container, so drop whatever
// `cleanup()` leaves on the body before the next test queries roles.
afterEach(() => {
  cleanup();
  document.body.innerHTML = "";
});
beforeEach(async () => {
  useAppSettingsStore.setState({ settings: { ...APP_SETTINGS_DEFAULTS }, loaded: true });
  ipc.appSettingsSet.mockReset().mockImplementation(async patch => ({ ...useAppSettingsStore.getState().settings, ...patch }));
  vi.mocked(invoke).mockReset().mockResolvedValue(false);
  await i18n.changeLanguage("en-US");
  onConfirm.mockReset();
  onCancel.mockReset();
  ipc.exportSettingsGet.mockReset().mockResolvedValue(null);
  ipc.exportSettingsSet.mockReset().mockResolvedValue(undefined);
  ipc.workspaceDir.mockReset().mockResolvedValue("C:/ws");
});

describe("export dialog accessibility", () => {
  it('keeps overwrite off if saving fails and allows retrying the preference', async () => {
    const user = userEvent.setup();
    await renderDialog(user);
    await user.click(screen.getByRole('tab', { name: 'General' }));
    ipc.appSettingsSet.mockRejectedValueOnce(new Error('disk unavailable'));
    const checkbox = screen.getByRole('checkbox', { name: 'Automatically overwrite files with the same name on export' });
    await user.click(checkbox);
    await screen.findByRole('alert');
    expect(checkbox.getAttribute('aria-checked')).toBe('false');
    await user.click(checkbox);
    await waitFor(() => expect(checkbox.getAttribute('aria-checked')).toBe('true'));
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('hides collision information while automatic overwrite is enabled', async () => {
    useAppSettingsStore.setState({ settings: { ...APP_SETTINGS_DEFAULTS, export_auto_overwrite: true } });
    const user = userEvent.setup();
    await renderDialog(user);
    await user.click(screen.getByRole('tab', { name: 'General' }));
    vi.mocked(invoke).mockImplementation(async (channel, args) => {
      if (channel === 'export_job_suggest_name') return 'existing (1)';
      return String(args?.path).endsWith('/existing.mp4');
    });
    fireEvent.change(screen.getByLabelText('File name'), { target: { value: 'existing' } });
    await waitFor(() => expect(exportButton().disabled).toBe(false));
    expect(document.querySelector('.export-path-status-line')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Use “existing (1)”' })).toBeNull();
    expect(screen.getByRole('checkbox', { name: 'Automatically overwrite files with the same name on export' }).getAttribute('aria-checked')).toBe('true');
    expect(ipc.appSettingsSet).not.toHaveBeenCalled();
  });

  it('always shows overwrite and keeps the Export button label when it is checked', async () => {
    const user = userEvent.setup();
    await renderDialog(user);
    await user.click(screen.getByRole('tab', { name: 'General' }));
    const checkbox = screen.getByRole('checkbox', { name: 'Automatically overwrite files with the same name on export' });
    expect(checkbox.getAttribute('aria-checked')).toBe('false');
    expect(document.querySelector('.export-path-status-line')).toBeNull();
    await user.click(checkbox);
    expect(exportButton().textContent).toBe('Export');
    expect(exportButton().disabled).toBe(false);
    fireEvent.change(screen.getByLabelText('File name'), { target: { value: 'another' } });
    await waitFor(() => expect(exportButton().disabled).toBe(false));
    expect(checkbox.getAttribute('aria-checked')).toBe('true');
    fireEvent.change(screen.getByLabelText('Location'), { target: { value: 'C:/another-project/output' } });
    await waitFor(() => expect(exportButton().disabled).toBe(false));
    expect(checkbox.getAttribute('aria-checked')).toBe('true');
    cleanup();
    await renderDialog(user);
    await user.click(screen.getByRole('tab', { name: 'General' }));
    expect(screen.getByRole('checkbox', { name: 'Automatically overwrite files with the same name on export' }).getAttribute('aria-checked')).toBe('true');
    expect(ipc.appSettingsSet).toHaveBeenCalledExactlyOnceWith({ export_auto_overwrite: true });
  });

  it('adopts a suggested filename only when clicked, and exports without overwrite consent', async () => {
    const user = userEvent.setup();
    await renderDialog(user);
    await user.click(screen.getByRole('tab', { name: 'General' }));
    vi.mocked(invoke).mockImplementation(async (channel, args) => {
      if (channel === 'export_job_suggest_name') return 'existing (2)';
      return String(args?.path).endsWith('/existing.mp4');
    });
    const field = screen.getByLabelText('File name') as HTMLInputElement;
    fireEvent.change(field, { target: { value: 'existing' } });
    const rename = await screen.findByRole('button', { name: 'Use “existing (2)”' });
    expect(field.value).toBe('existing');
    expect(exportButton().disabled).toBe(true);
    await user.click(rename);
    await waitFor(() => expect(exportButton().disabled).toBe(false));
    expect(field.value).toBe('existing (2)');
    expect(screen.getByRole('checkbox', { name: 'Automatically overwrite files with the same name on export' }).getAttribute('aria-checked')).toBe('false');
    await user.click(exportButton());
    await waitFor(() => expect(onConfirm).toHaveBeenCalledOnce());
    expect(onConfirm.mock.calls[0]![1]).toBe('C:/ws/output/existing (2).mp4');
    expect(onConfirm.mock.calls[0]![3]).toBe(false);
  });

  it('ignores a late name suggestion after the user edits the target', async () => {
    const user = userEvent.setup();
    await renderDialog(user);
    await user.click(screen.getByRole('tab', { name: 'General' }));
    let resolveName!: (name: string) => void;
    const suggestion = new Promise<string>(resolve => { resolveName = resolve; });
    vi.mocked(invoke).mockImplementation(async (channel, args) => {
      if (channel === 'export_job_suggest_name') return suggestion;
      return String(args?.path).endsWith('/existing.mp4');
    });
    const field = screen.getByLabelText('File name') as HTMLInputElement;
    fireEvent.change(field, { target: { value: 'existing' } });
    await waitFor(() => expect(invoke).toHaveBeenCalledWith('export_job_suggest_name', { path: 'C:/ws/output/existing.mp4' }));
    fireEvent.change(field, { target: { value: 'chosen-name' } });
    await waitFor(() => expect(exportButton().disabled).toBe(false));
    resolveName('existing (1)');
    await suggestion;
    expect(screen.queryByRole('button', { name: 'Use “existing (1)”' })).toBeNull();
    expect(field.value).toBe('chosen-name');
  });

  it('blocks collisions by default and retains the enabled preference after renaming', async () => {
    const user = userEvent.setup();
    await renderDialog(user);
    await user.click(screen.getByRole('tab',{name:'General'}));
    vi.mocked(invoke).mockResolvedValue(true);
    const name = screen.getByLabelText('File name');
    fireEvent.change(name,{target:{value:'existing'}});
    await screen.findByText('A file with this name exists');
    expect(exportButton().disabled).toBe(true);
    await user.click(screen.getByRole('checkbox',{name:'Automatically overwrite files with the same name on export'}));
    await waitFor(() => expect(document.querySelector('.export-path-status-line')).toBeNull());
    expect(exportButton().disabled).toBe(false);
    fireEvent.change(name,{target:{value:'existing-other'}});
    await waitFor(()=>expect(exportButton().disabled).toBe(false));
    await user.click(exportButton());
    await waitFor(()=>expect(onConfirm).toHaveBeenCalledOnce());
    expect(onConfirm.mock.calls[0]![3]).toBe(true);
  });
  it('keeps export disabled after a failed filename check and can recheck the same path', async () => {
    const user = userEvent.setup();
    await renderDialog(user);
    await user.click(screen.getByRole('tab', { name: 'General' }));
    vi.mocked(invoke).mockRejectedValueOnce(new Error('EACCES: permission denied'));
    fireEvent.change(screen.getByLabelText('File name'), { target: { value: 'unreadable' } });
    await screen.findByText('Could not check whether a file with this name exists.');
    expect(exportButton().disabled).toBe(true);
    expect(onConfirm).not.toHaveBeenCalled();
    // The folder becomes readable; rechecking discovers a collision, so the
    // retry must not bypass explicit overwrite consent.
    vi.mocked(invoke).mockResolvedValue(true);
    await user.click(screen.getByRole('button', { name: 'Check again' }));
    await screen.findByText('A file with this name exists');
    expect(exportButton().disabled).toBe(true);
    await user.click(screen.getByRole('checkbox', { name: 'Automatically overwrite files with the same name on export' }));
    expect(exportButton().disabled).toBe(false);
  });
  // The dialog labels each row with a plain sibling <span>, which names nothing
  // as far as assistive tech is concerned — a screen reader reading the Video
  // pane got a column of unnamed dropdowns. Every AppSelect therefore passes
  // `ariaLabel`, and this asserts it for the whole dialog at once so a NEW row
  // added later fails here instead of shipping unnamed.
  it("gives every dropdown an accessible name", async () => {
    const user = userEvent.setup();
    await renderDialog(user);

    // Query the DOM, not `getAllByRole`: every pane stays mounted and only the
    // inactive ones are `hidden`, which role queries skip by default — so a
    // role query would silently check just the pane in view.
    const triggers = Array.from(
      document.querySelectorAll<HTMLElement>('[role="combobox"]'),
    );
    // Guard the guard: if AppSelect ever stops rendering role=combobox, an
    // empty list would make this test vacuously pass.
    expect(triggers.length).toBeGreaterThanOrEqual(15);
    const unnamed = triggers.filter(
      (el) =>
        !(el.getAttribute("aria-label") ?? "").trim() &&
        !(el.getAttribute("aria-labelledby") ?? "").trim(),
    );
    expect(unnamed.map((el) => el.textContent)).toEqual([]);
  });
});

describe("export dialog rate control", () => {
  it("shows the preset-derived target bitrate without picking Custom", async () => {
    const user = userEvent.setup();
    await renderDialog(user);

    expect(screen.getByRole("combobox", { name: "Quality" }).textContent).toContain(
      "Medium",
    );
    expect(screen.getByLabelText("Target bitrate")).toHaveProperty(
      "value",
      MEDIUM_MBPS,
    );
  });

  it("keeps the target bitrate editable under CBR, with no separate peak", async () => {
    const user = userEvent.setup();
    await renderDialog(user);
    await setRateMode(user, "CBR (constant)");

    expect(screen.getByLabelText("Target bitrate")).toBeTruthy();
    // CBR's peak IS its target, so offering a second number would be a lie.
    expect(screen.queryByLabelText("Maximum bitrate")).toBeNull();
    await typeNumber(user, "Target bitrate", "6");
    await user.click(exportButton());

    const settings = confirmedSettings();
    expect(settings.rateMode).toBe("cbr");
    expect(settings.customBitrate).toBe(6_000_000);
    // Typing the number is what takes it over from the preset.
    expect(settings.quality).toBe("custom");
  });

  it("starts VBR uncapped and sends a typed peak through", async () => {
    const user = userEvent.setup();
    await renderDialog(user);

    // Default VBR: the peak field exists but is empty — uncapped ABR.
    expect(screen.getByLabelText("Maximum bitrate")).toHaveProperty("value", "");
    expect(screen.getByText(/Peak uncapped/)).toBeTruthy();
    // Nothing to average over yet, so no buffer row.
    expect(screen.queryByLabelText("Buffer size")).toBeNull();

    await typeNumber(user, "Maximum bitrate", "12");
    // A ceiling exists now, so the buffer becomes meaningful.
    expect(screen.getByLabelText("Buffer size")).toBeTruthy();
    await user.click(exportButton());

    const settings = confirmedSettings();
    expect(settings.maxBitrate).toBe(12_000_000);
    expect(settings.bufferSize).toBeNull(); // left on the derived default
  });

  it("blocks export while the peak is below the target, and explains why", async () => {
    const user = userEvent.setup();
    await renderDialog(user);
    await typeNumber(user, "Maximum bitrate", "4");

    // 4 Mbps peak under an ~8 Mbps target: the encoder would abandon the
    // target and emit at the ceiling, so the seam rejects it — stop here.
    await waitFor(() => expect(exportButton().disabled).toBe(true));
    expect(screen.getByText(/maximum must be at least the target/)).toBeTruthy();

    // Raising the target's own value back under the ceiling clears it.
    await typeNumber(user, "Target bitrate", "3");
    await waitFor(() => expect(exportButton().disabled).toBe(false));
  });

  it("sends an explicit buffer size when one is typed", async () => {
    const user = userEvent.setup();
    await renderDialog(user);
    await typeNumber(user, "Maximum bitrate", "12");
    await typeNumber(user, "Buffer size", "6");
    await user.click(exportButton());

    expect(confirmedSettings().bufferSize).toBe(6_000_000);
  });

  it("replaces the whole bitrate group with CRF under quality mode", async () => {
    const user = userEvent.setup();
    await renderDialog(user);
    await setRateMode(user, "Quality (CRF)");

    // A quality preset decides nothing here — it only seeds a bitrate target,
    // and CRF has none. Showing it would be a control that does nothing.
    expect(screen.queryByRole("combobox", { name: "Quality" })).toBeNull();
    expect(screen.queryByLabelText("Target bitrate")).toBeNull();
    expect(screen.queryByLabelText("Maximum bitrate")).toBeNull();
    expect(screen.getByLabelText("CRF")).toHaveProperty("value", "18");
  });

  it("restores a saved peak and buffer on reopen", async () => {
    // Round-trip check: these fields are persisted per project, so a reopened
    // dialog must show the constraint the last export ran with.
    ipc.exportSettingsGet.mockResolvedValue({
      maxBitrate: 15_000_000,
      bufferSize: 20_000_000,
    } as Partial<ExportSettings>);
    const user = userEvent.setup();
    await renderDialog(user);

    expect(screen.getByLabelText("Maximum bitrate")).toHaveProperty("value", "15");
    expect(screen.getByLabelText("Buffer size")).toHaveProperty("value", "20");
  });

  it("drops a non-positive saved peak rather than passing it to ffmpeg", async () => {
    // export.json is hand-editable, and `-maxrate 0` is a launch failure.
    ipc.exportSettingsGet.mockResolvedValue({
      maxBitrate: 0,
    } as Partial<ExportSettings>);
    const user = userEvent.setup();
    await renderDialog(user);

    expect(screen.getByLabelText("Maximum bitrate")).toHaveProperty("value", "");
    await user.click(exportButton());
    expect(confirmedSettings().maxBitrate).toBeNull();
  });
});

async function openPresetMenu(user: ReturnType<typeof userEvent.setup>) {
  const trigger = screen.getByRole('button', { name: 'Preset' });
  trigger.focus();
  await user.keyboard('{Enter}');
  await waitFor(() => expect(trigger.getAttribute('aria-expanded')).toBe('true'));
}

describe('export presets workflow', () => {
  beforeEach(() => {
    ipc.appSettingsSet.mockImplementation(async ({ export_preset_change, ...patch }) => {
      const current = useAppSettingsStore.getState().settings;
      return { ...current, ...patch, export_presets: export_preset_change ? changeExportPresets(current.export_presets ?? [], export_preset_change) : current.export_presets };
    });
  });
  it('applies a built-in, saves modified values, and exposes that recipe in another project', async () => {
    const user = userEvent.setup();
    await renderDialog(user);
    await openPresetMenu(user);
    await user.click(screen.getByRole('menuitemradio', { name: /^1080p Full HD Landscape/ }));
    expect(screen.getByRole('combobox', { name: 'Resolution' }).textContent).toContain('1080p');
    await typeNumber(user, 'Target bitrate', '6');
    expect(screen.getByRole('button', { name: 'Preset' }).textContent).toContain('(modified)');
    await openPresetMenu(user);
    await user.click(screen.getByRole('menuitem', { name: 'Save as preset…' }));
    await user.type(screen.getByRole('textbox', { name: 'Preset name' }), 'Review copy');
    await user.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(useAppSettingsStore.getState().settings.export_presets).toHaveLength(1));
    const saved = useAppSettingsStore.getState().settings.export_presets![0]!;
    expect(saved.values.customBitrate).toBe(6_000_000);
    expect(saved.values).not.toHaveProperty('encoderEngine');
    expect(ipc.exportSettingsSet).not.toHaveBeenCalled();
    cleanup();
    useAppSettingsStore.setState({ settings: { ...useAppSettingsStore.getState().settings, default_export_preset_id: saved.id } });
    await renderDialog(user);
    expect(screen.getByLabelText('Target bitrate')).toHaveProperty('value', '6');
    expect(screen.getByRole('button', { name: 'Preset' }).textContent).toContain('Review copy');
    await user.click(exportButton());
    expect(confirmedSettings().customBitrate).toBe(6_000_000);
  });
  it('preserves project settings ahead of the global default and restores an edited preset explicitly', async () => {
    const user = userEvent.setup();
    useAppSettingsStore.setState({ settings: { ...APP_SETTINGS_DEFAULTS, default_export_preset_id: 'builtin:hd' } });
    ipc.exportSettingsGet.mockResolvedValue(mergeSettings({ quality: 'custom', customBitrate: 15_000_000 }));
    await renderDialog(user);
    expect(screen.getByLabelText('Target bitrate')).toHaveProperty('value', '15');
    await openPresetMenu(user);
    await user.click(screen.getByRole('menuitemradio', { name: /^1080p Full HD Landscape/ }));
    await typeNumber(user, 'Target bitrate', '6');
    await openPresetMenu(user);
    await user.click(screen.getByRole('menuitem', { name: 'Restore' }));
    expect(screen.getByLabelText('Target bitrate')).toHaveProperty('value', '8');
  });
  it('manages recipes in the export menu without making selection a default change', async () => {
    const user = userEvent.setup();
    await renderDialog(user);
    expect(screen.queryByRole('button', { name: 'Duplicate…' })).toBeNull();
    await openPresetMenu(user);
    await user.click(screen.getByRole('menuitemradio', { name: /^1080p Full HD Landscape/ }));
    expect(ipc.appSettingsSet).not.toHaveBeenCalled();
    await openPresetMenu(user);
    expect(screen.queryByRole('menuitem', { name: 'Delete' })).toBeNull();
    await user.click(screen.getByRole('menuitem', { name: 'Save as preset…' }));
    await user.type(screen.getByRole('textbox', { name: 'Preset name' }), 'Personal delivery');
    await user.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Preset' }).textContent).toContain('Personal delivery'));
    await openPresetMenu(user);
    await user.click(screen.getByRole('menuitem', { name: 'Set as default' }));
    await waitFor(() => expect(useAppSettingsStore.getState().settings.default_export_preset_id).toBe(useAppSettingsStore.getState().settings.export_presets![0]!.id));
    await openPresetMenu(user);
    await user.click(screen.getByRole('menuitem', { name: 'Rename…' }));
    await user.clear(screen.getByRole('textbox', { name: 'Preset name' }));
    await user.type(screen.getByRole('textbox', { name: 'Preset name' }), 'Renamed delivery');
    await user.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Preset' }).textContent).toContain('Renamed delivery'));
    await openPresetMenu(user);
    await user.click(screen.getByRole('menuitem', { name: 'Delete' }));
    await waitFor(() => expect(useAppSettingsStore.getState().settings.export_presets).toHaveLength(0));
    expect(screen.getByRole('button', { name: 'Preset' }).textContent).toContain('Custom');
  });
  it('updates a personal preset from the current export form only on explicit save', async () => {
    const user = userEvent.setup();
    const preset = { id: 'personal', name: 'Review', version: 1 as const, values: exportPresetValues(mergeSettings({ quality: 'custom', customBitrate: 5_000_000 })) };
    useAppSettingsStore.setState({ settings: { ...APP_SETTINGS_DEFAULTS, export_presets: [preset], default_export_preset_id: preset.id } });
    await renderDialog(user);
    await typeNumber(user, 'Target bitrate', '7');
    expect(useAppSettingsStore.getState().settings.export_presets![0]!.values.customBitrate).toBe(5_000_000);
    await openPresetMenu(user);
    expect(screen.queryByRole('menuitem', { name: 'Edit…' })).toBeNull();
    await user.click(screen.getByRole('menuitem', { name: 'Update preset' }));
    await waitFor(() => expect(useAppSettingsStore.getState().settings.export_presets![0]!.values.customBitrate).toBe(7_000_000));
    expect(screen.getByRole('button', { name: 'Preset' }).textContent).toBe('Review');
    expect(ipc.exportSettingsSet).not.toHaveBeenCalled();
    expect(onConfirm).not.toHaveBeenCalled();
  });
});
