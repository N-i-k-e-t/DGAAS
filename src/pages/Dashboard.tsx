import { 
  Radar, 
  Flame, 
  Megaphone, 
  LineChart, 
  Eye, 
  Cpu,
  Cloud,
  TrendingUp,
  RefreshCw,
  Bot,
  Download,
  CheckCircle2,
  AlertCircle,
  Loader2
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useLiveQuery } from 'dexie-react-hooks';
import { db } from '../db/database';
import { triggerWorkflow } from '../lib/n8nClient';
import { useState } from 'react';

import { useNavigate } from 'react-router-dom';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const MetricCard = ({ title, value, icon: Icon, color, trend, path }: any) => {
  const navigate = useNavigate();
  return (
    <motion.div 
      whileHover={{ y: -5, scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      onClick={() => path && navigate(path)}
      className={cn("card flex flex-col justify-between cursor-pointer transition-all", path && "hover:border-primary/50")}
    >
      <div className="flex items-center justify-between">
        <div className={`p-2 rounded-lg bg-${color}/10 text-${color}`}>
        <Icon size={24} />
      </div>
      {trend !== undefined && (
        <span className={`text-xs ${trend >= 0 ? 'text-success' : 'text-danger'}`}>
          {trend >= 0 ? '+' : ''}{trend}%
        </span>
      )}
    </div>
    <div className="mt-4">
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-sm text-text-secondary">{title}</div>
    </div>
    </motion.div>
  );
};

const ActivityItem = ({ type, title, time, status }: any) => (
  <div className="flex items-center p-4 hover:bg-white/5 transition-colors border-b border-white/5 last:border-0 text-sm">
    <div className={`w-2 h-2 rounded-full mr-4 shrink-0 ${
      status === 'success' ? 'bg-success' : status === 'danger' ? 'bg-danger' : status === 'warning' ? 'bg-warning' : 'bg-primary'
    }`} />
    <div className="flex-1 min-w-0">
      <div className="font-medium truncate">{title}</div>
      <div className="text-[10px] text-text-secondary uppercase tracking-tight">{type}</div>
    </div>
    <div className="text-[10px] text-text-secondary ml-4 whitespace-nowrap">{time}</div>
  </div>
);

const ActionButton = ({ icon: Icon, label, onClick }: any) => {
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  const handleClick = async () => {
    setLoading(true);
    await onClick();
    setLoading(false);
    setDone(true);
    setTimeout(() => setDone(false), 2000);
  };

  return (
    <button 
      disabled={loading}
      onClick={handleClick}
      className="flex items-center space-x-3 w-full p-3 rounded-lg border border-white/5 hover:bg-primary/10 hover:border-primary/50 transition-all text-sm group disabled:opacity-50"
    >
      <div className="p-2 rounded bg-white/5 text-text-secondary group-hover:text-primary transition-colors">
        {loading ? <Loader2 size={18} className="animate-spin" /> : done ? <CheckCircle2 size={18} className="text-success" /> : <Icon size={18} />}
      </div>
      <span>{label}</span>
      {done && <span className="text-[10px] text-success font-bold uppercase ml-auto">Triggered</span>}
    </button>
  );
};

export const Dashboard = () => {
  const signalsCount = useLiveQuery(() => db.demand_signals.count()) || 0;
  const leadsCount = useLiveQuery(() => db.leads.count()) || 0;
  const hotLeadsCount = useLiveQuery(() => db.leads.where('ai_score').above(70).count()) || 0;
  const campaignsCount = useLiveQuery(() => db.campaigns.where('is_active').equals(1).count()) || 0;
  const recentSignals = useLiveQuery(() => db.demand_signals.reverse().limit(10).toArray()) || [];
  const topSegment = useLiveQuery(async () => {
    const signals = await db.demand_signals.toArray();
    const counts: Record<string, number> = {};
    signals.forEach(s => counts[s.target_segment] = (counts[s.target_segment] || 0) + 1);
    return Object.entries(counts).sort((a,b) => b[1] - a[1])[0]?.[0] || 'N/A';
  }) || 'Loading...';

  return (
    <div className="p-6 space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-6">
        <MetricCard 
          title="Signals Today" 
          value={signalsCount} 
          icon={Radar} 
          color="primary" 
          trend={12}
          path="/signals"
        />
        <MetricCard 
          title="Hot Leads" 
          value={hotLeadsCount} 
          icon={Flame} 
          color="warning" 
          trend={5}
          path="/leads"
        />
        <MetricCard 
          title="Active Campaigns" 
          value={campaignsCount} 
          icon={Megaphone} 
          color="secondary"
          path="/campaigns"
        />
        <MetricCard 
          title="Forecast" 
          value="High" 
          icon={LineChart} 
          color="success"
          path="/forecasts"
        />
        <MetricCard 
          title="Top Segment" 
          value={topSegment} 
          icon={Bot} 
          color="blue-500" 
        />
        <MetricCard 
          title="Total Leads" 
          value={leadsCount} 
          icon={Eye} 
          color="primary"
          path="/leads"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-10 gap-6">
        <div className="lg:col-span-6 card p-0 overflow-hidden">
          <div className="p-4 border-b border-white/5 flex items-center justify-between bg-white/[0.02]">
            <h3 className="font-semibold text-sm uppercase tracking-wider">Live Activity Stream</h3>
            <button className="text-[10px] text-primary hover:underline font-bold uppercase">View Logs</button>
          </div>
          <div className="max-h-[440px] overflow-y-auto custom-scrollbar">
            {recentSignals.map(signal => (
              <ActivityItem 
                key={signal.id}
                type={signal.signal_type} 
                title={`${signal.source}: ${signal.target_segment} intent detected`} 
                time={signal.timestamp} 
                status={signal.urgency === 'critical' || signal.urgency === 'high' ? 'danger' : 'primary'} 
              />
            ))}
            {recentSignals.length === 0 && (
              <div className="p-10 text-center text-xs text-text-secondary italic">No recent activity detected.</div>
            )}
          </div>
        </div>

        <div className="lg:col-span-4 card space-y-4">
          <h3 className="font-semibold text-sm uppercase tracking-wider mb-2">Command Center</h3>
          <ActionButton 
            icon={Cloud} 
            label="Force Weather Check" 
            onClick={() => triggerWorkflow('weather-check')}
          />
          <ActionButton 
            icon={TrendingUp} 
            label="Run Trend Scan" 
            onClick={() => triggerWorkflow('trend-scan')}
          />
          <ActionButton 
            icon={RefreshCw} 
            label="Rescore All Leads" 
            onClick={() => triggerWorkflow('rescore-leads')}
          />
          <ActionButton 
            icon={Bot} 
            label="Sync VPS Intelligence" 
            onClick={() => triggerWorkflow('vps-sync')}
          />
          <div className="mt-6 p-4 rounded-xl bg-primary/5 border border-primary/20 space-y-3">
             <div className="flex items-center space-x-3 text-primary">
                <Cpu size={18} />
                <span className="text-xs font-bold uppercase">System Status</span>
             </div>
             <div className="flex justify-between text-[10px]">
                <span className="text-text-secondary">Ollama (qwen2.5)</span>
                <span className="text-success font-bold">ACTIVE</span>
             </div>
             <div className="flex justify-between text-[10px]">
                <span className="text-text-secondary">n8n Gateway</span>
                <span className="text-success font-bold">CONNECTED</span>
             </div>
          </div>
        </div>
      </div>

      {/* Row 3: Timeline */}
      <div className="card">
        <h3 className="font-semibold mb-6">Demand Signal Timeline</h3>
        <div className="h-48 flex items-end space-x-2 overflow-x-auto pb-4">
          {[...Array(24)].map((_, i) => {
            const height = Math.random() * 80 + 20;
            return (
              <div key={i} className="flex flex-col items-center flex-shrink-0 group">
                <div 
                  className="w-8 bg-primary/20 rounded-t hover:bg-primary/50 transition-all cursor-pointer relative"
                  style={{ height: `${height}%` }}
                >
                  <div className="absolute -top-8 left-1/2 -translate-x-1/2 bg-card border border-white/5 px-2 py-1 rounded text-[10px] opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-10">
                    {Math.round(height)} signals
                  </div>
                </div>
                <span className="text-[10px] text-text-secondary mt-2">
                  {String(i).padStart(2, '0')}:00
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
