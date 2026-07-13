import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import {
  Zap, ArrowRight, CheckCircle, AlertTriangle, Clock, Lock,
  Rocket, Eye, FileText, ChevronDown, ChevronUp, Play, Users,
  LayoutDashboard, Target, Send, RotateCcw,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const ACTION_ICONS = {
  review: Eye,
  launch: Rocket,
  unlock: Lock,
  generate: Zap,
  worker_execute: Play,
  worker_review: AlertTriangle,
  blocked: Lock,
};

const ACTION_COLORS = {
  review: 'border-blue-800/50 bg-blue-950/20 text-blue-400',
  launch: 'border-emerald-800/50 bg-emerald-950/20 text-emerald-400',
  unlock: 'border-amber-800/50 bg-amber-950/20 text-amber-400',
  generate: 'border-purple-800/50 bg-purple-950/20 text-purple-400',
  worker_execute: 'border-emerald-800/50 bg-emerald-950/20 text-emerald-400',
  worker_review: 'border-red-800/50 bg-red-950/20 text-red-400',
  blocked: 'border-zinc-700 bg-zinc-900/30 text-zinc-400',
};

const STATUS_DOT = {
  'Draft Ready': 'bg-blue-400',
  'Needs Review': 'bg-blue-400',
  'Approved': 'bg-emerald-400',
  'placed': 'bg-emerald-500',
  'Planned': 'bg-zinc-500',
  'Generating': 'bg-amber-400 animate-pulse',
  'Deferred': 'bg-zinc-600',
};

const FAMILY_COLORS = {
  'Core Hub': 'text-amber-400',
  'District': 'text-purple-400',
  'Trust': 'text-emerald-400',
  'FAQ/Support': 'text-blue-400',
  'Guided Path': 'text-cyan-400',
  'Conversion': 'text-red-400',
  'Category Support': 'text-orange-400',
  'Media/Asset': 'text-pink-400',
  'Digital/Tools': 'text-teal-400',
};

export default function CommandCenter() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeSection, setActiveSection] = useState('actions');
  const [expandedStructure, setExpandedStructure] = useState(null);

  // Execution Map state
  const [goalInput, setGoalInput] = useState('');
  const [mapTimeframe, setMapTimeframe] = useState('');
  const [mapPriority, setMapPriority] = useState('');
  const [mapLane, setMapLane] = useState('');
  const [generating, setGenerating] = useState(false);
  const [currentMap, setCurrentMap] = useState(null);
  const [savedMaps, setSavedMaps] = useState([]);

  const fetchData = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/command-center/dashboard`, { withCredentials: true });
      setData(res.data);
    } catch (err) {
      console.error('Failed to load command center:', err);
    }
    setLoading(false);
  }, []);

  useEffect(() => { fetchData(); fetchSavedMaps(); }, [fetchData]);

  const handleBatchLaunch = async (pageIds) => {
    try {
      const res = await axios.post(`${API}/command-center/batch-launch`, { page_ids: pageIds }, { withCredentials: true });
      alert(`Launched: ${res.data.launched}, Skipped: ${res.data.skipped}`);
      await fetchData();
    } catch (err) {
      alert(err.response?.data?.detail || 'Launch failed');
    }
  };

  const handleRetrofit = async () => {
    if (!confirm('This will re-place all live pages with updated formatting (hero fix + body formatter). Continue?')) return;
    try {
      const res = await axios.post(`${API}/command-center/bulk-retrofit`, {}, { withCredentials: true });
      alert(`${res.data.message}. Execute them in the Queue to complete.`);
      await fetchData();
    } catch (err) {
      alert(err.response?.data?.detail || 'Retrofit failed');
    }
  };

  const handleGenerateMap = async () => {
    if (!goalInput.trim()) return;
    setGenerating(true);
    try {
      const res = await axios.post(`${API}/command-center/execution-map`, {
        goal_input: goalInput,
        timeframe: mapTimeframe,
        priority: mapPriority,
        main_lane: mapLane,
      }, { withCredentials: true });
      setCurrentMap(res.data);
      fetchSavedMaps();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to generate execution map');
    }
    setGenerating(false);
  };

  const fetchSavedMaps = async () => {
    try {
      const res = await axios.get(`${API}/command-center/execution-maps?limit=5`, { withCredentials: true });
      setSavedMaps(res.data.maps || []);
    } catch {}
  };

  const handleSendToQueue = async (mapId) => {
    try {
      const res = await axios.post(`${API}/command-center/execution-maps/${mapId}/send-to-queue`, {}, { withCredentials: true });
      alert(`Sent to ${res.data.worker} queue: "${res.data.action}"`);
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to send to queue');
    }
  };

  const loadSavedMap = async (mapId) => {
    try {
      const res = await axios.get(`${API}/command-center/execution-maps/${mapId}`, { withCredentials: true });
      setCurrentMap(res.data);
      setActiveSection('plan');
    } catch {}
  };

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[50vh]">
        <div className="text-zinc-500 text-sm animate-pulse">Loading Command Center...</div>
      </div>
    );
  }

  if (!data) {
    return <div className="p-8 text-center text-zinc-500">Failed to load Command Center</div>;
  }

  const { stats, actions, ready_for_review, ready_to_launch, launched, blocked, next_unlocks, structure_map } = data;

  const sections = [
    { key: 'actions', label: "Today's Actions" },
    { key: 'plan', label: 'Execution Map' },
    { key: 'review', label: `Review (${stats.review_ready})` },
    { key: 'launch', label: `Launch (${stats.launch_ready})` },
    { key: 'blocked', label: `Blocked (${stats.blocked})` },
    { key: 'structure', label: `Structure (${stats.total_pages})` },
  ];

  return (
    <div className="p-6 max-w-7xl mx-auto" data-testid="command-center">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-xl font-bold text-white flex items-center gap-2">
          <LayoutDashboard className="w-5 h-5" /> Founder Command Center
        </h1>
        <p className="text-xs text-zinc-500 mt-0.5">
          {stats.total_pages} pages &middot; {stats.review_ready} review &middot; {stats.launch_ready} launch &middot; {stats.launched} live &middot; {stats.planned} planned
        </p>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-3 md:grid-cols-6 gap-2 mb-6" data-testid="stats-row">
        {[
          { label: 'Review', value: stats.review_ready, color: 'text-blue-400' },
          { label: 'Launch', value: stats.launch_ready, color: 'text-emerald-400' },
          { label: 'Live', value: stats.launched, color: 'text-emerald-500' },
          { label: 'Planned', value: stats.planned, color: 'text-zinc-400' },
          { label: 'Blocked', value: stats.blocked, color: 'text-amber-400' },
          { label: 'Generate', value: stats.can_generate, color: 'text-purple-400' },
        ].map(s => (
          <div key={s.label} className="border border-zinc-800 p-3 text-center">
            <div className={`text-2xl font-bold ${s.color}`}>{s.value}</div>
            <div className="text-[10px] text-zinc-500 uppercase tracking-wider mt-1">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Section Tabs */}
      <div className="flex items-center gap-1 mb-4 border-b border-zinc-800 pb-3" data-testid="section-tabs">
        {sections.map(s => (
          <button
            key={s.key}
            onClick={() => setActiveSection(s.key)}
            className={`px-3 py-1.5 text-xs transition ${
              activeSection === s.key
                ? 'text-white border border-zinc-600 bg-zinc-800/50'
                : 'text-zinc-500 hover:text-zinc-300'
            }`}
            data-testid={`tab-${s.key}`}
          >
            {s.label}
          </button>
        ))}
      </div>

      {/* === TODAY'S ACTIONS === */}
      {activeSection === 'actions' && (
        <div className="space-y-3" data-testid="actions-section">
          {actions.length === 0 ? (
            <div className="border border-zinc-800 p-8 text-center text-zinc-600 text-sm">
              Nothing urgent right now. Check back after generating or placing pages.
            </div>
          ) : (
            actions.map((action, i) => {
              const Icon = ACTION_ICONS[action.type] || Zap;
              const colorClass = ACTION_COLORS[action.type] || 'border-zinc-700 text-zinc-400';
              return (
                <div key={i} className={`border p-4 ${colorClass}`} data-testid={`action-${action.type}`}>
                  <div className="flex items-center gap-3">
                    <Icon className="w-5 h-5 flex-shrink-0" />
                    <div className="flex-1">
                      <div className="text-sm font-medium">{action.message}</div>
                      {action.pages && action.pages.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1">
                          {action.pages.slice(0, 6).map(p => (
                            <button
                              key={p.id}
                              onClick={() => navigate(`/workspace/${p.id}`)}
                              className="text-[10px] bg-zinc-900 border border-zinc-700 px-2 py-0.5 hover:border-zinc-500 transition"
                            >
                              {p.code && <span className="text-zinc-500 mr-1">{p.code}</span>}
                              {p.name}
                            </button>
                          ))}
                          {action.pages.length > 6 && <span className="text-[10px] text-zinc-600">+{action.pages.length - 6} more</span>}
                        </div>
                      )}
                      {action.unlocks && action.unlocks.length > 0 && (
                        <div className="mt-2 space-y-1">
                          {action.unlocks.map((u, j) => (
                            <div key={j} className="text-[10px] text-zinc-400">
                              Approve <span className="text-white">{u.approve_page_name}</span>
                              <ArrowRight className="w-3 h-3 inline mx-1" />
                              unlocks {u.unlocks_count} page{u.unlocks_count !== 1 ? 's' : ''}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                    {action.type === 'review' && (
                      <button onClick={() => setActiveSection('review')} className="text-[10px] border border-current px-2 py-1 hover:bg-white/5 transition">
                        Review Now
                      </button>
                    )}
                    {action.type === 'launch' && (
                      <button
                        onClick={() => handleBatchLaunch(action.pages.map(p => p.id))}
                        className="text-[10px] border border-current px-2 py-1 hover:bg-white/5 transition"
                        data-testid="launch-all-btn"
                      >
                        Launch All
                      </button>
                    )}
                    {action.type === 'worker_execute' && (
                      <button onClick={() => navigate('/queue')} className="text-[10px] border border-current px-2 py-1 hover:bg-white/5 transition">
                        Go to Queue
                      </button>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}

      {/* === EXECUTION MAP === */}
      {activeSection === 'plan' && (
        <div data-testid="plan-section">
          {/* Input */}
          <div className="border border-zinc-800 p-5 mb-4">
            <div className="flex items-center gap-2 mb-3">
              <Target className="w-4 h-4 text-amber-400" />
              <span className="text-sm text-white font-medium">Goal to Execution Map</span>
            </div>
            <textarea
              value={goalInput}
              onChange={e => setGoalInput(e.target.value)}
              placeholder="What are we trying to get done? Dump your messy goal here..."
              className="w-full bg-zinc-900 border border-zinc-700 text-white text-sm px-4 py-3 min-h-[100px] outline-none focus:border-zinc-500 resize-y placeholder:text-zinc-600"
              data-testid="goal-input"
            />
            <div className="flex flex-wrap gap-3 mt-3">
              <input
                value={mapTimeframe}
                onChange={e => setMapTimeframe(e.target.value)}
                placeholder="Timeframe (e.g., 14 days)"
                className="bg-zinc-900 border border-zinc-700 text-white text-xs px-3 py-1.5 outline-none focus:border-zinc-500 placeholder:text-zinc-600 w-40"
              />
              <select
                value={mapPriority}
                onChange={e => setMapPriority(e.target.value)}
                className="bg-zinc-900 border border-zinc-700 text-white text-xs px-3 py-1.5 outline-none focus:border-zinc-500"
              >
                <option value="">Priority</option>
                <option value="urgent">Urgent</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
              <select
                value={mapLane}
                onChange={e => setMapLane(e.target.value)}
                className="bg-zinc-900 border border-zinc-700 text-white text-xs px-3 py-1.5 outline-none focus:border-zinc-500"
              >
                <option value="">Main Lane</option>
                <option value="Pages / Content">Pages / Content</option>
                <option value="Product / Catalog">Product / Catalog</option>
                <option value="Grants">Grants</option>
                <option value="Ops / System">Ops / System</option>
                <option value="Marketing">Marketing</option>
                <option value="Multi-lane">Multi-lane</option>
              </select>
              <button
                onClick={handleGenerateMap}
                disabled={!goalInput.trim() || generating}
                className="ml-auto flex items-center gap-2 px-4 py-1.5 border border-amber-800 text-amber-400 text-xs hover:bg-amber-950/30 disabled:opacity-30 transition"
                data-testid="generate-map-btn"
              >
                <Zap className="w-3.5 h-3.5" />
                {generating ? 'Generating...' : 'Generate Execution Map'}
              </button>
            </div>
          </div>

          {/* Generated Map Output */}
          {currentMap && !currentMap.error && (
            <div className="space-y-3" data-testid="execution-map-output">
              {/* Main Goal */}
              <div className="border border-amber-800/40 bg-amber-950/15 p-4">
                <div className="text-[10px] text-amber-400/60 uppercase tracking-wider mb-1">Main Goal</div>
                <div className="text-sm text-white">{currentMap.main_goal}</div>
              </div>

              {/* Crystal First Move */}
              {currentMap.crystal_first_move && (
                <div className="border border-emerald-800/40 bg-emerald-950/15 p-4">
                  <div className="text-[10px] text-emerald-400/60 uppercase tracking-wider mb-1">Crystal — Do This First</div>
                  <div className="text-sm text-emerald-300 font-medium">{currentMap.crystal_first_move}</div>
                </div>
              )}

              {/* First Actions */}
              {currentMap.first_actions?.length > 0 && (
                <div className="border border-zinc-800 p-4">
                  <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-3">First Actions</div>
                  <div className="space-y-2">
                    {currentMap.first_actions.map((a, i) => (
                      <div key={i} className="flex items-center gap-3">
                        <span className="w-5 h-5 border border-zinc-700 flex items-center justify-center text-[10px] text-zinc-500 flex-shrink-0">{i + 1}</span>
                        <span className="text-xs text-white flex-1">{a.action}</span>
                        <span className="text-[9px] text-zinc-600 border border-zinc-800 px-1.5 py-0.5">{a.owner}</span>
                        <span className={`text-[9px] px-1.5 py-0.5 ${a.priority === 'high' ? 'text-red-400 border border-red-900' : a.priority === 'medium' ? 'text-amber-400 border border-amber-900' : 'text-zinc-500 border border-zinc-800'}`}>
                          {a.priority}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Phases */}
              {currentMap.phases?.length > 0 && (
                <div className="border border-zinc-800 p-4">
                  <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-3">Phases</div>
                  <div className="space-y-3">
                    {currentMap.phases.map((p, i) => (
                      <div key={i} className="border-l-2 border-zinc-700 pl-3">
                        <div className="text-xs text-white font-medium">{p.name}</div>
                        <div className="text-[10px] text-zinc-400 mt-0.5">{p.description}</div>
                        <div className="text-[10px] text-zinc-600 mt-0.5">Outcome: {p.outcome}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Dependencies */}
              {currentMap.dependencies?.length > 0 && (
                <div className="border border-zinc-800 p-4">
                  <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-3">Dependencies / Blockers</div>
                  {currentMap.dependencies.map((d, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs mb-1.5">
                      <Lock className="w-3 h-3 text-amber-500 flex-shrink-0" />
                      <span className="text-zinc-400">{d.blocker}</span>
                      <ArrowRight className="w-3 h-3 text-zinc-600" />
                      <span className="text-zinc-300">{d.blocks}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Minion Ownership */}
              {currentMap.minion_ownership?.length > 0 && (
                <div className="border border-zinc-800 p-4">
                  <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-3">Minion Ownership</div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    {currentMap.minion_ownership.map((m, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs">
                        <Users className="w-3 h-3 text-purple-400 flex-shrink-0" />
                        <span className="text-purple-300">{m.minion}</span>
                        <span className="text-zinc-600">—</span>
                        <span className="text-zinc-400">{m.responsibility}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Actions row */}
              <div className="flex items-center gap-3">
                {currentMap.id && (
                  <button
                    onClick={() => handleSendToQueue(currentMap.id)}
                    className="flex items-center gap-2 px-3 py-1.5 border border-emerald-800 text-emerald-400 text-xs hover:bg-emerald-950/30 transition"
                    data-testid="send-to-queue-btn"
                  >
                    <Send className="w-3.5 h-3.5" /> Send First Action to Queue
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Saved Maps */}
          {savedMaps.length > 0 && (
            <div className="mt-6 border border-zinc-800 p-4">
              <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-3">Saved Execution Maps</div>
              <div className="space-y-2">
                {savedMaps.map(m => (
                  <button
                    key={m.id}
                    onClick={() => loadSavedMap(m.id)}
                    className="w-full text-left flex items-center gap-3 px-3 py-2 border border-zinc-800/50 hover:border-zinc-600 transition"
                  >
                    <Target className="w-3.5 h-3.5 text-zinc-600 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="text-xs text-white truncate">{m.main_goal || m.goal_input}</div>
                      <div className="text-[10px] text-zinc-600">{m.timeframe || 'No timeframe'} &middot; {new Date(m.created_at).toLocaleDateString()}</div>
                    </div>
                    {m.first_action_sent_to_queue && <CheckCircle className="w-3 h-3 text-emerald-500" />}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* === READY FOR REVIEW === */}
      {activeSection === 'review' && (
        <div data-testid="review-section">
          {ready_for_review.length === 0 ? (
            <div className="border border-zinc-800 p-8 text-center text-zinc-600 text-sm">No pages waiting for review.</div>
          ) : (
            <div className="border border-zinc-800">
              <div className="px-4 py-2 border-b border-zinc-800 flex items-center gap-3 text-[10px] text-zinc-600 uppercase tracking-wider">
                <span className="w-14">Code</span>
                <span className="flex-1">Page</span>
                <span className="w-20">Family</span>
                <span className="w-16 text-center">Score</span>
                <span className="w-20">Status</span>
                <span className="w-24">Actions</span>
              </div>
              {ready_for_review.map(p => (
                <div key={p.id} className="flex items-center gap-3 px-4 py-3 border-b border-zinc-800/50 last:border-0 hover:bg-zinc-900/30 transition">
                  <span className="w-14 text-xs text-zinc-500 font-mono">{p.page_code}</span>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-white truncate">{p.page_name}</div>
                    {p.slug && <div className="text-[10px] text-zinc-600">/{p.slug}</div>}
                  </div>
                  <span className={`w-20 text-xs ${FAMILY_COLORS[p.page_family] || 'text-zinc-400'}`}>{p.page_family}</span>
                  <span className="w-16 text-center text-xs text-zinc-400">{p.quality_score || '—'}</span>
                  <span className="w-20">
                    <span className="flex items-center gap-1.5 text-[10px]">
                      <span className={`w-1.5 h-1.5 rounded-full ${STATUS_DOT[p.status] || 'bg-zinc-500'}`} />
                      {p.status}
                    </span>
                  </span>
                  <div className="w-24 flex gap-1">
                    <button
                      onClick={() => navigate(`/workspace/${p.id}`)}
                      className="px-2 py-1 text-[10px] border border-blue-800 text-blue-400 hover:bg-blue-950/30 transition"
                    >
                      Review
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* === READY TO LAUNCH === */}
      {activeSection === 'launch' && (
        <div data-testid="launch-section">
          {ready_to_launch.length === 0 ? (
            <div className="border border-zinc-800 p-8 text-center text-zinc-600 text-sm">No pages ready to launch. Approve reviewed pages first.</div>
          ) : (
            <>
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs text-zinc-500">{ready_to_launch.length} page{ready_to_launch.length !== 1 ? 's' : ''} approved</span>
                <button
                  onClick={() => handleBatchLaunch(ready_to_launch.map(p => p.id))}
                  className="flex items-center gap-2 px-3 py-1.5 border border-emerald-800 text-emerald-400 text-xs hover:bg-emerald-950/30 transition"
                  data-testid="batch-launch-btn"
                >
                  <Rocket className="w-3.5 h-3.5" /> Launch All ({ready_to_launch.length})
                </button>
              </div>
              <div className="border border-zinc-800">
                {ready_to_launch.map(p => (
                  <div key={p.id} className="flex items-center gap-3 px-4 py-3 border-b border-zinc-800/50 last:border-0 hover:bg-zinc-900/30 transition">
                    <span className="text-xs text-zinc-500 font-mono w-14">{p.page_code}</span>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-white truncate">{p.page_name}</div>
                      <div className="text-[10px] text-zinc-600">/{p.slug}</div>
                    </div>
                    <span className={`text-xs ${FAMILY_COLORS[p.page_family] || 'text-zinc-400'}`}>{p.page_family}</span>
                    <span className="flex items-center gap-1.5 text-[10px] text-emerald-400">
                      <CheckCircle className="w-3 h-3" /> Approved
                    </span>
                    <button
                      onClick={() => handleBatchLaunch([p.id])}
                      className="px-2 py-1 text-[10px] border border-emerald-800 text-emerald-400 hover:bg-emerald-950/30 transition"
                    >
                      Launch
                    </button>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* Recently Launched */}
          {launched.length > 0 && (
            <div className="mt-6">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-zinc-500">Recently Launched ({launched.length})</span>
                <button
                  onClick={handleRetrofit}
                  className="flex items-center gap-1.5 px-3 py-1 border border-amber-800 text-amber-400 text-[10px] hover:bg-amber-950/30 transition"
                  data-testid="retrofit-btn"
                >
                  <RotateCcw className="w-3 h-3" /> Retrofit All (Fix Formatting)
                </button>
              </div>
              <div className="border border-zinc-800/50">
                {launched.map(p => (
                  <div key={p.id} className="flex items-center gap-3 px-4 py-2 border-b border-zinc-800/30 last:border-0">
                    <span className="text-xs text-zinc-600 font-mono w-14">{p.page_code}</span>
                    <span className="text-xs text-zinc-400 flex-1 truncate">{p.page_name}</span>
                    <span className="text-[10px] text-emerald-600 flex items-center gap-1"><CheckCircle className="w-3 h-3" /> Live</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* === BLOCKED === */}
      {activeSection === 'blocked' && (
        <div data-testid="blocked-section">
          {blocked.length === 0 ? (
            <div className="border border-zinc-800 p-8 text-center text-zinc-600 text-sm">No blocked pages. All dependencies are clear.</div>
          ) : (
            <div className="space-y-2">
              {blocked.map((b, i) => (
                <div key={i} className="border border-amber-900/30 bg-amber-950/10 p-3">
                  <div className="flex items-center gap-2 text-sm">
                    <Lock className="w-3.5 h-3.5 text-amber-400" />
                    <span className="text-white">{b.page_name}</span>
                    <span className="text-zinc-600 text-xs font-mono">{b.page_code}</span>
                  </div>
                  <div className="text-xs text-amber-400/70 mt-1 ml-6">{b.reason}</div>
                </div>
              ))}
            </div>
          )}

          {/* Next Unlocks */}
          {next_unlocks.length > 0 && (
            <div className="mt-6">
              <div className="text-xs text-zinc-500 mb-2">Approve to Unlock</div>
              <div className="space-y-2">
                {next_unlocks.map((u, i) => (
                  <div key={i} className="border border-purple-900/30 bg-purple-950/10 p-3">
                    <div className="flex items-center gap-2 text-sm">
                      <Zap className="w-3.5 h-3.5 text-purple-400" />
                      <span className="text-white">Approve "{u.approve_page_name}"</span>
                      <ArrowRight className="w-3 h-3 text-zinc-600" />
                      <span className="text-purple-400">unlocks {u.unlocks_count} page{u.unlocks_count !== 1 ? 's' : ''}</span>
                    </div>
                    <div className="mt-2 ml-6 flex flex-wrap gap-1">
                      {u.unlocks.map(c => (
                        <span key={c.page_id} className="text-[10px] bg-zinc-900 border border-zinc-700 px-2 py-0.5 text-zinc-400">
                          {c.page_code && <span className="text-zinc-600 mr-1">{c.page_code}</span>}
                          {c.page_name}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* === STRUCTURE MAP === */}
      {activeSection === 'structure' && (
        <div data-testid="structure-section">
          <div className="border border-zinc-800">
            <div className="px-4 py-2 border-b border-zinc-800 flex items-center gap-3 text-[10px] text-zinc-600 uppercase tracking-wider">
              <span className="w-14">Code</span>
              <span className="flex-1">Page Name</span>
              <span className="w-24">Family</span>
              <span className="w-20">District</span>
              <span className="w-20">Status</span>
              <span className="w-16 text-center">Content</span>
              <span className="w-16 text-center">WP</span>
              <span className="w-8" />
            </div>

            {structure_map.map(p => (
              <div key={p.id} className="border-b border-zinc-800/30 last:border-0">
                <div
                  className="flex items-center gap-3 px-4 py-2.5 hover:bg-zinc-900/30 transition cursor-pointer"
                  onClick={() => setExpandedStructure(expandedStructure === p.id ? null : p.id)}
                >
                  <span className="w-14 text-xs text-zinc-500 font-mono">{p.page_code}</span>
                  <div className="flex-1 min-w-0">
                    <span className="text-sm text-white truncate block">{p.page_name}</span>
                  </div>
                  <span className={`w-24 text-xs ${FAMILY_COLORS[p.page_family] || 'text-zinc-400'}`}>{p.page_family}</span>
                  <span className="w-20 text-xs text-zinc-500 truncate">{p.district || '—'}</span>
                  <span className="w-20">
                    <span className="flex items-center gap-1.5 text-[10px]">
                      <span className={`w-1.5 h-1.5 rounded-full ${STATUS_DOT[p.status] || 'bg-zinc-500'}`} />
                      {p.status}
                    </span>
                  </span>
                  <span className="w-16 text-center text-[10px]">
                    {p.has_content ? <CheckCircle className="w-3 h-3 text-emerald-500 mx-auto" /> : <span className="text-zinc-700">—</span>}
                  </span>
                  <span className="w-16 text-center text-[10px]">
                    {p.wp_page_id ? <span className="text-emerald-500">{p.wp_page_id}</span> : <span className="text-zinc-700">—</span>}
                  </span>
                  <span className="w-8">
                    {expandedStructure === p.id ? <ChevronUp className="w-3.5 h-3.5 text-zinc-500" /> : <ChevronDown className="w-3.5 h-3.5 text-zinc-700" />}
                  </span>
                </div>

                {expandedStructure === p.id && (
                  <div className="px-4 pb-3 pt-1 bg-zinc-900/20 border-t border-zinc-800/50 grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                    <div><span className="text-zinc-600">Slug:</span> <span className="text-zinc-400">/{p.slug || '—'}</span></div>
                    <div><span className="text-zinc-600">Parent:</span> <span className="text-zinc-400">{p.parent_page || 'None'}</span></div>
                    <div><span className="text-zinc-600">Priority:</span> <span className="text-zinc-400">{p.priority_score}</span></div>
                    <div><span className="text-zinc-600">Quality:</span> <span className="text-zinc-400">{p.quality_score || '—'}</span></div>
                    <div className="col-span-2 md:col-span-4 flex gap-2 mt-1">
                      <button
                        onClick={() => navigate(`/workspace/${p.id}`)}
                        className="px-2 py-1 text-[10px] border border-zinc-700 text-zinc-400 hover:text-white hover:border-zinc-500 transition"
                      >
                        Open in Workspace
                      </button>
                      {p.status === 'Approved' && !p.wp_page_id && (
                        <button
                          onClick={() => handleBatchLaunch([p.id])}
                          className="px-2 py-1 text-[10px] border border-emerald-800 text-emerald-400 hover:bg-emerald-950/30 transition"
                        >
                          Launch to WP
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
