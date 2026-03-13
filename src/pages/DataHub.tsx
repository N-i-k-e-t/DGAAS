import { TableBrowser } from '../components/datahub/TableBrowser';
import { ShieldCheck, Zap } from 'lucide-react';

export default function DataHub() {
  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-text-primary">Data Intelligence Hub</h2>
          <p className="text-sm text-text-secondary">Centralized access to all 37 seed intelligence tables.</p>
        </div>
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2 text-xs text-text-secondary">
            <ShieldCheck size={14} className="text-success" />
            <span>Local Database Secured</span>
          </div>
          <div className="flex items-center space-x-2 text-xs text-text-secondary">
            <Zap size={14} className="text-success" />
            <span>IndexedDB Performance: High</span>
          </div>
        </div>
      </div>

      <TableBrowser />
    </div>
  );
}
