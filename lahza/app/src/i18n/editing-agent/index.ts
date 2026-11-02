import { useSettings } from "../../store/settings";
import { dictionaries, type Messages } from "./messages";
export function useEditingAgentT() {
  const locale = useSettings(s => s.locale);
  return (key: keyof Messages) => dictionaries[locale][key];
}
