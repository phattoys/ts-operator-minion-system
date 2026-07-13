import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import {
  Zap, CheckCircle, XCircle, Clock, RotateCcw,
  ChevronDown, ChevronRight, Download, RefreshCw,
  AlertTriangle, Square, CheckSquare, Minus,
  Sparkles, FileText, Shield,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const STATUS_ORDER = [
  'Planned', 'Generating', 'Draft Ready', 'Needs Review',
  'Needs Rewrite', 'Approved', 'Deferred',
];

const STATUS_BADGES = {
  Planned: { color: 'text-zinc-400', bg: 'bg-zinc-800' },
  Generating: { color: 'text-yellow-400', bg: 'bg-yellow-900/20' },
  'Draft Ready': { color: 'text-blue-400', bg: 'bg-blue-900/20' },
  'Needs Review': { color: 'text-amber-400', bg: 'bg-amber-900/20' },
  'Needs Rewrite': { color: 'text-red-400', bg: 'bg-red-900/20' },
  Approved: { color: 'text-emerald-400', bg: 'bg-emerald-900/20' },
  Deferred: { color: 'text-zinc-500', bg: 'bg-zinc-800/50' },
};

const ACTIONS = [
  { type: 'generate', label: 'Generate', icon: Sparkles, desc: 'Generate draft content' },
  { type: 'score', label: 'Score', icon: Zap, desc: 'Score quality with Claude' },
  { type: 'tighten', label: 'Tighten', icon: FileText, desc: 'Apply taste tightener' },
  { type: 'status_change', label: 'Approve', icon: CheckCircle, desc: 'Set status to Approved', params: { target_status: 'Approved' } },
  { type: 'status_change', label: 'Rewrite', icon: RotateCcw, desc: 'Send to rewrite queue', params: { target_status: 'Needs Rewrite' } },
  { type: 'status_change', label: 'Defer', icon: Clock, desc: 'Defer for later', params: { target_status: 'Deferred' } },
  { type: 'export', label: 'Export ZIP', icon: Download, desc: 'Export as markdown ZIP' },
];

export default function BulkQueue() {
  const [pages, setPages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(new Set());
  const [searchQuery, setSearchQuery] = useState('');
  const [collapsedGroups, setCollapsedGroups] = useState(new Set());
  const [confirmAction, setConfirmAction] = useState(null);
  const [activeJob, setActiveJob] = useState(null);
  const [jobItems, setJobItems] = useState([]);
  const [recentJobs, setRecentJobs] = useState([]);
  const pollRef = useRef(null);

  const fetchPages = async () => {
    try {
      const res = await axios.get(`${API}/pages`, { withCredentials: true });
      setPages(res.data.pages || []);
    } catch (err) {
      console.error('Failed to fetch pages:', err);
    }
    setLoading(false);
  };

  const fetchRecentJobs = async () => {
    try {
      const res = await axios.get(`${API}/batch-jobs`, { withCredentials: true });
      setRecentJobs((res.data.jobs || []).slice(0, 5));
    } catch (err) {
      console.error('Failed to fetch jobs:', err);
    }
  };

  useEffect(() => {
    fetchPages();
    fetchRecentJobs();
  }, []);

  // Poll active job
  useEffect(() => {
    if (activeJob && ['queued', 'running'].includes(activeJob.state)) {
      pollRef.current = setInterval(async () => {
        try {
          const res = await axios.get(`${API}/batch-jobs/${activeJob.id}`, { withCredentials: true });
          setActiveJob(res.data.job);
          setJobItems(res.data.items || []);
          if (!['queued', 'running'].includes(res.data.job.state)) {
            clearInterval(pollRef.current);
            fetchPages();
            fetchRecentJobs();
          }
        } catch (err) {
          clearInterval(pollRef.current);
        }
      }, 1500);
      return () => clearInterval(pollRef.current);
    }
  }, [activeJob?.id, activeJob?.state]);

  const filtered = pages.filter(p =>
    !searchQuery || p.page_name?.toLowerCase().includes(searchQuery.toLowerCase())
    || p.slug?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const grouped = {};
  STATUS_ORDER.forEach(s => { grouped[s] = []; });
  filtered.forEach(p => {
    const st = p.status || 'Planned';
    if (grouped[st]) grouped[st].push(p);
    else {
      if (!grouped['Other']) grouped['Other'] = [];
      grouped['Other'].push(p);
    }
  });

  const toggleSelect = (id) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleGroupSelect = (status) => {
    const groupPages = grouped[status] || [];
    const groupIds = groupPages.map(p => p.id);
    const allSelected = groupIds.every(id => selected.has(id));
    setSelected(prev => {
      const next = new Set(prev);
      groupIds.forEach(id => {
        if (allSelected) next.delete(id);
        else next.add(id);
      });
      return next;
    });
  };

  const toggleCollapse = (status) => {
    setCollapsedGroups(prev => {
      const next = new Set(prev);
      if (next.has(status)) next.delete(status);
      else next.add(status);
      return next;
    });
  };

  const handleAction = async (action) => {
    if (selected.size === 0) return;
    try {
      const res = await axios.post(`${API}/batch-jobs`, {
        type: action.type,
        page_ids: Array.from(selected),
        params: action.params || {},
      }, { withCredentials: true });
      setActiveJob(res.data.job);
      setJobItems([]);
      setConfirmAction(null);
      if (action.type !== 'export') {
        setSelected(new Set());
      }
    } catch (err) {
      console.error('Batch action failed:', err);
    }
  };

  const handleCancel = async () => {
    if (!activeJob) return;
    try {
      await axios.post(`${API}/batch-jobs/${activeJob.id}/cancel`, {}, { withCredentials: true });
      setActiveJob(prev => ({ ...prev, state: 'canceled' }));
    } catch (err) {
      console.error('Cancel failed:', err);
    }
  };

  const handleRetryFailed = async () => {
    if (!activeJob) return;
    try {
      const res = await axios.post(`${API}/batch-jobs/${activeJob.id}/retry-failed`, {}, { withCredentials: true });
      setActiveJob(res.data.job);
      setJobItems([]);
    } catch (err) {
      console.error('Retry failed:', err);
    }
  };

  const handleDownload = async (jobId) => {
    try {
      const res = await axios.get(`${API}/batch-jobs/${jobId}/download`, {
        withCredentials: true,
        responseType: 'blob',
      });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `page-export-${jobId.slice(0, 8)}.zip`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Download failed:', err);
    }
  };

  return (
    <div className="p-8 max-w-[1400px] mx-auto" data-testid="bulk-queue">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-['Outfit'] font-light text-white tracking-tight">
            Bulk Queue
          </h1>
          <p className="text-sm text-zinc-500 mt-1">
            {selected.size > 0 ? (
              <span className="text-white">{selected.size} selected</span>
            ) : (
              `${pages.length} pages`
            )}
            {selected.size > 0 && (
              <button
                onClick={() => setSelected(new Set())}
                className="ml-3 text-zinc-500 hover:text-white text-xs underline"
                data-testid="clear-selection"
              >
                Clear
              </button>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="text"
            placeholder="Search pages..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="bg-zinc-900 border border-zinc-800 px-3 py-1.5 text-sm text-white placeholder-zinc-600 focus:border-zinc-600 focus:outline-none w-48"
            data-testid="queue-search"
          />
          <button
            onClick={() => { fetchPages(); fetchRecentJobs(); }}
            className="p-2 border border-zinc-800 text-zinc-500 hover:text-white transition-colors"
            data-testid="refresh-queue"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Action Toolbar */}
      <div className="flex items-center gap-2 mb-6 flex-wrap" data-testid="action-toolbar">
        {ACTIONS.map((action, idx) => (
          <button
            key={idx}
            onClick={() => selected.size > 0 && setConfirmAction(action)}
            disabled={selected.size === 0}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs border transition-colors ${
              selected.size > 0
                ? 'border-zinc-700 text-zinc-300 hover:text-white hover:border-zinc-500'
                : 'border-zinc-800 text-zinc-600 cursor-not-allowed'
            }`}
            data-testid={`action-${action.label.toLowerCase().replace(' ', '-')}`}
          >
            <action.icon className="w-3 h-3" />
            {action.label}
          </button>
        ))}
      </div>

      {/* Status-Grouped Page List */}
      {loading ? (
        <div className="text-center py-12 text-zinc-500 text-sm animate-pulse">Loading pages...</div>
      ) : (
        <div className="space-y-3">
          {STATUS_ORDER.map(status => {
            const group = grouped[status] || [];
            if (group.length === 0) return null;
            const collapsed = collapsedGroups.has(status);
            const badge = STATUS_BADGES[status] || STATUS_BADGES.Planned;
            const groupIds = group.map(p => p.id);
            const allSelected = groupIds.length > 0 && groupIds.every(id => selected.has(id));
            const someSelected = groupIds.some(id => selected.has(id));

            return (
              <div key={status} className="border border-zinc-800" data-testid={`group-${status.toLowerCase().replace(/\s+/g, '-')}`}>
                <div className="flex items-center gap-3 px-4 py-3 hover:bg-zinc-900/50 transition-colors">
                  <button
                    onClick={() => toggleGroupSelect(status)}
                    className="text-zinc-500 hover:text-white transition-colors"
                    data-testid={`select-all-${status.toLowerCase().replace(/\s+/g, '-')}`}
                  >
                    {allSelected ? (
                      <CheckSquare className="w-4 h-4 text-white" />
                    ) : someSelected ? (
                      <Minus className="w-4 h-4 text-zinc-400" />
                    ) : (
                      <Square className="w-4 h-4" />
                    )}
                  </button>
                  <button
                    onClick={() => toggleCollapse(status)}
                    className="flex items-center gap-2 flex-1 text-left"
                  >
                    {collapsed ? <ChevronRight className="w-4 h-4 text-zinc-500" /> : <ChevronDown className="w-4 h-4 text-zinc-500" />}
                    <span className={`text-xs px-2 py-0.5 ${badge.bg} ${badge.color}`}>{status}</span>
                    <span className="text-xs text-zinc-500">{group.length}</span>
                  </button>
                </div>
                {!collapsed && (
                  <div className="divide-y divide-zinc-800/50">
                    {group.map(page => (
                      <div
                        key={page.id}
                        className={`flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
                          selected.has(page.id) ? 'bg-zinc-800/30' : 'hover:bg-zinc-900/30'
                        }`}
                        data-testid={`page-row-${page.id}`}
                      >
                        <button
                          onClick={() => toggleSelect(page.id)}
                          className="text-zinc-500 hover:text-white transition-colors shrink-0"
                        >
                          {selected.has(page.id) ? (
                            <CheckSquare className="w-4 h-4 text-white" />
                          ) : (
                            <Square className="w-4 h-4" />
                          )}
                        </button>
                        <div className="flex-1 min-w-0">
                          <Link
                            to={`/workspace/${page.id}`}
                            className="text-zinc-300 hover:text-white transition-colors truncate block"
                          >
                            {page.page_name}
                          </Link>
                        </div>
                        <span className="text-xs text-zinc-600 shrink-0">{page.page_family}</span>
                        {page.quality_score && (
                          <span className="text-xs text-zinc-500 font-mono shrink-0">{page.quality_score}</span>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Active Job Progress */}
      {activeJob && (
        <JobProgress
          job={activeJob}
          items={jobItems}
          onCancel={handleCancel}
          onRetryFailed={handleRetryFailed}
          onDownload={handleDownload}
          onDismiss={() => setActiveJob(null)}
        />
      )}

      {/* Recent Jobs */}
      {recentJobs.length > 0 && !activeJob && (
        <div className="mt-8 border border-zinc-800 p-4" data-testid="recent-jobs">
          <h3 className="text-xs text-zinc-500 uppercase tracking-wider mb-3">Recent Batch Jobs</h3>
          <div className="space-y-2">
            {recentJobs.map(job => (
              <div key={job.id} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-3">
                  <span className="text-zinc-400 capitalize">{job.type.replace('_', ' ')}</span>
                  <span className={
                    job.state === 'completed' ? 'text-emerald-400' :
                    job.state === 'failed' ? 'text-red-400' :
                    job.state === 'canceled' ? 'text-zinc-500' : 'text-amber-400'
                  }>{job.state}</span>
                  <span className="text-zinc-600">{job.completed_items}/{job.total_items}</span>
                </div>
                <div className="flex items-center gap-2">
                  {job.type === 'export' && job.state === 'completed' && (
                    <button
                      onClick={() => handleDownload(job.id)}
                      className="text-zinc-500 hover:text-white transition-colors"
                    >
                      <Download className="w-3 h-3" />
                    </button>
                  )}
                  {job.failed_items > 0 && (
                    <button
                      onClick={() => setActiveJob(job)}
                      className="text-zinc-500 hover:text-white transition-colors"
                    >
                      View
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Confirmation Modal */}
      {confirmAction && (
        <ConfirmModal
          action={confirmAction}
          count={selected.size}
          onConfirm={() => handleAction(confirmAction)}
          onCancel={() => setConfirmAction(null)}
        />
      )}
    </div>
  );
}

function ConfirmModal({ action, count, onConfirm, onCancel }) {
  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4" onClick={onCancel}>
      <div className="bg-[#0C0C0E] border border-zinc-800 w-full max-w-sm p-6" onClick={e => e.stopPropagation()} data-testid="confirm-modal">
        <div className="flex items-center gap-3 mb-4">
          <action.icon className="w-5 h-5 text-white" />
          <h3 className="text-lg font-['Outfit'] text-white">{action.label}</h3>
        </div>
        <p className="text-sm text-zinc-400 mb-2">{action.desc}</p>
        <p className="text-sm text-zinc-300 mb-1">{count} page{count !== 1 ? 's' : ''} selected</p>
        <p className="text-xs text-zinc-600 mb-6">Runs sequentially to avoid rate limits.</p>
        <div className="flex justify-end gap-3">
          <button onClick={onCancel} className="px-4 py-2 text-sm text-zinc-400 hover:text-white transition-colors">Cancel</button>
          <button
            onClick={onConfirm}
            className="px-4 py-2 bg-white text-black text-sm font-medium hover:bg-zinc-200 transition-colors"
            data-testid="confirm-batch-btn"
          >
            Run {action.label}
          </button>
        </div>
      </div>
    </div>
  );
}

function JobProgress({ job, items, onCancel, onRetryFailed, onDownload, onDismiss }) {
  const isRunning = ['queued', 'running'].includes(job.state);
  const pct = job.total_items > 0 ? Math.round((job.completed_items / job.total_items) * 100) : 0;
  const failedItems = items.filter(i => i.state === 'failed');

  return (
    <div className="fixed bottom-6 right-6 w-[400px] border border-zinc-700 bg-[#0C0C0E] shadow-2xl z-40" data-testid="job-progress">
      <div className="p-4 border-b border-zinc-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {isRunning ? (
            <RefreshCw className="w-4 h-4 text-amber-400 animate-spin" />
          ) : job.state === 'completed' ? (
            <CheckCircle className="w-4 h-4 text-emerald-400" />
          ) : job.state === 'canceled' ? (
            <XCircle className="w-4 h-4 text-zinc-500" />
          ) : (
            <AlertTriangle className="w-4 h-4 text-red-400" />
          )}
          <span className="text-sm text-white capitalize">{job.type.replace('_', ' ')}</span>
          <span className="text-xs text-zinc-500">{job.state}</span>
        </div>
        <button onClick={onDismiss} className="text-zinc-500 hover:text-white text-xs">Dismiss</button>
      </div>

      <div className="p-4">
        {/* Progress bar */}
        <div className="flex items-center justify-between text-xs text-zinc-400 mb-2">
          <span>{job.completed_items + job.failed_items + job.skipped_items} / {job.total_items}</span>
          <span>{pct}%</span>
        </div>
        <div className="w-full h-1.5 bg-zinc-800 mb-4 overflow-hidden">
          <div
            className={`h-full transition-all duration-300 ${job.failed_items > 0 ? 'bg-amber-500' : 'bg-emerald-500'}`}
            style={{ width: `${pct}%` }}
          />
        </div>

        {/* Stats */}
        <div className="flex gap-4 text-xs mb-4">
          <span className="text-emerald-400">{job.completed_items} done</span>
          {job.failed_items > 0 && <span className="text-red-400">{job.failed_items} failed</span>}
          {job.skipped_items > 0 && <span className="text-zinc-500">{job.skipped_items} skipped</span>}
        </div>

        {/* Failed items list */}
        {failedItems.length > 0 && (
          <div className="max-h-32 overflow-y-auto border border-zinc-800 mb-4 divide-y divide-zinc-800">
            {failedItems.map(item => (
              <div key={item.id} className="px-3 py-2 text-xs">
                <span className="text-zinc-300">{item.page_name}</span>
                <span className="text-red-400 ml-2">{item.message?.slice(0, 60)}</span>
              </div>
            ))}
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-2">
          {isRunning && (
            <button onClick={onCancel} className="px-3 py-1.5 text-xs border border-zinc-700 text-zinc-400 hover:text-white transition-colors" data-testid="cancel-batch-btn">
              Cancel
            </button>
          )}
          {!isRunning && job.failed_items > 0 && (
            <button onClick={onRetryFailed} className="px-3 py-1.5 text-xs border border-zinc-700 text-zinc-400 hover:text-white transition-colors" data-testid="retry-failed-btn">
              Retry Failed
            </button>
          )}
          {job.type === 'export' && job.state === 'completed' && (
            <button
              onClick={() => onDownload(job.id)}
              className="px-3 py-1.5 text-xs bg-white text-black font-medium hover:bg-zinc-200 transition-colors"
              data-testid="download-export-btn"
            >
              Download ZIP
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
