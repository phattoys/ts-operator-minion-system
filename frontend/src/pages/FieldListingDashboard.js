import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Plus, Camera, Package, ChevronRight, Trash2 } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export default function FieldListingDashboard() {
  const navigate = useNavigate();
  const [batches, setBatches] = useState([]);
  const [stats, setStats] = useState({});
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({
    name: '', source_vendor: '', grouped_pricing_note: '',
    grouped_category_note: '', condition_note: '', pickup_shipping_note: '',
    destinations: ['website', 'offerup', 'facebook'],
  });
  const [creating, setCreating] = useState(false);

  const fetchData = async () => {
    try {
      const [batchRes, statsRes] = await Promise.all([
        axios.get(`${API}/field-listing/batches`, { withCredentials: true }),
        axios.get(`${API}/field-listing/stats`, { withCredentials: true }),
      ]);
      setBatches(batchRes.data.batches || []);
      setStats(statsRes.data);
    } catch (err) {
      console.error('Failed to load field listing data:', err);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const handleCreate = async () => {
    if (!form.name.trim()) return;
    setCreating(true);
    try {
      const res = await axios.post(`${API}/field-listing/batches`, form, { withCredentials: true });
      navigate(`/field-listing/${res.data.id}`);
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to create batch');
    }
    setCreating(false);
  };

  const handleDelete = async (id, name) => {
    if (!window.confirm(`Delete batch "${name}" and all items?`)) return;
    try {
      await axios.delete(`${API}/field-listing/batches/${id}`, { withCredentials: true });
      await fetchData();
    } catch (err) {
      alert('Delete failed');
    }
  };

  const toggleDest = (d) => {
    setForm(prev => ({
      ...prev,
      destinations: prev.destinations.includes(d)
        ? prev.destinations.filter(x => x !== d)
        : [...prev.destinations, d],
    }));
  };

  const statusColor = {
    intake: 'text-zinc-400 border-zinc-700',
    processing: 'text-amber-400 border-amber-800',
    review: 'text-blue-400 border-blue-800',
    complete: 'text-emerald-400 border-emerald-800',
  };

  return (
    <div className="p-8 max-w-6xl mx-auto" data-testid="field-listing-dashboard">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Field-to-Listing</h1>
          <p className="text-sm text-zinc-500 mt-1">Upload phone photos + grouped notes → listing-ready records + marketplace packs</p>
        </div>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="flex items-center gap-2 px-4 py-2 bg-white text-black text-sm font-medium hover:bg-zinc-200 transition"
          data-testid="new-batch-btn"
        >
          <Plus className="w-4 h-4" /> New Photo Batch
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
        {[
          { label: 'BATCHES', value: stats.total_batches || 0 },
          { label: 'TOTAL ITEMS', value: stats.total_items || 0 },
          { label: 'APPROVED', value: stats.approved_items || 0, color: 'text-emerald-400' },
          { label: 'DRAFTS', value: stats.draft_items || 0, color: 'text-amber-400' },
        ].map(s => (
          <div key={s.label} className="border border-zinc-800 p-4">
            <div className={`text-2xl font-bold ${s.color || 'text-white'}`}>{s.value}</div>
            <div className="text-[10px] text-zinc-600 uppercase tracking-wider mt-1">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Create Form */}
      {showCreate && (
        <div className="mb-8 border border-zinc-800 bg-zinc-900/50 p-6" data-testid="create-batch-form">
          <h2 className="text-sm text-white font-medium mb-4">New Photo Batch</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="text-[10px] text-zinc-500 uppercase tracking-wider">Batch Name *</label>
              <input
                value={form.name}
                onChange={e => setForm(p => ({ ...p, name: e.target.value }))}
                placeholder="e.g., Downtown LA finds, In-store clearance"
                className="w-full mt-1 bg-zinc-900 border border-zinc-700 text-white text-sm px-3 py-2 focus:border-zinc-500 outline-none"
                data-testid="batch-name-input"
              />
            </div>
            <div>
              <label className="text-[10px] text-zinc-500 uppercase tracking-wider">Source / Vendor</label>
              <input
                value={form.source_vendor}
                onChange={e => setForm(p => ({ ...p, source_vendor: e.target.value }))}
                placeholder="e.g., Downtown LA, Temu, Store clearance"
                className="w-full mt-1 bg-zinc-900 border border-zinc-700 text-white text-sm px-3 py-2 focus:border-zinc-500 outline-none"
                data-testid="batch-vendor-input"
              />
            </div>
            <div>
              <label className="text-[10px] text-zinc-500 uppercase tracking-wider">Grouped Pricing Note</label>
              <input
                value={form.grouped_pricing_note}
                onChange={e => setForm(p => ({ ...p, grouped_pricing_note: e.target.value }))}
                placeholder='e.g., "These were $25 each, sell at $55"'
                className="w-full mt-1 bg-zinc-900 border border-zinc-700 text-white text-sm px-3 py-2 focus:border-zinc-500 outline-none"
                data-testid="batch-pricing-input"
              />
            </div>
            <div>
              <label className="text-[10px] text-zinc-500 uppercase tracking-wider">Category / Type Hint</label>
              <input
                value={form.grouped_category_note}
                onChange={e => setForm(p => ({ ...p, grouped_category_note: e.target.value }))}
                placeholder='e.g., "These are panties", "Jewelry"'
                className="w-full mt-1 bg-zinc-900 border border-zinc-700 text-white text-sm px-3 py-2 focus:border-zinc-500 outline-none"
                data-testid="batch-category-input"
              />
            </div>
            <div>
              <label className="text-[10px] text-zinc-500 uppercase tracking-wider">Condition Note</label>
              <input
                value={form.condition_note}
                onChange={e => setForm(p => ({ ...p, condition_note: e.target.value }))}
                placeholder="e.g., New with tags, Like new, Clearance"
                className="w-full mt-1 bg-zinc-900 border border-zinc-700 text-white text-sm px-3 py-2 focus:border-zinc-500 outline-none"
              />
            </div>
            <div>
              <label className="text-[10px] text-zinc-500 uppercase tracking-wider">Pickup / Shipping Note</label>
              <input
                value={form.pickup_shipping_note}
                onChange={e => setForm(p => ({ ...p, pickup_shipping_note: e.target.value }))}
                placeholder="e.g., Local pickup only, Ships nationwide"
                className="w-full mt-1 bg-zinc-900 border border-zinc-700 text-white text-sm px-3 py-2 focus:border-zinc-500 outline-none"
              />
            </div>
          </div>

          <div className="mt-4">
            <label className="text-[10px] text-zinc-500 uppercase tracking-wider">Destinations</label>
            <div className="flex gap-3 mt-2">
              {['website', 'offerup', 'facebook'].map(d => (
                <button
                  key={d}
                  onClick={() => toggleDest(d)}
                  className={`px-3 py-1.5 text-xs border transition ${
                    form.destinations.includes(d)
                      ? 'bg-white text-black border-white'
                      : 'bg-transparent text-zinc-500 border-zinc-700 hover:border-zinc-500'
                  }`}
                  data-testid={`dest-${d}`}
                >
                  {d === 'offerup' ? 'OfferUp' : d === 'facebook' ? 'FB Marketplace' : 'Website'}
                </button>
              ))}
            </div>
          </div>

          <div className="flex gap-3 mt-6">
            <button
              onClick={handleCreate}
              disabled={creating || !form.name.trim()}
              className="px-6 py-2 bg-white text-black text-sm font-medium hover:bg-zinc-200 disabled:opacity-40 transition"
              data-testid="create-batch-submit"
            >
              {creating ? 'Creating...' : 'Create Batch'}
            </button>
            <button
              onClick={() => setShowCreate(false)}
              className="px-4 py-2 text-zinc-500 text-sm hover:text-white transition"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Batch List */}
      <div className="space-y-2" data-testid="batch-list">
        {batches.length === 0 && !showCreate && (
          <div className="text-center py-16 border border-zinc-800 border-dashed">
            <Camera className="w-10 h-10 text-zinc-600 mx-auto mb-4" />
            <p className="text-white text-lg font-medium mb-2">Photo Batch Intake</p>
            <p className="text-zinc-500 text-sm mb-1">Upload product photos from your phone, store, or sourcing trips</p>
            <p className="text-zinc-600 text-xs mb-6">Photos + grouped note = listing-ready records + marketplace packs</p>
            <button
              onClick={() => setShowCreate(true)}
              className="px-6 py-2 bg-white text-black text-sm font-medium hover:bg-zinc-200 transition"
            >
              Create First Batch
            </button>
          </div>
        )}

        {batches.map(batch => (
          <div
            key={batch.id}
            className="flex items-center border border-zinc-800 hover:border-zinc-600 transition group"
            data-testid={`batch-row-${batch.id}`}
          >
            <button
              onClick={() => navigate(`/field-listing/${batch.id}`)}
              className="flex-1 flex items-center gap-4 p-4 text-left"
            >
              <Package className="w-5 h-5 text-zinc-600 group-hover:text-zinc-400" />
              <div className="flex-1 min-w-0">
                <div className="text-sm text-white font-medium truncate">{batch.name}</div>
                <div className="text-xs text-zinc-500 mt-0.5">
                  {batch.source_vendor && <span>{batch.source_vendor} &middot; </span>}
                  {batch.item_count || 0} items
                  {batch.grouped_pricing_note && <span className="text-zinc-600"> &middot; {batch.grouped_pricing_note.slice(0, 40)}</span>}
                </div>
              </div>
              <span className={`text-[10px] border px-2 py-0.5 uppercase tracking-wider ${statusColor[batch.status] || 'text-zinc-400 border-zinc-700'}`}>
                {batch.status}
              </span>
              <ChevronRight className="w-4 h-4 text-zinc-700 group-hover:text-zinc-400" />
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); handleDelete(batch.id, batch.name); }}
              className="p-4 text-zinc-700 hover:text-red-500 transition"
              data-testid={`delete-batch-${batch.id}`}
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
