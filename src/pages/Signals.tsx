import { SignalsTable } from '../components/signals/SignalsTable';
import { Radar, PieChart, TrendingUp, AlertCircle } from 'lucide-react';

const IntelligenceCard = ({ title, value, subtext, icon: Icon, color }: any) => (
  <div className="card p-4 flex items-start justify-between">
    <div>
      <div className="text-xs text-text-secondary uppercase font-bold tracking-wider mb-1">{title}</div>
      <div className="text-xl font-bold">{value}</div>
      <div className="text-[10px] text-text-secondary mt-1">{subtext}</div>
    </div>
    <div className={`p-2 rounded-lg bg-${color}/10 text-${color}`}>
      <Icon size={18} />
    </div>
  </div>
);

export default function Signals() {
  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-text-primary">Demand Signals</h2>
          <p className="text-sm text-text-secondary">Real-time intelligence from weather, trends, and market data.</p>
        </div>
        <div className="flex items-center space-x-3 text-xs">
          <span className="flex items-center space-x-1">
            <div className="w-2 h-2 rounded-full bg-success" />
            <span className="text-text-secondary">Tracking 12 APIs</span>
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <IntelligenceCard 
          title="Avg Signals/Day" 
          value="184" 
          subtext="+5% from last week" 
          icon={TrendingUp} 
          color="success" 
        />
        <IntelligenceCard 
          title="Most Active" 
          value="Weather" 
          subtext="42 triggers today" 
          icon={Radar} 
          color="primary" 
        />
        <IntelligenceCard 
          title="Signals Distribution" 
          value="82% High Qual" 
          subtext="Based on AI classification" 
          icon={PieChart} 
          color="secondary" 
        />
        <IntelligenceCard 
          title="Actionable Now" 
          value="12" 
          subtext="Requires campaign review" 
          icon={AlertCircle} 
          color="warning" 
        />
      </div>

      <SignalsTable />
    </div>
  );
}
