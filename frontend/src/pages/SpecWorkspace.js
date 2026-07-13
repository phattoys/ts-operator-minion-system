import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import axios from 'axios';
import {
  ArrowLeft, Zap, ClipboardCopy, Download, RefreshCw,
  CheckCircle, AlertCircle, Clock, Send, Archive,
  ChevronDown, ChevronUp, History,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const INPUT_FIELDS = [
  { key: 'what_is_it', label: 'What is it?', placeholder: 'Brief description of the thing being built' },
  { key: 'who_is_it_for', label: 'Who is it for?', placeholder: 'Target users or audience' },
  { key: 'what_pain', label: 'What pain does it solve?', placeholder: 'The problem or bottleneck this addresses' },
  { key: 'what_must_it_do', label: 'What must it do?', placeholder: 'Core capabilities, non-negotiable features' },
  { key: 'what_to_avoid', label: 'What should it avoid?', placeholder: 'Scope limits, anti-patterns, things NOT to build' },
  { key: 'success_measurement', label: 'How should success be measured?', placeholder: 'KPIs, metrics, or qualitative signals' },
  { key: 'build_timing', label: 'Build now or later?', placeholder: 'Urgency, dependencies, sequencing' },
  { key: 'cost_risk_notes', label: 'Cost/risk notes', placeholder: 'Budget, timeline, technical risk' },
];

const STATUS_CONFIG = {
  Draft: { icon: Clock, color: 'text-zinc-400', bg: 'bg-zinc-800' },
  Scored: { icon: Zap, color: 'text-amber-400', bg: 'bg-amber-900/30' },
  'Needs Refinement': { icon: AlertCircle, color: 'text-orange-400', bg: 'bg-orange-900/30' },
  Ready: { icon: CheckCircle, color: 'text-emerald-400', bg: 'bg-emerald-900/30' },
  'Handed Off': { icon: Send, color: 'text-blue-400', bg: 'bg-blue-900/30' },
  Archived: { icon: Archive, color: 'text-zinc-500', bg: 'bg-zinc-800/50' },
};

export default function SpecWorkspace() {
  const { specId } = useParams();
  const navigate = useNavigate();
  const [spec, setSpec] = useState(null);
  const [versions, setVersions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [scoring, setScoring] = useState(false);
  const [showInputs, setShowInputs] = useState(false);
  const [showVersions, setShowVersions] = useState(false);
  const [showFollowUp, setShowFollowUp] = useState(false);
  const [inputAnswers, setInputAnswers] = useState({});
  const [followUpAnswers, setFollowUpAnswers] = useState({});
  const [copied, setCopied] = useState(false);

  const fetchSpec = useCallback(async () => {
    try {
      const [specRes, versionsRes] = await Promise.all([
        axios.get(`${API}/specs/${specId}`, { withCredentials: true }),
        axios.get(`${API}/specs/${specId}/versions`, { withCredentials: true }),
      ]);
      setSpec(specRes.data);
      setVersions(versionsRes.data.versions || []);
      setInputAnswers(specRes.data.input_answers || {});
    } catch (err) {
      console.error('Failed to fetch spec:', err);
    }
    setLoading(false);
  }, [specId]);

  useEffect(() => { fetchSpec(); }, [fetchSpec]);

  const handleGenerate = async (regenerate = false) => {
    setGenerating(true);
    try {
      // Save input answers first if any were filled
      const filledAnswers = Object.fromEntries(
        Object.entries(inputAnswers).filter(([, v]) => v?.trim())
      );
      if (Object.keys(filledAnswers).length > 0) {
        await axios.put(`${API}/specs/${specId}`, {
          input_answers: filledAnswers,
        }, { withCredentials: true });
      }

      const res = await axios.post(`${API}/specs/${specId}/generate`, { regenerate }, { withCredentials: true });
      setSpec(res.data.spec);
      await fetchSpec();
    } catch (err) {
      console.error('Generation failed:', err);
    }
    setGenerating(false);
  };

  const handleScore = async () => {
    setScoring(true);
    try {
      const res = await axios.post(`${API}/specs/${specId}/score`, {}, { withCredentials: true });
      setSpec(res.data.spec);
      if (res.data.spec.follow_up_questions?.length > 0) {
        setShowFollowUp(true);
      }
    } catch (err) {
      console.error('Scoring failed:', err);
    }
    setScoring(false);
  };

  const handleFollowUpSubmit = async () => {
    const filled = Object.fromEntries(
      Object.entries(followUpAnswers).filter(([, v]) => v?.trim())
    );
    if (Object.keys(filled).length === 0) return;
    setGenerating(true);
    try {
      const res = await axios.post(`${API}/specs/${specId}/follow-up`, { answers: filled }, { withCredentials: true });
      setSpec(res.data.spec);
      setFollowUpAnswers({});
      setShowFollowUp(false);
      await fetchSpec();
    } catch (err) {
      console.error('Follow-up failed:', err);
    }
    setGenerating(false);
  };

  const handleStatusChange = async (status) => {
    try {
      const res = await axios.post(`${API}/specs/${specId}/status`, { status }, { withCredentials: true });
      setSpec(res.data);
    } catch (err) {
      console.error('Status change failed:', err);
    }
  };

  const handleRestoreVersion = async (versionId) => {
    try {
      const res = await axios.post(`${API}/specs/${specId}/versions/${versionId}/restore`, {}, { withCredentials: true });
      setSpec(res.data);
      await fetchSpec();
    } catch (err) {
      console.error('Restore failed:', err);
    }
  };

  const handleCopy = () => {
    if (spec?.generated_spec) {
      navigator.clipboard.writeText(spec.generated_spec);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleDownload = async () => {
    try {
      const res = await axios.get(`${API}/specs/${specId}/export`, { withCredentials: true });
      const blob = new Blob([res.data.content], { type: 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${spec.title?.replace(/\s+/g, '-').toLowerCase() || 'spec'}.md`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Export failed:', err);
    }
  };

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[50vh]">
        <div className="text-zinc-500 text-sm animate-pulse">Loading spec...</div>
      </div>
    );
  }

  if (!spec) {
    return (
      <div className="p-8">
        <p className="text-zinc-500">Spec not found.</p>
        <Link to="/specs" className="text-white text-sm mt-2 inline-block hover:underline">Back to library</Link>
      </div>
    );
  }

  const statusCfg = STATUS_CONFIG[spec.status] || STATUS_CONFIG.Draft;
  const StatusIcon = statusCfg.icon;

  return (
    <div className="p-8 max-w-[1200px] mx-auto" data-testid="spec-workspace">
      {/* Header */}
      <div className="flex items-center gap-4 mb-6">
        <Link to="/specs" className="text-zinc-500 hover:text-white transition-colors" data-testid="back-to-specs">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div className="flex-1 min-w-0">
          <h1 className="text-2xl font-['Outfit'] text-white truncate">{spec.title}</h1>
          <div className="flex items-center gap-3 mt-1">
            <span className="text-xs text-zinc-500">{spec.spec_type}</span>
            <span className="text-xs text-zinc-700">&middot;</span>
            <span className={`text-xs px-2 py-0.5 ${statusCfg.bg} ${statusCfg.color} flex items-center gap-1`}>
              <StatusIcon className="w-3 h-3" />
              {spec.status}
            </span>
            <span className="text-xs text-zinc-700">&middot;</span>
            <span className="text-xs text-zinc-500">{spec.priority}</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {spec.generated_spec && (
            <>
              <button onClick={handleCopy} className="px-3 py-1.5 text-xs border border-zinc-700 text-zinc-400 hover:text-white hover:border-zinc-500 transition-colors flex items-center gap-1.5" data-testid="copy-spec-btn">
                <ClipboardCopy className="w-3 h-3" />
                {copied ? 'Copied' : 'Copy'}
              </button>
              <button onClick={handleDownload} className="px-3 py-1.5 text-xs border border-zinc-700 text-zinc-400 hover:text-white hover:border-zinc-500 transition-colors flex items-center gap-1.5" data-testid="download-spec-btn">
                <Download className="w-3 h-3" />
                .md
              </button>
            </>
          )}
          <select
            value={spec.status}
            onChange={e => handleStatusChange(e.target.value)}
            className="bg-zinc-900 border border-zinc-700 px-2 py-1.5 text-xs text-white focus:outline-none"
            data-testid="spec-status-select"
          >
            <option value="Draft">Draft</option>
            <option value="Scored">Scored</option>
            <option value="Needs Refinement">Needs Refinement</option>
            <option value="Ready">Ready</option>
            <option value="Handed Off">Handed Off</option>
            <option value="Archived">Archived</option>
          </select>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Left: Main Content */}
        <div className="col-span-2 space-y-6">
          {/* Raw Idea */}
          <div className="border border-zinc-800 p-4">
            <h3 className="text-xs text-zinc-500 uppercase tracking-wider mb-2">Raw Idea</h3>
            <p className="text-sm text-zinc-300 whitespace-pre-wrap">{spec.raw_idea}</p>
          </div>

          {/* Structured Inputs (collapsible) */}
          <div className="border border-zinc-800">
            <button
              onClick={() => setShowInputs(!showInputs)}
              className="w-full flex items-center justify-between p-4 text-left hover:bg-zinc-900/50 transition-colors"
              data-testid="toggle-inputs-btn"
            >
              <span className="text-xs text-zinc-500 uppercase tracking-wider">Structured Inputs</span>
              {showInputs ? <ChevronUp className="w-4 h-4 text-zinc-500" /> : <ChevronDown className="w-4 h-4 text-zinc-500" />}
            </button>
            {showInputs && (
              <div className="px-4 pb-4 space-y-3">
                {INPUT_FIELDS.map(f => (
                  <div key={f.key}>
                    <label className="block text-xs text-zinc-500 mb-1">{f.label}</label>
                    <input
                      value={inputAnswers[f.key] || ''}
                      onChange={e => setInputAnswers(prev => ({ ...prev, [f.key]: e.target.value }))}
                      className="w-full bg-zinc-900 border border-zinc-800 px-3 py-1.5 text-sm text-white placeholder-zinc-600 focus:border-zinc-600 focus:outline-none"
                      placeholder={f.placeholder}
                      data-testid={`input-${f.key}`}
                    />
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Generate / Score Actions */}
          <div className="flex items-center gap-3">
            {!spec.generated_spec ? (
              <button
                onClick={() => handleGenerate(false)}
                disabled={generating}
                className="flex items-center gap-2 px-5 py-2.5 bg-white text-black text-sm font-medium hover:bg-zinc-200 transition-colors disabled:opacity-40"
                data-testid="generate-spec-btn"
              >
                <Zap className="w-4 h-4" />
                {generating ? 'Generating...' : 'Generate Spec'}
              </button>
            ) : (
              <>
                <button
                  onClick={() => handleGenerate(true)}
                  disabled={generating}
                  className="flex items-center gap-2 px-4 py-2 border border-zinc-700 text-sm text-zinc-300 hover:text-white hover:border-zinc-500 transition-colors disabled:opacity-40"
                  data-testid="regenerate-spec-btn"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  {generating ? 'Generating...' : 'Regenerate'}
                </button>
                <button
                  onClick={handleScore}
                  disabled={scoring}
                  className="flex items-center gap-2 px-5 py-2 bg-white text-black text-sm font-medium hover:bg-zinc-200 transition-colors disabled:opacity-40"
                  data-testid="score-spec-btn"
                >
                  <Zap className="w-4 h-4" />
                  {scoring ? 'Scoring...' : 'Score Completeness'}
                </button>
              </>
            )}
          </div>

          {/* Generated Spec */}
          {spec.generated_spec && (
            <div className="border border-zinc-800 p-6" data-testid="generated-spec-content">
              <h3 className="text-xs text-zinc-500 uppercase tracking-wider mb-4">Generated Spec</h3>
              <div className="prose prose-invert prose-sm max-w-none text-zinc-300 whitespace-pre-wrap font-mono text-xs leading-relaxed">
                {spec.generated_spec}
              </div>
            </div>
          )}

          {/* Follow-Up Questions */}
          {showFollowUp && spec.follow_up_questions?.length > 0 && (
            <div className="border border-orange-900/50 bg-orange-950/10 p-4" data-testid="follow-up-section">
              <h3 className="text-xs text-orange-400 uppercase tracking-wider mb-3">Follow-Up Questions</h3>
              <p className="text-xs text-zinc-500 mb-4">Answer what matters. Skip what doesn't. Then regenerate.</p>
              <div className="space-y-3">
                {spec.follow_up_questions.map((q, i) => (
                  <div key={i}>
                    <label className="block text-xs text-zinc-400 mb-1">{q}</label>
                    <input
                      value={followUpAnswers[q] || ''}
                      onChange={e => setFollowUpAnswers(prev => ({ ...prev, [q]: e.target.value }))}
                      className="w-full bg-zinc-900 border border-zinc-800 px-3 py-1.5 text-sm text-white placeholder-zinc-600 focus:border-zinc-600 focus:outline-none"
                      placeholder="Your answer..."
                      data-testid={`follow-up-${i}`}
                    />
                  </div>
                ))}
              </div>
              <button
                onClick={handleFollowUpSubmit}
                disabled={generating}
                className="mt-4 flex items-center gap-2 px-4 py-2 bg-white text-black text-sm font-medium hover:bg-zinc-200 transition-colors disabled:opacity-40"
                data-testid="submit-follow-up-btn"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                {generating ? 'Regenerating...' : 'Answer & Regenerate'}
              </button>
            </div>
          )}
        </div>

        {/* Right: Sidebar */}
        <div className="space-y-6">
          {/* Score Card */}
          {spec.completeness_score != null && (
            <div className="border border-zinc-800 p-4" data-testid="spec-score-card">
              <h3 className="text-xs text-zinc-500 uppercase tracking-wider mb-3">Completeness Score</h3>
              <div className="text-3xl font-['Outfit'] text-white mb-3">{spec.completeness_score}<span className="text-sm text-zinc-500">/100</span></div>
              {spec.score_breakdown && (
                <div className="space-y-2">
                  {Object.entries(spec.score_breakdown).map(([dim, score]) => (
                    <div key={dim} className="flex items-center justify-between">
                      <span className="text-xs text-zinc-500 capitalize">{dim.replace(/_/g, ' ')}</span>
                      <div className="flex items-center gap-2">
                        <div className="w-16 h-1 bg-zinc-800 overflow-hidden">
                          <div
                            className={`h-full transition-all ${score >= 85 ? 'bg-emerald-500' : score >= 70 ? 'bg-amber-500' : 'bg-red-500'}`}
                            style={{ width: `${score}%` }}
                          />
                        </div>
                        <span className="text-xs text-zinc-400 font-mono w-6 text-right">{score}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              {spec.follow_up_questions?.length > 0 && !showFollowUp && (
                <button
                  onClick={() => setShowFollowUp(true)}
                  className="mt-3 w-full py-2 text-xs text-orange-400 border border-orange-900/50 hover:bg-orange-950/20 transition-colors"
                  data-testid="show-follow-up-btn"
                >
                  {spec.follow_up_questions.length} follow-up question{spec.follow_up_questions.length > 1 ? 's' : ''}
                </button>
              )}
            </div>
          )}

          {/* Metadata */}
          <div className="border border-zinc-800 p-4">
            <h3 className="text-xs text-zinc-500 uppercase tracking-wider mb-3">Details</h3>
            <div className="space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="text-zinc-500">Type</span>
                <span className="text-zinc-300">{spec.spec_type}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500">Priority</span>
                <span className="text-zinc-300">{spec.priority}</span>
              </div>
              {spec.complexity_estimate && (
                <div className="flex justify-between">
                  <span className="text-zinc-500">Complexity</span>
                  <span className="text-zinc-300">{spec.complexity_estimate}</span>
                </div>
              )}
              {spec.target_audience && (
                <div className="flex justify-between">
                  <span className="text-zinc-500">Audience</span>
                  <span className="text-zinc-300 text-right max-w-[60%]">{spec.target_audience}</span>
                </div>
              )}
              {spec.constraints && (
                <div className="flex justify-between">
                  <span className="text-zinc-500">Constraints</span>
                  <span className="text-zinc-300 text-right max-w-[60%]">{spec.constraints}</span>
                </div>
              )}
              <div className="flex justify-between pt-2 border-t border-zinc-800">
                <span className="text-zinc-500">Created</span>
                <span className="text-zinc-400">{new Date(spec.created_at).toLocaleDateString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500">Updated</span>
                <span className="text-zinc-400">{new Date(spec.updated_at).toLocaleDateString()}</span>
              </div>
            </div>
          </div>

          {/* Version History */}
          <div className="border border-zinc-800">
            <button
              onClick={() => setShowVersions(!showVersions)}
              className="w-full flex items-center justify-between p-4 hover:bg-zinc-900/50 transition-colors"
              data-testid="toggle-versions-btn"
            >
              <div className="flex items-center gap-2">
                <History className="w-3.5 h-3.5 text-zinc-500" />
                <span className="text-xs text-zinc-500 uppercase tracking-wider">Versions ({versions.length})</span>
              </div>
              {showVersions ? <ChevronUp className="w-4 h-4 text-zinc-500" /> : <ChevronDown className="w-4 h-4 text-zinc-500" />}
            </button>
            {showVersions && versions.length > 0 && (
              <div className="px-4 pb-4 space-y-2">
                {versions.map(v => (
                  <div key={v.id} className={`flex items-center justify-between p-2 text-xs ${v.is_current ? 'border border-zinc-700 bg-zinc-900/50' : 'border border-transparent'}`}>
                    <div>
                      <span className="text-white">v{v.version_number}</span>
                      <span className="text-zinc-500 ml-2">{v.generation_trigger}</span>
                      {v.completeness_score && <span className="text-zinc-400 ml-2">{v.completeness_score}/100</span>}
                      {v.is_current && <span className="text-emerald-500 ml-2">current</span>}
                    </div>
                    {!v.is_current && (
                      <button
                        onClick={() => handleRestoreVersion(v.id)}
                        className="text-zinc-500 hover:text-white transition-colors"
                        data-testid={`restore-version-${v.version_number}`}
                      >
                        Restore
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
