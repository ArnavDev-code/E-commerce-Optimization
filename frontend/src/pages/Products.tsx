import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { Product } from '../types';
import { formatCurrency, formatPercent, formatNumber } from '../utils/format';
import { Package, Search, Edit2, Check, X, Filter } from 'lucide-react';

export const Products: React.FC = () => {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('all');

  // Editing state for COGS
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editCost, setEditCost] = useState<string>('');
  const [savingCost, setSavingCost] = useState(false);

  const fetchProducts = async () => {
    setLoading(true);
    try {
      const data = await api.get<Product[]>('/products?days=30');
      setProducts(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load products');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProducts();
  }, []);

  const handleStartEdit = (p: Product) => {
    setEditingId(p.id);
    setEditCost(p.unit_cost != null ? String(p.unit_cost) : '');
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditCost('');
  };

  const handleSaveCost = async (productId: string) => {
    const numCost = parseFloat(editCost);
    if (isNaN(numCost) || numCost <= 0) {
      alert('Please enter a valid positive unit cost');
      return;
    }
    setSavingCost(true);
    try {
      await api.put(`/products/${productId}/cost`, {
        unit_cost: numCost,
        cost_source: 'manual',
      });
      // Refresh products to recalculate margins
      await fetchProducts();
      setEditingId(null);
    } catch (err: any) {
      alert(err.message || 'Failed to update unit cost');
    } finally {
      setSavingCost(false);
    }
  };

  const categories = ['all', ...Array.from(new Set(products.map((p) => p.product_type).filter(Boolean)))];

  const filtered = products.filter((p) => {
    const matchesSearch =
      p.title.toLowerCase().includes(search.toLowerCase()) ||
      (p.vendor && p.vendor.toLowerCase().includes(search.toLowerCase()));
    const matchesCategory = categoryFilter === 'all' || p.product_type === categoryFilter;
    return matchesSearch && matchesCategory;
  });

  return (
    <div className="space-y-6">
      {/* Title & Stats */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2.5">
            <Package className="w-6 h-6 text-blue-600" />
            Products & Cost Management
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Product performance metrics and Unit Costs (COGS) required for gross profit analysis.
          </p>
        </div>
        <div className="text-xs text-slate-500 bg-white border border-slate-200 rounded-lg px-3 py-2 shadow-sm">
          Tracking <strong>{products.length}</strong> active products &bull; 30-day reporting window
        </div>
      </div>

      {/* Filter / Search Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-col sm:flex-row gap-3 items-center justify-between">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search products or vendors..."
            className="w-full pl-9 pr-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
          />
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <Filter className="w-4 h-4 text-slate-400" />
          <span className="text-xs font-semibold text-slate-500">Category:</span>
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="text-xs border border-slate-300 rounded-lg px-2.5 py-2 bg-white outline-none focus:ring-2 focus:ring-blue-500"
          >
            {categories.map((c) => (
              <option key={c} value={c || 'all'}>
                {c === 'all' ? 'All Categories' : c}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Products Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-xs text-slate-400">Loading catalog performance...</div>
        ) : error ? (
          <div className="p-8 text-center text-xs text-rose-500">{error}</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-200">
                  <th className="py-3 px-4">Product</th>
                  <th className="py-3 px-3">Category</th>
                  <th className="py-3 px-3">Price</th>
                  <th className="py-3 px-3">Unit Cost (COGS)</th>
                  <th className="py-3 px-3">Gross Margin</th>
                  <th className="py-3 px-3 text-right">Views</th>
                  <th className="py-3 px-3 text-right">ATC Rate</th>
                  <th className="py-3 px-3 text-right">Orders</th>
                  <th className="py-3 px-4 text-right">Revenue</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-medium text-slate-700">
                {filtered.map((p) => {
                  const isEditing = editingId === p.id;
                  const isLowAtc = p.atc_rate != null && p.views != null && p.views >= 50 && p.atc_rate < 2.0;

                  return (
                    <tr key={p.id} className="hover:bg-slate-50/80 transition">
                      <td className="py-3.5 px-4 max-w-xs">
                        <div className="font-semibold text-slate-900 truncate" title={p.title}>
                          {p.title}
                        </div>
                        <div className="text-[11px] text-slate-400 truncate">{p.vendor}</div>
                      </td>
                      <td className="py-3.5 px-3">
                        <span className="px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 text-[11px]">
                          {p.product_type || 'General'}
                        </span>
                      </td>
                      <td className="py-3.5 px-3 font-semibold text-slate-900">
                        {formatCurrency(p.price)}
                      </td>
                      <td className="py-3.5 px-3">
                        {isEditing ? (
                          <div className="flex items-center gap-1">
                            <input
                              type="number"
                              step="0.01"
                              value={editCost}
                              onChange={(e) => setEditCost(e.target.value)}
                              className="w-20 px-2 py-1 border border-blue-500 rounded text-xs outline-none"
                              autoFocus
                            />
                            <button
                              onClick={() => handleSaveCost(p.id)}
                              disabled={savingCost}
                              className="p-1 rounded bg-emerald-600 text-white hover:bg-emerald-700"
                              title="Save"
                            >
                              <Check className="w-3 h-3" />
                            </button>
                            <button
                              onClick={handleCancelEdit}
                              className="p-1 rounded bg-slate-200 text-slate-600 hover:bg-slate-300"
                              title="Cancel"
                            >
                              <X className="w-3 h-3" />
                            </button>
                          </div>
                        ) : (
                          <div className="flex items-center gap-1.5 group">
                            <span className={p.unit_cost ? 'font-semibold text-slate-800' : 'text-slate-400 italic'}>
                              {p.unit_cost ? formatCurrency(p.unit_cost) : 'Not set'}
                            </span>
                            <button
                              onClick={() => handleStartEdit(p)}
                              className="opacity-0 group-hover:opacity-100 p-1 text-slate-400 hover:text-blue-600 rounded transition"
                              title="Edit unit cost"
                            >
                              <Edit2 className="w-3 h-3" />
                            </button>
                          </div>
                        )}
                      </td>
                      <td className="py-3.5 px-3">
                        {p.gross_margin_pct != null ? (
                          <span
                            className={`font-semibold ${
                              p.gross_margin_pct >= 50
                                ? 'text-emerald-600'
                                : p.gross_margin_pct >= 30
                                ? 'text-amber-600'
                                : 'text-rose-600'
                            }`}
                          >
                            {formatPercent(p.gross_margin_pct, 1)}
                          </span>
                        ) : (
                          <span className="text-slate-400 text-[11px]">—</span>
                        )}
                      </td>
                      <td className="py-3.5 px-3 text-right font-mono">{formatNumber(p.views)}</td>
                      <td className="py-3.5 px-3 text-right">
                        <span
                          className={`font-semibold ${
                            isLowAtc ? 'text-rose-600 bg-rose-50 px-1.5 py-0.5 rounded' : 'text-slate-900'
                          }`}
                        >
                          {formatPercent(p.atc_rate, 2)}
                        </span>
                      </td>
                      <td className="py-3.5 px-3 text-right font-mono">{formatNumber(p.purchases)}</td>
                      <td className="py-3.5 px-4 text-right font-semibold text-slate-900 font-mono">
                        {formatCurrency(p.revenue)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
