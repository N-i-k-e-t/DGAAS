import { useLiveQuery } from 'dexie-react-hooks';
import { db } from '../db/database';
import { CampaignCard } from '../components/campaigns/CampaignCard';
import { Plus, Search, Activity } from 'lucide-react';

export default function Campaigns() {
  const campaigns = useLiveQuery(() => db.campaigns.toArray()) || [];

  const handleToggle = async (id: number) => {
    const campaign = await db.campaigns.get(id);
    if (campaign) {
      await db.campaigns.update(id, { is_active: !campaign.is_active });
    }
  };

  const handleTrigger = async (id: number) => {
    await db.campaigns.update(id, { status: 'triggered', last_triggered: new Date().toISOString() });
    setTimeout(async () => {
      await db.campaigns.update(id, { status: 'cooldown' });
    }, 5000);
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-text-primary">Campaign Automation</h2>
          <p className="text-sm text-text-secondary">Pre-planned scenarios triggered by demand engine intelligence.</p>
        </div>
        <button className="btn-primary flex items-center space-x-2">
          <Plus size={18} />
          <span>New Scenario</span>
        </button>
      </div>

      <div className="flex items-center space-x-4 mb-6">
        <div className="flex-1 relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary" />
          <input 
            type="text" 
            placeholder="Search campaigns..." 
            className="w-full bg-card border border-white/5 rounded-lg pl-10 pr-4 py-2 text-sm focus:outline-none focus:border-primary/50"
          />
        </div>
        <div className="flex items-center bg-card border border-white/5 rounded-lg p-1">
          <button className="px-3 py-1 text-xs font-medium rounded-md bg-primary text-white">All Groups</button>
          <button className="px-3 py-1 text-xs font-medium text-text-secondary hover:text-text-primary transition-colors">By Trigger</button>
          <button className="px-3 py-1 text-xs font-medium text-text-secondary hover:text-text-primary transition-colors">Active Only</button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
        {campaigns.map((campaign) => (
          <CampaignCard 
            key={campaign.id} 
            campaign={campaign} 
            onToggle={handleToggle}
            onTrigger={handleTrigger}
            onEdit={() => {}}
          />
        ))}
      </div>

      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold flex items-center space-x-2">
            <Activity size={18} className="text-primary" />
            <span>Campaign Execution Log</span>
          </h3>
          <button className="text-xs text-text-secondary hover:text-text-primary transition-colors underline">Download Report</button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="text-text-secondary uppercase border-b border-white/5">
              <tr>
                <th className="px-4 py-2 font-medium">Timestamp</th>
                <th className="px-4 py-2 font-medium">Campaign</th>
                <th className="px-4 py-2 font-medium">Trigger Signal</th>
                <th className="px-4 py-2 font-medium">Outcome</th>
                <th className="px-4 py-2 font-medium">Leads Impacted</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              <tr className="hover:bg-white/[0.02]">
                <td className="px-4 py-3 font-mono text-text-secondary">2026-03-13 02:15:30</td>
                <td className="px-4 py-3 font-bold">Pollution Escape</td>
                <td className="px-4 py-3 text-danger">AQI DELHI 340</td>
                <td className="px-4 py-3 text-success font-medium">SENT (120 Email, 95 WA)</td>
                <td className="px-4 py-3">120</td>
              </tr>
              <tr className="hover:bg-white/[0.02]">
                <td className="px-4 py-3 font-mono text-text-secondary">2026-03-12 18:45:00</td>
                <td className="px-4 py-3 font-bold">Clear Weekend Push</td>
                <td className="px-4 py-3 text-success underline">NASHIK 24C CLEAR</td>
                <td className="px-4 py-3 text-success font-medium">SENT (450 Email, 380 WA)</td>
                <td className="px-4 py-3">450</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
