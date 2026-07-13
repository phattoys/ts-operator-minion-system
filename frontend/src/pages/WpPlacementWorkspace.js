import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import {
  Globe, FileText, Plus, RefreshCw, ChevronDown, ChevronUp,
  Check, AlertTriangle, Copy, Clock, ArrowRight,
  Settings, Layers, Upload, Code, X,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const TEMPLATE_COLORS = {
  standard_content: 'border-emerald-800/40 text-emerald-400',
  category_support: 'border-blue-800/40 text-blue-400',
  local_seo_landing: 'border-purple-800/40 text-purple-400',
};

export default function WpPlacementWorkspace() {
  const [templates, setTemplates] = useState([]);
  const [wpConnected, setWpConnected] = useState(false);
  const [stats, setStats] = useState(null);
  const [view, setView] = useState('place'); // place | log | drafts | settings
  const [settings, setSettings] = useState(null);

  // Placement form
  const [mode, setMode] = useState('create');
  const [templateId, setTemplateId] = useState('standard_content');
  const [targetPageId, setTargetPageId] = useState('');
  const [form, setForm] = useState({
    page_title: '', slug: '', page_type: '',
    hero_headline: '', subheadline: '', intro: '',
    body_section_1: '', body_section_2: '', body_section_3: '',
    cta_text: '', cta_url: '',
    seo_title: '', meta_description: '',
  });
  const [relatedLinks, setRelatedLinks] = useState([]);
  const [linkTitle, setLinkTitle] = useState('');
  const [linkUrl, setLinkUrl] = useState('');
  const [placing, setPlacing] = useState(false);
  const [result, setResult] = useState(null);

  // Log / Drafts
  const [logs, setLogs] = useState([]);
  const [drafts, setDrafts] = useState([]);
  const [expandedLog, setExpandedLog] = useState(null);
  const [showPreview, setShowPreview] = useState(null);

  // Import
  const [showImport, setShowImport] = useState(false);
  const [approvedPages, setApprovedPages] = useState([]);
  const [importLoading, setImportLoading] = useState(false);

  useEffect(() => {
    fetchTemplates();
    fetchStats();
  }, []);

  const fetchTemplates = async () => {
    try {
      const res = await axios.get(`${API}/wp-placement/templates`, { withCredentials: true });
      setTemplates(res.data.templates || []);
      setWpConnected(res.data.wp_connected);
    } catch (err) { console.error(err); }
  };

  const fetchStats = async () => {
    try {
      const res = await axios.get(`${API}/wp-placement/stats`, { withCredentials: true });
      setStats(res.data);
    } catch (err) { console.error(err); }
  };

  const fetchLogs = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/wp-placement/log`, { withCredentials: true });
      setLogs(res.data.placements || []);
    } catch (err) { console.error(err); }
  }, []);

  const fetchDrafts = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/wp-placement/drafts`, { withCredentials: true });
      setDrafts(res.data.pages || []);
    } catch (err) { console.error(err); }
  }, []);

  const fetchSettings = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/wp-placement/settings`, { withCredentials: true });
      setSettings(res.data);
    } catch (err) { console.error(err); }
  }, []);

  useEffect(() => {
    if (view === 'log') fetchLogs();
    if (view === 'drafts') fetchDrafts();
    if (view === 'settings') fetchSettings();
  }, [view, fetchLogs, fetchDrafts, fetchSettings]);

  const updateForm = (field, value) => setForm(prev => ({ ...prev, [field]: value }));

  const addLink = () => {
    if (linkTitle.trim() || linkUrl.trim()) {
      setRelatedLinks(prev => [...prev, { title: linkTitle.trim() || linkUrl.trim(), url: linkUrl.trim() }]);
      setLinkTitle('');
      setLinkUrl('');
    }
  };

  const removeLink = (idx) => setRelatedLinks(prev => prev.filter((_, i) => i !== idx));

  const handlePlace = async () => {
    if (!form.page_title.trim()) return;
    setPlacing(true);
    setResult(null);
    try {
      const payload = {
        mode,
        template_id: templateId,
        ...form,
        related_links: relatedLinks.length > 0 ? relatedLinks : null,
      };
      if (mode === 'update') payload.target_page_id = targetPageId;
      const res = await axios.post(`${API}/wp-placement/place`, payload, { withCredentials: true });
      setResult(res.data);
      fetchStats();
    } catch (err) {
      setResult({ error: err.response?.data?.detail || 'Placement failed' });
    }
    setPlacing(false);
  };

  const handleImportPage = async (pageId) => {
    setImportLoading(true);
    try {
      const res = await axios.post(`${API}/wp-placement/import-from-pages/${pageId}`, {}, { withCredentials: true });
      const pre = res.data.prefilled;
      const inf = res.data.inference;
      setForm({
        page_title: pre.page_title || '', slug: pre.slug || '', page_type: pre.page_type || '',
        hero_headline: pre.hero_headline || '', subheadline: '', intro: pre.intro || '',
        body_section_1: pre.body_section_1 || '', body_section_2: pre.body_section_2 || '',
        body_section_3: pre.body_section_3 || '',
        cta_text: '', cta_url: '', seo_title: '', meta_description: '',
      });
      if (inf?.template_id) setTemplateId(inf.template_id);
      setShowImport(false);
      setResult(null);
    } catch (err) {
      alert(err.response?.data?.detail || 'Import failed');
    }
    setImportLoading(false);
  };

  const fetchApprovedPages = async () => {
    try {
      const res = await axios.get(`${API}/pages?status=Approved`, { withCredentials: true });
      setApprovedPages(res.data.pages || []);
    } catch {
      try {
        const res = await axios.get(`${API}/pages`, { withCredentials: true });
        setApprovedPages((res.data.pages || []).filter(p => p.generated_content));
      } catch (err) { console.error(err); setApprovedPages([]); }
    }
    setShowImport(true);
  };

  const handleSaveSettings = async (updates) => {
    try {
      const res = await axios.put(`${API}/wp-placement/settings`, updates, { withCredentials: true });
      setSettings(res.data);
    } catch (err) { alert('Failed to save settings'); }
  };

  const resetForm = () => {
    setForm({ page_title: '', slug: '', page_type: '', hero_headline: '', subheadline: '', intro: '', body_section_1: '', body_section_2: '', body_section_3: '', cta_text: '', cta_url: '', seo_title: '', meta_description: '' });
    setRelatedLinks([]);
    setResult(null);
    setTargetPageId('');
  };

  return (
    <div className="p-8 max-w-[1400px] mx-auto" data-testid="wp-placement-workspace">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-['Outfit'] font-light text-white tracking-tight">
            WP Page Placement
          </h1>
          <div className="flex items-center gap-3 mt-1">
            <p className="text-sm text-zinc-500">Map content into WordPress page templates</p>
            <span className={`px-2 py-0.5 text-[10px] uppercase tracking-wider ${wpConnected ? 'bg-emerald-900/30 text-emerald-400' : 'bg-zinc-800 text-zinc-500'}`} data-testid="wp-status-badge">
              {wpConnected ? 'WP Connected' : 'Mock Mode'}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={fetchApprovedPages} className="flex items-center gap-2 px-3 py-2 border border-zinc-700 text-zinc-300 text-sm hover:bg-zinc-800" data-testid="import-page-btn">
            <Upload className="w-4 h-4" /> Import from Page Ops
          </button>
        </div>
      </div>

      {/* Stats bar */}
      {stats && (
        <div className="grid grid-cols-4 gap-4 mb-6" data-testid="wp-stats">
          <MiniStat label="Placements" value={stats.total_placements} />
          <MiniStat label="Created" value={stats.creates} color="text-emerald-400" />
          <MiniStat label="Updated" value={stats.updates} color="text-blue-400" />
          <MiniStat label="WP Status" value={wpConnected ? 'Live' : 'Mock'} color={wpConnected ? 'text-emerald-400' : 'text-zinc-500'} />
        </div>
      )}

      {/* View tabs */}
      <div className="flex items-center gap-1 mb-6 border-b border-zinc-800" data-testid="view-tabs">
        {[
          { key: 'place', label: 'Place Content', icon: Globe },
          { key: 'log', label: 'Placement Log', icon: Clock },
          { key: 'drafts', label: 'Drafts', icon: FileText },
          { key: 'settings', label: 'Settings', icon: Settings },
        ].map(tab => (
          <button
            key={tab.key}
            onClick={() => setView(tab.key)}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm border-b-2 -mb-[1px] transition-colors ${
              view === tab.key ? 'border-white text-white' : 'border-transparent text-zinc-500 hover:text-zinc-300'
            }`}
            data-testid={`tab-${tab.key}`}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Place Content */}
      {view === 'place' && (
        <div className="grid grid-cols-3 gap-6">
          <div className="col-span-2 space-y-4">
            {/* Mode + Template */}
            <div className="flex gap-4">
              <div className="flex-1">
                <Label>Mode</Label>
                <div className="flex gap-2">
                  <ModeBtn active={mode === 'create'} onClick={() => setMode('create')} label="Create Draft" testid="mode-create" />
                  <ModeBtn active={mode === 'update'} onClick={() => setMode('update')} label="Update Draft" testid="mode-update" />
                </div>
              </div>
              <div className="flex-1">
                <Label>Template</Label>
                <select value={templateId} onChange={e => setTemplateId(e.target.value)} className="w-full bg-zinc-900 border border-zinc-800 text-zinc-300 text-sm px-3 py-2 focus:outline-none" data-testid="template-select">
                  {templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                </select>
              </div>
            </div>

            {mode === 'update' && (
              <Field label="Target Page ID" value={targetPageId} onChange={setTargetPageId} testid="target-page-id" placeholder="wp-xxxxxxxx" />
            )}

            <div className="grid grid-cols-2 gap-4">
              <Field label="Page Title *" value={form.page_title} onChange={v => updateForm('page_title', v)} testid="field-page-title" />
              <Field label="Slug" value={form.slug} onChange={v => updateForm('slug', v)} testid="field-slug" placeholder="auto-generated if empty" />
            </div>

            <Field label="Hero Headline" value={form.hero_headline} onChange={v => updateForm('hero_headline', v)} testid="field-hero" />
            <Field label="Subheadline" value={form.subheadline} onChange={v => updateForm('subheadline', v)} testid="field-sub" />
            <TextArea label="Intro Paragraph" value={form.intro} onChange={v => updateForm('intro', v)} testid="field-intro" rows={3} />
            <TextArea label="Body Section 1" value={form.body_section_1} onChange={v => updateForm('body_section_1', v)} testid="field-body1" rows={4} />
            <TextArea label="Body Section 2" value={form.body_section_2} onChange={v => updateForm('body_section_2', v)} testid="field-body2" rows={3} />
            <TextArea label="Body Section 3" value={form.body_section_3} onChange={v => updateForm('body_section_3', v)} testid="field-body3" rows={3} />

            <div className="grid grid-cols-2 gap-4">
              <Field label="CTA Text" value={form.cta_text} onChange={v => updateForm('cta_text', v)} testid="field-cta-text" placeholder="e.g. Shop Now" />
              <Field label="CTA URL" value={form.cta_url} onChange={v => updateForm('cta_url', v)} testid="field-cta-url" placeholder="/shop" />
            </div>

            {/* Related Links */}
            <div>
              <Label>Related Links</Label>
              {relatedLinks.length > 0 && (
                <div className="space-y-1 mb-2">
                  {relatedLinks.map((link, i) => (
                    <div key={i} className="flex items-center gap-2 text-sm text-zinc-300 bg-zinc-900 px-3 py-1.5 border border-zinc-800">
                      <span className="flex-1 truncate">{link.title} → {link.url}</span>
                      <button onClick={() => removeLink(i)} className="text-zinc-600 hover:text-red-400"><X className="w-3 h-3" /></button>
                    </div>
                  ))}
                </div>
              )}
              <div className="flex gap-2">
                <input value={linkTitle} onChange={e => setLinkTitle(e.target.value)} placeholder="Link title" className="flex-1 bg-zinc-900 border border-zinc-800 text-white text-sm px-3 py-1.5 placeholder-zinc-600 focus:outline-none" data-testid="link-title-input" />
                <input value={linkUrl} onChange={e => setLinkUrl(e.target.value)} placeholder="URL" className="flex-1 bg-zinc-900 border border-zinc-800 text-white text-sm px-3 py-1.5 placeholder-zinc-600 focus:outline-none" data-testid="link-url-input" />
                <button onClick={addLink} className="px-3 py-1.5 border border-zinc-700 text-zinc-400 text-sm hover:bg-zinc-800" data-testid="add-link-btn">Add</button>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <Field label="SEO Title" value={form.seo_title} onChange={v => updateForm('seo_title', v)} testid="field-seo-title" />
              <Field label="Meta Description" value={form.meta_description} onChange={v => updateForm('meta_description', v)} testid="field-meta-desc" />
            </div>

            <div className="flex gap-3 pt-2">
              <button onClick={handlePlace} disabled={placing || !form.page_title.trim()} className="flex items-center gap-2 px-6 py-2.5 bg-white text-black text-sm font-medium hover:bg-zinc-200 disabled:opacity-50" data-testid="run-placement-btn">
                <Globe className="w-4 h-4" />
                {placing ? 'Placing...' : mode === 'create' ? 'Create Page Draft' : 'Update Page Draft'}
              </button>
              <button onClick={resetForm} className="px-4 py-2.5 text-zinc-500 text-sm hover:text-white" data-testid="reset-form-btn">Reset</button>
            </div>
          </div>

          {/* Right panel — template info + result */}
          <div className="space-y-4">
            <TemplateInfo templates={templates} activeId={templateId} />
            {result && <PlacementResult result={result} />}
          </div>
        </div>
      )}

      {/* Log View */}
      {view === 'log' && <LogView logs={logs} expandedLog={expandedLog} setExpandedLog={setExpandedLog} showPreview={showPreview} setShowPreview={setShowPreview} />}

      {/* Drafts View */}
      {view === 'drafts' && <DraftsView drafts={drafts} showPreview={showPreview} setShowPreview={setShowPreview} onSelect={(id) => { setTargetPageId(id); setMode('update'); setView('place'); }} />}

      {/* Settings */}
      {view === 'settings' && settings && <SettingsView settings={settings} onSave={handleSaveSettings} />}

      {/* Import Modal */}
      {showImport && (
        <ImportModal
          pages={approvedPages}
          loading={importLoading}
          onImport={handleImportPage}
          onClose={() => setShowImport(false)}
        />
      )}
    </div>
  );
}

