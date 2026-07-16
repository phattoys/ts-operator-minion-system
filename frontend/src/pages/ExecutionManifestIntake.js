import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Upload, FileJson, CheckCircle2, XCircle, AlertTriangle,
  ArrowRight, RefreshCw, Filter, Inbox, ChevronDown, ChevronUp,
} from 'lucide-react';
import { submitManualIntake, listReceipts, retryReceipt } from '../lib/executionManifestIntakeApi';

const STATUS_STYLES = {
  received: 'text-zinc-400 border-zinc-700',
  authenticated: 'text-blue-400 border-blue-800',
  rejected: 'text-red-400 border-red-800',
  duplicate: 'text-amber-400 border-amber-800',
  quarantined: 'text-red-500 border-red-900',
  validated: 'text-blue-400 border-blue-800',
  accepted: 'text-emerald-400 border-emerald-800',
  failed: 'text-red-500 border-red-900',
};

/**
 * Client-side check is READABILITY ONLY (does this parse as JSON at all).
 * The backend (services/execution_manifest.validate_manifest +
 * services/execution_manifest_intake) remains the sole authority on
 * schema, destination support, checksum, and safety validation -- nothing
 * here duplicates that logic.
 */
function buildLocalPreview(parsed) {
  if (!parsed || typeof parsed !== 'object') return null;
  const manifest = parsed.manifest || {};
  const items = manifest.execution_items || [];
  const destinationCounts = {};
  items.forEach((i) => {
    const d = i.destination || 'unknown';
    destinationCounts[d] = (destinationCounts[d] || 0) + 1;
  });
  return {
    packetId: parsed.packet_id || null,
    sourceSystem: parsed.source_system || null,
    campaignName: parsed.campaign_name || manifest.campaign_name || null,
    itemCount: items.length,
    destinationCounts,
    assetRefCount: (parsed.asset_index || []).length,
  };
}

