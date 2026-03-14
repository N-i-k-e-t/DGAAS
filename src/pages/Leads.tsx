import { useState } from 'react';
import { useLiveQuery } from 'dexie-react-hooks';
import { db } from '../db/database';
import { LeadsTable } from '../components/leads/LeadsTable';
import { LeadKanban } from '../components/leads/LeadKanban';
import { LeadDrawer } from '../components/leads/LeadDrawer';
import { Users, Heart, Zap, LayoutGrid, List } from 'lucide-react';

export default function Leads() {
  const [selectedLead, setSelectedLead] = useState<any>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [viewMode, setViewMode] = useState<'kanban' | 'table'>('kanban');

  const leads = useLiveQuery(() => db.leads.reverse().toArray()) || [];

  const handleRowClick = (lead: any) => {
    setSelectedLead(lead);
    setIsDrawerOpen(true);
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-text-primary">Leads Management</h2>
          <p className="text-sm text-text-secondary">AI-scored leads with lifecycle tracking and campaign integration.</p>
        </div>
        <div className="flex items-center space-x-3">
          <div className="flex items-center bg-white/5 p-1 rounded-lg border border-white/5">
            <button 
              onClick={() => setViewMode('kanban')}
              className={`p-1.5 rounded-md transition-all ${viewMode === 'kanban' ? 'bg-primary text-white shadow-lg shadow-primary/20' : 'text-text-secondary hover:text-text-primary'}`}
            >
              <LayoutGrid size={16} />
            </button>
            <button 
              onClick={() => setViewMode('table')}
              className={`p-1.5 rounded-md transition-all ${viewMode === 'table' ? 'bg-primary text-white shadow-lg shadow-primary/20' : 'text-text-secondary hover:text-text-primary'}`}
            >
              <List size={16} />
            </button>
          </div>
          <div className="bg-success/10 text-success border border-success/20 px-3 py-1 rounded-full text-xs font-bold animate-pulse">
            {leads.filter(l => l.ai_score > 70).length} Hot Leads
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* ... stats cards ... */}
        <div className="card flex items-center space-x-4">
          <div className="p-3 rounded-xl bg-primary/10 text-primary">
            <Users size={24} />
          </div>
          <div>
            <div className="text-xs text-text-secondary uppercase font-bold">Total Leads</div>
            <div className="text-2xl font-bold">{leads.length}</div>
          </div>
        </div>
        <div className="card flex items-center space-x-4">
          <div className="p-3 rounded-xl bg-success/10 text-success">
            <Zap size={24} />
          </div>
          <div>
            <div className="text-xs text-text-secondary uppercase font-bold">Conversion Rate</div>
            <div className="text-2xl font-bold">4.2%</div>
          </div>
        </div>
        <div className="card flex items-center space-x-4">
          <div className="p-3 rounded-xl bg-secondary/10 text-secondary">
            <Heart size={24} />
          </div>
          <div>
            <div className="text-xs text-text-secondary uppercase font-bold">Loyalty Score</div>
            <div className="text-2xl font-bold">8.8</div>
          </div>
        </div>
      </div>

      {viewMode === 'kanban' ? (
        <LeadKanban leads={leads} onCardClick={handleRowClick} />
      ) : (
        <LeadsTable onRowClick={handleRowClick} />
      )}
      
      <LeadDrawer 
        lead={selectedLead} 
        isOpen={isDrawerOpen} 
        onClose={() => setIsDrawerOpen(false)} 
      />
    </div>
  );
}
