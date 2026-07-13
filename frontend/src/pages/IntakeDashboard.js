import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import axios from 'axios';
import {
  Package, Plus, Search, AlertTriangle,
  CheckCircle, Clock, Eye, ChevronRight, ShoppingCart,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const SOURCE_PRESETS = ['Temu', 'SHEIN', 'AliExpress', 'Amazon', 'Other'];

const STATUS_PILL = {
  needs_info: 'text-orange-400 bg-orange-900/30',
  in_review: 'text-amber-400 bg-amber-900/30',
  ready: 'text-emerald-400 bg-emerald-900/30',
};

export default function IntakeDashboard() {
  const [sessions, setSessions] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showNewForm, setShowNewForm] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const navigate = useNavigate();

  const fetchData = async () => {
    try {
      const [sessRes, statsRes] = await Promise.all([
        axios.get(`${API}/intake/sessions`, { withCredentials: true }),
        axios.get(`${API}/intake/stats`, { withCredentials: true }),
      ]);
      setSessions(sessRes.data.sessions || []);
      setStats(statsRes.data);
    } catch (err) {
      console.error('Failed to fetch intake data:', err);
    }
    setLoading(false);
  };

  useEffect(() => { fetchData(); }, []);

  const filtered = sessions.filter(s =>
    !searchQuery ||
    s.source_store?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    s.order_id?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="p-8 max-w-[1400px] mx-auto" data-testid="intake-dashboard">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-['Outfit'] font-light text-white tracking-tight">
            Product Intake
          </h1>
          <p className="text-sm text-zinc-500 mt-1">Product Intake Minion</p>
        </div>
        <button
          onClick={() => setShowNewForm(true)}
          className="flex items-center gap-2 px-4 py-2 bg-white text-black text-sm font-medium hover:bg-zinc-200 transition-colors"
          data-testid="new-session-btn"
        >
          <Plus className="w-4 h-4" />
          New Intake Session
        </button>
      </div>

      {stats && (
        <div className="grid grid-cols-5 gap-4 mb-8" data-testid="intake-stats">
          <div className="border border-zinc-800 p-4">
            <div className="text-2xl font-['Outfit'] text-white">{stats.total_sessions}</div>
            <div className="text-xs text-zinc-500 uppercase tracking-wider mt-1">Sessions</div>
          </div>
          <div className="border border-zinc-800 p-4">
            <div className="text-2xl font-['Outfit'] text-white">{stats.total_items}</div>
            <div className="text-xs text-zinc-500 uppercase tracking-wider mt-1">Total Items</div>
          </div>
          <div className="border border-zinc-800 p-4">
            <div className="text-2xl font-['Outfit'] text-emerald-400">{stats.ready_count}</div>
            <div className="text-xs text-zinc-500 uppercase tracking-wider mt-1">Ready</div>
          </div>
          <div className="border border-zinc-800 p-4">
            <div className="text-2xl font-['Outfit'] text-amber-400">{stats.in_review_count}</div>
            <div className="text-xs text-zinc-500 uppercase tracking-wider mt-1">In Review</div>
          </div>
          <div className="border border-zinc-800 p-4">
            <div className={`text-2xl font-['Outfit'] ${stats.stuck_count > 0 ? 'text-red-400' : 'text-zinc-400'}`}>
              {stats.stuck_count}
            </div>
            <div className="text-xs text-zinc-500 uppercase tracking-wider mt-1 flex items-center gap-1">
              {stats.stuck_count > 0 && <AlertTriangle className="w-3 h-3 text-red-400" />}
              Stuck ({stats.stuck_days_threshold}d+)
            </div>
          </div>
        </div>
      )}

      <div className="flex items-center gap-3 mb-6">
        <div className="relative flex-1">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
          <input
            type="text"
            placeholder="Search sessions by store or order ID..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="w-full bg-zinc-900 border border-zinc-800 pl-10 pr-4 py-2 text-sm text-white placeholder-zinc-600 focus:border-zinc-600 focus:outline-none"
            data-testid="intake-search"
          />
        </div>
      </div>

      {loading ? (
        <div className="text-center py-12 text-zinc-500 text-sm animate-pulse">Loading sessions...</div>
      ) : filtered.length === 0 ? (
        <div className="border border-zinc-800 p-12 text-center" data-testid="intake-empty">
          <ShoppingCart className="w-8 h-8 text-zinc-600 mx-auto mb-3" />
          <p className="text-zinc-500 text-sm">
            {sessions.length === 0
              ? 'No intake sessions yet. Create one to start processing purchases.'
              : 'No sessions match your search.'}
          </p>
        </div>
      ) : (
        <div className="border border-zinc-800 divide-y divide-zinc-800" data-testid="session-list">
          {filtered.map((s, idx) => (
            <Link
              key={s.id}
              to={`/intake/${s.id}`}
              className="flex items-center justify-between p-4 hover:bg-zinc-900/60 transition-colors group"
              data-testid={`session-item-${idx}`}
            >
              <div className="flex items-center gap-4 flex-1 min-w-0">
                <div className="w-9 h-9 border border-zinc-700 flex items-center justify-center shrink-0">
                  <Package className="w-4 h-4 text-zinc-400" />
                </div>
                <div className="min-w-0">
                  <div className="text-sm text-white font-medium truncate">
                    {s.source_store}
                    {s.order_id && <span className="text-zinc-500 ml-2">#{s.order_id}</span>}
                  </div>
                  <div className="text-xs text-zinc-500 mt-0.5">
                    {s.item_count} items
                    {s.purchase_date && <span> &middot; {s.purchase_date}</span>}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-3 ml-4 shrink-0">
                {s.needs_info_count > 0 && (
                  <span className={`text-xs px-1.5 py-0.5 ${STATUS_PILL.needs_info}`}>
                    {s.needs_info_count} need info
                  </span>
                )}
                {s.in_review_count > 0 && (
                  <span className={`text-xs px-1.5 py-0.5 ${STATUS_PILL.in_review}`}>
                    {s.in_review_count} review
                  </span>
                )}
                {s.ready_count > 0 && (
                  <span className={`text-xs px-1.5 py-0.5 ${STATUS_PILL.ready}`}>
                    {s.ready_count} ready
                  </span>
                )}
                <ChevronRight className="w-4 h-4 text-zinc-600 group-hover:text-zinc-400 transition-colors" />
              </div>
            </Link>
          ))}
        </div>
      )}

      {showNewForm && (
        <NewSessionModal
          onClose={() => setShowNewForm(false)}
          onCreated={(s) => { setShowNewForm(false); navigate(`/intake/${s.id}`); }}
        />
      )}
    </div>
  );
}

function NewSessionModal({ onClose, onCreated }) {
  const [store, setStore] = useState('');
  const [customStore, setCustomStore] = useState('');
  const [orderId, setOrderId] = useState('');
  const [purchaseDate, setPurchaseDate] = useState('');
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);

  const effectiveStore = store === 'Other' ? customStore : store;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!effectiveStore.trim()) return;
    setSaving(true);
    try {
      const res = await axios.post(`${API}/intake/sessions`, {
        source_store: effectiveStore.trim(),
        order_id: orderId.trim() || null,
        purchase_date: purchaseDate || null,
        notes: notes.trim() || null,
      }, { withCredentials: true });
      onCreated(res.data);
    } catch (err) {
      console.error('Failed to create session:', err);
    }
    setSaving(false);
  };

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-[#0C0C0E] border border-zinc-800 w-full max-w-md" onClick={e => e.stopPropagation()}>
        <div className="p-6 border-b border-zinc-800">
          <h2 className="text-lg font-['Outfit'] text-white">New Intake Session</h2>
          <p className="text-xs text-zinc-500 mt-1">Create a session for a purchase batch</p>
        </div>
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-xs text-zinc-500 uppercase tracking-wider mb-1">Source Store *</label>
            <div className="flex flex-wrap gap-2 mb-2">
              {SOURCE_PRESETS.map(p => (
                <button
                  key={p}
                  type="button"
                  onClick={() => setStore(p)}
                  className={`px-3 py-1 text-xs border transition-colors ${
                    store === p
                      ? 'border-white text-white bg-zinc-800'
                      : 'border-zinc-700 text-zinc-400 hover:border-zinc-500'
                  }`}
                  data-testid={`store-preset-${p.toLowerCase()}`}
                >
                  {p}
                </button>
              ))}
            </div>
            {store === 'Other' && (
              <input
                value={customStore}
                onChange={e => setCustomStore(e.target.value)}
                className="w-full bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-white focus:border-zinc-600 focus:outline-none"
                placeholder="Store name..."
                data-testid="custom-store-input"
                autoFocus
              />
            )}
          </div>
          <div>
            <label className="block text-xs text-zinc-500 uppercase tracking-wider mb-1">Order ID</label>
            <input
              value={orderId}
              onChange={e => setOrderId(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-white placeholder-zinc-600 focus:border-zinc-600 focus:outline-none"
              placeholder="e.g. ORD-12345"
              data-testid="session-order-id"
            />
          </div>
          <div>
            <label className="block text-xs text-zinc-500 uppercase tracking-wider mb-1">Purchase Date</label>
            <input
              type="date"
              value={purchaseDate}
              onChange={e => setPurchaseDate(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-white focus:border-zinc-600 focus:outline-none"
              data-testid="session-date"
            />
          </div>
          <div>
            <label className="block text-xs text-zinc-500 uppercase tracking-wider mb-1">Notes</label>
            <textarea
              value={notes}
              onChange={e => setNotes(e.target.value)}
              rows={2}
              className="w-full bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-white placeholder-zinc-600 focus:border-zinc-600 focus:outline-none resize-none"
              placeholder="Optional notes about this order..."
              data-testid="session-notes"
            />
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-zinc-400 hover:text-white transition-colors">Cancel</button>
            <button
              type="submit"
              disabled={saving || !effectiveStore.trim()}
              className="px-4 py-2 bg-white text-black text-sm font-medium hover:bg-zinc-200 transition-colors disabled:opacity-40"
              data-testid="create-session-submit"
            >
              {saving ? 'Creating...' : 'Create Session'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
