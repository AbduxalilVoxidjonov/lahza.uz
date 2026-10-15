// Meta 9:16 xavfsiz zonasi: yuqori 14%, pastki 35%, yonlar 6% (TZ 9-bo'lim).
export const SAFE = { top: 0.14, bottom: 0.35, side: 0.06 } as const;

export function SafeZoneOverlay({ visible }: { visible: boolean }) {
  if (!visible) return null;
  return (
    <>
      <div className="safe-band" style={{ top: 0, height: `${SAFE.top * 100}%` }} />
      <div className="safe-band" style={{ bottom: 0, height: `${SAFE.bottom * 100}%` }} />
      <div
        className="safe-zone"
        style={{
          top: `${SAFE.top * 100}%`,
          bottom: `${SAFE.bottom * 100}%`,
          left: `${SAFE.side * 100}%`,
          right: `${SAFE.side * 100}%`,
        }}
      />
    </>
  );
}
