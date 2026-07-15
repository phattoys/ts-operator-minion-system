import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Layers, RefreshCw, AlertTriangle, CheckCircle2,
  Filter, ArrowUpDown, ShieldAlert, Inbox,
} from 'lucide-react';
import { listManifests, getTrace } from '../lib/executionManifestApi';
import { FOUNDER_GATED_WORKERS } from '../lib/executionManifestSupport';

const MANIFEST_STATUS_STYLES = {
  received: 'text-zinc-400 border-zinc-700',
  validated: 'text-blue-400 border-blue-800',
  needs_review: 'text-red-400 border-red-800',
  ready: 'text-emerald-400 border-emerald-800',
  in_progress: 'text-amber-400 border-amber-800',
  partially_completed: 'text-amber-400 border-amber-800',
  completed: 'text-emerald-400 border-emerald-800',
  blocked: 'text-red-500 border-red-900',
  failed: 'text-red-500 border-red-900',
  cancelled: 'text-zinc-500 border-zinc-800',
};

function itemCounts(items) {
  const total = items.length;
  const completed = items.filter((i) => i.status === 'completed').length;
  const blocked = items.filter((i) => i.status === 'blocked' || i.status === 'needs_review').length;
  // Approximate for the table column only -- an item's recommended_worker
  // reflects the ORIGINAL routing decision (e.g. "jenny"), not necessarily
  // the currently-active worker further down an auto-executed chain (e.g.
  // once Jenny -> Rene have completed and WP Placement is now the
  // actionable step). The Founder Action Center view below is the
  // authoritative source -- it inspects each item's real worker chain via
  // the trace endpoint rather than guessing from this field.
  const founderAction = items.filter(
    (i) => i.status === 'needs_review' || (i.status === 'queued' && FOUNDER_GATED_WORKERS.has(i.recommended_worker)),
  ).length;
  return { total, completed, blocked, founderAction };
}

