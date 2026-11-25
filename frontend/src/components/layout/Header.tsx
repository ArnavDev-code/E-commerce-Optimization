import React from 'react';
import { Calendar, Store } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export const Header: React.FC = () => {
  const { isDemo } = useAuth();

  return (
    <header className="h-16 bg-white border-b border-slate-200 px-6 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-100 rounded-md text-xs font-medium text-slate-700">
          <Store className="w-3.5 h-3.5 text-blue-600" />
          <span>{isDemo ? 'demo-store.myshopify.com' : 'live-store.myshopify.com'}</span>
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 px-3 py-1.5 border border-slate-200 rounded-md text-xs font-medium text-slate-600 bg-white shadow-sm">
          <Calendar className="w-3.5 h-3.5 text-slate-400" />
          <span>Last 30 Days (Demo Period)</span>
        </div>
      </div>
    </header>
  );
};
