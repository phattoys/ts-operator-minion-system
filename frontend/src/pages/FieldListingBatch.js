import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import {
  ArrowLeft, Upload, Eye, Sparkles, DollarSign, Package,
  Check, X, Copy, ChevronDown, ChevronUp, AlertTriangle, Layers,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';
const IMAGE_BASE = process.env.REACT_APP_BACKEND_URL + '/api/field-listing/images';

export default function FieldListingBatch() {
  const { batchId } = useParams();
  const navigate = useNavigate();
  const fileInputRef = useRef(null);

  const [batch, setBatch] = useState(null);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [selectedItems, setSelectedItems] = useState(new Set());
  const [activeJob, setActiveJob] = useState(null);
  const [pricingNote, setPricingNote] = useState('');
  const [showPacks, setShowPacks] = useState(false);
  const [packs, setPacks] = useState(null);
  const [expandedItem, setExpandedItem] = useState(null);
  const [suggestedGroups, setSuggestedGroups] = useState([]);
  const [refiningTitle, setRefiningTitle] = useState(null);

  const fetchBatch = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/field-listing/batches/${batchId}`, { withCredentials: true });
      setBatch(res.data);
      setItems(res.data.items || []);
      setPricingNote(res.data.grouped_pricing_note || '');
    } catch (err) {
      console.error('Failed to load batch:', err);
    }
    setLoading(false);
  }, [batchId]);

  useEffect(() => { fetchBatch(); }, [fetchBatch]);

  // Polling for active jobs
  useEffect(() => {
    if (!activeJob) return;
    const interval = setInterval(async () => {
      try {
        const res = await axios.get(`${API}/field-listing/jobs/${activeJob}`, { withCredentials: true });
        if (res.data.status === 'completed' || res.data.status === 'failed') {
          setActiveJob(null);
          await fetchBatch();
        }
      } catch {}
    }, 2000);
    return () => clearInterval(interval);
  }, [activeJob, fetchBatch]);

  const handlePhotoUpload = async (e) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    setUploading(true);
    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
      formData.append('files', files[i]);
    }
    try {
      await axios.post(`${API}/field-listing/batches/${batchId}/upload-photos`, formData, {
        withCredentials: true,
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      await fetchBatch();
    } catch (err) {
      alert(err.response?.data?.detail || 'Upload failed');
    }
    setUploading(false);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleAnalyze = async () => {
    try {
      const res = await axios.post(`${API}/field-listing/batches/${batchId}/analyze`, {}, { withCredentials: true });
      if (res.data.job_id) setActiveJob(res.data.job_id);
      else await fetchBatch();
    } catch (err) {
      alert(err.response?.data?.detail || 'Analysis failed');
    }
  };

  const handleApplyPricing = async () => {
    try {
      const ids = selectedItems.size > 0 ? Array.from(selectedItems) : [];
      await axios.post(`${API}/field-listing/batches/${batchId}/apply-pricing`, {
        pricing_note: pricingNote,
        item_ids: ids,
      }, { withCredentials: true });
      await fetchBatch();
    } catch (err) {
      alert(err.response?.data?.detail || 'Pricing failed');
    }
  };

  const handleGenerateListings = async () => {
    try {
      const res = await axios.post(`${API}/field-listing/batches/${batchId}/generate-listings`, {}, { withCredentials: true });
      if (res.data.job_id) setActiveJob(res.data.job_id);
      else await fetchBatch();
    } catch (err) {
      alert(err.response?.data?.detail || 'Generation failed');
    }
  };

  const handleGeneratePacks = async () => {
    try {
      await axios.post(`${API}/field-listing/batches/${batchId}/generate-packs`, {}, { withCredentials: true });
      const packRes = await axios.get(`${API}/field-listing/batches/${batchId}/packs`, { withCredentials: true });
      setPacks(packRes.data);
      setShowPacks(true);
    } catch (err) {
      alert(err.response?.data?.detail || 'Pack generation failed');
    }
  };

  const handleBulkAction = async (action, value = '') => {
    if (selectedItems.size === 0) return;
    try {
      await axios.post(`${API}/field-listing/batches/${batchId}/bulk-action`, {
        item_ids: Array.from(selectedItems),
        action,
        value,
      }, { withCredentials: true });
      setSelectedItems(new Set());
      await fetchBatch();
    } catch (err) {
      alert(err.response?.data?.detail || 'Action failed');
    }
  };

  const handleMerge = async () => {
    if (selectedItems.size < 2) {
      alert('Select 2 or more items to merge into one product');
      return;
    }
    try {
      setRefiningTitle('merge');
      const res = await axios.post(`${API}/field-listing/batches/${batchId}/merge-items`, {
        item_ids: Array.from(selectedItems),
      }, { withCredentials: true });
      setSelectedItems(new Set());
      setRefiningTitle(null);
      await fetchBatch();
      const titleMsg = res.data.title_refined
        ? `Merged ${res.data.total_images} photos — title refined to: "${res.data.refined_title}"`
        : `Merged ${res.data.total_images} photos into 1 item`;
      alert(titleMsg);
    } catch (err) {
      setRefiningTitle(null);
      alert(err.response?.data?.detail || 'Merge failed');
    }
  };

  const handleSplit = async (itemId) => {
    try {
      const res = await axios.post(`${API}/field-listing/items/${itemId}/split`, {}, { withCredentials: true });
      await fetchBatch();
      alert(`Split into ${res.data.total_split} separate items`);
    } catch (err) {
      alert(err.response?.data?.detail || 'Split failed');
    }
  };

  const handleRefineTitle = async (itemId) => {
    try {
      setRefiningTitle(itemId);
      const res = await axios.post(`${API}/field-listing/items/${itemId}/refine-title`, {}, { withCredentials: true });
      setRefiningTitle(null);
      await fetchBatch();
      alert(`Title refined: "${res.data.refined_title}"`);
    } catch (err) {
      setRefiningTitle(null);
      alert(err.response?.data?.detail || 'Title refinement failed');
    }
  };

  const handleSuggestGroups = async () => {
    try {
      const res = await axios.post(`${API}/field-listing/batches/${batchId}/suggest-groups`, {}, { withCredentials: true });
      if (res.data.suggestions?.length > 0) {
        setSuggestedGroups(res.data.suggestions);
      } else {
        alert('No obvious groupings detected');
      }
    } catch (err) {
      alert(err.response?.data?.detail || 'Suggestion failed');
    }
  };

  const handleAcceptGroup = async (group) => {
    try {
      setRefiningTitle('merge');
      await axios.post(`${API}/field-listing/batches/${batchId}/merge-items`, {
        item_ids: group.item_ids,
      }, { withCredentials: true });
      setSuggestedGroups(prev => prev.filter(g => g !== group));
      setRefiningTitle(null);
      await fetchBatch();
    } catch (err) {
      setRefiningTitle(null);
      alert(err.response?.data?.detail || 'Merge failed');
    }
  };

  const handleDismissGroup = (group) => {
    setSuggestedGroups(prev => prev.filter(g => g !== group));
  };

  const handleItemUpdate = async (itemId, field, value) => {
    try {
      await axios.put(`${API}/field-listing/items/${itemId}`, { [field]: value }, { withCredentials: true });
      await fetchBatch();
    } catch (err) {
      console.error('Update failed:', err);
    }
  };

  const handleBatchNoteUpdate = async (field, value) => {
    try {
      await axios.put(`${API}/field-listing/batches/${batchId}`, { [field]: value }, { withCredentials: true });
      setBatch(prev => ({ ...prev, [field]: value }));
    } catch (err) {
      console.error('Batch update failed:', err);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
  };

  const toggleSelect = (id) => {
    setSelectedItems(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedItems.size === items.length) setSelectedItems(new Set());
    else setSelectedItems(new Set(items.map(i => i.id)));
  };

  const confColor = (flag) => {
    switch (flag) {
      case 'high': return 'text-emerald-400';
      case 'medium': return 'text-amber-400';
      case 'weak': return 'text-red-400';
      default: return 'text-zinc-500';
    }
  };

  const statusBadge = (status) => {
    const colors = {
      draft: 'text-zinc-400 border-zinc-700',
      review: 'text-blue-400 border-blue-800',
      approved: 'text-emerald-400 border-emerald-800',
      skipped: 'text-red-400 border-red-800',
    };
    return colors[status] || 'text-zinc-400 border-zinc-700';
  };

  if (loading) {
    return <div className="p-8 flex items-center justify-center min-h-[50vh]"><div className="text-zinc-500 text-sm animate-pulse">Loading batch...</div></div>;
  }

  if (!batch) {
    return <div className="p-8 text-center text-zinc-500">Batch not found</div>;
  }

  return (
    <div className="p-6 max-w-7xl mx-auto" data-testid="field-listing-batch">
      {/* Header */}
      <div className="flex items-center gap-4 mb-6">
        <button onClick={() => navigate('/field-listing')} className="text-zinc-500 hover:text-white transition">
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex-1">
          <h1 className="text-xl font-bold text-white">{batch.name}</h1>
          <div className="text-xs text-zinc-500 mt-0.5">
            {batch.source_vendor && <span>{batch.source_vendor} &middot; </span>}
            {items.length} items
            {batch.grouped_pricing_note && <span className="text-zinc-600"> &middot; {batch.grouped_pricing_note}</span>}
          </div>
        </div>
        {activeJob && (
          <div className="flex items-center gap-2 text-amber-400 text-xs">
            <div className="w-3 h-3 border-2 border-amber-400 border-t-transparent rounded-full animate-spin" />
            Processing...
          </div>
        )}
      </div>

      {/* === PHOTO-FIRST: Big dropzone when batch has no items === */}
      {items.length === 0 && !uploading && (
        <div className="mb-8" data-testid="photo-dropzone">
          <label className="block border-2 border-dashed border-zinc-700 hover:border-zinc-500 transition cursor-pointer p-12 text-center">
            <Upload className="w-10 h-10 text-zinc-600 mx-auto mb-4" />
            <div className="text-lg text-white font-medium mb-2">Upload Product Photos</div>
            <div className="text-sm text-zinc-500 mb-4">
              Drop phone photos, fixture pics, or product images here
            </div>
            <div className="text-xs text-zinc-600">
              Supports JPG, PNG, WEBP — select multiple files at once
            </div>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept="image/*"
              onChange={handlePhotoUpload}
              className="hidden"
              data-testid="photo-upload-input"
            />
          </label>

          {/* Grouped notes (editable inline when empty) */}
          <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-4 border border-zinc-800 p-4">
            <div className="col-span-full">
              <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-3">Batch Notes (apply to all photos)</div>
            </div>
            <div>
              <label className="text-[10px] text-zinc-600 uppercase">Source / Vendor</label>
              <input
                defaultValue={batch.source_vendor}
                onBlur={e => handleBatchNoteUpdate('source_vendor', e.target.value)}
                placeholder="e.g., Downtown LA, Used fixtures, Store closeout"
                className="w-full mt-1 bg-zinc-900 border border-zinc-700 text-white text-sm px-3 py-2 focus:border-zinc-500 outline-none"
              />
            </div>
            <div>
              <label className="text-[10px] text-zinc-600 uppercase">Grouped Pricing</label>
              <input
                defaultValue={batch.grouped_pricing_note}
                onBlur={e => handleBatchNoteUpdate('grouped_pricing_note', e.target.value)}
                placeholder='e.g., "These were $25 each, sell at $55"'
                className="w-full mt-1 bg-zinc-900 border border-zinc-700 text-white text-sm px-3 py-2 focus:border-zinc-500 outline-none"
              />
            </div>
            <div>
              <label className="text-[10px] text-zinc-600 uppercase">Category / Type Hint</label>
              <input
                defaultValue={batch.grouped_category_note}
                onBlur={e => handleBatchNoteUpdate('grouped_category_note', e.target.value)}
                placeholder='e.g., "Fixtures", "Panties", "Jewelry"'
                className="w-full mt-1 bg-zinc-900 border border-zinc-700 text-white text-sm px-3 py-2 focus:border-zinc-500 outline-none"
              />
            </div>
            <div>
              <label className="text-[10px] text-zinc-600 uppercase">Condition / Pickup Note</label>
              <input
                defaultValue={batch.condition_note || batch.pickup_shipping_note || ''}
                onBlur={e => handleBatchNoteUpdate('condition_note', e.target.value)}
                placeholder="e.g., Used, Local pickup only, Ships free"
                className="w-full mt-1 bg-zinc-900 border border-zinc-700 text-white text-sm px-3 py-2 focus:border-zinc-500 outline-none"
              />
            </div>
          </div>
        </div>
      )}

      {/* === Upload progress === */}
      {uploading && (
        <div className="mb-8 border-2 border-dashed border-amber-800 p-12 text-center">
          <div className="w-6 h-6 border-2 border-amber-400 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <div className="text-sm text-amber-400">Uploading photos...</div>
        </div>
      )}

      {/* === Action bar — shown once items exist === */}
      {items.length > 0 && (
        <>
          <div className="flex flex-wrap gap-2 mb-4 border border-zinc-800 p-3" data-testid="action-bar">
            <label className="flex items-center gap-2 px-3 py-1.5 border border-zinc-700 text-sm text-zinc-300 hover:border-zinc-500 cursor-pointer transition">
              <Upload className="w-3.5 h-3.5" />
              {uploading ? 'Uploading...' : 'Add More Photos'}
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept="image/*"
                onChange={handlePhotoUpload}
                className="hidden"
                disabled={uploading}
                data-testid="photo-upload-input-more"
              />
            </label>
            <button
              onClick={handleAnalyze}
              disabled={!!activeJob || items.filter(i => i.confidence_flag === 'pending').length === 0}
              className="flex items-center gap-2 px-3 py-1.5 border border-zinc-700 text-sm text-zinc-300 hover:border-zinc-500 disabled:opacity-30 transition"
              data-testid="analyze-btn"
            >
              <Eye className="w-3.5 h-3.5" /> Analyze Photos
              {items.filter(i => i.confidence_flag === 'pending').length > 0 && (
                <span className="text-[10px] text-amber-400 ml-1">({items.filter(i => i.confidence_flag === 'pending').length} pending)</span>
              )}
            </button>
            <button
              onClick={handleGenerateListings}
              disabled={!!activeJob || items.filter(i => i.draft_title && !i.short_description).length === 0}
              className="flex items-center gap-2 px-3 py-1.5 border border-zinc-700 text-sm text-zinc-300 hover:border-zinc-500 disabled:opacity-30 transition"
              data-testid="generate-listings-btn"
            >
              <Sparkles className="w-3.5 h-3.5" /> Generate Listings
            </button>
            <button
              onClick={handleGeneratePacks}
              disabled={items.filter(i => i.status === 'review' || i.status === 'approved').length === 0}
              className="flex items-center gap-2 px-3 py-1.5 border border-amber-800/50 text-sm text-amber-400 hover:border-amber-600 disabled:opacity-30 transition"
              data-testid="generate-packs-btn"
            >
              <Package className="w-3.5 h-3.5" /> Generate Packs
            </button>
            <button
              onClick={handleSuggestGroups}
              disabled={items.length < 2}
              className="flex items-center gap-2 px-3 py-1.5 border border-purple-800/50 text-sm text-purple-400 hover:border-purple-600 disabled:opacity-30 transition"
              data-testid="suggest-groups-btn"
            >
              <Layers className="w-3.5 h-3.5" /> Suggest Groups
            </button>
          </div>

          {/* Pricing Bar */}
          <div className="flex items-center gap-3 mb-4 border border-zinc-800 p-3" data-testid="pricing-bar">
            <DollarSign className="w-4 h-4 text-zinc-600" />
            <input
              value={pricingNote}
              onChange={e => setPricingNote(e.target.value)}
              placeholder='Grouped pricing note: "These were $25 each, sell at $55"'
              className="flex-1 bg-transparent text-sm text-white outline-none placeholder:text-zinc-600"
              data-testid="pricing-note-input"
            />
            <button
              onClick={handleApplyPricing}
              disabled={!pricingNote.trim()}
              className="px-3 py-1 text-xs bg-zinc-800 text-zinc-300 hover:bg-zinc-700 disabled:opacity-30 transition"
              data-testid="apply-pricing-btn"
            >
              Apply {selectedItems.size > 0 ? `(${selectedItems.size})` : 'All'}
            </button>
          </div>
        </>
      )}

      {/* Bulk Actions */}
      {selectedItems.size > 0 && (
        <div className="flex items-center gap-3 mb-4 border border-blue-900/40 bg-blue-950/20 p-3" data-testid="bulk-actions-bar">
          <span className="text-xs text-blue-400">{selectedItems.size} selected</span>
          {selectedItems.size >= 2 && (
            <button onClick={handleMerge} disabled={refiningTitle === 'merge'} className="px-3 py-1 text-xs border border-purple-800 text-purple-400 hover:bg-purple-950/30 disabled:opacity-50 transition" data-testid="merge-btn">
              <span className="flex items-center gap-1">
                <Layers className="w-3 h-3" />
                {refiningTitle === 'merge' ? 'Merging & Refining Title...' : 'Merge into 1 Item'}
              </span>
            </button>
          )}
          <button onClick={() => handleBulkAction('approve')} className="px-3 py-1 text-xs border border-emerald-800 text-emerald-400 hover:bg-emerald-950/30 transition">Approve</button>
          <button onClick={() => handleBulkAction('skip')} className="px-3 py-1 text-xs border border-red-800 text-red-400 hover:bg-red-950/30 transition">Skip</button>
          <button onClick={() => setSelectedItems(new Set())} className="ml-auto text-xs text-zinc-500 hover:text-white">Clear</button>
        </div>
      )}

      {/* Suggested Groups Banner */}
      {suggestedGroups.length > 0 && (
        <div className="mb-4 border border-purple-900/40 bg-purple-950/20 p-4" data-testid="suggested-groups">
          <div className="flex items-center gap-2 mb-3">
            <Layers className="w-4 h-4 text-purple-400" />
            <span className="text-sm text-purple-400 font-medium">Suggested Groups — Same product, multiple photos?</span>
            <span className="text-[10px] text-zinc-500 ml-2">{suggestedGroups.length} potential matches</span>
          </div>
          <div className="space-y-2">
            {suggestedGroups.map((group, i) => (
              <div key={i} className="flex items-center gap-3 bg-zinc-900/50 border border-zinc-800 p-2">
                <div className="flex gap-1">
                  {group.item_ids.map(id => {
                    const item = items.find(it => it.id === id);
                    const img = item?.images?.[0];
                    const imgUrl = img ? `${IMAGE_BASE}/${batchId}/${img.filename}` : null;
                    return (
                      <div key={id} className="w-10 h-10 bg-zinc-800 border border-zinc-700 overflow-hidden">
                        {imgUrl ? <img src={imgUrl} alt="" className="w-full h-full object-cover" /> : <div className="w-full h-full" />}
                      </div>
                    );
                  })}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-xs text-white truncate">{group.suggested_title}</div>
                  <div className="text-[10px] text-zinc-500">{group.reason} ({Math.round(group.confidence * 100)}% confident)</div>
                </div>
                <button
                  onClick={() => handleAcceptGroup(group)}
                  className="px-2 py-1 text-[10px] border border-emerald-800 text-emerald-400 hover:bg-emerald-950/30 transition"
                >
                  Merge
                </button>
                <button
                  onClick={() => handleDismissGroup(group)}
                  className="px-2 py-1 text-[10px] border border-zinc-700 text-zinc-500 hover:text-white transition"
                >
                  Dismiss
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Items Table */}
      <div className="border border-zinc-800" data-testid="items-table">
        {/* Header */}
        <div className="flex items-center gap-3 px-4 py-2 border-b border-zinc-800 text-[10px] text-zinc-600 uppercase tracking-wider">
          <input
            type="checkbox"
            checked={selectedItems.size === items.length && items.length > 0}
            onChange={toggleSelectAll}
            className="accent-white"
          />
          <span className="w-16">Image</span>
          <span className="flex-1">Title / Description</span>
          <span className="w-20 text-right">Price</span>
          <span className="w-24">Category</span>
          <span className="w-16 text-center">Conf.</span>
          <span className="w-20">Source</span>
          <span className="w-20 text-center">Status</span>
          <span className="w-16">Actions</span>
        </div>

        {/* Empty state */}
        {items.length === 0 && (
          <div className="p-8 text-center text-zinc-600 text-sm">
            No items yet. Upload product photos to get started.
          </div>
        )}

        {/* Item rows */}
        {items.map(item => {
          const img = item.images?.[0];
          const imgUrl = img ? `${IMAGE_BASE}/${batchId}/${img.filename}` : null;
          const isExpanded = expandedItem === item.id;

          return (
            <div key={item.id} className="border-b border-zinc-800/50 last:border-0">
              <div
                className="flex items-center gap-3 px-4 py-3 hover:bg-zinc-900/30 transition cursor-pointer"
                onClick={() => setExpandedItem(isExpanded ? null : item.id)}
                data-testid={`item-row-${item.id}`}
              >
                <input
                  type="checkbox"
                  checked={selectedItems.has(item.id)}
                  onChange={(e) => { e.stopPropagation(); toggleSelect(item.id); }}
                  className="accent-white"
                />
                {/* Thumbnail — shows multiple for merged items */}
                <div className="w-16 flex-shrink-0">
                  {item.images?.length > 1 ? (
                    <div className="relative w-16 h-16">
                      {item.images.slice(0, 3).map((img, idx) => {
                        const url = `${IMAGE_BASE}/${batchId}/${img.filename}`;
                        return (
                          <img
                            key={idx}
                            src={url}
                            alt=""
                            className="absolute w-12 h-12 object-cover border border-zinc-800"
                            style={{ left: idx * 6, top: idx * 6, zIndex: 3 - idx }}
                            loading="lazy"
                          />
                        );
                      })}
                      {item.images.length > 3 && (
                        <span className="absolute bottom-0 right-0 text-[9px] bg-purple-900 text-purple-300 px-1 rounded z-10">+{item.images.length - 3}</span>
                      )}
                      <span className="absolute top-0 right-0 text-[9px] bg-purple-900/80 text-purple-300 px-1 rounded z-10">{item.images.length}</span>
                    </div>
                  ) : (
                    <div className="w-16 h-16 bg-zinc-900 border border-zinc-800 overflow-hidden">
                      {imgUrl ? (
                        <img src={imgUrl} alt="" className="w-full h-full object-cover" loading="lazy" />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-zinc-700"><Upload className="w-4 h-4" /></div>
                      )}
                    </div>
                  )}
                </div>
                {/* Title + desc */}
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-white truncate">
                    {item.draft_title || <span className="text-zinc-600 italic">Pending analysis...</span>}
                    {item.title_refined && <span className="ml-1.5 text-[9px] text-amber-500 border border-amber-800/50 px-1 py-0.5 uppercase">refined</span>}
                  </div>
                  {item.short_description && <div className="text-xs text-zinc-500 truncate mt-0.5">{item.short_description}</div>}
                  {item.confidence_flag === 'weak' && (
                    <div className="flex items-center gap-1 mt-1 text-[10px] text-red-400">
                      <AlertTriangle className="w-3 h-3" /> Weak recognition — review needed
                    </div>
                  )}
                </div>
                {/* Price */}
                <div className="w-20 text-right">
                  {item.retail_price ? (
                    <div className="text-sm text-emerald-400">${item.retail_price.toFixed(2)}</div>
                  ) : item.unit_cost ? (
                    <div className="text-sm text-zinc-400">${item.unit_cost.toFixed(2)}</div>
                  ) : (
                    <div className="text-xs text-zinc-600">—</div>
                  )}
                </div>
                {/* Category */}
                <div className="w-24 text-xs text-zinc-400 truncate">{item.category_suggestion || '—'}</div>
                {/* Confidence */}
                <div className={`w-16 text-center text-xs ${confColor(item.confidence_flag)}`}>
                  {item.confidence_flag === 'pending' ? '...' : `${Math.round(item.confidence * 100)}%`}
                </div>
                {/* Source */}
                <div className="w-20 text-xs text-zinc-500 truncate">{item.source_vendor || batch.source_vendor || '—'}</div>
                {/* Status */}
                <div className="w-20 text-center">
                  <span className={`text-[10px] border px-1.5 py-0.5 uppercase tracking-wider ${statusBadge(item.status)}`}>
                    {item.status}
                  </span>
                </div>
                {/* Expand */}
                <div className="w-16 flex justify-end">
                  {isExpanded ? <ChevronUp className="w-4 h-4 text-zinc-500" /> : <ChevronDown className="w-4 h-4 text-zinc-600" />}
                </div>
              </div>

              {/* Expanded Detail */}
              {isExpanded && (
                <div className="px-4 pb-4 pt-1 bg-zinc-900/20 border-t border-zinc-800/50" data-testid={`item-detail-${item.id}`}>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {/* Image + Vision */}
                    <div>
                      {item.images?.length > 1 ? (
                        <div className="grid grid-cols-3 gap-1 mb-2">
                          {item.images.map((img, idx) => (
                            <img key={idx} src={`${IMAGE_BASE}/${batchId}/${img.filename}`} alt="" className="w-full h-20 object-cover border border-zinc-800" />
                          ))}
                        </div>
                      ) : imgUrl ? (
                        <img src={imgUrl} alt="" className="w-full max-h-48 object-contain border border-zinc-800 mb-2" />
                      ) : null}
                      {img && <div className="text-[10px] text-zinc-600">File: {img.original_name}{item.images?.length > 1 ? ` (+${item.images.length - 1} more)` : ''}</div>}
                      {item.vision_analysis?.notable_features && (
                        <div className="mt-2 text-xs text-zinc-500">
                          <span className="text-zinc-600">Features:</span> {item.vision_analysis.notable_features}
                        </div>
                      )}
                      {item.grouped_note_ref && (
                        <div className="mt-2 text-[10px] text-zinc-600">Note: {item.grouped_note_ref}</div>
                      )}
                      {item.images?.length > 1 && (
                        <div className="flex gap-2 mt-2">
                          <button
                            onClick={() => handleRefineTitle(item.id)}
                            disabled={refiningTitle === item.id}
                            className="px-2 py-1 text-[10px] border border-amber-700 text-amber-400 hover:bg-amber-950/30 disabled:opacity-50 transition"
                            data-testid={`refine-title-${item.id}`}
                          >
                            {refiningTitle === item.id ? 'Refining...' : 'Refine Title'}
                          </button>
                          <button
                            onClick={() => handleSplit(item.id)}
                            className="px-2 py-1 text-[10px] border border-zinc-700 text-zinc-400 hover:text-white hover:border-zinc-500 transition"
                            data-testid={`split-${item.id}`}
                          >
                            Split into {item.images.length} items
                          </button>
                        </div>
                      )}
                    </div>
                    {/* Editable fields */}
                    <div className="space-y-2">
                      <div>
                        <label className="text-[10px] text-zinc-600 uppercase">Title</label>
                        <input
                          key={`title-${item.id}-${item.draft_title}`}
                          defaultValue={item.draft_title}
                          onBlur={e => handleItemUpdate(item.id, 'draft_title', e.target.value)}
                          className="w-full bg-zinc-900 border border-zinc-700 text-white text-xs px-2 py-1.5 outline-none focus:border-zinc-500"
                        />
                      </div>
                      <div>
                        <label className="text-[10px] text-zinc-600 uppercase">Price</label>
                        <input
                          type="number"
                          step="0.01"
                          defaultValue={item.retail_price || ''}
                          onBlur={e => handleItemUpdate(item.id, 'retail_price', parseFloat(e.target.value) || null)}
                          className="w-full bg-zinc-900 border border-zinc-700 text-white text-xs px-2 py-1.5 outline-none focus:border-zinc-500"
                        />
                      </div>
                      <div>
                        <label className="text-[10px] text-zinc-600 uppercase">Category</label>
                        <input
                          defaultValue={item.category_suggestion}
                          onBlur={e => handleItemUpdate(item.id, 'category_suggestion', e.target.value)}
                          className="w-full bg-zinc-900 border border-zinc-700 text-white text-xs px-2 py-1.5 outline-none focus:border-zinc-500"
                        />
                      </div>
                      <div className="flex gap-2 pt-2">
                        <button onClick={() => handleItemUpdate(item.id, 'status', 'approved')} className="px-3 py-1 text-xs border border-emerald-800 text-emerald-400 hover:bg-emerald-950/30">Approve</button>
                        <button onClick={() => handleItemUpdate(item.id, 'status', 'skipped')} className="px-3 py-1 text-xs border border-red-800 text-red-400 hover:bg-red-950/30">Skip</button>
                      </div>
                    </div>
                    {/* Destination Packs */}
                    <div>
                      {item.destination_packs && Object.keys(item.destination_packs).length > 0 ? (
                        <div className="space-y-3">
                          {Object.entries(item.destination_packs).map(([dest, text]) => (
                            <div key={dest}>
                              <div className="flex items-center justify-between mb-1">
                                <span className="text-[10px] text-zinc-500 uppercase tracking-wider">
                                  {dest === 'offerup' ? 'OfferUp' : dest === 'facebook' ? 'FB Marketplace' : 'Website'}
                                </span>
                                <button
                                  onClick={() => copyToClipboard(text)}
                                  className="text-zinc-600 hover:text-white transition"
                                  title="Copy to clipboard"
                                >
                                  <Copy className="w-3 h-3" />
                                </button>
                              </div>
                              <pre className="text-[10px] text-zinc-400 bg-zinc-950 border border-zinc-800 p-2 whitespace-pre-wrap max-h-32 overflow-y-auto">{text}</pre>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="text-xs text-zinc-600 italic">Generate packs to see output here</div>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Destination Packs Panel */}
      {showPacks && packs && (
        <div className="mt-8 border border-amber-900/40 bg-amber-950/10 p-6" data-testid="packs-panel">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm text-amber-400 font-medium">Destination Packs — {packs.batch_name}</h2>
            <button onClick={() => setShowPacks(false)} className="text-zinc-500 hover:text-white"><X className="w-4 h-4" /></button>
          </div>

          {/* Website Page Pack */}
          {packs.website_page_pack && (
            <div className="mb-6">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-zinc-500 uppercase tracking-wider">Website Sale Page</span>
                <button onClick={() => copyToClipboard(packs.website_page_pack)} className="flex items-center gap-1 text-xs text-zinc-500 hover:text-white transition">
                  <Copy className="w-3 h-3" /> Copy
                </button>
              </div>
              <pre className="text-xs text-zinc-300 bg-zinc-950 border border-zinc-800 p-4 whitespace-pre-wrap max-h-64 overflow-y-auto" data-testid="website-pack">
                {packs.website_page_pack}
              </pre>
            </div>
          )}

          {/* Per-item packs */}
          <div className="space-y-4">
            {packs.items?.map(item => (
              <details key={item.id} className="border border-zinc-800">
                <summary className="px-4 py-2 text-sm text-zinc-300 cursor-pointer hover:bg-zinc-900/30">
                  {item.draft_title} {item.retail_price ? `— $${item.retail_price.toFixed(2)}` : ''}
                </summary>
                <div className="px-4 pb-3 grid grid-cols-1 md:grid-cols-3 gap-3">
                  {Object.entries(item.destination_packs || {}).map(([dest, text]) => (
                    <div key={dest}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[10px] text-zinc-500 uppercase">
                          {dest === 'offerup' ? 'OfferUp' : dest === 'facebook' ? 'FB Marketplace' : 'Website'}
                        </span>
                        <button onClick={() => copyToClipboard(text)} className="text-zinc-600 hover:text-white"><Copy className="w-3 h-3" /></button>
                      </div>
                      <pre className="text-[10px] text-zinc-400 bg-zinc-950 border border-zinc-800 p-2 whitespace-pre-wrap">{text}</pre>
                    </div>
                  ))}
                </div>
              </details>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
