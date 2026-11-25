import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { DetectedLeak, AIDiagnosis } from '../types';
import { getSeverityBadge } from '../utils/format';
import {
  AlertTriangle,
  Play,
  RefreshCw,
  ChevronRight,
  CheckCircle2,
  ShieldAlert,
  Brain,
  HelpCircle,
  Search,
  Sparkles,
  ArrowRight,
  Info,
} from 'lucide-react';

export const Leaks: React.FC = () => {
  const navigate = useNavigate();
  const [leaks, setLeaks] = useState<DetectedLeak[]>([]);
  const [loading, setLoading] = useState(true);
  const [detecting, setDetecting] = useState(false);
  const [selectedLeak, setSelectedLeak] = useState<DetectedLeak | null>(null);
  const [severityFilter, setSeverityFilter] = useState('all');

  // Diagnosis State
  const [diagnosis, setDiagnosis] = useState<AIDiagnosis | null>(null);
  const [loadingDiagnosis, setLoadingDiagnosis] = useState(false);
  const [generatingRecs, setGeneratingRecs] = useState(false);

  const fetchLeaks = async () => {
    setLoading(true);
    try {
      const data = await api.get<DetectedLeak[]>('/leaks');
      setLeaks(data);
      if (data.length > 0 && !selectedLeak) {
        setSelectedLeak(data[0] ?? null);
      }
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLeaks();
  }, []);

  // Fetch or load diagnosis whenever selected leak changes
  useEffect(() => {
    if (!selectedLeak) {
      setDiagnosis(null);
      return;
    }
    const fetchDiagnosis = async () => {
      setLoadingDiagnosis(true);
      try {
        const diag = await api.get<AIDiagnosis>(`/leaks/${selectedLeak.id}/diagnosis`);
        setDiagnosis(diag);
      } catch (err) {
        console.error('Failed to load diagnosis for leak', err);
        setDiagnosis(null);
      } finally {
        setLoadingDiagnosis(false);
      }
    };
    fetchDiagnosis();
  }, [selectedLeak?.id]);

  const handleRunDetect = async () => {
    setDetecting(true);
    try {
      const refreshed = await api.post<DetectedLeak[]>('/leaks/detect', {
        days: 30,
        min_sample_size: 40,
      });
      setLeaks(refreshed);
      if (refreshed.length > 0) {
        setSelectedLeak(refreshed[0] ?? null);
      }
    } catch (err: any) {
      alert(err.message || 'Error running leak detection');
    } finally {
      setDetecting(false);
    }
  };

  const handleDiagnoseNow = async () => {
    if (!selectedLeak) return;
    setLoadingDiagnosis(true);
    try {
      const result = await api.post<AIDiagnosis>(`/leaks/${selectedLeak.id}/diagnose`);
      setDiagnosis(result);
    } catch (err: any) {
      alert(err.message || 'Error running AI diagnosis');
    } finally {
      setLoadingDiagnosis(false);
    }
  };

  const handleGenerateRecommendations = async () => {
    if (!selectedLeak) return;
    setGeneratingRecs(true);
    try {
      await api.post('/recommendations/generate', { leak_id: selectedLeak.id });
      navigate('/recommendations');
    } catch (err: any) {
      alert(err.message || 'Error generating recommendations');
    } finally {
      setGeneratingRecs(false);
    }
  };

  const filteredLeaks = leaks.filter((l) => {
    if (severityFilter === 'all') return true;
    return l.severity.toLowerCase() === severityFilter.toLowerCase();
  });

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2.5">
            <AlertTriangle className="w-6 h-6 text-rose-600" />
            Revenue & Conversion Leaks
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Deterministic detection of high-traffic dropoffs backed by historical baselines and sample thresholds.
          </p>
        </div>
        <button
          onClick={handleRunDetect}
          disabled={detecting}
          className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-4 py-2.5 rounded-lg shadow-sm transition disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${detecting ? 'animate-spin' : ''}`} />
          {detecting ? 'Analyzing Catalog...' : 'Run Leak Detection Now'}
        </button>
      </div>

      {/* Main Split Layout: Leaks List on Left, Detail & Diagnosis on Right */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Leaks List */}
        <div className="lg:col-span-5 bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="p-4 border-b border-slate-100 flex items-center justify-between">
            <span className="text-xs font-bold text-slate-800 uppercase tracking-wider">
              Detected Leaks ({filteredLeaks.length})
            </span>
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="text-xs border border-slate-200 rounded-md px-2 py-1 bg-white text-slate-600"
            >
              <option value="all">All Severities</option>
              <option value="critical">Critical Only</option>
              <option value="high">High Only</option>
              <option value="medium">Medium Only</option>
            </select>
          </div>

          <div className="divide-y divide-slate-100 max-h-[700px] overflow-y-auto">
            {loading ? (
              <div className="p-8 text-center text-xs text-slate-400">Loading detected leaks...</div>
            ) : filteredLeaks.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-500">No revenue leaks found matching criteria.</div>
            ) : (
              filteredLeaks.map((l) => {
                const badge = getSeverityBadge(l.severity);
                const isSelected = selectedLeak?.id === l.id;

                return (
                  <div
                    key={l.id}
                    onClick={() => setSelectedLeak(l)}
                    className={`p-4 cursor-pointer transition flex items-start justify-between gap-3 ${
                      isSelected
                        ? 'bg-blue-50/70 border-l-4 border-l-blue-600'
                        : 'hover:bg-slate-50/80 border-l-4 border-l-transparent'
                    }`}
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${badge.bg}`}>
                          {badge.text}
                        </span>
                        <span className="text-[10px] font-mono text-slate-400 uppercase">
                          {l.metric_affected.replace(/_/g, ' ')}
                        </span>
                      </div>
                      <h4 className="text-xs font-bold text-slate-900 truncate">
                        {l.product_title || 'Storewide Flow'}
                      </h4>
                      <p className="text-[11px] text-slate-500 line-clamp-2 mt-0.5">{l.reason}</p>
                      <div className="mt-2 flex items-center gap-3 text-[11px]">
                        <span className="text-rose-600 font-bold font-mono">
                          Observed: {Number(l.observed_value).toFixed(2)}%
                        </span>
                        <span className="text-slate-400 font-mono">
                          Baseline: {Number(l.baseline_value).toFixed(2)}%
                        </span>
                        <span className="text-slate-400 text-[10px]">N={l.sample_size}</span>
                      </div>
                    </div>
                    <ChevronRight className="w-4 h-4 text-slate-300 mt-2 shrink-0" />
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right Column: Selected Leak Diagnostic Detail */}
        <div className="lg:col-span-7 bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-6">
          {selectedLeak ? (
            <div className="space-y-6">
              {/* Header */}
              <div className="border-b border-slate-100 pb-5">
                <div className="flex items-center justify-between gap-2">
                  <span
                    className={`text-xs font-bold px-2.5 py-1 rounded-full border ${
                      getSeverityBadge(selectedLeak.severity).bg
                    }`}
                  >
                    {selectedLeak.severity.toUpperCase()} SEVERITY
                  </span>
                  <span className="text-xs text-slate-400">
                    Period: {selectedLeak.period_start} to {selectedLeak.period_end}
                  </span>
                </div>
                <h2 className="text-lg font-bold text-slate-900 mt-3">{selectedLeak.product_title}</h2>
                <p className="text-xs text-slate-600 mt-1 leading-relaxed bg-slate-50 p-3 rounded-lg border border-slate-200/60">
                  {selectedLeak.reason}
                </p>

                {/* Action Bar */}
                <div className="mt-4 flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-slate-100">
                  <div className="flex items-center gap-2">
                    <button
                      onClick={handleDiagnoseNow}
                      disabled={loadingDiagnosis}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 text-xs font-semibold rounded-lg border border-indigo-200 transition disabled:opacity-50"
                    >
                      <Sparkles className={`w-3.5 h-3.5 ${loadingDiagnosis ? 'animate-spin' : ''}`} />
                      {loadingDiagnosis ? 'Diagnosing...' : 'Re-diagnose Leak'}
                    </button>
                    {diagnosis && (
                      <span className="text-[11px] text-slate-500 flex items-center gap-1">
                        Engine: <strong className="text-slate-700 uppercase font-mono">{diagnosis.provider}</strong>
                        {diagnosis.is_fallback && (
                          <span className="text-[10px] bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded border border-slate-200">
                            Deterministic
                          </span>
                        )}
                      </span>
                    )}
                  </div>

                  <button
                    onClick={handleGenerateRecommendations}
                    disabled={generatingRecs}
                    className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg shadow-sm transition disabled:opacity-50"
                  >
                    <span>Generate CRO Recommendations</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {/* Metric Comparison Cards */}
              <div className="grid grid-cols-3 gap-3">
                <div className="p-3 bg-rose-50 border border-rose-200/80 rounded-lg">
                  <span className="text-[10px] font-bold text-rose-800 uppercase tracking-wider block">
                    Observed Metric
                  </span>
                  <span className="text-lg font-extrabold text-rose-600 font-mono mt-0.5 block">
                    {Number(selectedLeak.observed_value).toFixed(2)}%
                  </span>
                  <span className="text-[10px] text-rose-600/80">Underperforming</span>
                </div>

                <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
                  <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
                    Target Baseline
                  </span>
                  <span className="text-lg font-extrabold text-slate-800 font-mono mt-0.5 block">
                    {Number(selectedLeak.baseline_value).toFixed(2)}%
                  </span>
                  <span className="text-[10px] text-slate-400">Store / Category Benchmark</span>
                </div>

                <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
                  <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
                    Sample Evidence
                  </span>
                  <span className="text-lg font-extrabold text-slate-800 font-mono mt-0.5 block">
                    {selectedLeak.sample_size.toLocaleString()}
                  </span>
                  <span className="text-[10px] text-emerald-600 font-semibold flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3" /> Sample Sufficient
                  </span>
                </div>
              </div>

              {/* AI Diagnosis Breakdown */}
              {loadingDiagnosis ? (
                <div className="p-12 text-center text-xs text-slate-500 flex flex-col items-center justify-center gap-2">
                  <RefreshCw className="w-5 h-5 animate-spin text-blue-600" />
                  <span>Synthesizing observations and diagnostic hypotheses...</span>
                </div>
              ) : diagnosis ? (
                <div className="space-y-5">
                  {/* Summary Callout */}
                  <div className="p-4 rounded-lg bg-indigo-50/50 border border-indigo-100">
                    <div className="flex items-center gap-2 text-xs font-bold text-indigo-950 uppercase tracking-wider mb-1">
                      <Brain className="w-4 h-4 text-indigo-600" />
                      Diagnostic Overview
                    </div>
                    <p className="text-xs text-indigo-900 leading-relaxed font-medium">
                      {diagnosis.issue_summary}
                    </p>
                  </div>

                  {/* Facts vs Hypotheses Dual View */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Verified Facts */}
                    <div className="p-4 rounded-lg border border-emerald-200 bg-emerald-50/20 space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="flex items-center gap-1.5 text-xs font-bold text-emerald-900 uppercase tracking-wider">
                          <ShieldAlert className="w-3.5 h-3.5 text-emerald-600" />
                          Verified Facts
                        </span>
                        <span className="text-[10px] bg-emerald-100 text-emerald-800 font-bold px-2 py-0.5 rounded-full">
                          Deterministic
                        </span>
                      </div>
                      <div className="space-y-2.5">
                        {diagnosis.evidence?.map((obs: any, idx: number) => (
                          <div key={idx} className="p-2.5 bg-white rounded border border-emerald-100 text-xs">
                            <div className="font-semibold text-slate-800 flex justify-between">
                              <span>{obs.metric || obs.fact || 'Metric'}</span>
                              <span className="font-mono text-emerald-700">{obs.observed_value}</span>
                            </div>
                            {obs.context && (
                              <p className="text-[11px] text-slate-500 mt-1 leading-normal">{obs.context}</p>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Hypotheses */}
                    <div className="p-4 rounded-lg border border-amber-200 bg-amber-50/20 space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="flex items-center gap-1.5 text-xs font-bold text-amber-900 uppercase tracking-wider">
                          <HelpCircle className="w-3.5 h-3.5 text-amber-600" />
                          Hypotheses to Validate
                        </span>
                        <span className="text-[10px] bg-amber-100 text-amber-800 font-bold px-2 py-0.5 rounded-full">
                          Requires Validation
                        </span>
                      </div>
                      <div className="space-y-2.5">
                        {diagnosis.possible_explanations?.map((hyp: any, idx: number) => (
                          <div key={idx} className="p-2.5 bg-white rounded border border-amber-100 text-xs">
                            <div className="flex items-center justify-between gap-2 mb-1">
                              <span className="font-semibold text-slate-800 leading-tight">
                                {hyp.hypothesis}
                              </span>
                              <span
                                className={`text-[9px] font-bold uppercase px-1.5 py-0.5 rounded shrink-0 ${
                                  hyp.likelihood === 'high'
                                    ? 'bg-rose-100 text-rose-800'
                                    : 'bg-amber-100 text-amber-800'
                                }`}
                              >
                                {hyp.likelihood}
                              </span>
                            </div>
                            {hyp.supporting_signals?.length > 0 && (
                              <ul className="text-[10px] text-slate-500 space-y-0.5 pl-3 list-disc mt-1">
                                {hyp.supporting_signals.map((sig: string, sIdx: number) => (
                                  <li key={sIdx}>{sig}</li>
                                ))}
                              </ul>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Missing Telemetry & Next Steps */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Missing Information */}
                    {diagnosis.missing_information && diagnosis.missing_information.length > 0 && (
                      <div className="p-4 rounded-lg border border-slate-200 bg-slate-50/60 space-y-2">
                        <div className="flex items-center gap-1.5 text-xs font-bold text-slate-700 uppercase tracking-wider">
                          <Info className="w-3.5 h-3.5 text-slate-500" />
                          Missing Telemetry for Stronger Proof
                        </div>
                        <ul className="text-xs text-slate-600 space-y-1.5 pl-4 list-disc">
                          {diagnosis.missing_information.map((item, idx) => (
                            <li key={idx}>{item}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Recommended Next Investigation */}
                    {diagnosis.recommended_investigation && diagnosis.recommended_investigation.length > 0 && (
                      <div className="p-4 rounded-lg border border-blue-200 bg-blue-50/40 space-y-2">
                        <div className="flex items-center gap-1.5 text-xs font-bold text-blue-900 uppercase tracking-wider">
                          <Search className="w-3.5 h-3.5 text-blue-600" />
                          Recommended Next Investigation
                        </div>
                        <ul className="text-xs text-slate-700 space-y-1.5 pl-4 list-disc">
                          {diagnosis.recommended_investigation.map((item, idx) => (
                            <li key={idx}>{item}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>

                  {/* Recommended Actions */}
                  {diagnosis.recommended_actions && diagnosis.recommended_actions.length > 0 && (
                    <div className="p-4 rounded-lg border border-slate-200 bg-white space-y-2">
                      <div className="flex items-center gap-1.5 text-xs font-bold text-slate-900 uppercase tracking-wider">
                        <Play className="w-3.5 h-3.5 text-blue-600" />
                        Immediate High-Probability Interventions
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-2">
                        {diagnosis.recommended_actions.map((act: any, idx: number) => {
                          const actionText = typeof act === 'string' ? act : act.action;
                          return (
                            <div key={idx} className="p-2.5 bg-slate-50 border border-slate-200/80 rounded text-xs text-slate-700 leading-relaxed flex items-start gap-2">
                              <span className="w-4 h-4 rounded-full bg-blue-100 text-blue-700 text-[10px] font-bold flex items-center justify-center shrink-0 mt-0.5">
                                {idx + 1}
                              </span>
                              <span>{actionText}</span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="p-8 text-center border border-dashed border-slate-300 rounded-lg space-y-3">
                  <Brain className="w-8 h-8 text-slate-400 mx-auto" />
                  <p className="text-xs text-slate-500">
                    No diagnosis has been saved for this leak yet.
                  </p>
                  <button
                    onClick={handleDiagnoseNow}
                    disabled={loadingDiagnosis}
                    className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-4 py-2 rounded-lg shadow-sm transition"
                  >
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>Run AI Diagnosis Now</span>
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="p-12 text-center text-xs text-slate-400">Select a revenue leak on the left to inspect.</div>
          )}
        </div>
      </div>
    </div>
  );
};
