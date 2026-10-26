import { useClaudeT } from "../../i18n/claude/hook";
import { parseClaudeError } from "../../lib/claude";
import { ErrorText } from "../ui";

/** `claude_*` kodli xato - tushunarli matn (engine xabari "batafsil" ichida); boshqa xatolar - umumiy ko'rinish. */
export function ClaudeErrorText({ error }: { error: unknown }) {
  const { errors } = useClaudeT();
  if (!error) return null;
  const parsed = parseClaudeError(error);
  if (!parsed) return <ErrorText error={error} />;
  return (
    <span className="error stack" role="alert" style={{ gap: 2 }}>
      <span>{errors[parsed.code]}</span>
      {parsed.message && <span className="muted mono">{parsed.message}</span>}
    </span>
  );
}
