import React, { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { 
  LayoutDashboard, 
  Radar, 
  Users, 
  Megaphone, 
  LineChart, 
  Calendar, 
  Swords, 
  Database, 
  Terminal, 
  Settings,
  Menu,
  ChevronLeft
} from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const navItems = [
  { name: 'Dashboard', icon: LayoutDashboard, path: '/' },
  { name: 'Signals', icon: Radar, path: '/signals' },
  { name: 'Leads', icon: Users, path: '/leads' },
  { name: 'Campaigns', icon: Megaphone, path: '/campaigns' },
  { name: 'Forecasts', icon: LineChart, path: '/forecasts' },
  { name: 'Content Calendar', icon: Calendar, path: '/calendar' },
  { name: 'Competitors', icon: Swords, path: '/competitors' },
  { name: 'Data Hub', icon: Database, path: '/datahub' },
  { name: 'System Logs', icon: Terminal, path: '/logs' },
  { name: 'Settings', icon: Settings, path: '/settings' },
];

interface SidebarProps {
  isCollapsed: boolean;
  setIsCollapsed: (collapsed: boolean) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ isCollapsed, setIsCollapsed }) => {

  return (
    <aside 
      className={cn(
        "fixed left-0 top-0 h-screen bg-card border-r border-white/5 transition-all duration-300 z-50",
        isCollapsed ? "w-16" : "w-60"
      )}
    >
      <div className="flex flex-col h-full">
        {/* Header */}
        <div className="h-16 flex items-center justify-between px-4 border-b border-white/5">
          {!isCollapsed && (
            <span className="text-primary font-bold text-xl tracking-tight">VayaVia</span>
          )}
          <button 
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="p-1 hover:bg-white/5 rounded-md text-text-secondary transition-colors"
          >
            {isCollapsed ? <Menu size={20} /> : <ChevronLeft size={20} />}
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-4 overflow-y-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }: { isActive: boolean }) => cn(
                "flex items-center px-4 py-3 text-sm font-medium transition-all group",
                isActive 
                  ? "bg-primary/10 text-primary border-r-2 border-primary" 
                  : "text-text-secondary hover:text-text-primary hover:bg-white/5"
              )}
            >
              <item.icon 
                size={20} 
                className={cn(
                  "flex-shrink-0 transition-colors",
                  isCollapsed ? "mx-auto" : "mr-3"
                )} 
              />
              {!isCollapsed && <span>{item.name}</span>}
              {!isCollapsed && (
                <div className="absolute left-0 w-1 h-8 bg-primary rounded-r-full opacity-0 group-hover:opacity-100 transition-opacity" />
              )}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-white/5">
          <div className={cn(
            "flex items-center text-xs text-text-secondary bg-background rounded-lg p-2 transition-all",
            isCollapsed && "justify-center"
          )}>
            <div className="w-2 h-2 rounded-full bg-success animate-pulse mr-2" />
            {!isCollapsed && <span>System Online</span>}
          </div>
        </div>
      </div>
    </aside>
  );
};
