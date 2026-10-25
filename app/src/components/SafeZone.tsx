// Legacy clip editor guide; montage guides come from the selected export profile.
export const SAFE = { top: 0.14, bottom: 0.35, side: 0.06 } as const;

export function SafeZoneOverlay({ visible, margins = SAFE }: { visible: boolean; margins?: { top: number; bottom: number; side: number } }) {
  if (!visible) return null;
  return (
    <>
      <div className="safe-band" style={{ top: 0, height: `${margins.top * 100}%` }} />
      <div className="safe-band" style={{ bottom: 0, height: `${margins.bottom * 100}%` }} />
      <div
        className="safe-zone"
        style={{
          top: `${margins.top * 100}%`,
          bottom: `${margins.bottom * 100}%`,
          left: `${margins.side * 100}%`,
          right: `${margins.side * 100}%`,
        }}
      />
    </>
  );
}
