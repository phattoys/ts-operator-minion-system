import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import {
  Package, Plus, Search, Download, Upload,
  RefreshCw, ChevronRight, Filter, Archive,
  CheckCircle, AlertTriangle, FileText, Layers,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const STATUS_STYLES = {
  Draft: 'text-zinc-400 bg-zinc-800/60',
  'Needs Review': 'text-amber-400 bg-amber-900/30',
  Ready: 'text-emerald-400 bg-emerald-900/30',
  Exported: 'text-blue-400 bg-blue-900/30',
  Archived: 'text-zinc-600 bg-zinc-900/40',
};

export default function CatalogDashboard() {
  const [items, setItems] = useState([]);
  const [stats, setStats] = useState(null);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [showImportModal, setShowImportModal] = useState(false);
  const [showNewForm, setShowNewForm] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState(null);
  const navigate = useNavigate();

  const fetchData = useCallback(async () => {
    try {
      const params = {};
      if (statusFilter) params.status = statusFilter;
      if (categoryFilter) params.category_id = categoryFilter;
      if (search) params.search = search;

      const [itemsRes, statsRes, catsRes] = await Promise.all([
        axios.get(`${API}/catalog/items`, { params, withCredentials: true }),
        axios.get(`${API}/catalog/stats`, { withCredentials: true }),
        axios.get(`${API}/catalog/categories`, { withCredentials: true }),
      ]);
      setItems(itemsRes.data.items || []);
      setStats(statsRes.data);
      setCategories(catsRes.data.categories || []);
    } catch (err) {
      console.error('Failed to fetch catalog data:', err);
    }
    setLoading(false);
  }, [statusFilter, categoryFilter, search]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const catMap = {};
  categories.forEach(c => { catMap[c.id] = c.name; });

  const handleImportFromIntake = async (statusList) => {
    setImporting(true);
    try {
      const res = await axios.post(`${API}/catalog/import-from-intake`, {
        statuses: statusList,
      }, { withCredentials: true });
      setImportResult(res.data);
      fetchData();
    } catch (err) {
      setImportResult({ error: err.response?.data?.detail || 'Import failed' });
    }
    setImporting(false);
  };

  const handleExportWoo = async () => {
    try {
      const res = await axios.get(`${API}/catalog/export/woo-csv`, {
        params: { status: 'Ready' },
        withCredentials: true,
        responseType: 'blob',
      });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = `woo-catalog-export.csv`;
      a.click();
      window.URL.revokeObjectURL(url);
      fetchData();
    } catch (err) {
      alert(err.response?.data?.detail || 'No items ready for export');
    }
  };

  return (
    <div className="p-8 max-w-[1400px] mx-auto" data-testid="catalog-dashboard">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-['Outfit'] font-light text-white tracking-tight">
            Catalog
          </h1>
          <p className="text-sm text-zinc-500 mt-1">Catalog Minion — normalize, dedupe, publish</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowImportModal(true)}
            className="flex items-center gap-2 px-4 py-2 border border-zinc-700 text-zinc-300 text-sm hover:bg-zinc-800 transition-colors"
            data-testid="import-intake-btn"
          >
            <Upload className="w-4 h-4" />
            Import from Intake
          </button>
          <button
            onClick={handleExportWoo}
            className="flex items-center gap-2 px-4 py-2 border border-zinc-700 text-zinc-300 text-sm hover:bg-zinc-800 transition-colors"
            data-testid="export-woo-btn"
          >
            <Download className="w-4 h-4" />
            Woo Export
          </button>
          <button
            onClick={() => setShowNewForm(true)}
            className="flex items-center gap-2 px-4 py-2 bg-white text-black text-sm font-medium hover:bg-zinc-200 transition-colors"
            data-testid="new-catalog-item-btn"
          >
            <Plus className="w-4 h-4" />
            New Item
          </button>
        </div>
      </div>

      {stats && (
        <div className="grid grid-cols-6 gap-4 mb-8" data-testid="catalog-stats">
          <StatCard label="Total" value={stats.total_items} />
          <StatCard label="Draft" value={stats.draft_count} color="text-zinc-400" />
          <StatCard label="Needs Review" value={stats.needs_review_count} color="text-amber-400" />
          <StatCard label="Ready" value={stats.ready_count} color="text-emerald-400" />
          <StatCard label="Exported" value={stats.exported_count} color="text-blue-400" />
          <StatCard label="Categories" value={stats.category_count} color="text-purple-400" />
        </div>
      )}

      <div className="flex items-center gap-3 mb-6">
        <div className="relative flex-1">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
          <input
            type="text"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search title, brand, SKU..."
            className="w-full bg-zinc-900 border border-zinc-800 text-white text-sm pl-10 pr-4 py-2 placeholder-zinc-600 focus:outline-none focus:border-zinc-600"
            data-testid="catalog-search"
          />
        </div>
        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          className="bg-zinc-900 border border-zinc-800 text-zinc-300 text-sm px-3 py-2 focus:outline-none"
          data-testid="status-filter"
        >
          <option value="">All Statuses</option>
          {['Draft', 'Needs Review', 'Ready', 'Exported', 'Archived'].map(s => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <select
          value={categoryFilter}
          onChange={e => setCategoryFilter(e.target.value)}
          className="bg-zinc-900 border border-zinc-800 text-zinc-300 text-sm px-3 py-2 focus:outline-none"
          data-testid="category-filter"
        >
          <option value="">All Categories</option>
          {categories.map(c => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
        <button
          onClick={() => navigate('/catalog/duplicates')}
          className="flex items-center gap-2 px-4 py-2 border border-amber-800/50 text-amber-400 text-sm hover:bg-amber-900/20 transition-colors"
          data-testid="duplicate-review-btn"
        >
          <Layers className="w-4 h-4" />
          Duplicate Review
        </button>
      </div>

      {loading ? (
        <div className="text-center py-20 text-zinc-500 text-sm animate-pulse">Loading catalog...</div>
      ) : items.length === 0 ? (
        <div className="text-center py-20 border border-zinc-800 border-dashed" data-testid="catalog-empty">
          <Package className="w-10 h-10 mx-auto text-zinc-700 mb-3" />
          <p className="text-zinc-500 text-sm">No catalog items yet</p>
          <p className="text-zinc-600 text-xs mt-1">Import from Product Intake or create manually</p>
        </div>
      ) : (
        <div className="border border-zinc-800" data-testid="catalog-items-table">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-800 text-left">
                <th className="px-4 py-3 text-zinc-500 text-xs uppercase tracking-wider font-normal">Title</th>
                <th className="px-4 py-3 text-zinc-500 text-xs uppercase tracking-wider font-normal">Brand</th>
                <th className="px-4 py-3 text-zinc-500 text-xs uppercase tracking-wider font-normal">Category</th>
                <th className="px-4 py-3 text-zinc-500 text-xs uppercase tracking-wider font-normal">Price</th>
                <th className="px-4 py-3 text-zinc-500 text-xs uppercase tracking-wider font-normal">Status</th>
                <th className="px-4 py-3 text-zinc-500 text-xs uppercase tracking-wider font-normal w-10"></th>
              </tr>
            </thead>
            <tbody>
              {items.map(item => (
                <tr
                  key={item.id}
                  className="border-b border-zinc-800/50 hover:bg-zinc-900/50 cursor-pointer transition-colors"
                  onClick={() => navigate(`/catalog/${item.id}`)}
                  data-testid={`catalog-item-${item.id}`}
                >
                  <td className="px-4 py-3">
                    <div className="text-white font-medium truncate max-w-[300px]">{item.title}</div>
                    {item.sku && <div className="text-zinc-600 text-xs mt-0.5">SKU: {item.sku}</div>}
                  </td>
                  <td className="px-4 py-3 text-zinc-400">{item.brand || '—'}</td>
                  <td className="px-4 py-3 text-zinc-400">{catMap[item.category_id] || '—'}</td>
                  <td className="px-4 py-3 text-zinc-300">
                    {item.regular_price ? `$${Number(item.regular_price).toFixed(2)}` : '—'}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 text-xs ${STATUS_STYLES[item.status] || 'text-zinc-500 bg-zinc-800'}`}>
                      {item.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <ChevronRight className="w-4 h-4 text-zinc-600" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showImportModal && (
        <ImportModal
          importing={importing}
          result={importResult}
          onImport={handleImportFromIntake}
          onClose={() => { setShowImportModal(false); setImportResult(null); }}
        />
      )}

      {showNewForm && (
        <NewItemModal
          categories={categories}
          onCreated={() => { setShowNewForm(false); fetchData(); }}
          onClose={() => setShowNewForm(false)}
        />
      )}
    </div>
  );
}

function StatCard({ label, value, color = 'text-white' }) {
  return (
    <div className="border border-zinc-800 p-4">
      <div className={`text-2xl font-['Outfit'] ${color}`}>{value}</div>
      <div className="text-xs text-zinc-500 uppercase tracking-wider mt-1">{label}</div>
    </div>
  );
}

function ImportModal({ importing, result, onImport, onClose }) {
  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50" data-testid="import-modal">
      <div className="bg-zinc-900 border border-zinc-700 p-6 w-full max-w-md">
        <h2 className="text-lg font-['Outfit'] text-white mb-4">Import from Product Intake</h2>
        {result ? (
          <div className="space-y-3">
            {result.error ? (
              <div className="text-red-400 text-sm">{result.error}</div>
            ) : (
              <>
                <div className="text-emerald-400 text-sm flex items-center gap-2">
                  <CheckCircle className="w-4 h-4" />
                  Imported {result.imported_count} items
                </div>
                {result.skipped_duplicates > 0 && (
                  <div className="text-zinc-500 text-xs">Skipped {result.skipped_duplicates} already-imported items</div>
                )}
              </>
            )}
            <button onClick={onClose} className="w-full mt-3 px-4 py-2 bg-zinc-800 text-white text-sm hover:bg-zinc-700">
              Close
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-zinc-400 text-sm">Pull items from Product Intake into the catalog pipeline.</p>
            <button
              onClick={() => onImport(['ready'])}
              disabled={importing}
              className="w-full px-4 py-2 bg-white text-black text-sm font-medium hover:bg-zinc-200 disabled:opacity-50"
              data-testid="import-ready-btn"
            >
              {importing ? 'Importing...' : 'Import Ready Items'}
            </button>
            <button
              onClick={() => onImport(['ready', 'in_review'])}
              disabled={importing}
              className="w-full px-4 py-2 border border-zinc-700 text-zinc-300 text-sm hover:bg-zinc-800 disabled:opacity-50"
              data-testid="import-all-btn"
            >
              {importing ? 'Importing...' : 'Import Ready + In Review'}
            </button>
            <button onClick={onClose} className="w-full px-4 py-2 text-zinc-500 text-sm hover:text-white">Cancel</button>
          </div>
        )}
      </div>
    </div>
  );
}

function NewItemModal({ categories, onCreated, onClose }) {
  const [title, setTitle] = useState('');
  const [brand, setBrand] = useState('');
  const [price, setPrice] = useState('');
  const [categoryId, setCategoryId] = useState('');
  const [saving, setSaving] = useState(false);

  const handleSubmit = async () => {
    if (!title.trim()) return;
    setSaving(true);
    try {
      await axios.post(`${API}/catalog/items`, {
        title: title.trim(),
        brand: brand.trim() || null,
        regular_price: price ? parseFloat(price) : null,
        category_id: categoryId || null,
      }, { withCredentials: true });
      onCreated();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to create');
    }
    setSaving(false);
  };

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50" data-testid="new-item-modal">
      <div className="bg-zinc-900 border border-zinc-700 p-6 w-full max-w-md">
        <h2 className="text-lg font-['Outfit'] text-white mb-4">New Catalog Item</h2>
        <div className="space-y-3">
          <input
            value={title}
            onChange={e => setTitle(e.target.value)}
            placeholder="Product title *"
            className="w-full bg-zinc-800 border border-zinc-700 text-white text-sm px-3 py-2 placeholder-zinc-600 focus:outline-none focus:border-zinc-500"
            data-testid="new-item-title"
          />
          <input
            value={brand}
            onChange={e => setBrand(e.target.value)}
            placeholder="Brand (optional)"
            className="w-full bg-zinc-800 border border-zinc-700 text-white text-sm px-3 py-2 placeholder-zinc-600 focus:outline-none focus:border-zinc-500"
            data-testid="new-item-brand"
          />
          <input
            value={price}
            onChange={e => setPrice(e.target.value)}
            placeholder="Price (optional)"
            type="number"
            step="0.01"
            className="w-full bg-zinc-800 border border-zinc-700 text-white text-sm px-3 py-2 placeholder-zinc-600 focus:outline-none focus:border-zinc-500"
            data-testid="new-item-price"
          />
          <select
            value={categoryId}
            onChange={e => setCategoryId(e.target.value)}
            className="w-full bg-zinc-800 border border-zinc-700 text-zinc-300 text-sm px-3 py-2 focus:outline-none"
            data-testid="new-item-category"
          >
            <option value="">Select Category (optional)</option>
            {categories.map(c => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
          <div className="flex gap-3 mt-4">
            <button
              onClick={handleSubmit}
              disabled={saving || !title.trim()}
              className="flex-1 px-4 py-2 bg-white text-black text-sm font-medium hover:bg-zinc-200 disabled:opacity-50"
              data-testid="create-item-submit"
            >
              {saving ? 'Creating...' : 'Create'}
            </button>
            <button onClick={onClose} className="px-4 py-2 text-zinc-500 text-sm hover:text-white">Cancel</button>
          </div>
        </div>
      </div>
    </div>
  );
}
