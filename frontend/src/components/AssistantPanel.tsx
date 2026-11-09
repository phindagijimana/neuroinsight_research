/**
 * AssistantPanel — docked job assistant.
 *
 * Drafts the same job the Jobs form would submit, explains the pipeline, and
 * shows read-only checks. It never submits: the Approve button is the human
 * submit, and the backend re-runs every check before accepting it.
 */
import React, { useEffect, useState } from 'react';
import { Sparkles, X, RefreshCw, CheckCircle2, XCircle, AlertTriangle, MinusCircle, BookOpen } from 'lucide-react';
import {
  apiService,
  type AssistantCheck,
  type AssistantDraft,
  type AssistantExplanation,
  type AssistantStatus,
} from '../services/api';
import {
  GATE_LABEL,
  assistantFilled,
  checkTone,
  draftedByLabel,
  editDraft,
  isBlocked,
  saveEditsEnabled,
  type CheckTone,
} from '../lib/assistant';

interface AssistantPanelProps {
  onClose: () => void;
  onJobSubmitted: (jobId: string) => void;
}

const INSTANCE_FIELDS: { key: string; label: string; hint: string }[] = [
  { key: 'modality', label: 'Modality', hint: 'e.g. T1w' },
  { key: 'space', label: 'Space', hint: 'e.g. subject_native' },
  { key: 'subject', label: 'Subject', hint: 'e.g. sub-01' },
  { key: 'atlas', label: 'Atlas (label images only)', hint: 'leave blank for raw scans' },
];

const TONE_STYLE: Record<CheckTone, { cls: string; Icon: typeof CheckCircle2 }> = {
  pass: { cls: 'border-green-200 bg-green-50 text-green-800', Icon: CheckCircle2 },
  block: { cls: 'border-red-200 bg-red-50 text-red-800', Icon: XCircle },
  warn: { cls: 'border-amber-200 bg-amber-50 text-amber-800', Icon: AlertTriangle },
  idle: { cls: 'border-gray-200 bg-gray-50 text-gray-600', Icon: MinusCircle },
};

const FilledTag: React.FC<{ source?: string }> = ({ source }) =>
  source ? (
    <span title={`Filled by the assistant: ${source}`} className="ml-1 rounded bg-navy-50 px-1.5 py-0.5 text-[10px] font-semibold text-navy-700">
      assistant
    </span>
  ) : null;

const CheckRow: React.FC<{ check: AssistantCheck }> = ({ check }) => {
  const { cls, Icon } = TONE_STYLE[checkTone(check)];
  return (
    <div className={`rounded-md border px-2.5 py-2 text-xs ${cls}`} data-testid={`check-${check.gate}`}>
      <div className="flex items-center gap-1.5 font-semibold">
        <Icon className="h-3.5 w-3.5 shrink-0" />
        {GATE_LABEL[check.gate] || check.gate}
        <span className="ml-auto font-mono">{check.status}</span>
      </div>
      {check.reason && <p className="mt-1 leading-snug opacity-90">{check.reason}</p>}
    </div>
  );
};

function errorText(e: any): string {
  const detail = e?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (detail?.message) return detail.message;
  return e?.message || 'Request failed';
}

