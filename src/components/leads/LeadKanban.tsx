import { motion, Reorder } from 'framer-motion';
import { db, type Lead } from '../../db/database';
import { User, Mail, Phone, MapPin, Star, MoreHorizontal, ExternalLink } from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface KanbanColumnProps {
  title: string;
  status: Lead['status'];
  leads: Lead[];
  onCardClick: (lead: Lead) => void;
}

const LeadCard = ({ lead, onClick }: { lead: Lead; onClick: () => void }) => {
  return (
    <motion.div 
      layout
      whileHover={{ y: -2, scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      onClick={onClick}
      className="card p-3 mb-3 cursor-pointer group hover:border-primary/50 transition-all border border-white/5 bg-background/40 backdrop-blur-sm"
    >
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center space-x-2">
          <div className="p-1.5 rounded-md bg-primary/10 text-primary">
            <User size={14} />
          </div>
          <span className="text-xs font-bold truncate max-w-[120px]">{lead.name}</span>
        </div>
        <div className="flex items-center space-x-1">
          <Star size={10} className="text-warning fill-warning" />
          <span className="text-[10px] font-bold">{lead.ai_score}</span>
        </div>
      </div>
      
      <p className="text-[10px] text-text-secondary line-clamp-2 mb-3 h-7 italic">
        "{lead.ai_reasoning || 'No AI analysis available yet.'}"
      </p>

      <div className="flex items-center justify-between mt-auto">
        <div className="flex items-center -space-x-1">
          <span className="px-1.5 py-0.5 rounded bg-white/5 text-[8px] uppercase tracking-wider font-bold">
            {lead.segment}
          </span>
        </div>
        <div className="flex items-center space-x-2 opacity-0 group-hover:opacity-100 transition-opacity">
          <button className="p-1 hover:bg-white/10 rounded">
            <ExternalLink size={12} className="text-text-secondary" />
          </button>
          <button className="p-1 hover:bg-white/10 rounded">
            <MoreHorizontal size={12} className="text-text-secondary" />
          </button>
        </div>
      </div>
    </motion.div>
  );
};

const KanbanColumn = ({ title, status, leads, onCardClick }: KanbanColumnProps) => {
  const columnColor = {
    new: 'bg-primary/20',
    contacted: 'bg-warning/20',
    nurturing: 'bg-secondary/20',
    booked: 'bg-success/20',
    lost: 'bg-danger/20',
  }[status];

  const textColor = {
    new: 'text-primary',
    contacted: 'text-warning',
    nurturing: 'text-secondary',
    booked: 'text-success',
    lost: 'text-danger',
  }[status];

  return (
    <div className="flex-1 min-w-[280px] bg-card/30 rounded-2xl border border-white/5 p-4 flex flex-col h-[calc(100vh-250px)]">
      <div className="flex items-center justify-between mb-6 px-1">
        <div className="flex items-center space-x-2">
          <div className={cn("w-2 h-2 rounded-full", columnColor.replace('/20', ''))} />
          <h3 className="font-bold text-sm uppercase tracking-widest">{title}</h3>
          <span className="text-[10px] text-text-secondary font-mono px-1.5 py-0.5 rounded-full bg-white/5">
            {leads.length}
          </span>
        </div>
      </div>
      
      <div className="flex-1 overflow-y-auto pr-1 custom-scrollbar">
        {leads.map((lead) => (
          <LeadCard key={lead.id} lead={lead} onClick={() => onCardClick(lead)} />
        ))}
        {leads.length === 0 && (
          <div className="h-24 border border-dashed border-white/5 rounded-xl flex items-center justify-center text-xs text-text-secondary italic">
            Empty
          </div>
        )}
      </div>
    </div>
  );
};

export const LeadKanban = ({ leads, onCardClick }: { leads: Lead[], onCardClick: (lead: Lead) => void }) => {
  const columns: { title: string; status: Lead['status'] }[] = [
    { title: 'New Leads', status: 'new' },
    { title: 'Contacted', status: 'contacted' },
    { title: 'Nurturing', status: 'nurturing' },
    { title: 'Booked', status: 'booked' },
    { title: 'Lost', status: 'lost' },
  ];

  const getLeadsByStatus = (status: Lead['status']) => 
    leads.filter(l => l.status === status);

  return (
    <div className="flex space-x-6 overflow-x-auto pb-6 scroll-smooth">
      {columns.map(col => (
        <KanbanColumn 
          key={col.status}
          title={col.title}
          status={col.status}
          leads={getLeadsByStatus(col.status)}
          onCardClick={onCardClick}
        />
      ))}
    </div>
  );
};
