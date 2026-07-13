import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import {
  Zap, ArrowRight, FileText, ShoppingCart, Package, Globe,
  Camera, BookOpen, Magnet, MessageSquare, Users, Eye,
  Activity, CheckCircle,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const MINION_ICONS = {
  page_ops: FileText,
  worker_queue: Users,
  wp_placement: Globe,
  field_listing: Camera,
  product_intake: ShoppingCart,
  catalog: Package,
  lead_magnets: Magnet,
  spec_writer: BookOpen,
  comms: MessageSquare,
  spine: Zap,
};

const STAGE_COLORS = {
  'Content Creation': 'border-blue-800/40 bg-blue-950/15',
  'Orchestration': 'border-amber-800/40 bg-amber-950/15',
  'Publishing': 'border-emerald-800/40 bg-emerald-950/15',
  'Product Intake': 'border-purple-800/40 bg-purple-950/15',
  'Product Management': 'border-orange-800/40 bg-orange-950/15',
  'Marketing': 'border-pink-800/40 bg-pink-950/15',
  'Planning': 'border-cyan-800/40 bg-cyan-950/15',
  'Customer Relations': 'border-teal-800/40 bg-teal-950/15',
};

export default function EcoHub() {
  const navigate = useNavigate();
  const [minions, setMinions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchMinions = async () => {
      try {
        const res = await axios.get(`${API}/command-center/minion-directory`, { withCredentials: true });
        setMinions(res.data.minions || []);
      } catch (err) {
        console.error('Failed to load minion directory:', err);
      }
      setLoading(false);
    };
    fetchMinions();
  }, []);

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[50vh]">
        <div className="text-zinc-500 text-sm animate-pulse">Loading Ecosystem...</div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl mx-auto" data-testid="eco-hub">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">TS Operator Ecosystem</h1>
        <p className="text-sm text-zinc-500 mt-1">
          {minions.length} minions &middot; Your staff, organized
        </p>
      </div>

      {/* Quick Access */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8" data-testid="quick-access">
        <button
          onClick={() => navigate('/')}
          className="border border-amber-800/40 bg-amber-950/15 p-4 text-left hover:border-amber-600/60 transition"
          data-testid="go-to-ops"
        >
          <Activity className="w-5 h-5 text-amber-400 mb-2" />
          <div className="text-sm text-white font-medium">OPS</div>
          <div className="text-[10px] text-zinc-500 mt-0.5">Action dashboard</div>
        </button>
        <button
          onClick={() => navigate('/queue')}
          className="border border-blue-800/40 bg-blue-950/15 p-4 text-left hover:border-blue-600/60 transition"
          data-testid="go-to-queue"
        >
          <Users className="w-5 h-5 text-blue-400 mb-2" />
          <div className="text-sm text-white font-medium">Queue</div>
          <div className="text-[10px] text-zinc-500 mt-0.5">All tasks in motion</div>
        </button>
        <button
          onClick={() => navigate('/field-listing')}
          className="border border-purple-800/40 bg-purple-950/15 p-4 text-left hover:border-purple-600/60 transition"
        >
          <Camera className="w-5 h-5 text-purple-400 mb-2" />
          <div className="text-sm text-white font-medium">Field-to-Listing</div>
          <div className="text-[10px] text-zinc-500 mt-0.5">Photo batch intake</div>
        </button>
        <button
          onClick={() => navigate('/wp-placement')}
          className="border border-emerald-800/40 bg-emerald-950/15 p-4 text-left hover:border-emerald-600/60 transition"
        >
          <Globe className="w-5 h-5 text-emerald-400 mb-2" />
          <div className="text-sm text-white font-medium">WP Placement</div>
          <div className="text-[10px] text-zinc-500 mt-0.5">WordPress drafts</div>
        </button>
      </div>

      {/* Minion Staffing Chart */}
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm text-zinc-400 font-medium">Minion Staffing Chart</h2>
        <span className="text-[10px] text-zinc-600">{minions.length} active</span>
      </div>

      <div className="space-y-2" data-testid="minion-directory">
        {minions.map(m => {
          const Icon = MINION_ICONS[m.code] || Zap;
          const stageColor = STAGE_COLORS[m.workflow_stage] || 'border-zinc-800 bg-zinc-900/30';

          return (
            <div
              key={m.code}
              className={`border p-4 ${stageColor} hover:brightness-110 transition cursor-pointer`}
              onClick={() => navigate(m.nav_path)}
              data-testid={`minion-${m.code}`}
            >
              <div className="flex items-start gap-4">
                <div className="w-10 h-10 border border-zinc-700 flex items-center justify-center flex-shrink-0">
                  <Icon className="w-5 h-5 text-zinc-300" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-white font-medium">{m.name}</span>
                    {m.labor_ready && <CheckCircle className="w-3 h-3 text-emerald-500" />}
                    <span className="text-[9px] text-zinc-600 border border-zinc-800 px-1.5 py-0.5">{m.workflow_stage}</span>
                  </div>
                  <div className="text-xs text-zinc-400 mt-1">{m.role}</div>
                  <div className="text-[10px] text-zinc-500 mt-1">{m.what_it_does}</div>
                  <div className="flex items-center gap-4 mt-2 text-[10px]">
                    <span className="text-zinc-500">
                      <span className="text-zinc-600">In:</span> {m.inputs}
                    </span>
                  </div>
                  <div className="flex items-center gap-4 mt-0.5 text-[10px]">
                    <span className="text-zinc-500">
                      <span className="text-zinc-600">Out:</span> {m.outputs}
                    </span>
                  </div>
                </div>
                <div className="text-right flex-shrink-0">
                  <div className="text-xs text-zinc-400">{m.stats}</div>
                  <div className="text-[10px] text-zinc-500 mt-1">{m.next_action}</div>
                  <ArrowRight className="w-3.5 h-3.5 text-zinc-600 mt-2 ml-auto" />
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
