import React from 'react';
import { useLiveQuery } from 'dexie-react-hooks';
import { db } from '../../db/database';
import { Calendar, Filter, Download, MoreHorizontal, AlertTriangle, Cloud, Wind, TrendingUp, Users } from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const UrgencyBadge = ({ urgency }: { urgency: string }) => {
  const colors: Record<string, string> = {
    low: 'bg-success/10 text-success border-success/20',
    medium: 'bg-warning/10 text-warning border-warning/20',
    high: 'bg-primary/10 text-primary border-primary/20',
    critical: 'bg-danger/10 text-danger border-danger/20',
  };
  return (
    <span className={cn("px-2 py-0.5 rounded-full text-[10px] font-bold uppercase border", colors[urgency] || colors.medium)}>
      {urgency}
    </span>
  );
};

const SignalIcon = ({ type }: { type: string }) => {
  if (type.toLowerCase().includes('weather')) return <Cloud size={16} className="text-blue-400" />;
  if (type.toLowerCase().includes('aqi')) return <Wind size={16} className="text-success" />;
  if (type.toLowerCase().includes('trend')) return <TrendingUp size={16} className="text-primary" />;
  return <AlertTriangle size={16} className="text-warning" />;
};

export const SignalsTable = () => {
  const signals = useLiveQuery(() => db.demand_signals.reverse().toArray()) || [];

  return (
    <div className="card p-0 overflow-hidden">
      <div className="p-4 border-b border-white/5 flex flex-wrap items-center justify-between gap-4 bg-white/[0.02]">
        <div className="flex items-center space-x-2">
          <div className="relative">
            <Filter size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-secondary" />
            <select className="bg-background border border-white/10 rounded-md pl-8 pr-3 py-1.5 text-xs focus:outline-none focus:border-primary/50 transition-all appearance-none cursor-pointer">
              <option>All Signal Types</option>
              <option>Weather</option>
              <option>AQI</option>
              <option>Trend</option>
              <option>Competitor</option>
            </select>
          </div>
          <div className="relative">
            <Calendar size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-secondary" />
            <select className="bg-background border border-white/10 rounded-md pl-8 pr-3 py-1.5 text-xs focus:outline-none focus:border-primary/50 transition-all appearance-none cursor-pointer">
              <option>Last 24 Hours</option>
              <option>Last 7 Days</option>
              <option>Last 30 Days</option>
            </select>
          </div>
        </div>
        <button className="flex items-center space-x-2 text-xs text-text-secondary hover:text-text-primary transition-colors bg-white/5 px-3 py-1.5 rounded-md border border-white/5">
          <Download size={14} />
          <span>Export CSV</span>
        </button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-xs text-text-secondary uppercase bg-white/[0.01]">
            <tr>
              <th className="px-6 py-3 font-medium">Timestamp</th>
              <th className="px-6 py-3 font-medium">Type</th>
              <th className="px-6 py-3 font-medium">Source</th>
              <th className="px-6 py-3 font-medium">Urgency</th>
              <th className="px-6 py-3 font-medium">Target Segment</th>
              <th className="px-6 py-3 font-medium">Triggered</th>
              <th className="px-6 py-3 font-medium"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {signals.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-6 py-10 text-center text-text-secondary italic">
                  No demand signals recorded yet. Generate some activity or wait for VPS sync.
                </td>
              </tr>
            ) : (
              signals.map((signal) => (
                <tr key={signal.id} className="hover:bg-white/[0.02] transition-colors group cursor-pointer">
                  <td className="px-6 py-4 text-xs font-mono">{signal.timestamp}</td>
                  <td className="px-6 py-4">
                    <div className="flex items-center space-x-2">
                      <SignalIcon type={signal.signal_type} />
                      <span className="font-medium">{signal.signal_type}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-text-secondary">{signal.source}</td>
                  <td className="px-6 py-4">
                    <UrgencyBadge urgency={signal.urgency} />
                  </td>
                  <td className="px-6 py-4">
                    <span className="px-2 py-0.5 rounded bg-white/5 text-[10px]">{signal.target_segment}</span>
                  </td>
                  <td className="px-6 py-4">
                    {signal.campaign_triggered ? (
                      <div className="w-5 h-5 rounded-full bg-success/20 flex items-center justify-center text-success">
                        <TrendingUp size={12} />
                      </div>
                    ) : (
                      <span className="text-text-secondary opacity-50">—</span>
                    )}
                  </td>
                  <td className="px-6 py-4 text-right opacity-0 group-hover:opacity-100 transition-opacity">
                    <button className="p-1 hover:bg-white/10 rounded transition-colors text-text-secondary">
                      <MoreHorizontal size={16} />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
