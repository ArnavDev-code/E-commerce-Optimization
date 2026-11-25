import React from 'react';
import { useAuth } from '../../context/AuthContext';
import { Sparkles, ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';

export const DemoBanner: React.FC = () => {
  const { isDemo } = useAuth();
  if (!isDemo) return null;

  return (
    <div className="bg-gradient-to-r from-blue-600 to-indigo-700 text-white px-4 py-2.5 text-xs sm:text-sm font-medium flex items-center justify-between shadow-sm">
      <div className="flex items-center gap-2">
        <span className="flex h-2 w-2 relative">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-300 opacity-75"></span>
          <span className="relative inline-flex rounded-full h-2 w-2 bg-white"></span>
        </span>
        <Sparkles className="w-4 h-4 text-blue-200" />
        <span>
          <strong>DEMO STORE MODE</strong> — Viewing simulated Shopify & Web Pixel telemetry with deliberate conversion leaks.
        </span>
      </div>
      <Link
        to="/integrations"
        className="hidden md:inline-flex items-center gap-1.5 bg-white/20 hover:bg-white/30 text-white rounded-md px-3 py-1 text-xs transition"
      >
        Connect Live Shopify Store
        <ArrowRight className="w-3.5 h-3.5" />
      </Link>
    </div>
  );
};
