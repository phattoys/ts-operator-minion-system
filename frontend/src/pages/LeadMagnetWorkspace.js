import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import {
  ArrowLeft, Wand2, FileDown, Eye, Send, Archive, CheckCircle,
  Clock, RefreshCw, Copy, Check, Download, History, RotateCcw,
  Trash2, Edit3, ChevronDown,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const STATUS_CONFIG = {
  Draft: { color: 'text-zinc-400 bg-zinc-800 border-zinc-700', icon: Clock },
  Ready: { color: 'text-amber-400 bg-amber-900/30 border-amber-800', icon: Send },
  Published: { color: 'text-emerald-400 bg-emerald-900/30 border-emerald-800', icon: CheckCircle },
  Archived: { color: 'text-zinc-500 bg-zinc-800/50 border-zinc-700', icon: Archive },
};

export default function LeadMagnetWorkspace() {
  const { magnetId } = useParams();
  const navigate = useNavigate();
  const [magnet, setMagnet] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [generatingPdf, setGeneratingPdf] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [activeTab, setActiveTab] = useState('content');
  const [editing, setEditing] = useState(false);
  const [editFields, setEditFields] = useState({});
  const [saving, setSaving] = useState(false);
  const [copied, setCopied] = useState(null);
  const [versions, setVersions] = useState([]);
  const [showVersions, setShowVersions] = useState(false);

  const fetchMagnet = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/lead-magnets/${magnetId}`, { withCredentials: true });
      setMagnet(res.data);
    } catch (err) {
      console.error('Failed to fetch lead magnet:', err);
    }
    setLoading(false);
  }, [magnetId]);

  useEffect(() => { fetchMagnet(); }, [fetchMagnet]);

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const res = await axios.post(`${API}/lead-magnets/${magnetId}/generate`, {}, { withCredentials: true });
      setMagnet(res.data);
      setActiveTab('content');
    } catch (err) {
      console.error('Generation failed:', err);
      alert(err.response?.data?.detail || 'Generation failed. Please try again.');
    }
    setGenerating(false);
  };

  const handleGeneratePdf = async () => {
    setGeneratingPdf(true);
    try {
      await axios.post(`${API}/lead-magnets/${magnetId}/generate-pdf`, {}, { withCredentials: true });
      await fetchMagnet();
    } catch (err) {
      console.error('PDF generation failed:', err);
      alert(err.response?.data?.detail || 'PDF generation failed.');
    }
    setGeneratingPdf(false);
  };

  const handlePreviewPdf = () => {
    window.open(`${API}/lead-magnets/${magnetId}/preview-pdf`, '_blank');
  };

  const handleMarkReady = async () => {
    try {
      const res = await axios.post(`${API}/lead-magnets/${magnetId}/mark-ready`, {}, { withCredentials: true });
      setMagnet(res.data);
    } catch (err) {
      alert(err.response?.data?.detail || 'Cannot mark ready.');
    }
  };

  const handlePublish = async () => {
    setPublishing(true);
    try {
      const res = await axios.post(`${API}/lead-magnets/${magnetId}/publish`, {}, { withCredentials: true });
      setMagnet(res.data);
    } catch (err) {
      alert(err.response?.data?.detail || 'Cannot publish.');
    }
    setPublishing(false);
  };

  const handleArchive = async () => {
    if (!window.confirm('Archive this lead magnet? It will no longer be downloadable.')) return;
    try {
      const res = await axios.post(`${API}/lead-magnets/${magnetId}/archive`, {}, { withCredentials: true });
      setMagnet(res.data);
    } catch (err) {
      alert(err.response?.data?.detail || 'Cannot archive.');
    }
  };

  const handleDelete = async () => {
    if (!window.confirm('Delete this lead magnet permanently?')) return;
    try {
      await axios.delete(`${API}/lead-magnets/${magnetId}`, { withCredentials: true });
      navigate('/lead-magnets');
    } catch (err) {
      alert(err.response?.data?.detail || 'Cannot delete.');
    }
  };

  const startEditing = () => {
    setEditing(true);
    setEditFields({
      title: magnet.title || '',
      subtitle: magnet.subtitle || '',
      description: magnet.description || '',
      markdown_content: magnet.markdown_content || '',
      landing_headline: magnet.landing_headline || '',
      landing_body: magnet.landing_body || '',
      landing_cta: magnet.landing_cta || '',
    });
  };

  const saveEdits = async () => {
    setSaving(true);
    try {
      const res = await axios.put(`${API}/lead-magnets/${magnetId}`, editFields, { withCredentials: true });
      setMagnet(res.data);
      setEditing(false);
    } catch (err) {
      console.error('Save failed:', err);
    }
    setSaving(false);
  };

  const copyToClipboard = (text, label) => {
    navigator.clipboard.writeText(text);
    setCopied(label);
    setTimeout(() => setCopied(null), 2000);
  };

  const fetchVersions = async () => {
    try {
      const res = await axios.get(`${API}/lead-magnets/${magnetId}/versions`, { withCredentials: true });
      setVersions(res.data.versions || []);
      setShowVersions(true);
    } catch (err) {
      console.error('Failed to fetch versions:', err);
    }
  };

  const restoreVersion = async (versionId) => {
    if (!window.confirm('Restore this version? Current content will be saved as a new version first.')) return;
    try {
      const res = await axios.post(`${API}/lead-magnets/${magnetId}/versions/${versionId}/restore`, {}, { withCredentials: true });
      setMagnet(res.data);
      setShowVersions(false);
    } catch (err) {
      console.error('Restore failed:', err);
    }
  };

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[50vh]">
        <div className="text-zinc-500 text-sm animate-pulse">Loading...</div>
      </div>
    );
  }

  if (!magnet) {
    return (
      <div className="p-8 text-center">
        <p className="text-zinc-500">Lead magnet not found.</p>
        <button onClick={() => navigate('/lead-magnets')} className="mt-4 text-sm text-white underline">Back to Library</button>
      </div>
    );
  }

  const StatusConf = STATUS_CONFIG[magnet.status] || STATUS_CONFIG.Draft;
  const StatusIcon = StatusConf.icon;
  const hasContent = !!magnet.markdown_content;

  return (
    <div className="p-8 max-w-[1200px] mx-auto" data-testid="lead-magnet-workspace">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => navigate('/lead-magnets')}
          className="p-2 text-zinc-500 hover:text-white transition-colors"
          data-testid="back-to-library-btn"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div className="flex-1 min-w-0">
          <h1 className="text-2xl font-['Outfit'] font-light text-white tracking-tight truncate">
            {magnet.title || magnet.topic}
          </h1>
          <div className="flex items-center gap-3 mt-1">
            <span className={`text-xs px-2 py-0.5 border flex items-center gap-1.5 ${StatusConf.color}`}>
              <StatusIcon className="w-3 h-3" />
              {magnet.status}
            </span>
            <span className="text-xs text-zinc-600">{magnet.format_type}</span>
            {magnet.district_tag && <span className="text-xs text-zinc-600">{magnet.district_tag}</span>}
            {magnet.download_count > 0 && (
              <span className="text-xs text-zinc-500 flex items-center gap-1">
                <Download className="w-3 h-3" /> {magnet.download_count}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Action Bar */}
      <div className="flex items-center gap-2 mb-6 flex-wrap" data-testid="workspace-actions">
        {!hasContent && (
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="flex items-center gap-2 px-4 py-2 bg-white text-black text-sm font-medium hover:bg-zinc-200 transition-colors disabled:opacity-40"
            data-testid="generate-content-btn"
          >
            <Wand2 className="w-4 h-4" />
            {generating ? 'Generating...' : 'Generate Content'}
          </button>
        )}
        {hasContent && (
          <>
            <button
              onClick={handleGenerate}
              disabled={generating}
              className="flex items-center gap-2 px-3 py-2 border border-zinc-700 text-sm text-zinc-300 hover:border-zinc-500 transition-colors disabled:opacity-40"
              data-testid="regenerate-btn"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${generating ? 'animate-spin' : ''}`} />
              {generating ? 'Regenerating...' : 'Regenerate'}
            </button>
            {!editing ? (
              <button
                onClick={startEditing}
                className="flex items-center gap-2 px-3 py-2 border border-zinc-700 text-sm text-zinc-300 hover:border-zinc-500 transition-colors"
                data-testid="edit-btn"
              >
                <Edit3 className="w-3.5 h-3.5" /> Edit
              </button>
            ) : (
              <>
                <button
                  onClick={saveEdits}
                  disabled={saving}
                  className="flex items-center gap-2 px-3 py-2 bg-white text-black text-sm font-medium hover:bg-zinc-200 transition-colors disabled:opacity-40"
                  data-testid="save-edits-btn"
                >
                  {saving ? 'Saving...' : 'Save'}
                </button>
                <button
                  onClick={() => setEditing(false)}
                  className="px-3 py-2 text-sm text-zinc-400 hover:text-white transition-colors"
                >
                  Cancel
                </button>
              </>
            )}
            <button
              onClick={handleGeneratePdf}
              disabled={generatingPdf}
              className="flex items-center gap-2 px-3 py-2 border border-zinc-700 text-sm text-zinc-300 hover:border-zinc-500 transition-colors disabled:opacity-40"
              data-testid="generate-pdf-btn"
            >
              <FileDown className={`w-3.5 h-3.5 ${generatingPdf ? 'animate-pulse' : ''}`} />
              {generatingPdf ? 'Creating PDF...' : magnet.has_pdf ? 'Regenerate PDF' : 'Generate PDF'}
            </button>
            {magnet.has_pdf && (
              <button
                onClick={handlePreviewPdf}
                className="flex items-center gap-2 px-3 py-2 border border-zinc-700 text-sm text-zinc-300 hover:border-zinc-500 transition-colors"
                data-testid="preview-pdf-btn"
              >
                <Eye className="w-3.5 h-3.5" /> Preview PDF
              </button>
            )}
            <button
              onClick={fetchVersions}
              className="flex items-center gap-2 px-3 py-2 border border-zinc-700 text-sm text-zinc-300 hover:border-zinc-500 transition-colors"
              data-testid="versions-btn"
            >
              <History className="w-3.5 h-3.5" /> Versions
            </button>
          </>
        )}
        <div className="flex-1" />
        {/* Status actions */}
        {magnet.status === 'Draft' && hasContent && magnet.has_pdf && (
          <button
            onClick={handleMarkReady}
            className="flex items-center gap-2 px-3 py-2 border border-amber-800 text-sm text-amber-400 hover:bg-amber-900/20 transition-colors"
            data-testid="mark-ready-btn"
          >
            <Send className="w-3.5 h-3.5" /> Mark Ready
          </button>
        )}
        {magnet.status === 'Ready' && (
          <button
            onClick={handlePublish}
            disabled={publishing}
            className="flex items-center gap-2 px-4 py-2 bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-500 transition-colors disabled:opacity-40"
            data-testid="publish-btn"
          >
            <CheckCircle className="w-3.5 h-3.5" />
            {publishing ? 'Publishing...' : 'Publish'}
          </button>
        )}
        {magnet.status !== 'Archived' && (
          <button
            onClick={handleArchive}
            className="flex items-center gap-2 px-3 py-2 text-sm text-zinc-500 hover:text-zinc-300 transition-colors"
            data-testid="archive-btn"
          >
            <Archive className="w-3.5 h-3.5" />
          </button>
        )}
        {magnet.status !== 'Published' && (
          <button
            onClick={handleDelete}
            className="flex items-center gap-2 px-3 py-2 text-sm text-red-500/60 hover:text-red-400 transition-colors"
            data-testid="delete-btn"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {/* Tabs */}
      {hasContent && (
        <div className="flex border-b border-zinc-800 mb-6" data-testid="workspace-tabs">
          {['content', 'landing', 'embed', 'meta'].map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2.5 text-sm capitalize transition-colors ${
                activeTab === tab
                  ? 'text-white border-b-2 border-white -mb-px'
                  : 'text-zinc-500 hover:text-zinc-300'
              }`}
              data-testid={`tab-${tab}`}
            >
              {tab === 'embed' ? 'Embed Code' : tab === 'meta' ? 'Details' : tab === 'landing' ? 'Landing Snippet' : 'Content'}
            </button>
          ))}
        </div>
      )}

      {/* Content */}
      {!hasContent ? (
        <div className="border border-zinc-800 border-dashed p-12 text-center" data-testid="empty-content">
          <Wand2 className="w-8 h-8 text-zinc-600 mx-auto mb-3" />
          <p className="text-zinc-400 text-sm mb-2">No content generated yet</p>
          <p className="text-zinc-600 text-xs">
            Topic: {magnet.topic}<br />
            Audience: {magnet.target_audience}<br />
            Format: {magnet.format_type} &middot; {magnet.length}
          </p>
        </div>
      ) : (
        <>
          {/* CONTENT TAB */}
          {activeTab === 'content' && (
            <div data-testid="content-panel">
              {editing ? (
                <div className="space-y-4">
                  <div>
                    <label className="block text-xs text-zinc-500 uppercase tracking-wider mb-1">Title</label>
                    <input
                      value={editFields.title}
                      onChange={e => setEditFields({ ...editFields, title: e.target.value })}
                      className="w-full bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-white focus:border-zinc-600 focus:outline-none"
                      data-testid="edit-title"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-zinc-500 uppercase tracking-wider mb-1">Subtitle</label>
                    <input
                      value={editFields.subtitle}
                      onChange={e => setEditFields({ ...editFields, subtitle: e.target.value })}
                      className="w-full bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-white focus:border-zinc-600 focus:outline-none"
                      data-testid="edit-subtitle"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-zinc-500 uppercase tracking-wider mb-1">Content (Markdown)</label>
                    <textarea
                      value={editFields.markdown_content}
                      onChange={e => setEditFields({ ...editFields, markdown_content: e.target.value })}
                      rows={20}
                      className="w-full bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-white font-mono focus:border-zinc-600 focus:outline-none resize-y"
                      data-testid="edit-content"
                    />
                  </div>
                </div>
              ) : (
                <div className="border border-zinc-800 p-6">
                  {magnet.title && (
                    <h2 className="text-xl font-['Outfit'] text-white mb-1">{magnet.title}</h2>
                  )}
                  {magnet.subtitle && (
                    <p className="text-sm text-zinc-400 italic mb-4">{magnet.subtitle}</p>
                  )}
                  <div
                    className="prose prose-invert prose-sm max-w-none text-zinc-300 leading-relaxed"
                    data-testid="content-preview"
                  >
                    <MarkdownRenderer content={magnet.markdown_content} />
                  </div>
                </div>
              )}
            </div>
          )}

          {/* LANDING TAB */}
          {activeTab === 'landing' && (
            <div className="space-y-4" data-testid="landing-panel">
              {editing ? (
                <>
                  <div>
                    <label className="block text-xs text-zinc-500 uppercase tracking-wider mb-1">Headline</label>
                    <input
                      value={editFields.landing_headline}
                      onChange={e => setEditFields({ ...editFields, landing_headline: e.target.value })}
                      className="w-full bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-white focus:border-zinc-600 focus:outline-none"
                      data-testid="edit-headline"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-zinc-500 uppercase tracking-wider mb-1">Body Copy</label>
                    <textarea
                      value={editFields.landing_body}
                      onChange={e => setEditFields({ ...editFields, landing_body: e.target.value })}
                      rows={4}
                      className="w-full bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-white focus:border-zinc-600 focus:outline-none resize-none"
                      data-testid="edit-body"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-zinc-500 uppercase tracking-wider mb-1">CTA Button Text</label>
                    <input
                      value={editFields.landing_cta}
                      onChange={e => setEditFields({ ...editFields, landing_cta: e.target.value })}
                      className="w-full bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-white focus:border-zinc-600 focus:outline-none"
                      data-testid="edit-cta"
                    />
                  </div>
                </>
              ) : (
                <div className="border border-zinc-800 p-6">
                  <div className="text-[10px] text-zinc-600 uppercase tracking-wider mb-4">Landing Page Snippet Preview</div>
                  <div className="border border-zinc-700 p-6 bg-zinc-900/50 max-w-md">
                    <h3 className="text-lg text-white font-medium mb-2">{magnet.landing_headline || 'No headline'}</h3>
                    <p className="text-sm text-zinc-400 leading-relaxed mb-4">{magnet.landing_body || 'No body copy'}</p>
                    <div className="inline-block px-5 py-2.5 bg-white text-black text-sm font-medium">
                      {magnet.landing_cta || 'Download'}
                    </div>
                  </div>
                  <div className="mt-4 flex gap-2">
                    <CopyButton
                      text={`${magnet.landing_headline}\n\n${magnet.landing_body}\n\n[${magnet.landing_cta}]`}
                      label="snippet"
                      copied={copied}
                      onCopy={copyToClipboard}
                    />
                  </div>
                </div>
              )}
            </div>
          )}

          {/* EMBED TAB */}
          {activeTab === 'embed' && (
            <div data-testid="embed-panel">
              {magnet.status === 'Published' && magnet.embed_code ? (
                <div className="space-y-4">
                  <div className="border border-zinc-800 p-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs text-zinc-500 uppercase tracking-wider">Embed Code</span>
                      <CopyButton
                        text={magnet.embed_code}
                        label="embed"
                        copied={copied}
                        onCopy={copyToClipboard}
                      />
                    </div>
                    <pre className="text-xs text-zinc-400 bg-zinc-900 p-4 overflow-x-auto whitespace-pre-wrap font-mono" data-testid="embed-code">
                      {magnet.embed_code}
                    </pre>
                  </div>
                  <div className="border border-zinc-800 p-4">
                    <div className="text-xs text-zinc-500 uppercase tracking-wider mb-2">Download URL</div>
                    <div className="flex items-center gap-2">
                      <code className="text-sm text-zinc-300 bg-zinc-900 px-3 py-1.5 flex-1 font-mono" data-testid="download-url">
                        {process.env.REACT_APP_BACKEND_URL}/api/lm/{magnet.public_id}/download
                      </code>
                      <CopyButton
                        text={`${process.env.REACT_APP_BACKEND_URL}/api/lm/${magnet.public_id}/download`}
                        label="url"
                        copied={copied}
                        onCopy={copyToClipboard}
                      />
                    </div>
                  </div>
                </div>
              ) : (
                <div className="border border-zinc-800 border-dashed p-8 text-center">
                  <p className="text-zinc-500 text-sm">Publish the lead magnet to get embed code and download URL.</p>
                </div>
              )}
            </div>
          )}

          {/* META TAB */}
          {activeTab === 'meta' && (
            <div className="grid grid-cols-2 gap-4" data-testid="meta-panel">
              <MetaField label="Topic" value={magnet.topic} />
              <MetaField label="Audience" value={magnet.target_audience} />
              <MetaField label="Format" value={magnet.format_type} />
              <MetaField label="Length" value={magnet.length} />
              <MetaField label="District" value={magnet.district_tag || '—'} />
              <MetaField label="Disclaimer" value={magnet.include_disclaimer ? 'Included' : 'Excluded'} />
              <MetaField label="PDF Ready" value={magnet.has_pdf ? 'Yes' : 'No'} />
              <MetaField label="Version" value={`v${magnet.current_version}`} />
              <MetaField label="Downloads" value={String(magnet.download_count)} />
              <MetaField label="Created" value={new Date(magnet.created_at).toLocaleDateString()} />
              {magnet.content_direction && (
                <div className="col-span-2">
                  <MetaField label="Content Direction" value={magnet.content_direction} />
                </div>
              )}
              {magnet.description && (
                <div className="col-span-2">
                  <MetaField label="Description" value={magnet.description} />
                </div>
              )}
            </div>
          )}
        </>
      )}

      {/* Versions Drawer */}
      {showVersions && (
        <div className="fixed inset-0 bg-black/70 flex justify-end z-50" onClick={() => setShowVersions(false)}>
          <div className="bg-[#0C0C0E] border-l border-zinc-800 w-full max-w-md overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="p-6 border-b border-zinc-800 flex items-center justify-between">
              <h3 className="text-lg font-['Outfit'] text-white">Version History</h3>
              <button onClick={() => setShowVersions(false)} className="text-zinc-500 hover:text-white text-sm">Close</button>
            </div>
            <div className="divide-y divide-zinc-800">
              {versions.length === 0 ? (
                <div className="p-6 text-center text-zinc-500 text-sm">No versions yet.</div>
              ) : (
                versions.map(v => (
                  <div key={v.id} className="p-4">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm text-white font-medium">
                        Version {v.version_number}
                        {v.version_number === magnet.current_version && (
                          <span className="ml-2 text-xs text-emerald-400">(current)</span>
                        )}
                      </span>
                      {v.version_number !== magnet.current_version && (
                        <button
                          onClick={() => restoreVersion(v.id)}
                          className="text-xs text-zinc-400 hover:text-white flex items-center gap-1"
                          data-testid={`restore-version-${v.version_number}`}
                        >
                          <RotateCcw className="w-3 h-3" /> Restore
                        </button>
                      )}
                    </div>
                    <div className="text-xs text-zinc-500">
                      {v.title && <span>{v.title} &middot; </span>}
                      {new Date(v.created_at).toLocaleString()}
                    </div>
                    {v.markdown_content && (
                      <p className="text-xs text-zinc-600 mt-1 line-clamp-2">{v.markdown_content.slice(0, 120)}...</p>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function MetaField({ label, value }) {
  return (
    <div className="border border-zinc-800 p-3">
      <div className="text-[10px] text-zinc-600 uppercase tracking-wider mb-1">{label}</div>
      <div className="text-sm text-zinc-300">{value}</div>
    </div>
  );
}

function CopyButton({ text, label, copied, onCopy }) {
  const isCopied = copied === label;
  return (
    <button
      onClick={() => onCopy(text, label)}
      className="flex items-center gap-1.5 px-2 py-1 text-xs text-zinc-400 hover:text-white border border-zinc-700 hover:border-zinc-500 transition-colors"
      data-testid={`copy-${label}-btn`}
    >
      {isCopied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
      {isCopied ? 'Copied' : 'Copy'}
    </button>
  );
}

function MarkdownRenderer({ content }) {
  if (!content) return null;

  const lines = content.split('\n');
  const elements = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    if (!trimmed) {
      i++;
      continue;
    }

    if (trimmed.startsWith('### ')) {
      elements.push(<h3 key={i} className="text-base font-semibold text-white mt-5 mb-2">{renderInline(trimmed.slice(4))}</h3>);
    } else if (trimmed.startsWith('## ')) {
      elements.push(<h2 key={i} className="text-lg font-semibold text-white mt-6 mb-3">{renderInline(trimmed.slice(3))}</h2>);
    } else if (trimmed.startsWith('# ')) {
      elements.push(<h1 key={i} className="text-xl font-semibold text-white mt-6 mb-3">{renderInline(trimmed.slice(2))}</h1>);
    } else if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      const items = [];
      while (i < lines.length && (lines[i].trim().startsWith('- ') || lines[i].trim().startsWith('* '))) {
        items.push(<li key={i} className="text-zinc-300">{renderInline(lines[i].trim().slice(2))}</li>);
        i++;
      }
      elements.push(<ul key={`ul-${i}`} className="list-disc list-inside space-y-1 my-2 ml-2">{items}</ul>);
      continue;
    } else if (/^\d+\.\s/.test(trimmed)) {
      const items = [];
      while (i < lines.length && /^\d+\.\s/.test(lines[i].trim())) {
        const text = lines[i].trim().replace(/^\d+\.\s/, '');
        items.push(<li key={i} className="text-zinc-300">{renderInline(text)}</li>);
        i++;
      }
      elements.push(<ol key={`ol-${i}`} className="list-decimal list-inside space-y-1 my-2 ml-2">{items}</ol>);
      continue;
    } else if (trimmed.startsWith('>')) {
      elements.push(
        <blockquote key={i} className="border-l-2 border-zinc-600 pl-4 py-1 my-3 text-zinc-400 italic">
          {renderInline(trimmed.slice(1).trim())}
        </blockquote>
      );
    } else {
      elements.push(<p key={i} className="text-zinc-300 my-1.5">{renderInline(trimmed)}</p>);
    }
    i++;
  }

  return <>{elements}</>;
}

function renderInline(text) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} className="text-white font-medium">{part.slice(2, -2)}</strong>;
    }
    return part;
  });
}
