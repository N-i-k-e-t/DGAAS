import React from 'react';
import { X, Mail, Phone, MapPin, Copy, Send, CheckCircle2, History, MessageSquare, Star } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export const LeadDrawer = ({ lead, isOpen, onClose }: { lead: any; isOpen: boolean; onClose: () => void }) => {
  if (!lead) return null;

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[60]"
          />
          
          {/* Drawer */}
          <motion.div 
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="fixed top-0 right-0 h-full w-full max-w-md bg-card border-l border-white/10 z-[70] shadow-2xl overflow-y-auto"
          >
            <div className="p-6 space-y-8">
              {/* Header */}
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="text-2xl font-bold">{lead.name}</h2>
                  <div className="flex items-center text-text-secondary text-sm mt-1">
                    <MapPin size={14} className="mr-1" />
                    {lead.city}
                  </div>
                </div>
                <button 
                  onClick={onClose}
                  className="p-2 hover:bg-white/5 rounded-full transition-colors"
                >
                  <X size={20} />
                </button>
              </div>

              {/* Status & Score */}
              <div className="flex items-center space-x-4">
                <div className="flex-1 bg-background rounded-xl p-4 border border-white/5">
                  <div className="text-[10px] text-text-secondary uppercase font-bold mb-1">AI Lead Score</div>
                  <div className="flex items-center space-x-2">
                    <span className="text-3xl font-bold text-success">{lead.ai_score}</span>
                    <div className="text-[10px] text-success bg-success/10 px-1.5 py-0.5 rounded">High Intent</div>
                  </div>
                </div>
                <div className="flex-1 bg-background rounded-xl p-4 border border-white/5">
                  <div className="text-[10px] text-text-secondary uppercase font-bold mb-1">Status</div>
                  <div className="mt-1">
                    <select className="bg-transparent text-sm font-bold text-primary focus:outline-none cursor-pointer">
                      <option value="new">NEW</option>
                      <option value="contacted">CONTACTED</option>
                      <option value="booked">BOOKED</option>
                      <option value="lost">LOST</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* Info Items */}
              <div className="space-y-4">
                <div className="flex items-center justify-between text-sm">
                  <div className="flex items-center text-text-secondary">
                    <Mail size={16} className="mr-3" />
                    <span>Email</span>
                  </div>
                  <div className="font-medium">{lead.email}</div>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <div className="flex items-center text-text-secondary">
                    <Phone size={16} className="mr-3" />
                    <span>Phone</span>
                  </div>
                  <div className="font-medium">{lead.phone || '—'}</div>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <div className="flex items-center text-text-secondary">
                    <Star size={16} className="mr-3" />
                    <span>Segment</span>
                  </div>
                  <div className="font-medium text-secondary">{lead.segment}</div>
                </div>
              </div>

              {/* AI Reasoning */}
              <div className="space-y-3">
                <div className="flex items-center space-x-2 text-sm font-bold text-text-secondary uppercase tracking-wider">
                  <MessageSquare size={16} />
                  <span>AI Agent Reasoning</span>
                </div>
                <div className="bg-background rounded-xl p-4 border border-white/5 text-sm leading-relaxed text-text-secondary">
                  {lead.ai_reasoning || "Detected life event: 'Recently promoted to VP'. High correlation with heritage travel segments. Historical conversion for this trigger is 35%."}
                </div>
              </div>

              {/* Campaign Draft */}
              <div className="space-y-3">
                <div className="text-sm font-bold text-text-secondary uppercase tracking-wider">Generated Message</div>
                <div className="relative group">
                  <div className="bg-primary/5 border border-primary/20 rounded-xl p-4 pr-12 text-sm text-text-primary italic">
                    "Hi {lead.name.split(' ')[0]}, congratulations on your recent promotion! Nasik would be the perfect place for a celebratory weekend getaway..."
                  </div>
                  <button className="absolute top-3 right-3 p-2 bg-white/5 hover:bg-white/10 rounded-lg transition-all opacity-0 group-hover:opacity-100">
                    <Copy size={16} />
                  </button>
                </div>
                <div className="flex gap-2">
                  <button className="flex-1 btn-primary py-2.5 flex items-center justify-center space-x-2">
                    <Send size={16} />
                    <span>Send Message</span>
                  </button>
                  <button className="px-4 py-2.5 rounded-md border border-white/10 hover:bg-white/5 transition-all text-xs">
                    Mark as Booked
                  </button>
                </div>
              </div>

              {/* Timeline */}
              <div className="space-y-4">
                <div className="flex items-center space-x-2 text-sm font-bold text-text-secondary uppercase tracking-wider">
                  <History size={16} />
                  <span>Timeline</span>
                </div>
                <div className="space-y-4 pl-2">
                  <div className="relative pl-6 border-l border-white/10 pb-4">
                    <div className="absolute -left-[5px] top-0 w-2.5 h-2.5 rounded-full bg-primary" />
                    <div className="text-[10px] text-text-secondary uppercase">Today, 2:15 PM</div>
                    <div className="text-xs mt-1">AI Agent rescored lead from 45 to 85 based on LinkedIn event</div>
                  </div>
                  <div className="relative pl-6 border-l border-white/10">
                    <div className="absolute -left-[5px] top-0 w-2.5 h-2.5 rounded-full bg-white/20" />
                    <div className="text-[10px] text-text-secondary uppercase">Yesterday, 9:00 AM</div>
                    <div className="text-xs mt-1">Lead captured from Website Form</div>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};
