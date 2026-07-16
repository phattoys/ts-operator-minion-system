import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, RefreshCw, Play, ListChecks, GitBranch, Paperclip,
  ChevronDown, ChevronUp, ShieldAlert, AlertTriangle, CheckCircle2,
  Link2, FileWarning,
} from 'lucide-react';
import { getManifest, validateManifest, queueAllReady, queueItem, getTrace } from '../lib/executionManifestApi';
import { deriveSupportBadge, SUPPORT_BADGE_STYLE, FOUNDER_GATED_WORKERS } from '../lib/executionManifestSupport';

const ITEM_STATUS_STYLES = {
  pending: 'text-zinc-500 border-zinc-800',
  needs_review: 'text-red-400 border-red-800',
  ready: 'text-emerald-400 border-emerald-800',
  queued: 'text-amber-400 border-amber-800',
  processing: 'text-amber-400 border-amber-800',
  completed: 'text-emerald-400 border-emerald-800',
  blocked: 'text-red-500 border-red-900',
  failed: 'text-red-500 border-red-900',
  cancelled: 'text-zinc-500 border-zinc-800',
};

export default function ExecutionManifestDetail() {
  const { manifestId } = useParams();
  const navigate = useNavigate();

  const [manifest, setManifest] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionMessage, setActionMessage] = useState(null);
  const [validating, setValidating] = useState(false);
  const [queueingAll, setQueueingAll] = useState(false);
  const [queueingItem, setQueueingItem] = useState(null);
  const [expandedItem, setExpandedItem] = useState(null);
  const [traceByItem, setTraceByItem] = useState({});

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getManifest(manifestId);
      setManifest(data);
    } catch (err) {
      console.error('Failed to load manifest:', err);
      setError(err?.response?.status === 404
        ? 'Manifest not found.'
        : 'Could not load this manifest. The Execution Manifest Layer backend may be unreachable.');
      setManifest(null);
    } finally {
      setLoading(false);
    }
  }, [manifestId]);

  useEffect(() => { load(); }, [load]);

  const handleValidate = async () => {
    setValidating(true);
    setActionMessage(null);
    try {
      const result = await validateManifest(manifestId);
      setActionMessage(result.errors && result.errors.length > 0
        ? `Validation found ${result.errors.length} issue(s): ${result.errors.join('; ')}`
        : 'Validation passed. Items are now annotated with routing decisions.');
      await load();
    } catch (err) {
      setActionMessage(`Validation failed: ${err?.response?.data?.detail || err.message}`);
    } finally {
      setValidating(false);
    }
  };

  const handleQueueAll = async () => {
    setQueueingAll(true);
    setActionMessage(null);
    try {
      const result = await queueAllReady(manifestId);
      const queuedCount = (result.items || []).filter((i) => i.queued).length;
      const alreadyCount = (result.items || []).filter((i) => i.already_queued).length;
      setActionMessage(`Queued ${queuedCount} item(s).${alreadyCount ? ` ${alreadyCount} already queued.` : ''}`);
      await load();
    } catch (err) {
      setActionMessage(`Queue all failed: ${err?.response?.data?.detail || err.message}`);
    } finally {
      setQueueingAll(false);
    }
  };

  const handleQueueItem = async (itemId) => {
    setQueueingItem(itemId);
    setActionMessage(null);
    try {
      const result = await queueItem(manifestId, itemId);
      if (result.already_queued) {
        setActionMessage(`Item ${itemId} was already queued (worker task ${result.worker_task_id}) — no duplicate created.`);
      } else if (result.queued) {
        setActionMessage(`Item ${itemId} queued as a ${result.worker} task (${result.task_status}).`);
      } else {
        setActionMessage(`Item ${itemId} could not be queued: ${result.reason}`);
      }
      await load();
    } catch (err) {
      setActionMessage(`Queue failed: ${err?.response?.data?.detail || err.message}`);
    } finally {
      setQueueingItem(null);
    }
  };

  const toggleItem = async (itemId) => {
    if (expandedItem === itemId) {
      setExpandedItem(null);
      return;
    }
    setExpandedItem(itemId);
    if (!traceByItem[itemId]) {
      try {
        const trace = await getTrace(manifestId);
        setTraceByItem((prev) => ({ ...prev, ...Object.fromEntries((trace.items || []).map((t) => [t.item_id, t])) }));
      } catch (err) {
        console.error('Failed to load trace:', err);
      }
    }
  };

  if (loading) {
    return <div className="p-6 text-zinc-500 text-sm" data-testid="manifest-detail-loading">Loading manifest...</div>;
  }

  if (error || !manifest) {
    return (
      <div className="p-6">
        <button onClick={() => navigate('/execution-manifests')} className="flex items-center gap-1.5 text-zinc-500 text-sm mb-4">
          <ArrowLeft className="w-3.5 h-3.5" /> Back to manifests
        </button>
        <div className="p-4 border border-red-900 bg-red-950/20 text-red-300 text-sm rounded" data-testid="manifest-detail-error">
          {error || 'Manifest not found.'}
        </div>
      </div>
    );
  }

  const items = manifest.execution_items || [];
  const readyCount = items.filter((i) => i.status === 'ready').length;

  return (
    <div className="p-6 max-w-6xl mx-auto" data-testid="execution-manifest-detail">
      <button onClick={() => navigate('/execution-manifests')} className="flex items-center gap-1.5 text-zinc-500 text-sm mb-4 hover:text-zinc-300">
        <ArrowLeft className="w-3.5 h-3.5" /> Back to manifests
      </button>

      <div className="border border-zinc-800 rounded p-5 mb-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-lg font-medium text-zinc-100">{manifest.campaign_name || manifest.manifest_id}</h1>
            <div className="text-zinc-500 text-xs mt-1 flex items-center gap-3 flex-wrap">
              <span>Manifest: {manifest.manifest_id}</span>
              <span>Source: {manifest.source_system}</span>
              <span>Packet: {manifest.source_packet_id}</span>
              <span className={`px-2 py-0.5 border rounded ${ITEM_STATUS_STYLES[manifest.status] || 'text-zinc-400 border-zinc-700'}`}>{manifest.status}</span>
              <span>Priority: {manifest.priority}</span>
              {manifest.due_at && <span>Due: {new Date(manifest.due_at).toLocaleDateString()}</span>}
            </div>
            {manifest.notes && <div className="text-zinc-500 text-xs mt-2">Notes: {manifest.notes}</div>}
            {manifest.intake_receipt_id && (
              <div className="text-zinc-600 text-xs mt-2 flex items-center gap-3 flex-wrap" data-testid="manifest-intake-origin">
                <span className="text-zinc-500">Intake origin:</span>
                <span>Receipt {manifest.intake_receipt_id}</span>
                <span>Packet {manifest.intake_packet_id}</span>
                <span>{manifest.intake_source_system}</span>
                <span>{manifest.intake_transport}</span>
                {manifest.intake_received_at && <span>{new Date(manifest.intake_received_at).toLocaleString()}</span>}
              </div>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleValidate}
              disabled={validating}
              className="px-3 py-1.5 text-xs border border-zinc-700 rounded text-zinc-300 hover:bg-zinc-800 flex items-center gap-1.5 disabled:opacity-50"
              data-testid="validate-manifest-btn"
            >
              <ListChecks className="w-3.5 h-3.5" /> {validating ? 'Validating...' : 'Validate'}
            </button>
            <button
              onClick={handleQueueAll}
              disabled={queueingAll || readyCount === 0}
              className="px-3 py-1.5 text-xs border border-emerald-800 text-emerald-400 rounded hover:bg-emerald-950/30 flex items-center gap-1.5 disabled:opacity-40"
              data-testid="queue-all-ready-btn"
              title={readyCount === 0 ? 'No ready items to queue' : `Queue ${readyCount} ready item(s)`}
            >
              <Play className="w-3.5 h-3.5" /> {queueingAll ? 'Queueing...' : `Queue All Ready (${readyCount})`}
            </button>
            <button onClick={load} className="p-1.5 border border-zinc-800 rounded text-zinc-500 hover:text-zinc-300" data-testid="refresh-manifest-detail">
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {manifest.assets && manifest.assets.length > 0 && (
          <AssetIndex assets={manifest.assets} items={items} />
        )}
      </div>

      {actionMessage && (
        <div className="mb-4 p-3 border border-zinc-700 bg-zinc-900/50 text-zinc-300 text-sm rounded" data-testid="manifest-action-message">
          {actionMessage}
        </div>
      )}

      <h2 className="text-sm font-medium text-zinc-400 mb-3">Execution Items ({items.length})</h2>

      {items.length === 0 ? (
        <div className="text-center py-12 border border-dashed border-zinc-800 rounded text-zinc-500 text-sm" data-testid="no-execution-items">
          This manifest has no execution items.
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <ExecutionItemCard
              key={item.item_id}
              item={item}
              expanded={expandedItem === item.item_id}
              onToggle={() => toggleItem(item.item_id)}
              onQueue={() => handleQueueItem(item.item_id)}
              queueing={queueingItem === item.item_id}
              trace={traceByItem[item.item_id]}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function ExecutionItemCard({ item, expanded, onToggle, onQueue, queueing, trace }) {
  const { badge, reason } = deriveSupportBadge(item);
  const isSupportedNow = item.status === 'ready';
  const alreadyQueued = !!item.worker_task_id;
  const isFounderGated = FOUNDER_GATED_WORKERS.has(item.recommended_worker);

  return (
    <div className="border border-zinc-800 rounded" data-testid={`execution-item-${item.item_id}`}>
      <div className="p-4 flex items-start justify-between cursor-pointer" onClick={onToggle}>
        <div className="flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-zinc-200 text-sm">{item.title}</span>
            <span className={`px-2 py-0.5 border rounded text-xs ${ITEM_STATUS_STYLES[item.status] || 'text-zinc-400 border-zinc-700'}`}>{item.status}</span>
            <span className={`px-2 py-0.5 border rounded text-xs ${SUPPORT_BADGE_STYLE[badge]}`} data-testid={`support-badge-${item.item_id}`}>{badge}</span>
            {isFounderGated && (
              <span className="px-2 py-0.5 border border-purple-800 text-purple-300 rounded text-xs flex items-center gap-1">
                <ShieldAlert className="w-3 h-3" /> Founder-gated
              </span>
            )}
          </div>
          {item.description && <div className="text-zinc-500 text-xs mt-1">{item.description}</div>}
          <div className="text-zinc-600 text-xs mt-1 flex items-center gap-3 flex-wrap">
            <span>{item.destination}{item.channel ? ` / ${item.channel}` : ''}{item.platform ? ` / ${item.platform}` : ''}</span>
            <span>{item.execution_type}</span>
            <span>Priority: {item.priority}</span>
            {item.due_at && <span>Due: {new Date(item.due_at).toLocaleDateString()}</span>}
            {item.recommended_worker && <span>Worker: {item.recommended_worker}</span>}
            {item.worker_task_id && <span>Task: {item.worker_task_id.slice(0, 8)}...</span>}
          </div>
          {!isSupportedNow && (
            <div className="text-xs text-amber-500 mt-1.5 flex items-center gap-1" data-testid={`item-reason-${item.item_id}`}>
              <AlertTriangle className="w-3 h-3" /> {reason}
            </div>
          )}
        </div>
        <div className="flex items-center gap-2 ml-4">
          {isSupportedNow && !alreadyQueued && (
            <button
              onClick={(e) => { e.stopPropagation(); onQueue(); }}
              disabled={queueing}
              className="px-2.5 py-1 text-xs border border-emerald-800 text-emerald-400 rounded hover:bg-emerald-950/30 disabled:opacity-50"
              data-testid={`queue-item-btn-${item.item_id}`}
            >
              {queueing ? 'Queueing...' : 'Queue Item'}
            </button>
          )}
          {alreadyQueued && (
            <span className="text-xs text-zinc-500 flex items-center gap-1" data-testid={`already-queued-${item.item_id}`}>
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" /> Queued
            </span>
          )}
          {!isSupportedNow && !alreadyQueued && (
            <span className="text-xs text-zinc-600" data-testid={`cannot-queue-${item.item_id}`}>Cannot queue</span>
          )}
          {expanded ? <ChevronUp className="w-4 h-4 text-zinc-600" /> : <ChevronDown className="w-4 h-4 text-zinc-600" />}
        </div>
      </div>

      {expanded && (
        <div className="border-t border-zinc-800 p-4 space-y-4 text-xs" data-testid={`execution-item-expanded-${item.item_id}`}>
          {item.copy && (
            <Field label="Copy"><div className="whitespace-pre-wrap text-zinc-300">{item.copy}</div></Field>
          )}
          {item.instructions && (
            <Field label="Instructions"><div className="whitespace-pre-wrap text-zinc-300">{item.instructions}</div></Field>
          )}
          {item.placement && Object.keys(item.placement).length > 0 && (
            <Field label="Placement"><pre className="text-zinc-400 whitespace-pre-wrap">{JSON.stringify(item.placement, null, 2)}</pre></Field>
          )}
          {item.compliance_notes && <Field label="Compliance Notes"><div className="text-zinc-400">{item.compliance_notes}</div></Field>}
          {item.qa_requirements && item.qa_requirements.length > 0 && (
            <Field label="QA Requirements">
              <ul className="list-disc list-inside text-zinc-400">{item.qa_requirements.map((q, i) => <li key={i}>{q}</li>)}</ul>
            </Field>
          )}
          {item.dependencies && item.dependencies.length > 0 && (
            <Field label="Dependencies"><div className="text-zinc-400">{item.dependencies.join(', ')}</div></Field>
          )}
          {item.asset_refs && item.asset_refs.length > 0 && (
            <Field label="Asset References"><div className="text-zinc-400 flex items-center gap-1"><Paperclip className="w-3 h-3" />{item.asset_refs.join(', ')}</div></Field>
          )}
          {item.warnings && item.warnings.length > 0 && (
            <Field label="Warnings">
              <ul className="space-y-1">
                {item.warnings.map((w, i) => (
                  <li key={i} className="text-amber-500 flex items-center gap-1"><FileWarning className="w-3 h-3" />{w}</li>
                ))}
              </ul>
            </Field>
          )}

          <TraceSection item={item} trace={trace} />
        </div>
      )}
    </div>
  );
}

function TraceSection({ item, trace }) {
  const chain = (trace && trace.worker_chain) || [];
  return (
    <Field label="Trace">
      <div className="flex items-center gap-2 flex-wrap text-zinc-400" data-testid={`trace-${item.item_id}`}>
        <TraceNode label="Manifest" value={item.manifest_id} />
        <GitBranch className="w-3 h-3 text-zinc-700" />
        <TraceNode label="Execution Item" value={item.item_id} />
        {chain.length > 0 ? (
          chain.map((task) => (
            <React.Fragment key={task.task_id}>
              <GitBranch className="w-3 h-3 text-zinc-700" />
              <TraceNode
                label={task.worker_name || task.worker}
                value={task.status}
                founderGated={task.founder_action_needed}
                testId={`trace-node-${item.item_id}-${task.worker}`}
              />
            </React.Fragment>
          ))
        ) : item.worker_task_id ? (
          <>
            <GitBranch className="w-3 h-3 text-zinc-700" />
            <TraceNode label="Worker Task" value={item.worker_task_id.slice(0, 8) + '...'} />
            <GitBranch className="w-3 h-3 text-zinc-700" />
            <TraceNode label="Worker" value={(trace && trace.worker) || item.recommended_worker || '—'} />
            <GitBranch className="w-3 h-3 text-zinc-700" />
            <TraceNode label="Status" value={(trace && trace.task_status) || item.status} />
          </>
        ) : (
          <span className="text-zinc-600">Not yet queued — no worker task exists.</span>
        )}
      </div>
      {trace && trace.task_warnings && trace.task_warnings.length > 0 && (
        <div className="mt-2 text-amber-500">
          {trace.task_warnings.map((w, i) => <div key={i} className="flex items-center gap-1"><AlertTriangle className="w-3 h-3" />{w}</div>)}
        </div>
      )}
      {trace && trace.task_result && Object.keys(trace.task_result).length > 0 && (
        <pre className="mt-2 text-zinc-500 whitespace-pre-wrap">{JSON.stringify(trace.task_result, null, 2)}</pre>
      )}
    </Field>
  );
}

function TraceNode({ label, value, founderGated, testId }) {
  return (
    <span
      className={`px-2 py-1 border rounded flex items-center gap-1 ${founderGated ? 'border-purple-800' : 'border-zinc-800'}`}
      data-testid={testId}
    >
      <Link2 className="w-3 h-3 text-zinc-700" />
      <span className="text-zinc-600">{label}:</span> <span className="text-zinc-300">{value}</span>
      {founderGated && <ShieldAlert className="w-3 h-3 text-purple-400" />}
    </span>
  );
}

function Field({ label, children }) {
  return (
    <div>
      <div className="text-zinc-600 uppercase tracking-wide text-[10px] mb-1">{label}</div>
      {children}
    </div>
  );
}

function AssetIndex({ assets, items }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-4 pt-4 border-t border-zinc-800">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300"
        data-testid="toggle-asset-index"
      >
        <Paperclip className="w-3.5 h-3.5" /> Assets ({assets.length}) {open ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
      </button>
      {open && (
        <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-2" data-testid="asset-index">
          {assets.map((asset) => {
            const usedBy = items.filter((i) => (i.asset_refs || []).includes(asset.asset_id));
            return (
              <div key={asset.asset_id} className="border border-zinc-800 rounded p-2 text-xs" data-testid={`asset-${asset.asset_id}`}>
                <div className="text-zinc-300">{asset.asset_id}</div>
                <div className="text-zinc-600">{asset.type || 'unknown type'}</div>
                {asset.url && <div className="text-zinc-500 truncate">{asset.url}</div>}
                {asset.alt_text && <div className="text-zinc-600">Alt: {asset.alt_text}</div>}
                <div className="text-zinc-600 mt-1">
                  Used by: {usedBy.length > 0 ? usedBy.map((i) => i.item_id).join(', ') : <span className="text-zinc-700">no items reference this asset</span>}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
