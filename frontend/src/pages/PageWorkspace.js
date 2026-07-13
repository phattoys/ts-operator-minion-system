import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import axios from 'axios';
import { 
  ArrowLeft, Zap, BarChart3, Check, RefreshCw, 
  Clock, AlertTriangle, ChevronDown, ChevronUp,
  FileText, Trash2, Download, Copy, Sparkles, Wand2,
  Award, Crown, Tag, History, RotateCcw, LayoutTemplate, Palette
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function PageWorkspace() {
  const { pageId } = useParams();
  const navigate = useNavigate();
  const [page, setPage] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [scoring, setScoring] = useState(false);
  const [tightening, setTightening] = useState(false);
  const [variantGenerating, setVariantGenerating] = useState(false);
  const [tone, setTone] = useState('professional');
  const [additionalInstructions, setAdditionalInstructions] = useState('');
  const [showScoreDetails, setShowScoreDetails] = useState(false);
  const [showVariants, setShowVariants] = useState(false);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);
  // Version History state
  const [versions, setVersions] = useState([]);
  const [showVersions, setShowVersions] = useState(false);
  const [currentVersion, setCurrentVersion] = useState(null);
  // Exemplar state
  const [showExemplarForm, setShowExemplarForm] = useState(false);
  const [exemplarVersion, setExemplarVersion] = useState(null);
  const [exemplarTags, setExemplarTags] = useState([]);
  const [exemplarNotes, setExemplarNotes] = useState('');
  const [exemplarPrimary, setExemplarPrimary] = useState(false);
  const [savingExemplar, setSavingExemplar] = useState(false);
  const [availableReasonTags, setAvailableReasonTags] = useState([]);
  const [pageExemplars, setPageExemplars] = useState([]);
  // House Template state
  const [useTemplate, setUseTemplate] = useState(true);
  const [familyTemplate, setFamilyTemplate] = useState(null);
  const [showTemplateForm, setShowTemplateForm] = useState(false);
  const [templateVersion, setTemplateVersion] = useState(null);
  const [templateName, setTemplateName] = useState('');
  const [templatePurpose, setTemplatePurpose] = useState('');
  const [templateToneGuidance, setTemplateToneGuidance] = useState('');
  const [templatePrimary, setTemplatePrimary] = useState(false);
  const [savingTemplate, setSavingTemplate] = useState(false);
  const [extractedPattern, setExtractedPattern] = useState('');
  // Style Profile state
  const [useStyleProfile, setUseStyleProfile] = useState(true);
  const [familyStyleProfile, setFamilyStyleProfile] = useState(null);
  // Promotion state
  const [promotionCandidate, setPromotionCandidate] = useState(null);
  const [promotionDismissed, setPromotionDismissed] = useState(false);
  // Content Direction state
  const [showContentDirection, setShowContentDirection] = useState(false);
  const [contentDirection, setContentDirection] = useState({});

  const variants = [
    { id: 'luxurious', name: 'Luxurious', desc: 'Premium, elevated' },
    { id: 'warmer', name: 'Warmer', desc: 'Personal, comforting' },
    { id: 'direct', name: 'Direct', desc: 'Action-oriented, clear' },
    { id: 'trust-heavy', name: 'Trust-Heavy', desc: 'Credibility focused' },
    { id: 'educational', name: 'Educational', desc: 'Informative, guiding' },
    { id: 'commanding', name: 'Commanding', desc: 'Authoritative' },
    { id: 'feminine', name: 'Feminine', desc: 'Elegant, intuitive' },
    { id: 'grounded', name: 'Grounded', desc: 'Specific, concrete' }
  ];

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    fetchPage();
    fetchVersions();
    fetchExemplarData();
    fetchPagePromotions();
  }, [pageId]);

  const fetchPage = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/pages/${pageId}`, { withCredentials: true });
      setPage(res.data);
      // Fetch family template when page loads
      if (res.data.page_family) {
        fetchFamilyTemplate(res.data.page_family);
      }
    } catch (err) {
      setError('Page not found');
    }
    setLoading(false);
  };

  const fetchVersions = async () => {
    try {
      const res = await axios.get(`${API}/pages/${pageId}/versions`, { withCredentials: true });
      setVersions(res.data.versions || []);
      setCurrentVersion(res.data.current_version);
    } catch (err) {
      // Versions might not exist yet
    }
  };

  const fetchExemplarData = async () => {
    try {
      const [tagsRes, exemplarsRes] = await Promise.all([
        axios.get(`${API}/exemplars/reason-tags/options`, { withCredentials: true }),
        axios.get(`${API}/exemplars`, { withCredentials: true })
      ]);
      setAvailableReasonTags(tagsRes.data.tags || []);
      const allExemplars = exemplarsRes.data.exemplars || [];
      setPageExemplars(allExemplars.filter(e => e.page_id === pageId));
    } catch (err) {
      // Non-critical
    }
  };

  const fetchFamilyTemplate = async (family) => {
    try {
      const [templateRes, styleRes] = await Promise.all([
        axios.get(`${API}/house-templates/family/${encodeURIComponent(family)}`, { withCredentials: true }),
        axios.get(`${API}/style-profiles/family/${encodeURIComponent(family)}`, { withCredentials: true })
      ]);
      setFamilyTemplate(templateRes.data.primary_template || null);
      setFamilyStyleProfile(styleRes.data.default_profile || null);
    } catch (err) {
      setFamilyTemplate(null);
      setFamilyStyleProfile(null);
    }
  };

  const fetchPagePromotions = async () => {
    try {
      const res = await axios.get(`${API}/promotions/page/${pageId}`, { withCredentials: true });
      const pending = (res.data.candidates || []).find(c => c.status === 'pending' || c.status === 'deferred');
      setPromotionCandidate(pending || null);
      setPromotionDismissed(false);
    } catch (err) {
      // Non-critical
    }
  };

  const handlePromotionAction = async (action) => {
    if (!promotionCandidate) return;
    try {
      await axios.post(`${API}/promotions/candidates/${promotionCandidate.id}/action`, {
        action,
        is_primary: false
      }, { withCredentials: true });
      if (action === 'dismiss') {
        setPromotionDismissed(true);
      }
      fetchPagePromotions();
      if (action === 'promote-exemplar') fetchExemplarData();
    } catch (err) {
      setError(err.response?.data?.detail || 'Promotion action failed');
    }
  };

  const generateContent = async () => {
    setGenerating(true);
    setError('');
    try {
      const res = await axios.post(`${API}/pages/${pageId}/generate`, {
        tone,
        additional_instructions: additionalInstructions || null,
        use_house_template: useTemplate,
        use_style_profile: useStyleProfile,
        content_direction: Object.keys(contentDirection).length > 0 ? contentDirection : null
      }, { withCredentials: true });
      setPage(res.data);
      fetchVersions();
    } catch (err) {
      setError(err.response?.data?.detail || 'Generation failed');
    }
    setGenerating(false);
  };

  const tightenContent = async () => {
    setTightening(true);
    setError('');
    try {
      const res = await axios.post(`${API}/pages/${pageId}/tighten`, {
        apply_to_current: true
      }, { withCredentials: true });
      setPage(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Tightening failed');
    }
    setTightening(false);
  };

  const generateVariant = async (variantId) => {
    setVariantGenerating(true);
    setShowVariants(false);
    setError('');
    try {
      const res = await axios.post(`${API}/pages/${pageId}/variant`, {
        variant: variantId,
        save_as_current: true
      }, { withCredentials: true });
      setPage(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Variant generation failed');
    }
    setVariantGenerating(false);
  };

  const scoreContent = async () => {
    setScoring(true);
    setError('');
    try {
      const res = await axios.post(`${API}/pages/${pageId}/score`, {}, { withCredentials: true });
      setPage(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Scoring failed');
    }
    setScoring(false);
  };

  const handleAction = async (action) => {
    try {
      const res = await axios.post(`${API}/pages/${pageId}/${action}`, {}, { withCredentials: true });
      setPage(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || `${action} failed`);
    }
  };

  const deletePage = async () => {
    if (!window.confirm('Are you sure you want to delete this page?')) return;
    try {
      await axios.delete(`${API}/pages/${pageId}`, { withCredentials: true });
      navigate('/queue');
    } catch (err) {
      setError('Delete failed');
    }
  };

  const exportPage = async (format = 'markdown') => {
    try {
      const res = await axios.get(`${API}/pages/${pageId}/export?format=${format}`, { withCredentials: true });
      const content = res.data.content;
      
      // Create download
      const blob = new Blob([content], { type: 'text/plain' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${page.slug}.${format === 'markdown' ? 'md' : 'txt'}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      setError('Export failed');
    }
  };

  const copyContent = async () => {
    if (page?.generated_content) {
      await navigator.clipboard.writeText(page.generated_content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const restoreVersion = async (versionId) => {
    try {
      await axios.post(`${API}/pages/${pageId}/versions/${versionId}/restore`, {
        preserve_current_as_version: true
      }, { withCredentials: true });
      fetchPage();
      fetchVersions();
    } catch (err) {
      setError('Restore failed');
    }
  };

  const openExemplarForm = (version) => {
    setExemplarVersion(version);
    setExemplarTags([]);
    setExemplarNotes('');
    setExemplarPrimary(false);
    setShowExemplarForm(true);
  };

  const saveExemplar = async () => {
    if (!exemplarVersion) return;
    setSavingExemplar(true);
    setError('');
    try {
      await axios.post(`${API}/exemplars`, {
        page_id: pageId,
        version_id: exemplarVersion.id,
        reason_tags: exemplarTags,
        exemplar_notes: exemplarNotes || null,
        is_primary: exemplarPrimary
      }, { withCredentials: true });
      setShowExemplarForm(false);
      setExemplarVersion(null);
      fetchVersions();
      fetchExemplarData();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create exemplar');
    }
    setSavingExemplar(false);
  };

  const toggleReasonTag = (tag) => {
    setExemplarTags(prev => 
      prev.includes(tag) ? prev.filter(t => t !== tag) : [...prev, tag]
    );
  };

  const isVersionExemplar = (versionId) => {
    return pageExemplars.some(e => e.version_id === versionId);
  };

  const openTemplateForm = async (version) => {
    setTemplateVersion(version);
    setTemplateName('');
    setTemplatePurpose('');
    setTemplateToneGuidance('');
    setTemplatePrimary(false);
    setExtractedPattern('');
    setShowTemplateForm(true);
    // Auto-extract structure
    try {
      const res = await axios.post(
        `${API}/house-templates/extract-structure?page_id=${pageId}&version_id=${version.id}`,
        {}, { withCredentials: true }
      );
      setExtractedPattern(res.data.structural_pattern || '');
    } catch (err) {
      console.error('Failed to extract structure:', err);
    }
  };

  const saveTemplate = async () => {
    if (!templateVersion || !templateName.trim()) return;
    setSavingTemplate(true);
    setError('');
    try {
      await axios.post(`${API}/house-templates`, {
        template_name: templateName,
        purpose: templatePurpose,
        page_family: page?.page_family,
        page_type: page?.page_type || null,
        source_page_id: pageId,
        source_version_id: templateVersion.id,
        structural_pattern: extractedPattern,
        tone_guidance: templateToneGuidance || null,
        is_primary: templatePrimary
      }, { withCredentials: true });
      setShowTemplateForm(false);
      setTemplateVersion(null);
      if (page?.page_family) fetchFamilyTemplate(page.page_family);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create template');
    }
    setSavingTemplate(false);
  };

  const getStatusColor = (status) => {
    const colors = {
      'Approved': 'border-[#34C759] text-[#34C759] bg-[#34C759]/10',
      'Needs Review': 'border-[#FFCC00] text-[#FFCC00] bg-[#FFCC00]/10',
      'Draft Ready': 'border-[#FFCC00] text-[#FFCC00] bg-[#FFCC00]/10',
      'Needs Rewrite': 'border-[#FF3B30] text-[#FF3B30] bg-[#FF3B30]/10',
      'Planned': 'border-zinc-600 text-zinc-400 bg-zinc-800/50',
      'Deferred': 'border-zinc-600 text-zinc-500 bg-zinc-800/50',
      'Generating': 'border-[#FFCC00] text-[#FFCC00] bg-[#FFCC00]/10'
    };
    return colors[status] || 'border-zinc-600 text-zinc-400';
  };

  const getScoreColor = (score) => {
    if (score >= 85) return 'text-[#34C759]';
    if (score >= 70) return 'text-[#FFCC00]';
    return 'text-[#FF3B30]';
  };

  if (loading) {
    return (
      <div className="p-6 md:p-8">
        <div className="animate-pulse space-y-6">
          <div className="h-8 bg-zinc-800 w-48"></div>
          <div className="h-64 bg-zinc-800"></div>
        </div>
      </div>
    );
  }

  if (!page) {
    return (
      <div className="p-6 md:p-8 text-center">
        <FileText className="w-12 h-12 mx-auto mb-4 text-zinc-600" />
        <h2 className="text-xl text-white mb-2">Page Not Found</h2>
        <Link to="/queue" className="text-zinc-400 hover:text-white">
          ← Back to Queue
        </Link>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex">
      {/* Main Content */}
      <div className="flex-1 p-6 md:p-8 overflow-y-auto">
        {/* Header */}
        <div className="flex items-start justify-between mb-6">
          <div>
            <Link 
              to="/queue" 
              className="inline-flex items-center gap-2 text-zinc-500 hover:text-white mb-4 text-sm"
              data-testid="back-to-queue"
            >
              <ArrowLeft className="w-4 h-4" />
              Back to Queue
            </Link>
            <h1 
              className="font-['Outfit'] text-3xl font-light tracking-tight text-white"
              data-testid="page-title"
            >
              {page.page_name}
            </h1>
            <div className="flex items-center gap-4 mt-2">
              <span className={`badge-flat border ${getStatusColor(page.status)}`}>
                {page.status}
              </span>
              <span className="text-zinc-500 text-sm">{page.page_family}</span>
              <span className="text-zinc-600 text-sm">P{page.priority_score}</span>
            </div>
          </div>
          <button
            onClick={deletePage}
            className="p-2 text-zinc-500 hover:text-[#FF3B30] transition-colors"
            data-testid="delete-page-btn"
          >
            <Trash2 className="w-5 h-5" />
          </button>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-6 p-4 border border-[#FF3B30]/30 bg-[#FF3B30]/10 text-[#FF3B30] text-sm flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" />
            {error}
          </div>
        )}

        {/* Page Details */}
        <div className="border border-zinc-800 mb-6">
          <div className="p-4 border-b border-zinc-800">
            <h2 className="font-['Outfit'] text-lg font-medium">Page Details</h2>
          </div>
          <div className="p-4 grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="label-uppercase block mb-1">Type</span>
              <span className="text-white">{page.page_type}</span>
            </div>
            <div>
              <span className="label-uppercase block mb-1">District</span>
              <span className="text-white">{page.district_or_pillar || '—'}</span>
            </div>
            <div>
              <span className="label-uppercase block mb-1">Audience</span>
              <span className="text-white">{page.audience || '—'}</span>
            </div>
            <div>
              <span className="label-uppercase block mb-1">CTA</span>
              <span className="text-white">{page.CTA_type || '—'}</span>
            </div>
            <div className="col-span-2">
              <span className="label-uppercase block mb-1">Purpose</span>
              <span className="text-white">{page.purpose || '—'}</span>
            </div>
            <div className="col-span-2">
              <span className="label-uppercase block mb-1">Notes</span>
              <span className="text-white">{page.notes || '—'}</span>
            </div>
          </div>
        </div>

        {/* Generation Controls */}
        <div className="border border-zinc-800 mb-6">
          <div className="p-4 border-b border-zinc-800">
            <h2 className="font-['Outfit'] text-lg font-medium">Generate Content</h2>
          </div>
          <div className="p-4 space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="label-uppercase block mb-2">Tone</label>
                <select
                  value={tone}
                  onChange={(e) => setTone(e.target.value)}
                  className="input-flat w-full"
                  data-testid="tone-select"
                >
                  <option value="professional">Professional</option>
                  <option value="friendly">Friendly</option>
                  <option value="playful">Playful</option>
                  <option value="authoritative">Authoritative</option>
                  <option value="casual">Casual</option>
                </select>
              </div>
              <div>
                <label className="label-uppercase block mb-2">Additional Instructions</label>
                <input
                  type="text"
                  value={additionalInstructions}
                  onChange={(e) => setAdditionalInstructions(e.target.value)}
                  className="input-flat w-full"
                  placeholder="Optional: special instructions..."
                  data-testid="instructions-input"
                />
              </div>
            </div>

            {/* Content Direction (Trust & FAQ/Support families) */}
            {(page?.page_family === 'Trust' || page?.page_family === 'FAQ/Support') && (
              <div className="border border-zinc-800" data-testid="content-direction-section">
                <button
                  onClick={() => setShowContentDirection(!showContentDirection)}
                  className="w-full p-3 flex items-center justify-between text-left hover:bg-zinc-900/50 transition-colors"
                  data-testid="toggle-content-direction"
                >
                  <span className="text-xs text-zinc-300 flex items-center gap-2">
                    <Zap className="w-3 h-3 text-[#FF9500]" />
                    Content Direction
                    <span className="text-[10px] text-zinc-500">
                      ({Object.values(contentDirection).filter(Boolean).length} inputs set)
                    </span>
                  </span>
                  {showContentDirection ? <ChevronUp className="w-3 h-3 text-zinc-500" /> : <ChevronDown className="w-3 h-3 text-zinc-500" />}
                </button>

                {showContentDirection && (
                  <div className="p-3 pt-0 space-y-3">
                    {page?.page_family === 'Trust' && (
                      <>
                        <div>
                          <label className="text-[10px] text-zinc-500 uppercase tracking-wider block mb-1">Trust Angle (what matters most)</label>
                          <input
                            value={contentDirection.trust_angle || ''}
                            onChange={(e) => setContentDirection({...contentDirection, trust_angle: e.target.value})}
                            className="input-flat w-full text-xs"
                            placeholder="e.g. privacy, shipping discretion, body-safe curation, support quality..."
                            data-testid="cd-trust-angle"
                          />
                        </div>
                        <div>
                          <label className="text-[10px] text-zinc-500 uppercase tracking-wider block mb-1">Privacy / Discretion Focus</label>
                          <input
                            value={contentDirection.privacy_focus || ''}
                            onChange={(e) => setContentDirection({...contentDirection, privacy_focus: e.target.value})}
                            className="input-flat w-full text-xs"
                            placeholder="e.g. emphasize packaging discretion, billing privacy..."
                            data-testid="cd-privacy-focus"
                          />
                        </div>
                        <div>
                          <label className="text-[10px] text-zinc-500 uppercase tracking-wider block mb-1">First-Time Buyer Reassurance</label>
                          <input
                            value={contentDirection.first_time_reassurance || ''}
                            onChange={(e) => setContentDirection({...contentDirection, first_time_reassurance: e.target.value})}
                            className="input-flat w-full text-xs"
                            placeholder="e.g. no judgment, easy returns, starter guidance..."
                            data-testid="cd-first-time"
                          />
                        </div>
                        <div>
                          <label className="text-[10px] text-zinc-500 uppercase tracking-wider block mb-1">Proof Style</label>
                          <select
                            value={contentDirection.proof_style || ''}
                            onChange={(e) => setContentDirection({...contentDirection, proof_style: e.target.value})}
                            className="input-flat w-full text-xs"
                            data-testid="cd-proof-style"
                          >
                            <option value="">Choose...</option>
                            <option value="literal quotes">Literal quotes</option>
                            <option value="paraphrased stories">Paraphrased stories</option>
                            <option value="thematic impressions">Thematic impressions</option>
                            <option value="mixed">Mixed</option>
                          </select>
                        </div>
                        <div>
                          <label className="text-[10px] text-zinc-500 uppercase tracking-wider block mb-1">Professionalism vs Warmth</label>
                          <select
                            value={contentDirection.professionalism_vs_warmth || ''}
                            onChange={(e) => setContentDirection({...contentDirection, professionalism_vs_warmth: e.target.value})}
                            className="input-flat w-full text-xs"
                            data-testid="cd-prof-warmth"
                          >
                            <option value="">Choose...</option>
                            <option value="mostly professional">Mostly professional</option>
                            <option value="balanced">Balanced</option>
                            <option value="mostly warm">Mostly warm</option>
                          </select>
                        </div>
                      </>
                    )}

                    {page?.page_family === 'FAQ/Support' && (
                      <>
                        <div>
                          <label className="text-[10px] text-zinc-500 uppercase tracking-wider block mb-1">Topics to Cover</label>
                          <textarea
                            value={contentDirection.topics_to_cover || ''}
                            onChange={(e) => setContentDirection({...contentDirection, topics_to_cover: e.target.value})}
                            className="input-flat w-full text-xs h-14 resize-none"
                            placeholder="e.g. cleaning silicone toys, lube compatibility, battery care..."
                            data-testid="cd-topics"
                          />
                        </div>
                        <div>
                          <label className="text-[10px] text-zinc-500 uppercase tracking-wider block mb-1">Material Context</label>
                          <input
                            value={contentDirection.material_context || ''}
                            onChange={(e) => setContentDirection({...contentDirection, material_context: e.target.value})}
                            className="input-flat w-full text-xs"
                            placeholder="e.g. silicone, glass, stainless steel, ABS plastic..."
                            data-testid="cd-materials"
                          />
                        </div>
                        <div>
                          <label className="text-[10px] text-zinc-500 uppercase tracking-wider block mb-1">Lube Compatibility</label>
                          <input
                            value={contentDirection.lube_compatibility || ''}
                            onChange={(e) => setContentDirection({...contentDirection, lube_compatibility: e.target.value})}
                            className="input-flat w-full text-xs"
                            placeholder="e.g. water-based only for silicone, avoid oil-based..."
                            data-testid="cd-lube"
                          />
                        </div>
                        <div>
                          <label className="text-[10px] text-zinc-500 uppercase tracking-wider block mb-1">Cleaning & Storage Rules</label>
                          <input
                            value={contentDirection.cleaning_storage || ''}
                            onChange={(e) => setContentDirection({...contentDirection, cleaning_storage: e.target.value})}
                            className="input-flat w-full text-xs"
                            placeholder="e.g. warm water + mild soap, store individually, avoid alcohol..."
                            data-testid="cd-cleaning"
                          />
                        </div>
                        <div>
                          <label className="text-[10px] text-zinc-500 uppercase tracking-wider block mb-1">Body-Safety Points</label>
                          <input
                            value={contentDirection.body_safety || ''}
                            onChange={(e) => setContentDirection({...contentDirection, body_safety: e.target.value})}
                            className="input-flat w-full text-xs"
                            placeholder="e.g. body-safe materials only, phthalate-free, non-porous..."
                            data-testid="cd-safety"
                          />
                        </div>
                        <div>
                          <label className="text-[10px] text-zinc-500 uppercase tracking-wider block mb-1">Detail Level</label>
                          <select
                            value={contentDirection.detail_level || ''}
                            onChange={(e) => setContentDirection({...contentDirection, detail_level: e.target.value})}
                            className="input-flat w-full text-xs"
                            data-testid="cd-detail-level"
                          >
                            <option value="">Choose...</option>
                            <option value="low">Low (overview)</option>
                            <option value="medium">Medium (practical)</option>
                            <option value="high">High (comprehensive with specifics)</option>
                          </select>
                        </div>
                      </>
                    )}

                    {Object.values(contentDirection).filter(Boolean).length > 0 && (
                      <button
                        onClick={() => setContentDirection({})}
                        className="text-[10px] text-zinc-500 hover:text-white"
                        data-testid="clear-content-direction"
                      >
                        Clear all inputs
                      </button>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* House Template Toggle */}
            {familyTemplate && (
              <div className="p-3 border border-zinc-800 bg-zinc-900/50" data-testid="template-toggle-section">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <LayoutTemplate className="w-4 h-4 text-[#34C759]" />
                    <span className="text-xs text-zinc-300">
                      Template: <span className="text-white">{familyTemplate.template_name}</span>
                    </span>
                  </div>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <span className="text-[10px] text-zinc-500">
                      {useTemplate ? 'ON' : 'OFF'}
                    </span>
                    <input
                      type="checkbox"
                      checked={useTemplate}
                      onChange={(e) => setUseTemplate(e.target.checked)}
                      className="accent-[#34C759]"
                      data-testid="use-template-toggle"
                    />
                  </label>
                </div>
                {useTemplate && (
                  <p className="text-[10px] text-zinc-500 mt-1">
                    Structural guidance will be applied during generation. Uncheck to bypass.
                  </p>
                )}
              </div>
            )}

            {/* Style Profile Toggle */}
            {familyStyleProfile && (
              <div className="p-3 border border-zinc-800 bg-zinc-900/50" data-testid="style-toggle-section">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Palette className="w-4 h-4 text-[#AF52DE]" />
                    <span className="text-xs text-zinc-300">
                      Style: <span className="text-white">{familyStyleProfile.profile_name}</span>
                    </span>
                  </div>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <span className="text-[10px] text-zinc-500">
                      {useStyleProfile ? 'ON' : 'OFF'}
                    </span>
                    <input
                      type="checkbox"
                      checked={useStyleProfile}
                      onChange={(e) => setUseStyleProfile(e.target.checked)}
                      className="accent-[#AF52DE]"
                      data-testid="use-style-toggle"
                    />
                  </label>
                </div>
                {useStyleProfile && (
                  <p className="text-[10px] text-zinc-500 mt-1">
                    Tonal layer will shape how generated content feels. Uncheck to bypass.
                  </p>
                )}
              </div>
            )}

            <div className="flex gap-3">
              <button
                onClick={generateContent}
                disabled={generating}
                className="btn-primary flex items-center gap-2 disabled:opacity-50"
                data-testid="generate-btn"
              >
                {generating ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    Generating...
                  </>
                ) : (
                  <>
                    <Zap className="w-4 h-4" />
                    Generate Draft
                  </>
                )}
              </button>
              {page.generated_content && (
                <>
                  <button
                    onClick={scoreContent}
                    disabled={scoring}
                    className="btn-secondary flex items-center gap-2 disabled:opacity-50"
                    data-testid="score-btn"
                  >
                    {scoring ? (
                      <>
                        <RefreshCw className="w-4 h-4 animate-spin" />
                        Scoring...
                      </>
                    ) : (
                      <>
                        <BarChart3 className="w-4 h-4" />
                        Score
                      </>
                    )}
                  </button>
                  <button
                    onClick={tightenContent}
                    disabled={tightening}
                    className="btn-secondary flex items-center gap-2 disabled:opacity-50"
                    data-testid="tighten-btn"
                    title="Apply Taste Tightener - makes content feel more real and less AI-polished"
                  >
                    {tightening ? (
                      <>
                        <RefreshCw className="w-4 h-4 animate-spin" />
                        Tightening...
                      </>
                    ) : (
                      <>
                        <Sparkles className="w-4 h-4" />
                        Tighten
                      </>
                    )}
                  </button>
                  <div className="relative">
                    <button
                      onClick={() => setShowVariants(!showVariants)}
                      disabled={variantGenerating}
                      className="btn-secondary flex items-center gap-2 disabled:opacity-50"
                      data-testid="variant-btn"
                    >
                      {variantGenerating ? (
                        <>
                          <RefreshCw className="w-4 h-4 animate-spin" />
                          Generating...
                        </>
                      ) : (
                        <>
                          <Wand2 className="w-4 h-4" />
                          Variant
                          <ChevronDown className="w-3 h-3" />
                        </>
                      )}
                    </button>
                    {showVariants && (
                      <div className="absolute top-full left-0 mt-1 w-48 bg-[#09090B] border border-zinc-800 z-10">
                        {variants.map(v => (
                          <button
                            key={v.id}
                            onClick={() => generateVariant(v.id)}
                            className="w-full text-left px-3 py-2 text-sm hover:bg-zinc-800 transition-colors"
                            data-testid={`variant-${v.id}`}
                          >
                            <div className="text-white">{v.name}</div>
                            <div className="text-xs text-zinc-500">{v.desc}</div>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Generated Content */}
        {page.generated_content && (
          <div className="border border-zinc-800">
            <div className="p-4 border-b border-zinc-800 flex items-center justify-between">
              <div className="flex items-center gap-4">
                <h2 className="font-['Outfit'] text-lg font-medium">Generated Draft</h2>
                {page.generation_history?.length > 0 && (
                  <span className="text-xs text-zinc-500">
                    v{page.generation_history.length}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={copyContent}
                  className="p-2 text-zinc-500 hover:text-white transition-colors"
                  title="Copy to clipboard"
                  data-testid="copy-content-btn"
                >
                  {copied ? <Check className="w-4 h-4 text-[#34C759]" /> : <Copy className="w-4 h-4" />}
                </button>
                <button
                  onClick={() => exportPage('markdown')}
                  className="p-2 text-zinc-500 hover:text-white transition-colors"
                  title="Export as Markdown"
                  data-testid="export-md-btn"
                >
                  <Download className="w-4 h-4" />
                </button>
              </div>
            </div>
            <div className="content-preview max-h-[500px] overflow-y-auto" data-testid="generated-content">
              {page.generated_content}
            </div>
          </div>
        )}
      </div>

      {/* Sidebar */}
      <div className="workspace-sidebar hidden lg:block overflow-y-auto">
        {/* Quality Score */}
        {page.quality_score && (
          <div className="mb-6">
            <h3 className="label-uppercase mb-3">Quality Score</h3>
            <div className="text-center p-6 border border-zinc-800">
              <div className={`score-display ${getScoreColor(page.quality_score)}`} data-testid="quality-score">
                {page.quality_score}
              </div>
              <div className="text-zinc-500 text-xs mt-1">/100</div>
              <div className={`text-sm mt-2 ${getScoreColor(page.quality_score)}`}>
                {page.quality_score >= 85 ? 'Strong' : page.quality_score >= 70 ? 'Usable' : 'Needs Work'}
              </div>
            </div>

            {/* Score Details Toggle */}
            {page.score_notes?.category_scores && (
              <button
                onClick={() => setShowScoreDetails(!showScoreDetails)}
                className="w-full mt-2 text-xs text-zinc-500 hover:text-white flex items-center justify-center gap-1"
                data-testid="toggle-score-details"
              >
                {showScoreDetails ? 'Hide' : 'Show'} Details
                {showScoreDetails ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
              </button>
            )}

            {showScoreDetails && page.score_notes?.category_scores && (
              <div className="mt-3 space-y-2 text-xs" data-testid="score-details">
                {Object.entries(page.score_notes.category_scores).map(([key, value]) => (
                  <div key={key} className="flex justify-between">
                    <span className="text-zinc-500 capitalize">{key.replace(/_/g, ' ')}</span>
                    <span className={getScoreColor(value)}>{value}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Edit Recommendations */}
        {page.edit_recommendations?.length > 0 && (
          <div className="mb-6">
            <h3 className="label-uppercase mb-3">Recommendations</h3>
            <div className="space-y-2" data-testid="recommendations">
              {page.edit_recommendations.map((rec, idx) => (
                <div key={idx} className="recommendation-item text-xs text-zinc-300">
                  {rec}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Exemplar Status */}
        {pageExemplars.length > 0 && (
          <div className="mb-6">
            <h3 className="label-uppercase mb-3">Exemplar Status</h3>
            <div className="space-y-2" data-testid="page-exemplar-status">
              {pageExemplars.map(ex => (
                <div key={ex.id} className="p-3 border border-[#FFCC00]/20 bg-[#FFCC00]/5">
                  <div className="flex items-center gap-2">
                    {ex.is_primary ? (
                      <Crown className="w-4 h-4 text-[#FFCC00]" />
                    ) : (
                      <Award className="w-4 h-4 text-[#FFCC00]" />
                    )}
                    <span className="text-xs text-[#FFCC00]">
                      v{ex.version_number} — {ex.is_primary ? 'Primary Exemplar' : 'Exemplar'}
                    </span>
                  </div>
                  {ex.reason_tags?.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {ex.reason_tags.map((tag, i) => (
                        <span key={i} className="text-[10px] text-zinc-400 border border-zinc-800 px-1.5 py-0.5">{tag}</span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Active Template Indicator */}
        {familyTemplate && (
          <div className="mb-6">
            <h3 className="label-uppercase mb-3">Active Template</h3>
            <div className="p-3 border border-[#34C759]/20 bg-[#34C759]/5" data-testid="active-template-indicator">
              <div className="flex items-center gap-2">
                <LayoutTemplate className="w-4 h-4 text-[#34C759]" />
                <span className="text-xs text-[#34C759]">{familyTemplate.template_name}</span>
              </div>
              <p className="text-[10px] text-zinc-500 mt-1">
                Primary template for {page?.page_family}
              </p>
              <Link
                to="/templates"
                className="text-[10px] text-zinc-500 hover:text-white mt-1 inline-block"
              >
                Manage templates
              </Link>
            </div>
          </div>
        )}

        {/* Active Style Profile Indicator */}
        {familyStyleProfile && (
          <div className="mb-6">
            <h3 className="label-uppercase mb-3">Active Style</h3>
            <div className="p-3 border border-[#AF52DE]/20 bg-[#AF52DE]/5" data-testid="active-style-indicator">
              <div className="flex items-center gap-2">
                <Palette className="w-4 h-4 text-[#AF52DE]" />
                <span className="text-xs text-[#AF52DE]">{familyStyleProfile.profile_name}</span>
              </div>
              <p className="text-[10px] text-zinc-500 mt-1">
                {familyStyleProfile.description?.slice(0, 80)}{familyStyleProfile.description?.length > 80 ? '...' : ''}
              </p>
              <Link
                to="/styles"
                className="text-[10px] text-zinc-500 hover:text-white mt-1 inline-block"
              >
                Manage styles
              </Link>
            </div>
          </div>
        )}

        {/* Promotion Recommendation */}
        {promotionCandidate && !promotionDismissed && (
          <div className="mb-6" data-testid="promotion-recommendation">
            <h3 className="label-uppercase mb-3 text-[#FF9500]">Promotion Detected</h3>
            <div className="p-3 border border-[#FF9500]/30 bg-[#FF9500]/5">
              <p className="text-xs text-zinc-300 mb-3">{promotionCandidate.recommendation_reason}</p>
              <div className="flex flex-wrap gap-1.5 mb-3">
                {(promotionCandidate.promotion_types || []).map(t => {
                  const config = {
                    'exemplar': { color: '#FFCC00', label: 'Exemplar' },
                    'template': { color: '#34C759', label: 'Template' },
                    'style-candidate': { color: '#AF52DE', label: 'Style' },
                  }[t];
                  return config ? (
                    <span key={t} className="text-[10px] border px-2 py-0.5" style={{ color: config.color, borderColor: `${config.color}33` }}>
                      {config.label}
                    </span>
                  ) : null;
                })}
              </div>
              <div className="flex flex-wrap gap-1.5">
                {promotionCandidate.promotion_types?.includes('exemplar') && (
                  <button onClick={() => handlePromotionAction('promote-exemplar')} className="text-[10px] border border-[#FFCC00]/30 text-[#FFCC00] px-2 py-1 hover:bg-[#FFCC00]/10 transition-colors" data-testid="promo-to-exemplar">
                    Exemplar
                  </button>
                )}
                {promotionCandidate.promotion_types?.includes('template') && (
                  <button onClick={() => handlePromotionAction('create-template')} className="text-[10px] border border-[#34C759]/30 text-[#34C759] px-2 py-1 hover:bg-[#34C759]/10 transition-colors" data-testid="promo-to-template">
                    Template
                  </button>
                )}
                {promotionCandidate.promotion_types?.includes('style-candidate') && (
                  <button onClick={() => handlePromotionAction('save-style-candidate')} className="text-[10px] border border-[#AF52DE]/30 text-[#AF52DE] px-2 py-1 hover:bg-[#AF52DE]/10 transition-colors" data-testid="promo-to-style">
                    Style
                  </button>
                )}
                <button onClick={() => handlePromotionAction('decide-later')} className="text-[10px] border border-zinc-700 text-zinc-400 px-2 py-1 hover:bg-zinc-800 transition-colors" data-testid="promo-defer">
                  Later
                </button>
                <button onClick={() => handlePromotionAction('dismiss')} className="text-[10px] border border-zinc-700 text-zinc-400 px-2 py-1 hover:text-[#FF3B30] hover:border-[#FF3B30]/30 transition-colors" data-testid="promo-dismiss">
                  Dismiss
                </button>
              </div>
              <Link to="/promotions" className="text-[10px] text-zinc-500 hover:text-white mt-2 inline-block">
                View all promotions
              </Link>
            </div>
          </div>
        )}

        {/* Approval Actions */}
        <div className="mb-6">
          <h3 className="label-uppercase mb-3">Actions</h3>
          <div className="space-y-2">
            <button
              onClick={() => handleAction('approve')}
              className="w-full py-2 px-4 border border-[#34C759] text-[#34C759] hover:bg-[#34C759]/10 transition-colors text-sm flex items-center justify-center gap-2"
              data-testid="approve-btn"
            >
              <Check className="w-4 h-4" />
              Approve
            </button>
            <button
              onClick={() => handleAction('rewrite')}
              className="w-full py-2 px-4 border border-[#FF3B30] text-[#FF3B30] hover:bg-[#FF3B30]/10 transition-colors text-sm flex items-center justify-center gap-2"
              data-testid="rewrite-btn"
            >
              <RefreshCw className="w-4 h-4" />
              Send to Rewrite
            </button>
            <button
              onClick={() => handleAction('defer')}
              className="w-full py-2 px-4 border border-zinc-600 text-zinc-400 hover:bg-zinc-800 transition-colors text-sm flex items-center justify-center gap-2"
              data-testid="defer-btn"
            >
              <Clock className="w-4 h-4" />
              Defer
            </button>
          </div>
        </div>

        {/* Version History */}
        <div className="mb-6">
          <button
            onClick={() => setShowVersions(!showVersions)}
            className="w-full flex items-center justify-between mb-3"
            data-testid="toggle-versions-btn"
          >
            <h3 className="label-uppercase flex items-center gap-2">
              <History className="w-3 h-3" />
              Version History ({versions.length})
            </h3>
            {showVersions ? <ChevronUp className="w-3 h-3 text-zinc-500" /> : <ChevronDown className="w-3 h-3 text-zinc-500" />}
          </button>

          {showVersions && (
            <div className="space-y-2" data-testid="version-history-list">
              {versions.map((v) => (
                <div
                  key={v.id}
                  className={`p-3 border text-xs ${
                    v.is_current ? 'border-white/20 bg-zinc-900' : 'border-zinc-800'
                  }`}
                  data-testid={`version-${v.version_number}`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                      <span className="text-white font-mono">v{v.version_number}</span>
                      {v.is_current && <span className="text-[10px] text-zinc-400 border border-zinc-700 px-1">current</span>}
                      {isVersionExemplar(v.id) && <Award className="w-3 h-3 text-[#FFCC00]" />}
                      {v.label && <span className="text-[10px] text-zinc-500">{v.label}</span>}
                    </div>
                    <span className={`font-mono ${getScoreColor(v.quality_score)}`}>
                      {v.quality_score || '—'}
                    </span>
                  </div>
                  <div className="text-zinc-500 mb-2">
                    {v.generation_action_type}
                    {v.variant_used && ` (${v.variant_used})`}
                    {v.tightened_applied && ' + tightened'}
                  </div>
                  <div className="flex items-center gap-2">
                    {!v.is_current && (
                      <button
                        onClick={() => restoreVersion(v.id)}
                        className="text-[10px] text-zinc-400 border border-zinc-700 px-2 py-0.5 hover:text-white hover:border-zinc-500 transition-colors flex items-center gap-1"
                        data-testid={`restore-version-${v.version_number}`}
                      >
                        <RotateCcw className="w-2.5 h-2.5" />
                        Restore
                      </button>
                    )}
                    {!isVersionExemplar(v.id) && v.quality_score && v.quality_score >= 70 && (
                      <button
                        onClick={() => openExemplarForm(v)}
                        className="text-[10px] text-[#FFCC00] border border-[#FFCC00]/30 px-2 py-0.5 hover:bg-[#FFCC00]/10 transition-colors flex items-center gap-1"
                        data-testid={`mark-exemplar-${v.version_number}`}
                      >
                        <Award className="w-2.5 h-2.5" />
                        Mark Exemplar
                      </button>
                    )}
                    {v.quality_score && v.quality_score >= 70 && (
                      <button
                        onClick={() => openTemplateForm(v)}
                        className="text-[10px] text-[#34C759] border border-[#34C759]/30 px-2 py-0.5 hover:bg-[#34C759]/10 transition-colors flex items-center gap-1"
                        data-testid={`create-template-${v.version_number}`}
                      >
                        <LayoutTemplate className="w-2.5 h-2.5" />
                        Create Template
                      </button>
                    )}
                  </div>
                  <div className="text-[10px] text-zinc-600 font-mono mt-1">
                    {new Date(v.created_at).toLocaleString()}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Exemplar Form Modal (inline) */}
        {showExemplarForm && exemplarVersion && (
          <div className="mb-6 border border-[#FFCC00]/30 bg-[#FFCC00]/5 p-4" data-testid="exemplar-form">
            <h3 className="label-uppercase mb-3 text-[#FFCC00]">
              Mark v{exemplarVersion.version_number} as Exemplar
            </h3>

            {/* Reason Tags */}
            <div className="mb-3">
              <span className="text-[10px] text-zinc-500 uppercase tracking-wider block mb-2">Reason Tags</span>
              <div className="flex flex-wrap gap-1.5">
                {availableReasonTags.map(tag => (
                  <button
                    key={tag}
                    onClick={() => toggleReasonTag(tag)}
                    className={`text-[10px] px-2 py-1 border transition-colors ${
                      exemplarTags.includes(tag)
                        ? 'border-[#FFCC00] text-[#FFCC00] bg-[#FFCC00]/10'
                        : 'border-zinc-700 text-zinc-400 hover:border-zinc-500'
                    }`}
                    data-testid={`reason-tag-${tag.toLowerCase().replace(/ /g, '-')}`}
                  >
                    {tag}
                  </button>
                ))}
              </div>
            </div>

            {/* Notes */}
            <div className="mb-3">
              <span className="text-[10px] text-zinc-500 uppercase tracking-wider block mb-2">Notes (Why Gold Standard)</span>
              <textarea
                value={exemplarNotes}
                onChange={(e) => setExemplarNotes(e.target.value)}
                className="input-flat w-full text-xs h-16 resize-none"
                placeholder="What makes this version stand out..."
                data-testid="exemplar-notes-input"
              />
            </div>

            {/* Primary Toggle */}
            <label className="flex items-center gap-2 mb-4 cursor-pointer">
              <input
                type="checkbox"
                checked={exemplarPrimary}
                onChange={(e) => setExemplarPrimary(e.target.checked)}
                className="accent-[#FFCC00]"
                data-testid="exemplar-primary-checkbox"
              />
              <span className="text-xs text-zinc-400">Set as Primary Exemplar for {page?.page_family}</span>
            </label>

            {/* Actions */}
            <div className="flex items-center gap-2">
              <button
                onClick={saveExemplar}
                disabled={savingExemplar}
                className="text-xs bg-[#FFCC00] text-black px-4 py-1.5 hover:bg-[#FFCC00]/80 transition-colors disabled:opacity-50 flex items-center gap-1.5"
                data-testid="save-exemplar-btn"
              >
                {savingExemplar ? (
                  <RefreshCw className="w-3 h-3 animate-spin" />
                ) : (
                  <Award className="w-3 h-3" />
                )}
                {savingExemplar ? 'Saving...' : 'Save Exemplar'}
              </button>
              <button
                onClick={() => setShowExemplarForm(false)}
                className="text-xs text-zinc-400 border border-zinc-700 px-3 py-1.5 hover:bg-zinc-800 transition-colors"
                data-testid="cancel-exemplar-btn"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Template Creation Form (inline) */}
        {showTemplateForm && templateVersion && (
          <div className="mb-6 border border-[#34C759]/30 bg-[#34C759]/5 p-4" data-testid="template-form">
            <h3 className="label-uppercase mb-3 text-[#34C759]">
              Create Template from v{templateVersion.version_number}
            </h3>

            <div className="mb-3">
              <span className="text-[10px] text-zinc-500 uppercase tracking-wider block mb-2">Template Name</span>
              <input
                value={templateName}
                onChange={(e) => setTemplateName(e.target.value)}
                className="input-flat w-full text-xs"
                placeholder="e.g. Core Hub Warmth Pattern"
                data-testid="template-name-input"
              />
            </div>

            <div className="mb-3">
              <span className="text-[10px] text-zinc-500 uppercase tracking-wider block mb-2">Purpose</span>
              <textarea
                value={templatePurpose}
                onChange={(e) => setTemplatePurpose(e.target.value)}
                className="input-flat w-full text-xs h-14 resize-none"
                placeholder="What this template captures and when to use it..."
                data-testid="template-purpose-input"
              />
            </div>

            <div className="mb-3">
              <span className="text-[10px] text-zinc-500 uppercase tracking-wider block mb-2">Tone Guidance</span>
              <textarea
                value={templateToneGuidance}
                onChange={(e) => setTemplateToneGuidance(e.target.value)}
                className="input-flat w-full text-xs h-14 resize-none"
                placeholder="Optional: how should this template influence tone..."
                data-testid="template-tone-input"
              />
            </div>

            <div className="mb-3">
              <span className="text-[10px] text-zinc-500 uppercase tracking-wider block mb-2">
                Extracted Structure {extractedPattern ? '(editable)' : '(loading...)'}
              </span>
              <textarea
                value={extractedPattern}
                onChange={(e) => setExtractedPattern(e.target.value)}
                className="input-flat w-full text-[10px] h-28 resize-none font-mono"
                placeholder="Structure will be auto-extracted..."
                data-testid="template-structure-input"
              />
            </div>

            <label className="flex items-center gap-2 mb-4 cursor-pointer">
              <input
                type="checkbox"
                checked={templatePrimary}
                onChange={(e) => setTemplatePrimary(e.target.checked)}
                className="accent-[#34C759]"
                data-testid="template-primary-checkbox"
              />
              <span className="text-xs text-zinc-400">Set as Primary Template for {page?.page_family}</span>
            </label>

            <div className="flex items-center gap-2">
              <button
                onClick={saveTemplate}
                disabled={savingTemplate || !templateName.trim()}
                className="text-xs bg-[#34C759] text-black px-4 py-1.5 hover:bg-[#34C759]/80 transition-colors disabled:opacity-50 flex items-center gap-1.5"
                data-testid="save-template-btn"
              >
                {savingTemplate ? (
                  <RefreshCw className="w-3 h-3 animate-spin" />
                ) : (
                  <LayoutTemplate className="w-3 h-3" />
                )}
                {savingTemplate ? 'Saving...' : 'Save Template'}
              </button>
              <button
                onClick={() => setShowTemplateForm(false)}
                className="text-xs text-zinc-400 border border-zinc-700 px-3 py-1.5 hover:bg-zinc-800 transition-colors"
                data-testid="cancel-template-btn"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Legacy History */}
        {!showVersions && page.generation_history?.length > 0 && (
          <div>
            <h3 className="label-uppercase mb-3">Quick History</h3>
            <div className="space-y-2 text-xs" data-testid="generation-history">
              {page.generation_history.slice(-5).reverse().map((entry, idx) => (
                <div key={idx} className="p-2 border border-zinc-800 text-zinc-500">
                  <div className="flex justify-between">
                    <span>{entry.model}</span>
                    <span>{entry.tone}</span>
                  </div>
                  <div className="text-zinc-600 mt-1 font-mono text-[10px]">
                    {new Date(entry.timestamp).toLocaleString()}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
