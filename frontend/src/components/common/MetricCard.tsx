import React from 'react';
import { LucideIcon } from 'lucide-react';

interface MetricCardProps {
  title: string;
  value: string;
  subtitle?: string;
  change?: string;
  isPositive?: boolean;
  icon: LucideIcon;
  variant?: 'default' | 'danger' | 'warning' | 'success';
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  subtitle,
  change,
  isPositive,
  icon: Icon,
  variant = 'default',
}) => {
  const getVariantStyles = () => {
    switch (variant) {
      case 'danger':
        return 'border-rose-200 bg-rose-50/50 text-rose-900';
      case 'warning':
        return 'border-amber-200 bg-amber-50/50 text-amber-900';
      case 'success':
        return 'border-emerald-200 bg-emerald-50/50 text-emerald-900';
      default:
        return 'border-slate-200 bg-white text-slate-900';
    }
  };

  const getIconColor = () => {
    switch (variant) {
      case 'danger':
        return 'bg-rose-100 text-rose-600';
      case 'warning':
        return 'bg-amber-100 text-amber-600';
      case 'success':
        return 'bg-emerald-100 text-emerald-600';
      default:
        return 'bg-blue-50 text-blue-600';
    }
  };

  return (
    <div className={`p-5 rounded-xl border shadow-sm transition hover:shadow-md ${getVariantStyles()}`}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">{title}</span>
        <div className={`p-2 rounded-lg ${getIconColor()}`}>
          <Icon className="w-5 h-5" />
        </div>
      </div>
      <div className="mt-2 flex items-baseline gap-2">
        <span className="text-2xl font-bold tracking-tight">{value}</span>
        {change && (
          <span
            className={`text-xs font-semibold ${
              isPositive ? 'text-emerald-600' : 'text-rose-600'
            }`}
          >
            {change}
          </span>
        )}
      </div>
      {subtitle && <p className="mt-1 text-xs text-slate-500">{subtitle}</p>}
    </div>
  );
};
