import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { 
  LayoutDashboard, FileText, Settings, LogOut, 
  Layers, Zap, Award, LayoutTemplate, Palette, TrendingUp,
  BookOpen, ListChecks, Magnet, ShoppingCart, Activity, MessageSquare,
  Package, Globe, Camera, Users, Command,
} from 'lucide-react';

export default function Layout({ children }) {
  const { logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const pageOpsItems = [
    { to: '/page-queue', icon: FileText, label: 'Page Queue' },
    { to: '/bulk', icon: ListChecks, label: 'Bulk Queue' },
    { to: '/exemplars', icon: Award, label: 'Exemplars' },
    { to: '/templates', icon: LayoutTemplate, label: 'Templates' },
    { to: '/styles', icon: Palette, label: 'Styles' },
    { to: '/promotions', icon: TrendingUp, label: 'Promotions' },
  ];

  const productItems = [
    { to: '/intake', icon: ShoppingCart, label: 'Product Intake' },
    { to: '/field-listing', icon: Camera, label: 'Field-to-Listing' },
    { to: '/catalog', icon: Package, label: 'Catalog' },
  ];

  const publishItems = [
    { to: '/wp-placement', icon: Globe, label: 'WP Placement' },
  ];

  const opsItems = [
    { to: '/execution-manifests', icon: Layers, label: 'Execution Manifests' },
  ];

  const toolItems = [
    { to: '/specs', icon: BookOpen, label: 'Spec Library' },
    { to: '/lead-magnets', icon: Magnet, label: 'Lead Magnets' },
    { to: '/comms', icon: MessageSquare, label: 'Customer Comms' },
  ];

  const systemItems = [
    { to: '/health', icon: Activity, label: 'Operator Health' },
    { to: '/spine', icon: Zap, label: 'Execution Spine' },
    { to: '/settings', icon: Settings, label: 'Settings' },
  ];

  return (
    <div className="min-h-screen bg-[#09090B] flex">
      {/* Sidebar */}
      <aside className="sidebar flex flex-col">
        {/* Logo */}
        <div className="p-6 border-b border-zinc-800">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 border border-white flex items-center justify-center">
              <Zap className="w-4 h-4 text-white" />
            </div>
            <div>
              <h1 className="font-['Outfit'] text-sm font-medium text-white tracking-tight">
                TS Operator
              </h1>
              <p className="text-[10px] text-zinc-500 tracking-[0.15em] uppercase">
                Minion System
              </p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-4 overflow-y-auto" data-testid="main-navigation">
          {/* Core 3: OPS / ECO / Queue */}
          <NavLink
            to="/"
            end
            className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
            data-testid="nav-ops"
          >
            <Command className="w-4 h-4" />
            <span className="text-sm">OPS</span>
          </NavLink>
          <NavLink
            to="/eco"
            className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
            data-testid="nav-eco"
          >
            <Layers className="w-4 h-4" />
            <span className="text-sm">ECO Hub</span>
          </NavLink>
          <NavLink
            to="/queue"
            className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
            data-testid="nav-queue"
          >
            <Users className="w-4 h-4" />
            <span className="text-sm">Queue</span>
          </NavLink>

          <div className="px-4 mt-5 mb-2">
            <span className="text-[10px] text-zinc-600 uppercase tracking-[0.15em]">Page Ops</span>
          </div>
          {pageOpsItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) => 
                `nav-link ${isActive ? 'active' : ''}`
              }
              data-testid={`nav-${item.label.toLowerCase().replace(/\s+/g, '-')}`}
            >
              <item.icon className="w-4 h-4" />
              <span className="text-sm">{item.label}</span>
            </NavLink>
          ))}
          
          <div className="px-4 mt-5 mb-2">
            <span className="text-[10px] text-zinc-600 uppercase tracking-[0.15em]">Product</span>
          </div>
          {productItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => 
                `nav-link ${isActive ? 'active' : ''}`
              }
              data-testid={`nav-${item.label.toLowerCase().replace(/\s+/g, '-')}`}
            >
              <item.icon className="w-4 h-4" />
              <span className="text-sm">{item.label}</span>
            </NavLink>
          ))}

          <div className="px-4 mt-5 mb-2">
            <span className="text-[10px] text-zinc-600 uppercase tracking-[0.15em]">OPS Execution</span>
          </div>
          {opsItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => 
                `nav-link ${isActive ? 'active' : ''}`
              }
              data-testid={`nav-${item.label.toLowerCase().replace(/\s+/g, '-')}`}
            >
              <item.icon className="w-4 h-4" />
              <span className="text-sm">{item.label}</span>
            </NavLink>
          ))}

          <div className="px-4 mt-5 mb-2">
            <span className="text-[10px] text-zinc-600 uppercase tracking-[0.15em]">Publish</span>
          </div>
          {publishItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => 
                `nav-link ${isActive ? 'active' : ''}`
              }
              data-testid={`nav-${item.label.toLowerCase().replace(/\s+/g, '-')}`}
            >
              <item.icon className="w-4 h-4" />
              <span className="text-sm">{item.label}</span>
            </NavLink>
          ))}

          <div className="px-4 mt-5 mb-2">
            <span className="text-[10px] text-zinc-600 uppercase tracking-[0.15em]">Tools</span>
          </div>
          {toolItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => 
                `nav-link ${isActive ? 'active' : ''}`
              }
              data-testid={`nav-${item.label.toLowerCase().replace(/\s+/g, '-')}`}
            >
              <item.icon className="w-4 h-4" />
              <span className="text-sm">{item.label}</span>
            </NavLink>
          ))}

          <div className="px-4 mt-5 mb-2">
            <span className="text-[10px] text-zinc-600 uppercase tracking-[0.15em]">System</span>
          </div>
          {systemItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => 
                `nav-link ${isActive ? 'active' : ''}`
              }
              data-testid={`nav-${item.label.toLowerCase().replace(/\s+/g, '-')}`}
            >
              <item.icon className="w-4 h-4" />
              <span className="text-sm">{item.label}</span>
            </NavLink>
          ))}
        </nav>

        {/* Module Badge */}
        <div className="px-4 py-3">
          <div className="p-3 border border-zinc-800 bg-zinc-900/50">
            <div className="flex items-center gap-2 text-xs text-zinc-500">
              <Layers className="w-3 h-3" />
              <span className="tracking-[0.1em] uppercase">TS Operator</span>
            </div>
            <div className="text-sm text-white mt-1 font-['Outfit']">v2.8 — Modular</div>
          </div>
        </div>

        {/* Logout */}
        <div className="p-4 border-t border-zinc-800">
          <button
            onClick={handleLogout}
            className="nav-link w-full justify-start text-zinc-500 hover:text-white"
            data-testid="logout-btn"
          >
            <LogOut className="w-4 h-4" />
            <span className="text-sm">Exit</span>
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto">
        {children}
      </main>
    </div>
  );
}
