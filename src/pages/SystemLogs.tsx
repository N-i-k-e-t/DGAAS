import { useLiveQuery } from 'dexie-react-hooks';
import { db } from '../db/database';
import type { WorkflowLog } from '../db/database';
import { Terminal, Cpu, Database, Wifi, Shield, RefreshCw, Search, ChevronRight } from 'lucide-react';
import { useState } from 'react';

const StatusCard = ({ title, value, status, icon: Icon }: any) => (
  <div className="card flex items-center space-x-4">
    <div className={`p-3 rounded-xl ${status === 'online' ? 'bg-success/10 text-success' : 'bg-danger/10 text-danger'}`}>
      <Icon size={24} />
    </div>
    <div>
      <div className="text-[10px] text-text-secondary uppercase font-bold">{title}</div>
      <div className="text-lg font-bold flex items-center">
        {value}
        <div className={`w-2 h-2 rounded-full ml-3 ${status === 'online' ? 'bg-success animate-pulse' : 'bg-danger'}`} />
      </div>
    </div>
  </div>
);

export default function SystemLogs() {
  const [selectedLog, setSelectedLog] = useState<WorkflowLog | null>(null);
  const logs = useLiveQuery(() => db.workflow_logs.reverse().toArray()) || [];

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-text-primary">System Logs</h2>
          <p className="text-sm text-text-secondary">Monitor background engine processes, n8n workflows, and VPS health.</p>
        </div>
        <button className="flex items-center space-x-2 bg-white/5 px-4 py-2 rounded-md border border-white/5 text-xs hover:bg-white/10 transition-all">
          <RefreshCw size={14} />
          <span>Refresh All Status</span>
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatusCard title="n8n Engine" value="Connected" status="online" icon={Wifi} />
        <StatusCard title="Ollama AI" value="Llama 3.1" status="online" icon={Cpu} />
        <StatusCard title="PostgreSQL" status="online" value="Active Hub" icon={Database} />
        <StatusCard title="System Load" value="Balanced" status="online" icon={Shield} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-10 gap-6">
        <div className="lg:col-span-7 space-y-4">
          <div className="card p-0 overflow-hidden">
            <div className="p-4 border-b border-white/5 flex items-center justify-between bg-white/[0.02]">
              <h3 className="font-semibold flex items-center space-x-2">
                <Terminal size={18} className="text-primary" />
                <span>Workflow Execution History</span>
              </h3>
              <div className="relative">
                <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-secondary" />
                <input type="text" placeholder="Filter logs..." className="bg-background border border-white/10 rounded-md pl-8 pr-3 py-1 text-xs focus:outline-none" />
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-white/5 text-text-secondary uppercase font-medium">
                  <tr>
                    <th className="px-6 py-3">Workflow Name</th>
                    <th className="px-6 py-3">Status</th>
                    <th className="px-6 py-3">Duration</th>
                    <th className="px-6 py-3">Started At</th>
                    <th className="px-6 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {logs.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-6 py-10 text-center text-text-secondary italic">
                        No logs recorded yet. Run a workflow from the Quick Actions menu.
                      </td>
                    </tr>
                  ) : (
                    logs.map((log) => (
                      <tr 
                        key={log.id} 
                        onClick={() => setSelectedLog(log)}
                        className={`hover:bg-white/[0.04] transition-colors cursor-pointer ${selectedLog?.id === log.id ? 'bg-primary/5' : ''}`}
                      >
                        <td className="px-6 py-4 font-medium">{log.workflow_name}</td>
                        <td className="px-6 py-4">
                          <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase border ${
                            log.status === 'success' ? 'bg-success/10 text-success border-success/20' : 'bg-danger/10 text-danger border-danger/20'
                          }`}>
                            {log.status}
                          </span>
                        </td>
                        <td className="px-6 py-4 font-mono text-text-secondary">{log.duration_ms}ms</td>
                        <td className="px-6 py-4 text-text-secondary">{log.started_at}</td>
                        <td className="px-6 py-4 text-right">
                           <ChevronRight size={14} className="ml-auto text-text-secondary" />
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div className="lg:col-span-3 card flex flex-col h-full bg-background border-primary/20">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-2 text-primary">
              <Terminal size={18} />
              <h3 className="font-bold">Raw Log Viewer</h3>
            </div>
            {selectedLog && (
              <span className="text-[10px] bg-primary/10 text-primary px-2 py-0.5 rounded uppercase font-bold">
                {selectedLog.workflow_name}
              </span>
            )}
          </div>
          <div className="flex-1 bg-black/40 rounded-lg p-3 font-mono text-[11px] text-primary/80 overflow-y-auto space-y-2 whitespace-pre-wrap leading-relaxed custom-scrollbar">
            {selectedLog ? (
              <>
                <div className="text-primary/50 text-[9px] border-b border-white/5 pb-2 mb-2">
                  ID: {selectedLog.id} | START: {selectedLog.started_at}
                </div>
                {selectedLog.logs}
                {selectedLog.status === 'success' && <div className="text-success mt-1">--- SUCCESS: WORKFLOW COMPLETE ---</div>}
                {selectedLog.status === 'error' && <div className="text-danger mt-1">--- FAILED: EXECUTION CRASHED ---</div>}
              </>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-center opacity-40">
                 <Terminal size={32} className="mb-4" />
                 <p className="text-[10px] uppercase tracking-widest font-bold">Select a workflow execution<br/>to view detailed logs</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
