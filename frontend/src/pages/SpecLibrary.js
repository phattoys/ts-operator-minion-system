import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import axios from 'axios';
import {
  FileText, Plus, Search, Filter, Zap,
  CheckCircle, AlertCircle, Clock, Archive, Send, ChevronRight,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const SPEC_TYPES = [
  'Software Feature', 'Standalone App', 'Plugin / Extension',
  'GPT / AI Agent', 'Automation / Workflow', 'Internal Tool',
];

const STATUS_COLORS = {
  Draft: 'text-zinc-400 bg-zinc-800',
  Scored: 'text-amber-400 bg-amber-900/30',
  'Needs Refinement': 'text-orange-400 bg-orange-900/30',
  Ready: 'text-emerald-400 bg-emerald-900/30',
  'Handed Off': 'text-blue-400 bg-blue-900/30',
  Archived: 'text-zinc-500 bg-zinc-800/50',
};

const STATUS_ICONS = {
  Draft: Clock,
  Scored: Zap,
  'Needs Refinement': AlertCircle,
  Ready: CheckCircle,
  'Handed Off': Send,
  Archived: Archive,
};

const PRIORITY_COLORS = {
  P0: 'text-red-400 border-red-500/30',
  P1: 'text-amber-400 border-amber-500/30',
  P2: 'text-zinc-400 border-zinc-600',
};

export default function SpecLibrary() {
  const [specs, setSpecs] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filterType, setFilterType] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [showNewForm, setShowNewForm] = useState(false);
  const navigate = useNavigate();

  const fetchData = async () => {
    try {
      const params = {};
      if (filterType) params.spec_type = filterType;
      if (filterStatus) params.status = filterStatus;
      const [specsRes, statsRes] = await Promise.all([
        axios.get(`${API}/specs`, { params, withCredentials: true }),
        axios.get(`${API}/specs/stats`, { withCredentials: true }),
      ]);
      setSpecs(specsRes.data.specs || []);
      setStats(statsRes.data);
    } catch (err) {
      console.error('Failed to fetch specs:', err);
    }
    setLoading(false);
  };

  useEffect(() => { fetchData(); }, [filterType, filterStatus]);

  const filtered = specs.filter(s =>
    !searchQuery || s.title?.toLowerCase().includes(searchQuery.toLowerCase())
    || s.raw_idea?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="p-8 max-w-[1400px] mx-auto" data-testid="spec-library">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-['Outfit'] font-light text-white tracking-tight">
            Spec Library
          </h1>
          <p className="text-sm text-zinc-500 mt-1">Spec Writer Minion</p>
        </div>
        <button
          onClick={() => setShowNewForm(true)}
          className="flex items-center gap-2 px-4 py-2 bg-white text-black text-sm font-medium hover:bg-zinc-200 transition-colors"
          data-testid="new-spec-btn"
        >
          <Plus className="w-4 h-4" />
          New Spec
        </button>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-4 gap-4 mb-8">
          <div className="border border-zinc-800 p-4">
            <div className="text-2xl font-['Outfit'] text-white">{stats.total}</div>
            <div className="text-xs text-zinc-500 uppercase tracking-wider mt-1">Total Specs</div>
          </div>
          <div className="border border-zinc-800 p-4">
            <div className="text-2xl font-['Outfit'] text-emerald-400">{stats.ready_count}</div>
            <div className="text-xs text-zinc-500 uppercase tracking-wider mt-1">Ready</div>
          </div>
          <div className="border border-zinc-800 p-4">
            <div className="text-2xl font-['Outfit'] text-orange-400">{stats.needs_refinement_count}</div>
            <div className="text-xs text-zinc-500 uppercase tracking-wider mt-1">Needs Refinement</div>
          </div>
          <div className="border border-zinc-800 p-4">
            <div className="text-2xl font-['Outfit'] text-white">
              {stats.avg_completeness_score ?? '—'}
            </div>
            <div className="text-xs text-zinc-500 uppercase tracking-wider mt-1">Avg Score</div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-3 mb-6">
        <div className="relative flex-1">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
          <input
            type="text"
            placeholder="Search specs..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="w-full bg-zinc-900 border border-zinc-800 pl-10 pr-4 py-2 text-sm text-white placeholder-zinc-600 focus:border-zinc-600 focus:outline-none"
            data-testid="spec-search"
          />
        </div>
        <select
          value={filterType}
          onChange={e => setFilterType(e.target.value)}
          className="bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-white focus:border-zinc-600 focus:outline-none"
          data-testid="spec-filter-type"
        >
          <option value="">All Types</option>
          {SPEC_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <select
          value={filterStatus}
          onChange={e => setFilterStatus(e.target.value)}
          className="bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-white focus:border-zinc-600 focus:outline-none"
          data-testid="spec-filter-status"
        >
          <option value="">All Statuses</option>
          <option value="Draft">Draft</option>
          <option value="Scored">Scored</option>
          <option value="Needs Refinement">Needs Refinement</option>
          <option value="Ready">Ready</option>
          <option value="Handed Off">Handed Off</option>
          <option value="Archived">Archived</option>
        </select>
      </div>

      {/* Spec List */}
      {loading ? (
        <div className="text-center py-12 text-zinc-500 text-sm animate-pulse">Loading specs...</div>
      ) : filtered.length === 0 ? (
        <div className="border border-zinc-800 p-12 text-center">
          <FileText className="w-8 h-8 text-zinc-600 mx-auto mb-3" />
          <p className="text-zinc-500 text-sm">
            {specs.length === 0 ? 'No specs yet. Create your first one.' : 'No specs match your filters.'}
          </p>
        </div>
      ) : (
        <div className="border border-zinc-800 divide-y divide-zinc-800">
          {filtered.map((spec, idx) => {
            const StatusIcon = STATUS_ICONS[spec.status] || Clock;
            return (
              <Link
                key={spec.id}
                to={`/specs/${spec.id}`}
                className="flex items-center justify-between p-4 hover:bg-zinc-900/60 transition-colors group"
                data-testid={`spec-item-${idx}`}
              >
                <div className="flex items-center gap-4 flex-1 min-w-0">
                  <span className={`text-xs px-2 py-0.5 border ${PRIORITY_COLORS[spec.priority] || PRIORITY_COLORS.P1}`}>
                    {spec.priority}
                  </span>
                  <div className="min-w-0">
                    <div className="text-sm text-white font-medium truncate">{spec.title}</div>
                    <div className="text-xs text-zinc-500 truncate mt-0.5">
                      {spec.spec_type} &middot; {spec.raw_idea?.slice(0, 80)}{spec.raw_idea?.length > 80 ? '...' : ''}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-4 ml-4 shrink-0">
                  {spec.completeness_score && (
                    <span className="text-xs text-zinc-400 font-mono">{spec.completeness_score}/100</span>
                  )}
                  <span className={`text-xs px-2 py-1 flex items-center gap-1.5 ${STATUS_COLORS[spec.status] || STATUS_COLORS.Draft}`}>
                    <StatusIcon className="w-3 h-3" />
                    {spec.status}
                  </span>
                  <ChevronRight className="w-4 h-4 text-zinc-600 group-hover:text-zinc-400 transition-colors" />
                </div>
              </Link>
            );
          })}
        </div>
      )}

      {/* New Spec Modal */}
      {showNewForm && (
        <NewSpecModal
          onClose={() => setShowNewForm(false)}
          onCreated={(spec) => {
            setShowNewForm(false);
            navigate(`/specs/${spec.id}`);
          }}
        />
      )}
    </div>
  );
}

function NewSpecModal({ onClose, onCreated }) {
  const [title, setTitle] = useState('');
  const [specType, setSpecType] = useState('Software Feature');
  const [rawIdea, setRawIdea] = useState('');
  const [audience, setAudience] = useState('');
  const [priority, setPriority] = useState('P1');
  const [constraints, setConstraints] = useState('');
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!title.trim() || !rawIdea.trim()) return;
    setSaving(true);
    try {
      const res = await axios.post(`${API}/specs`, {
        title: title.trim(),
        spec_type: specType,
        raw_idea: rawIdea.trim(),
        target_audience: audience.trim() || null,
        priority,
        constraints: constraints.trim() || null,
      }, { withCredentials: true });
      onCreated(res.data);
    } catch (err) {
      console.error('Failed to create spec:', err);
    }
    setSaving(false);
  };

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-[#0C0C0E] border border-zinc-800 w-full max-w-xl" onClick={e => e.stopPropagation()}>
        <div className="p-6 border-b border-zinc-800">
          <h2 className="text-lg font-['Outfit'] text-white">New Spec</h2>
        </div>
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-xs text-zinc-500 uppercase tracking-wider mb-1">Title *</label>
            <input
              value={title}
              onChange={e => setTitle(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-white focus:border-zinc-600 focus:outline-none"
              placeholder="e.g. Product Intake Minion"
              data-testid="new-spec-title"
              required
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-zinc-500 uppercase tracking-wider mb-1">Spec Type *</label>
              <select
                value={specType}
                onChange={e => setSpecType(e.target.value)}
                className="w-full bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-white focus:border-zinc-600 focus:outline-none"
                data-testid="new-spec-type"
              >
                {SPEC_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-zinc-500 uppercase tracking-wider mb-1">Priority</label>
              <select
                value={priority}
                onChange={e => setPriority(e.target.value)}
                className="w-full bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-white focus:border-zinc-600 focus:outline-none"
                data-testid="new-spec-priority"
              >
                <option value="P0">P0 (Now)</option>
                <option value="P1">P1 (Soon)</option>
                <option value="P2">P2 (Backlog)</option>
              </select>
            </div>
          </div>
          <div>
            <label className="block text-xs text-zinc-500 uppercase tracking-wider mb-1">Raw Idea *</label>
            <textarea
              value={rawIdea}
              onChange={e => setRawIdea(e.target.value)}
              rows={4}
              className="w-full bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-white placeholder-zinc-600 focus:border-zinc-600 focus:outline-none resize-none"
              placeholder="Describe your idea in plain language..."
              data-testid="new-spec-idea"
              required
            />
          </div>
          <div>
            <label className="block text-xs text-zinc-500 uppercase tracking-wider mb-1">Target Audience</label>
            <input
              value={audience}
              onChange={e => setAudience(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-white placeholder-zinc-600 focus:border-zinc-600 focus:outline-none"
              placeholder="Who uses this?"
              data-testid="new-spec-audience"
            />
          </div>
          <div>
            <label className="block text-xs text-zinc-500 uppercase tracking-wider mb-1">Constraints</label>
            <input
              value={constraints}
              onChange={e => setConstraints(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-white placeholder-zinc-600 focus:border-zinc-600 focus:outline-none"
              placeholder="Budget, platform, timeline limits..."
              data-testid="new-spec-constraints"
            />
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-zinc-400 hover:text-white transition-colors">Cancel</button>
            <button
              type="submit"
              disabled={saving || !title.trim() || !rawIdea.trim()}
              className="px-4 py-2 bg-white text-black text-sm font-medium hover:bg-zinc-200 transition-colors disabled:opacity-40"
              data-testid="create-spec-submit"
            >
              {saving ? 'Creating...' : 'Create Spec'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
