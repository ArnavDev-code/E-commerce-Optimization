import React from 'react';
import {
  DollarSign,
  TrendingUp,
  ShoppingCart,
  AlertTriangle,
  ArrowRight,
} from 'lucide-react';
import { MetricCard } from '../components/common/MetricCard';
import { Link } from 'react-router-dom';

export const Dashboard: React.FC = () => {
  return (
    <div className="space-y-8">
      {/* Top Welcome & Summary */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Revenue Recovery Intelligence</h1>
          <p className="text-sm text-slate-500 mt-1">
            Analyzing product-level conversion dropoffs, cart frictions, and margin impacts.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            to="/leaks"
            className="inline-flex items-center gap-2 bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold px-4 py-2.5 rounded-lg shadow-sm transition"
          >
            <AlertTriangle className="w-4 h-4" />
            View 4 Active Leaks
          </Link>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Revenue (30d)"
          value="$12,480.00"
          subtitle="From 159 completed orders"
          change="+8.4% vs last period"
          isPositive={true}
          icon={DollarSign}
        />
        <MetricCard
          title="Overall Conversion"
          value="2.45%"
          subtitle="Store-wide checkout completion"
          change="-0.6% vs baseline"
          isPositive={false}
          icon={TrendingUp}
        />
        <MetricCard
          title="Average Order Value"
          value="$78.49"
          subtitle="Across 24 active products"
          change="+$4.20 vs baseline"
          isPositive={true}
          icon={ShoppingCart}
        />
        <MetricCard
          title="Detected Revenue Leaks"
          value="4 Products"
          subtitle="Estimated $6,200/mo opportunity"
          variant="danger"
          icon={AlertTriangle}
        />
      </div>

      {/* Revenue Leaks Spotlight Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-5 border-b border-slate-100 flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-500" />
              Highest Priority Conversion Leaks
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Verified product-level dropoffs backed by deterministic sample thresholds (min sample &ge; 50).
            </p>
          </div>
          <Link
            to="/leaks"
            className="text-xs font-semibold text-blue-600 hover:text-blue-700 flex items-center gap-1"
          >
            All Leaks <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-200">
                <th className="py-3 px-4">Product</th>
                <th className="py-3 px-4">Leak Type</th>
                <th className="py-3 px-4">Observed vs Baseline</th>
                <th className="py-3 px-4">Sample Size</th>
                <th className="py-3 px-4">Severity</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-medium text-slate-700">
              <tr className="hover:bg-slate-50/80 transition">
                <td className="py-3.5 px-4">
                  <div className="font-semibold text-slate-900">Vitamin C Brightening Serum (30ml)</div>
                  <div className="text-[11px] text-slate-400">Skincare &bull; Lumina Botanicals</div>
                </td>
                <td className="py-3.5 px-4">
                  <span className="font-mono text-slate-600">Low Add-to-Cart Rate</span>
                </td>
                <td className="py-3.5 px-4">
                  <span className="text-rose-600 font-bold">1.25%</span> vs <span className="text-slate-400">4.80%</span>
                  <span className="block text-[11px] text-rose-500">-74.0% deficit</span>
                </td>
                <td className="py-3.5 px-4 font-mono">4,280 views</td>
                <td className="py-3.5 px-4">
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-100 text-rose-800 border border-rose-200">
                    Critical
                  </span>
                </td>
                <td className="py-3.5 px-4 text-right">
                  <Link
                    to="/leaks"
                    className="text-blue-600 hover:text-blue-700 font-semibold text-xs"
                  >
                    Diagnose &rarr;
                  </Link>
                </td>
              </tr>

              <tr className="hover:bg-slate-50/80 transition">
                <td className="py-3.5 px-4">
                  <div className="font-semibold text-slate-900">Retinol Recovery Night Cream</div>
                  <div className="text-[11px] text-slate-400">Skincare &bull; Lumina Botanicals</div>
                </td>
                <td className="py-3.5 px-4">
                  <span className="font-mono text-slate-600">ATC Rate Decline</span>
                </td>
                <td className="py-3.5 px-4">
                  <span className="text-rose-600 font-bold">2.10%</span> vs <span className="text-slate-400">5.20%</span>
                  <span className="block text-[11px] text-rose-500">-59.6% decline</span>
                </td>
                <td className="py-3.5 px-4 font-mono">2,150 views</td>
                <td className="py-3.5 px-4">
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-orange-100 text-orange-800 border border-orange-200">
                    High
                  </span>
                </td>
                <td className="py-3.5 px-4 text-right">
                  <Link
                    to="/leaks"
                    className="text-blue-600 hover:text-blue-700 font-semibold text-xs"
                  >
                    Diagnose &rarr;
                  </Link>
                </td>
              </tr>

              <tr className="hover:bg-slate-50/80 transition">
                <td className="py-3.5 px-4">
                  <div className="font-semibold text-slate-900">Hyaluronic Acid Intense Moisturizer</div>
                  <div className="text-[11px] text-slate-400">Skincare &bull; Lumina Botanicals</div>
                </td>
                <td className="py-3.5 px-4">
                  <span className="font-mono text-slate-600">High ATC, Low Checkout</span>
                </td>
                <td className="py-3.5 px-4">
                  <span className="text-rose-600 font-bold">14.20%</span> vs <span className="text-slate-400">64.50%</span>
                  <span className="block text-[11px] text-rose-500">Cart dropoff</span>
                </td>
                <td className="py-3.5 px-4 font-mono">340 ATCs</td>
                <td className="py-3.5 px-4">
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-orange-100 text-orange-800 border border-orange-200">
                    High
                  </span>
                </td>
                <td className="py-3.5 px-4 text-right">
                  <Link
                    to="/leaks"
                    className="text-blue-600 hover:text-blue-700 font-semibold text-xs"
                  >
                    Diagnose &rarr;
                  </Link>
                </td>
              </tr>

              <tr className="hover:bg-slate-50/80 transition">
                <td className="py-3.5 px-4">
                  <div className="font-semibold text-slate-900">Organic Rosehip Face Oil</div>
                  <div className="text-[11px] text-slate-400">Skincare &bull; Pure Botanics</div>
                </td>
                <td className="py-3.5 px-4">
                  <span className="font-mono text-slate-600">Low Purchase Completion</span>
                </td>
                <td className="py-3.5 px-4">
                  <span className="text-rose-600 font-bold">22.50%</span> vs <span className="text-slate-400">72.00%</span>
                  <span className="block text-[11px] text-rose-500">Payment dropoff</span>
                </td>
                <td className="py-3.5 px-4 font-mono">180 Checkouts</td>
                <td className="py-3.5 px-4">
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-200">
                    Medium
                  </span>
                </td>
                <td className="py-3.5 px-4 text-right">
                  <Link
                    to="/leaks"
                    className="text-blue-600 hover:text-blue-700 font-semibold text-xs"
                  >
                    Diagnose &rarr;
                  </Link>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
