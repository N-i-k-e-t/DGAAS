import { XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';
import { Calendar, TrendingUp, Info, CheckCircle2 } from 'lucide-react';

const data = [
  { name: 'Week 1', demand: 2 },
  { name: 'Week 2', demand: 3 },
  { name: 'Week 3', demand: 4 },
  { name: 'Week 4', demand: 3 },
  { name: 'Week 5', demand: 4 },
  { name: 'Week 6', demand: 4 },
];

const demandLevels = ['Low', 'Medium', 'High', 'Very High'];

export default function Forecasts() {
  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-text-primary">Demand Forecasting</h2>
          <p className="text-sm text-text-secondary">AI-powered 14-day outlook based on historical patterns and current signals.</p>
        </div>
      </div>

      {/* Top: Outlook Card */}
      <div className="card bg-primary/5 border-primary/20 p-8 flex flex-col md:flex-row items-center justify-between gap-8">
        <div className="space-y-4 text-center md:text-left">
          <h3 className="text-sm font-bold text-primary uppercase tracking-[0.2em]">14-Day Demand Outlook</h3>
          <div className="flex flex-col">
            <span className="text-6xl font-black text-primary">VERY HIGH</span>
            <span className="text-text-secondary mt-2 flex items-center justify-center md:justify-start">
              <Calendar size={14} className="mr-2" />
              March 14 - March 28, 2026
            </span>
          </div>
          <div className="flex flex-wrap gap-2 justify-center md:justify-start">
            {['Pollution Spike', 'Holiday Weekend', 'Competitor Sellout'].map(tag => (
              <span key={tag} className="px-3 py-1 bg-primary/10 text-primary border border-primary/20 rounded-full text-[10px] font-bold uppercase tracking-wider">
                {tag}
              </span>
            ))}
          </div>
        </div>
        
        <div className="w-full md:w-auto card bg-background border border-white/5 p-6 min-w-[300px]">
          <h4 className="text-xs font-bold text-text-secondary uppercase mb-4 flex items-center">
            <CheckCircle2 size={14} className="text-success mr-2" />
            Recommended Actions
          </h4>
          <ul className="space-y-3">
            {[
              "Trigger 'Pollution Escape' for segments A & B",
              "Increase PPC bid for 'Nashik Resorts' by 20%",
              "Optimize 'Clear Weekend' email sequence",
              "Alert property managers for 100% occupancy"
            ].map((action, i) => (
              <li key={i} className="flex items-start text-sm">
                <input type="checkbox" className="mt-1 mr-3 accent-primary" defaultChecked={i < 1} />
                <span className={i < 1 ? 'text-text-primary' : 'text-text-secondary'}>{action}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Middle: Chart */}
      <div className="card h-80">
        <h3 className="font-semibold mb-6">Demand History & Projection</h3>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data}>
            <defs>
              <linearGradient id="colorDemand" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#722F37" stopOpacity={0.3}/>
                <stop offset="95%" stopColor="#722F37" stopOpacity={0}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" vertical={false} />
            <XAxis dataKey="name" stroke="#9CA3AF" fontSize={12} tickLine={false} axisLine={false} />
            <YAxis 
              stroke="#9CA3AF" 
              fontSize={12} 
              tickLine={false} 
              axisLine={false} 
              domain={[0, 4]} 
              ticks={[1, 2, 3, 4]}
              tickFormatter={(val) => demandLevels[val-1]}
            />
            <Tooltip 
              contentStyle={{ backgroundColor: '#1a1a24', border: '1px solid #ffffff10', borderRadius: '8px' }}
              itemStyle={{ color: '#722F37' }}
            />
            <Area 
              type="monotone" 
              dataKey="demand" 
              stroke="#722F37" 
              strokeWidth={3}
              fillOpacity={1} 
              fill="url(#colorDemand)" 
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Bottom: Insights */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="card">
          <h3 className="font-semibold mb-4 flex items-center">
            <TrendingUp size={18} className="text-primary mr-2" />
            Signal Correlation Matrix
          </h3>
          <div className="space-y-4">
            {[
              { signal: 'AQI > 250', correlation: 0.92, status: 'Strong Positive' },
              { signal: 'Long Weekend', correlation: 0.85, status: 'Positive' },
              { signal: 'Temp 22-26C', correlation: 0.78, status: 'Positive' },
            ].map(item => (
              <div key={item.signal} className="flex items-center justify-between p-3 bg-white/5 rounded-lg">
                <div className="text-sm font-medium">{item.signal}</div>
                <div className="flex items-center space-x-3">
                  <div className="w-24 h-1.5 bg-white/10 rounded-full overflow-hidden">
                    <div className="h-full bg-primary" style={{ width: `${item.correlation * 100}%` }} />
                  </div>
                  <span className="text-[10px] font-bold text-text-secondary uppercase">{item.status}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <h3 className="font-semibold mb-4 flex items-center">
            <Info size={18} className="text-primary mr-2" />
            Upcoming Events Impact
          </h3>
          <div className="space-y-3">
            {[
              { event: 'Sula Fest 2026', date: 'March 20', impact: '+45%' },
              { event: 'Holi Weekend', date: 'March 25', impact: '+35%' },
              { event: 'Wine Expo', date: 'April 02', impact: '+15%' },
            ].map(item => (
              <div key={item.event} className="flex items-center justify-between p-3 border-b border-white/5 last:border-0 hover:bg-white/[0.02] transition-colors">
                <div>
                  <div className="text-sm font-bold">{item.event}</div>
                  <div className="text-[10px] text-text-secondary uppercase">{item.date}</div>
                </div>
                <div className="text-success font-bold">{item.impact}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