const AssistantPanel: React.FC<AssistantPanelProps> = ({ onClose, onJobSubmitted }) => {
  const [status, setStatus] = useState<AssistantStatus | null>(null);
  const [request, setRequest] = useState('');
  const [inputPath, setInputPath] = useState('');
  const [draft, setDraft] = useState<AssistantDraft | null>(null);
  const [originalDraft, setOriginalDraft] = useState<AssistantDraft | null>(null);
  const [checks, setChecks] = useState<AssistantCheck[]>([]);
  const [stale, setStale] = useState(false);
  const [busy, setBusy] = useState<'' | 'draft' | 'check' | 'approve'>('');
  const [error, setError] = useState('');
  const [explain, setExplain] = useState<AssistantExplanation | null>(null);
  const [showExplain, setShowExplain] = useState(false);
  const [targets, setTargets] = useState<{ value: string; label: string }[]>([]);
  const [submitted, setSubmitted] = useState<string | null>(null);

  useEffect(() => {
    apiService.assistantStatus().then(setStatus).catch(() => setStatus(null));
    Promise.all([apiService.getPlugins(true), apiService.getWorkflows()])
      .then(([p, w]) =>
        setTargets([
          ...p.plugins.map((x: any) => ({ value: `plugin:${x.id}`, label: x.name || x.id })),
          ...w.workflows.map((x: any) => ({ value: `workflow:${x.id}`, label: `${x.name || x.id} (workflow)` })),
        ]),
      )
      .catch(() => setTargets([]));
  }, []);

  useEffect(() => {
    if (!draft) return;
    setExplain(null);
    apiService.assistantExplain(draft.target_type, draft.target_id).then(setExplain).catch(() => setExplain(null));
  }, [draft?.target_type, draft?.target_id]);

  const runDraft = async () => {
    setBusy('draft'); setError(''); setSubmitted(null);
    try {
      const res = await apiService.assistantDraft(request, inputPath.trim());
      setDraft(res.draft); setOriginalDraft(res.draft); setChecks(res.checks); setStale(false);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy('');
    }
  };

  const recheck = async () => {
    if (!draft) return;
    setBusy('check'); setError('');
    try {
      const res = await apiService.assistantRecheck(draft);
      setChecks(res.checks); setStale(false);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy('');
    }
  };

  const approve = async () => {
    if (!draft) return;
    setBusy('approve'); setError('');
    try {
      const res = await apiService.assistantApprove(draft, {
        originalDraft: originalDraft || undefined,
        saveFeedback: saveEditsEnabled(),
      });
      setChecks(res.checks);
      setSubmitted(res.job_id);
      onJobSubmitted(res.job_id);
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      if (detail?.checks) setChecks(detail.checks);
      setError(errorText(e));
    } finally {
      setBusy('');
    }
  };

  const edit = (field: string, value: unknown) => {
    if (!draft) return;
    setDraft(editDraft(draft, field, value));
    setStale(true);
  };

  const blocked = isBlocked(checks);
  const approveDisabled = !draft || blocked || stale || busy !== '' || !!submitted;
  const gatesMissing = status && (!status.gates.scicap || !status.gates.sciguard);

  return (
    <aside
      className="fixed bottom-0 right-0 top-14 z-40 flex w-full max-w-sm flex-col border-l border-navy-100 bg-white shadow-xl"
      aria-label="Job assistant"
      data-testid="assistant-panel"
    >
      <div className="flex items-center gap-2 border-b border-gray-100 px-4 py-3">
        <Sparkles className="h-4 w-4 text-navy-600" />
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-bold text-gray-900">Job assistant</h2>
          <p className="text-[11px] text-gray-500">Drafts and checks a job. Only you can approve it.</p>
        </div>
        <button type="button" onClick={onClose} aria-label="Close assistant"
          className="rounded-md border-none bg-transparent p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-700">
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4 text-sm">
        {gatesMissing && (
          <p className="rounded-md border border-amber-200 bg-amber-50 px-2.5 py-2 text-xs text-amber-800">
            Scientific checks are not installed, so they will show as "not_run". Nothing is marked as passed without running.
          </p>
        )}

        <div className="space-y-2">
          <label className="block text-xs font-semibold text-gray-700" htmlFor="assistant-request">What do you want to do?</label>
          <textarea id="assistant-request" value={request} onChange={(e) => setRequest(e.target.value)} rows={2}
            placeholder="e.g. segment this T1 on CPU, no surfaces"
            className="w-full rounded-md border border-gray-300 p-2 text-sm focus:border-transparent focus:ring-1 focus:ring-navy-500" />
          <label className="block text-xs font-semibold text-gray-700" htmlFor="assistant-input">Input file or folder (path on the machine running jobs)</label>
          <input id="assistant-input" value={inputPath} onChange={(e) => setInputPath(e.target.value)}
            placeholder="/data/ds000003/sub-01/anat/sub-01_T1w.nii.gz"
            className="w-full rounded-md border border-gray-300 p-2 font-mono text-xs focus:border-transparent focus:ring-1 focus:ring-navy-500" />
          <button type="button" onClick={runDraft} disabled={busy !== ''}
            className="w-full rounded-md bg-navy-600 px-3 py-2 text-sm font-medium text-white hover:bg-navy-800 disabled:bg-gray-300">
            {busy === 'draft' ? 'Drafting…' : draft ? 'Draft again' : 'Draft a job'}
          </button>
        </div>

        {draft && (
          <div className="space-y-3 rounded-lg border border-gray-200 p-3" data-testid="assistant-draft">
            <p className="text-[11px] text-gray-500" data-testid="assistant-drafted-by">
              {draftedByLabel(draft, status?.model?.name)}
              {draft.fallback_reason && (
                <span className="block text-amber-700">Local model not used: {draft.fallback_reason}</span>
              )}
            </p>
            <div>
              <label className="block text-xs font-semibold text-gray-700">
                Pipeline <FilledTag source={assistantFilled(draft, 'target_id')} />
              </label>
              <select value={`${draft.target_type}:${draft.target_id}`} onChange={(e) => edit('target', e.target.value)}
                className="mt-1 w-full rounded-md border border-gray-300 p-1.5 text-sm">
                {!targets.some((t) => t.value === `${draft.target_type}:${draft.target_id}`) && (
                  <option value={`${draft.target_type}:${draft.target_id}`}>{draft.target_id}</option>
                )}
                {targets.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700">Input</label>
              <input value={draft.input_files[0] || ''} onChange={(e) => edit('input_files', e.target.value)}
                className="mt-1 w-full rounded-md border border-gray-300 p-1.5 font-mono text-xs" />
            </div>

            <div className="grid grid-cols-2 gap-2">
              {INSTANCE_FIELDS.map((f) => (
                <div key={f.key}>
                  <label className="block text-[11px] font-semibold text-gray-600">
                    {f.label} <FilledTag source={assistantFilled(draft, `instance.${f.key}`)} />
                  </label>
                  <input value={draft.instance[f.key] || ''} placeholder={f.hint}
                    onChange={(e) => edit(`instance.${f.key}`, e.target.value)}
                    className="mt-0.5 w-full rounded-md border border-gray-300 p-1.5 text-xs" />
                </div>
              ))}
            </div>

            {explain && explain.parameters.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-gray-700">Settings</p>
                <div className="mt-1 space-y-1">
                  {explain.parameters.filter((p) => p.type === 'bool').map((p) => {
                    const value = draft.parameters[p.name] ?? p.default;
                    return (
                      <label key={p.name} className="flex items-start gap-2 text-xs text-gray-700" title={p.description}>
                        <input type="checkbox" checked={!!value} onChange={(e) => edit(`parameters.${p.name}`, e.target.checked)} className="mt-0.5" />
                        <span>
                          <span className="font-mono">{p.name}</span>
                          <FilledTag source={assistantFilled(draft, `parameters.${p.name}`)} />
                          <span className="block text-[11px] text-gray-500">{p.description}</span>
                        </span>
                      </label>
                    );
                  })}
                </div>
              </div>
            )}

            {draft.rationale.length > 0 && (
              <ul className="list-disc space-y-0.5 pl-4 text-[11px] text-gray-500">
                {draft.rationale.map((r) => <li key={r}>{r}</li>)}
              </ul>
            )}

            <div className="space-y-1.5">
              <div className="flex items-center">
                <p className="text-xs font-semibold text-gray-700">Checks</p>
                <button type="button" onClick={recheck} disabled={busy !== ''}
                  className="ml-auto flex items-center gap-1 rounded border-none bg-transparent px-1.5 py-0.5 text-[11px] text-navy-700 hover:bg-navy-50 disabled:opacity-50">
                  <RefreshCw className={`h-3 w-3 ${busy === 'check' ? 'animate-spin' : ''}`} /> Re-check
                </button>
              </div>
              {stale && <p className="text-[11px] text-amber-700">You changed the draft. Re-check before approving.</p>}
              {checks.map((c) => <CheckRow key={c.gate} check={c} />)}
            </div>

            {explain && (
              <div className="rounded-md bg-slate-50 p-2">
                <button type="button" onClick={() => setShowExplain((v) => !v)}
                  className="flex w-full items-center gap-1.5 border-none bg-transparent p-0 text-left text-xs font-semibold text-navy-700">
                  <BookOpen className="h-3.5 w-3.5" /> What does {explain.name} do?
                </button>
                {showExplain && (
                  <div className="mt-2 space-y-2 text-[11px] text-gray-700">
                    <p>{explain.what_it_does}</p>
                    {explain.steps.length > 0 && <p>Steps: {explain.steps.map((s) => s.label || s.uses).join(' → ')}</p>}
                    {explain.input_notes.length > 0 && (
                      <ul className="list-disc pl-4">{explain.input_notes.map((n) => <li key={n}>{n}</li>)}</ul>
                    )}
                    {explain.needs_freesurfer_license && <p className="text-amber-700">Needs a free FreeSurfer license (Settings → Licenses).</p>}
                    <dl className="space-y-1">
                      {Object.entries(explain.glossary).map(([term, text]) => (
                        <div key={term}><dt className="inline font-semibold">{term}: </dt><dd className="inline">{text}</dd></div>
                      ))}
                    </dl>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {error && <p className="rounded-md border border-red-200 bg-red-50 px-2.5 py-2 text-xs text-red-700">{error}</p>}
        {submitted && (
          <p className="rounded-md border border-green-200 bg-green-50 px-2.5 py-2 text-xs text-green-800" data-testid="assistant-submitted">
            You approved it. Job <span className="font-mono">{submitted.slice(0, 8)}</span> was submitted and is listed in Results.
          </p>
        )}
      </div>

      {draft && (
        <div className="border-t border-gray-100 px-4 py-3">
          <button type="button" onClick={approve} disabled={approveDisabled} data-testid="assistant-approve"
            className="w-full rounded-md bg-green-700 px-3 py-2 text-sm font-semibold text-white hover:bg-green-800 disabled:bg-gray-300">
            {busy === 'approve' ? 'Submitting…' : 'Approve and submit'}
          </button>
          <p className="mt-1 text-center text-[11px] text-gray-500">
            {blocked ? 'A check blocks this job. Fix the highlighted field and re-check.'
              : stale ? 'Re-check your edits first.'
              : 'Submits exactly this draft with your approval recorded.'}
          </p>
        </div>
      )}
    </aside>
  );
};

export default AssistantPanel;