export default function ExecutionManifestList() {
  const navigate = useNavigate();
  const [manifests, setManifests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [view, setView] = useState('all'); // 'all' | 'founder-action'

  const [founderActionRows, setFounderActionRows] = useState([]);
  const [founderActionLoading, setFounderActionLoading] = useState(false);
  const [founderActionError, setFounderActionError] = useState(null);
  const [founderActionCount, setFounderActionCount] = useState(0);

  const [statusFilter, setStatusFilter] = useState('all');
  const [destinationFilter, setDestinationFilter] = useState('all');
  const [priorityFilter, setPriorityFilter] = useState('all');
  const [sourceFilter, setSourceFilter] = useState('all');
  const [founderOnly, setFounderOnly] = useState(false);
  const [blockedOnly, setBlockedOnly] = useState(false);
  const [sortBy, setSortBy] = useState('newest');

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listManifests();
      setManifests(data.manifests || []);
    } catch (err) {
      console.error('Failed to load execution manifests:', err);
      setError('Could not load execution manifests. The Execution Manifest Layer backend may be unreachable.');
      setManifests([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const destinations = useMemo(() => {
    const set = new Set();
    manifests.forEach((m) => (m.execution_items || []).forEach((i) => set.add(i.destination)));
    return Array.from(set).sort();
  }, [manifests]);

  const sourceSystems = useMemo(() => {
    const set = new Set(manifests.map((m) => m.source_system).filter(Boolean));
    return Array.from(set).sort();
  }, [manifests]);

  const filtered = useMemo(() => {
    let rows = manifests.map((m) => ({ manifest: m, counts: itemCounts(m.execution_items || []) }));

    if (statusFilter !== 'all') rows = rows.filter((r) => r.manifest.status === statusFilter);
    if (sourceFilter !== 'all') rows = rows.filter((r) => r.manifest.source_system === sourceFilter);
    if (priorityFilter !== 'all') rows = rows.filter((r) => r.manifest.priority === priorityFilter);
    if (destinationFilter !== 'all') {
      rows = rows.filter((r) => (r.manifest.execution_items || []).some((i) => i.destination === destinationFilter));
    }
    if (founderOnly) rows = rows.filter((r) => r.counts.founderAction > 0);
    if (blockedOnly) rows = rows.filter((r) => r.counts.blocked > 0);

    const priorityRank = { urgent: 0, high: 1, normal: 2, low: 3 };
    switch (sortBy) {
      case 'oldest':
        rows.sort((a, b) => new Date(a.manifest.created_at) - new Date(b.manifest.created_at));
        break;
      case 'due_date':
        rows.sort((a, b) => new Date(a.manifest.due_at || '9999-12-31') - new Date(b.manifest.due_at || '9999-12-31'));
        break;
      case 'priority':
        rows.sort((a, b) => (priorityRank[a.manifest.priority] ?? 9) - (priorityRank[b.manifest.priority] ?? 9));
        break;
      case 'most_blocked':
        rows.sort((a, b) => b.counts.blocked - a.counts.blocked);
        break;
      case 'most_founder_action':
        rows.sort((a, b) => b.counts.founderAction - a.counts.founderAction);
        break;
      case 'newest':
      default:
        rows.sort((a, b) => new Date(b.manifest.created_at) - new Date(a.manifest.created_at));
    }
    return rows;
  }, [manifests, statusFilter, sourceFilter, priorityFilter, destinationFilter, founderOnly, blockedOnly, sortBy]);

  // Founder Action Center: the authoritative source. Rather than guessing
  // from an item's status/recommended_worker (which only reflect the
  // ORIGINAL routing decision, not necessarily the currently-active step
  // in an auto-executed chain), this inspects each item's real worker
  // chain via the trace endpoint and surfaces any task where the backend
  // itself says founder_action_needed === true. A Metricool item that's
  // merely "blocked" never has a worker task at all (queueing refuses to
  // create one for an unsupported destination), so it can never appear
  // here unless the backend explicitly creates a founder-gated task for it.
  const loadFounderActions = useCallback(async (manifestList) => {
    if (manifestList.length === 0) {
      setFounderActionRows([]);
      setFounderActionCount(0);
      return;
    }
    setFounderActionLoading(true);
    setFounderActionError(null);
    try {
      const traces = await Promise.all(
        manifestList.map((m) => getTrace(m.manifest_id).catch((err) => {
          console.error(`Failed to load trace for ${m.manifest_id}:`, err);
          return null;
        })),
      );
      const rows = [];
      manifestList.forEach((manifest, idx) => {
        const trace = traces[idx];
        if (!trace) return;
        (trace.items || []).forEach((traceItem) => {
          (traceItem.worker_chain || []).forEach((task) => {
            if (task.founder_action_needed) {
              rows.push({ manifest, traceItem, task });
            }
          });
        });
      });
      setFounderActionRows(rows);
      setFounderActionCount(rows.length);
    } catch (err) {
      console.error('Failed to load founder actions:', err);
      setFounderActionError('Could not load founder actions. The Execution Manifest Layer backend may be unreachable.');
      setFounderActionRows([]);
    } finally {
      setFounderActionLoading(false);
    }
  }, []);

  useEffect(() => {
    if (manifests.length > 0) loadFounderActions(manifests);
    else { setFounderActionRows([]); setFounderActionCount(0); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [manifests]);

  return (
    <div className="p-6 max-w-7xl mx-auto" data-testid="execution-manifest-list">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Layers className="w-5 h-5 text-zinc-400" />
          <h1 className="text-lg font-medium text-zinc-100">Execution Manifests</h1>
        </div>
        <div className="flex items-center gap-2">
          <button
            className={`px-3 py-1.5 text-xs border rounded ${view === 'all' ? 'border-zinc-600 text-zinc-100 bg-zinc-800' : 'border-zinc-800 text-zinc-500'}`}
            onClick={() => setView('all')}
            data-testid="view-all-manifests"
          >
            All Manifests
          </button>
          <button
            className={`px-3 py-1.5 text-xs border rounded flex items-center gap-1.5 ${view === 'founder-action' ? 'border-red-700 text-red-300 bg-red-950/30' : 'border-zinc-800 text-zinc-500'}`}
            onClick={() => setView('founder-action')}
            data-testid="view-founder-action-center"
          >
            <ShieldAlert className="w-3.5 h-3.5" />
            Founder Action Center
            {founderActionCount > 0 && (
              <span className="ml-1 px-1.5 py-0.5 rounded-full bg-red-900/60 text-red-200 text-[10px]">{founderActionCount}</span>
            )}
          </button>
          <button onClick={load} className="p-1.5 border border-zinc-800 rounded text-zinc-500 hover:text-zinc-300" data-testid="refresh-manifests">
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 border border-red-900 bg-red-950/20 text-red-300 text-sm rounded" data-testid="manifest-list-error">
          {error}
        </div>
      )}

      {view === 'founder-action' ? (
        <FounderActionCenter
          rows={founderActionRows}
          loading={founderActionLoading}
          error={founderActionError}
          navigate={navigate}
        />
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2 mb-4 text-xs" data-testid="manifest-filters">
            <Filter className="w-3.5 h-3.5 text-zinc-600" />
            <FilterSelect label="Status" value={statusFilter} onChange={setStatusFilter} options={Object.keys(MANIFEST_STATUS_STYLES)} testId="filter-status" />
            <FilterSelect label="Destination" value={destinationFilter} onChange={setDestinationFilter} options={destinations} testId="filter-destination" />
            <FilterSelect label="Priority" value={priorityFilter} onChange={setPriorityFilter} options={['urgent', 'high', 'normal', 'low']} testId="filter-priority" />
            <FilterSelect label="Source System" value={sourceFilter} onChange={setSourceFilter} options={sourceSystems} testId="filter-source" />
            <label className="flex items-center gap-1.5 px-2 py-1 border border-zinc-800 rounded cursor-pointer text-zinc-400">
              <input type="checkbox" checked={founderOnly} onChange={(e) => setFounderOnly(e.target.checked)} data-testid="filter-founder-only" />
              Founder action needed
            </label>
            <label className="flex items-center gap-1.5 px-2 py-1 border border-zinc-800 rounded cursor-pointer text-zinc-400">
              <input type="checkbox" checked={blockedOnly} onChange={(e) => setBlockedOnly(e.target.checked)} data-testid="filter-blocked-only" />
              Blocked only
            </label>
            <div className="ml-auto flex items-center gap-1.5 text-zinc-500">
              <ArrowUpDown className="w-3.5 h-3.5" />
              <select value={sortBy} onChange={(e) => setSortBy(e.target.value)} className="bg-zinc-900 border border-zinc-800 rounded px-2 py-1" data-testid="sort-by">
                <option value="newest">Newest</option>
                <option value="oldest">Oldest</option>
                <option value="due_date">Due date</option>
                <option value="priority">Priority</option>
                <option value="most_blocked">Most blocked</option>
                <option value="most_founder_action">Most founder action needed</option>
              </select>
            </div>
          </div>

          {loading ? (
            <div className="text-zinc-500 text-sm py-12 text-center" data-testid="manifest-list-loading">Loading manifests...</div>
          ) : filtered.length === 0 ? (
            <EmptyState manifestsExist={manifests.length > 0} />
          ) : (
            <div className="border border-zinc-800 rounded overflow-hidden" data-testid="manifest-table">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-zinc-900/60 text-zinc-500 text-xs uppercase tracking-wide">
                    <th className="text-left px-4 py-2 font-normal">Manifest</th>
                    <th className="text-left px-4 py-2 font-normal">Source</th>
                    <th className="text-left px-4 py-2 font-normal">Status</th>
                    <th className="text-left px-4 py-2 font-normal">Priority</th>
                    <th className="text-left px-4 py-2 font-normal">Items</th>
                    <th className="text-left px-4 py-2 font-normal">Completed</th>
                    <th className="text-left px-4 py-2 font-normal">Blocked</th>
                    <th className="text-left px-4 py-2 font-normal">Founder Action</th>
                    <th className="text-left px-4 py-2 font-normal">Created</th>
                    <th className="text-left px-4 py-2 font-normal">Due</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(({ manifest, counts }) => (
                    <tr
                      key={manifest.manifest_id}
                      className="border-t border-zinc-800 hover:bg-zinc-900/40 cursor-pointer"
                      onClick={() => navigate(`/execution-manifests/${manifest.manifest_id}`)}
                      data-testid={`manifest-row-${manifest.manifest_id}`}
                    >
                      <td className="px-4 py-3">
                        <div className="text-zinc-200">{manifest.campaign_name || manifest.manifest_id}</div>
                        <div className="text-zinc-600 text-xs">{manifest.manifest_id}</div>
                      </td>
                      <td className="px-4 py-3 text-zinc-400">{manifest.source_system}</td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 border rounded text-xs ${MANIFEST_STATUS_STYLES[manifest.status] || 'text-zinc-400 border-zinc-700'}`}>
                          {manifest.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-zinc-400">{manifest.priority}</td>
                      <td className="px-4 py-3 text-zinc-400">{counts.total}</td>
                      <td className="px-4 py-3 text-emerald-400">{counts.completed}</td>
                      <td className="px-4 py-3 text-red-400">{counts.blocked}</td>
                      <td className="px-4 py-3">
                        {counts.founderAction > 0 ? (
                          <span className="flex items-center gap-1 text-red-300"><ShieldAlert className="w-3.5 h-3.5" />{counts.founderAction}</span>
                        ) : (
                          <span className="text-zinc-600">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-zinc-500 text-xs">{manifest.created_at ? new Date(manifest.created_at).toLocaleDateString() : '—'}</td>
                      <td className="px-4 py-3 text-zinc-500 text-xs">{manifest.due_at ? new Date(manifest.due_at).toLocaleDateString() : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function FilterSelect({ label, value, onChange, options, testId }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="bg-zinc-900 border border-zinc-800 rounded px-2 py-1 text-zinc-400"
      data-testid={testId}
      aria-label={label}
    >
      <option value="all">{label}: All</option>
      {options.map((opt) => (
        <option key={opt} value={opt}>{opt}</option>
      ))}
    </select>
  );
}

function EmptyState({ manifestsExist }) {
  return (
    <div className="text-center py-16 border border-dashed border-zinc-800 rounded" data-testid="manifest-empty-state">
      <Inbox className="w-8 h-8 text-zinc-700 mx-auto mb-3" />
      <p className="text-zinc-500 text-sm">
        {manifestsExist ? 'No manifests match the current filters.' : 'No execution manifests have been received yet.'}
      </p>
      {!manifestsExist && (
        <p className="text-zinc-600 text-xs mt-1">
          Manifests arrive from TSAF via the Execution Manifest Layer backend. Nothing to show until one is received.
        </p>
      )}
    </div>
  );
}

function FounderActionCenter({ rows, loading, error, navigate }) {
  if (loading) {
    return <div className="text-zinc-500 text-sm py-12 text-center" data-testid="founder-action-loading">Loading founder actions...</div>;
  }
  if (error) {
    return (
      <div className="p-3 border border-red-900 bg-red-950/20 text-red-300 text-sm rounded" data-testid="founder-action-error">
        {error}
      </div>
    );
  }
  if (rows.length === 0) {
    return (
      <div className="text-center py-16 border border-dashed border-zinc-800 rounded" data-testid="founder-action-empty-state">
        <CheckCircle2 className="w-8 h-8 text-emerald-700 mx-auto mb-3" />
        <p className="text-zinc-500 text-sm">Nothing needs founder action right now.</p>
      </div>
    );
  }
  return (
    <div className="space-y-3" data-testid="founder-action-list">
      {rows.map(({ manifest, traceItem, task }) => (
        <div
          key={`${manifest.manifest_id}-${traceItem.item_id}-${task.task_id}`}
          className="border border-zinc-800 rounded p-4 hover:border-zinc-700 cursor-pointer"
          onClick={() => navigate(`/execution-manifests/${manifest.manifest_id}`)}
          data-testid={`founder-action-item-${traceItem.item_id}-${task.worker}`}
        >
          <div className="flex items-start justify-between">
            <div>
              <div className="text-zinc-200 text-sm">{traceItem.title}</div>
              <div className="text-zinc-600 text-xs mt-0.5">
                {manifest.campaign_name} · {manifest.manifest_id} · item {traceItem.item_id}
              </div>
            </div>
            <span className="px-2 py-0.5 border border-purple-800 text-purple-300 rounded text-xs">{task.status}</span>
          </div>
          <div className="mt-2 text-xs text-zinc-500 flex items-center gap-2 flex-wrap">
            <span className="flex items-center gap-1">
              <AlertTriangle className="w-3 h-3 text-amber-500" />
              {task.worker_name || task.worker} task ({task.task_type}) is waiting on founder review — {task.next_action || 'no action description available'}.
            </span>
          </div>
          <div className="mt-2 text-xs text-zinc-600">
            Worker: <span className="text-zinc-400">{task.worker}</span> ·
            Destination: <span className="text-zinc-400">{traceItem.destination}</span> ·
            Task status: <span className="text-zinc-400">{task.status}</span> ·
            Next action: <span className="text-zinc-400">
              Open the item, run its dry-run preview if not already done, review, then approve to execute live
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

export { itemCounts };