// ================== SUB COMPONENTS ==================

function MiniStat({ label, value, color = 'text-white' }) {
  return (
    <div className="border border-zinc-800 p-3">
      <div className={`text-xl font-['Outfit'] ${color}`}>{value}</div>
      <div className="text-[10px] text-zinc-600 uppercase tracking-wider mt-0.5">{label}</div>
    </div>
  );
}

function Label({ children }) {
  return <label className="block text-xs text-zinc-500 uppercase tracking-wider mb-1.5">{children}</label>;
}

function Field({ label, value, onChange, testid, placeholder }) {
  return (
    <div>
      <Label>{label}</Label>
      <input value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder} className="w-full bg-zinc-900 border border-zinc-800 text-white text-sm px-3 py-2 placeholder-zinc-600 focus:outline-none focus:border-zinc-600" data-testid={testid} />
    </div>
  );
}

function TextArea({ label, value, onChange, testid, rows = 3 }) {
  return (
    <div>
      <Label>{label}</Label>
      <textarea value={value} onChange={e => onChange(e.target.value)} rows={rows} className="w-full bg-zinc-900 border border-zinc-800 text-white text-sm px-3 py-2 placeholder-zinc-600 focus:outline-none focus:border-zinc-600 resize-none" data-testid={testid} />
    </div>
  );
}

