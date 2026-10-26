import { useSettings } from "../../store/settings";
import { claudeDictionaries, claudeErrors } from "./index";

export function useClaudeT() {
  const locale = useSettings((s) => s.locale);
  return { c: claudeDictionaries[locale], errors: claudeErrors[locale] };
}
