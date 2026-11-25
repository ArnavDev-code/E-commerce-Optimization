import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../api/client';
import { ConnectedStore } from '../types';
import {
  Plug,
  Store,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Shield,
  Layers,
  Trash2,
  ArrowRight,
  Database,
  Radio,
} from 'lucide-react';

export const Integrations: React.FC = () => {
  const [searchParams] = useSearchParams();
  const [store, setStore] = useState<ConnectedStore | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [showConnectModal, setShowConnectModal] = useState(false);
  const [shopInput, setShopInput] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const fetchStatus = async () => {
    setLoading(true);
    try {
      const data = await api.get<ConnectedStore>('/shopify/status');
      setStore(data);
    } catch (err: any) {
      console.error('Error loading store status', err);
      setStore(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    if (searchParams.get('connected') === 'true') {
      setSuccessMsg('Shopify store connected successfully! Initial synchronization is underway.');
    }
  }, [searchParams]);

  const handleConnectOAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!shopInput.trim()) return;

    setConnecting(true);
    setError(null);
    try {
      const res = await api.post<{ authorization_url: string; shop: string }>(
        '/shopify/oauth/authorize',
        { shop: shopInput }
      );
      // Redirect merchant to Shopify OAuth consent screen
      window.location.href = res.authorization_url;
    } catch (err: any) {
      setError(err.message || 'Failed to initiate Shopify OAuth');
      setConnecting(false);
    }
  };

  const handleTriggerSync = async () => {
    setSyncing(true);
    setError(null);
    setSuccessMsg(null);
    try {
      await api.post('/shopify/sync');
      setSuccessMsg('Store catalog, inventory, and orders synchronized successfully.');
      await fetchStatus();
    } catch (err: any) {
      setError(err.message || 'Synchronization failed');
      await fetchStatus();
    } finally {
      setSyncing(false);
    }
  };

  const handleDisconnect = async () => {
    if (!window.confirm('Are you sure you want to disconnect this store? Offline API access will be revoked.')) {
      return;
    }
    try {
      await api.post('/shopify/disconnect');
      setSuccessMsg('Store disconnected successfully.');
      await fetchStatus();
    } catch (err: any) {
      setError(err.message || 'Failed to disconnect store');
    }
  };

  const scopesList = store?.scopes ? store.scopes.split(',') : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2.5">
          <Plug className="w-6 h-6 text-indigo-600" />
          Store & Analytics Integrations
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Connect your live Shopify merchant store, Web Pixels, and Google Analytics 4 for automated telemetry.
        </p>
      </div>

      {/* Notifications */}
      {successMsg && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center gap-3 text-xs text-emerald-800 font-medium">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}

      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl flex items-center gap-3 text-xs text-rose-800 font-medium">
          <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Main Shopify Card */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-6 border-b border-slate-100 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-start gap-4">
            <div className="p-3 bg-emerald-500/10 rounded-xl text-emerald-600 border border-emerald-500/20">
              <Store className="w-7 h-7" />
            </div>
            <div>
              <div className="flex items-center gap-2.5">
                <h2 className="text-lg font-bold text-slate-900">Shopify Admin GraphQL</h2>
                <span className="text-[10px] bg-slate-100 text-slate-600 font-bold px-2 py-0.5 rounded-full border border-slate-200">
                  API v2026-10
                </span>
                {store?.is_active ? (
                  <span className="text-[10px] bg-emerald-100 text-emerald-800 font-bold px-2.5 py-0.5 rounded-full flex items-center gap-1 border border-emerald-200">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                    ACTIVE
                  </span>
                ) : (
                  <span className="text-[10px] bg-slate-100 text-slate-500 font-bold px-2.5 py-0.5 rounded-full">
                    DISCONNECTED
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-500 mt-1">
                Ingests live catalog items, product variants, inventory quantities by location, and 60-day historical orders.
              </p>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-2">
            {store?.is_active ? (
              <>
                <button
                  onClick={handleTriggerSync}
                  disabled={syncing}
                  className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-4 py-2 rounded-lg shadow-sm transition disabled:opacity-50"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${syncing ? 'animate-spin' : ''}`} />
                  {syncing ? 'Synchronizing...' : 'Sync Now'}
                </button>
                <button
                  onClick={handleDisconnect}
                  className="inline-flex items-center gap-1.5 border border-slate-200 text-slate-600 hover:bg-rose-50 hover:text-rose-600 text-xs font-semibold px-3 py-2 rounded-lg transition"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  <span>Disconnect</span>
                </button>
              </>
            ) : (
              <button
                onClick={() => setShowConnectModal(true)}
                className="inline-flex items-center gap-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold px-4 py-2 rounded-lg shadow-sm transition"
              >
                <Store className="w-3.5 h-3.5" />
                <span>Connect Shopify Store</span>
              </button>
            )}
          </div>
        </div>

        {/* Store Metadata & Sync Details */}
        {loading ? (
          <div className="p-8 text-center text-xs text-slate-400">Loading store credentials and status...</div>
        ) : store && store.is_active ? (
          <div className="p-6 space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg">
                <span className="text-[10px] uppercase font-bold text-slate-500 block">Connected Domain</span>
                <span className="text-sm font-bold text-slate-800 font-mono mt-0.5 block truncate">
                  {store.shop_domain}
                </span>
                <span className="text-[10px] text-slate-400 mt-1 block">Platform: {store.platform}</span>
              </div>

              <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg">
                <span className="text-[10px] uppercase font-bold text-slate-500 block">Synchronization State</span>
                <span
                  className={`text-sm font-bold mt-0.5 block capitalize ${
                    store.sync_status === 'success'
                      ? 'text-emerald-600'
                      : store.sync_status === 'syncing'
                      ? 'text-blue-600'
                      : store.sync_status === 'failed'
                      ? 'text-rose-600'
                      : 'text-slate-700'
                  }`}
                >
                  {store.sync_status}
                </span>
                <span className="text-[10px] text-slate-400 mt-1 block">
                  {store.last_sync_at
                    ? `Last synced: ${new Date(store.last_sync_at).toLocaleTimeString()}`
                    : 'Initial sync pending'}
                </span>
              </div>

              <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg">
                <span className="text-[10px] uppercase font-bold text-slate-500 block">Security & Storage</span>
                <span className="text-sm font-bold text-emerald-700 mt-0.5 flex items-center gap-1.5">
                  <Shield className="w-3.5 h-3.5" /> AES-256 Encrypted
                </span>
                <span className="text-[10px] text-slate-400 mt-1 block">Offline Token Stored at Rest</span>
              </div>

              <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg">
                <span className="text-[10px] uppercase font-bold text-slate-500 block">Data Mode</span>
                <span className="text-sm font-bold text-indigo-700 mt-0.5 flex items-center gap-1.5 uppercase">
                  <Database className="w-3.5 h-3.5" /> {store.data_source || 'shopify'}
                </span>
                <span className="text-[10px] text-slate-400 mt-1 block">Live Merchant Production</span>
              </div>
            </div>

            {/* Granted OAuth Scopes */}
            {scopesList.length > 0 && (
              <div className="space-y-2">
                <span className="text-xs font-bold text-slate-700 uppercase tracking-wider block">
                  Granted Shopify OAuth Scopes
                </span>
                <div className="flex flex-wrap gap-2">
                  {scopesList.map((scope, idx) => (
                    <span
                      key={idx}
                      className="px-2.5 py-1 bg-slate-100 text-slate-700 text-xs font-mono rounded-md border border-slate-200"
                    >
                      {scope.trim()}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Recent Sync Audit History */}
            {store.recent_sync_logs && store.recent_sync_logs.length > 0 && (
              <div className="space-y-3">
                <span className="text-xs font-bold text-slate-800 uppercase tracking-wider block">
                  Recent Sync Audit History
                </span>
                <div className="overflow-x-auto border border-slate-200 rounded-lg">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-200">
                        <th className="py-2 px-3">Sync Type</th>
                        <th className="py-2 px-3">Records Synced</th>
                        <th className="py-2 px-3">Status</th>
                        <th className="py-2 px-3">Started At</th>
                        <th className="py-2 px-3">Completed At</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 font-medium text-slate-700">
                      {store.recent_sync_logs.map((log) => (
                        <tr key={log.id} className="hover:bg-slate-50/60">
                          <td className="py-2.5 px-3 font-mono text-slate-900">{log.sync_type}</td>
                          <td className="py-2.5 px-3 font-mono font-bold text-slate-800">
                            {log.records_synced.toLocaleString()}
                          </td>
                          <td className="py-2.5 px-3">
                            <span
                              className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                                log.status === 'completed'
                                  ? 'bg-emerald-100 text-emerald-800'
                                  : log.status === 'failed'
                                  ? 'bg-rose-100 text-rose-800'
                                  : 'bg-blue-100 text-blue-800'
                              }`}
                            >
                              {log.status}
                            </span>
                          </td>
                          <td className="py-2.5 px-3 text-slate-500 font-mono text-[11px]">
                            {new Date(log.started_at).toLocaleString()}
                          </td>
                          <td className="py-2.5 px-3 text-slate-500 font-mono text-[11px]">
                            {log.completed_at ? new Date(log.completed_at).toLocaleString() : '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="p-8 text-center space-y-3">
            <Store className="w-10 h-10 text-slate-300 mx-auto" />
            <div className="max-w-md mx-auto">
              <h3 className="text-sm font-bold text-slate-800">No Shopify store currently connected</h3>
              <p className="text-xs text-slate-500 mt-1">
                Connect your development or live store to unlock automated product revenue tracking, accurate COGS analysis, and real conversion leak diagnosis.
              </p>
            </div>
            <button
              onClick={() => setShowConnectModal(true)}
              className="inline-flex items-center gap-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold px-4 py-2 rounded-lg shadow-sm transition"
            >
              <Store className="w-3.5 h-3.5" />
              <span>Connect Shopify Store Now</span>
            </button>
          </div>
        )}
      </div>

      {/* Upcoming Integrations Showcase (GA4 & Web Pixels) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Web Pixels */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-3 opacity-90">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="p-2 bg-purple-50 text-purple-600 rounded-lg border border-purple-200">
                <Radio className="w-5 h-5" />
              </div>
              <h3 className="text-sm font-bold text-slate-900">Shopify Web Pixel Extension</h3>
            </div>
            <span className="text-[10px] font-bold uppercase bg-slate-100 text-slate-500 px-2 py-0.5 rounded-full">
              Phase 4B
            </span>
          </div>
          <p className="text-xs text-slate-500 leading-relaxed">
            Privacy-first client-side event tracking across the customer journey: Product Views, Add-to-Cart events, Cart Drawer views, and Checkout progression.
          </p>
        </div>

        {/* GA4 */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-3 opacity-90">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="p-2 bg-amber-50 text-amber-600 rounded-lg border border-amber-200">
                <Layers className="w-5 h-5" />
              </div>
              <h3 className="text-sm font-bold text-slate-900">Google Analytics 4 Data API</h3>
            </div>
            <span className="text-[10px] font-bold uppercase bg-slate-100 text-slate-500 px-2 py-0.5 rounded-full">
              Phase 4C
            </span>
          </div>
          <p className="text-xs text-slate-500 leading-relaxed">
            Cross-references store traffic sources, bounce rates, and landing page sessions with product-level revenue dropoffs for diagnostic context.
          </p>
        </div>
      </div>

      {/* Connect Modal */}
      {showConnectModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full shadow-2xl border border-slate-200 overflow-hidden">
            <div className="p-6 border-b border-slate-100">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-emerald-50 text-emerald-600 rounded-xl border border-emerald-100">
                  <Store className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-900">Connect Your Shopify Store</h3>
                  <p className="text-xs text-slate-500 mt-0.5">Enter your store's myshopify.com domain to begin OAuth</p>
                </div>
              </div>
            </div>

            <form onSubmit={handleConnectOAuth} className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                  Shopify Store Domain
                </label>
                <div className="relative">
                  <input
                    type="text"
                    value={shopInput}
                    onChange={(e) => setShopInput(e.target.value)}
                    placeholder="my-boutique.myshopify.com"
                    required
                    className="w-full text-xs font-mono p-3 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  />
                </div>
                <span className="text-[11px] text-slate-400 mt-1.5 block">
                  Example: <code>your-store-name.myshopify.com</code> (or just <code>your-store-name</code>)
                </span>
              </div>

              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs text-slate-600 space-y-1">
                <span className="font-semibold block text-slate-700">What happens next:</span>
                <p>1. You will be redirected to Shopify's secure authorization page.</p>
                <p>2. Approve the read-only scopes (products, inventory, orders).</p>
                <p>3. FunnelLeak securely encrypts access tokens at rest and triggers initial sync.</p>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowConnectModal(false)}
                  className="px-4 py-2 border border-slate-200 rounded-lg text-xs font-semibold text-slate-600 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={connecting || !shopInput.trim()}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold shadow-sm transition disabled:opacity-50 flex items-center gap-1.5"
                >
                  {connecting ? 'Redirecting...' : 'Authorize on Shopify'}
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
