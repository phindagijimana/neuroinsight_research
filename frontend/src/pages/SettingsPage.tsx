/**
 * SettingsPage — app settings.
 *
 * Currently hosts the Licenses panel: upload the third-party licenses some
 * pipelines need (FreeSurfer, MELD, ...). Driven by the backend registry
 * (/api/licenses), so new licenses appear here automatically.
 */
import { useEffect, useState } from 'react';
import { apiService, type LicenseInfo } from '../services/api';

const LicenseCard: React.FC<{ lic: LicenseInfo; onChange: () => void }> = ({ lic, onChange }) => {
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  const save = async (content: string) => {
    if (!content.trim()) { setErr('Paste your license, or choose a file.'); return; }
    setBusy(true); setErr('');
    try {
      await apiService.uploadLicense(lic.id, content);
      setText('');
      onChange();
    } catch (e: any) {
      setErr(e?.response?.data?.detail || 'Could not save the license.');
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    setBusy(true); setErr('');
    try { await apiService.deleteLicense(lic.id); onChange(); }
    catch { setErr('Could not remove the license.'); }
    finally { setBusy(false); }
  };

  const onFile = (f?: File) => {
    if (!f) return;
    const reader = new FileReader();
    reader.onload = () => save(String(reader.result || ''));
    reader.readAsText(f);
  };

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 mb-4 shadow-sm">
      <div className="flex items-center justify-between">
        <span className="font-bold text-gray-900">{lic.name}</span>
        {lic.installed ? (
          <span className="text-xs font-bold text-green-700 bg-green-100 rounded-full px-3 py-0.5">● Installed</span>
        ) : (
          <span className="text-xs font-bold text-amber-700 bg-amber-100 rounded-full px-3 py-0.5">○ Not installed</span>
        )}
      </div>
      <p className="text-sm text-gray-500 mt-2 leading-relaxed">{lic.description}</p>
      <p className="text-xs text-gray-400 mt-1">Required by: {lic.required_by.join(' · ')}</p>

      {!lic.installed && (
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={`Paste your ${lic.filename} contents here…`}
          className="w-full h-20 mt-3 border border-gray-300 rounded-md p-2 font-mono text-xs focus:ring-1 focus:ring-navy-500 focus:border-transparent"
        />
      )}
      {err && <p className="text-xs text-red-600 mt-2">{err}</p>}

      <div className="flex items-center gap-2 mt-3">
        <a href={lic.registration_url} target="_blank" rel="noreferrer"
           className="text-sm text-navy-600 font-semibold hover:underline">Get a license →</a>
        <span className="flex-1" />
        {lic.installed ? (
          <>
            <label className="px-3 py-1.5 text-sm bg-white border border-gray-300 rounded-md cursor-pointer hover:bg-gray-50">
              Replace
              <input type="file" className="hidden" onChange={(e) => onFile(e.target.files?.[0])} />
            </label>
            <button onClick={remove} disabled={busy}
              className="px-3 py-1.5 text-sm bg-white border border-red-200 text-red-700 rounded-md hover:bg-red-50 disabled:opacity-50">
              Remove
            </button>
          </>
        ) : (
          <>
            <label className="px-3 py-1.5 text-sm bg-white border border-gray-300 rounded-md cursor-pointer hover:bg-gray-50">
              Choose file…
              <input type="file" className="hidden" onChange={(e) => onFile(e.target.files?.[0])} />
            </label>
            <button onClick={() => save(text)} disabled={busy}
              className="px-3 py-1.5 text-sm bg-navy-600 text-white rounded-md font-medium hover:bg-navy-800 disabled:bg-gray-300">
              {busy ? 'Saving…' : 'Save license'}
            </button>
          </>
        )}
      </div>
    </div>
  );
};

const SettingsPage: React.FC = () => {
  const [licenses, setLicenses] = useState<LicenseInfo[]>([]);
  const [loading, setLoading] = useState(true);

  const load = () => {
    apiService.getLicenses().then(setLicenses).catch(() => {}).finally(() => setLoading(false));
  };
  useEffect(load, []);

  return (
    <div className="min-h-screen bg-gray-50">
      <main className="max-w-3xl mx-auto px-6 py-10">
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>

        <h2 className="text-xs font-semibold uppercase tracking-widest text-gray-400 mt-8 mb-1">Licenses</h2>
        <p className="text-sm text-gray-500 mb-4 leading-relaxed">
          Upload each license once — jobs that need it use it automatically (locally and on HPC).
          Stored privately in your data folder; never uploaded anywhere.
        </p>

        {loading ? (
          <p className="text-sm text-gray-400">Loading…</p>
        ) : (
          licenses.map((lic) => <LicenseCard key={lic.id} lic={lic} onChange={load} />)
        )}

        <p className="text-xs text-gray-400 mt-2">
          More licenses appear here automatically as new pipelines require them.
        </p>
      </main>
    </div>
  );
};

export default SettingsPage;
