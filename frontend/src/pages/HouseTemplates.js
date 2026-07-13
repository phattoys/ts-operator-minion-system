import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { 
  LayoutTemplate, Crown, ChevronDown, ChevronUp, 
  FileText, ArrowRight, RefreshCw, Plus, Power,
  Trash2, Pencil, X, Check
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function HouseTemplates() {
  const [templates, setTemplates] = useState([]);
  const [byFamily, setByFamily] = useState({});
  const [loading, setLoading] = useState(true);
  const [expandedTemplate, setExpandedTemplate] = useState(null);
  const [filterFamily, setFilterFamily] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState({});

  useEffect(() => {
    fetchTemplates();
  }, [filterFamily]);

  const fetchTemplates = async () => {
    setLoading(true);
    try {
      const url = filterFamily
        ? `${API}/house-templates?family=${encodeURIComponent(filterFamily)}`
        : `${API}/house-templates`;
      const res = await axios.get(url, { withCredentials: true });
      setTemplates(res.data.templates || []);
      setByFamily(res.data.by_family || {});
    } catch (err) {
      console.error('Failed to fetch templates:', err);
    }
    setLoading(false);
  };

  const setPrimary = async (templateId) => {
    try {
      await axios.post(`${API}/house-templates/${templateId}/set-primary`, {}, { withCredentials: true });
      fetchTemplates();
    } catch (err) {
      console.error('Failed to set primary:', err);
    }
  };

  const toggleStatus = async (templateId) => {
    try {
      await axios.post(`${API}/house-templates/${templateId}/toggle-status`, {}, { withCredentials: true });
      fetchTemplates();
    } catch (err) {
      console.error('Failed to toggle status:', err);
    }
  };

  const deleteTemplate = async (templateId) => {
    if (!window.confirm('Delete this house template?')) return;
    try {
      await axios.delete(`${API}/house-templates/${templateId}`, { withCredentials: true });
      fetchTemplates();
    } catch (err) {
      console.error('Failed to delete template:', err);
    }
  };

  const startEdit = (t) => {
    setEditingId(t.id);
    setEditForm({
      template_name: t.template_name,
      purpose: t.purpose,
      tone_guidance: t.tone_guidance || '',
      structural_pattern: t.structural_pattern
    });
  };

  const saveEdit = async () => {
    try {
      await axios.put(`${API}/house-templates/${editingId}`, editForm, { withCredentials: true });
      setEditingId(null);
      fetchTemplates();
    } catch (err) {
      console.error('Failed to update template:', err);
    }
  };

  const families = [
    'Core Hub', 'District', 'Trust', 'Guided Path',
    'Category Support', 'Conversion', 'FAQ/Support', 'Media/Asset'
  ];

  if (loading) {
    return (
      <div className="p-6 md:p-8">
        <div className="animate-pulse space-y-6">
          <div className="h-8 bg-zinc-800 w-64"></div>
          <div className="h-48 bg-zinc-800"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 md:p-8 space-y-8" data-testid="house-templates-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-['Outfit'] text-4xl font-light tracking-tight text-white" data-testid="house-templates-title">
            House Templates
          </h1>
          <p className="text-zinc-500 text-sm mt-1">Reusable structural patterns from winning pages</p>
        </div>
        <button
          onClick={fetchTemplates}
          className="p-2 border border-zinc-800 hover:bg-zinc-800 transition-colors duration-150"
          data-testid="refresh-templates-btn"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Family Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {families.map(fam => {
          const data = byFamily[fam];
          const count = data?.count || 0;
          const hasPrimary = !!data?.primary;
          return (
            <button
              key={fam}
              onClick={() => setFilterFamily(filterFamily === fam ? '' : fam)}
              className={`p-4 border text-left transition-colors duration-150 ${
                filterFamily === fam
                  ? 'border-white bg-zinc-900'
                  : count > 0
                    ? 'border-zinc-700 hover:border-zinc-500 hover:bg-zinc-900/50'
                    : 'border-zinc-800 opacity-50 hover:opacity-75'
              }`}
              data-testid={`family-filter-${fam.toLowerCase().replace(/[/ ]/g, '-')}`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-mono text-2xl font-semibold text-white">{count}</span>
                {hasPrimary && <Crown className="w-4 h-4 text-[#34C759]" />}
              </div>
              <div className="text-xs text-zinc-500 tracking-[0.1em] uppercase">{fam}</div>
            </button>
          );
        })}
      </div>

      {/* Active Filter */}
      {filterFamily && (
        <div className="flex items-center gap-2">
          <span className="text-xs text-zinc-500">Filtered by:</span>
          <span className="text-xs text-white border border-zinc-700 px-2 py-1">{filterFamily}</span>
          <button
            onClick={() => setFilterFamily('')}
            className="text-xs text-zinc-500 hover:text-white"
            data-testid="clear-filter-btn"
          >
            Clear
          </button>
        </div>
      )}

      {/* Template List */}
      {templates.length === 0 ? (
        <div className="border border-zinc-800 p-12 text-center">
          <LayoutTemplate className="w-10 h-10 mx-auto mb-4 text-zinc-600" />
          <h2 className="font-['Outfit'] text-xl text-white mb-2">No Templates Yet</h2>
          <p className="text-zinc-500 text-sm max-w-md mx-auto">
            Create house templates from winning page versions in the Page Workspace.
            These become reusable structural guides for future generation.
          </p>
        </div>
      ) : (
        <div className="space-y-4" data-testid="template-list">
          {templates.map((t) => (
            <div
              key={t.id}
              className={`border transition-colors duration-150 ${
                t.status === 'inactive'
                  ? 'border-zinc-800 opacity-60'
                  : 'border-zinc-800 hover:border-zinc-700'
              }`}
              data-testid={`template-item-${t.id}`}
            >
              {/* Template Header */}
              <div className="p-4 flex items-center justify-between">
                <div className="flex items-center gap-4 flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    {t.is_primary ? (
                      <Crown className="w-5 h-5 text-[#34C759]" />
                    ) : (
                      <LayoutTemplate className="w-5 h-5 text-zinc-500" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3">
                      <span className="text-white font-['Outfit'] font-medium truncate">
                        {t.template_name}
                      </span>
                      {t.is_primary && (
                        <span className="text-[10px] tracking-[0.15em] uppercase text-[#34C759] border border-[#34C759]/30 px-2 py-0.5">
                          Primary
                        </span>
                      )}
                      {t.status === 'inactive' && (
                        <span className="text-[10px] tracking-[0.15em] uppercase text-zinc-500 border border-zinc-700 px-2 py-0.5">
                          Inactive
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-4 mt-1">
                      <span className="text-xs text-zinc-500">{t.page_family}</span>
                      {t.page_type && <span className="text-xs text-zinc-600">{t.page_type}</span>}
                      <span className="text-xs text-zinc-600">
                        from: {t.source_page_name} v{t.source_version_number}
                      </span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setExpandedTemplate(expandedTemplate === t.id ? null : t.id)}
                    className="p-2 text-zinc-500 hover:text-white transition-colors"
                    data-testid={`toggle-template-${t.id}`}
                  >
                    {expandedTemplate === t.id ? (
                      <ChevronUp className="w-4 h-4" />
                    ) : (
                      <ChevronDown className="w-4 h-4" />
                    )}
                  </button>
                </div>
              </div>

              {/* Purpose Preview */}
              {expandedTemplate !== t.id && (
                <div className="px-4 pb-3">
                  <p className="text-xs text-zinc-500 italic truncate">{t.purpose}</p>
                </div>
              )}

              {/* Expanded Detail */}
              {expandedTemplate === t.id && (
                <div className="border-t border-zinc-800">
                  {editingId === t.id ? (
                    /* Edit Mode */
                    <div className="p-4 space-y-4">
                      <div>
                        <span className="label-uppercase block mb-2">Template Name</span>
                        <input
                          value={editForm.template_name}
                          onChange={(e) => setEditForm({...editForm, template_name: e.target.value})}
                          className="input-flat w-full text-sm"
                          data-testid="edit-template-name"
                        />
                      </div>
                      <div>
                        <span className="label-uppercase block mb-2">Purpose</span>
                        <textarea
                          value={editForm.purpose}
                          onChange={(e) => setEditForm({...editForm, purpose: e.target.value})}
                          className="input-flat w-full text-xs h-20 resize-none"
                          data-testid="edit-template-purpose"
                        />
                      </div>
                      <div>
                        <span className="label-uppercase block mb-2">Tone Guidance</span>
                        <textarea
                          value={editForm.tone_guidance}
                          onChange={(e) => setEditForm({...editForm, tone_guidance: e.target.value})}
                          className="input-flat w-full text-xs h-16 resize-none"
                          data-testid="edit-template-tone"
                        />
                      </div>
                      <div>
                        <span className="label-uppercase block mb-2">Structural Pattern</span>
                        <textarea
                          value={editForm.structural_pattern}
                          onChange={(e) => setEditForm({...editForm, structural_pattern: e.target.value})}
                          className="input-flat w-full text-xs h-32 resize-none font-mono"
                          data-testid="edit-template-structure"
                        />
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={saveEdit}
                          className="text-xs bg-white text-black px-4 py-1.5 hover:bg-zinc-200 transition-colors flex items-center gap-1.5"
                          data-testid="save-edit-btn"
                        >
                          <Check className="w-3 h-3" />
                          Save Changes
                        </button>
                        <button
                          onClick={() => setEditingId(null)}
                          className="text-xs text-zinc-400 border border-zinc-700 px-3 py-1.5 hover:bg-zinc-800 transition-colors"
                          data-testid="cancel-edit-btn"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    /* View Mode */
                    <>
                      <div className="p-4 border-b border-zinc-800">
                        <span className="label-uppercase block mb-2">Purpose</span>
                        <p className="text-sm text-zinc-300">{t.purpose}</p>
                      </div>

                      {t.tone_guidance && (
                        <div className="p-4 border-b border-zinc-800">
                          <span className="label-uppercase block mb-2">Tone Guidance</span>
                          <p className="text-sm text-zinc-300">{t.tone_guidance}</p>
                        </div>
                      )}

                      <div className="p-4 border-b border-zinc-800">
                        <span className="label-uppercase block mb-2">Structural Pattern</span>
                        <div className="content-preview max-h-[250px] overflow-y-auto text-xs">
                          {t.structural_pattern}
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="p-4 flex items-center gap-3 flex-wrap">
                        <button
                          onClick={() => startEdit(t)}
                          className="text-xs border border-zinc-700 text-zinc-400 px-3 py-1.5 hover:text-white hover:border-zinc-500 transition-colors flex items-center gap-1.5"
                          data-testid={`edit-template-${t.id}`}
                        >
                          <Pencil className="w-3 h-3" />
                          Edit
                        </button>
                        {!t.is_primary && t.status === 'active' && (
                          <button
                            onClick={() => setPrimary(t.id)}
                            className="text-xs border border-[#34C759]/30 text-[#34C759] px-3 py-1.5 hover:bg-[#34C759]/10 transition-colors flex items-center gap-1.5"
                            data-testid={`set-primary-template-${t.id}`}
                          >
                            <Crown className="w-3 h-3" />
                            Set as Primary
                          </button>
                        )}
                        <button
                          onClick={() => toggleStatus(t.id)}
                          className={`text-xs border px-3 py-1.5 transition-colors flex items-center gap-1.5 ${
                            t.status === 'active'
                              ? 'border-zinc-700 text-zinc-400 hover:border-[#FF3B30] hover:text-[#FF3B30]'
                              : 'border-[#34C759]/30 text-[#34C759] hover:bg-[#34C759]/10'
                          }`}
                          data-testid={`toggle-status-${t.id}`}
                        >
                          <Power className="w-3 h-3" />
                          {t.status === 'active' ? 'Deactivate' : 'Activate'}
                        </button>
                        <button
                          onClick={() => deleteTemplate(t.id)}
                          className="text-xs border border-zinc-700 text-zinc-400 px-3 py-1.5 hover:border-[#FF3B30] hover:text-[#FF3B30] transition-colors flex items-center gap-1.5"
                          data-testid={`delete-template-${t.id}`}
                        >
                          <Trash2 className="w-3 h-3" />
                          Delete
                        </button>
                        <Link
                          to={`/workspace/${t.source_page_id}`}
                          className="text-xs border border-zinc-700 text-zinc-400 px-3 py-1.5 hover:bg-zinc-800 transition-colors flex items-center gap-1.5"
                          data-testid={`view-source-${t.id}`}
                        >
                          <FileText className="w-3 h-3" />
                          View Source Page
                        </Link>
                      </div>

                      {/* Meta */}
                      <div className="px-4 pb-4 flex items-center gap-4 text-[10px] text-zinc-600 font-mono">
                        <span>Created: {new Date(t.created_at).toLocaleDateString()}</span>
                        <span>Source score: {t.source_quality_score || '—'}</span>
                      </div>
                    </>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
