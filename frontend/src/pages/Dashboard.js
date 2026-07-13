import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { 
  FileText, Clock, CheckCircle, AlertTriangle, 
  ArrowRight, RefreshCw, Zap, Play
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [recommended, setRecommended] = useState([]);
  const [activity, setActivity] = useState([]);
  const [loading, setLoading] = useState(true);
  const [batchGenerating, setBatchGenerating] = useState(false);
  const [batchResult, setBatchResult] = useState(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [statsRes, recommendedRes, activityRes] = await Promise.all([
        axios.get(`${API}/stats`, { withCredentials: true }),
        axios.get(`${API}/pages/recommended?limit=5`, { withCredentials: true }),
        axios.get(`${API}/activity?limit=10`, { withCredentials: true })
      ]);
      setStats(statsRes.data);
      setRecommended(recommendedRes.data);
      setActivity(activityRes.data);
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error);
    }
    setLoading(false);
  };

  const seedData = async () => {
    try {
      await axios.post(`${API}/seed`, {}, { withCredentials: true });
      fetchData();
    } catch (error) {
      console.error('Seed failed:', error);
    }
  };

  const batchGenerate = async () => {
    setBatchGenerating(true);
    setBatchResult(null);
    try {
      const res = await axios.post(`${API}/pages/batch-generate`, {
        count: 5,
        tone: 'professional',
        auto_score: true,
        score_threshold: 70
      }, { withCredentials: true });
      setBatchResult(res.data);
      fetchData();
    } catch (error) {
      console.error('Batch generate failed:', error);
      setBatchResult({ error: error.response?.data?.detail || 'Failed' });
    }
    setBatchGenerating(false);
  };

  const getStatusColor = (status) => {
    const colors = {
      'Approved': 'text-[#34C759]',
      'Needs Review': 'text-[#FFCC00]',
      'Draft Ready': 'text-[#FFCC00]',
      'Needs Rewrite': 'text-[#FF3B30]',
      'Planned': 'text-zinc-500',
      'Deferred': 'text-zinc-500',
      'Generating': 'text-[#FFCC00]'
    };
    return colors[status] || 'text-zinc-500';
  };

  const getActionIcon = (action) => {
    const icons = {
      'page_created': <FileText className="w-4 h-4" />,
      'page_generated': <Zap className="w-4 h-4" />,
      'page_scored': <CheckCircle className="w-4 h-4" />,
      'page_approved': <CheckCircle className="w-4 h-4 text-[#34C759]" />,
      'page_rewrite': <RefreshCw className="w-4 h-4 text-[#FF3B30]" />,
      'login': <Clock className="w-4 h-4" />
    };
    return icons[action] || <Clock className="w-4 h-4" />;
  };

  if (loading) {
    return (
      <div className="p-6 md:p-8">
        <div className="animate-pulse space-y-6">
          <div className="h-8 bg-zinc-800 w-48"></div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {[1,2,3,4].map(i => (
              <div key={i} className="h-24 bg-zinc-800 border border-zinc-700"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 md:p-8 space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-['Outfit'] text-4xl font-light tracking-tight text-white" data-testid="dashboard-title">
            Dashboard
          </h1>
          <p className="text-zinc-500 text-sm mt-1">Page Ops Control Center</p>
        </div>
        <button
          onClick={fetchData}
          className="p-2 border border-zinc-800 hover:bg-zinc-800 transition-colors duration-150"
          data-testid="refresh-btn"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="stat-card" data-testid="stat-total-pages">
          <div className="stat-value">{stats?.total_pages || 0}</div>
          <div className="stat-label">Total Pages</div>
        </div>
        <div className="stat-card" data-testid="stat-ready-review">
          <div className="stat-value text-[#FFCC00]">{stats?.pages_ready_for_review || 0}</div>
          <div className="stat-label">Ready for Review</div>
        </div>
        <div className="stat-card" data-testid="stat-needs-rewrite">
          <div className="stat-value text-[#FF3B30]">{stats?.pages_needing_rewrite || 0}</div>
          <div className="stat-label">Needs Rewrite</div>
        </div>
        <div className="stat-card" data-testid="stat-avg-score">
          <div className="stat-value">
            {stats?.avg_quality_score ? Math.round(stats.avg_quality_score) : '—'}
          </div>
          <div className="stat-label">Avg Quality Score</div>
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recommended Next Pages */}
        <div className="lg:col-span-2 border border-zinc-800">
          <div className="p-4 border-b border-zinc-800 flex items-center justify-between">
            <h2 className="font-['Outfit'] text-lg font-medium tracking-tight">
              Recommended Next
            </h2>
            <div className="flex items-center gap-2">
              {stats?.total_pages === 0 && (
                <button
                  onClick={seedData}
                  className="text-xs bg-white text-black px-3 py-1 hover:bg-zinc-200 transition-colors"
                  data-testid="seed-data-btn"
                >
                  Seed Ecosystem Data
                </button>
              )}
              {recommended.length > 0 && (
                <button
                  onClick={batchGenerate}
                  disabled={batchGenerating}
                  className="text-xs bg-white text-black px-3 py-1 hover:bg-zinc-200 transition-colors flex items-center gap-1 disabled:opacity-50"
                  data-testid="batch-generate-btn"
                  title="Generate & score next 5 pages (drafts only, no auto-approve)"
                >
                  {batchGenerating ? (
                    <>
                      <RefreshCw className="w-3 h-3 animate-spin" />
                      Processing...
                    </>
                  ) : (
                    <>
                      <Play className="w-3 h-3" />
                      Quick Generate 5
                    </>
                  )}
                </button>
              )}
            </div>
          </div>
          
          {/* Batch Result */}
          {batchResult && (
            <div className="p-4 border-b border-zinc-800 bg-zinc-900/50">
              {batchResult.error ? (
                <div className="text-[#FF3B30] text-sm">{batchResult.error}</div>
              ) : (
                <div className="space-y-2">
                  <div className="flex items-center gap-4 text-sm">
                    <span className="text-zinc-400">Processed: {batchResult.total_processed}</span>
                    <span className="text-[#34C759]">Success: {batchResult.successful}</span>
                    <span className="text-[#FFCC00]">Review: {batchResult.ready_for_review}</span>
                    <span className="text-[#FF3B30]">Rewrite: {batchResult.needs_rewrite}</span>
                  </div>
                  <div className="text-xs text-zinc-500">
                    All pages saved as drafts for your review. None auto-approved.
                  </div>
                </div>
              )}
            </div>
          )}
          <div data-testid="recommended-pages-list">
            {recommended.length === 0 ? (
              <div className="p-8 text-center text-zinc-500">
                <FileText className="w-8 h-8 mx-auto mb-3 opacity-50" />
                <p className="text-sm">No pages in queue</p>
                <p className="text-xs mt-1">Seed data to get started</p>
              </div>
            ) : (
              recommended.map((page, idx) => (
                <Link
                  key={page.id}
                  to={`/workspace/${page.id}`}
                  className="flex items-center justify-between p-4 border-b border-zinc-800 last:border-b-0 hover:bg-zinc-900 transition-colors duration-150"
                  data-testid={`recommended-page-${idx}`}
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-zinc-500 font-mono w-6">#{idx + 1}</span>
                      <span className="text-white truncate">{page.page_name}</span>
                    </div>
                    <div className="flex items-center gap-4 mt-1 ml-9">
                      <span className="text-xs text-zinc-500">{page.page_family}</span>
                      <span className={`text-xs ${getStatusColor(page.status)}`}>{page.status}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="font-mono text-sm text-zinc-400">
                      P{page.priority_score}
                    </span>
                    <ArrowRight className="w-4 h-4 text-zinc-500" />
                  </div>
                </Link>
              ))
            )}
          </div>
        </div>

        {/* Recent Activity */}
        <div className="border border-zinc-800">
          <div className="p-4 border-b border-zinc-800">
            <h2 className="font-['Outfit'] text-lg font-medium tracking-tight">
              Recent Activity
            </h2>
          </div>
          <div className="max-h-[400px] overflow-y-auto" data-testid="activity-list">
            {activity.length === 0 ? (
              <div className="p-8 text-center text-zinc-500">
                <Clock className="w-8 h-8 mx-auto mb-3 opacity-50" />
                <p className="text-sm">No activity yet</p>
              </div>
            ) : (
              activity.map((item, idx) => (
                <div 
                  key={item.id} 
                  className="activity-item px-4"
                  data-testid={`activity-item-${idx}`}
                >
                  <div className="flex items-start gap-3">
                    <div className="mt-0.5 text-zinc-500">
                      {getActionIcon(item.action)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-white truncate">
                        {item.page_name || item.action.replace(/_/g, ' ')}
                      </p>
                      <p className="text-xs text-zinc-500 mt-0.5">
                        {item.details}
                      </p>
                      <p className="text-xs text-zinc-600 mt-1 font-mono">
                        {new Date(item.timestamp).toLocaleString()}
                      </p>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Status Breakdown */}
      {stats?.by_status && Object.keys(stats.by_status).length > 0 && (
        <div className="border border-zinc-800">
          <div className="p-4 border-b border-zinc-800">
            <h2 className="font-['Outfit'] text-lg font-medium tracking-tight">
              Status Breakdown
            </h2>
          </div>
          <div className="p-4 grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4" data-testid="status-breakdown">
            {Object.entries(stats.by_status).map(([status, count]) => (
              <div key={status} className="text-center">
                <div className={`font-mono text-2xl font-semibold ${getStatusColor(status)}`}>
                  {count}
                </div>
                <div className="text-xs text-zinc-500 mt-1">{status}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
