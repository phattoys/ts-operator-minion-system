import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import {
  ArrowLeft, Save, Wand2, Trash2, Tag,
  RefreshCw, CheckCircle, FolderTree,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const STATUS_STYLES = {
  Draft: 'text-zinc-400 bg-zinc-800/60',
  'Needs Review': 'text-amber-400 bg-amber-900/30',
  Ready: 'text-emerald-400 bg-emerald-900/30',
  Exported: 'text-blue-400 bg-blue-900/30',
  Archived: 'text-zinc-600 bg-zinc-900/40',
};

const STATUSES = ['Draft', 'Needs Review', 'Ready', 'Exported', 'Archived'];

export default function CatalogItemEditor() {
  const { itemId } = useParams();
  const navigate = useNavigate();
  const [item, setItem] = useState(null);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [normalizing, setNormalizing] = useState(false);
  const [normResult, setNormResult] = useState(null);
  const [form, setForm] = useState({});
  const [dirty, setDirty] = useState(false);
  const [tagInput, setTagInput] = useState('');
  const [showCatForm, setShowCatForm] = useState(false);
  const [newCatName, setNewCatName] = useState('');

  useEffect(() => {
    const fetchItem = async () => {
      try {
        const [itemRes, catsRes] = await Promise.all([
          axios.get(`${API}/catalog/items/${itemId}`, { withCredentials: true }),
          axios.get(`${API}/catalog/categories`, { withCredentials: true }),
        ]);
        setItem(itemRes.data);
        setForm(itemRes.data);
        setCategories(catsRes.data.categories || []);
      } catch (err) {
        console.error('Failed to fetch item:', err);
      }
      setLoading(false);
    };
    fetchItem();
  }, [itemId]);

  const updateField = (field, value) => {
    setForm(prev => ({ ...prev, [field]: value }));
    setDirty(true);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload = {};
      const fields = ['title', 'brand', 'short_description', 'description', 'sku',
        'regular_price', 'sale_price', 'category_id', 'secondary_category_ids',
        'tags', 'attributes', 'color', 'size', 'status', 'image_urls'];
      for (const f of fields) {
        if (form[f] !== item[f]) {
          payload[f] = form[f];
        }
      }
      if (Object.keys(payload).length > 0) {
        const res = await axios.put(`${API}/catalog/items/${itemId}`, payload, { withCredentials: true });
        setItem(res.data);
        setForm(res.data);
        setDirty(false);
      }
    } catch (err) {
      alert(err.response?.data?.detail || 'Save failed');
    }
    setSaving(false);
  };

  const handleNormalize = async () => {
    setNormalizing(true);
    setNormResult(null);
    try {
      const res = await axios.post(`${API}/catalog/items/${itemId}/normalize`, {}, { withCredentials: true });
      setItem(res.data.item);
      setForm(res.data.item);
      setNormResult(res.data.normalization_result);
      setDirty(false);
    } catch (err) {
      alert(err.response?.data?.detail || 'Normalization failed');
    }
    setNormalizing(false);
  };

  const handleDelete = async () => {
    if (!window.confirm('Delete this catalog item?')) return;
    try {
      await axios.delete(`${API}/catalog/items/${itemId}`, { withCredentials: true });
      navigate('/catalog');
    } catch (err) {
      alert(err.response?.data?.detail || 'Delete failed');
    }
  };

  const addTag = () => {
    if (tagInput.trim()) {
      const current = form.tags || [];
      if (!current.includes(tagInput.trim())) {
        updateField('tags', [...current, tagInput.trim()]);
      }
      setTagInput('');
    }
  };

  const removeTag = (t) => {
    updateField('tags', (form.tags || []).filter(x => x !== t));
  };

  const handleCreateCategory = async () => {
    if (!newCatName.trim()) return;
    try {
      const res = await axios.post(`${API}/catalog/categories`, { name: newCatName.trim() }, { withCredentials: true });
      setCategories(prev => [...prev, res.data].sort((a, b) => a.name.localeCompare(b.name)));
      updateField('category_id', res.data.id);
      setNewCatName('');
      setShowCatForm(false);
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to create category');
    }
  };

  if (loading) return <div className="p-8 text-zinc-500 text-sm animate-pulse">Loading...</div>;
  if (!item) return <div className="p-8 text-red-400 text-sm">Item not found</div>;

  return (
    <div className="p-8 max-w-[1200px] mx-auto" data-testid="catalog-item-editor">
      <div className="flex items-center gap-4 mb-6">
        <button onClick={() => navigate('/catalog')} className="text-zinc-500 hover:text-white" data-testid="back-to-catalog">
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex-1">
          <h1 className="text-2xl font-['Outfit'] font-light text-white tracking-tight truncate">
            {form.title || 'Untitled Item'}
          </h1>
          <div className="flex items-center gap-3 mt-1">
            <span className={`px-2 py-0.5 text-xs ${STATUS_STYLES[form.status] || 'text-zinc-500'}`}>
              {form.status}
            </span>
            {form.normalized && <span className="text-xs text-emerald-600">Normalized</span>}
            {form.source_intake_id && <span className="text-xs text-zinc-600">From Intake</span>}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleNormalize}
            disabled={normalizing}
            className="flex items-center gap-2 px-4 py-2 border border-purple-800/50 text-purple-400 text-sm hover:bg-purple-900/20 disabled:opacity-50"
            data-testid="normalize-btn"
          >
            <Wand2 className="w-4 h-4" />
            {normalizing ? 'Normalizing...' : 'Normalize'}
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !dirty}
            className="flex items-center gap-2 px-4 py-2 bg-white text-black text-sm font-medium hover:bg-zinc-200 disabled:opacity-50"
            data-testid="save-item-btn"
          >
            <Save className="w-4 h-4" />
            {saving ? 'Saving...' : 'Save'}
          </button>
          <button onClick={handleDelete} className="p-2 text-zinc-600 hover:text-red-400" data-testid="delete-item-btn">
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {normResult && (
        <div className="mb-6 border border-purple-800/30 bg-purple-950/20 p-4" data-testid="norm-result">
          <div className="flex items-center gap-2 text-purple-400 text-sm mb-2">
            <CheckCircle className="w-4 h-4" />
            Normalization applied
          </div>
          {normResult.category_suggestion && (
            <div className="text-xs text-zinc-400">
              Category: {normResult.category_suggestion.name} ({Math.round(normResult.category_suggestion.confidence * 100)}% confidence)
            </div>
          )}
          {normResult.variant_hint?.is_variant && (
            <div className="text-xs text-zinc-400 mt-1">
              Variant detected: {normResult.variant_hint.variant_attributes?.join(', ')}
            </div>
          )}
        </div>
      )}

      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2 space-y-4">
          <FieldGroup label="Title">
            <input
              value={form.title || ''}
              onChange={e => updateField('title', e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-800 text-white text-sm px-3 py-2 focus:outline-none focus:border-zinc-600"
              data-testid="field-title"
            />
          </FieldGroup>

          <FieldGroup label="Short Description">
            <textarea
              value={form.short_description || ''}
              onChange={e => updateField('short_description', e.target.value)}
              rows={2}
              className="w-full bg-zinc-900 border border-zinc-800 text-white text-sm px-3 py-2 focus:outline-none focus:border-zinc-600 resize-none"
              data-testid="field-short-description"
            />
          </FieldGroup>

          <FieldGroup label="Full Description">
            <textarea
              value={form.description || ''}
              onChange={e => updateField('description', e.target.value)}
              rows={6}
              className="w-full bg-zinc-900 border border-zinc-800 text-white text-sm px-3 py-2 focus:outline-none focus:border-zinc-600 resize-none"
              data-testid="field-description"
            />
          </FieldGroup>

          <FieldGroup label="Tags">
            <div className="flex flex-wrap gap-2 mb-2">
              {(form.tags || []).map(t => (
                <span key={t} className="flex items-center gap-1 px-2 py-0.5 bg-zinc-800 text-zinc-300 text-xs">
                  <Tag className="w-3 h-3" />{t}
                  <button onClick={() => removeTag(t)} className="text-zinc-600 hover:text-red-400 ml-1">&times;</button>
                </span>
              ))}
            </div>
            <div className="flex gap-2">
              <input
                value={tagInput}
                onChange={e => setTagInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && (e.preventDefault(), addTag())}
                placeholder="Add tag..."
                className="flex-1 bg-zinc-900 border border-zinc-800 text-white text-sm px-3 py-1.5 focus:outline-none focus:border-zinc-600"
                data-testid="tag-input"
              />
              <button onClick={addTag} className="px-3 py-1.5 border border-zinc-700 text-zinc-400 text-sm hover:bg-zinc-800">Add</button>
            </div>
          </FieldGroup>
        </div>

        <div className="space-y-4">
          <FieldGroup label="Status">
            <select
              value={form.status || 'Draft'}
              onChange={e => updateField('status', e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-800 text-zinc-300 text-sm px-3 py-2 focus:outline-none"
              data-testid="field-status"
            >
              {STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </FieldGroup>

          <FieldGroup label="Brand">
            <input
              value={form.brand || ''}
              onChange={e => updateField('brand', e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-800 text-white text-sm px-3 py-2 focus:outline-none focus:border-zinc-600"
              data-testid="field-brand"
            />
          </FieldGroup>

          <FieldGroup label="SKU">
            <input
              value={form.sku || ''}
              onChange={e => updateField('sku', e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-800 text-white text-sm px-3 py-2 focus:outline-none focus:border-zinc-600"
              data-testid="field-sku"
            />
          </FieldGroup>

          <div className="grid grid-cols-2 gap-3">
            <FieldGroup label="Regular Price">
              <input
                value={form.regular_price ?? ''}
                onChange={e => updateField('regular_price', e.target.value ? parseFloat(e.target.value) : null)}
                type="number" step="0.01"
                className="w-full bg-zinc-900 border border-zinc-800 text-white text-sm px-3 py-2 focus:outline-none focus:border-zinc-600"
                data-testid="field-regular-price"
              />
            </FieldGroup>
            <FieldGroup label="Sale Price">
              <input
                value={form.sale_price ?? ''}
                onChange={e => updateField('sale_price', e.target.value ? parseFloat(e.target.value) : null)}
                type="number" step="0.01"
                className="w-full bg-zinc-900 border border-zinc-800 text-white text-sm px-3 py-2 focus:outline-none focus:border-zinc-600"
                data-testid="field-sale-price"
              />
            </FieldGroup>
          </div>

          <FieldGroup label="Category">
            <select
              value={form.category_id || ''}
              onChange={e => updateField('category_id', e.target.value || null)}
              className="w-full bg-zinc-900 border border-zinc-800 text-zinc-300 text-sm px-3 py-2 focus:outline-none"
              data-testid="field-category"
            >
              <option value="">Uncategorized</option>
              {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
            {!showCatForm ? (
              <button onClick={() => setShowCatForm(true)} className="text-xs text-zinc-600 hover:text-zinc-400 mt-1" data-testid="add-category-link">
                + Add new category
              </button>
            ) : (
              <div className="flex gap-2 mt-2">
                <input
                  value={newCatName}
                  onChange={e => setNewCatName(e.target.value)}
                  placeholder="Category name"
                  className="flex-1 bg-zinc-800 border border-zinc-700 text-white text-xs px-2 py-1 focus:outline-none"
                  data-testid="new-cat-input"
                />
                <button onClick={handleCreateCategory} className="px-2 py-1 bg-zinc-700 text-white text-xs hover:bg-zinc-600" data-testid="create-cat-btn">Add</button>
                <button onClick={() => setShowCatForm(false)} className="text-xs text-zinc-600 hover:text-white">Cancel</button>
              </div>
            )}
          </FieldGroup>

          <div className="grid grid-cols-2 gap-3">
            <FieldGroup label="Color">
              <input
                value={form.color || ''}
                onChange={e => updateField('color', e.target.value)}
                className="w-full bg-zinc-900 border border-zinc-800 text-white text-sm px-3 py-2 focus:outline-none focus:border-zinc-600"
                data-testid="field-color"
              />
            </FieldGroup>
            <FieldGroup label="Size">
              <input
                value={form.size || ''}
                onChange={e => updateField('size', e.target.value)}
                className="w-full bg-zinc-900 border border-zinc-800 text-white text-sm px-3 py-2 focus:outline-none focus:border-zinc-600"
                data-testid="field-size"
              />
            </FieldGroup>
          </div>
        </div>
      </div>
    </div>
  );
}

function FieldGroup({ label, children }) {
  return (
    <div>
      <label className="block text-xs text-zinc-500 uppercase tracking-wider mb-1.5">{label}</label>
      {children}
    </div>
  );
}
