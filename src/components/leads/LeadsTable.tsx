import { useLiveQuery } from 'dexie-react-hooks';
import { db } from '../../db/database';
import { Search, Download, Plus } from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const LeadsTable = ({ onRowClick }: { onRowClick: (lead: any) => void }) => {
  const leads = useLiveQuery(() => db.leads.reverse().toArray()) || [];

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-success bg-success/10 border-success/20';
    if (score >= 60) return 'text-warning bg-warning/10 border-warning/20';
    return 'text-danger bg-danger/10 border-danger/20';
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'new': return 'bg-primary/20 text-primary';
      case 'contacted': return 'bg-blue-500/20 text-blue-400';
      case 'nurturing': return 'bg-purple-500/20 text-purple-400';
      case 'booked': return 'bg-success/20 text-success';
      case 'lost': return 'bg-white/10 text-text-secondary';
      default: return 'bg-white/10 text-text-secondary';
    }
  };

  return (
    <div className="card p-0 overflow-hidden">
      <div className="p-4 border-b border-white/5 flex flex-wrap items-center justify-between gap-4 bg-white/[0.02]">
        <div className="flex items-center space-x-3">
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-secondary" />
            <input 
              type="text" 
              placeholder="Search leads..." 
              className="bg-background border border-white/10 rounded-md pl-8 pr-3 py-1.5 text-xs focus:outline-none focus:border-primary/50 transition-all w-48"
            />
          </div>
          <select className="bg-background border border-white/10 rounded-md px-3 py-1.5 text-xs focus:outline-none focus:border-primary/50 transition-all">
            <option>Status: All</option>
            <option>New</option>
            <option>Contacted</option>
            <option>Booked</option>
          </select>
          <select className="bg-background border border-white/10 rounded-md px-3 py-1.5 text-xs focus:outline-none focus:border-primary/50 transition-all">
            <option>Segment: All</option>
            <option>Digital Nomad</option>
            <option>Luxury Couple</option>
          </select>
        </div>
        <div className="flex items-center space-x-2">
          <button className="flex items-center space-x-2 text-xs text-text-secondary hover:text-text-primary transition-colors bg-white/5 px-3 py-1.5 rounded-md border border-white/5">
            <Download size={14} />
            <span>Export</span>
          </button>
          <button className="btn-primary text-xs flex items-center space-x-2 px-3 py-1.5">
            <Plus size={14} />
            <span>Add Lead</span>
          </button>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-xs text-text-secondary uppercase bg-white/[0.01]">
            <tr>
              <th className="px-6 py-3 font-medium">Lead Name</th>
              <th className="px-6 py-3 font-medium">Source</th>
              <th className="px-6 py-3 font-medium">Life Event</th>
              <th className="px-6 py-3 font-medium">AI Score</th>
              <th className="px-6 py-3 font-medium">Segment</th>
              <th className="px-6 py-3 font-medium">Status</th>
              <th className="px-6 py-3 font-medium">Created</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {leads.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-6 py-10 text-center text-text-secondary italic">
                  No leads found. Sync with VPS or add manually.
                </td>
              </tr>
            ) : (
              leads.map((lead) => (
                <tr 
                  key={lead.id} 
                  onClick={() => onRowClick(lead)}
                  className="hover:bg-white/[0.02] transition-colors group cursor-pointer"
                >
                  <td className="px-6 py-4">
                    <div className="font-bold text-text-primary">{lead.name}</div>
                    <div className="text-xs text-text-secondary">{lead.email}</div>
                  </td>
                  <td className="px-6 py-4">
                    <span className="px-2 py-0.5 rounded-md bg-white/5 text-[10px] border border-white/10">
                      {lead.source}
                    </span>
                  </td>
                  <td className="px-6 py-4 italic text-text-secondary max-w-[200px] truncate">
                    {lead.life_event}
                  </td>
                  <td className="px-6 py-4">
                    <div className={cn("inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold border", getScoreColor(lead.ai_score))}>
                      {lead.ai_score}
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className="px-2 py-0.5 rounded bg-secondary/10 text-secondary text-[10px] font-medium border border-secondary/20 uppercase tracking-tighter">
                      {lead.segment}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <span className={cn("px-2 py-1 rounded-full text-[10px] font-bold uppercase", getStatusColor(lead.status))}>
                      {lead.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-xs text-text-secondary">{lead.created_at}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
