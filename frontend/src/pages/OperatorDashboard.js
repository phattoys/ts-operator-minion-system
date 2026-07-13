import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import {
  Activity, FileText, Magnet, ShoppingCart, BookOpen,
  TrendingUp, TrendingDown, Minus, AlertTriangle,
  CheckCircle, Clock, ArrowRight, Package, Zap,
  DollarSign, Download, Eye, RefreshCw,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export default function OperatorDashboard() {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState(null);

  const fetchHealth = async () => {
    try {
      const res = await axios.get(`${API}/dashboard/health`, { withCredentials: true });
      setHealth(res.data);
      setLastRefresh(new Date());
    } catch (err) {
      console.error('Failed to fetch health:', err);
    }
    setLoading(false);
  };

  useEffect(() => { fetchHealth(); }, []);

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[50vh]">
        <div className="text-zinc-500 text-sm animate-pulse">Loading operator health...</div>
      </div>
    );
  }

  if (!health) {
    return (
      <div className="p-8 text-center text-zinc-500">Failed to load dashboard data.</div>
    );
  }

  const m = health.modules;
  const rtp = health.ready_to_publish;

  return (
    <div className="p-8 max-w-[1400px] mx-auto" data-testid="operator-dashboard">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-['Outfit'] font-light text-white tracking-tight">
            Operator Health
          </h1>
          <p className="text-sm text-zinc-500 mt-1">
            Cross-module founder view
            {lastRefresh && <span> &middot; {lastRefresh.toLocaleTimeString()}</span>}
          </p>
        </div>
        <button
          onClick={() => { setLoading(true); fetchHealth(); }}
          className="flex items-center gap-2 px-3 py-2 border border-zinc-700 text-sm text-zinc-300 hover:border-zinc-500 transition-colors"
          data-testid="refresh-btn"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </div>

      {/* Ready to Publish Banner */}
      <div className="border border-zinc-800 p-5 mb-8 bg-zinc-900/30" data-testid="ready-banner">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-[10px] text-zinc-600 uppercase tracking-wider mb-1">Ready to Publish</div>
            <div className="text-3xl font-['Outfit'] text-emerald-400">{rtp.total}</div>
            <div className="text-xs text-zinc-500 mt-1">
              {rtp.pages_approved} pages &middot; {rtp.lead_magnets_ready} lead magnets &middot; {rtp.intake_items_ready} products
            </div>
          </div>
          {m.product_intake.revenue_estimate > 0 && (
            <div className="text-right">
              <div className="text-[10px] text-zinc-600 uppercase tracking-wider mb-1">Est. Revenue (Ready Items)</div>
              <div className="text-2xl font-['Outfit'] text-white flex items-center gap-1">
                <DollarSign className="w-5 h-5 text-emerald-400" />
                {m.product_intake.revenue_estimate.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Module Cards */}
      <div className="grid grid-cols-2 gap-4 mb-8" data-testid="module-cards">
        <ModuleCard
          title="Page Ops"
          icon={FileText}
          link="/queue"
          total={m.page_ops.total}
          items={[
            { label: 'Approved', value: m.page_ops.approved, color: 'text-emerald-400' },
            { label: 'Stuck (7d+)', value: m.page_ops.stuck, color: m.page_ops.stuck > 0 ? 'text-red-400' : 'text-zinc-400' },
          ]}
          velocity={m.page_ops.velocity}
          statusMap={m.page_ops.by_status}
        />
        <ModuleCard
          title="Lead Magnets"
          icon={Magnet}
          link="/lead-magnets"
          total={m.lead_magnets.total}
          items={[
            { label: 'Published', value: m.lead_magnets.published, color: 'text-emerald-400' },
            { label: 'Downloads', value: m.lead_magnets.total_downloads, color: 'text-white', icon: Download },
          ]}
          statusMap={m.lead_magnets.by_status}
        />
        <ModuleCard
          title="Product Intake"
          icon={ShoppingCart}
          link="/intake"
          total={m.product_intake.total_items}
          subtitle={`${m.product_intake.total_sessions} sessions`}
          items={[
            { label: 'Ready', value: m.product_intake.ready, color: 'text-emerald-400' },
            { label: 'Needs Info', value: m.product_intake.needs_info, color: m.product_intake.needs_info > 0 ? 'text-orange-400' : 'text-zinc-400' },
            { label: 'Stuck (7d+)', value: m.product_intake.stuck, color: m.product_intake.stuck > 0 ? 'text-red-400' : 'text-zinc-400' },
          ]}
          velocity={m.product_intake.velocity}
          statusMap={m.product_intake.by_status}
        />
        <ModuleCard
          title="Spec Writer"
          icon={BookOpen}
          link="/specs"
          total={m.specs.total}
          items={[
            { label: 'Scored', value: m.specs.by_status?.Scored || 0, color: 'text-emerald-400' },
            { label: 'Handed Off', value: m.specs.by_status?.['Handed Off'] || 0, color: 'text-blue-400' },
          ]}
          statusMap={m.specs.by_status}
        />
      </div>

      {/* Catalog Health Widget */}
      {health.catalog_health && health.catalog_health.total > 0 && (
        <div className="mb-8" data-testid="catalog-health-widget">
          <CatalogHealthWidget data={health.catalog_health} />
        </div>
      )}

      {/* Bottlenecks + Activity */}
      <div className="grid grid-cols-2 gap-4">
        {/* Bottlenecks */}
        <div className="border border-zinc-800" data-testid="bottlenecks">
          <div className="p-4 border-b border-zinc-800">
            <h3 className="text-sm font-medium text-white flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-400" />
              Bottlenecks
            </h3>
          </div>
          {health.bottlenecks.length === 0 ? (
            <div className="p-4 text-sm text-zinc-500 flex items-center gap-2">
              <CheckCircle className="w-4 h-4 text-emerald-500" />
              No bottlenecks detected. Systems running clean.
            </div>
          ) : (
            <div className="divide-y divide-zinc-800">
              {health.bottlenecks.map((b, i) => (
                <div key={i} className="p-3 flex items-start gap-3">
                  <div className={`mt-0.5 ${
                    b.severity === 'critical' ? 'text-red-400' :
                    b.severity === 'warning' ? 'text-amber-400' : 'text-zinc-500'
                  }`}>
                    <AlertTriangle className="w-3.5 h-3.5" />
                  </div>
                  <div>
                    <div className="text-xs text-zinc-300">{b.issue}</div>
                    <div className="text-[10px] text-zinc-600 mt-0.5">{b.module}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Activity Feed */}
        <div className="border border-zinc-800" data-testid="activity-feed">
          <div className="p-4 border-b border-zinc-800">
            <h3 className="text-sm font-medium text-white flex items-center gap-2">
              <Activity className="w-4 h-4 text-zinc-400" />
              Recent Activity
            </h3>
          </div>
          {health.recent_activity.length === 0 ? (
            <div className="p-4 text-sm text-zinc-500">No recent activity.</div>
          ) : (
            <div className="divide-y divide-zinc-800 max-h-[300px] overflow-y-auto">
              {health.recent_activity.map((a, i) => (
                <div key={i} className="p-3">
                  <div className="text-xs text-zinc-300">{a.details || a.action}</div>
                  <div className="text-[10px] text-zinc-600 mt-0.5">
                    {a.action && <span className="text-zinc-500">{a.action}</span>}
                    {a.timestamp && <span> &middot; {new Date(a.timestamp).toLocaleString()}</span>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}


function ModuleCard({ title, icon: Icon, link, total, subtitle, items, velocity, statusMap }) {
  return (
    <div className="border border-zinc-800 p-4 hover:border-zinc-700 transition-colors" data-testid={`module-${title.toLowerCase().replace(/\s+/g, '-')}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Icon className="w-4 h-4 text-zinc-500" />
          <span className="text-sm font-medium text-white">{title}</span>
        </div>
        <Link to={link} className="text-[10px] text-zinc-500 hover:text-white flex items-center gap-0.5 transition-colors">
          Open <ArrowRight className="w-3 h-3" />
        </Link>
      </div>

      <div className="flex items-end gap-3 mb-3">
        <div className="text-2xl font-['Outfit'] text-white">{total}</div>
        {subtitle && <span className="text-xs text-zinc-500 mb-0.5">{subtitle}</span>}
        {velocity && (
          <div className="flex items-center gap-1 text-xs mb-0.5 ml-auto">
            {velocity.trend === 'up' ? (
              <TrendingUp className="w-3.5 h-3.5 text-emerald-400" />
            ) : velocity.trend === 'down' ? (
              <TrendingDown className="w-3.5 h-3.5 text-red-400" />
            ) : (
              <Minus className="w-3.5 h-3.5 text-zinc-500" />
            )}
            <span className="text-zinc-400">{velocity.this_week} this wk</span>
            <span className="text-zinc-600">/ {velocity.last_week} last</span>
          </div>
        )}
      </div>

      <div className="flex items-center gap-4">
        {items.map((item, i) => (
          <div key={i} className="flex items-center gap-1.5">
            {item.icon && <item.icon className="w-3 h-3 text-zinc-500" />}
            <span className={`text-sm font-['Outfit'] ${item.color}`}>{item.value}</span>
            <span className="text-[10px] text-zinc-600">{item.label}</span>
          </div>
        ))}
      </div>

      {/* Mini status bar */}
      {statusMap && Object.keys(statusMap).length > 0 && (
        <div className="flex gap-1 mt-3">
          {Object.entries(statusMap).map(([status, count]) => (
            <div
              key={status}
              className="h-1 rounded-full"
              style={{
                flex: count,
                backgroundColor: getStatusColor(status),
              }}
              title={`${status}: ${count}`}
            />
          ))}
        </div>
      )}
    </div>
  );
}


function getStatusColor(status) {
  const s = status.toLowerCase();
  if (['approved', 'published', 'ready', 'handed off', 'scored'].includes(s)) return '#34d399';
  if (['queued', 'in_review', 'in review', 'draft'].includes(s)) return '#fbbf24';
  if (['needs_info', 'needs info', 'rejected'].includes(s)) return '#f97316';
  if (['archived'].includes(s)) return '#52525b';
  return '#71717a';
}


function CatalogHealthWidget({ data }) {
  const { pct_normalized, unresolved_duplicates, stuck_draft_7d, needs_attention, total } = data;
  const normColor = pct_normalized >= 80 ? 'text-emerald-400' : pct_normalized >= 50 ? 'text-amber-400' : 'text-red-400';
  const dupColor = unresolved_duplicates === 0 ? 'text-emerald-400' : unresolved_duplicates <= 3 ? 'text-amber-400' : 'text-red-400';
  const stuckColor = stuck_draft_7d === 0 ? 'text-emerald-400' : stuck_draft_7d <= 5 ? 'text-amber-400' : 'text-red-400';

  return (
    <div className={`border p-4 ${needs_attention ? 'border-amber-800/50 bg-amber-950/10' : 'border-zinc-800'}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Package className="w-4 h-4 text-zinc-500" />
          <span className="text-sm font-medium text-white">Catalog Health</span>
          {needs_attention && (
            <span className="px-1.5 py-0.5 text-[10px] uppercase tracking-wider bg-amber-900/30 text-amber-400">
              Needs Attention
            </span>
          )}
        </div>
        <Link to="/catalog" className="text-[10px] text-zinc-500 hover:text-white flex items-center gap-0.5 transition-colors">
          Open <ArrowRight className="w-3 h-3" />
        </Link>
      </div>
      <div className="flex items-center gap-8">
        <div>
          <div className={`text-xl font-['Outfit'] ${normColor}`}>{pct_normalized}%</div>
          <div className="text-[10px] text-zinc-600 uppercase tracking-wider mt-0.5">Normalized</div>
        </div>
        <div>
          <div className={`text-xl font-['Outfit'] ${dupColor}`}>{unresolved_duplicates}</div>
          <div className="text-[10px] text-zinc-600 uppercase tracking-wider mt-0.5">Unresolved Dupes</div>
        </div>
        <div>
          <div className={`text-xl font-['Outfit'] ${stuckColor}`}>{stuck_draft_7d}</div>
          <div className="text-[10px] text-zinc-600 uppercase tracking-wider mt-0.5">Stuck Draft (7d+)</div>
        </div>
        <div className="ml-auto text-right">
          <div className="text-xl font-['Outfit'] text-zinc-400">{total}</div>
          <div className="text-[10px] text-zinc-600 uppercase tracking-wider mt-0.5">Total Items</div>
        </div>
      </div>
    </div>
  );
}
