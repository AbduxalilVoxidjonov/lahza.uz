import { describe, expect, it } from 'vitest';
import { recommendLayoutTheme } from './layout-theme';

/** Work area leaves room for a typical taskbar / menu bar. */
const display = (width: number, height: number) =>
  recommendLayoutTheme({ width, height }, { width, height: height - 48 });

describe('recommendLayoutTheme', () => {
  it.each([
    ['1920×1080 laptop at 150%', 1280, 720, '1080p-standard'],
    ['MacBook Pro 16" default', 1728, 1117, '1080p-standard'],
    ['Surface 2256×1504 at 150%', 1504, 1003, '1080p-standard'],
    ['1080p at 100%', 1920, 1080, '1080p-standard'],
    ['16:10 1920×1200', 1920, 1200, '1080p-wide'],
    ['1440p / 5K Retina / 4K at 150%', 2560, 1440, '2k-standard'],
    ['3440×1440 ultrawide', 3440, 1440, '2k-standard'],
    ['2560×1600', 2560, 1600, '2k-wide'],
    ['4K at 125%', 3072, 1728, '2k-wide'],
    ['4K at 100%', 3840, 2160, '4k-standard'],
    ['5K at 100%', 5120, 2880, '4k-wide'],
    ['portrait 1440×2560', 1440, 2560, '1080p-standard'],
  ] as const)('%s → %s', (_name, width, height, expected) => {
    expect(display(width, height)).toBe(expected);
  });

  it('skips presets whose minimum window does not fit the work area', () => {
    // A 4K-sized display whose work area is too narrow for 4K minimum widths.
    expect(recommendLayoutTheme({ width: 3840, height: 2160 }, { width: 1400, height: 2100 }))
      .toBe('2k-standard');
  });

  it('falls back to the default when nothing fits', () => {
    expect(recommendLayoutTheme({ width: 800, height: 600 }, { width: 800, height: 560 }))
      .toBe('1080p-standard');
  });
});
