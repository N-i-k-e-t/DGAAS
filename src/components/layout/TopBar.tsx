import React from 'react';
import { Bell, Search, User, Cloud, Wifi, Database as DbIcon } from 'lucide-react';

interface TopBarProps {
  isSidebarCollapsed: boolean;
}

export const TopBar: React.FC<TopBarProps> = ({ isSidebarCollapsed }) => {
  return (
    <header className="h-16 fixed top-0 right-0 left-0 bg-background/80 backdrop-blur-md border-b border-white/5 z-40">
      <div className={`h-full flex items-center justify-between px-6 transition-all duration-300 ${isSidebarCollapsed ? 'ml-16' : 'ml-60'}`}>
        <div className="flex items-center space-x-4">
          <h1 className="text-lg font-semibold text-text-primary hidden md:block">
            VayaVia Demand Engine
          </h1>
          <div className="h-4 w-px bg-white/10 hidden md:block" />
          <div className="flex items-center space-x-3 text-xs text-text-secondary">
            <div className="flex items-center space-x-1.5">
              <Cloud size={14} className="text-success" />
              <span>Weather API: OK</span>
            </div>
            <div className="flex items-center space-x-1.5">
              <Wifi size={14} className="text-success" />
              <span>n8n: Connected</span>
            </div>
            <div className="flex items-center space-x-1.5">
              <DbIcon size={14} className="text-success" />
              <span>DB: Local+VPS</span>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-4">
          <div className="relative group hidden sm:block">
            <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary group-focus-within:text-primary transition-colors" />
            <input 
              type="text" 
              placeholder="Search demand signals..." 
              className="bg-card border border-white/5 rounded-full pl-10 pr-4 py-1.5 text-sm focus:outline-none focus:border-primary/50 transition-all w-64"
            />
          </div>

          <button className="relative p-2 hover:bg-white/5 rounded-full transition-colors text-text-secondary hover:text-text-primary">
            <Bell size={20} />
            <span className="absolute top-1 right-1 w-2 h-2 bg-primary rounded-full" />
          </button>

          <div className="flex items-center space-x-2 pl-2 cursor-pointer group">
            <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-primary group-hover:bg-primary/30 transition-colors">
              <User size={18} />
            </div>
            <div className="hidden lg:block">
              <div className="text-xs font-medium text-text-primary leading-none">Admin User</div>
              <div className="text-[10px] text-text-secondary">System Configurator</div>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};
