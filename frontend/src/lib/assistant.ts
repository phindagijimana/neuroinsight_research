/**
 * Job assistant helpers: panel preferences and check display rules.
 *
 * The panel opens on first run so new users meet it, then remembers whether
 * the user left it open or closed.
 */
import type { AssistantCheck, AssistantDraft } from '../services/api';

const OPEN_KEY = 'nir.assistant.open';
const HIDDEN_KEY = 'nir.assistant.hidden';

/** Fired on window when Settings changes the assistant preference. */
export const ASSISTANT_PREF_EVENT = 'nir-assistant-pref';

type KV = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

function storage(): KV | null {
  try {
    return typeof window !== 'undefined' ? window.localStorage : null;
  } catch {
    return null;
  }
}

export function assistantOpenOnStart(store: KV | null = storage()): boolean {
  if (!store) return true;
  if (store.getItem(HIDDEN_KEY) === '1') return false;
  const saved = store.getItem(OPEN_KEY);
  return saved === null ? true : saved === '1';
}

export function rememberAssistantOpen(open: boolean, store: KV | null = storage()): void {
  store?.setItem(OPEN_KEY, open ? '1' : '0');
}

export function assistantHidden(store: KV | null = storage()): boolean {
  return store?.getItem(HIDDEN_KEY) === '1';
}

export function setAssistantHidden(hidden: boolean, store: KV | null = storage()): void {
  if (!store) return;
  if (hidden) store.setItem(HIDDEN_KEY, '1');
  else store.removeItem(HIDDEN_KEY);
  if (typeof window !== 'undefined') window.dispatchEvent(new Event(ASSISTANT_PREF_EVENT));
}

const FEEDBACK_KEY = 'nir.assistant.saveEdits';

/** Opt-in, off by default: keep a local record of edits made before Approve. */
export function saveEditsEnabled(store: KV | null = storage()): boolean {
  return store?.getItem(FEEDBACK_KEY) === '1';
}

export function setSaveEdits(on: boolean, store: KV | null = storage()): void {
  if (!store) return;
  if (on) store.setItem(FEEDBACK_KEY, '1');
  else store.removeItem(FEEDBACK_KEY);
}

export function draftedByLabel(draft: AssistantDraft, modelName?: string | null): string {
  if (draft.drafted_by === 'model') return `Drafted by local model${modelName ? ` (${modelName})` : ''}`;
  return 'Drafted by keyword rules';
}

export type CheckTone = 'pass' | 'block' | 'warn' | 'idle';

export function checkTone(check: AssistantCheck): CheckTone {
  if (check.blocking) return 'block';
  if (check.status === 'PASS' || check.status === 'ALLOW') return 'pass';
  if (check.status === 'not_run') return 'idle';
  return 'warn';
}

export function isBlocked(checks: AssistantCheck[]): boolean {
  return checks.some((c) => c.blocking);
}

export const GATE_LABEL: Record<string, string> = {
  inputs: 'Input file',
  scicap: 'Fits this pipeline (SciCap)',
  sciguard: 'Spatial steps (SciGuard)',
};

/** True when the field's current value came from the assistant, not the user. */
export function assistantFilled(draft: AssistantDraft, field: string): string | undefined {
  return draft.filled_by[field];
}

/** Apply a user edit and drop the assistant marker for that field. */
export function editDraft(draft: AssistantDraft, field: string, value: unknown): AssistantDraft {
  const filled = { ...draft.filled_by };
  delete filled[field];
  const [section, key] = field.split('.', 2);
  if (section === 'instance' && key) {
    const instance = { ...draft.instance };
    if (value === '' || value === undefined) delete instance[key];
    else instance[key] = String(value);
    return { ...draft, instance, filled_by: filled };
  }
  if (section === 'parameters' && key) {
    return { ...draft, parameters: { ...draft.parameters, [key]: value }, filled_by: filled };
  }
  if (field === 'input_files') {
    const path = String(value || '');
    return { ...draft, input_files: path ? [path] : [], filled_by: filled };
  }
  if (field === 'target') {
    const [type, id] = String(value).split(':', 2) as ['plugin' | 'workflow', string];
    return { ...draft, target_type: type, target_id: id, parameters: {}, filled_by: filled };
  }
  return draft;
}
