import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import {
  Users, Play, Pause, RotateCcw, CheckCircle, AlertTriangle,
  Clock, XCircle, ChevronDown, ChevronUp, Zap, Eye, Package, Globe,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const WORKER_ICONS = {
  jenny: Zap,
  rene: Eye,
  sam: Package,
  wp_placement: Globe,
};

const WORKER_COLORS = {
  jenny: 'text-amber-400 border-amber-800/50 bg-amber-950/20',
  rene: 'text-blue-400 border-blue-800/50 bg-blue-950/20',
  sam: 'text-purple-400 border-purple-800/50 bg-purple-950/20',
  wp_placement: 'text-emerald-400 border-emerald-800/50 bg-emerald-950/20',
};

const STATUS_STYLES = {
  queued: 'text-zinc-400 border-zinc-700',
  processing: 'text-amber-400 border-amber-800',
  completed: 'text-emerald-400 border-emerald-800',
  needs_review: 'text-red-400 border-red-800',
  failed: 'text-red-500 border-red-900',
  held_back: 'text-zinc-500 border-zinc-800',
};

export default function WorkerQueue() {
  const [stats, setStats] = useState(null);
  const [activeView, setActiveView] = useState('ready');
  const [tasks, setTasks] = useState([]);
  const [activityLog, setActivityLog] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedTask, setExpandedTask] = useState(null);
  const [runningWorker, setRunningWorker] = useState(null);

  const fetchStats = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/worker-queue/stats`, { withCredentials: true });
      setStats(res.data);
    } catch (err) {
      console.error('Failed to load stats:', err);
    }
  }, []);

  const fetchTasks = useCallback(async (view) => {
    try {
      let url = `${API}/worker-queue/views/${view}`;
      if (view === 'all') url = `${API}/worker-queue/tasks?limit=50`;
      const res = await axios.get(url, { withCredentials: true });
      setTasks(res.data.tasks || []);
    } catch (err) {
      console.error('Failed to load tasks:', err);
      setTasks([]);
    }
  }, []);

  const fetchActivity = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/worker-queue/activity-log?limit=20`, { withCredentials: true });
      setActivityLog(res.data.logs || []);
    } catch (err) {
      console.error('Failed to load activity:', err);
    }
  }, []);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      await Promise.all([fetchStats(), fetchTasks(activeView), fetchActivity()]);
      setLoading(false);
    };
    load();
  }, [fetchStats, fetchTasks, fetchActivity, activeView]);

  const handleExecuteTask = async (taskId) => {
    try {
      await axios.post(`${API}/worker-queue/tasks/${taskId}/execute`, {}, { withCredentials: true });
      await Promise.all([fetchStats(), fetchTasks(activeView), fetchActivity()]);
    } catch (err) {
      alert(err.response?.data?.detail || 'Execution failed');
    }
  };

  const handleHoldTask = async (taskId) => {
    try {
      await axios.post(`${API}/worker-queue/tasks/${taskId}/hold`, {}, { withCredentials: true });
      await Promise.all([fetchStats(), fetchTasks(activeView), fetchActivity()]);
    } catch (err) {
      alert(err.response?.data?.detail || 'Hold failed');
    }
  };

  const handleRequeueTask = async (taskId) => {
    try {
      await axios.post(`${API}/worker-queue/tasks/${taskId}/requeue`, {}, { withCredentials: true });
      await Promise.all([fetchStats(), fetchTasks(activeView), fetchActivity()]);
    } catch (err) {
      alert(err.response?.data?.detail || 'Requeue failed');
    }
  };

  const handleRunWorker = async (worker, batchId) => {
    setRunningWorker(worker);
    try {
      const res = await axios.post(`${API}/worker-queue/run-worker`, {
        worker,
        batch_id: batchId || '',
        item_ids: [],
      }, { withCredentials: true });
      alert(`${res.data.worker_name}: ${res.data.tasks_created} tasks created${res.data.auto_executed ? ' (auto-executing)' : ''}`);
      await Promise.all([fetchStats(), fetchTasks(activeView), fetchActivity()]);
    } catch (err) {
      alert(err.response?.data?.detail || 'Worker run failed');
    }
    setRunningWorker(null);
  };

  const handleBatchExecute = async () => {
    const readyTasks = tasks.filter(t => t.status === 'queued' && t.founder_action_needed);
    if (readyTasks.length === 0) {
      alert('No tasks ready for execution');
      return;
    }
    try {
      const res = await axios.post(`${API}/worker-queue/batch-execute`, {
        task_ids: readyTasks.map(t => t.id),
      }, { withCredentials: true });
      alert(`Executed: ${res.data.executed}, Skipped: ${res.data.skipped}, Failed: ${res.data.failed}`);
      await Promise.all([fetchStats(), fetchTasks(activeView), fetchActivity()]);
    } catch (err) {
      alert(err.response?.data?.detail || 'Batch execution failed');
    }
  };

  const views = [
    { key: 'ready', label: 'Ready Now', count: stats?.queued || 0 },
    { key: 'needs-review', label: 'Needs Review', count: stats?.needs_review || 0 },
    { key: 'in-progress', label: 'In Progress', count: stats?.processing || 0 },
    { key: 'completed', label: 'Completed', count: stats?.completed || 0 },
    { key: 'held-back', label: 'Held Back', count: (stats?.failed || 0) + (stats?.held_back || 0) },
  ];

  const timeAgo = (iso) => {
    if (!iso) return '';
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  };

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[50vh]">
        <div className="text-zinc-500 text-sm animate-pulse">Loading worker queue...</div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl mx-auto" data-testid="worker-queue-page">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Users className="w-5 h-5" /> Worker Queue
          </h1>
          <p className="text-xs text-zinc-500 mt-0.5">
            {stats?.total || 0} total tasks &middot; {stats?.completed || 0} completed &middot; {stats?.needs_review || 0} need review
          </p>
        </div>
        {activeView === 'ready' && tasks.length > 0 && (
          <button
            onClick={handleBatchExecute}
            className="flex items-center gap-2 px-4 py-2 border border-emerald-800 text-emerald-400 text-sm hover:bg-emerald-950/30 transition"
            data-testid="batch-execute-btn"
          >
            <Play className="w-3.5 h-3.5" /> Execute All Ready ({tasks.filter(t => t.founder_action_needed).length})
          </button>
        )}
      </div>

      {/* Worker Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6" data-testid="worker-cards">
        {stats?.workers && Object.entries(stats.workers).map(([key, w]) => {
          const Icon = WORKER_ICONS[key] || Users;
          const colorClass = WORKER_COLORS[key] || 'text-zinc-400 border-zinc-700';
          return (
            <div key={key} className={`border p-3 ${colorClass}`} data-testid={`worker-card-${key}`}>
              <div className="flex items-center gap-2 mb-2">
                <Icon className="w-4 h-4" />
                <span className="text-sm font-medium">{w.name}</span>
                {w.auto_execute && <span className="text-[9px] bg-zinc-800 text-zinc-400 px-1 py-0.5 rounded">AUTO</span>}
              </div>
              <div className="text-[10px] text-zinc-500">{w.role}</div>
              <div className="flex items-center gap-3 mt-2 text-[10px]">
                <span>{w.completed} done</span>
                <span>{w.queued} queued</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* View Tabs */}
      <div className="flex items-center gap-1 mb-4 border-b border-zinc-800 pb-3" data-testid="view-tabs">
        {views.map(v => (
          <button
            key={v.key}
            onClick={() => setActiveView(v.key)}
            className={`px-3 py-1.5 text-xs transition ${
              activeView === v.key
                ? 'text-white border border-zinc-600 bg-zinc-800/50'
                : 'text-zinc-500 hover:text-zinc-300'
            }`}
            data-testid={`view-tab-${v.key}`}
          >
            {v.label}
            {v.count > 0 && <span className="ml-1.5 text-[10px] text-zinc-400">({v.count})</span>}
          </button>
        ))}
      </div>

      {/* Task List */}
      <div className="border border-zinc-800 mb-6" data-testid="task-list">
        {tasks.length === 0 && (
          <div className="p-8 text-center text-zinc-600 text-sm">
            No tasks in this view.
          </div>
        )}

        {tasks.map(task => {
          const Icon = WORKER_ICONS[task.worker] || Users;
          const isExpanded = expandedTask === task.id;

          return (
            <div key={task.id} className="border-b border-zinc-800/50 last:border-0">
              <div
                className="flex items-center gap-3 px-4 py-3 hover:bg-zinc-900/30 transition cursor-pointer"
                onClick={() => setExpandedTask(isExpanded ? null : task.id)}
                data-testid={`task-row-${task.id}`}
              >
                {/* Worker icon */}
                <div className={`w-8 h-8 flex items-center justify-center border ${WORKER_COLORS[task.worker] || 'border-zinc-700'}`}>
                  <Icon className="w-3.5 h-3.5" />
                </div>

                {/* Task info */}
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-white truncate">
                    {task.worker_name}: {task.next_action}
                  </div>
                  <div className="text-[10px] text-zinc-500 mt-0.5">
                    {task.source_module} &middot; {task.task_type} &middot; {timeAgo(task.created_at)}
                  </div>
                </div>

                {/* Status badge */}
                <span className={`text-[10px] border px-1.5 py-0.5 uppercase tracking-wider ${STATUS_STYLES[task.status] || 'text-zinc-400 border-zinc-700'}`}>
                  {task.status.replace('_', ' ')}
                </span>

                {/* Founder action indicator */}
                {task.founder_action_needed && task.status === 'queued' && (
                  <span className="text-[9px] bg-emerald-900/30 text-emerald-400 border border-emerald-800/50 px-1.5 py-0.5">
                    YOUR ACTION
                  </span>
                )}

                {/* Actions */}
                <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
                  {(task.status === 'queued' || task.status === 'needs_review') && (
                    <button
                      onClick={() => handleExecuteTask(task.id)}
                      className="p-1.5 text-emerald-400 hover:bg-emerald-950/30 transition"
                      title="Execute"
                      data-testid={`execute-task-${task.id}`}
                    >
                      <Play className="w-3.5 h-3.5" />
                    </button>
                  )}
                  {(task.status === 'queued' || task.status === 'needs_review') && (
                    <button
                      onClick={() => handleHoldTask(task.id)}
                      className="p-1.5 text-zinc-500 hover:text-white transition"
                      title="Hold back"
                    >
                      <Pause className="w-3.5 h-3.5" />
                    </button>
                  )}
                  {(task.status === 'held_back' || task.status === 'failed' || task.status === 'needs_review') && (
                    <button
                      onClick={() => handleRequeueTask(task.id)}
                      className="p-1.5 text-blue-400 hover:bg-blue-950/30 transition"
                      title="Requeue"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>

                {/* Expand */}
                {isExpanded ? <ChevronUp className="w-4 h-4 text-zinc-500" /> : <ChevronDown className="w-4 h-4 text-zinc-600" />}
              </div>

              {/* Expanded detail */}
              {isExpanded && (
                <div className="px-4 pb-4 pt-1 bg-zinc-900/20 border-t border-zinc-800/50" data-testid={`task-detail-${task.id}`}>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                    <div className="space-y-2">
                      <div><span className="text-zinc-600">Task ID:</span> <span className="text-zinc-400">{task.id}</span></div>
                      <div><span className="text-zinc-600">Source Module:</span> <span className="text-zinc-400">{task.source_module}</span></div>
                      <div><span className="text-zinc-600">Source Item:</span> <span className="text-zinc-400">{task.source_item_id}</span></div>
                      {task.source_batch_id && <div><span className="text-zinc-600">Batch:</span> <span className="text-zinc-400">{task.source_batch_id}</span></div>}
                      <div><span className="text-zinc-600">Created:</span> <span className="text-zinc-400">{new Date(task.created_at).toLocaleString()}</span></div>
                      {task.completed_at && <div><span className="text-zinc-600">Completed:</span> <span className="text-zinc-400">{new Date(task.completed_at).toLocaleString()}</span></div>}
                    </div>
                    <div className="space-y-2">
                      {task.result?.summary && (
                        <div><span className="text-zinc-600">Result:</span> <span className="text-white">{task.result.summary}</span></div>
                      )}
                      {task.result?.reason && (
                        <div><span className="text-zinc-600">Reason:</span> <span className="text-red-400">{task.result.reason}</span></div>
                      )}
                      {task.result?.changes && Object.keys(task.result.changes).length > 0 && (
                        <div>
                          <span className="text-zinc-600">Changes:</span>
                          <div className="mt-1 bg-zinc-950 border border-zinc-800 p-2 text-[10px]">
                            {Object.entries(task.result.changes).filter(([k]) => k !== 'updated_at').map(([k, v]) => (
                              <div key={k} className="text-zinc-400"><span className="text-zinc-600">{k}:</span> {typeof v === 'string' ? v : JSON.stringify(v)}</div>
                            ))}
                          </div>
                        </div>
                      )}
                      {task.warnings?.length > 0 && (
                        <div>
                          <span className="text-zinc-600">Warnings:</span>
                          {task.warnings.map((w, i) => (
                            <div key={i} className="flex items-center gap-1 text-amber-400 text-[10px] mt-0.5">
                              <AlertTriangle className="w-3 h-3" /> {w}
                            </div>
                          ))}
                        </div>
                      )}
                      {task.result?.issues?.length > 0 && (
                        <div>
                          <span className="text-zinc-600">Issues:</span>
                          {task.result.issues.map((issue, i) => (
                            <div key={i} className="flex items-center gap-1 text-red-400 text-[10px] mt-0.5">
                              <XCircle className="w-3 h-3" /> {issue}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Activity Log */}
      <div className="border border-zinc-800" data-testid="activity-log">
        <div className="px-4 py-2 border-b border-zinc-800 flex items-center gap-2">
          <Clock className="w-3.5 h-3.5 text-zinc-600" />
          <span className="text-[10px] text-zinc-500 uppercase tracking-wider">Activity Log</span>
        </div>
        {activityLog.length === 0 ? (
          <div className="p-6 text-center text-zinc-600 text-xs">No activity yet. Workers will log actions here.</div>
        ) : (
          <div className="max-h-64 overflow-y-auto">
            {activityLog.map(log => {
              const Icon = WORKER_ICONS[log.worker] || Users;
              return (
                <div key={log.id} className="flex items-center gap-3 px-4 py-2 border-b border-zinc-800/30 last:border-0">
                  <Icon className="w-3.5 h-3.5 text-zinc-500 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <span className="text-xs text-white">{log.worker_name}</span>
                    <span className="text-xs text-zinc-500 mx-1.5">&middot;</span>
                    <span className="text-xs text-zinc-400">{log.summary || log.action}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {log.success ? (
                      <CheckCircle className="w-3 h-3 text-emerald-500" />
                    ) : (
                      <AlertTriangle className="w-3 h-3 text-red-400" />
                    )}
                    <span className="text-[10px] text-zinc-600">{timeAgo(log.timestamp)}</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
