import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Package,
  AlertTriangle,
  Lightbulb,
  FlaskConical,
  Plug,
  Settings,
  LogOut,
  Flame,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

const NAV_ITEMS = [
  { label: 'Overview', to: '/', icon: LayoutDashboard },
  { label: 'Products & Costs', to: '/products', icon: Package },
  { label: 'Revenue Leaks', to: '/leaks', icon: AlertTriangle, badge: '4' },
  { label: 'AI Recommendations', to: '/recommendations', icon: Lightbulb },
  { label: 'CRO Experiments', to: '/experiments', icon: FlaskConical },
  { label: 'Integrations', to: '/integrations', icon: Plug },
  { label: 'Settings', to: '/settings', icon: Settings },
];

export const Sidebar: React.FC = () => {
  const { merchant, logout } = useAuth();

  return (
    <aside className="w-64 bg-slate-900 text-slate-300 flex flex-col shrink-0 min-h-screen">
      {/* Brand Header */}
      <div className="h-16 px-6 flex items-center gap-3 border-b border-slate-800">
        <div className="p-2 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-lg text-white">
          <Flame className="w-5 h-5 text-amber-300 fill-amber-300" />
        </div>
        <div>
          <span className="font-bold text-white text-base tracking-tight">FunnelLeak AI</span>
          <span className="block text-[10px] text-blue-400 font-medium uppercase tracking-wider">
            Revenue Recovery
          </span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              `flex items-center justify-between px-3.5 py-2.5 rounded-lg text-sm font-medium transition ${
                isActive
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-slate-400 hover:bg-slate-800/80 hover:text-slate-100'
              }`
            }
          >
            <div className="flex items-center gap-3">
              <item.icon className="w-4 h-4 shrink-0" />
              <span>{item.label}</span>
            </div>
            {item.badge && (
              <span className="bg-rose-500/20 text-rose-300 border border-rose-500/30 text-[11px] font-bold px-2 py-0.5 rounded-full">
                {item.badge}
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Footer / Account */}
      <div className="p-4 border-t border-slate-800">
        <div className="flex items-center justify-between">
          <div className="truncate pr-2">
            <p className="text-xs font-semibold text-white truncate">
              {merchant?.name || 'Demo Merchant'}
            </p>
            <p className="text-[11px] text-slate-400 truncate">{merchant?.email}</p>
          </div>
          <button
            onClick={logout}
            title="Log out"
            className="p-1.5 rounded-md text-slate-400 hover:text-rose-400 hover:bg-slate-800 transition"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </aside>
  );
};
