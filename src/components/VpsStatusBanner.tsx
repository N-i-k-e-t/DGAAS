import { useState, useEffect } from 'react';
import { syncVpsToLocal } from '../lib/vpsSync';
import { Activity, AlertCircle, CheckCircle, RefreshCw } from 'lucide-react';

export function VpsStatusBanner() {
  const [status, setStatus] = useState<'idle' | 'syncing' | 'success' | 'error'>('idle');
  const [lastSync, setLastSync] = useState<string | null>(null);
  const [syncCount, setSyncCount] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const doSync = async () => {
    setStatus('syncing');
    setError(null);
    try {
      const result = await syncVpsToLocal();
      if (result.error) {
        setStatus('error');
        setError(result.error);
      } else {
        setStatus('success');
        setSyncCount(result.synced);
        setLastSync(new Date().toLocaleTimeString());
      }
    } catch (e: any) {
      setStatus('error');
      setError(e.message);
    }
  };

  useEffect(() => {
    doSync();
    const interval = setInterval(doSync, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  const statusConfig = {
    idle: { icon: Activity, color: 'bg-gray-100 text-gray-600', label: 'VPS Idle' },
    syncing: { icon: RefreshCw, color: 'bg-blue-100 text-blue-700', label: 'Syncing VPS...' },
    success: { icon: CheckCircle, color: 'bg-green-100 text-green-700', label: `Synced ${syncCount} items` },
    error: { icon: AlertCircle, color: 'bg-red-100 text-red-700', label: 'Sync Failed' },
  };

  const config = statusConfig[status];
  const Icon = config.icon;

  return (
    <div className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium ${config.color}`}>
      <Icon className={`w-4 h-4 ${status === 'syncing' ? 'animate-spin' : ''}`} />
      <span>{config.label}</span>
      {lastSync && <span className="text-xs opacity-70">Last: {lastSync}</span>}
      {error && <span className="text-xs opacity-70">{error}</span>}
      <button
        onClick={doSync}
        disabled={status === 'syncing'}
        className="ml-auto text-xs underline opacity-70 hover:opacity-100"
      >
        Refresh
      </button>
    </div>
  );
}
