import React, { useState } from 'react';
import { useLiveQuery } from 'dexie-react-hooks';
import { db } from '../../db/database';
import { Calendar, Filter, Download, ChevronDown, ChevronUp, AlertTriangle, Cloud, Wind, TrendingUp, Cpu, Database } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
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
  const [expandedId, setExpandedId] = useState<number | null>(null);
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
        <table className="w-full text-left text-sm border-separate border-spacing-0">
          <thead className="text-xs text-text-secondary uppercase bg-white/[0.01]">
            <tr>
              <th className="px-6 py-3 font-medium">Timestamp</th>
              <th className="px-6 py-3 font-medium">Type</th>
              <th className="px-6 py-3 font-medium">Source</th>
              <th className="px-6 py-3 font-medium">Urgency</th>
              <th className="px-6 py-3 font-medium">Target Segment</th>
              <th className="px-6 py-3 font-medium">Triggered</th>
              <th className="px-6 py-3 font-medium w-10"></th>
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
                <React.Fragment key={signal.id}>
                  <tr 
                    onClick={() => setExpandedId(expandedId === signal.id ? null : (signal.id || null))}
                    className={cn(
                      "hover:bg-white/[0.02] transition-colors group cursor-pointer",
                      expandedId === signal.id && "bg-white/[0.03]"
                    )}
                  >
                    <td className="px-6 py-4 text-xs font-mono">{signal.timestamp}</td>
                    <td className="px-6 py-4">
                      <div className="flex items-center space-x-2">
                        <SignalIcon type={signal.signal_type} />
                        <span className="font-medium text-xs">{signal.signal_type}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-xs text-text-secondary">{signal.source}</td>
                    <td className="px-6 py-4">
                      <UrgencyBadge urgency={signal.urgency} />
                    </td>
                    <td className="px-6 py-4">
                      <span className="px-2 py-0.5 rounded bg-white/5 text-[10px] font-bold">{signal.target_segment}</span>
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
                    <td className="px-6 py-4 text-right">
                      {expandedId === signal.id ? <ChevronUp size={14} className="text-primary" /> : <ChevronDown size={14} className="text-text-secondary" />}
                    </td>
                  </tr>
                  <AnimatePresence>
                    {expandedId === signal.id && (
                      <motion.tr
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                      >
                        <td colSpan={7} className="px-6 pb-6 bg-white/[0.01]">
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 p-4 bg-background/50 rounded-xl border border-white/5">
                            <div className="space-y-3">
                              <h4 className="text-[10px] font-bold text-text-secondary uppercase tracking-widest flex items-center">
                                <Database size={10} className="mr-2" />
                                Raw Signal Payload
                              </h4>
                              <div className="bg-black/30 rounded-lg p-3 font-mono text-[10px] text-text-secondary overflow-x-auto whitespace-pre-wrap leading-relaxed border border-white/5">
                                {JSON.stringify(signal.raw_data, null, 2)}
                              </div>
                            </div>
                            <div className="space-y-3">
                              <h4 className="text-[10px] font-bold text-text-secondary uppercase tracking-widest flex items-center">
                                <Cpu size={10} className="mr-2" />
                                AI Classification & Logic
                              </h4>
                              <div className="bg-primary/5 rounded-lg p-3 border border-primary/20">
                                <div className="text-xs text-primary font-bold mb-2">Intent Logic Result:</div>
                                <div className="space-y-2">
                                  {Object.entries(signal.ai_classification || {}).map(([key, val]) => (
                                    <div key={key} className="flex items-center justify-between text-[10px] border-b border-white/5 pb-1 last:border-0">
                                      <span className="text-text-secondary font-medium">{key.replace(/_/g, ' ')}</span>
                                      <span className="text-text-primary font-bold">{String(val)}</span>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            </div>
                          </div>
                        </td>
                      </motion.tr>
                    )}
                  </AnimatePresence>
                </React.Fragment>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