function ModeBtn({ active, onClick, label, testid }) {
  return (
    <button onClick={onClick} className={`flex-1 px-3 py-2 text-sm border transition-colors ${active ? 'border-white text-white bg-zinc-800' : 'border-zinc-800 text-zinc-500 hover:text-zinc-300'}`} data-testid={testid}>
      {label}
    </button>
  );
}

function TemplateInfo({ templates, activeId }) {
  const tpl = templates.find(t => t.id === activeId);
  if (!tpl) return null;
  return (
    <div className={`border p-4 ${TEMPLATE_COLORS[activeId] || 'border-zinc-800 text-zinc-400'}`} data-testid="template-info">
      <div className="text-sm font-medium text-white mb-1">{tpl.name}</div>
      <div className="text-xs text-zinc-500 mb-3">{tpl.description}</div>
      <div className="text-[10px] text-zinc-600 uppercase tracking-wider mb-1">Use for:</div>
      <div className="flex flex-wrap gap-1 mb-3">
        {tpl.use_for.map(u => (
          <span key={u} className="px-1.5 py-0.5 bg-zinc-800 text-zinc-400 text-[10px]">{u}</span>
        ))}
      </div>
      {tpl.required_sections?.length > 0 && (
        <div className="mb-2">
          <div className="text-[10px] text-zinc-600 uppercase tracking-wider mb-1">Required Sections:</div>
          {tpl.required_sections.map(s => (
            <div key={s} className="text-xs text-emerald-400 flex items-center gap-1"><Check className="w-3 h-3" /> {s}</div>
          ))}
        </div>
      )}
      {tpl.optional_sections?.length > 0 && (
        <div>
          <div className="text-[10px] text-zinc-600 uppercase tracking-wider mb-1">Optional:</div>
          {tpl.optional_sections.map(s => (
            <div key={s} className="text-xs text-zinc-500">{s}</div>
          ))}
        </div>
      )}
    </div>
  );
}

