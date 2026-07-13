import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import {
  ArrowLeft, Plus, Wand2, FileDown, Trash2, RefreshCw,
  AlertTriangle, CheckCircle, Clock, Eye, Edit3,
  ClipboardPaste, Package, ChevronDown, ChevronUp, X,
  Upload, Copy,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const SOURCE_TYPES = [
  { value: 'pasted_order', label: 'Pasted Order/Cart' },
  { value: 'email_text', label: 'Email Text' },
  { value: 'csv_upload', label: 'CSV/TSV Upload' },
  { value: 'pdf_upload', label: 'PDF Upload' },
  { value: 'manual_entry', label: 'Manual Entry' },
];

const STATUS_CONFIG = {
  needs_info: { label: 'Needs Info', color: 'text-orange-400 bg-orange-900/30 border-orange-800', icon: AlertTriangle },
  in_review: { label: 'In Review', color: 'text-amber-400 bg-amber-900/30 border-amber-800', icon: Eye },
  ready: { label: 'Ready', color: 'text-emerald-400 bg-emerald-900/30 border-emerald-800', icon: CheckCircle },
};

export default function IntakeSession() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showExtract, setShowExtract] = useState(false);
  const [showAddItem, setShowAddItem] = useState(false);
  const [selectedItem, setSelectedItem] = useState(null);
  const [generating, setGenerating] = useState(null);
  const [batchGenerating, setBatchGenerating] = useState(false);
  const fileInputRef = React.useRef(null);
  const pdfInputRef = React.useRef(null);
  const [pdfUploading, setPdfUploading] = useState(false);
  const [pdfResult, setPdfResult] = useState(null);
  const [batchResult, setBatchResult] = useState(null);
  const [exportResult, setExportResult] = useState(null);
  const [markingReady, setMarkingReady] = useState(false);
  const [costNotes, setCostNotes] = useState('');
  const [costNotesResult, setCostNotesResult] = useState(null);
  const [applyingCostNotes, setApplyingCostNotes] = useState(false);
  const [showCostNotes, setShowCostNotes] = useState(false);
  const [checkedItems, setCheckedItems] = useState(new Set());
  const [bulkAction, setBulkAction] = useState(null);
  const [bulkValue, setBulkValue] = useState('');
  const [applyingBulk, setApplyingBulk] = useState(false);

  const fetchSession = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/intake/sessions/${sessionId}`, { withCredentials: true });
      setSession(res.data);
      if (res.data.cost_notes) setCostNotes(prev => prev || res.data.cost_notes);
    } catch (err) {
      console.error('Failed to fetch session:', err);
    }
    setLoading(false);
  }, [sessionId]);

  useEffect(() => { fetchSession(); }, [fetchSession]);

  const handleDeleteSession = async () => {
    if (!window.confirm('Delete this session and all items?')) return;
    try {
      await axios.delete(`${API}/intake/sessions/${sessionId}`, { withCredentials: true });
      navigate('/intake');
    } catch (err) {
      alert(err.response?.data?.detail || 'Delete failed');
    }
  };

  const handleGenerateItem = async (itemId) => {
    setGenerating(itemId);
    try {
      const res = await axios.post(`${API}/intake/items/${itemId}/generate`, {}, { withCredentials: true });
      setSession(prev => ({
        ...prev,
        items: prev.items.map(i => i.id === itemId ? res.data : i),
      }));
      if (selectedItem?.id === itemId) setSelectedItem(res.data);
    } catch (err) {
      alert(err.response?.data?.detail || 'Generation failed');
    }
    setGenerating(null);
  };

  const handleBatchGenerate = async () => {
    const needsGen = session?.items?.filter(it => !it.short_description && (it.source_title || it.clean_title)).length || 0;
    if (needsGen === 0) {
      alert('No items need generation. All items already have descriptions.');
      return;
    }
    if (!window.confirm(`Generate listings for ${needsGen} items? This will use LLM credits and may take a few minutes.`)) return;
    setBatchGenerating(true);
    setBatchResult(null);
    try {
      const res = await axios.post(
        `${API}/intake/sessions/${sessionId}/generate-all`, {},
        { withCredentials: true, timeout: 600000 }
      );
      setBatchResult(res.data);
      await fetchSession();
    } catch (err) {
      alert(err.response?.data?.detail || 'Batch generation failed');
    }
    setBatchGenerating(false);
  };

  const handleDeleteItem = async (itemId) => {
    if (!window.confirm('Delete this item?')) return;
    try {
      await axios.delete(`${API}/intake/items/${itemId}`, { withCredentials: true });
      if (selectedItem?.id === itemId) setSelectedItem(null);
      await fetchSession();
    } catch (err) {
      alert(err.response?.data?.detail || 'Delete failed');
    }
  };

  const handleExport = async () => {
    try {
      const res = await axios.get(`${API}/intake/sessions/${sessionId}/export`, {
        withCredentials: true,
        responseType: 'blob',
      });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = res.headers['content-disposition']?.split('filename=')[1] || 'export.csv';
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert(err.response?.data?.detail || 'Export failed. Make sure you have Ready items.');
    }
  };

  const handleMarkReadyExport = async () => {
    const reviewCount = items.filter(it => it.status === 'in_review').length;
    const readyCount = items.filter(it => it.status === 'ready').length;
    const msg = reviewCount > 0
      ? `Re-validate all items and export fresh WooCommerce CSV?\n\n${reviewCount} in review (will be validated)\n${readyCount} already ready (will be re-checked)\n\nEligible items will be exported. Held-back items stay in review.`
      : `Re-export ${readyCount} ready items as fresh WooCommerce CSV?\n\nAll items will be re-validated to catch any edits.`;
    if (!window.confirm(msg)) return;
    setMarkingReady(true);
    setExportResult(null);
    try {
      const res = await axios.post(
        `${API}/intake/sessions/${sessionId}/mark-ready-export`, {},
        { withCredentials: true, timeout: 30000 }
      );
      setExportResult(res.data);
      if (res.data.csv_data && res.data.exported > 0) {
        const blob = new Blob([res.data.csv_data], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = res.data.csv_filename || 'woo-import.csv';
        a.click();
        window.URL.revokeObjectURL(url);
      }
      await fetchSession();
    } catch (err) {
      alert(err.response?.data?.detail || 'Export failed');
    }
    setMarkingReady(false);
  };

  const handleDownloadWoo = async () => {
    try {
      const res = await axios.get(`${API}/intake/sessions/${sessionId}/export-woo`, {
        withCredentials: true,
        responseType: 'blob',
      });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = res.headers['content-disposition']?.split('filename=')[1] || 'woo-import.csv';
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert(err.response?.data?.detail || 'WooCommerce export failed. Make sure you have Ready items.');
    }
  };

  const handleApplyCostNotes = async () => {
    if (!costNotes.trim()) return;
    setApplyingCostNotes(true);
    setCostNotesResult(null);
    try {
      const res = await axios.post(
        `${API}/intake/sessions/${sessionId}/apply-cost-notes`,
        { cost_notes: costNotes },
        { withCredentials: true, timeout: 60000 }
      );
      setCostNotesResult(res.data);
      await fetchSession();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to apply cost notes');
    }
    setApplyingCostNotes(false);
  };

  const handleBulkApply = async (action, value) => {
    if (checkedItems.size === 0) return;
    setApplyingBulk(true);
    try {
      const res = await axios.post(
        `${API}/intake/sessions/${sessionId}/bulk-action`,
        { item_ids: Array.from(checkedItems), action, value },
        { withCredentials: true }
      );
      const d = res.data;
      const msg = `Updated ${d.updated} of ${d.total_selected} items.${d.skipped > 0 ? ` ${d.skipped} skipped.` : ''}`;
      if (d.skipped_items?.length > 0) {
        const reasons = d.skipped_items.slice(0, 3).map(s => `  ${s.title || s.id?.slice(0,8)}: ${s.reason}`).join('\n');
        alert(`${msg}\n\nSkipped:\n${reasons}`);
      }
      setCheckedItems(new Set());
      setBulkAction(null);
      setBulkValue('');
      await fetchSession();
    } catch (err) {
      alert(err.response?.data?.detail || 'Bulk action failed');
    }
    setApplyingBulk(false);
  };

  const toggleCheck = (itemId, e) => {
    e.stopPropagation();
    setCheckedItems(prev => {
      const next = new Set(prev);
      if (next.has(itemId)) next.delete(itemId); else next.add(itemId);
      return next;
    });
  };

  const toggleCheckAll = () => {
    if (checkedItems.size === items.length) {
      setCheckedItems(new Set());
    } else {
      setCheckedItems(new Set(items.map(i => i.id)));
    }
  };

  const handleCsvUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);
    try {
      const res = await axios.post(`${API}/intake/sessions/${sessionId}/upload-csv`, formData, {
        withCredentials: true,
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      alert(`Uploaded ${res.data.uploaded_count} items from ${res.data.filename}`);
      await fetchSession();
    } catch (err) {
      alert(err.response?.data?.detail || 'Upload failed');
    }
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handlePdfUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setPdfUploading(true);
    setPdfResult(null);
    const formData = new FormData();
    formData.append('file', file);
    try {
      const res = await axios.post(`${API}/intake/sessions/${sessionId}/upload-pdf`, formData, {
        withCredentials: true,
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 120000,
      });
      if (res.data.status === 'processing') {
        // Vision-based PDF — poll for completion
        setPdfResult({ ...res.data, polling: true });
        const jobId = res.data.job_id;
        let attempts = 0;
        const maxAttempts = 120; // ~4 minutes at 2s intervals
        const pollInterval = setInterval(async () => {
          attempts++;
          try {
            const pollRes = await axios.get(`${API}/intake/pdf-jobs/${jobId}`, { withCredentials: true });
            if (pollRes.data.status === 'completed') {
              clearInterval(pollInterval);
              setPdfResult({ ...pollRes.data, polling: false });
              setPdfUploading(false);
              await fetchSession();
            } else if (pollRes.data.status === 'failed') {
              clearInterval(pollInterval);
              setPdfResult({ ...pollRes.data, polling: false });
              setPdfUploading(false);
              alert(`Vision PDF processing failed: ${pollRes.data.error || 'Unknown error'}`);
            } else if (attempts >= maxAttempts) {
              clearInterval(pollInterval);
              setPdfResult({ status: 'timeout', message: 'Processing timed out. Refresh the page to check if items were imported.' });
              setPdfUploading(false);
            }
          } catch {
            // Polling error — keep trying
          }
        }, 2000);
      } else {
        // Text-based PDF — completed synchronously
        setPdfResult(res.data);
        await fetchSession();
        setPdfUploading(false);
      }
    } catch (err) {
      alert(err.response?.data?.detail || 'PDF upload failed');
      setPdfUploading(false);
    }
    if (pdfInputRef.current) pdfInputRef.current.value = '';
  };

  const handleCheckDuplicates = async (itemId) => {
    try {
      const res = await axios.get(`${API}/intake/items/${itemId}/check-duplicates`, { withCredentials: true });
      if (res.data.count > 0) {
        alert(`Found ${res.data.count} potential duplicate(s):\n${res.data.duplicate_flags.map(f => `- ${f.match_title} (${f.type})`).join('\n')}`);
      } else {
        alert('No duplicates found.');
      }
      await fetchSession();
    } catch (err) {
      console.error('Duplicate check failed:', err);
    }
  };

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[50vh]">
        <div className="text-zinc-500 text-sm animate-pulse">Loading session...</div>
      </div>
    );
  }

  if (!session) {
    return (
      <div className="p-8 text-center">
        <p className="text-zinc-500">Session not found.</p>
        <button onClick={() => navigate('/intake')} className="mt-4 text-sm text-white underline">Back</button>
      </div>
    );
  }

  const items = session.items || [];

  return (
    <div className="p-8 max-w-[1400px] mx-auto" data-testid="intake-session">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => navigate('/intake')} className="p-2 text-zinc-500 hover:text-white transition-colors" data-testid="back-btn">
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div className="flex-1 min-w-0">
          <h1 className="text-2xl font-['Outfit'] font-light text-white tracking-tight">
            {session.source_store}
            {session.order_id && <span className="text-zinc-500 ml-2">#{session.order_id}</span>}
          </h1>
          <div className="flex items-center gap-3 mt-1 text-xs text-zinc-500">
            {session.purchase_date && <span>{session.purchase_date}</span>}
            <span>{items.length} items</span>
            {session.notes && <span>&middot; {session.notes}</span>}
          </div>
        </div>
      </div>

      {/* Action Bar */}
      <div className="flex items-center gap-2 mb-6 flex-wrap" data-testid="session-actions">
        <button
          onClick={() => setShowExtract(true)}
          className="flex items-center gap-2 px-4 py-2 bg-white text-black text-sm font-medium hover:bg-zinc-200 transition-colors"
          data-testid="paste-text-btn"
        >
          <ClipboardPaste className="w-4 h-4" /> Paste & Extract
        </button>
        <button
          onClick={() => setShowAddItem(true)}
          className="flex items-center gap-2 px-3 py-2 border border-zinc-700 text-sm text-zinc-300 hover:border-zinc-500 transition-colors"
          data-testid="add-item-btn"
        >
          <Plus className="w-3.5 h-3.5" /> Add Manually
        </button>
        <button
          onClick={() => fileInputRef.current?.click()}
          className="flex items-center gap-2 px-3 py-2 border border-zinc-700 text-sm text-zinc-300 hover:border-zinc-500 transition-colors"
          data-testid="upload-csv-btn"
        >
          <Upload className="w-3.5 h-3.5" /> Upload CSV/TSV
        </button>
        <button
          onClick={() => pdfInputRef.current?.click()}
          disabled={pdfUploading}
          className="flex items-center gap-2 px-3 py-2 border border-zinc-700 text-sm text-zinc-300 hover:border-zinc-500 transition-colors disabled:opacity-40"
          data-testid="upload-pdf-btn"
        >
          {pdfUploading ? (
            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Upload className="w-3.5 h-3.5" />
          )}
          {pdfUploading ? 'Processing PDF...' : 'Upload PDF'}
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,.tsv,.txt"
          onChange={handleCsvUpload}
          className="hidden"
          data-testid="csv-file-input"
        />
        <input
          ref={pdfInputRef}
          type="file"
          accept=".pdf"
          onChange={handlePdfUpload}
          className="hidden"
          data-testid="pdf-file-input"
        />
        {items.length > 0 && (
          <>
            <button
              onClick={handleBatchGenerate}
              disabled={batchGenerating}
              className="flex items-center gap-2 px-3 py-2 border border-zinc-700 text-sm text-zinc-300 hover:border-zinc-500 transition-colors disabled:opacity-40"
              data-testid="batch-generate-btn"
            >
              <Wand2 className={`w-3.5 h-3.5 ${batchGenerating ? 'animate-spin' : ''}`} />
              {batchGenerating ? 'Generating All...' : 'Generate All Listings'}
            </button>
            <button
              onClick={handleMarkReadyExport}
              disabled={markingReady}
              className="flex items-center gap-2 px-3 py-2 border border-emerald-800 text-sm text-emerald-400 hover:bg-emerald-900/20 transition-colors disabled:opacity-40"
              data-testid="mark-ready-export-btn"
            >
              {markingReady ? (
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <CheckCircle className="w-3.5 h-3.5" />
              )}
              {markingReady ? 'Exporting...' : items.some(it => it.status === 'in_review')
                ? 'Mark Ready & Export'
                : `Re-export Woo CSV (${items.filter(it => it.status === 'ready').length})`}
            </button>
            <button
              onClick={handleExport}
              className="flex items-center gap-2 px-3 py-2 border border-zinc-700 text-sm text-zinc-300 hover:border-zinc-500 transition-colors"
              data-testid="export-btn"
            >
              <FileDown className="w-3.5 h-3.5" /> Export CSV
            </button>
            <button
              onClick={() => setShowCostNotes(!showCostNotes)}
              className={`flex items-center gap-2 px-3 py-2 border text-sm transition-colors ${showCostNotes ? 'border-amber-700 text-amber-400 bg-amber-900/10' : 'border-zinc-700 text-zinc-300 hover:border-zinc-500'}`}
              data-testid="cost-notes-toggle-btn"
            >
              <Edit3 className="w-3.5 h-3.5" /> Cost Notes
            </button>
          </>
        )}
        <div className="flex-1" />
        <button
          onClick={handleDeleteSession}
          className="flex items-center gap-2 px-3 py-2 text-sm text-red-500/60 hover:text-red-400 transition-colors"
          data-testid="delete-session-btn"
        >
          <Trash2 className="w-3.5 h-3.5" /> Delete Session
        </button>
      </div>

      {/* Status Summary */}
      {items.length > 0 && (
        <div className="flex gap-4 mb-6">
          {Object.entries(STATUS_CONFIG).map(([key, conf]) => {
            const count = items.filter(i => i.status === key).length;
            return (
              <div key={key} className="flex items-center gap-2 text-xs">
                <conf.icon className={`w-3.5 h-3.5 ${conf.color.split(' ')[0]}`} />
                <span className="text-zinc-400">{conf.label}: <span className="text-white">{count}</span></span>
              </div>
            );
          })}
        </div>
      )}

      {/* Cost Notes Panel */}
      {showCostNotes && (
        <div className="mb-6 border border-amber-900/30 bg-amber-950/10 p-4" data-testid="cost-notes-panel">
          <div className="flex items-center justify-between mb-2">
            <div className="text-sm text-amber-400 font-medium">Founder Cost Notes</div>
            <button onClick={() => setShowCostNotes(false)} className="text-zinc-500 hover:text-white">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
          <p className="text-[10px] text-zinc-500 mb-2">
            Write informal cost/pricing notes. Examples: "this group cost $25 and retails at $55" or "panties cost $4.75 each, sell for $12.99"
          </p>
          <textarea
            value={costNotes}
            onChange={(e) => setCostNotes(e.target.value)}
            placeholder={"e.g. this group was $25 and retails at $55\nthese are panties and cost $4.75 and retail at $12.99\nlingerie sets cost $8, sell for $24.99"}
            className="w-full bg-zinc-900 border border-zinc-700 text-sm text-zinc-200 p-3 resize-y min-h-[80px] max-h-[200px] placeholder-zinc-600 focus:border-amber-700 focus:outline-none"
            rows={3}
            data-testid="cost-notes-textarea"
          />
          <div className="mt-2 flex items-center gap-3">
            <button
              onClick={handleApplyCostNotes}
              disabled={applyingCostNotes || !costNotes.trim()}
              className="px-3 py-1.5 border border-amber-700 text-xs text-amber-400 hover:bg-amber-900/20 disabled:opacity-40 flex items-center gap-1.5"
              data-testid="apply-cost-notes-btn"
            >
              {applyingCostNotes ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Wand2 className="w-3 h-3" />}
              {applyingCostNotes ? 'Parsing & Applying...' : 'Parse & Apply'}
            </button>
            <span className="text-[10px] text-zinc-600">Uses LLM to match notes to items and update costs</span>
          </div>
          {costNotesResult && (
            <div className="mt-3 border-t border-zinc-800 pt-3">
              <div className="text-xs text-zinc-400 mb-1">
                Applied <span className="text-amber-400">{costNotesResult.applied}</span> updates from <span className="text-zinc-300">{costNotesResult.rules_parsed}</span> parsed rules
              </div>
              {costNotesResult.matches?.map((m, i) => (
                <div key={i} className="text-[10px] text-zinc-500 mt-1">
                  <span className={m.confidence === 'high' ? 'text-emerald-400' : m.confidence === 'medium' ? 'text-blue-400' : 'text-amber-400'}>
                    [{m.confidence}]
                  </span>
                  {' '}&quot;{m.note}&quot; → {m.matched_items} items
                  {m.unit_cost != null && <> | cost: ${m.unit_cost}</>}
                  {m.retail_price != null && <> | retail: ${m.retail_price}</>}
                  {m.reason && <span className="text-zinc-600"> ({m.reason})</span>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* PDF Upload Result Summary */}
      {pdfResult && (
        <div className={`mb-6 border p-4 ${
          pdfResult.polling ? 'border-amber-900/40 bg-amber-950/20' :
          pdfResult.status === 'failed' ? 'border-red-900/40 bg-red-950/20' :
          'border-emerald-900/40 bg-emerald-950/20'
        }`} data-testid="pdf-result-banner">
          {pdfResult.polling ? (
            <>
              <div className="flex items-center gap-2 mb-2">
                <div className="w-3 h-3 border-2 border-amber-400 border-t-transparent rounded-full animate-spin" />
                <div className="text-sm text-amber-400 font-medium">
                  Vision AI Processing — {pdfResult.total_pages} pages
                </div>
              </div>
              <div className="text-xs text-zinc-400">
                Image-based PDF detected. Extracting products via Vision AI... This typically takes 2-3 minutes.
              </div>
            </>
          ) : pdfResult.status === 'failed' ? (
            <div className="flex items-center justify-between">
              <div className="text-sm text-red-400">PDF Processing Failed: {pdfResult.error || 'Unknown error'}</div>
              <button onClick={() => setPdfResult(null)} className="text-zinc-500 hover:text-white">
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between mb-2">
                <div className="text-sm text-emerald-400 font-medium">
                  PDF Processed: {pdfResult.filename || 'Complete'}
                  {pdfResult.extraction_method === 'vision_llm' && (
                    <span className="ml-2 text-[10px] text-amber-400 border border-amber-800/40 px-1.5 py-0.5 rounded">VISION AI</span>
                  )}
                </div>
                <button onClick={() => setPdfResult(null)} className="text-zinc-500 hover:text-white">
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                <div>
                  <span className="text-zinc-500">Pages scanned</span>
                  <div className="text-white">{pdfResult.total_pages}{pdfResult.product_pages != null ? ` (${pdfResult.product_pages} with products)` : ''}</div>
                </div>
                <div>
                  <span className="text-zinc-500">Raw items found</span>
                  <div className="text-white">{pdfResult.raw_item_count}</div>
                </div>
                <div>
                  <span className="text-zinc-500">Duplicates merged</span>
                  <div className="text-amber-400">{pdfResult.duplicate_count}</div>
                </div>
                <div>
                  <span className="text-zinc-500">Unique items imported</span>
                  <div className="text-emerald-400 font-medium">{pdfResult.uploaded_count}</div>
                </div>
              </div>
              {pdfResult.detected_vendor && (
                <div className="mt-2 text-xs text-zinc-500">Detected vendor: <span className="text-zinc-300">{pdfResult.detected_vendor}</span></div>
              )}
              {pdfResult.duplicate_log?.length > 0 && (
                <details className="mt-2">
                  <summary className="text-xs text-zinc-500 cursor-pointer hover:text-zinc-300">
                    View duplicate merge log ({pdfResult.duplicate_log.length} entries)
                  </summary>
                  <div className="mt-1 max-h-32 overflow-y-auto text-[10px] text-zinc-500 space-y-0.5">
                    {pdfResult.duplicate_log.map((d, i) => (
                      <div key={i}>{d.sku ? `SKU ${d.sku}` : d.title?.slice(0, 40)} (page {d.page}) — {d.action}{d.match_type ? ` [${d.match_type}]` : ''}</div>
                    ))}
                  </div>
                </details>
              )}
            </>
          )}
        </div>
      )}

      {/* Batch Generation Result Summary */}
      {batchResult && (
        <div className="mb-6 border border-blue-900/40 bg-blue-950/20 p-4" data-testid="batch-result-banner">
          <div className="flex items-center justify-between mb-2">
            <div className="text-sm text-blue-400 font-medium">
              Batch Generation Complete
            </div>
            <button onClick={() => setBatchResult(null)} className="text-zinc-500 hover:text-white">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
            <div>
              <span className="text-zinc-500">Total processed</span>
              <div className="text-white">{batchResult.total}</div>
            </div>
            <div>
              <span className="text-zinc-500">Generated</span>
              <div className="text-emerald-400 font-medium">{batchResult.generated}</div>
            </div>
            <div>
              <span className="text-zinc-500">Low confidence (flagged)</span>
              <div className={batchResult.flagged > 0 ? "text-amber-400" : "text-zinc-400"}>{batchResult.flagged}</div>
            </div>
            <div>
              <span className="text-zinc-500">Failed</span>
              <div className={batchResult.failed > 0 ? "text-red-400" : "text-zinc-400"}>{batchResult.failed}</div>
            </div>
          </div>
          {batchResult.results?.length > 0 && (
            <details className="mt-2">
              <summary className="text-xs text-zinc-500 cursor-pointer hover:text-zinc-300">
                View per-item results ({batchResult.results.length} items)
              </summary>
              <div className="mt-1 max-h-40 overflow-y-auto text-[10px] space-y-0.5">
                {batchResult.results.map((r, i) => (
                  <div key={i} className={r.status === 'failed' ? 'text-red-400' : r.confidence < 0.5 ? 'text-amber-400' : 'text-zinc-400'}>
                    {r.status === 'generated' ? (
                      <>{r.clean_title?.slice(0, 50)} — {r.category} — conf: {(r.confidence * 100).toFixed(0)}% → {r.new_status}</>
                    ) : (
                      <>{r.source_title?.slice(0, 50)} — FAILED: {r.error}</>
                    )}
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      )}

      {/* Export Result Summary */}
      {exportResult && (
        <div className="mb-6 border border-emerald-900/40 bg-emerald-950/20 p-4" data-testid="export-result-banner">
          <div className="flex items-center justify-between mb-2">
            <div className="text-sm text-emerald-400 font-medium">
              WooCommerce Export Complete
            </div>
            <button onClick={() => setExportResult(null)} className="text-zinc-500 hover:text-white">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
            <div>
              <span className="text-zinc-500">Exported (ready)</span>
              <div className="text-emerald-400 font-medium">{exportResult.exported}</div>
            </div>
            <div>
              <span className="text-zinc-500">Newly promoted</span>
              <div className="text-blue-400">{exportResult.newly_ready || 0}</div>
            </div>
            <div>
              <span className="text-zinc-500">Held back</span>
              <div className={exportResult.held_back > 0 ? "text-amber-400" : "text-zinc-400"}>{exportResult.held_back}</div>
            </div>
            <div>
              <span className="text-zinc-500">Demoted (failed re-check)</span>
              <div className={exportResult.demoted > 0 ? "text-red-400" : "text-zinc-400"}>{exportResult.demoted || 0}</div>
            </div>
          </div>
          {exportResult.exported > 0 && (
            <div className="mt-3 flex items-center gap-3">
              <button
                onClick={handleDownloadWoo}
                className="text-xs px-3 py-1.5 border border-emerald-700 text-emerald-400 hover:bg-emerald-900/30 flex items-center gap-1.5"
                data-testid="download-woo-csv-btn"
              >
                <FileDown className="w-3 h-3" /> Download WooCommerce CSV ({exportResult.exported} items)
              </button>
              <span className="text-[10px] text-zinc-600">Published=0 (draft) — safe to import</span>
            </div>
          )}
          {exportResult.demoted_items?.length > 0 && (
            <details className="mt-2">
              <summary className="text-xs text-red-400/80 cursor-pointer hover:text-red-300">
                {exportResult.demoted} items demoted after re-validation
              </summary>
              <div className="mt-1 max-h-32 overflow-y-auto text-[10px] space-y-0.5">
                {exportResult.demoted_items.map((d, i) => (
                  <div key={i} className="text-zinc-400">
                    <span className="text-red-500">DEMOTED</span> {d.clean_title?.slice(0, 50)} — {d.reason}
                  </div>
                ))}
              </div>
            </details>
          )}
          {exportResult.held_back_items?.length > 0 && (
            <details className="mt-2">
              <summary className="text-xs text-amber-400/80 cursor-pointer hover:text-amber-300">
                {exportResult.held_back} items held back — view reasons
              </summary>
              <div className="mt-1 max-h-32 overflow-y-auto text-[10px] space-y-0.5">
                {exportResult.held_back_items.map((h, i) => {
                  const [type, detail] = (h.reason || '').split(':');
                  return (
                    <div key={i} className="text-zinc-400">
                      <span className="text-amber-500">{type === 'missing_fields' ? 'MISSING' : type === 'low_confidence' ? 'LOW CONF' : type === 'unresolved_duplicates' ? 'DUPES' : type.toUpperCase()}</span>
                      {' '}{h.clean_title || h.source_title} <span className="text-zinc-600">{detail}</span>
                    </div>
                  );
                })}
              </div>
            </details>
          )}
        </div>
      )}

      {/* Content Area */}
      <div className="flex gap-6">
        {/* Items Table */}
        <div className={`${selectedItem ? 'w-1/2' : 'w-full'} transition-all`}>
          {items.length === 0 ? (
            <div className="border border-zinc-800 border-dashed p-12 text-center" data-testid="no-items">
              <Package className="w-8 h-8 text-zinc-600 mx-auto mb-3" />
              <p className="text-zinc-400 text-sm mb-1">No items yet</p>
              <p className="text-zinc-600 text-xs">Paste order text to extract items, or add manually</p>
            </div>
          ) : (
            <div className="border border-zinc-800 divide-y divide-zinc-800" data-testid="items-table">
              {/* Bulk Action Bar */}
              <div className="flex items-center gap-2 p-2 bg-zinc-900/50">
                <input
                  type="checkbox"
                  checked={items.length > 0 && checkedItems.size === items.length}
                  onChange={toggleCheckAll}
                  className="w-3.5 h-3.5 accent-emerald-500 cursor-pointer"
                  data-testid="select-all-checkbox"
                />
                {checkedItems.size > 0 ? (
                  <div className="flex items-center gap-2 flex-1 flex-wrap">
                    <span className="text-[10px] text-zinc-400">{checkedItems.size} selected</span>
                    <div className="h-3 w-px bg-zinc-700" />
                    <button onClick={() => handleBulkApply('set_status', 'in_review')} disabled={applyingBulk}
                      className="text-[10px] px-2 py-0.5 border border-blue-800/40 text-blue-400 hover:bg-blue-900/20 disabled:opacity-40" data-testid="bulk-in-review-btn">
                      In Review
                    </button>
                    <button onClick={() => handleBulkApply('set_status', 'ready')} disabled={applyingBulk}
                      className="text-[10px] px-2 py-0.5 border border-emerald-800/40 text-emerald-400 hover:bg-emerald-900/20 disabled:opacity-40" data-testid="bulk-ready-btn">
                      Ready
                    </button>
                    <button onClick={() => handleBulkApply('set_status', 'needs_info')} disabled={applyingBulk}
                      className="text-[10px] px-2 py-0.5 border border-amber-800/40 text-amber-400 hover:bg-amber-900/20 disabled:opacity-40" data-testid="bulk-needs-info-btn">
                      Needs Info
                    </button>
                    <div className="h-3 w-px bg-zinc-700" />
                    {bulkAction === 'set_category' ? (
                      <div className="flex items-center gap-1">
                        <input
                          value={bulkValue}
                          onChange={(e) => setBulkValue(e.target.value)}
                          placeholder="Category name"
                          className="text-[10px] px-2 py-0.5 bg-zinc-800 border border-zinc-600 text-white w-28 focus:outline-none focus:border-zinc-400"
                          data-testid="bulk-category-input"
                          onKeyDown={(e) => { if (e.key === 'Enter' && bulkValue.trim()) handleBulkApply('set_category', bulkValue.trim()); }}
                        />
                        <button onClick={() => { if (bulkValue.trim()) handleBulkApply('set_category', bulkValue.trim()); }} disabled={applyingBulk || !bulkValue.trim()}
                          className="text-[10px] px-1.5 py-0.5 text-emerald-400 hover:text-white disabled:opacity-40">Apply</button>
                        <button onClick={() => { setBulkAction(null); setBulkValue(''); }}
                          className="text-[10px] px-1 py-0.5 text-zinc-500 hover:text-white">
                          <X className="w-2.5 h-2.5" />
                        </button>
                      </div>
                    ) : (
                      <button onClick={() => setBulkAction('set_category')} disabled={applyingBulk}
                        className="text-[10px] px-2 py-0.5 border border-zinc-700 text-zinc-400 hover:text-white disabled:opacity-40" data-testid="bulk-category-btn">
                        Set Category
                      </button>
                    )}
                    {bulkAction === 'add_tags' ? (
                      <div className="flex items-center gap-1">
                        <input
                          value={bulkValue}
                          onChange={(e) => setBulkValue(e.target.value)}
                          placeholder="tag1, tag2, ..."
                          className="text-[10px] px-2 py-0.5 bg-zinc-800 border border-zinc-600 text-white w-32 focus:outline-none focus:border-zinc-400"
                          data-testid="bulk-tags-input"
                          onKeyDown={(e) => { if (e.key === 'Enter' && bulkValue.trim()) handleBulkApply('add_tags', bulkValue.trim()); }}
                        />
                        <button onClick={() => { if (bulkValue.trim()) handleBulkApply('add_tags', bulkValue.trim()); }} disabled={applyingBulk || !bulkValue.trim()}
                          className="text-[10px] px-1.5 py-0.5 text-emerald-400 hover:text-white disabled:opacity-40">Apply</button>
                        <button onClick={() => { setBulkAction(null); setBulkValue(''); }}
                          className="text-[10px] px-1 py-0.5 text-zinc-500 hover:text-white">
                          <X className="w-2.5 h-2.5" />
                        </button>
                      </div>
                    ) : (
                      <button onClick={() => setBulkAction('add_tags')} disabled={applyingBulk}
                        className="text-[10px] px-2 py-0.5 border border-zinc-700 text-zinc-400 hover:text-white disabled:opacity-40" data-testid="bulk-tags-btn">
                        Add Tags
                      </button>
                    )}
                    <div className="h-3 w-px bg-zinc-700" />
                    <button onClick={() => setCheckedItems(new Set())}
                      className="text-[10px] px-2 py-0.5 text-zinc-500 hover:text-white">
                      Clear
                    </button>
                  </div>
                ) : (
                  <span className="text-[10px] text-zinc-600">Select items for bulk actions</span>
                )}
              </div>
              {items.map((item, idx) => {
                const conf = STATUS_CONFIG[item.status] || STATUS_CONFIG.needs_info;
                const StatusIcon = conf.icon;
                const isSelected = selectedItem?.id === item.id;
                const hasMissing = item.missing_fields?.length > 0;
                const hasDuplicates = item.duplicate_flags?.length > 0;

                return (
                  <div
                    key={item.id}
                    onClick={() => setSelectedItem(isSelected ? null : item)}
                    className={`p-3 cursor-pointer transition-colors ${
                      isSelected ? 'bg-zinc-800/50 border-l-2 border-white' : 'hover:bg-zinc-900/60'
                    }`}
                    data-testid={`item-row-${idx}`}
                  >
                    <div className="flex items-center gap-3">
                      <input
                        type="checkbox"
                        checked={checkedItems.has(item.id)}
                        onChange={(e) => toggleCheck(item.id, e)}
                        className="w-3.5 h-3.5 accent-emerald-500 cursor-pointer shrink-0"
                        data-testid={`item-checkbox-${idx}`}
                      />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm text-white truncate">
                          {item.clean_title || item.source_title || 'Untitled Item'}
                        </div>
                        <div className="flex items-center gap-2 mt-0.5">
                          {item.color && <span className="text-[10px] text-zinc-500">{item.color}</span>}
                          {item.size && <span className="text-[10px] text-zinc-500">{item.size}</span>}
                          {item.unit_cost != null && (
                            <span className="text-[10px] text-zinc-500">${item.unit_cost?.toFixed(2)}</span>
                          )}
                          {item.suggested_price != null && (
                            <span className="text-[10px] text-emerald-500">${item.suggested_price?.toFixed(2)}</span>
                          )}
                          <span className="text-[10px] text-zinc-600">x{item.quantity}</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {hasDuplicates && (
                          <span className="text-[10px] text-amber-400 flex items-center gap-0.5 px-1 py-0.5 bg-amber-900/20 border border-amber-800/30" title={`${item.duplicate_flags.length} potential duplicate(s)`}>
                            <Copy className="w-3 h-3" />
                            DUP
                          </span>
                        )}
                        {item.generation_confidence && (
                          <span
                            className={`text-[10px] px-1 py-0.5 border ${
                              item.generation_confidence.score >= 0.8
                                ? 'text-emerald-400 border-emerald-800/30 bg-emerald-900/20'
                                : item.generation_confidence.score >= 0.5
                                ? 'text-blue-400 border-blue-800/30 bg-blue-900/20'
                                : 'text-red-400 border-red-800/30 bg-red-900/20'
                            }`}
                            title={item.generation_confidence.reason || `Confidence: ${(item.generation_confidence.score * 100).toFixed(0)}%`}
                            data-testid={`confidence-badge-${idx}`}
                          >
                            {(item.generation_confidence.score * 100).toFixed(0)}%
                          </span>
                        )}
                        {hasMissing && (
                          <span className="text-[10px] text-orange-400 flex items-center gap-0.5" title={`Missing: ${item.missing_fields?.join(', ')}`}>
                            <AlertTriangle className="w-3 h-3" />
                            {item.missing_fields?.length}
                          </span>
                        )}
                        <span className={`text-[10px] px-1.5 py-0.5 flex items-center gap-1 border ${conf.color}`}>
                          <StatusIcon className="w-2.5 h-2.5" />
                          {conf.label}
                        </span>
                        {!item.short_description && (
                          <button
                            onClick={(e) => { e.stopPropagation(); handleGenerateItem(item.id); }}
                            disabled={generating === item.id}
                            className="p-1 text-zinc-500 hover:text-white transition-colors"
                            title="Generate listing"
                            data-testid={`generate-item-${idx}`}
                          >
                            <Wand2 className={`w-3.5 h-3.5 ${generating === item.id ? 'animate-spin' : ''}`} />
                          </button>
                        )}
                        <button
                          onClick={(e) => { e.stopPropagation(); handleDeleteItem(item.id); }}
                          className="p-1 text-zinc-600 hover:text-red-400 transition-colors"
                          data-testid={`delete-item-${idx}`}
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Detail Panel */}
        {selectedItem && (
          <ItemDetailPanel
            item={selectedItem}
            onUpdate={(updated) => {
              setSelectedItem(updated);
              setSession(prev => ({
                ...prev,
                items: prev.items.map(i => i.id === updated.id ? updated : i),
              }));
            }}
            onGenerate={() => handleGenerateItem(selectedItem.id)}
            generating={generating === selectedItem.id}
            onClose={() => setSelectedItem(null)}
            onCheckDuplicates={() => handleCheckDuplicates(selectedItem.id)}
          />
        )}
      </div>

      {/* Extract Modal */}
      {showExtract && (
        <ExtractModal
          sessionId={sessionId}
          onClose={() => setShowExtract(false)}
          onExtracted={() => { setShowExtract(false); fetchSession(); }}
        />
      )}

      {/* Manual Add Modal */}
      {showAddItem && (
        <AddItemModal
          sessionId={sessionId}
          onClose={() => setShowAddItem(false)}
          onCreated={() => { setShowAddItem(false); fetchSession(); }}
        />
      )}
    </div>
  );
}


function ItemDetailPanel({ item, onUpdate, onGenerate, generating, onClose, onCheckDuplicates }) {
  const [editing, setEditing] = useState(false);
  const [fields, setFields] = useState({});
  const [saving, setSaving] = useState(false);
  const [showEvidence, setShowEvidence] = useState(false);

  const startEdit = () => {
    setEditing(true);
    setFields({
      clean_title: item.clean_title || '',
      short_description: item.short_description || '',
      long_description: item.long_description || '',
      category: item.category || '',
      tags: (item.tags || []).join(', '),
      quantity: item.quantity || 1,
      unit_cost: item.unit_cost ?? '',
      suggested_price: item.suggested_price ?? '',
      currency: item.currency || 'USD',
      color: item.color || '',
      size: item.size || '',
      style: item.style || '',
      publish_notes: item.publish_notes || '',
    });
  };

  const saveEdit = async () => {
    setSaving(true);
    try {
      const payload = {
        ...fields,
        tags: fields.tags ? fields.tags.split(',').map(t => t.trim()).filter(Boolean) : [],
        quantity: parseInt(fields.quantity) || 1,
        unit_cost: parseFloat(fields.unit_cost) || null,
        suggested_price: parseFloat(fields.suggested_price) || null,
      };
      const res = await axios.put(`${API}/intake/items/${item.id}`, payload, { withCredentials: true });
      onUpdate(res.data);
      setEditing(false);
    } catch (err) {
      alert(err.response?.data?.detail || 'Save failed');
    }
    setSaving(false);
  };

  const changeStatus = async (newStatus) => {
    try {
      const res = await axios.put(`${API}/intake/items/${item.id}`, { status: newStatus }, { withCredentials: true });
      onUpdate(res.data);
    } catch (err) {
      alert(err.response?.data?.detail || 'Status change failed');
    }
  };

  const conf = STATUS_CONFIG[item.status] || STATUS_CONFIG.needs_info;

  return (
    <div className="w-1/2 border border-zinc-800 overflow-y-auto max-h-[calc(100vh-200px)]" data-testid="item-detail-panel">
      <div className="p-4 border-b border-zinc-800 flex items-center justify-between sticky top-0 bg-[#09090B] z-10">
        <h3 className="text-sm font-medium text-white truncate">{item.clean_title || item.source_title || 'Item Detail'}</h3>
        <button onClick={onClose} className="text-zinc-500 hover:text-white"><X className="w-4 h-4" /></button>
      </div>

      <div className="p-4 space-y-4">
        {/* Status + Actions */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`text-xs px-2 py-1 border flex items-center gap-1.5 ${conf.color}`}>
            <conf.icon className="w-3 h-3" /> {conf.label}
          </span>
          {item.status === 'needs_info' && (
            <button onClick={() => changeStatus('in_review')} className="text-xs px-2 py-1 border border-amber-800 text-amber-400 hover:bg-amber-900/20" data-testid="status-to-review">
              Move to Review
            </button>
          )}
          {item.status === 'in_review' && (
            <button onClick={() => changeStatus('ready')} className="text-xs px-2 py-1 border border-emerald-800 text-emerald-400 hover:bg-emerald-900/20" data-testid="status-to-ready">
              Mark Ready
            </button>
          )}
          {item.status !== 'needs_info' && (
            <button onClick={() => changeStatus('needs_info')} className="text-xs px-2 py-1 border border-zinc-700 text-zinc-400 hover:text-white" data-testid="status-to-needs-info">
              Back to Needs Info
            </button>
          )}
          {!editing && (
            <button onClick={startEdit} className="text-xs px-2 py-1 border border-zinc-700 text-zinc-400 hover:text-white flex items-center gap-1" data-testid="edit-item-btn">
              <Edit3 className="w-3 h-3" /> Edit
            </button>
          )}
          <button
            onClick={onGenerate}
            disabled={generating}
            className="text-xs px-2 py-1 border border-zinc-700 text-zinc-400 hover:text-white flex items-center gap-1 disabled:opacity-40"
            data-testid="generate-listing-btn"
          >
            <Wand2 className={`w-3 h-3 ${generating ? 'animate-spin' : ''}`} />
            {generating ? 'Generating...' : item.short_description ? 'Regenerate' : 'Generate'}
          </button>
          <button
            onClick={onCheckDuplicates}
            className="text-xs px-2 py-1 border border-zinc-700 text-zinc-400 hover:text-white flex items-center gap-1"
            data-testid="check-duplicates-btn"
          >
            <Copy className="w-3 h-3" /> Check Dupes
          </button>
        </div>

        {/* Missing Fields */}
        {item.missing_fields?.length > 0 && (
          <div className="bg-orange-950/30 border border-orange-900/40 p-3" data-testid="missing-fields-indicator">
            <div className="text-xs text-orange-400 font-medium mb-1 flex items-center gap-1.5">
              <AlertTriangle className="w-3.5 h-3.5" /> Missing Required Fields
            </div>
            <div className="flex flex-wrap gap-1.5">
              {item.missing_fields.map(f => (
                <span key={f} className="text-[10px] px-1.5 py-0.5 bg-orange-900/30 text-orange-300 border border-orange-800/40">
                  {f.replace(/_/g, ' ')}
                </span>
              ))}
            </div>
          </div>
        )}

        {editing ? (
          <EditForm fields={fields} setFields={setFields} item={item} onSave={saveEdit} onCancel={() => setEditing(false)} saving={saving} />
        ) : (
          <>
            <ViewFields item={item} />
            {/* Attribute Suggestions */}
            {item.attribute_suggestions && Object.keys(item.attribute_suggestions).length > 0 && (
              <div className="border border-zinc-800 p-3" data-testid="attribute-suggestions">
                <div className="text-[10px] text-zinc-600 uppercase tracking-wider mb-2">Attribute Suggestions</div>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(item.attribute_suggestions).map(([key, val]) => val ? (
                    <span key={key} className="text-[10px] px-1.5 py-0.5 bg-zinc-800 text-zinc-300 border border-zinc-700">
                      {key}: {val}
                    </span>
                  ) : null)}
                </div>
              </div>
            )}
            {/* Duplicate Flags */}
            {item.duplicate_flags?.length > 0 && (
              <div className="bg-amber-950/20 border border-amber-900/30 p-3" data-testid="duplicate-flags">
                <div className="text-xs text-amber-400 font-medium mb-2 flex items-center gap-1.5">
                  <Copy className="w-3.5 h-3.5" /> Potential Duplicates
                </div>
                {item.duplicate_flags.map((f, i) => (
                  <div key={i} className="text-xs text-zinc-400 mb-1">
                    {f.type === 'catalog_sku_match' && <span className="text-amber-300">SKU match in catalog:</span>}
                    {f.type === 'catalog_title_match' && <span className="text-amber-300">Title match in catalog ({f.score}%):</span>}
                    {f.type === 'draft_title_match' && <span className="text-zinc-500">Similar draft item ({f.score}%):</span>}
                    {' '}{f.match_title}
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {/* Evidence */}
        {item.extraction_evidence && (
          <div>
            <button
              onClick={() => setShowEvidence(!showEvidence)}
              className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300"
              data-testid="toggle-evidence"
            >
              {showEvidence ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
              Extraction Evidence
            </button>
            {showEvidence && (
              <pre className="mt-2 text-xs text-zinc-500 bg-zinc-900 p-3 whitespace-pre-wrap overflow-x-auto border border-zinc-800" data-testid="evidence-text">
                {item.extraction_evidence}
              </pre>
            )}
          </div>
        )}

        {/* Publish Notes */}
        {item.publish_notes && !editing && (
          <div className="border border-zinc-800 p-3" data-testid="publish-notes">
            <div className="text-[10px] text-zinc-600 uppercase tracking-wider mb-1">Publish Readiness Notes</div>
            <div className="text-xs text-zinc-400">{item.publish_notes}</div>
          </div>
        )}
      </div>
    </div>
  );
}


function ViewFields({ item }) {
  return (
    <div className="space-y-3">
      <Field label="Clean Title" value={item.clean_title} />
      <Field label="Source Title" value={item.source_title} muted />
      <Field label="Short Description" value={item.short_description} />
      {item.long_description && <Field label="Long Description" value={item.long_description} />}
      <div className="grid grid-cols-2 gap-3">
        <Field label="Category" value={item.category} />
        <Field label="Tags" value={(item.tags || []).join(', ')} />
      </div>
      <div className="grid grid-cols-3 gap-3">
        <Field label="Cost" value={item.unit_cost != null ? `$${item.unit_cost?.toFixed(2)}` : '—'} />
        <Field label="Suggested Price" value={item.suggested_price != null ? `$${item.suggested_price?.toFixed(2)}` : '—'} highlight />
        <Field label="Qty" value={item.quantity} />
      </div>
      <div className="grid grid-cols-3 gap-3">
        <Field label="Color" value={item.color} />
        <Field label="Size" value={item.size} />
        <Field label="Style" value={item.style} />
      </div>
      {item.category_suggestions?.length > 0 && (
        <div>
          <span className="text-[10px] text-zinc-600 uppercase tracking-wider">Category Suggestions</span>
          <div className="flex gap-1.5 mt-1">
            {item.category_suggestions.map((c, i) => (
              <span key={i} className="text-[10px] px-1.5 py-0.5 border border-zinc-700 text-zinc-400">{c}</span>
            ))}
          </div>
        </div>
      )}
      {item.generation_confidence && (
        <div data-testid="confidence-detail">
          <span className="text-[10px] text-zinc-600 uppercase tracking-wider">Generation Confidence</span>
          <div className="mt-1 flex items-center gap-3">
            <span className={`text-sm font-medium ${
              item.generation_confidence.score >= 0.8 ? 'text-emerald-400' :
              item.generation_confidence.score >= 0.5 ? 'text-blue-400' : 'text-red-400'
            }`}>
              {(item.generation_confidence.score * 100).toFixed(0)}%
            </span>
            <div className="flex gap-2 text-[10px]">
              {item.generation_confidence.title_confidence && (
                <span className="text-zinc-500">Title: <span className="text-zinc-300">{item.generation_confidence.title_confidence}</span></span>
              )}
              {item.generation_confidence.category_confidence && (
                <span className="text-zinc-500">Category: <span className="text-zinc-300">{item.generation_confidence.category_confidence}</span></span>
              )}
              {item.generation_confidence.description_confidence && (
                <span className="text-zinc-500">Desc: <span className="text-zinc-300">{item.generation_confidence.description_confidence}</span></span>
              )}
            </div>
          </div>
          {item.generation_confidence.reason && (
            <div className="mt-1 text-[10px] text-amber-400/80">{item.generation_confidence.reason}</div>
          )}
        </div>
      )}
    </div>
  );
}


function Field({ label, value, muted, highlight }) {
  return (
    <div>
      <div className="text-[10px] text-zinc-600 uppercase tracking-wider mb-0.5">{label}</div>
      <div className={`text-sm ${highlight ? 'text-emerald-400' : muted ? 'text-zinc-500' : 'text-zinc-300'}`}>
        {value || '—'}
      </div>
    </div>
  );
}


function EditForm({ fields, setFields, item, onSave, onCancel, saving }) {
  const set = (key, val) => setFields(prev => ({ ...prev, [key]: val }));

  return (
    <div className="space-y-3" data-testid="edit-form">
      <div>
        <label className="block text-[10px] text-zinc-600 uppercase tracking-wider mb-0.5">Clean Title</label>
        <input value={fields.clean_title} onChange={e => set('clean_title', e.target.value)}
          className="w-full bg-zinc-900 border border-zinc-800 px-2 py-1.5 text-sm text-white focus:border-zinc-600 focus:outline-none" data-testid="edit-clean-title" />
      </div>
      <div>
        <label className="block text-[10px] text-zinc-600 uppercase tracking-wider mb-0.5">Short Description</label>
        <textarea value={fields.short_description} onChange={e => set('short_description', e.target.value)} rows={2}
          className="w-full bg-zinc-900 border border-zinc-800 px-2 py-1.5 text-sm text-white focus:border-zinc-600 focus:outline-none resize-none" data-testid="edit-short-desc" />
      </div>
      <div>
        <label className="block text-[10px] text-zinc-600 uppercase tracking-wider mb-0.5">Long Description</label>
        <textarea value={fields.long_description} onChange={e => set('long_description', e.target.value)} rows={4}
          className="w-full bg-zinc-900 border border-zinc-800 px-2 py-1.5 text-sm text-white focus:border-zinc-600 focus:outline-none resize-y" data-testid="edit-long-desc" />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-[10px] text-zinc-600 uppercase tracking-wider mb-0.5">Category</label>
          <input value={fields.category} onChange={e => set('category', e.target.value)}
            className="w-full bg-zinc-900 border border-zinc-800 px-2 py-1.5 text-sm text-white focus:border-zinc-600 focus:outline-none" data-testid="edit-category" />
        </div>
        <div>
          <label className="block text-[10px] text-zinc-600 uppercase tracking-wider mb-0.5">Tags (comma-separated)</label>
          <input value={fields.tags} onChange={e => set('tags', e.target.value)}
            className="w-full bg-zinc-900 border border-zinc-800 px-2 py-1.5 text-sm text-white focus:border-zinc-600 focus:outline-none" data-testid="edit-tags" />
        </div>
      </div>
      <div className="grid grid-cols-3 gap-3">
        <div>
          <label className="block text-[10px] text-zinc-600 uppercase tracking-wider mb-0.5">Unit Cost</label>
          <input type="number" step="0.01" value={fields.unit_cost} onChange={e => set('unit_cost', e.target.value)}
            className="w-full bg-zinc-900 border border-zinc-800 px-2 py-1.5 text-sm text-white focus:border-zinc-600 focus:outline-none" data-testid="edit-cost" />
        </div>
        <div>
          <label className="block text-[10px] text-zinc-600 uppercase tracking-wider mb-0.5">Suggested Price</label>
          <input type="number" step="0.01" value={fields.suggested_price} onChange={e => set('suggested_price', e.target.value)}
            className="w-full bg-zinc-900 border border-zinc-800 px-2 py-1.5 text-sm text-white focus:border-zinc-600 focus:outline-none" data-testid="edit-price" />
        </div>
        <div>
          <label className="block text-[10px] text-zinc-600 uppercase tracking-wider mb-0.5">Qty</label>
          <input type="number" min="1" value={fields.quantity} onChange={e => set('quantity', e.target.value)}
            className="w-full bg-zinc-900 border border-zinc-800 px-2 py-1.5 text-sm text-white focus:border-zinc-600 focus:outline-none" data-testid="edit-qty" />
        </div>
      </div>
      <div className="grid grid-cols-3 gap-3">
        <div>
          <label className="block text-[10px] text-zinc-600 uppercase tracking-wider mb-0.5">Color</label>
          <input value={fields.color} onChange={e => set('color', e.target.value)}
            className="w-full bg-zinc-900 border border-zinc-800 px-2 py-1.5 text-sm text-white focus:border-zinc-600 focus:outline-none" data-testid="edit-color" />
        </div>
        <div>
          <label className="block text-[10px] text-zinc-600 uppercase tracking-wider mb-0.5">Size</label>
          <input value={fields.size} onChange={e => set('size', e.target.value)}
            className="w-full bg-zinc-900 border border-zinc-800 px-2 py-1.5 text-sm text-white focus:border-zinc-600 focus:outline-none" data-testid="edit-size" />
        </div>
        <div>
          <label className="block text-[10px] text-zinc-600 uppercase tracking-wider mb-0.5">Style</label>
          <input value={fields.style} onChange={e => set('style', e.target.value)}
            className="w-full bg-zinc-900 border border-zinc-800 px-2 py-1.5 text-sm text-white focus:border-zinc-600 focus:outline-none" data-testid="edit-style" />
        </div>
      </div>
      <div>
        <label className="block text-[10px] text-zinc-600 uppercase tracking-wider mb-0.5">Publish Readiness Notes</label>
        <textarea value={fields.publish_notes} onChange={e => set('publish_notes', e.target.value)} rows={2}
          className="w-full bg-zinc-900 border border-zinc-800 px-2 py-1.5 text-sm text-white placeholder-zinc-600 focus:border-zinc-600 focus:outline-none resize-none"
          placeholder="e.g. replace image, verify material, size unclear..." data-testid="edit-publish-notes" />
      </div>
      <div className="flex gap-2 pt-1">
        <button onClick={onSave} disabled={saving}
          className="px-3 py-1.5 bg-white text-black text-sm font-medium hover:bg-zinc-200 disabled:opacity-40" data-testid="save-item-btn">
          {saving ? 'Saving...' : 'Save'}
        </button>
        <button onClick={onCancel} className="px-3 py-1.5 text-sm text-zinc-400 hover:text-white">Cancel</button>
      </div>
    </div>
  );
}


function ExtractModal({ sessionId, onClose, onExtracted }) {
  const [text, setText] = useState('');
  const [sourceType, setSourceType] = useState('pasted_order');
  const [extracting, setExtracting] = useState(false);
  const [result, setResult] = useState(null);

  const handleExtract = async () => {
    if (!text.trim() || text.trim().length < 10) return;
    setExtracting(true);
    try {
      const res = await axios.post(`${API}/intake/sessions/${sessionId}/extract`, {
        text: text.trim(),
        source_type: sourceType,
      }, { withCredentials: true });
      setResult(res.data);
    } catch (err) {
      alert(err.response?.data?.detail || 'Extraction failed. Try again or add items manually.');
    }
    setExtracting(false);
  };

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-[#0C0C0E] border border-zinc-800 w-full max-w-2xl max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="p-6 border-b border-zinc-800">
          <h2 className="text-lg font-['Outfit'] text-white">Paste & Extract Items</h2>
          <p className="text-xs text-zinc-500 mt-1">Paste order confirmation, cart summary, or email text — AI will extract the items</p>
        </div>
        <div className="p-6 space-y-4">
          <div>
            <label className="block text-xs text-zinc-500 uppercase tracking-wider mb-1">Source Type</label>
            <div className="flex gap-2">
              {SOURCE_TYPES.filter(t => t.value !== 'manual_entry').map(t => (
                <button
                  key={t.value}
                  onClick={() => setSourceType(t.value)}
                  className={`px-3 py-1.5 text-xs border transition-colors ${
                    sourceType === t.value
                      ? 'border-white text-white bg-zinc-800'
                      : 'border-zinc-700 text-zinc-400 hover:border-zinc-500'
                  }`}
                  data-testid={`source-type-${t.value}`}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-xs text-zinc-500 uppercase tracking-wider mb-1">Paste Text *</label>
            <textarea
              value={text}
              onChange={e => setText(e.target.value)}
              rows={12}
              className="w-full bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-white font-mono placeholder-zinc-600 focus:border-zinc-600 focus:outline-none resize-y"
              placeholder="Paste your order confirmation, receipt, or cart text here..."
              data-testid="extract-text-input"
            />
            <span className="text-[10px] text-zinc-600">{text.length} chars</span>
          </div>

          {result && (
            <div className="border border-emerald-900/40 bg-emerald-950/20 p-4" data-testid="extract-result">
              <div className="text-sm text-emerald-400 font-medium mb-2">
                Extracted {result.extracted_count} item{result.extracted_count !== 1 ? 's' : ''}
              </div>
              {result.items?.map((item, i) => (
                <div key={i} className="text-xs text-zinc-400 py-1 border-t border-zinc-800 first:border-t-0">
                  {item.source_title || 'Untitled'} &middot; x{item.quantity} &middot; {item.unit_cost != null ? `$${item.unit_cost}` : 'no price'}
                </div>
              ))}
            </div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            {result ? (
              <button onClick={onExtracted} className="px-4 py-2 bg-white text-black text-sm font-medium hover:bg-zinc-200" data-testid="done-extract-btn">
                Done
              </button>
            ) : (
              <>
                <button onClick={onClose} className="px-4 py-2 text-sm text-zinc-400 hover:text-white transition-colors">Cancel</button>
                <button
                  onClick={handleExtract}
                  disabled={extracting || text.trim().length < 10}
                  className="px-4 py-2 bg-white text-black text-sm font-medium hover:bg-zinc-200 transition-colors disabled:opacity-40"
                  data-testid="extract-submit-btn"
                >
                  {extracting ? 'Extracting...' : 'Extract Items'}
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}


function AddItemModal({ sessionId, onClose, onCreated }) {
  const [title, setTitle] = useState('');
  const [color, setColor] = useState('');
  const [size, setSize] = useState('');
  const [qty, setQty] = useState('1');
  const [cost, setCost] = useState('');
  const [url, setUrl] = useState('');
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await axios.post(`${API}/intake/sessions/${sessionId}/items`, {
        source_type: 'manual_entry',
        source_title: title.trim(),
        quantity: parseInt(qty) || 1,
        unit_cost: parseFloat(cost) || null,
        color: color.trim() || null,
        size: size.trim() || null,
        source_url: url.trim() || null,
        notes: notes.trim() || null,
      }, { withCredentials: true });
      onCreated();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to add item');
    }
    setSaving(false);
  };

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-[#0C0C0E] border border-zinc-800 w-full max-w-md" onClick={e => e.stopPropagation()}>
        <div className="p-6 border-b border-zinc-800">
          <h2 className="text-lg font-['Outfit'] text-white">Add Item Manually</h2>
        </div>
        <form onSubmit={handleSubmit} className="p-6 space-y-3">
          <div>
            <label className="block text-[10px] text-zinc-600 uppercase tracking-wider mb-0.5">Product Title</label>
            <input value={title} onChange={e => setTitle(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-800 px-2 py-1.5 text-sm text-white focus:border-zinc-600 focus:outline-none"
              placeholder="Product name as shown on source" data-testid="manual-title" />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-[10px] text-zinc-600 uppercase tracking-wider mb-0.5">Color</label>
              <input value={color} onChange={e => setColor(e.target.value)}
                className="w-full bg-zinc-900 border border-zinc-800 px-2 py-1.5 text-sm text-white focus:border-zinc-600 focus:outline-none" data-testid="manual-color" />
            </div>
            <div>
              <label className="block text-[10px] text-zinc-600 uppercase tracking-wider mb-0.5">Size</label>
              <input value={size} onChange={e => setSize(e.target.value)}
                className="w-full bg-zinc-900 border border-zinc-800 px-2 py-1.5 text-sm text-white focus:border-zinc-600 focus:outline-none" data-testid="manual-size" />
            </div>
            <div>
              <label className="block text-[10px] text-zinc-600 uppercase tracking-wider mb-0.5">Qty</label>
              <input type="number" min="1" value={qty} onChange={e => setQty(e.target.value)}
                className="w-full bg-zinc-900 border border-zinc-800 px-2 py-1.5 text-sm text-white focus:border-zinc-600 focus:outline-none" data-testid="manual-qty" />
            </div>
          </div>
          <div>
            <label className="block text-[10px] text-zinc-600 uppercase tracking-wider mb-0.5">Unit Cost ($)</label>
            <input type="number" step="0.01" value={cost} onChange={e => setCost(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-800 px-2 py-1.5 text-sm text-white focus:border-zinc-600 focus:outline-none"
              placeholder="0.00" data-testid="manual-cost" />
          </div>
          <div>
            <label className="block text-[10px] text-zinc-600 uppercase tracking-wider mb-0.5">Source URL</label>
            <input value={url} onChange={e => setUrl(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-800 px-2 py-1.5 text-sm text-white placeholder-zinc-600 focus:border-zinc-600 focus:outline-none"
              placeholder="https://..." data-testid="manual-url" />
          </div>
          <div>
            <label className="block text-[10px] text-zinc-600 uppercase tracking-wider mb-0.5">Publish Notes</label>
            <input value={notes} onChange={e => setNotes(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-800 px-2 py-1.5 text-sm text-white placeholder-zinc-600 focus:border-zinc-600 focus:outline-none"
              placeholder="e.g. needs photo, check sizing..." data-testid="manual-notes" />
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-zinc-400 hover:text-white">Cancel</button>
            <button type="submit" disabled={saving}
              className="px-4 py-2 bg-white text-black text-sm font-medium hover:bg-zinc-200 disabled:opacity-40" data-testid="manual-submit-btn">
              {saving ? 'Adding...' : 'Add Item'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
