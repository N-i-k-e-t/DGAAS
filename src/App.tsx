import React, { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { Sidebar } from './components/layout/Sidebar';
import { TopBar } from './components/layout/TopBar';
import { VpsStatusBanner } from './components/VpsStatusBanner';
import { seedData, clearData } from './db/seed';
import { Dashboard } from './pages/Dashboard';
import Signals from './pages/Signals';
import Leads from './pages/Leads';
import Campaigns from './pages/Campaigns';
import DataHub from './pages/DataHub';
import Forecasts from './pages/Forecasts';
import ContentCalendar from './pages/ContentCalendar';
import Competitors from './pages/Competitors';
import SystemLogs from './pages/SystemLogs';
import Settings from './pages/Settings';

function App() {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = React.useState(false);

  useEffect(() => {
        const init = async () => {
      const cleaned = localStorage.getItem('v2_cleaned');
      if (!cleaned) {
        await clearData();
        localStorage.setItem('v2_cleaned', 'true');
      }
      await seedData();
    };
    init();
  }, []);

  return (
    <Router>
      <div className="flex min-h-screen bg-background text-text-primary">
        <Sidebar isCollapsed={isSidebarCollapsed} setIsCollapsed={setIsSidebarCollapsed} />
        <div className={`flex-1 flex flex-col transition-all duration-300 ${isSidebarCollapsed ? 'pl-16' : 'pl-60'}`}>
          <TopBar isSidebarCollapsed={isSidebarCollapsed} />
          <div className="mt-16 px-4 py-2">
            <VpsStatusBanner />
          </div>
          <main className="flex-1 overflow-auto">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/signals" element={<Signals />} />
              <Route path="/leads" element={<Leads />} />
              <Route path="/campaigns" element={<Campaigns />} />
              <Route path="/forecasts" element={<Forecasts />} />
              <Route path="/calendar" element={<ContentCalendar />} />
              <Route path="/competitors" element={<Competitors />} />
              <Route path="/datahub" element={<DataHub />} />
              <Route path="/logs" element={<SystemLogs />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </main>
        </div>
      </div>
    </Router>
  );
}

export default App;
