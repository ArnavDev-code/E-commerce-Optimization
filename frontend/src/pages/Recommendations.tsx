import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import { Recommendation } from '../types';
import { formatCurrency } from '../utils/format';
import {
  Lightbulb,
  Sparkles,
  CheckCircle2,
  XCircle,
  Clock,
  TrendingUp,
  Package,
  ChevronDown,
  ChevronUp,
  Sliders,
} from 'lucide-react';

export const Recommendations: React.FC = () => {
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [priorityFilter, setPriorityFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [stageFilter, setStageFilter] = useState('all');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Note editing state
  const [editingNoteId, setEditingNoteId] = useState<string | null>(null);
  const [noteText, setNoteText] = useState('');

  const fetchRecommendations = async () => {
    setLoading(true);
    try {
      const data = await api.get<Recommendation[]>('/recommendations');
      setRecommendations(data);
    } catch (err) {
      console.error('Failed to load recommendations', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRecommendations();
  }, []);

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const refreshed = await api.post<Recommendation[]>('/recommendations/generate', {});
      setRecommendations(refreshed);
    } catch (err: any) {
      alert(err.message || 'Error generating recommendations');
    } finally {
      setGenerating(false);
    }
  };

  const handleStatusUpdate = async (id: string, newStatus: string) => {
    try {
      const updated = await api.patch<Recommendation>(`/recommendations/${id}/status`, {
        status: newStatus,
      });
      setRecommendations((prev) =>
        prev.map((r) => (r.id === id ? updated : r))
      );
    } catch (err: any) {
      alert(err.message || 'Error updating recommendation status');
    }
  };

  const handleSaveNotes = async (id: string) => {
    try {
      const updated = await api.patch<Recommendation>(`/recommendations/${id}/status`, {
        status: recommendations.find((r) => r.id === id)?.status || 'new',
        merchant_notes: noteText,
      });
      setRecommendations((prev) =>
        prev.map((r) => (r.id === id ? updated : r))
      );
      setEditingNoteId(null);
    } catch (err: any) {
      alert(err.message || 'Error saving notes');
    }
  };

  // Filter recommendations
  const filtered = recommendations.filter((r) => {
    if (priorityFilter !== 'all' && r.priority.toLowerCase() !== priorityFilter.toLowerCase()) {
      return false;
    }
    if (statusFilter !== 'all') {
      const s = r.status.toLowerCase();
      if (statusFilter === 'accepted' && s !== 'accepted' && s !== 'approved') return false;
      if (statusFilter === 'new' && s !== 'new' && s !== 'pending') return false;
      if (statusFilter !== 'accepted' && statusFilter !== 'new' && s !== statusFilter) return false;
    }
    if (stageFilter !== 'all' && r.target_stage.toLowerCase() !== stageFilter.toLowerCase()) {
      return false;
    }
    return true;
  });

  // KPI calculations
  const highPriorityCount = recommendations.filter((r) => r.priority === 'high').length;
  const acceptedCount = recommendations.filter((r) => r.status === 'accepted' || r.status === 'approved' || r.status === 'in_progress').length;
  const totalPotentialProfit = recommendations.reduce(
    (sum, r) => sum + (Number(r.potential_impact_estimate) || 0),
    0
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2.5">
            <Lightbulb className="w-6 h-6 text-amber-500" />
            AI CRO Recommendations
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Prioritized by conversion lift, statistical evidence quality, product margins, and feasibility.
          </p>
        </div>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-4 py-2.5 rounded-lg shadow-sm transition disabled:opacity-50"
        >
          <Sparkles className={`w-3.5 h-3.5 ${generating ? 'animate-spin' : ''}`} />
          {generating ? 'Evaluating Store Leaks...' : 'Regenerate Recommendations'}
        </button>
      </div>

      {/* KPI Overview Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block">
            Total Recommendations
          </span>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-2xl font-extrabold text-slate-900">{recommendations.length}</span>
            <span className="text-xs text-slate-400">active interventions</span>
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-rose-200/80 shadow-sm bg-rose-50/20">
          <span className="text-xs font-semibold text-rose-800 uppercase tracking-wider block">
            High Priority Interventions
          </span>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-2xl font-extrabold text-rose-600">{highPriorityCount}</span>
            <span className="text-xs text-rose-600/80">score &ge; 70</span>
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-emerald-200/80 shadow-sm bg-emerald-50/20">
          <span className="text-xs font-semibold text-emerald-800 uppercase tracking-wider block">
            Est. Monthly Profit Recovery
          </span>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-2xl font-extrabold text-emerald-600 font-mono">
              {formatCurrency(totalPotentialProfit)}
            </span>
            <span className="text-[11px] text-emerald-700">conservative estimate</span>
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-blue-200/80 shadow-sm bg-blue-50/20">
          <span className="text-xs font-semibold text-blue-800 uppercase tracking-wider block">
            Merchant Accepted / Active
          </span>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-2xl font-extrabold text-blue-700">{acceptedCount}</span>
            <span className="text-xs text-blue-600/80">in experiment pipeline</span>
          </div>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <Sliders className="w-4 h-4 text-slate-400" />
            <span className="text-xs font-semibold text-slate-600">Filters:</span>
          </div>

          <select
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value)}
            className="text-xs border border-slate-200 rounded-lg px-2.5 py-1.5 bg-slate-50 text-slate-700 focus:bg-white"
          >
            <option value="all">All Priorities</option>
            <option value="high">High Priority (&ge;70)</option>
            <option value="medium">Medium Priority (40-69)</option>
            <option value="low">Low Priority (&lt;40)</option>
          </select>

          <select
            value={stageFilter}
            onChange={(e) => setStageFilter(e.target.value)}
            className="text-xs border border-slate-200 rounded-lg px-2.5 py-1.5 bg-slate-50 text-slate-700 focus:bg-white"
          >
            <option value="all">All Funnel Stages</option>
            <option value="product_page">Product Page</option>
            <option value="cart">Cart Drawer / Page</option>
            <option value="checkout">Checkout Step</option>
            <option value="post_purchase">Post-Purchase</option>
          </select>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-xs border border-slate-200 rounded-lg px-2.5 py-1.5 bg-slate-50 text-slate-700 focus:bg-white"
          >
            <option value="all">All Statuses</option>
            <option value="new">New / Pending</option>
            <option value="accepted">Accepted / Approved</option>
            <option value="in_progress">In Progress</option>
            <option value="completed">Completed</option>
            <option value="rejected">Rejected</option>
          </select>
        </div>

        <span className="text-xs text-slate-500">
          Showing <strong>{filtered.length}</strong> of {recommendations.length} recommendations
        </span>
      </div>

      {/* Recommendations List */}
      <div className="space-y-4">
        {loading ? (
          <div className="bg-white p-12 text-center rounded-xl border border-slate-200 text-xs text-slate-400">
            Loading recommendations...
          </div>
        ) : filtered.length === 0 ? (
          <div className="bg-white p-12 text-center rounded-xl border border-slate-200 space-y-3">
            <Lightbulb className="w-8 h-8 text-slate-300 mx-auto" />
            <p className="text-xs text-slate-500">
              No recommendations match the selected filters.
            </p>
            <button
              onClick={handleGenerate}
              className="text-xs text-blue-600 font-semibold hover:underline"
            >
              Click here to evaluate store leaks and generate recommendations.
            </button>
          </div>
        ) : (
          filtered.map((rec) => {
            const isExpanded = expandedId === rec.id;
            const score = rec.priority_score ? Number(rec.priority_score) : 50;
            const breakdown = rec.priority_breakdown;

            return (
              <div
                key={rec.id}
                className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden transition hover:border-slate-300"
              >
                {/* Main Card Header */}
                <div className="p-5">
                  <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
                    {/* Left: Priority Badge & Title */}
                    <div className="space-y-2 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        {/* Score Pill */}
                        <div
                          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold border ${
                            score >= 70
                              ? 'bg-rose-50 border-rose-200 text-rose-700'
                              : score >= 40
                              ? 'bg-amber-50 border-amber-200 text-amber-700'
                              : 'bg-slate-50 border-slate-200 text-slate-600'
                          }`}
                        >
                          <TrendingUp className="w-3.5 h-3.5" />
                          <span>Priority Score: {score.toFixed(0)}/100</span>
                        </div>

                        {/* Stage Badge */}
                        <span className="text-[10px] font-bold uppercase tracking-wider bg-slate-100 text-slate-600 px-2.5 py-1 rounded-full border border-slate-200">
                          {rec.target_stage.replace(/_/g, ' ')}
                        </span>

                        {/* Status Badge */}
                        <span
                          className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full ${
                            rec.status === 'accepted' || rec.status === 'approved'
                              ? 'bg-emerald-100 text-emerald-800'
                              : rec.status === 'rejected'
                              ? 'bg-slate-100 text-slate-500 line-through'
                              : rec.status === 'in_progress'
                              ? 'bg-blue-100 text-blue-800'
                              : 'bg-indigo-50 text-indigo-700'
                          }`}
                        >
                          {rec.status}
                        </span>
                      </div>

                      <h3 className="text-base font-bold text-slate-900 leading-snug">
                        {rec.title}
                      </h3>

                      {rec.product_title && (
                        <div className="flex items-center gap-2 text-xs text-slate-500">
                          <Package className="w-3.5 h-3.5 text-slate-400" />
                          <span>Target: <strong className="text-slate-700">{rec.product_title}</strong></span>
                          {rec.product_price && (
                            <span className="font-mono text-slate-600">
                              (${Number(rec.product_price).toFixed(2)})
                            </span>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Right: Profit Impact & Action Workflow */}
                    <div className="flex flex-col sm:items-end justify-between gap-3 shrink-0">
                      {rec.potential_impact_estimate !== null && rec.potential_impact_estimate !== undefined ? (
                        <div className="sm:text-right">
                          <span className="text-[10px] uppercase font-bold text-emerald-700 tracking-wider block">
                            Est. Monthly Profit Lift
                          </span>
                          <span className="text-lg font-extrabold text-emerald-600 font-mono">
                            +{formatCurrency(Number(rec.potential_impact_estimate))}
                          </span>
                        </div>
                      ) : (
                        <div className="sm:text-right bg-amber-50 border border-amber-200 rounded px-2.5 py-1">
                          <span className="text-[10px] font-semibold text-amber-800 block">
                            Profit estimate unavailable
                          </span>
                          <Link
                            to="/products"
                            className="text-[10px] text-blue-600 hover:underline font-medium"
                          >
                            Set COGS in Products tab &rarr;
                          </Link>
                        </div>
                      )}

                      {/* Status Action Buttons */}
                      <div className="flex items-center gap-2">
                        {rec.status === 'new' && (
                          <>
                            <button
                              onClick={() => handleStatusUpdate(rec.id, 'accepted')}
                              className="inline-flex items-center gap-1 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold px-3 py-1.5 rounded-lg transition"
                            >
                              <CheckCircle2 className="w-3.5 h-3.5" />
                              <span>Accept</span>
                            </button>
                            <button
                              onClick={() => handleStatusUpdate(rec.id, 'rejected')}
                              className="inline-flex items-center gap-1 bg-slate-100 hover:bg-slate-200 text-slate-600 text-xs font-semibold px-2.5 py-1.5 rounded-lg transition"
                            >
                              <XCircle className="w-3.5 h-3.5" />
                              <span>Reject</span>
                            </button>
                          </>
                        )}

                        {rec.status === 'accepted' && (
                          <button
                            onClick={() => handleStatusUpdate(rec.id, 'in_progress')}
                            className="inline-flex items-center gap-1 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-3 py-1.5 rounded-lg transition"
                          >
                            <Clock className="w-3.5 h-3.5" />
                            <span>Mark In Progress</span>
                          </button>
                        )}

                        {rec.status === 'in_progress' && (
                          <button
                            onClick={() => handleStatusUpdate(rec.id, 'completed')}
                            className="inline-flex items-center gap-1 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold px-3 py-1.5 rounded-lg transition"
                          >
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            <span>Mark Completed</span>
                          </button>
                        )}

                        <button
                          onClick={() => setExpandedId(isExpanded ? null : rec.id)}
                          className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition"
                          title="Toggle details"
                        >
                          {isExpanded ? (
                            <ChevronUp className="w-4 h-4" />
                          ) : (
                            <ChevronDown className="w-4 h-4" />
                          )}
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Core Action & Reason Preview */}
                  <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                    <div className="p-3 bg-slate-50 border border-slate-200/80 rounded-lg">
                      <span className="font-bold text-slate-800 uppercase tracking-wider text-[10px] block mb-1">
                        Suggested Intervention
                      </span>
                      <p className="text-slate-700 leading-relaxed">{rec.suggested_action}</p>
                    </div>

                    <div className="p-3 bg-slate-50 border border-slate-200/80 rounded-lg">
                      <span className="font-bold text-slate-800 uppercase tracking-wider text-[10px] block mb-1">
                        Business Justification
                      </span>
                      <p className="text-slate-700 leading-relaxed">{rec.business_reason}</p>
                    </div>
                  </div>
                </div>

                {/* Expanded Scoring Breakdown and Diagnostics */}
                {isExpanded && (
                  <div className="border-t border-slate-100 bg-slate-50/50 p-5 space-y-5">
                    {/* Multi-Factor Score Breakdown Bars */}
                    {breakdown && (
                      <div className="space-y-3">
                        <span className="text-xs font-bold text-slate-800 uppercase tracking-wider block">
                          Transparent 4-Factor Prioritization Model
                        </span>
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                          {/* Impact */}
                          <div className="bg-white p-3 rounded-lg border border-slate-200">
                            <div className="flex justify-between text-xs mb-1">
                              <span className="text-slate-600 font-medium">Impact (35%)</span>
                              <span className="font-bold text-slate-900 font-mono">
                                {breakdown.impact_score}/100
                              </span>
                            </div>
                            <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                              <div
                                className="bg-rose-500 h-full rounded-full"
                                style={{ width: `${breakdown.impact_score}%` }}
                              />
                            </div>
                            <span className="text-[10px] text-slate-400 mt-1 block">
                              Based on leak severity & traffic volume
                            </span>
                          </div>

                          {/* Confidence */}
                          <div className="bg-white p-3 rounded-lg border border-slate-200">
                            <div className="flex justify-between text-xs mb-1">
                              <span className="text-slate-600 font-medium">Confidence (25%)</span>
                              <span className="font-bold text-slate-900 font-mono">
                                {breakdown.confidence_score}/100
                              </span>
                            </div>
                            <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                              <div
                                className="bg-blue-500 h-full rounded-full"
                                style={{ width: `${breakdown.confidence_score}%` }}
                              />
                            </div>
                            <span className="text-[10px] text-slate-400 mt-1 block">
                              Statistical test & sample threshold
                            </span>
                          </div>

                          {/* Margin & Stock */}
                          <div className="bg-white p-3 rounded-lg border border-slate-200">
                            <div className="flex justify-between text-xs mb-1">
                              <span className="text-slate-600 font-medium">Margin & Stock (20%)</span>
                              <span className="font-bold text-slate-900 font-mono">
                                {breakdown.margin_stock_score}/100
                              </span>
                            </div>
                            <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                              <div
                                className="bg-emerald-500 h-full rounded-full"
                                style={{ width: `${breakdown.margin_stock_score}%` }}
                              />
                            </div>
                            <span className="text-[10px] text-slate-400 mt-1 block">
                              Stock: {breakdown.inventory_units} units ({breakdown.cogs_provided ? 'COGS verified' : 'COGS pending'})
                            </span>
                          </div>

                          {/* Feasibility */}
                          <div className="bg-white p-3 rounded-lg border border-slate-200">
                            <div className="flex justify-between text-xs mb-1">
                              <span className="text-slate-600 font-medium">Feasibility (20%)</span>
                              <span className="font-bold text-slate-900 font-mono">
                                {breakdown.feasibility_score}/100
                              </span>
                            </div>
                            <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                              <div
                                className="bg-amber-500 h-full rounded-full"
                                style={{ width: `${breakdown.feasibility_score}%` }}
                              />
                            </div>
                            <span className="text-[10px] text-slate-400 mt-1 block capitalize">
                              Effort: {rec.implementation_effort}
                            </span>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Prerequisites and Caveats */}
                    {rec.risks_or_prerequisites && rec.risks_or_prerequisites.length > 0 && (
                      <div className="p-3 bg-amber-50/50 border border-amber-200 rounded-lg text-xs space-y-1.5">
                        <span className="font-bold text-amber-900 uppercase tracking-wider text-[10px] block">
                          Prerequisites & Operational Notes
                        </span>
                        <ul className="pl-4 list-disc space-y-1 text-amber-800">
                          {rec.risks_or_prerequisites.map((risk, rIdx) => (
                            <li key={rIdx}>{risk}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Merchant Notes Section */}
                    <div className="bg-white p-4 rounded-lg border border-slate-200 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                          Merchant Implementation Notes
                        </span>
                        {editingNoteId !== rec.id && (
                          <button
                            onClick={() => {
                              setEditingNoteId(rec.id);
                              setNoteText(rec.merchant_notes || '');
                            }}
                            className="text-xs text-blue-600 hover:underline font-semibold"
                          >
                            {rec.merchant_notes ? 'Edit Notes' : '+ Add Note'}
                          </button>
                        )}
                      </div>

                      {editingNoteId === rec.id ? (
                        <div className="space-y-2">
                          <textarea
                            value={noteText}
                            onChange={(e) => setNoteText(e.target.value)}
                            placeholder="Add notes for your team (e.g., Assigned to Sarah for next week's sprint)..."
                            className="w-full text-xs p-2.5 border border-slate-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-500"
                            rows={3}
                          />
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => handleSaveNotes(rec.id)}
                              className="px-3 py-1 bg-blue-600 text-white text-xs font-semibold rounded-md hover:bg-blue-700"
                            >
                              Save Note
                            </button>
                            <button
                              onClick={() => setEditingNoteId(null)}
                              className="px-3 py-1 bg-slate-100 text-slate-600 text-xs font-semibold rounded-md hover:bg-slate-200"
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      ) : (
                        <p className="text-xs text-slate-600 italic">
                          {rec.merchant_notes || 'No merchant notes recorded yet.'}
                        </p>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
