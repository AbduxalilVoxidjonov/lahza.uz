export type PromptMode = 'local' | 'ai';
/** A user choice (including the mode locked by their first keystroke) wins forever. */
export function resolvePromptMode(choice: PromptMode | null, available: boolean): PromptMode {
  return choice ?? (available ? 'ai' : 'local');
}
