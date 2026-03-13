import React, { useState } from 'react';
import { Calendar as CalendarIcon, Filter, List, Grid, ChevronLeft, ChevronRight, Mail, MessageSquare, Instagram, Facebook, Twitter } from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const months = ['March 2026', 'April 2026'];

const contentItems = [
  { day: 15, platform: 'Instagram', type: 'Reel', title: 'Pollution Escape Story', color: 'pink' },
  { day: 15, platform: 'LinkedIn', type: 'Article', title: 'Why Nashik is the New Nomad Hub', color: 'blue' },
  { day: 16, platform: 'Twitter', type: 'Thread', title: 'Best Wine Tours for Weekends', color: 'cyan' },
  { day: 18, platform: 'Facebook', type: 'Image', title: 'Property of the Week: Villa 42', color: 'navy' },
  { day: 20, platform: 'Email', type: 'Newsletter', title: 'March Demand Report', color: 'purple' },
];

export default function ContentCalendar() {
  const [view, setView] = useState<'month' | 'list'>('month');

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-text-primary">Marketing Content Calendar</h2>
          <p className="text-sm text-text-secondary">Orchestrate multi-channel campaigns based on demand signals.</p>
        </div>
        <div className="flex items-center space-x-2 bg-card border border-white/5 p-1 rounded-lg">
          <button 
            onClick={() => setView('month')}
            className={cn("p-2 rounded-md transition-all", view === 'month' ? 'bg-primary text-white' : 'text-text-secondary hover:text-text-primary')}
          >
            <Grid size={18} />
          </button>
          <button 
            onClick={() => setView('list')}
            className={cn("p-2 rounded-md transition-all", view === 'list' ? 'bg-primary text-white' : 'text-text-secondary hover:text-text-primary')}
          >
            <List size={18} />
          </button>
        </div>
      </div>

      <div className="flex items-center justify-between bg-card border border-white/5 p-4 rounded-xl">
        <div className="flex items-center space-x-4">
          <button className="p-2 hover:bg-white/5 rounded-full transition-colors">
            <ChevronLeft size={20} />
          </button>
          <h3 className="text-lg font-bold">{months[0]}</h3>
          <button className="p-2 hover:bg-white/5 rounded-full transition-colors">
            <ChevronRight size={20} />
          </button>
        </div>
        <div className="flex items-center space-x-2">
          <select className="bg-background border border-white/10 rounded-md px-3 py-1.5 text-xs focus:outline-none">
            <option>All Platforms</option>
            <option>Instagram</option>
            <option>LinkedIn</option>
            <option>Email</option>
          </select>
          <button className="btn-primary text-xs flex items-center space-x-2 px-3 py-1.5 rounded-md">
            <Plus size={14} />
            <span>Schedule Post</span>
          </button>
        </div>
      </div>

      {view === 'month' ? (
        <div className="grid grid-cols-7 gap-px bg-white/5 border border-white/5 rounded-xl overflow-hidden">
          {days.map(day => (
            <div key={day} className="bg-white/[0.02] p-4 text-xs font-bold text-center text-text-secondary uppercase">
              {day}
            </div>
          ))}
          {Array.from({ length: 31 }).map((_, i) => (
            <div key={i} className="bg-card min-h-[140px] p-2 space-y-2 border-t border-white/5">
              <div className="text-xs font-medium text-text-secondary">{i + 1}</div>
              {contentItems.filter(item => item.day === i + 1).map((item, idx) => (
                <div key={idx} className={cn(
                  "px-2 py-1 rounded text-[10px] font-bold border truncate cursor-pointer hover:scale-105 transition-transform",
                  item.color === 'pink' ? 'bg-pink-500/10 text-pink-400 border-pink-500/20' :
                  item.color === 'blue' ? 'bg-blue-500/10 text-blue-400 border-blue-500/20' :
                  item.color === 'cyan' ? 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20' :
                  item.color === 'navy' ? 'bg-blue-900/40 text-blue-200 border-blue-800/20' :
                  'bg-purple-500/10 text-purple-400 border-purple-500/20'
                )}>
                  {item.platform}: {item.title}
                </div>
              ))}
            </div>
          ))}
        </div>
      ) : (
        <div className="card p-0">
          <table className="w-full text-left text-sm">
            <thead className="bg-white/5 text-text-secondary uppercase text-xs">
              <tr>
                <th className="px-6 py-3 font-medium">Date</th>
                <th className="px-6 py-3 font-medium">Platform</th>
                <th className="px-6 py-3 font-medium">Type</th>
                <th className="px-6 py-3 font-medium">Content Title</th>
                <th className="px-6 py-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {contentItems.map((item, i) => (
                <tr key={i} className="hover:bg-white/[0.02] transition-colors">
                  <td className="px-6 py-4 font-mono text-xs text-text-secondary">March {item.day}, 2026</td>
                  <td className="px-6 py-4 flex items-center space-x-2">
                    {item.platform === 'Instagram' && <Instagram size={14} className="text-pink-400" />}
                    {item.platform === 'LinkedIn' && <div className="w-3.5 h-3.5 bg-blue-600 rounded" />}
                    {item.platform === 'Twitter' && <Twitter size={14} className="text-cyan-400" />}
                    {item.platform === 'Email' && <Mail size={14} className="text-purple-400" />}
                    <span>{item.platform}</span>
                  </td>
                  <td className="px-6 py-4 text-xs">{item.type}</td>
                  <td className="px-6 py-4 font-medium">{item.title}</td>
                  <td className="px-6 py-4">
                    <span className="px-2 py-0.5 rounded-full bg-success/10 text-success text-[10px] uppercase font-bold border border-success/20">
                      Scheduled
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

const Plus = ({ size }: { size: number }) => <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>;
