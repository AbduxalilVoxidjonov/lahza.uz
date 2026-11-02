import { useT, type MessageKey } from "../../i18n";

const ROWS: [string, MessageKey][] = [
  ["Space", "kbd.play"],
  ["J", "kbd.back"],
  ["K", "kbd.pause"],
  ["L", "kbd.forward"],
  ["I", "kbd.in"],
  ["O", "kbd.out"],
  ["A", "kbd.accept"],
  ["R", "kbd.reject"],
  ["⌘/Ctrl + E", "kbd.export"],
];

export function ShortcutsTable() {
  const t = useT();
  return (
    <section className="card stack" aria-labelledby="set-kbd">
      <h2 id="set-kbd">{t("kbd.title")}</h2>
      <table className="table">
        <tbody>
          {ROWS.map(([k, label]) => (
            <tr key={k}>
              <th style={{ width: 140 }}><kbd>{k}</kbd></th>
              <td>{t(label)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted">{t("kbd.note")}</p>
    </section>
  );
}
