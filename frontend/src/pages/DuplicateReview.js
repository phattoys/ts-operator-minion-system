import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import {
  ArrowLeft, Layers, Check, X, Merge,
  AlertTriangle, ChevronRight,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export default function DuplicateReview() {
  const [pairs, setPairs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [threshold, setThreshold] = useState(60);
  const [resolving, setResolving] = useState(null);
  const [expandedIdx, setExpandedIdx] = useState(null);
  const navigate = useNavigate();

  const fetchDuplicates = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/catalog/duplicates`, {
        params: { threshold },
        withCredentials: true,
      });
      setPairs(res.data.pairs || []);
    } catch (err) {
      console.error('Failed to scan duplicates:', err);
    }
    setLoading(false);
  };

  useEffect(() => { fetchDuplicates(); }, [threshold]);

  const handleResolve = async (pairIdx, action) => {
    const pair = pairs[pairIdx];
    setResolving(pairIdx);
    try {
      await axios.post(`${API}/catalog/duplicates/resolve`, {
        action,
      }, {
        params: {
          item_a_id: pair.item_a.id,
          item_b_id: pair.item_b.id,
        },
        withCredentials: true,
      });
      setPairs(prev => prev.filter((_, i) => i !== pairIdx));
      if (expandedIdx === pairIdx) setExpandedIdx(null);
    } catch (err) {
      alert(err.response?.data?.detail || 'Resolve failed');
    }
    setResolving(null);
  };

  return (
    <div className="p-8 max-w-[1400px] mx-auto" data-testid="duplicate-review">
      <div className="flex items-center gap-4 mb-8">
        <button onClick={() => navigate('/catalog')} className="text-zinc-500 hover:text-white" data-testid="back-to-catalog">
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex-1">
          <h1 className="text-3xl font-['Outfit'] font-light text-white tracking-tight">
            Duplicate Review
          </h1>
          <p className="text-sm text-zinc-500 mt-1">Review and resolve potential duplicate catalog items</p>
        </div>
        <div className="flex items-center gap-3">
          <label className="text-xs text-zinc-500">Threshold:</label>
          <select
            value={threshold}
            onChange={e => setThreshold(Number(e.target.value))}
            className="bg-zinc-900 border border-zinc-800 text-zinc-300 text-sm px-3 py-1.5 focus:outline-none"
            data-testid="threshold-select"
          >
            <option value={50}>50% (Loose)</option>
            <option value={60}>60% (Default)</option>
            <option value={70}>70% (Moderate)</option>
            <option value={80}>80% (Strict)</option>
          </select>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-20 text-zinc-500 text-sm animate-pulse">Scanning for duplicates...</div>
      ) : pairs.length === 0 ? (
        <div className="text-center py-20 border border-zinc-800 border-dashed" data-testid="no-duplicates">
          <Layers className="w-10 h-10 mx-auto text-zinc-700 mb-3" />
          <p className="text-zinc-500 text-sm">No duplicate candidates found</p>
          <p className="text-zinc-600 text-xs mt-1">Try lowering the threshold or adding more items</p>
        </div>
      ) : (
        <div className="space-y-3" data-testid="duplicate-pairs">
          <div className="text-xs text-zinc-500 mb-2">{pairs.length} potential duplicate pair{pairs.length !== 1 ? 's' : ''} found</div>
          {pairs.map((pair, idx) => (
            <div key={idx} className="border border-zinc-800 hover:border-zinc-700 transition-colors" data-testid={`dup-pair-${idx}`}>
              <div
                className="flex items-center gap-4 px-4 py-3 cursor-pointer"
                onClick={() => setExpandedIdx(expandedIdx === idx ? null : idx)}
              >
                <div className="flex items-center gap-2 text-amber-400">
                  <AlertTriangle className="w-4 h-4" />
                  <span className="text-sm font-medium">{Math.round(pair.score * 100)}%</span>
                </div>
                <div className="flex-1 grid grid-cols-2 gap-4 text-sm">
                  <div className="text-white truncate">{pair.item_a.title}</div>
                  <div className="text-zinc-400 truncate">{pair.item_b.title}</div>
                </div>
                <div className="flex items-center gap-2 text-xs text-zinc-600">
                  {pair.signals.sku_match && <span className="px-1.5 py-0.5 bg-zinc-800 text-zinc-400">SKU</span>}
                  {pair.signals.brand_match && <span className="px-1.5 py-0.5 bg-zinc-800 text-zinc-400">Brand</span>}
                  {pair.signals.title_similarity && <span className="px-1.5 py-0.5 bg-zinc-800 text-zinc-400">Title</span>}
                  <ChevronRight className={`w-4 h-4 transition-transform ${expandedIdx === idx ? 'rotate-90' : ''}`} />
                </div>
              </div>

              {expandedIdx === idx && (
                <div className="border-t border-zinc-800 px-4 py-4" data-testid={`dup-detail-${idx}`}>
                  <div className="grid grid-cols-2 gap-6">
                    <ItemCard item={pair.item_a} label="Item A" />
                    <ItemCard item={pair.item_b} label="Item B" />
                  </div>
                  <div className="flex items-center justify-center gap-3 mt-4 pt-4 border-t border-zinc-800">
                    <button
                      onClick={() => handleResolve(idx, 'not_duplicate')}
                      disabled={resolving === idx}
                      className="flex items-center gap-2 px-4 py-2 border border-zinc-700 text-zinc-400 text-sm hover:bg-zinc-800 disabled:opacity-50"
                      data-testid={`dismiss-${idx}`}
                    >
                      <X className="w-4 h-4" />
                      Not a Duplicate
                    </button>
                    <button
                      onClick={() => handleResolve(idx, 'merge_keep_left')}
                      disabled={resolving === idx}
                      className="flex items-center gap-2 px-4 py-2 border border-emerald-800/50 text-emerald-400 text-sm hover:bg-emerald-900/20 disabled:opacity-50"
                      data-testid={`keep-a-${idx}`}
                    >
                      <Merge className="w-4 h-4" />
                      Keep A, Merge B
                    </button>
                    <button
                      onClick={() => handleResolve(idx, 'merge_keep_right')}
                      disabled={resolving === idx}
                      className="flex items-center gap-2 px-4 py-2 border border-blue-800/50 text-blue-400 text-sm hover:bg-blue-900/20 disabled:opacity-50"
                      data-testid={`keep-b-${idx}`}
                    >
                      <Merge className="w-4 h-4" />
                      Keep B, Merge A
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ItemCard({ item, label }) {
  return (
    <div className="space-y-2">
      <div className="text-xs text-zinc-500 uppercase tracking-wider">{label}</div>
      <div className="text-white text-sm font-medium">{item.title}</div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
        <FieldRow label="Brand" value={item.brand} />
        <FieldRow label="SKU" value={item.sku} />
        <FieldRow label="Price" value={item.regular_price ? `$${Number(item.regular_price).toFixed(2)}` : null} />
        <FieldRow label="Color" value={item.color} />
        <FieldRow label="Size" value={item.size} />
        <FieldRow label="Status" value={item.status} />
      </div>
      {item.short_description && (
        <div className="text-zinc-500 text-xs mt-1 line-clamp-2">{item.short_description}</div>
      )}
      {item.tags?.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-1">
          {item.tags.map(t => (
            <span key={t} className="px-1.5 py-0.5 bg-zinc-800 text-zinc-400 text-[10px]">{t}</span>
          ))}
        </div>
      )}
    </div>
  );
}

function FieldRow({ label, value }) {
  if (!value) return null;
  return (
    <>
      <span className="text-zinc-600">{label}</span>
      <span className="text-zinc-300">{value}</span>
    </>
  );
}
