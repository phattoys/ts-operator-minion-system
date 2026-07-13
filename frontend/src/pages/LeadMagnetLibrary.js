import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import axios from 'axios';
import {
  Magnet, Plus, Search, Download, FileText,
  CheckCircle, Clock, Archive, Send, ChevronRight, BarChart3,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const FORMATS = ['Guide', 'Checklist', 'Resource List', 'FAQ', 'Quiz'];
const LENGTHS = ['Short (1-2 pages)', 'Standard (3-5 pages)', 'Deep (6-10 pages)'];

const STATUS_COLORS = {
  Draft: 'text-zinc-400 bg-zinc-800',
  Ready: 'text-amber-400 bg-amber-900/30',
  Published: 'text-emerald-400 bg-emerald-900/30',
  Archived: 'text-zinc-500 bg-zinc-800/50',
};

const STATUS_ICONS = {
  Draft: Clock,
  Ready: Send,
  Published: CheckCircle,
  Archived: Archive,
};

export default function LeadMagnetLibrary() {
  const [magnets, setMagnets] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState('');
  const [filterFormat, setFilterFormat] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [showNewForm, setShowNewForm] = useState(false);
  const navigate = useNavigate();

  const fetchData = async () => {
    try {
      const params = {};
      if (filterStatus) params.status = filterStatus;
      if (filterFormat) params.format_type = filterFormat;
      const [listRes, statsRes] = await Promise.all([
        axios.get(`${API}/lead-magnets`, { params, withCredentials: true }),
        axios.get(`${API}/lead-magnets/stats`, { withCredentials: true }),
      ]);
      setMagnets(listRes.data.lead_magnets || []);
      setStats(statsRes.data);
    } catch (err) {
      console.error('Failed to fetch lead magnets:', err);
    }
    setLoading(false);
  };

  useEffect(() => { fetchData(); }, [filterStatus, filterFormat]);

  const filtered = magnets.filter(m =>
    !searchQuery ||
    m.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    m.topic?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="p-8 max-w-[1400px] mx-auto" data-testid="lead-magnet-library">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-['Outfit'] font-light text-white tracking-tight">
            Lead Magnets
          </h1>
          <p className="text-sm text-zinc-500 mt-1">Lead Magnet Minion</p>
        </div>
        <button
          onClick={() => setShowNewForm(true)}
          className="flex items-center gap-2 px-4 py-2 bg-white text-black text-sm font-medium hover:bg-zinc-200 transition-colors"
          data-testid="new-lead-magnet-btn"
        >
          <Plus className="w-4 h-4" />
          New Lead Magnet
        </button>
      </div>

      {stats && (
        <div className="grid grid-cols-4 gap-4 mb-8" data-testid="lead-magnet-stats">
          <div className="border border-zinc-800 p-4">
            <div className="text-2xl font-['Outfit'] text-white">{stats.total}</div>
            <div className="text-xs text-zinc-500 uppercase tracking-wider mt-1">Total</div>
          </div>
          <div className="border border-zinc-800 p-4">
            <div className="text-2xl font-['Outfit'] text-emerald-400">{stats.published_count}</div>
            <div className="text-xs text-zinc-500 uppercase tracking-wider mt-1">Published</div>
          </div>
          <div className="border border-zinc-800 p-4">
            <div className="text-2xl font-['Outfit'] text-zinc-400">{stats.draft_count}</div>
            <div className="text-xs text-zinc-500 uppercase tracking-wider mt-1">Drafts</div>
          </div>
          <div className="border border-zinc-800 p-4">
            <div className="flex items-center gap-2">
              <Download className="w-4 h-4 text-zinc-500" />
              <div className="text-2xl font-['Outfit'] text-white">{stats.total_downloads}</div>
            </div>
            <div className="text-xs text-zinc-500 uppercase tracking-wider mt-1">Downloads</div>
          </div>
        </div>
      )}

      <div className="flex items-center gap-3 mb-6" data-testid="lead-magnet-filters">
        <div className="relative flex-1">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
          <input
            type="text"
            placeholder="Search lead magnets..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="w-full bg-zinc-900 border border-zinc-800 pl-10 pr-4 py-2 text-sm text-white placeholder-zinc-600 focus:border-zinc-600 focus:outline-none"
            data-testid="lead-magnet-search"
          />
        </div>
        <select
          value={filterFormat}
          onChange={e => setFilterFormat(e.target.value)}
          className="bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-white focus:border-zinc-600 focus:outline-none"
          data-testid="lead-magnet-filter-format"
        >
          <option value="">All Formats</option>
          {FORMATS.map(f => <option key={f} value={f}>{f}</option>)}
        </select>
        <select
          value={filterStatus}
          onChange={e => setFilterStatus(e.target.value)}
          className="bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-white focus:border-zinc-600 focus:outline-none"
          data-testid="lead-magnet-filter-status"
        >
          <option value="">All Statuses</option>
          <option value="Draft">Draft</option>
          <option value="Ready">Ready</option>
          <option value="Published">Published</option>
          <option value="Archived">Archived</option>
        </select>
      </div>

      {loading ? (
        <div className="text-center py-12 text-zinc-500 text-sm animate-pulse">Loading lead magnets...</div>
      ) : filtered.length === 0 ? (
        <div className="border border-zinc-800 p-12 text-center" data-testid="lead-magnet-empty">
          <Magnet className="w-8 h-8 text-zinc-600 mx-auto mb-3" />
          <p className="text-zinc-500 text-sm">
            {magnets.length === 0
              ? 'No lead magnets yet. Create your first one to start growing your list.'
              : 'No lead magnets match your filters.'}
          </p>
        </div>
      ) : (
        <div className="border border-zinc-800 divide-y divide-zinc-800" data-testid="lead-magnet-list">
          {filtered.map((m, idx) => {
            const StatusIcon = STATUS_ICONS[m.status] || Clock;
            return (
              <Link
                key={m.id}
                to={`/lead-magnets/${m.id}`}
                className="flex items-center justify-between p-4 hover:bg-zinc-900/60 transition-colors group"
                data-testid={`lead-magnet-item-${idx}`}
              >
                <div className="flex items-center gap-4 flex-1 min-w-0">
                  <span className="text-xs px-2 py-0.5 border border-zinc-700 text-zinc-400">
                    {m.format_type}
                  </span>
                  <div className="min-w-0">
                    <div className="text-sm text-white font-medium truncate">
                      {m.title || m.topic}
                    </div>
                    <div className="text-xs text-zinc-500 truncate mt-0.5">
                      {m.district_tag && <span>{m.district_tag} &middot; </span>}
                      {m.target_audience?.slice(0, 60)}{m.target_audience?.length > 60 ? '...' : ''}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-4 ml-4 shrink-0">
                  {m.download_count > 0 && (
                    <span className="text-xs text-zinc-500 flex items-center gap-1">
                      <Download className="w-3 h-3" />
                      {m.download_count}
                    </span>
                  )}
                  <span className={`text-xs px-2 py-1 flex items-center gap-1.5 ${STATUS_COLORS[m.status] || STATUS_COLORS.Draft}`}>
                    <StatusIcon className="w-3 h-3" />
                    {m.status}
                  </span>
                  <ChevronRight className="w-4 h-4 text-zinc-600 group-hover:text-zinc-400 transition-colors" />
                </div>
              </Link>
            );
          })}
        </div>
      )}

      {showNewForm && (
        <NewLeadMagnetModal
          onClose={() => setShowNewForm(false)}
          onCreated={(m) => {
            setShowNewForm(false);
            navigate(`/lead-magnets/${m.id}`);
          }}
        />
      )}
    </div>
  );
}

function NewLeadMagnetModal({ onClose, onCreated }) {
  const [topic, setTopic] = useState('');
  const [audience, setAudience] = useState('');
  const [formatType, setFormatType] = useState('Guide');
  const [district, setDistrict] = useState('');
  const [length, setLength] = useState('Standard (3-5 pages)');
  const [direction, setDirection] = useState('');
  const [disclaimer, setDisclaimer] = useState(true);
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!topic.trim() || !audience.trim()) return;
    setSaving(true);
    try {
      const res = await axios.post(`${API}/lead-magnets`, {
        topic: topic.trim(),
        target_audience: audience.trim(),
        format_type: formatType,
        district_tag: district.trim() || null,
        content_direction: direction.trim() || null,
        length,
        include_disclaimer: disclaimer,
      }, { withCredentials: true });
      onCreated(res.data);
    } catch (err) {
      console.error('Failed to create lead magnet:', err);
    }
    setSaving(false);
  };

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-[#0C0C0E] border border-zinc-800 w-full max-w-xl max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="p-6 border-b border-zinc-800">
          <h2 className="text-lg font-['Outfit'] text-white">New Lead Magnet</h2>
          <p className="text-xs text-zinc-500 mt-1">Define the inputs, then generate content with AI</p>
        </div>
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-xs text-zinc-500 uppercase tracking-wider mb-1">Topic *</label>
            <input
              value={topic}
              onChange={e => setTopic(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-white focus:border-zinc-600 focus:outline-none"
              placeholder="e.g. Beginner's Guide to Self-Care Products"
              data-testid="new-lm-topic"
              required
              maxLength={120}
            />
            <span className="text-[10px] text-zinc-600 mt-0.5 block">{topic.length}/120</span>
          </div>
          <div>
            <label className="block text-xs text-zinc-500 uppercase tracking-wider mb-1">Target Audience *</label>
            <input
              value={audience}
              onChange={e => setAudience(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-white focus:border-zinc-600 focus:outline-none"
              placeholder="e.g. First-time buyers exploring wellness products"
              data-testid="new-lm-audience"
              required
              maxLength={240}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-zinc-500 uppercase tracking-wider mb-1">Format *</label>
              <select
                value={formatType}
                onChange={e => setFormatType(e.target.value)}
                className="w-full bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-white focus:border-zinc-600 focus:outline-none"
                data-testid="new-lm-format"
              >
                {FORMATS.map(f => <option key={f} value={f}>{f}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-zinc-500 uppercase tracking-wider mb-1">Length</label>
              <select
                value={length}
                onChange={e => setLength(e.target.value)}
                className="w-full bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-white focus:border-zinc-600 focus:outline-none"
                data-testid="new-lm-length"
              >
                {LENGTHS.map(l => <option key={l} value={l}>{l}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label className="block text-xs text-zinc-500 uppercase tracking-wider mb-1">District / Page Family</label>
            <input
              value={district}
              onChange={e => setDistrict(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-white placeholder-zinc-600 focus:border-zinc-600 focus:outline-none"
              placeholder="e.g. Education District"
              data-testid="new-lm-district"
            />
          </div>
          <div>
            <label className="block text-xs text-zinc-500 uppercase tracking-wider mb-1">Content Direction / Notes</label>
            <textarea
              value={direction}
              onChange={e => setDirection(e.target.value)}
              rows={3}
              className="w-full bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-white placeholder-zinc-600 focus:border-zinc-600 focus:outline-none resize-none"
              placeholder="Any specific direction, angles to cover, or notes..."
              data-testid="new-lm-direction"
              maxLength={2000}
            />
          </div>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={disclaimer}
              onChange={e => setDisclaimer(e.target.checked)}
              id="disclaimer-toggle"
              className="accent-white"
              data-testid="new-lm-disclaimer"
            />
            <label htmlFor="disclaimer-toggle" className="text-sm text-zinc-400">Include disclaimer block</label>
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-zinc-400 hover:text-white transition-colors">Cancel</button>
            <button
              type="submit"
              disabled={saving || topic.trim().length < 3 || audience.trim().length < 3}
              className="px-4 py-2 bg-white text-black text-sm font-medium hover:bg-zinc-200 transition-colors disabled:opacity-40"
              data-testid="create-lead-magnet-submit"
            >
              {saving ? 'Creating...' : 'Create Lead Magnet'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