function PlacementResult({ result }) {
  if (result.error) {
    return (
      <div className="border border-red-800/40 p-4" data-testid="placement-error">
        <div className="text-red-400 text-sm flex items-center gap-2"><AlertTriangle className="w-4 h-4" /> {result.error}</div>
      </div>
    );
  }

  const p = result.placement;
  return (
    <div className="border border-emerald-800/40 p-4 space-y-3" data-testid="placement-result">
      <div className="text-emerald-400 text-sm flex items-center gap-2">
        <Check className="w-4 h-4" />
        {p.mode === 'create' ? 'Page draft created' : 'Page draft updated'}
      </div>
      <div className="text-white text-sm font-medium">{p.page_title}</div>
      <div className="text-xs text-zinc-500">{p.template_name}</div>
      <div className="text-xs text-zinc-500">ID: {p.page_id}</div>

      {p.inference && (
        <div className={`text-xs px-2 py-1 border ${p.inference.needs_review ? 'border-amber-800/30 text-amber-400' : 'border-emerald-800/30 text-emerald-400'}`} data-testid="inference-result">
          Auto-inferred: {p.inference.confidence} confidence
          {p.inference.matched_keywords?.length > 0 && (
            <span className="text-zinc-500 ml-1">({p.inference.matched_keywords.join(', ')})</span>
          )}
          {p.inference.needs_review && <span className="text-amber-400 ml-1"> — verify selection</span>}
        </div>
      )}

      {p.sections_placed.length > 0 && (
        <div>
          <div className="text-[10px] text-zinc-600 uppercase tracking-wider mb-1">Placed</div>
          {p.sections_placed.map((s, i) => (
            <div key={i} className="text-xs text-emerald-400 flex items-center gap-1">
              <Check className="w-3 h-3" /> {s.label}
              {s.ux_block && <span className="text-zinc-600 ml-1">({s.ux_block})</span>}
            </div>
          ))}
        </div>
      )}

      {p.sections_skipped.length > 0 && (
        <div>
          <div className="text-[10px] text-zinc-600 uppercase tracking-wider mb-1">Skipped</div>
          {p.sections_skipped.map((s, i) => (
            <div key={i} className="text-xs text-zinc-500">
              {s.label}: {s.reason}
              {s.required && <span className="text-amber-400 ml-1">(required)</span>}
            </div>
          ))}
        </div>
      )}

      {p.warnings.length > 0 && (
        <div>
          <div className="text-[10px] text-zinc-600 uppercase tracking-wider mb-1">Warnings</div>
          {p.warnings.map((w, i) => (
            <div key={i} className="text-xs text-amber-400 flex items-center gap-1"><AlertTriangle className="w-3 h-3" /> {w}</div>
          ))}
        </div>
      )}

      {!p.wp_connected && <div className="text-[10px] text-zinc-600 mt-2">Mock mode — add WP credentials to push to WordPress</div>}
    </div>
  );
}

