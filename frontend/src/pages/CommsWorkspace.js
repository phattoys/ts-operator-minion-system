import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import {
  MessageSquare, Send, Copy, Check, Star, Search,
  RefreshCw, ChevronDown, ChevronUp, Clock, Trash2,
  Mail, Smartphone, MessagesSquare, Shield, AlertTriangle,
  Clipboard, X, History, Wand2,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const CHANNEL_CONFIG = {
  email: { icon: Mail, label: 'Email' },
  sms: { icon: Smartphone, label: 'SMS' },
  chat: { icon: MessagesSquare, label: 'Chat' },
};

const VARIANT_LABELS = {
  short: 'Short',
  standard: 'Standard',
  extra_careful: 'Extra-Careful',
};

export default function CommsWorkspace() {
  const [scenarios, setScenarios] = useState([]);
  const [channels, setChannels] = useState([]);
  const [view, setView] = useState('draft'); // draft | history
  const [stats, setStats] = useState(null);

  // Draft state
  const [selectedScenario, setSelectedScenario] = useState('');
  const [selectedChannel, setSelectedChannel] = useState('email');
  const [customerMessage, setCustomerMessage] = useState('');
  const [contextFields, setContextFields] = useState({});
  const [maxDiscretion, setMaxDiscretion] = useState(false);
  const [usePlaceholders, setUsePlaceholders] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState(null);
  const [needsInfo, setNeedsInfo] = useState(null);
  const [selectedVariant, setSelectedVariant] = useState(null);
  const [editingText, setEditingText] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [copied, setCopied] = useState(false);

  // History state
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historySearch, setHistorySearch] = useState('');
  const [historyFilter, setHistoryFilter] = useState('');
  const [favoritesOnly, setFavoritesOnly] = useState(false);
  const [expandedDraft, setExpandedDraft] = useState(null);

  useEffect(() => {
    fetchScenarios();
    fetchStats();
  }, []);

  const fetchScenarios = async () => {
    try {
      const res = await axios.get(`${API}/comms/scenarios`, { withCredentials: true });
      setScenarios(res.data.scenarios || []);
      setChannels(res.data.channels || []);
    } catch (err) {
      console.error('Failed to fetch scenarios:', err);
    }
  };

  const fetchStats = async () => {
    try {
      const res = await axios.get(`${API}/comms/stats`, { withCredentials: true });
      setStats(res.data);
    } catch (err) {
      console.error('Failed to fetch stats:', err);
    }
  };

  const fetchHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const params = {};
      if (historyFilter) params.scenario_key = historyFilter;
      if (historySearch) params.search = historySearch;
      if (favoritesOnly) params.favorites_only = true;
      const res = await axios.get(`${API}/comms/history`, { params, withCredentials: true });
      setHistory(res.data.drafts || []);
    } catch (err) {
      console.error('Failed to fetch history:', err);
    }
    setHistoryLoading(false);
  }, [historyFilter, historySearch, favoritesOnly]);

  useEffect(() => {
    if (view === 'history') fetchHistory();
  }, [view, fetchHistory]);

  const currentScenario = scenarios.find(s => s.key === selectedScenario);

  const handleGenerate = async () => {
    if (!selectedScenario) return;
    setGenerating(true);
    setResult(null);
    setNeedsInfo(null);
    setSelectedVariant(null);
    setIsEditing(false);

    try {
      const res = await axios.post(`${API}/comms/generate`, {
        scenario_key: selectedScenario,
        channel: selectedChannel,
        customer_message: customerMessage.trim() || null,
        context_fields: contextFields,
        max_discretion: maxDiscretion,
        generate_with_placeholders: usePlaceholders,
      }, { withCredentials: true });

      if (res.data.status === 'needs_info') {
        setNeedsInfo(res.data);
      } else {
        setResult(res.data);
        if (res.data.variants?.length > 0) {
          setSelectedVariant(res.data.variants[1] || res.data.variants[0]);
        }
      }
    } catch (err) {
      alert(err.response?.data?.detail || 'Generation failed. Try again.');
    }
    setGenerating(false);
  };

  const handleCopy = () => {
    const text = isEditing ? editingText : selectedVariant?.body || '';
    let copyText = text;
    if (selectedChannel === 'email' && result?.subject) {
      copyText = `Subject: ${result.subject}\n\n${text}`;
    }
    if (result?.ps_line) {
      copyText += `\n\nP.S. ${result.ps_line}`;
    }
    navigator.clipboard.writeText(copyText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleToggleFavorite = async (draftId) => {
    try {
      await axios.post(`${API}/comms/history/${draftId}/favorite`, { draft_id: draftId }, { withCredentials: true });
      fetchHistory();
    } catch (err) {
      console.error('Favorite toggle failed:', err);
    }
  };

  const handleDuplicate = async (draftId) => {
    try {
      const res = await axios.post(`${API}/comms/history/${draftId}/duplicate`, {}, { withCredentials: true });
      const data = res.data;
      setSelectedScenario(data.scenario_key);
      setSelectedChannel(data.channel);
      setCustomerMessage(data.customer_message || '');
      setContextFields(data.context_fields || {});
      setMaxDiscretion(data.max_discretion || false);
      setResult(null);
      setNeedsInfo(null);
      setView('draft');
    } catch (err) {
      console.error('Duplicate failed:', err);
    }
  };

  const handleDeleteDraft = async (draftId) => {
    if (!window.confirm('Delete this draft?')) return;
    try {
      await axios.delete(`${API}/comms/history/${draftId}`, { withCredentials: true });
      fetchHistory();
    } catch (err) {
      console.error('Delete failed:', err);
    }
  };

  const resetDraft = () => {
    setSelectedScenario('');
    setSelectedChannel('email');
    setCustomerMessage('');
    setContextFields({});
    setMaxDiscretion(false);
    setUsePlaceholders(false);
    setResult(null);
    setNeedsInfo(null);
    setSelectedVariant(null);
    setIsEditing(false);
  };

  return (
    <div className="p-8 max-w-[1400px] mx-auto" data-testid="comms-workspace">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-['Outfit'] font-light text-white tracking-tight">
            Customer Comms
          </h1>
          <p className="text-sm text-zinc-500 mt-1">Customer Comms Minion</p>
        </div>
        <div className="flex items-center gap-2">
          {stats && (
            <span className="text-xs text-zinc-500 mr-3">
              {stats.total_drafts} drafts &middot; {stats.favorites} saved
            </span>
          )}
          <button
            onClick={() => { setView('draft'); resetDraft(); }}
            className={`px-3 py-2 text-sm transition-colors ${view === 'draft' ? 'bg-white text-black' : 'border border-zinc-700 text-zinc-300 hover:border-zinc-500'}`}
            data-testid="view-draft-btn"
          >
            <Wand2 className="w-3.5 h-3.5 inline mr-1.5" />New Draft
          </button>
          <button
            onClick={() => setView('history')}
            className={`px-3 py-2 text-sm transition-colors ${view === 'history' ? 'bg-white text-black' : 'border border-zinc-700 text-zinc-300 hover:border-zinc-500'}`}
            data-testid="view-history-btn"
          >
            <History className="w-3.5 h-3.5 inline mr-1.5" />History
          </button>
        </div>
      </div>

      {view === 'draft' ? (
        <div className="flex gap-6">
          {/* Left: Input Panel */}
          <div className="w-1/2 space-y-4" data-testid="draft-input-panel">
            {/* Scenario Selector */}
            <div>
              <label className="block text-xs text-zinc-500 uppercase tracking-wider mb-1">Scenario *</label>
              <select
                value={selectedScenario}
                onChange={e => { setSelectedScenario(e.target.value); setResult(null); setNeedsInfo(null); setContextFields({}); }}
                className="w-full bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-white focus:border-zinc-600 focus:outline-none"
                data-testid="scenario-select"
              >
                <option value="">Select a scenario...</option>
                {scenarios.map(s => (
                  <option key={s.key} value={s.key}>{s.label}</option>
                ))}
              </select>
            </div>

            {/* Channel Selector */}
            <div>
              <label className="block text-xs text-zinc-500 uppercase tracking-wider mb-1">Channel</label>
              <div className="flex gap-2">
                {Object.entries(CHANNEL_CONFIG).map(([key, conf]) => (
                  <button
                    key={key}
                    onClick={() => setSelectedChannel(key)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 text-xs border transition-colors ${
                      selectedChannel === key
                        ? 'border-white text-white bg-zinc-800'
                        : 'border-zinc-700 text-zinc-400 hover:border-zinc-500'
                    }`}
                    data-testid={`channel-${key}`}
                  >
                    <conf.icon className="w-3.5 h-3.5" />
                    {conf.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Context Fields */}
            {currentScenario && (
              <div>
                <label className="block text-xs text-zinc-500 uppercase tracking-wider mb-1">Context Fields</label>
                <div className="space-y-2">
                  {[...currentScenario.required_fields, ...currentScenario.optional_fields].map(field => (
                    <div key={field} className="flex items-center gap-2">
                      <label className="text-xs text-zinc-400 w-32 shrink-0 capitalize">
                        {field.replace(/_/g, ' ')}
                        {currentScenario.required_fields.includes(field) && <span className="text-red-400 ml-0.5">*</span>}
                      </label>
                      <input
                        value={contextFields[field] || ''}
                        onChange={e => setContextFields({ ...contextFields, [field]: e.target.value })}
                        className="flex-1 bg-zinc-900 border border-zinc-800 px-2 py-1.5 text-sm text-white focus:border-zinc-600 focus:outline-none"
                        placeholder={field.replace(/_/g, ' ')}
                        data-testid={`field-${field}`}
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Customer Message */}
            <div>
              <label className="block text-xs text-zinc-500 uppercase tracking-wider mb-1">Customer Message (optional)</label>
              <textarea
                value={customerMessage}
                onChange={e => setCustomerMessage(e.target.value)}
                rows={4}
                className="w-full bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-white placeholder-zinc-600 focus:border-zinc-600 focus:outline-none resize-y"
                placeholder="Paste the customer's message here..."
                data-testid="customer-message"
              />
            </div>

            {/* Toggles */}
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2 text-sm text-zinc-400 cursor-pointer">
                <input
                  type="checkbox"
                  checked={maxDiscretion}
                  onChange={e => setMaxDiscretion(e.target.checked)}
                  className="accent-white"
                  data-testid="max-discretion-toggle"
                />
                <Shield className="w-3.5 h-3.5" /> Max Discretion
              </label>
              <label className="flex items-center gap-2 text-sm text-zinc-400 cursor-pointer">
                <input
                  type="checkbox"
                  checked={usePlaceholders}
                  onChange={e => setUsePlaceholders(e.target.checked)}
                  className="accent-white"
                  data-testid="placeholders-toggle"
                />
                Allow Placeholders
              </label>
            </div>

            {/* Generate Button */}
            <button
              onClick={handleGenerate}
              disabled={generating || !selectedScenario}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-white text-black text-sm font-medium hover:bg-zinc-200 transition-colors disabled:opacity-40"
              data-testid="generate-btn"
            >
              <Send className={`w-4 h-4 ${generating ? 'animate-pulse' : ''}`} />
              {generating ? 'Generating 3 Variants...' : 'Generate Draft'}
            </button>
          </div>

          {/* Right: Output Panel */}
          <div className="w-1/2" data-testid="draft-output-panel">
            {needsInfo && (
              <div className="border border-orange-900/40 bg-orange-950/20 p-4" data-testid="needs-info-panel">
                <div className="text-sm text-orange-400 font-medium mb-2 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4" /> Missing Required Fields
                </div>
                <p className="text-xs text-zinc-400 mb-3">{needsInfo.message}</p>
                <div className="flex flex-wrap gap-1.5">
                  {needsInfo.missing_fields.map(f => (
                    <span key={f} className="text-[10px] px-2 py-0.5 bg-orange-900/30 text-orange-300 border border-orange-800/40">
                      {f.replace(/_/g, ' ')}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {!result && !needsInfo && (
              <div className="border border-zinc-800 border-dashed p-12 text-center">
                <MessageSquare className="w-8 h-8 text-zinc-600 mx-auto mb-3" />
                <p className="text-zinc-500 text-sm">Select a scenario and generate a draft</p>
                <p className="text-zinc-600 text-xs mt-1">3 variants will be generated: Short, Standard, Extra-Careful</p>
              </div>
            )}

            {result && (
              <div className="space-y-4">
                {/* Subject (email only) */}
                {result.subject && selectedChannel === 'email' && (
                  <div className="border border-zinc-800 p-3">
                    <div className="text-[10px] text-zinc-600 uppercase tracking-wider mb-1">Subject Line</div>
                    <div className="text-sm text-white">{result.subject}</div>
                  </div>
                )}

                {/* Variant Tabs */}
                <div className="flex border-b border-zinc-800">
                  {result.variants?.map(v => (
                    <button
                      key={v.type}
                      onClick={() => { setSelectedVariant(v); setIsEditing(false); }}
                      className={`px-4 py-2.5 text-sm transition-colors ${
                        selectedVariant?.type === v.type
                          ? 'text-white border-b-2 border-white -mb-px'
                          : 'text-zinc-500 hover:text-zinc-300'
                      }`}
                      data-testid={`variant-${v.type}`}
                    >
                      {VARIANT_LABELS[v.type] || v.type}
                    </button>
                  ))}
                </div>

                {/* Selected Variant */}
                {selectedVariant && (
                  <div className="border border-zinc-800 p-4">
                    {isEditing ? (
                      <textarea
                        value={editingText}
                        onChange={e => setEditingText(e.target.value)}
                        rows={12}
                        className="w-full bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-white focus:border-zinc-600 focus:outline-none resize-y"
                        data-testid="edit-variant-textarea"
                      />
                    ) : (
                      <div className="text-sm text-zinc-300 whitespace-pre-wrap leading-relaxed" data-testid="variant-body">
                        {selectedVariant.body}
                      </div>
                    )}

                    {result.ps_line && (
                      <div className="mt-3 pt-3 border-t border-zinc-800 text-xs text-zinc-500 italic">
                        P.S. {result.ps_line}
                      </div>
                    )}

                    {/* Action buttons */}
                    <div className="flex items-center gap-2 mt-4 pt-3 border-t border-zinc-800">
                      <button
                        onClick={handleCopy}
                        className="flex items-center gap-1.5 px-3 py-1.5 bg-white text-black text-sm font-medium hover:bg-zinc-200 transition-colors"
                        data-testid="copy-btn"
                      >
                        {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                        {copied ? 'Copied!' : 'Copy'}
                      </button>
                      {!isEditing ? (
                        <button
                          onClick={() => { setIsEditing(true); setEditingText(selectedVariant.body); }}
                          className="flex items-center gap-1.5 px-3 py-1.5 border border-zinc-700 text-sm text-zinc-300 hover:border-zinc-500 transition-colors"
                          data-testid="edit-variant-btn"
                        >
                          Edit Before Copy
                        </button>
                      ) : (
                        <button
                          onClick={() => setIsEditing(false)}
                          className="px-3 py-1.5 text-sm text-zinc-400 hover:text-white"
                        >
                          Cancel Edit
                        </button>
                      )}
                      <button
                        onClick={handleGenerate}
                        disabled={generating}
                        className="flex items-center gap-1.5 px-3 py-1.5 border border-zinc-700 text-sm text-zinc-300 hover:border-zinc-500 transition-colors disabled:opacity-40"
                        data-testid="regenerate-btn"
                      >
                        <RefreshCw className={`w-3.5 h-3.5 ${generating ? 'animate-spin' : ''}`} />
                        Regenerate
                      </button>
                    </div>
                  </div>
                )}

                {/* Draft info */}
                <div className="text-[10px] text-zinc-600 flex items-center gap-3">
                  <span>ID: {result.id?.slice(0, 8)}</span>
                  <span>{result.scenario_label}</span>
                  <span>{selectedChannel}</span>
                  {result.max_discretion && <span className="text-amber-500 flex items-center gap-0.5"><Shield className="w-2.5 h-2.5" /> Discreet</span>}
                </div>
              </div>
            )}
          </div>
        </div>
      ) : (
        /* HISTORY VIEW */
        <div data-testid="comms-history">
          <div className="flex items-center gap-3 mb-6">
            <div className="relative flex-1">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
              <input
                type="text"
                placeholder="Search by order #, customer name..."
                value={historySearch}
                onChange={e => setHistorySearch(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && fetchHistory()}
                className="w-full bg-zinc-900 border border-zinc-800 pl-10 pr-4 py-2 text-sm text-white placeholder-zinc-600 focus:border-zinc-600 focus:outline-none"
                data-testid="history-search"
              />
            </div>
            <select
              value={historyFilter}
              onChange={e => setHistoryFilter(e.target.value)}
              className="bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-white focus:border-zinc-600 focus:outline-none"
              data-testid="history-filter"
            >
              <option value="">All Scenarios</option>
              {scenarios.map(s => <option key={s.key} value={s.key}>{s.label}</option>)}
            </select>
            <button
              onClick={() => setFavoritesOnly(!favoritesOnly)}
              className={`px-3 py-2 text-sm border transition-colors flex items-center gap-1.5 ${
                favoritesOnly ? 'border-amber-600 text-amber-400 bg-amber-900/20' : 'border-zinc-700 text-zinc-400'
              }`}
              data-testid="favorites-filter"
            >
              <Star className="w-3.5 h-3.5" /> Saved
            </button>
          </div>

          {historyLoading ? (
            <div className="text-center py-12 text-zinc-500 text-sm animate-pulse">Loading history...</div>
          ) : history.length === 0 ? (
            <div className="border border-zinc-800 p-12 text-center">
              <Clock className="w-8 h-8 text-zinc-600 mx-auto mb-3" />
              <p className="text-zinc-500 text-sm">No drafts yet</p>
            </div>
          ) : (
            <div className="border border-zinc-800 divide-y divide-zinc-800">
              {history.map((d, idx) => (
                <HistoryItem
                  key={d.id}
                  draft={d}
                  idx={idx}
                  expanded={expandedDraft === d.id}
                  onToggle={() => setExpandedDraft(expandedDraft === d.id ? null : d.id)}
                  onDuplicate={() => handleDuplicate(d.id)}
                  onFavorite={() => handleToggleFavorite(d.id)}
                  onDelete={() => handleDeleteDraft(d.id)}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function HistoryItem({ draft, idx, expanded, onToggle, onDuplicate, onFavorite, onDelete }) {
  const [copied, setCopied] = useState(false);

  const copyVariant = (body) => {
    let text = body;
    if (draft.channel === 'email' && draft.subject) {
      text = `Subject: ${draft.subject}\n\n${body}`;
    }
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const ChannelIcon = CHANNEL_CONFIG[draft.channel]?.icon || Mail;

  return (
    <div data-testid={`history-item-${idx}`}>
      <div
        onClick={onToggle}
        className="p-3 cursor-pointer hover:bg-zinc-900/60 transition-colors flex items-center gap-3"
      >
        <ChannelIcon className="w-4 h-4 text-zinc-500 shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="text-sm text-white truncate">{draft.scenario_label}</div>
          <div className="text-xs text-zinc-500 mt-0.5">
            {new Date(draft.created_at).toLocaleString()}
            {draft.context_fields?.order_number && <span> &middot; #{draft.context_fields.order_number}</span>}
            {draft.context_fields?.customer_name && <span> &middot; {draft.context_fields.customer_name}</span>}
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {draft.max_discretion && <Shield className="w-3 h-3 text-amber-400" title="Max Discretion" />}
          {draft.is_favorite && <Star className="w-3 h-3 text-amber-400 fill-amber-400" />}
          {expanded ? <ChevronUp className="w-4 h-4 text-zinc-500" /> : <ChevronDown className="w-4 h-4 text-zinc-500" />}
        </div>
      </div>

      {expanded && (
        <div className="px-3 pb-4 space-y-3">
          {draft.subject && (
            <div className="text-xs text-zinc-400">
              <span className="text-zinc-600">Subject:</span> {draft.subject}
            </div>
          )}

          <div className="grid grid-cols-3 gap-2">
            {draft.variants?.map(v => (
              <div key={v.type} className="border border-zinc-800 p-3">
                <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1.5">{VARIANT_LABELS[v.type] || v.type}</div>
                <div className="text-xs text-zinc-300 whitespace-pre-wrap line-clamp-6">{v.body}</div>
                <button
                  onClick={(e) => { e.stopPropagation(); copyVariant(v.body); }}
                  className="mt-2 flex items-center gap-1 text-[10px] text-zinc-500 hover:text-white transition-colors"
                  data-testid={`copy-variant-${v.type}-${idx}`}
                >
                  {copied ? <Check className="w-2.5 h-2.5 text-emerald-400" /> : <Copy className="w-2.5 h-2.5" />}
                  {copied ? 'Copied' : 'Copy'}
                </button>
              </div>
            ))}
          </div>

          <div className="flex items-center gap-2">
            <button onClick={(e) => { e.stopPropagation(); onDuplicate(); }}
              className="text-xs px-2 py-1 border border-zinc-700 text-zinc-400 hover:text-white transition-colors"
              data-testid={`duplicate-${idx}`}
            >
              Duplicate & Edit
            </button>
            <button onClick={(e) => { e.stopPropagation(); onFavorite(); }}
              className={`text-xs px-2 py-1 border transition-colors flex items-center gap-1 ${
                draft.is_favorite ? 'border-amber-600 text-amber-400' : 'border-zinc-700 text-zinc-400 hover:text-white'
              }`}
              data-testid={`favorite-${idx}`}
            >
              <Star className="w-3 h-3" /> {draft.is_favorite ? 'Saved' : 'Save'}
            </button>
            <button onClick={(e) => { e.stopPropagation(); onDelete(); }}
              className="text-xs px-2 py-1 text-red-500/50 hover:text-red-400 transition-colors"
              data-testid={`delete-${idx}`}
            >
              <Trash2 className="w-3 h-3" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
