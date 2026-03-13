import { useState } from 'react';
import { 
  Server, 
  Key, 
  Webhook, 
  Database, 
  Save, 
  RefreshCw,
  Trash2,
  FileJson
} from 'lucide-react';

const ConfigSection = ({ title, icon: Icon, children }: any) => (
  <div className="card space-y-6">
    <div className="flex items-center space-x-2 border-b border-white/5 pb-4">
      <Icon size={18} className="text-primary" />
      <h3 className="font-bold">{title}</h3>
    </div>
    <div className="space-y-4">
      {children}
    </div>
  </div>
);

const InputField = ({ label, placeholder, type = "text", value }: any) => (
  <div className="space-y-1.5">
    <label className="text-[10px] font-bold text-text-secondary uppercase tracking-wider px-1">{label}</label>
    <div className="relative">
      <input 
        type={type} 
        placeholder={placeholder} 
        defaultValue={value}
        className="w-full bg-background border border-white/10 rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-primary/50 transition-all font-mono"
      />
    </div>
  </div>
);

export default function Settings() {
  const [activeTab, setActiveTab] = useState('connection');

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-text-primary">System Settings</h2>
          <p className="text-sm text-text-secondary">Configure VPS connections, API keys, and data synchronization.</p>
        </div>
        <button className="btn-primary flex items-center space-x-2 px-6">
          <Save size={18} />
          <span>Save Changes</span>
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Navigation */}
        <div className="lg:col-span-3 space-y-1">
          {[
            { id: 'connection', label: 'VPS Connection', icon: Server },
            { id: 'api', label: 'API Keys', icon: Key },
            { id: 'webhooks', label: 'Webhook Endpoints', icon: Webhook },
            { id: 'data', label: 'Data Management', icon: Database },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`w-full flex items-center space-x-3 px-4 py-3 rounded-lg text-sm font-medium transition-all ${
                activeTab === tab.id ? 'bg-primary/10 text-primary border border-primary/20' : 'text-text-secondary hover:bg-white/5'
              }`}
            >
              <tab.icon size={18} />
              <span>{tab.label}</span>
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="lg:col-span-9 space-y-6">
          {activeTab === 'connection' && (
            <ConfigSection title="VPS Connection" icon={Server}>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <InputField label="n8n Base URL" value="https://n8n.vayavia.com" placeholder="https://..." />
                <InputField label="Webhook Auth Token" type="password" value="••••••••••••••••" />
              </div>
              <div className="flex items-center justify-between p-4 bg-background border border-white/5 rounded-xl mt-4">
                <div className="flex items-center space-x-3">
                  <div className="w-2 h-2 rounded-full bg-success" />
                  <span className="text-sm font-medium">Connection Status: <span className="text-success">Verified</span></span>
                </div>
                <button className="text-xs text-primary hover:underline flex items-center">
                  <RefreshCw size={12} className="mr-1" />
                  Test Connection
                </button>
              </div>
            </ConfigSection>
          )}

          {activeTab === 'api' && (
            <ConfigSection title="External API Keys" icon={Key}>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <InputField label="OpenWeatherMap Key" value="ow_742...912" />
                <InputField label="IQAir API Key" value="iq_104...482" />
                <InputField label="SerpApi Key" value="sa_002...115" />
                <InputField label="Clay API Key" value="cl_882...104" />
                <InputField label="Google Analytics ID" value="G-4R92..." />
              </div>
              <p className="text-[10px] text-text-secondary italic">Keys are encrypted and stored in your browser's localStorage.</p>
            </ConfigSection>
          )}

          {activeTab === 'webhooks' && (
            <ConfigSection title="Webhook Endpoints" icon={Webhook}>
              <div className="space-y-2">
                {[
                  { path: '/webhook/trigger-campaign', method: 'POST', status: 200 },
                  { path: '/webhook/rescore-lead', method: 'POST', status: 200 },
                  { path: '/webhook/force-weather-check', method: 'GET', status: 401 },
                  { path: '/webhook/get-signals', method: 'GET', status: 200 },
                ].map(hook => (
                  <div key={hook.path} className="flex items-center justify-between p-3 bg-background border border-white/5 rounded-lg hover:border-white/10 transition-colors group">
                    <div className="flex items-center space-x-3">
                      <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${hook.method === 'POST' ? 'bg-primary/20 text-primary' : 'bg-blue-500/20 text-blue-400'}`}>
                        {hook.method}
                      </span>
                      <span className="text-xs font-mono text-text-secondary group-hover:text-text-primary">{hook.path}</span>
                    </div>
                    <div className={`text-xs font-bold ${hook.status === 200 ? 'text-success' : 'text-danger'}`}>
                      {hook.status}
                    </div>
                  </div>
                ))}
              </div>
            </ConfigSection>
          )}

          {activeTab === 'data' && (
            <ConfigSection title="Data Management" icon={Database}>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <button className="flex flex-col items-start p-4 bg-background border border-white/5 rounded-xl hover:border-primary/30 transition-all group">
                  <div className="flex items-center space-x-2 text-primary mb-1">
                    <FileJson size={18} />
                    <span className="font-bold text-sm">Export All Data</span>
                  </div>
                  <p className="text-[10px] text-text-secondary text-left">Downloads a full JSON backup of your local IndexedDB database including all 45 tables.</p>
                </button>
                <button className="flex flex-col items-start p-4 bg-background border border-white/5 rounded-xl hover:border-primary/30 transition-all group">
                  <div className="flex items-center space-x-2 text-primary mb-1">
                    <RefreshCw size={18} />
                    <span className="font-bold text-sm">Full System Sync</span>
                  </div>
                  <p className="text-[10px] text-text-secondary text-left">Triggers a manual sync with the VPS to refresh all live engine tables.</p>
                </button>
                <button className="flex flex-col items-start p-4 bg-background border border-white/5 rounded-xl hover:border-danger/30 transition-all group lg:col-span-2">
                  <div className="flex items-center space-x-2 text-danger mb-1">
                    <Trash2 size={18} />
                    <span className="font-bold text-sm">Reset Local Database</span>
                  </div>
                  <p className="text-[10px] text-text-secondary text-left">Clears all data from the browser storage. This action cannot be undone.</p>
                </button>
              </div>
            </ConfigSection>
          )}
        </div>
      </div>
    </div>
  );
}