export default function ExecutionManifestIntake() {
  const navigate = useNavigate();
  const [rawText, setRawText] = useState('');
  const [parseError, setParseError] = useState(null);
  const [preview, setPreview] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const [submitError, setSubmitError] = useState(null);

  const [receipts, setReceipts] = useState([]);
  const [receiptsLoading, setReceiptsLoading] = useState(true);
  const [receiptsError, setReceiptsError] = useState(null);
  const [statusFilter, setStatusFilter] = useState('all');
  const [sourceFilter, setSourceFilter] = useState('all');
  const [transportFilter, setTransportFilter] = useState('all');
  const [rejectedOnly, setRejectedOnly] = useState(false);
  const [expandedReceipt, setExpandedReceipt] = useState(null);

  const loadReceipts = useCallback(async () => {
    setReceiptsLoading(true);
    setReceiptsError(null);
    try {
      const data = await listReceipts();
      setReceipts(data.receipts || []);
    } catch (err) {
      console.error('Failed to load intake receipts:', err);
      setReceiptsError('Could not load intake receipts. The Execution Manifest Intake backend may be unreachable.');
      setReceipts([]);
    } finally {
      setReceiptsLoading(false);
    }
  }, []);

  useEffect(() => { loadReceipts(); }, [loadReceipts]);

  const handleTextChange = (text) => {
    setRawText(text);
    setResult(null);
    setSubmitError(null);
    if (!text.trim()) {
      setParseError(null);
      setPreview(null);
      return;
    }
    try {
      const parsed = JSON.parse(text);
      setParseError(null);
      setPreview(buildLocalPreview(parsed));
    } catch (err) {
      setParseError(`This does not parse as JSON: ${err.message}`);
      setPreview(null);
    }
  };

  const handleFileUpload = (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (evt) => handleTextChange(String(evt.target.result));
    reader.readAsText(file);
  };

  const handleSubmit = async () => {
    let envelope;
    try {
      envelope = JSON.parse(rawText);
    } catch (err) {
      setParseError(`This does not parse as JSON: ${err.message}`);
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    setResult(null);
    try {
      const receipt = await submitManualIntake(envelope);
      setResult(receipt);
      loadReceipts();
    } catch (err) {
      setSubmitError(err?.response?.data?.detail
        ? (Array.isArray(err.response.data.detail) ? err.response.data.detail.join('; ') : String(err.response.data.detail))
        : err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const filteredReceipts = receipts.filter((r) => {
    if (statusFilter !== 'all' && r.status !== statusFilter) return false;
    if (sourceFilter !== 'all' && r.source_system !== sourceFilter) return false;
    if (transportFilter !== 'all' && r.transport !== transportFilter) return false;
    if (rejectedOnly && !['rejected', 'quarantined'].includes(r.status)) return false;
    return true;
  });

  const sourceSystems = Array.from(new Set(receipts.map((r) => r.source_system).filter(Boolean))).sort();

  return (
    <div className="p-6 max-w-6xl mx-auto" data-testid="execution-manifest-intake">
      <div className="flex items-center gap-3 mb-6">
        <FileJson className="w-5 h-5 text-zinc-400" />
        <h1 className="text-lg font-medium text-zinc-100">Execution Manifest Intake</h1>
      </div>

      <div className="border border-zinc-800 rounded p-5 mb-8">
        <h2 className="text-sm font-medium text-zinc-300 mb-3">Manual Intake</h2>
        <p className="text-xs text-zinc-500 mb-3">
          Paste or upload a machine-readable manifest packet JSON for testing, recovery, or a controlled manual
          handoff. This never automatically queues workers or writes to WordPress — the founder still reviews and
          queues in the Execution Manifests workspace.
        </p>

        <div className="flex items-center gap-3 mb-3">
          <label className="flex items-center gap-1.5 px-3 py-1.5 text-xs border border-zinc-700 rounded cursor-pointer text-zinc-300 hover:bg-zinc-800">
            <Upload className="w-3.5 h-3.5" /> Upload .json
            <input type="file" accept=".json,application/json" className="hidden" onChange={handleFileUpload} data-testid="intake-file-upload" />
          </label>
        </div>

        <textarea
          value={rawText}
          onChange={(e) => handleTextChange(e.target.value)}
          placeholder="Paste packet JSON here..."
          className="w-full h-48 bg-zinc-900 border border-zinc-800 rounded p-3 text-xs text-zinc-300 font-mono"
          data-testid="intake-json-textarea"
        />

        {parseError && (
          <div className="mt-2 p-2 border border-red-900 bg-red-950/20 text-red-300 text-xs rounded" data-testid="intake-parse-error">
            {parseError}
          </div>
        )}

        {preview && !parseError && (
          <div className="mt-3 p-3 border border-zinc-800 rounded text-xs" data-testid="intake-preview">
            <div className="text-zinc-500 uppercase tracking-wide text-[10px] mb-2">Packet Preview (local readability check only)</div>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-zinc-400">
              <div>Packet ID: <span className="text-zinc-200">{preview.packetId || '—'}</span></div>
              <div>Source system: <span className="text-zinc-200">{preview.sourceSystem || '—'}</span></div>
              <div>Campaign: <span className="text-zinc-200">{preview.campaignName || '—'}</span></div>
              <div>Items: <span className="text-zinc-200">{preview.itemCount}</span></div>
              <div>Asset refs: <span className="text-zinc-200">{preview.assetRefCount}</span></div>
              <div>
                Destinations:{' '}
                <span className="text-zinc-200">
                  {Object.entries(preview.destinationCounts).map(([d, c]) => `${d} (${c})`).join(', ') || '—'}
                </span>
              </div>
            </div>
          </div>
        )}

        <button
          onClick={handleSubmit}
          disabled={submitting || !rawText.trim() || !!parseError}
          className="mt-3 px-3 py-1.5 text-xs border border-emerald-800 text-emerald-400 rounded hover:bg-emerald-950/30 disabled:opacity-40 flex items-center gap-1.5"
          data-testid="intake-submit-btn"
        >
          {submitting ? 'Submitting...' : 'Submit for Intake'}
        </button>

        {submitError && (
          <div className="mt-3 p-3 border border-red-900 bg-red-950/20 text-red-300 text-xs rounded" data-testid="intake-submit-error">
            {submitError}
          </div>
        )}

        {result && (
          <div
            className={`mt-3 p-3 border rounded text-xs ${result.status === 'accepted' ? 'border-emerald-800 bg-emerald-950/20' : 'border-red-900 bg-red-950/20'}`}
            data-testid="intake-result"
          >
            <div className="flex items-center gap-2 mb-1">
              {result.status === 'accepted' ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <XCircle className="w-4 h-4 text-red-400" />}
              <span className={`px-2 py-0.5 border rounded ${STATUS_STYLES[result.status] || 'text-zinc-400 border-zinc-700'}`}>{result.status}</span>
              <span className="text-zinc-500">Receipt: {result.receipt_id}</span>
            </div>
            {result.manifest_id && (
              <div className="mt-1">
                Manifest: <span className="text-zinc-200">{result.manifest_id}</span>{' '}
                <button
                  onClick={() => navigate(`/execution-manifests/${result.manifest_id}`)}
                  className="text-blue-400 hover:underline inline-flex items-center gap-1"
                  data-testid="intake-result-manifest-link"
                >
                  View manifest <ArrowRight className="w-3 h-3" />
                </button>
              </div>
            )}
            {result.errors && result.errors.length > 0 && (
              <ul className="mt-2 space-y-1">
                {result.errors.map((e, i) => (
                  <li key={i} className="text-red-400 flex items-center gap-1"><AlertTriangle className="w-3 h-3" />{e}</li>
                ))}
              </ul>
            )}
            {result.warnings && result.warnings.length > 0 && (
              <ul className="mt-2 space-y-1">
                {result.warnings.map((w, i) => (
                  <li key={i} className="text-amber-400 flex items-center gap-1"><AlertTriangle className="w-3 h-3" />{w}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-medium text-zinc-300">Intake Receipts</h2>
        <button onClick={loadReceipts} className="p-1.5 border border-zinc-800 rounded text-zinc-500 hover:text-zinc-300" data-testid="refresh-receipts">
          <RefreshCw className={`w-3.5 h-3.5 ${receiptsLoading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {receiptsError && (
        <div className="mb-3 p-3 border border-red-900 bg-red-950/20 text-red-300 text-sm rounded" data-testid="receipts-error">
          {receiptsError}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2 mb-4 text-xs" data-testid="receipt-filters">
        <Filter className="w-3.5 h-3.5 text-zinc-600" />
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="bg-zinc-900 border border-zinc-800 rounded px-2 py-1 text-zinc-400" data-testid="receipt-filter-status">
          <option value="all">Status: All</option>
          {Object.keys(STATUS_STYLES).map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)} className="bg-zinc-900 border border-zinc-800 rounded px-2 py-1 text-zinc-400" data-testid="receipt-filter-source">
          <option value="all">Source: All</option>
          {sourceSystems.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={transportFilter} onChange={(e) => setTransportFilter(e.target.value)} className="bg-zinc-900 border border-zinc-800 rounded px-2 py-1 text-zinc-400" data-testid="receipt-filter-transport">
          <option value="all">Transport: All</option>
          <option value="server_to_server">server_to_server</option>
          <option value="manual">manual</option>
        </select>
        <label className="flex items-center gap-1.5 px-2 py-1 border border-zinc-800 rounded cursor-pointer text-zinc-400">
          <input type="checkbox" checked={rejectedOnly} onChange={(e) => setRejectedOnly(e.target.checked)} data-testid="receipt-filter-rejected-only" />
          Rejected/quarantined only
        </label>
      </div>

      {receiptsLoading ? (
        <div className="text-zinc-500 text-sm py-8 text-center" data-testid="receipts-loading">Loading receipts...</div>
      ) : filteredReceipts.length === 0 ? (
        <div className="text-center py-12 border border-dashed border-zinc-800 rounded" data-testid="receipts-empty-state">
          <Inbox className="w-8 h-8 text-zinc-700 mx-auto mb-3" />
          <p className="text-zinc-500 text-sm">
            {receipts.length === 0 ? 'No intake packets have been received yet.' : 'No receipts match the current filters.'}
          </p>
        </div>
      ) : (
        <div className="space-y-2" data-testid="receipts-list">
          {filteredReceipts.map((r) => (
            <ReceiptRow
              key={r.receipt_id}
              receipt={r}
              expanded={expandedReceipt === r.receipt_id}
              onToggle={() => setExpandedReceipt(expandedReceipt === r.receipt_id ? null : r.receipt_id)}
              onRetry={async () => { await retryReceipt(r.receipt_id); loadReceipts(); }}
              navigate={navigate}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function ReceiptRow({ receipt, expanded, onToggle, onRetry, navigate }) {
  const canRetry = receipt.status === 'quarantined' || receipt.status === 'failed' || receipt.status === 'rejected';
  return (
    <div className="border border-zinc-800 rounded" data-testid={`receipt-row-${receipt.receipt_id}`}>
      <div className="p-3 flex items-center justify-between cursor-pointer" onClick={onToggle}>
        <div className="flex items-center gap-3 flex-wrap text-xs">
          <span className="text-zinc-300">{receipt.receipt_id}</span>
          <span className="text-zinc-600">{receipt.packet_id || '—'}</span>
          <span className="text-zinc-500">{receipt.source_system}</span>
          <span className="text-zinc-500">{receipt.transport}</span>
          <span className={`px-2 py-0.5 border rounded ${STATUS_STYLES[receipt.status] || 'text-zinc-400 border-zinc-700'}`}>{receipt.status}</span>
          {receipt.manifest_id && <span className="text-blue-400">manifest: {receipt.manifest_id}</span>}
        </div>
        {expanded ? <ChevronUp className="w-4 h-4 text-zinc-600" /> : <ChevronDown className="w-4 h-4 text-zinc-600" />}
      </div>
      {expanded && (
        <div className="border-t border-zinc-800 p-3 text-xs space-y-2" data-testid={`receipt-detail-${receipt.receipt_id}`}>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-zinc-500">
            <div>Auth: <span className="text-zinc-300">{receipt.authentication_status}</span></div>
            <div>Checksum: <span className="text-zinc-300">{receipt.checksum_status}</span></div>
            <div>Schema: <span className="text-zinc-300">{receipt.schema_status}</span></div>
            <div>Received: <span className="text-zinc-300">{receipt.received_at ? new Date(receipt.received_at).toLocaleString() : '—'}</span></div>
          </div>
          {receipt.errors && receipt.errors.length > 0 && (
            <div>
              <div className="text-zinc-600 uppercase text-[10px] mb-1">Errors</div>
              {receipt.errors.map((e, i) => <div key={i} className="text-red-400 flex items-center gap-1"><AlertTriangle className="w-3 h-3" />{e}</div>)}
            </div>
          )}
          {receipt.warnings && receipt.warnings.length > 0 && (
            <div>
              <div className="text-zinc-600 uppercase text-[10px] mb-1">Warnings</div>
              {receipt.warnings.map((w, i) => <div key={i} className="text-amber-400 flex items-center gap-1"><AlertTriangle className="w-3 h-3" />{w}</div>)}
            </div>
          )}
          <div className="flex items-center gap-3 pt-1">
            {receipt.manifest_id && (
              <button
                onClick={() => navigate(`/execution-manifests/${receipt.manifest_id}`)}
                className="text-blue-400 hover:underline inline-flex items-center gap-1"
                data-testid={`receipt-manifest-link-${receipt.receipt_id}`}
              >
                View manifest <ArrowRight className="w-3 h-3" />
              </button>
            )}
            {canRetry && (
              <button
                onClick={onRetry}
                className="px-2 py-1 border border-zinc-700 rounded text-zinc-300 hover:bg-zinc-800"
                data-testid={`receipt-retry-${receipt.receipt_id}`}
              >
                Retry
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
