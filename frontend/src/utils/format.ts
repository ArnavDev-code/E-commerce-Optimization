/**
 * Formatting helpers for currency, percentages, and metrics.
 */

export function formatCurrency(amount: number | null | undefined): string {
  if (amount == null) return '$0.00';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(amount);
}

export function formatPercent(val: number | null | undefined, decimals = 1): string {
  if (val == null) return '0.0%';
  return `${Number(val).toFixed(decimals)}%`;
}

export function formatNumber(val: number | null | undefined): string {
  if (val == null) return '0';
  return new Intl.NumberFormat('en-US').format(val);
}

export function formatCompactNumber(val: number | null | undefined): string {
  if (val == null) return '0';
  return new Intl.NumberFormat('en-US', {
    notation: 'compact',
    compactDisplay: 'short',
  }).format(val);
}

export function getSeverityBadge(severity: string): { bg: string; text: string } {
  switch (severity?.toLowerCase()) {
    case 'critical':
      return { bg: 'bg-rose-100 text-rose-800 border-rose-200', text: 'Critical' };
    case 'high':
      return { bg: 'bg-orange-100 text-orange-800 border-orange-200', text: 'High' };
    case 'medium':
      return { bg: 'bg-amber-100 text-amber-800 border-amber-200', text: 'Medium' };
    default:
      return { bg: 'bg-slate-100 text-slate-700 border-slate-200', text: 'Low' };
  }
}
