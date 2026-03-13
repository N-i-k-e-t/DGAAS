import React from 'react';
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
  Download
} from 'lucide-react';
import { motion } from 'framer-motion';
import { triggerWorkflow } from '../lib/n8nClient';

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
      {trend && (
        <span className={`text-xs ${trend > 0 ? 'text-success' : 'text-danger'}`}>
          {trend > 0 ? '+' : ''}{trend}%
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
  <div className="flex items-center p-4 hover:bg-white/5 transition-colors border-b border-white/5 last:border-0">
    <div className={`w-2 h-2 rounded-full mr-4 ${
      status === 'success' ? 'bg-success' : status === 'warning' ? 'bg-warning' : 'bg-primary'
    }`} />
    <div className="flex-1">
      <div className="text-sm font-medium">{title}</div>
      <div className="text-xs text-text-secondary">{type}</div>
    </div>
    <div className="text-xs text-text-secondary">{time}</div>
  </div>
);

const ActionButton = ({ icon: Icon, label, onClick }: any) => (
  <button 
    onClick={onClick}
    className="flex items-center space-x-3 w-full p-3 rounded-lg border border-white/5 hover:bg-primary/10 hover:border-primary/50 transition-all text-sm group"
  >
    <div className="p-2 rounded bg-white/5 text-text-secondary group-hover:text-primary transition-colors">
      <Icon size={18} />
    </div>
    <span>{label}</span>
  </button>
);

export const Dashboard = () => {
  return (
    <div className="p-6 space-y-6">
      {/* Row 1: Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <MetricCard 
          title="Signals Today" 
          value="142" 
          icon={Radar} 
          color="primary" 
          trend={12}
          path="/signals"
        />
        <MetricCard 
          title="Hot Leads" 
          value="24" 
          icon={Flame} 
          color="warning" 
          trend={5}
          path="/leads"
        />
        <MetricCard 
          title="Active Campaigns" 
          value="4" 
          icon={Megaphone} 
          color="secondary"
          path="/campaigns"
        />
        <MetricCard 
          title="Forecast Score" 
          value="High" 
          icon={LineChart} 
          color="success"
          path="/forecasts"
        />
        <MetricCard 
          title="Website Visitors" 
          value="1,280" 
          icon={Eye} 
          color="blue-500" 
          trend={-2}
        />
        <MetricCard 
          title="AI Model Status" 
          value="Online" 
          icon={Cpu} 
          color="success"
          path="/logs"
        />
      </div>

      {/* Row 2: Activity & Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-10 gap-6">
        <div className="lg:col-span-6 card p-0 overflow-hidden">
          <div className="p-4 border-b border-white/5 flex items-center justify-between bg-white/[0.02]">
            <h3 className="font-semibold">Recent Activity</h3>
            <button className="text-xs text-primary hover:underline">View All</button>
          </div>
          <div className="max-h-[400px] overflow-y-auto">
            <ActivityItem 
              type="Demand Signal" 
              title="Pollution spike detected in Delhi (AQI 340)" 
              time="2 mins ago" 
              status="danger" 
            />
            <ActivityItem 
              type="Campaign" 
              title="Pollution Escape triggered for 120 leads" 
              time="5 mins ago" 
              status="success" 
            />
            <ActivityItem 
              type="Lead" 
              title="New high-score lead from Instagram (92)" 
              time="15 mins ago" 
              status="primary" 
            />
            <ActivityItem 
              type="System" 
              title="n8n workflow 'Price Monitor' completed" 
              time="1 hour ago" 
              status="success" 
            />
          </div>
        </div>

        <div className="lg:col-span-4 card space-y-4">
          <h3 className="font-semibold mb-2">Quick Actions</h3>
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
            label="Test AI Model" 
            onClick={() => triggerWorkflow('ai-test')}
          />
          <ActionButton 
            icon={Download} 
            label="Sync Live Data" 
            onClick={() => triggerWorkflow('vps-sync')}
          />
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