function LogView({ logs, expandedLog, setExpandedLog, showPreview, setShowPreview }) {
  if (logs.length === 0) {
    return <div className="text-center py-16 text-zinc-500 text-sm" data-testid="log-empty">No placements yet</div>;
  }
  return (
    <div className="space-y-2" data-testid="placement-log">
      {logs.map((log, idx) => (
        <div key={log.id} className="border border-zinc-800" data-testid={`log-${log.id}`}>
          <div className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-zinc-900/50" onClick={() => setExpandedLog(expandedLog === idx ? null : idx)}>
            <span className={`px-1.5 py-0.5 text-[10px] uppercase ${log.mode === 'create' ? 'bg-emerald-900/30 text-emerald-400' : 'bg-blue-900/30 text-blue-400'}`}>{log.mode}</span>
            <span className="text-white text-sm flex-1 truncate">{log.page_title}</span>
            <span className="text-zinc-600 text-xs">{log.template_name?.split('—')[0]}</span>
            <span className="text-zinc-600 text-xs">{new Date(log.created_at).toLocaleString()}</span>
            {expandedLog === idx ? <ChevronUp className="w-4 h-4 text-zinc-600" /> : <ChevronDown className="w-4 h-4 text-zinc-600" />}
          </div>
          {expandedLog === idx && (
            <div className="border-t border-zinc-800 px-4 py-3 text-xs space-y-2">
              <div className="grid grid-cols-3 gap-4">
                <div><span className="text-zinc-600">Page ID:</span> <span className="text-zinc-300">{log.page_id}</span></div>
                <div><span className="text-zinc-600">Template:</span> <span className="text-zinc-300">{log.template_id}</span></div>
                <div><span className="text-zinc-600">Status:</span> <span className="text-zinc-300">{log.status}</span></div>
              </div>
              <div className="flex gap-4">
                <span className="text-emerald-400">{log.sections_placed?.length || 0} placed</span>
                <span className="text-zinc-500">{log.sections_skipped?.length || 0} skipped</span>
                <span className="text-amber-400">{log.warnings?.length || 0} warnings</span>
              </div>
              {log.warnings?.length > 0 && log.warnings.map((w, i) => (
                <div key={i} className="text-amber-400 flex items-center gap-1"><AlertTriangle className="w-3 h-3" /> {w}</div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function DraftsView({ drafts, showPreview, setShowPreview, onSelect }) {
  if (drafts.length === 0) {
    return <div className="text-center py-16 text-zinc-500 text-sm" data-testid="drafts-empty">No drafts yet</div>;
  }
  return (
    <div className="space-y-2" data-testid="drafts-list">
      {drafts.map(d => (
        <div key={d.id} className="border border-zinc-800 px-4 py-3 flex items-center gap-3" data-testid={`draft-${d.id}`}>
          <div className="flex-1">
            <div className="text-white text-sm">{d.title}</div>
            <div className="text-zinc-600 text-xs">/{d.slug} · {d.status}</div>
          </div>
          <button onClick={() => setShowPreview(showPreview === d.id ? null : d.id)} className="px-2 py-1 text-xs text-zinc-500 border border-zinc-800 hover:text-white">
            <Code className="w-3 h-3" />
          </button>
          <button onClick={() => onSelect(d.id)} className="px-3 py-1 text-xs border border-zinc-700 text-zinc-400 hover:bg-zinc-800" data-testid={`select-draft-${d.id}`}>
            Update This
          </button>
          {showPreview === d.id && (
            <div className="absolute right-8 mt-2 w-[600px] max-h-[400px] overflow-y-auto bg-zinc-900 border border-zinc-700 p-4 z-50">
              <pre className="text-[11px] text-zinc-400 whitespace-pre-wrap">{d.content}</pre>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function SettingsView({ settings, onSave }) {
  const [local, setLocal] = useState(settings);
  const toggle = (key) => {
    const updated = { ...local, [key]: !local[key] };
    setLocal(updated);
    onSave({ [key]: updated[key] });
  };

  return (
    <div className="max-w-lg space-y-4" data-testid="wp-settings">
      <div className="text-sm text-white mb-4">WordPress Placement Settings</div>
      <SettingToggle label="Preserve slug on update" value={local.preserve_slug_on_update} onToggle={() => toggle('preserve_slug_on_update')} testid="setting-preserve-slug" />
      <SettingToggle label="Preserve unmapped content on update" value={local.preserve_unmapped_on_update} onToggle={() => toggle('preserve_unmapped_on_update')} testid="setting-preserve-unmapped" />
      <SettingToggle label="Flag missing CTA" value={local.flag_missing_cta} onToggle={() => toggle('flag_missing_cta')} testid="setting-flag-cta" />
      <SettingToggle label="Save placement log" value={local.save_placement_log} onToggle={() => toggle('save_placement_log')} testid="setting-save-log" />
      <div>
        <Label>Default Draft Status</Label>
        <select value={local.default_status} onChange={e => { setLocal(prev => ({ ...prev, default_status: e.target.value })); onSave({ default_status: e.target.value }); }} className="bg-zinc-900 border border-zinc-800 text-zinc-300 text-sm px-3 py-2 focus:outline-none" data-testid="setting-default-status">
          <option value="draft">Draft</option>
          <option value="pending">Pending Review</option>
        </select>
      </div>
      {!settings.wp_connected && (
        <div className="mt-6 border border-zinc-800 p-4 text-xs text-zinc-500">
          <div className="text-zinc-400 text-sm mb-1">WordPress Connection</div>
          Currently in <strong>Mock Mode</strong>. To connect to a live WordPress site, add these to your backend .env:
          <pre className="mt-2 text-zinc-600 bg-zinc-900 p-2">WP_SITE_URL=https://yoursite.com{'\n'}WP_USERNAME=your_wp_user{'\n'}WP_APP_PASSWORD=your_app_password</pre>
        </div>
      )}
    </div>
  );
}

function SettingToggle({ label, value, onToggle, testid }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-zinc-800/50">
      <span className="text-sm text-zinc-300">{label}</span>
      <button onClick={onToggle} className={`w-10 h-5 rounded-full flex items-center px-0.5 transition-colors ${value ? 'bg-emerald-600' : 'bg-zinc-700'}`} data-testid={testid}>
        <div className={`w-4 h-4 rounded-full bg-white transition-transform ${value ? 'translate-x-5' : 'translate-x-0'}`} />
      </button>
    </div>
  );
}

function ImportModal({ pages, loading, onImport, onClose }) {
  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50" data-testid="import-modal">
      <div className="bg-zinc-900 border border-zinc-700 p-6 w-full max-w-lg max-h-[80vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-['Outfit'] text-white">Import from Page Ops</h2>
          <button onClick={onClose} className="text-zinc-500 hover:text-white"><X className="w-4 h-4" /></button>
        </div>
        {pages.length === 0 ? (
          <p className="text-zinc-500 text-sm">No pages with generated content found.</p>
        ) : (
          <div className="space-y-2">
            <p className="text-zinc-500 text-xs mb-3">Select a page to prefill the placement form:</p>
            {pages.map(p => (
              <div key={p.id} className="flex items-center gap-3 px-3 py-2 border border-zinc-800 hover:border-zinc-600 cursor-pointer" onClick={() => !loading && onImport(p.id)} data-testid={`import-page-${p.id}`}>
                <div className="flex-1">
                  <div className="text-white text-sm">{p.page_name}</div>
                  <div className="text-zinc-600 text-xs">{p.page_family} · {p.page_type} · {p.status}</div>
                </div>
                <ArrowRight className="w-4 h-4 text-zinc-600" />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
