import React, { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../api/client';
import { ConnectedStore, GA4ConnectionStatus, GA4PropertiesResponse, GA4AccountSummary } from '../types';
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
  ExternalLink,
  ChevronDown,
  ChevronRight,
  X,
} from 'lucide-react';

// ── GA4 Property Selector Modal ──────────────────────────────────────────────

interface PropertySelectorProps {
  accounts: GA4AccountSummary[];
  onSelect: (propertyId: string, propertyName: string) => void;
  onClose: () => void;
  loading: boolean;
}

const GA4PropertySelectorModal: React.FC<PropertySelectorProps> = ({
  accounts,
  onSelect,
  onClose,
  loading,
}) => {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [selected, setSelected] = useState<{ id: string; name: string } | null>(null);

  const toggleAccount = (accountId: string) =>
    setExpanded((prev) => ({ ...prev, [accountId]: !prev[accountId] }));

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl max-w-lg w-full shadow-2xl border border-slate-200 overflow-hidden">
        {/* Header */}
        <div className="p-6 border-b border-slate-100 flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-amber-50 text-amber-600 rounded-xl border border-amber-100">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">Select GA4 Property</h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Choose the property whose data to import into FunnelLeak AI
              </p>
            </div>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 transition">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-4 max-h-96 overflow-y-auto space-y-2">
          {loading ? (
            <div className="text-center py-8 text-xs text-slate-400">Fetching properties from Google Analytics…</div>
          ) : accounts.length === 0 ? (
            <div className="text-center py-8 text-xs text-slate-500">
              No GA4 accounts or properties found for this Google account.
            </div>
          ) : (
            accounts.map((account) => (
              <div key={account.account_id} className="border border-slate-200 rounded-xl overflow-hidden">
                <button
                  onClick={() => toggleAccount(account.account_id)}
                  className="w-full flex items-center justify-between p-3 hover:bg-slate-50 text-left transition"
                >
                  <span className="text-xs font-bold text-slate-800">{account.display_name}</span>
                  {expanded[account.account_id] ? (
                    <ChevronDown className="w-4 h-4 text-slate-400" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-slate-400" />
                  )}
                </button>
                {expanded[account.account_id] && (
                  <div className="border-t border-slate-100 divide-y divide-slate-100">
                    {account.properties.map((prop) => (
                      <button
                        key={prop.property_id}
                        onClick={() =>
                          setSelected({ id: prop.property_id, name: prop.display_name })
                        }
                        className={`w-full text-left px-4 py-3 text-xs transition flex items-center justify-between hover:bg-amber-50 ${
                          selected?.id === prop.property_id
                            ? 'bg-amber-50 font-semibold text-amber-700'
                            : 'text-slate-700'
                        }`}
                      >
                        <span>{prop.display_name}</span>
                        <span className="text-[10px] text-slate-400 font-mono">
                          properties/{prop.property_id}
                        </span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-100 flex items-center justify-end gap-2">
          <button
            onClick={onClose}
            className="px-4 py-2 border border-slate-200 rounded-lg text-xs font-semibold text-slate-600 hover:bg-slate-50"
          >
            Cancel
          </button>
          <button
            disabled={!selected}
            onClick={() => selected && onSelect(selected.id, selected.name)}
            className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-xs font-semibold shadow-sm transition disabled:opacity-40 flex items-center gap-1.5"
          >
            Use This Property
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
};

// ── GA4 Integration Card ──────────────────────────────────────────────────────

const GA4IntegrationCard: React.FC = () => {
  const [status, setStatus] = useState<GA4ConnectionStatus | null>(null);
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [connecting, setConnecting] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);

  const [showPropertyModal, setShowPropertyModal] = useState(false);
  const [propertiesLoading, setPropertiesLoading] = useState(false);
  const [accounts, setAccounts] = useState<GA4AccountSummary[]>([]);

  const [ga4Error, setGa4Error] = useState<string | null>(null);
  const [ga4Success, setGa4Success] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    setLoadingStatus(true);
    try {
      const data = await api.get<GA4ConnectionStatus>('/integrations/ga4/status');
      setStatus(data);
    } catch {
      setStatus(null);
    } finally {
      setLoadingStatus(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  const handleConnect = async () => {
    setConnecting(true);
    setGa4Error(null);
    try {
      const res = await api.get<{ auth_url: string }>('/integrations/ga4/connect');
      window.location.href = res.auth_url;
    } catch (err: any) {
      setGa4Error(err.message || 'Failed to initiate Google OAuth');
      setConnecting(false);
    }
  };

  const handleOpenPropertySelector = async () => {
    setShowPropertyModal(true);
    setPropertiesLoading(true);
    setGa4Error(null);
    try {
      const res = await api.get<GA4PropertiesResponse>('/integrations/ga4/properties');
      setAccounts(res.accounts);
    } catch (err: any) {
      setGa4Error(err.message || 'Failed to load GA4 properties');
      setShowPropertyModal(false);
    } finally {
      setPropertiesLoading(false);
    }
  };

  const handleSelectProperty = async (propertyId: string, propertyName: string) => {
    try {
      await api.post('/integrations/ga4/select-property', {
        property_id: propertyId,
        property_name: propertyName,
      });
      setShowPropertyModal(false);
      setGa4Success(`Property "${propertyName}" selected. You can now sync GA4 data.`);
      await fetchStatus();
    } catch (err: any) {
      setGa4Error(err.message || 'Failed to save property selection');
    }
  };

  const handleSync = async () => {
    setSyncing(true);
    setGa4Error(null);
    setGa4Success(null);
    try {
      const res = await api.post<{ success: boolean; records_synced: number; message: string }>(
        '/integrations/ga4/sync',
        {}
      );
      setGa4Success(`Synced ${res.records_synced.toLocaleString()} GA4 metric records successfully.`);
      await fetchStatus();
    } catch (err: any) {
      setGa4Error(err.message || 'GA4 synchronization failed');
    } finally {
      setSyncing(false);
    }
  };

  const handleDisconnect = async () => {
    if (!window.confirm('Disconnect Google Analytics 4? This will revoke access and clear stored credentials.')) return;
    setDisconnecting(true);
    try {
      await api.post('/integrations/ga4/disconnect', {});
      setGa4Success('Google Analytics 4 disconnected successfully.');
      await fetchStatus();
    } catch (err: any) {
      setGa4Error(err.message || 'Failed to disconnect GA4');
    } finally {
      setDisconnecting(false);
    }
  };

  const isConnected = status?.is_connected ?? false;
  const hasProperty = !!status?.provider_property_id;
  const isExpired = status?.token_expired ?? false;

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
      {/* Card Header */}
      <div className="p-5 border-b border-slate-100 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-start gap-3">
          <div
            className={`p-2.5 rounded-xl border ${
              isConnected
                ? 'bg-amber-50 text-amber-600 border-amber-200'
                : 'bg-slate-50 text-slate-500 border-slate-200'
            }`}
          >
            <Layers className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="text-sm font-bold text-slate-900">Google Analytics 4</h3>
              <span className="text-[10px] bg-slate-100 text-slate-500 font-bold px-2 py-0.5 rounded-full border border-slate-200">
                Data API v1beta
              </span>
              {isConnected && !isExpired ? (
                <span className="text-[10px] bg-emerald-100 text-emerald-800 font-bold px-2.5 py-0.5 rounded-full flex items-center gap-1 border border-emerald-200">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  CONNECTED
                </span>
              ) : isExpired ? (
                <span className="text-[10px] bg-amber-100 text-amber-700 font-bold px-2.5 py-0.5 rounded-full border border-amber-200">
                  TOKEN EXPIRED
                </span>
              ) : (
                <span className="text-[10px] bg-slate-100 text-slate-500 font-bold px-2.5 py-0.5 rounded-full border border-slate-200">
                  NOT CONNECTED
                </span>
              )}
            </div>
            <p className="text-xs text-slate-500 mt-1">
              Ingests sessions, traffic sources, and device breakdowns. Shopify remains the authoritative source for all orders and revenue.
            </p>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2 shrink-0">
          {loadingStatus ? (
            <div className="text-xs text-slate-400 animate-pulse">Loading…</div>
          ) : isConnected && !isExpired ? (
            <>
              {!hasProperty && (
                <button
                  onClick={handleOpenPropertySelector}
                  className="inline-flex items-center gap-1.5 bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold px-3 py-2 rounded-lg shadow-sm transition"
                >
                  <Layers className="w-3.5 h-3.5" />
                  Select Property
                </button>
              )}
              {hasProperty && (
                <button
                  onClick={handleSync}
                  disabled={syncing}
                  className="inline-flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-3 py-2 rounded-lg shadow-sm transition disabled:opacity-50"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${syncing ? 'animate-spin' : ''}`} />
                  {syncing ? 'Syncing…' : 'Sync Now'}
                </button>
              )}
              {hasProperty && (
                <button
                  onClick={handleOpenPropertySelector}
                  className="inline-flex items-center gap-1.5 border border-slate-200 text-slate-600 hover:bg-slate-50 text-xs font-semibold px-3 py-2 rounded-lg transition"
                >
                  Change Property
                </button>
              )}
              <button
                onClick={handleDisconnect}
                disabled={disconnecting}
                className="inline-flex items-center gap-1 border border-slate-200 text-slate-500 hover:bg-rose-50 hover:text-rose-600 text-xs font-semibold px-2.5 py-2 rounded-lg transition disabled:opacity-50"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </>
          ) : isExpired ? (
            <button
              onClick={handleConnect}
              disabled={connecting}
              className="inline-flex items-center gap-1.5 bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold px-3 py-2 rounded-lg shadow-sm transition disabled:opacity-50"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              Reconnect Google
            </button>
          ) : (
            <button
              onClick={handleConnect}
              disabled={connecting}
              className="inline-flex items-center gap-1.5 bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold px-3 py-2 rounded-lg shadow-sm transition disabled:opacity-50"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              {connecting ? 'Redirecting…' : 'Connect Google Account'}
            </button>
          )}
        </div>
      </div>

      {/* Inline Notifications */}
      {ga4Success && (
        <div className="mx-5 mt-4 p-3 bg-emerald-50 border border-emerald-200 rounded-lg flex items-center gap-2 text-xs text-emerald-800 font-medium">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          {ga4Success}
        </div>
      )}
      {ga4Error && (
        <div className="mx-5 mt-4 p-3 bg-rose-50 border border-rose-200 rounded-lg flex items-center gap-2 text-xs text-rose-800 font-medium">
          <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
          {ga4Error}
        </div>
      )}

      {/* Connection Details */}
      {isConnected && (
        <div className="p-5 grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
            <span className="text-[10px] uppercase font-bold text-slate-500 block">Active Property</span>
            <span className="text-xs font-bold text-slate-800 mt-0.5 block truncate">
              {status?.provider_property_name ?? 'Not selected yet'}
            </span>
            {status?.provider_property_id && (
              <span className="text-[10px] text-slate-400 font-mono block mt-0.5">
                ID: {status.provider_property_id}
              </span>
            )}
          </div>

          <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
            <span className="text-[10px] uppercase font-bold text-slate-500 block">Last Synced</span>
            <span className="text-xs font-bold text-slate-800 mt-0.5 block">
              {status?.last_sync_at
                ? new Date(status.last_sync_at).toLocaleString()
                : 'Never synced'}
            </span>
            {status?.last_sync_error && (
              <span className="text-[10px] text-rose-500 mt-0.5 block truncate">{status.last_sync_error}</span>
            )}
          </div>

          <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
            <span className="text-[10px] uppercase font-bold text-slate-500 block">Security & Scope</span>
            <span className="text-xs font-bold text-emerald-700 mt-0.5 flex items-center gap-1.5">
              <Shield className="w-3.5 h-3.5" /> AES-256 Encrypted
            </span>
            <span className="text-[10px] text-slate-400 mt-0.5 block">analytics.readonly · read-only</span>
          </div>
        </div>
      )}

      {/* Not connected empty state */}
      {!isConnected && !loadingStatus && (
        <div className="p-6 text-center space-y-2">
          <Layers className="w-8 h-8 text-slate-300 mx-auto" />
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            Connect your Google Account to import session counts, traffic sources, and device breakdowns from GA4.
            Shopify remains authoritative for all order revenue.
          </p>
        </div>
      )}

      {/* Property Selector Modal */}
      {showPropertyModal && (
        <GA4PropertySelectorModal
          accounts={accounts}
          onSelect={handleSelectProperty}
          onClose={() => setShowPropertyModal(false)}
          loading={propertiesLoading}
        />
      )}
    </div>
  );
};

// ── Main Integrations Page ────────────────────────────────────────────────────

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
    const statusParam = searchParams.get('status');
    const connectedParam = searchParams.get('connected');
    if (connectedParam === 'true' || statusParam === 'ga4_connected') {
      if (statusParam === 'ga4_connected') {
        setSuccessMsg('Google Analytics 4 connected! Select a property below to start syncing data.');
      } else {
        setSuccessMsg('Shopify store connected successfully! Initial synchronization is underway.');
      }
    }
    const errParam = searchParams.get('error');
    if (errParam) {
      setError(`OAuth error: ${errParam}`);
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
      await api.post('/shopify/sync', {});
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
    if (!window.confirm('Are you sure you want to disconnect this store? Offline API access will be revoked.')) return;
    try {
      await api.post('/shopify/disconnect', {});
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
          Store &amp; Analytics Integrations
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Connect your Shopify store and Google Analytics 4 for live telemetry and revenue intelligence.
        </p>
      </div>

      {/* Page-level Notifications */}
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

      {/* ── Shopify Card ─────────────────────────────────────────────────── */}
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
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
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
                <span className="text-[10px] uppercase font-bold text-slate-500 block">Security &amp; Storage</span>
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
                        <th className="py-2 px-3">Records</th>
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
                Connect your development or live store to unlock automated product revenue tracking, accurate COGS
                analysis, and real conversion leak diagnosis.
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

      {/* ── GA4 Integration Card ─────────────────────────────────────────── */}
      <GA4IntegrationCard />

      {/* ── Web Pixels (Planned) ─────────────────────────────────────────── */}
      <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-3 opacity-80">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-purple-50 text-purple-600 rounded-lg border border-purple-200">
              <Radio className="w-5 h-5" />
            </div>
            <h3 className="text-sm font-bold text-slate-900">Shopify Web Pixel Extension</h3>
          </div>
          <span className="text-[10px] font-bold uppercase bg-slate-100 text-slate-500 px-2 py-0.5 rounded-full border border-slate-200">
            Coming Soon
          </span>
        </div>
        <p className="text-xs text-slate-500 leading-relaxed">
          Privacy-first client-side event tracking across the customer journey: Product Views, Add-to-Cart events,
          Cart Drawer views, and Checkout progression — directly from your storefront.
        </p>
      </div>

      {/* ── Shopify Connect Modal ─────────────────────────────────────────── */}
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
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">Shopify Store Domain</label>
                <input
                  type="text"
                  value={shopInput}
                  onChange={(e) => setShopInput(e.target.value)}
                  placeholder="my-boutique.myshopify.com"
                  required
                  className="w-full text-xs font-mono p-3 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
                <span className="text-[11px] text-slate-400 mt-1.5 block">
                  Example: <code>your-store-name.myshopify.com</code> or just <code>your-store-name</code>
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
