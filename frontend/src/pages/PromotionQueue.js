import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { 
  TrendingUp, Award, LayoutTemplate, Palette, 
  ChevronDown, ChevronUp, ArrowRight, RefreshCw,
  Check, X, Clock, Zap
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const ACTION_CONFIG = {
  'promote-exemplar': { label: 'Promoted to Exemplar', icon: Award, color: '#FFCC00' },
  'create-template': { label: 'Created House Template', icon: LayoutTemplate, color: '#34C759' },
  'save-style-candidate': { label: 'Saved as Style Candidate', icon: Palette, color: '#AF52DE' },
  'dismiss': { label: 'Dismissed', icon: X, color: '#FF3B30' },
  'decide-later': { label: 'Deferred', icon: Clock, color: '#FF9500' },
};

const STATUS_STYLES = {
  pending: { label: 'Pending', color: '#FF9500', bg: 'bg-[#FF9500]/10 border-[#FF9500]/30' },
  promoted: { label: 'Promoted', color: '#34C759', bg: 'bg-[#34C759]/10 border-[#34C759]/30' },
  dismissed: { label: 'Dismissed', color: '#FF3B30', bg: 'bg-[#FF3B30]/10 border-[#FF3B30]/30' },
  deferred: { label: 'Deferred', color: '#FF9500', bg: 'bg-[#FF9500]/5 border-[#FF9500]/20' },
};

export default function PromotionQueue() {
  const [candidates, setCandidates] = useState([]);
  const [statusCounts, setStatusCounts] = useState({});
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState('pending');
  const [expandedId, setExpandedId] = useState(null);

  useEffect(() => {
    fetchCandidates();
  }, [filterStatus]);

  const fetchCandidates = async () => {
    setLoading(true);
    try {
      const url = filterStatus
        ? `${API}/promotions/candidates?status=${filterStatus}`
        : `${API}/promotions/candidates`;
      const res = await axios.get(url, { withCredentials: true });
      setCandidates(res.data.candidates || []);
      setStatusCounts(res.data.status_counts || {});
    } catch (err) {
      console.error('Failed to fetch candidates:', err);
    }
    setLoading(false);
  };

  const takeAction = async (candidateId, action, notes = null) => {
    try {
      await axios.post(`${API}/promotions/candidates/${candidateId}/action`, {
        action,
        notes,
        is_primary: false
      }, { withCredentials: true });
      fetchCandidates();
    } catch (err) {
      console.error('Action failed:', err);
    }
  };

  const getScoreColor = (score) => {
    if (!score) return 'text-zinc-500';
    if (score >= 85) return 'text-[#34C759]';
    if (score >= 70) return 'text-[#FFCC00]';
    return 'text-[#FF3B30]';
  };

  const statusFilters = ['pending', 'promoted', 'dismissed', 'deferred'];

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
    <div className="p-6 md:p-8 space-y-8" data-testid="promotion-queue-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-['Outfit'] text-4xl font-light tracking-tight text-white" data-testid="promotion-queue-title">
            Promotion Queue
          </h1>
          <p className="text-zinc-500 text-sm mt-1">Strong variants recommended for reuse as permanent assets</p>
        </div>
        <button onClick={fetchCandidates} className="p-2 border border-zinc-800 hover:bg-zinc-800 transition-colors" data-testid="refresh-promotions-btn">
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Status Filters */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => setFilterStatus('')}
          className={`text-xs px-3 py-1.5 border transition-colors ${!filterStatus ? 'border-white text-white' : 'border-zinc-700 text-zinc-400 hover:text-white'}`}
          data-testid="filter-all"
        >
          All ({Object.values(statusCounts).reduce((a, b) => a + b, 0)})
        </button>
        {statusFilters.map(s => {
          const style = STATUS_STYLES[s];
          const count = statusCounts[s] || 0;
          return (
            <button
              key={s}
              onClick={() => setFilterStatus(filterStatus === s ? '' : s)}
              className={`text-xs px-3 py-1.5 border transition-colors ${
                filterStatus === s
                  ? `border-white text-white`
                  : `border-zinc-700 text-zinc-400 hover:text-white`
              }`}
              data-testid={`filter-${s}`}
            >
              {style.label} ({count})
            </button>
          );
        })}
      </div>

      {/* Candidates */}
      {candidates.length === 0 ? (
        <div className="border border-zinc-800 p-12 text-center">
          <TrendingUp className="w-10 h-10 mx-auto mb-4 text-zinc-600" />
          <h2 className="font-['Outfit'] text-xl text-white mb-2">
            {filterStatus === 'pending' ? 'No Pending Promotions' : 'No Candidates Found'}
          </h2>
          <p className="text-zinc-500 text-sm max-w-md mx-auto">
            {filterStatus === 'pending'
              ? 'The system will flag strong versions for promotion after scoring. Keep generating and scoring pages.'
              : 'Try a different status filter to see candidates.'}
          </p>
        </div>
      ) : (
        <div className="space-y-4" data-testid="candidate-list">
          {candidates.map(c => {
            const statusStyle = STATUS_STYLES[c.status] || STATUS_STYLES.pending;
            return (
              <div key={c.id} className="border border-zinc-800 hover:border-zinc-700 transition-colors" data-testid={`candidate-${c.id}`}>
                {/* Header */}
                <div className="p-4 flex items-center justify-between">
                  <div className="flex items-center gap-4 flex-1 min-w-0">
                    <TrendingUp className={`w-5 h-5`} style={{ color: statusStyle.color }} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3">
                        <span className="text-white font-['Outfit'] font-medium truncate">{c.page_name}</span>
                        <span className={`text-[10px] tracking-[0.15em] uppercase border px-2 py-0.5 ${statusStyle.bg}`} style={{ color: statusStyle.color }}>
                          {statusStyle.label}
                        </span>
                      </div>
                      <div className="flex items-center gap-4 mt-1">
                        <span className="text-xs text-zinc-500">{c.page_family}</span>
                        <span className="text-xs text-zinc-600">v{c.version_number}</span>
                        <span className={`text-xs font-mono ${getScoreColor(c.quality_score)}`}>{c.quality_score}/100</span>
                        <span className="text-xs text-zinc-600">{c.signals?.length || 0} signals</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Link to={`/workspace/${c.page_id}`} className="p-2 text-zinc-500 hover:text-white transition-colors" data-testid={`goto-workspace-${c.id}`}>
                      <ArrowRight className="w-4 h-4" />
                    </Link>
                    <button onClick={() => setExpandedId(expandedId === c.id ? null : c.id)} className="p-2 text-zinc-500 hover:text-white transition-colors" data-testid={`toggle-candidate-${c.id}`}>
                      {expandedId === c.id ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                {/* Recommendation */}
                {c.recommendation_reason && expandedId !== c.id && (
                  <div className="px-4 pb-3">
                    <p className="text-xs text-zinc-400 italic">{c.recommendation_reason}</p>
                  </div>
                )}

                {/* Promotion Type Badges */}
                {c.promotion_types?.length > 0 && expandedId !== c.id && (
                  <div className="px-4 pb-3 flex gap-2">
                    {c.promotion_types.map(t => {
                      const config = {
                        'exemplar': { icon: Award, color: '#FFCC00', label: 'Exemplar' },
                        'template': { icon: LayoutTemplate, color: '#34C759', label: 'Template' },
                        'style-candidate': { icon: Palette, color: '#AF52DE', label: 'Style' },
                      }[t];
                      if (!config) return null;
                      const Icon = config.icon;
                      return (
                        <span key={t} className="inline-flex items-center gap-1 text-[10px] border px-2 py-0.5" style={{ color: config.color, borderColor: `${config.color}33` }}>
                          <Icon className="w-3 h-3" /> {config.label}
                        </span>
                      );
                    })}
                  </div>
                )}

                {/* Expanded Detail */}
                {expandedId === c.id && (
                  <div className="border-t border-zinc-800">
                    {/* Recommendation */}
                    <div className="p-4 border-b border-zinc-800">
                      <span className="label-uppercase block mb-2">Recommendation</span>
                      <p className="text-sm text-zinc-300">{c.recommendation_reason}</p>
                    </div>

                    {/* Signals */}
                    <div className="p-4 border-b border-zinc-800">
                      <span className="label-uppercase block mb-3">Detection Signals ({c.signals?.length || 0})</span>
                      <div className="space-y-2">
                        {(c.signals || []).map((s, i) => (
                          <div key={i} className="flex items-start gap-3 text-xs">
                            <Zap className="w-3 h-3 text-[#FF9500] mt-0.5 flex-shrink-0" />
                            <div>
                              <span className="text-zinc-300">{s.explanation}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Promotion Paths */}
                    <div className="p-4 border-b border-zinc-800">
                      <span className="label-uppercase block mb-3">Promotion Paths</span>
                      <div className="flex flex-wrap gap-2">
                        {(c.promotion_types || []).map(t => {
                          const config = {
                            'exemplar': { icon: Award, color: '#FFCC00', label: 'Exemplar', desc: 'Reference-quality page' },
                            'template': { icon: LayoutTemplate, color: '#34C759', label: 'House Template', desc: 'Reusable structure' },
                            'style-candidate': { icon: Palette, color: '#AF52DE', label: 'Style Candidate', desc: 'Distinct tonal pattern' },
                          }[t];
                          if (!config) return null;
                          const Icon = config.icon;
                          return (
                            <div key={t} className="p-3 border" style={{ borderColor: `${config.color}33` }}>
                              <div className="flex items-center gap-2 mb-1">
                                <Icon className="w-4 h-4" style={{ color: config.color }} />
                                <span className="text-xs font-medium" style={{ color: config.color }}>{config.label}</span>
                              </div>
                              <p className="text-[10px] text-zinc-500">{config.desc}</p>
                            </div>
                          );
                        })}
                      </div>
                    </div>

                    {/* Action Taken (if resolved) */}
                    {c.action_taken && (
                      <div className="p-4 border-b border-zinc-800">
                        <span className="label-uppercase block mb-2">Action Taken</span>
                        <div className="flex items-center gap-2">
                          {ACTION_CONFIG[c.action_taken] && React.createElement(ACTION_CONFIG[c.action_taken].icon, {
                            className: "w-4 h-4",
                            style: { color: ACTION_CONFIG[c.action_taken].color }
                          })}
                          <span className="text-sm text-zinc-300">{ACTION_CONFIG[c.action_taken]?.label || c.action_taken}</span>
                        </div>
                        {c.resolved_at && (
                          <span className="text-[10px] text-zinc-600 font-mono mt-1 block">
                            {new Date(c.resolved_at).toLocaleString()}
                          </span>
                        )}
                      </div>
                    )}

                    {/* Actions (only for pending/deferred) */}
                    {(c.status === 'pending' || c.status === 'deferred') && (
                      <div className="p-4 flex items-center gap-3 flex-wrap">
                        {c.promotion_types?.includes('exemplar') && (
                          <button
                            onClick={() => takeAction(c.id, 'promote-exemplar')}
                            className="text-xs border border-[#FFCC00]/30 text-[#FFCC00] px-3 py-1.5 hover:bg-[#FFCC00]/10 transition-colors flex items-center gap-1.5"
                            data-testid={`action-exemplar-${c.id}`}
                          >
                            <Award className="w-3 h-3" /> Promote to Exemplar
                          </button>
                        )}
                        {c.promotion_types?.includes('template') && (
                          <button
                            onClick={() => takeAction(c.id, 'create-template')}
                            className="text-xs border border-[#34C759]/30 text-[#34C759] px-3 py-1.5 hover:bg-[#34C759]/10 transition-colors flex items-center gap-1.5"
                            data-testid={`action-template-${c.id}`}
                          >
                            <LayoutTemplate className="w-3 h-3" /> Create Template
                          </button>
                        )}
                        {c.promotion_types?.includes('style-candidate') && (
                          <button
                            onClick={() => takeAction(c.id, 'save-style-candidate')}
                            className="text-xs border border-[#AF52DE]/30 text-[#AF52DE] px-3 py-1.5 hover:bg-[#AF52DE]/10 transition-colors flex items-center gap-1.5"
                            data-testid={`action-style-${c.id}`}
                          >
                            <Palette className="w-3 h-3" /> Save Style Candidate
                          </button>
                        )}
                        <button
                          onClick={() => takeAction(c.id, 'decide-later')}
                          className="text-xs border border-zinc-700 text-zinc-400 px-3 py-1.5 hover:bg-zinc-800 transition-colors flex items-center gap-1.5"
                          data-testid={`action-defer-${c.id}`}
                        >
                          <Clock className="w-3 h-3" /> Decide Later
                        </button>
                        <button
                          onClick={() => takeAction(c.id, 'dismiss')}
                          className="text-xs border border-zinc-700 text-zinc-400 px-3 py-1.5 hover:border-[#FF3B30] hover:text-[#FF3B30] transition-colors flex items-center gap-1.5"
                          data-testid={`action-dismiss-${c.id}`}
                        >
                          <X className="w-3 h-3" /> Dismiss
                        </button>
                      </div>
                    )}

                    {/* Meta */}
                    <div className="px-4 pb-4 text-[10px] text-zinc-600 font-mono">
                      Flagged: {new Date(c.created_at).toLocaleString()}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
