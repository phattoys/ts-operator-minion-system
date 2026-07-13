import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { 
  Award, Star, ChevronDown, ChevronUp, Tag,
  FileText, ArrowRight, RefreshCw, Crown
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function ExemplarLibrary() {
  const [exemplars, setExemplars] = useState([]);
  const [byFamily, setByFamily] = useState({});
  const [loading, setLoading] = useState(true);
  const [expandedExemplar, setExpandedExemplar] = useState(null);
  const [filterFamily, setFilterFamily] = useState('');
  const [availableTags, setAvailableTags] = useState([]);

  useEffect(() => {
    fetchExemplars();
  }, [filterFamily]);

  const fetchExemplars = async () => {
    setLoading(true);
    try {
      const url = filterFamily 
        ? `${API}/exemplars?family=${encodeURIComponent(filterFamily)}`
        : `${API}/exemplars`;
      const res = await axios.get(url, { withCredentials: true });
      setExemplars(res.data.exemplars || []);
      setByFamily(res.data.by_family || {});
      setAvailableTags(res.data.available_reason_tags || []);
    } catch (err) {
      console.error('Failed to fetch exemplars:', err);
    }
    setLoading(false);
  };

  const setPrimary = async (exemplarId) => {
    try {
      await axios.post(`${API}/exemplars/${exemplarId}/set-primary`, {}, { withCredentials: true });
      fetchExemplars();
    } catch (err) {
      console.error('Failed to set primary:', err);
    }
  };

  const removeExemplar = async (exemplarId) => {
    if (!window.confirm('Remove this exemplar from the Gold Standard Library?')) return;
    try {
      await axios.delete(`${API}/exemplars/${exemplarId}`, { withCredentials: true });
      fetchExemplars();
    } catch (err) {
      console.error('Failed to remove exemplar:', err);
    }
  };

  const getScoreColor = (score) => {
    if (!score) return 'text-zinc-500';
    if (score >= 85) return 'text-[#34C759]';
    if (score >= 70) return 'text-[#FFCC00]';
    return 'text-[#FF3B30]';
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
    <div className="p-6 md:p-8 space-y-8" data-testid="exemplar-library">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-['Outfit'] text-4xl font-light tracking-tight text-white" data-testid="exemplar-library-title">
            Exemplar Library
          </h1>
          <p className="text-zinc-500 text-sm mt-1">Gold Standard Pages — Your Brand Intelligence</p>
        </div>
        <button
          onClick={fetchExemplars}
          className="p-2 border border-zinc-800 hover:bg-zinc-800 transition-colors duration-150"
          data-testid="refresh-exemplars-btn"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Family Summary Cards */}
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
                {hasPrimary && <Crown className="w-4 h-4 text-[#FFCC00]" />}
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

      {/* Exemplar List */}
      {exemplars.length === 0 ? (
        <div className="border border-zinc-800 p-12 text-center">
          <Award className="w-10 h-10 mx-auto mb-4 text-zinc-600" />
          <h2 className="font-['Outfit'] text-xl text-white mb-2">No Exemplars Yet</h2>
          <p className="text-zinc-500 text-sm max-w-md mx-auto">
            Mark your strongest page versions as Exemplars from the Page Workspace. 
            These become your brand's gold standard intelligence.
          </p>
        </div>
      ) : (
        <div className="space-y-4" data-testid="exemplar-list">
          {exemplars.map((ex) => (
            <div
              key={ex.id}
              className="border border-zinc-800 hover:border-zinc-700 transition-colors duration-150"
              data-testid={`exemplar-item-${ex.id}`}
            >
              {/* Exemplar Header */}
              <div className="p-4 flex items-center justify-between">
                <div className="flex items-center gap-4 flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    {ex.is_primary ? (
                      <Crown className="w-5 h-5 text-[#FFCC00]" />
                    ) : (
                      <Award className="w-5 h-5 text-zinc-500" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3">
                      <span className="text-white font-['Outfit'] font-medium truncate">
                        {ex.page_name}
                      </span>
                      {ex.is_primary && (
                        <span className="text-[10px] tracking-[0.15em] uppercase text-[#FFCC00] border border-[#FFCC00]/30 px-2 py-0.5">
                          Primary
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-4 mt-1">
                      <span className="text-xs text-zinc-500">{ex.page_family}</span>
                      <span className="text-xs text-zinc-600">v{ex.version_number}</span>
                      <span className={`text-xs font-mono ${getScoreColor(ex.quality_score)}`}>
                        {ex.quality_score ? `${ex.quality_score}/100` : '—'}
                      </span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Link
                    to={`/workspace/${ex.page_id}`}
                    className="p-2 text-zinc-500 hover:text-white transition-colors"
                    data-testid={`view-page-${ex.id}`}
                  >
                    <ArrowRight className="w-4 h-4" />
                  </Link>
                  <button
                    onClick={() => setExpandedExemplar(expandedExemplar === ex.id ? null : ex.id)}
                    className="p-2 text-zinc-500 hover:text-white transition-colors"
                    data-testid={`toggle-exemplar-${ex.id}`}
                  >
                    {expandedExemplar === ex.id ? (
                      <ChevronUp className="w-4 h-4" />
                    ) : (
                      <ChevronDown className="w-4 h-4" />
                    )}
                  </button>
                </div>
              </div>

              {/* Reason Tags */}
              {ex.reason_tags?.length > 0 && (
                <div className="px-4 pb-3 flex flex-wrap gap-2">
                  {ex.reason_tags.map((tag, idx) => (
                    <span
                      key={idx}
                      className="inline-flex items-center gap-1 text-[11px] text-zinc-400 border border-zinc-800 px-2 py-0.5"
                    >
                      <Tag className="w-3 h-3" />
                      {tag}
                    </span>
                  ))}
                </div>
              )}

              {/* Exemplar Notes */}
              {ex.exemplar_notes && expandedExemplar !== ex.id && (
                <div className="px-4 pb-3">
                  <p className="text-xs text-zinc-500 italic truncate">{ex.exemplar_notes}</p>
                </div>
              )}

              {/* Expanded Detail */}
              {expandedExemplar === ex.id && (
                <div className="border-t border-zinc-800">
                  {/* Notes */}
                  {ex.exemplar_notes && (
                    <div className="p-4 border-b border-zinc-800">
                      <span className="label-uppercase block mb-2">Why This Is Gold Standard</span>
                      <p className="text-sm text-zinc-300">{ex.exemplar_notes}</p>
                    </div>
                  )}

                  {/* Content Preview */}
                  <div className="p-4 border-b border-zinc-800">
                    <span className="label-uppercase block mb-2">Content Preview</span>
                    <div className="content-preview max-h-[300px] overflow-y-auto text-xs">
                      {ex.generated_content?.slice(0, 800)}
                      {ex.generated_content?.length > 800 && '...'}
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="p-4 flex items-center gap-3">
                    {!ex.is_primary && (
                      <button
                        onClick={() => setPrimary(ex.id)}
                        className="text-xs border border-[#FFCC00]/30 text-[#FFCC00] px-3 py-1.5 hover:bg-[#FFCC00]/10 transition-colors flex items-center gap-1.5"
                        data-testid={`set-primary-${ex.id}`}
                      >
                        <Crown className="w-3 h-3" />
                        Set as Primary
                      </button>
                    )}
                    <button
                      onClick={() => removeExemplar(ex.id)}
                      className="text-xs border border-zinc-700 text-zinc-400 px-3 py-1.5 hover:border-[#FF3B30] hover:text-[#FF3B30] transition-colors"
                      data-testid={`remove-exemplar-${ex.id}`}
                    >
                      Remove Exemplar
                    </button>
                    <Link
                      to={`/workspace/${ex.page_id}`}
                      className="text-xs border border-zinc-700 text-zinc-400 px-3 py-1.5 hover:bg-zinc-800 transition-colors flex items-center gap-1.5"
                      data-testid={`open-workspace-${ex.id}`}
                    >
                      <FileText className="w-3 h-3" />
                      Open in Workspace
                    </Link>
                  </div>

                  {/* Meta */}
                  <div className="px-4 pb-4 flex items-center gap-4 text-[10px] text-zinc-600 font-mono">
                    <span>Created: {new Date(ex.created_at).toLocaleDateString()}</span>
                    <span>Type: {ex.page_type}</span>
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
