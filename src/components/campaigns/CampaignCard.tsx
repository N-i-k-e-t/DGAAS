import React from 'react';
import { Power, Clock, Play, Edit2, AlertCircle, Mail, MessageSquare } from 'lucide-react';
import { motion } from 'framer-motion';

export const CampaignCard = ({ campaign, onToggle, onEdit, onTrigger }: any) => {
  const getStatusColor = () => {
    switch (campaign.status) {
      case 'armed': return 'text-success';
      case 'triggered': return 'text-primary animate-pulse';
      case 'cooldown': return 'text-text-secondary';
      default: return 'text-text-secondary';
    }
  };

  return (
    <div className="card space-y-4">
      <div className="flex items-start justify-between">
        <div className="flex items-center space-x-3">
          <div className={`p-2 rounded-lg bg-white/5 ${campaign.is_active ? 'text-primary' : 'text-text-secondary'}`}>
            <AlertCircle size={20} />
          </div>
          <div>
            <h3 className="font-bold">{campaign.name}</h3>
            <p className="text-[10px] text-text-secondary uppercase tracking-wider">{campaign.trigger}</p>
          </div>
        </div>
        <button 
          onClick={() => onToggle(campaign.id)}
          className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none ${campaign.is_active ? 'bg-primary' : 'bg-white/10'}`}
        >
          <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${campaign.is_active ? 'translate-x-6' : 'translate-x-1'}`} />
        </button>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="bg-background rounded-lg p-3 border border-white/5">
          <div className="text-[10px] text-text-secondary uppercase mb-1">Status</div>
          <div className={`text-xs font-bold uppercase flex items-center ${getStatusColor()}`}>
            <div className={`w-1.5 h-1.5 rounded-full mr-2 ${
              campaign.status === 'armed' ? 'bg-success' : campaign.status === 'triggered' ? 'bg-primary' : 'bg-white/20'
            }`} />
            {campaign.status}
          </div>
        </div>
        <div className="bg-background rounded-lg p-3 border border-white/5">
          <div className="text-[10px] text-text-secondary uppercase mb-1">Cooldown</div>
          <div className="text-xs font-bold uppercase flex items-center text-text-secondary">
            <Clock size={12} className="mr-2" />
            {campaign.cooldown_hours}h
          </div>
        </div>
      </div>

      <div className="space-y-2">
        <div className="text-[10px] text-text-secondary uppercase font-bold px-1">Channels</div>
        <div className="flex space-x-2">
          <div className="flex-1 flex items-center justify-center space-x-2 bg-white/5 py-2 rounded-md border border-white/5 text-xs">
            <Mail size={14} className="text-blue-400" />
            <span>Email</span>
          </div>
          <div className="flex-1 flex items-center justify-center space-x-2 bg-white/5 py-2 rounded-md border border-white/5 text-xs">
            <MessageSquare size={14} className="text-success" />
            <span>WhatsApp</span>
          </div>
        </div>
      </div>

      <div className="pt-2 flex items-center space-x-2">
        <button 
          onClick={() => onEdit(campaign)}
          className="flex-1 flex items-center justify-center space-x-2 bg-white/5 hover:bg-white/10 py-2 rounded-md text-xs transition-colors"
        >
          <Edit2 size={14} />
          <span>Edit Template</span>
        </button>
        <button 
          onClick={() => onTrigger(campaign.id)}
          className="p-2 bg-white/5 hover:bg-primary/20 hover:text-primary rounded-md transition-colors"
          title="Force Trigger"
        >
          <Play size={14} />
        </button>
      </div>
    </div>
  );
};
