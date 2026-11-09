import { describe, expect, it } from 'vitest';
import type { AssistantCheck, AssistantDraft } from '../services/api';
import {
  assistantOpenOnStart,
  checkTone,
  editDraft,
  isBlocked,
  draftedByLabel,
  rememberAssistantOpen,
  saveEditsEnabled,
  setAssistantHidden,
  setSaveEdits,
} from './assistant';

function memoryStore() {
  const data = new Map<string, string>();
  return {
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => void data.set(k, v),
    removeItem: (k: string) => void data.delete(k),
  };
}

const draft: AssistantDraft = {
  target_type: 'plugin',
  target_id: 'fastsurfer',
  input_files: ['/d/sub-01_T1w.nii.gz'],
  parameters: { use_cpu: true },
  instance: { modality: 'T1w', space: 'subject_native' },
  filled_by: { 'instance.space': 'BIDS', 'parameters.use_cpu': 'request keywords', target_id: 'request keywords' },
  rationale: [],
  alternatives: [],
  request: 'segment on cpu',
};

const check = (status: string, blocking = false): AssistantCheck => ({ gate: 'scicap', status, blocking, reason: '' });

describe('assistant panel preference', () => {
  it('opens on first run, then remembers', () => {
    const store = memoryStore();
    expect(assistantOpenOnStart(store)).toBe(true);
    rememberAssistantOpen(false, store);
    expect(assistantOpenOnStart(store)).toBe(false);
    rememberAssistantOpen(true, store);
    expect(assistantOpenOnStart(store)).toBe(true);
  });

  it('stays closed when turned off in Settings', () => {
    const store = memoryStore();
    setAssistantHidden(true, store);
    expect(assistantOpenOnStart(store)).toBe(false);
    setAssistantHidden(false, store);
    expect(assistantOpenOnStart(store)).toBe(true);
  });
});

describe('saving edits', () => {
  it('is off until the user opts in', () => {
    const store = memoryStore();
    expect(saveEditsEnabled(store)).toBe(false);
    setSaveEdits(true, store);
    expect(saveEditsEnabled(store)).toBe(true);
    setSaveEdits(false, store);
    expect(saveEditsEnabled(store)).toBe(false);
  });
});

describe('drafted-by label', () => {
  it('names the drafter', () => {
    expect(draftedByLabel(draft)).toBe('Drafted by keyword rules');
    expect(draftedByLabel({ ...draft, drafted_by: 'model' }, 'qwen')).toBe('Drafted by local model (qwen)');
  });
});

describe('checks', () => {
  it('never shows not_run as a pass', () => {
    expect(checkTone(check('not_run'))).toBe('idle');
    expect(checkTone(check('ALLOW'))).toBe('pass');
    expect(checkTone(check('ABSTAIN', true))).toBe('block');
    expect(checkTone(check('UNKNOWN'))).toBe('warn');
  });

  it('blocks when any check blocks', () => {
    expect(isBlocked([check('ALLOW'), check('REJECT', true)])).toBe(true);
    expect(isBlocked([check('ALLOW'), check('not_run')])).toBe(false);
  });
});

describe('editDraft', () => {
  it('clears the assistant marker on user edits', () => {
    const next = editDraft(draft, 'instance.space', 'MNI152NLin2009cAsym');
    expect(next.instance.space).toBe('MNI152NLin2009cAsym');
    expect(next.filled_by['instance.space']).toBeUndefined();
    expect(next.filled_by['parameters.use_cpu']).toBe('request keywords');
  });

  it('blank instance field is removed so the check can abstain', () => {
    expect('space' in editDraft(draft, 'instance.space', '').instance).toBe(false);
  });

  it('switching pipeline resets parameters', () => {
    const next = editDraft(draft, 'target', 'workflow:hippo_subfields_t1');
    expect([next.target_type, next.target_id]).toEqual(['workflow', 'hippo_subfields_t1']);
    expect(next.parameters).toEqual({});
  });
});
