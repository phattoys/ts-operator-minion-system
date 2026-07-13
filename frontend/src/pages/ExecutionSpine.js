import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import {
  RefreshCw, Zap, AlertTriangle, CheckCircle, Clock, Ban,
  ArrowRight, ChevronDown, ChevronUp, Globe, Package, Camera,
  FileText, Activity,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const MODULE_LABELS = {
  page_ops: { label: 'Page Ops', icon: FileText, color: 'text-blue-400' },
  product_intake: { label: 'Product Intake', icon: Package, color: 'text-emerald-400' },
  field_listing: { label: 'Field-to-Listing', icon: Camera, color: 'text-amber-400' },
  wp_placement: { label: 'WP Placement', icon: Globe, color: 'text-purple-400' },
};

const STATUS_CONFIG = {
  new: { label: 'New', color: 'text-zinc-400 border-zinc-700 bg-zinc-900/30' },
  processing: { label: 'Processing', color: 'text-amber-400 border-amber-800 bg-amber-950/20' },
  needs_review: { label: 'Needs Review', color: 'text-orange-400 border-orange-800 bg-orange-950/20' },
  ready: { label: 'Ready', color: 'text-blue-400 border-blue-800 bg-blue-950/20' },
  exported: { label: 'Exported', color: 'text-emerald-400 border-emerald-800 bg-emerald-950/20' },
  drafted: { label: 'Drafted', color: 'text-purple-400 border-purple-800 bg-purple-950/20' },
  placed: { label: 'Placed', color: 'text-emerald-400 border-emerald-800 bg-emerald-950/20' },
  done: { label: 'Done', color: 'text-emerald-400 border-emerald-800 bg-emerald-950/20' },
  skipped: { label: 'Skipped', color: 'text-red-400 border-red-800 bg-red-950/20' },
  held_back: { label: 'Held Back', color: 'text-zinc-500 border-zinc-700 bg-zinc-900/30' },
};

const TYPE_LABELS = {
  page: 'Page',
  intake_session: 'Intake',
  field_batch: 'Field Batch',
};

function StatusBadge({ status }) {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.new;
  return (
    <span className={`text-[10px] border px-1.5 py-0.5 uppercase tracking-wider ${cfg.color}`} data-testid={`status-${status}`}>
      {cfg.label}
    </span>
  );
}

function TaskRow({ task, onExecute, executing }) {
  const [expanded, setExpanded] = useState(false);
  const mod = MODULE_LABELS[task.source_module] || {};
  const ModIcon = mod.icon || Activity;
  const action = task.available_action;
  const navigate = useNavigate();

  const getLink = () => {
    if (task.type === 'page') return `/page-ops`;
    if (task.type === 'intake_session') return `/intake/${task.ref_id}`;
    if (task.type === 'field_batch') return `/field-listing/${task.ref_id}`;
    return null;
  };

  return (
    <div className="border-b border-zinc-800/50 last:border-0">
      <div
        className="flex items-center gap-3 px-4 py-3 hover:bg-zinc-900/30 transition cursor-pointer"
        onClick={() => setExpanded(!expanded)}
        data-testid={`task-row-${task.ref_id}`}
      >
        <ModIcon className={`w-4 h-4 ${mod.color || 'text-zinc-500'} flex-shrink-0`} />
        <div className="flex-1 min-w-0">
          <div className="text-sm text-white truncate">{task.title}</div>
          <div className="text-xs text-zinc-500 mt-0.5 truncate">{task.summary}</div>
        </div>
        <div className="hidden sm:block text-[10px] text-zinc-600 uppercase w-16">{TYPE_LABELS[task.type] || task.type}</div>
        <StatusBadge status={task.status} />
        <div className="w-40 text-right">
          {action ? (
            <button
              onClick={(e) => { e.stopPropagation(); onExecute(task); }}
              disabled={executing === task.ref_id}
              className="flex items-center gap-1.5 ml-auto px-3 py-1 text-xs border border-emerald-800 text-emerald-400 hover:bg-emerald-950/30 disabled:opacity-40 transition"
              data-testid={`execute-${task.ref_id}`}
            >
              {executing === task.ref_id ? (
                <><RefreshCw className="w-3 h-3 animate-spin" /> Running...</>
              ) : (
                <><Zap className="w-3 h-3" /> {action.label}</>
              )}
            </button>
          ) : (
            <span className="text-[10px] text-zinc-600">{task.next_action}</span>
          )}
        </div>
        {expanded ? <ChevronUp className="w-4 h-4 text-zinc-600" /> : <ChevronDown className="w-4 h-4 text-zinc-700" />}
      </div>

      {expanded && (
        <div className="px-4 pb-3 pt-1 bg-zinc-900/20 border-t border-zinc-800/50">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
            <div>
              <span className="text-zinc-600">Source Module</span>
              <div className={mod.color || 'text-zinc-400'}>{mod.label || task.source_module}</div>
            </div>
            <div>
              <span className="text-zinc-600">Next Action</span>
              <div className="text-zinc-300">{task.next_action}</div>
            </div>
            <div>
              <span className="text-zinc-600">Founder Action?</span>
              <div className={task.founder_action_required ? 'text-amber-400' : 'text-zinc-500'}>
                {task.founder_action_required ? 'Yes' : 'No'}
              </div>
            </div>
            <div>
              <span className="text-zinc-600">Last Synced</span>
              <div className="text-zinc-400">{task.last_synced_at ? new Date(task.last_synced_at).toLocaleTimeString() : '—'}</div>
            </div>
          </div>
          {task.metadata && Object.keys(task.metadata).length > 0 && (
            <div className="mt-2 text-[10px] text-zinc-600">
              {Object.entries(task.metadata).filter(([, v]) => v && v !== 0 && (!Array.isArray(v) || v.length > 0)).map(([k, v]) => (
                <span key={k} className="mr-3">{k.replace(/_/g, ' ')}: <span className="text-zinc-400">{Array.isArray(v) ? v.join(', ') : v}</span></span>
              ))}
            </div>
          )}
          {getLink() && (
            <button
              onClick={() => navigate(getLink())}
              className="mt-2 flex items-center gap-1 text-xs text-zinc-500 hover:text-white transition"
            >
              Open in module <ArrowRight className="w-3 h-3" />
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export default function ExecutionSpine() {
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [executing, setExecuting] = useState(null);
  const [showLog, setShowLog] = useState(false);

  const fetchDashboard = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/spine/dashboard`, { withCredentials: true });
      setDashboard(res.data);
    } catch (err) {
      console.error('Spine dashboard error:', err);
    }
    setLoading(false);
  }, []);

  useEffect(() => { fetchDashboard(); }, [fetchDashboard]);

  const handleSync = async () => {
    setSyncing(true);
    await fetchDashboard();
    setSyncing(false);
  };

  const handleExecute = async (task) => {
    setExecuting(task.ref_id);
    try {
      const res = await axios.post(`${API}/spine/tasks/${task.ref_id}/execute`, {}, { withCredentials: true });
      const r = res.data;
      const msg = `${r.result === 'success' ? 'Done' : 'Failed'}: ${r.details || r.action}`;
      if (r.warnings?.length) {
        alert(`${msg}\n\nWarnings:\n${r.warnings.join('\n')}`);
      }
      await fetchDashboard();
    } catch (err) {
      alert(err.response?.data?.detail || 'Execution failed');
    }
    setExecuting(null);
  };

  if (loading) {
    return <div className="p-8 flex items-center justify-center min-h-[50vh]"><div className="text-zinc-500 text-sm animate-pulse">Loading spine...</div></div>;
  }

  if (!dashboard) {
    return <div className="p-8 text-center text-zinc-500">Failed to load spine dashboard</div>;
  }

  const { needs_action, in_progress, ready_to_execute, recently_completed, held_back, module_health, status_counts, recent_log } = dashboard;

  return (
    <div className="p-6 max-w-7xl mx-auto" data-testid="execution-spine">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Execution Spine</h1>
          <p className="text-sm text-zinc-500 mt-1">Connected workflow — routing, status, and one-click actions</p>
        </div>
        <button
          onClick={handleSync}
          disabled={syncing}
          className="flex items-center gap-2 px-4 py-2 border border-zinc-700 text-sm text-zinc-300 hover:border-zinc-500 disabled:opacity-40 transition"
          data-testid="sync-btn"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${syncing ? 'animate-spin' : ''}`} /> Sync
        </button>
      </div>

      {/* Status Summary */}
      <div className="grid grid-cols-3 sm:grid-cols-6 gap-3 mb-6">
        {[
          { label: 'TOTAL', value: dashboard.total_tasks, color: 'text-white' },
          { label: 'NEEDS ACTION', value: needs_action.length, color: needs_action.length > 0 ? 'text-amber-400' : 'text-zinc-500' },
          { label: 'IN PROGRESS', value: in_progress.length, color: in_progress.length > 0 ? 'text-blue-400' : 'text-zinc-500' },
          { label: 'READY', value: ready_to_execute.length, color: ready_to_execute.length > 0 ? 'text-emerald-400' : 'text-zinc-500' },
          { label: 'COMPLETED', value: recently_completed.length, color: 'text-zinc-400' },
          { label: 'HELD BACK', value: held_back.length, color: 'text-zinc-600' },
        ].map(s => (
          <div key={s.label} className="border border-zinc-800 p-3 text-center">
            <div className={`text-xl font-bold ${s.color}`}>{s.value}</div>
            <div className="text-[9px] text-zinc-600 uppercase tracking-wider mt-1">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Module Health */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-8">
        {Object.entries(module_health).map(([key, health]) => {
          const mod = MODULE_LABELS[key] || {};
          const ModIcon = mod.icon || Activity;
          return (
            <div key={key} className="border border-zinc-800 p-4" data-testid={`module-health-${key}`}>
              <div className="flex items-center gap-2 mb-3">
                <ModIcon className={`w-4 h-4 ${mod.color || 'text-zinc-500'}`} />
                <span className="text-sm text-white font-medium">{mod.label || key}</span>
                <span className="text-[10px] text-zinc-600 ml-auto">{health.total} items</span>
              </div>
              <div className="flex gap-4 text-xs">
                <div>
                  <span className="text-zinc-600">Action</span>
                  <div className={health.needs_action > 0 ? 'text-amber-400' : 'text-zinc-500'}>{health.needs_action}</div>
                </div>
                <div>
                  <span className="text-zinc-600">Ready</span>
                  <div className={health.ready > 0 ? 'text-emerald-400' : 'text-zinc-500'}>{health.ready}</div>
                </div>
                <div>
                  <span className="text-zinc-600">Done</span>
                  <div className="text-zinc-400">{health.done}</div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Ready to Execute — Top priority section */}
      {ready_to_execute.length > 0 && (
        <div className="mb-6" data-testid="ready-section">
          <div className="flex items-center gap-2 mb-3">
            <Zap className="w-4 h-4 text-emerald-400" />
            <h2 className="text-sm font-medium text-emerald-400">Ready to Execute</h2>
            <span className="text-[10px] text-zinc-600 ml-1">{ready_to_execute.length} items</span>
          </div>
          <div className="border border-emerald-900/40">
            {ready_to_execute.map(task => (
              <TaskRow key={task.ref_id} task={task} onExecute={handleExecute} executing={executing} />
            ))}
          </div>
        </div>
      )}

      {/* Needs Your Action */}
      {needs_action.length > 0 && (
        <div className="mb-6" data-testid="needs-action-section">
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <h2 className="text-sm font-medium text-amber-400">Needs Your Action</h2>
            <span className="text-[10px] text-zinc-600 ml-1">{needs_action.length} items</span>
          </div>
          <div className="border border-zinc-800">
            {needs_action.filter(t => t.status !== 'ready').map(task => (
              <TaskRow key={task.ref_id} task={task} onExecute={handleExecute} executing={executing} />
            ))}
          </div>
        </div>
      )}

      {/* In Progress */}
      {in_progress.length > 0 && (
        <div className="mb-6" data-testid="in-progress-section">
          <div className="flex items-center gap-2 mb-3">
            <Clock className="w-4 h-4 text-blue-400" />
            <h2 className="text-sm font-medium text-blue-400">In Progress</h2>
            <span className="text-[10px] text-zinc-600 ml-1">{in_progress.length} items</span>
          </div>
          <div className="border border-zinc-800">
            {in_progress.map(task => (
              <TaskRow key={task.ref_id} task={task} onExecute={handleExecute} executing={executing} />
            ))}
          </div>
        </div>
      )}

      {/* Recently Completed */}
      {recently_completed.length > 0 && (
        <div className="mb-6" data-testid="completed-section">
          <div className="flex items-center gap-2 mb-3">
            <CheckCircle className="w-4 h-4 text-zinc-500" />
            <h2 className="text-sm font-medium text-zinc-400">Recently Completed</h2>
            <span className="text-[10px] text-zinc-600 ml-1">{recently_completed.length}</span>
          </div>
          <div className="border border-zinc-800">
            {recently_completed.map(task => (
              <TaskRow key={task.ref_id} task={task} onExecute={handleExecute} executing={executing} />
            ))}
          </div>
        </div>
      )}

      {/* Held Back */}
      {held_back.length > 0 && (
        <div className="mb-6" data-testid="held-back-section">
          <div className="flex items-center gap-2 mb-3">
            <Ban className="w-4 h-4 text-zinc-600" />
            <h2 className="text-sm font-medium text-zinc-500">Held Back / Skipped</h2>
            <span className="text-[10px] text-zinc-600 ml-1">{held_back.length}</span>
          </div>
          <div className="border border-zinc-800">
            {held_back.map(task => (
              <TaskRow key={task.ref_id} task={task} onExecute={handleExecute} executing={executing} />
            ))}
          </div>
        </div>
      )}

      {/* Execution Log */}
      <div className="mt-8" data-testid="execution-log">
        <button
          onClick={() => setShowLog(!showLog)}
          className="flex items-center gap-2 text-sm text-zinc-500 hover:text-zinc-300 transition"
        >
          <Activity className="w-3.5 h-3.5" />
          Execution Log {recent_log.length > 0 && `(${recent_log.length})`}
          {showLog ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        </button>
        {showLog && (
          <div className="mt-3 border border-zinc-800">
            {recent_log.length === 0 ? (
              <div className="p-4 text-xs text-zinc-600 text-center">No executions yet</div>
            ) : (
              recent_log.map((entry, i) => (
                <div key={i} className="flex items-center gap-3 px-4 py-2 border-b border-zinc-800/50 last:border-0 text-xs">
                  <span className={entry.result === 'success' ? 'text-emerald-400' : 'text-red-400'}>
                    {entry.result === 'success' ? <CheckCircle className="w-3 h-3" /> : <AlertTriangle className="w-3 h-3" />}
                  </span>
                  <span className="text-zinc-400 flex-1">{entry.action.replace(/_/g, ' ')} — {entry.details?.slice(0, 80) || entry.action}</span>
                  <span className="text-zinc-600">{entry.status_before} → {entry.status_after}</span>
                  <span className="text-zinc-700">{entry.executed_at ? new Date(entry.executed_at).toLocaleTimeString() : ''}</span>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
}
