import { useState, useEffect, useCallback } from 'react';
import { db } from '../db/database';
import { useLiveQuery } from 'dexie-react-hooks';
import { vpsClient } from '../lib/vpsClient';

export function useVpsData() {
  const [vpsStatus, setVpsStatus] = useState<'online' | 'offline' | 'checking'>('checking');
  const [lastCheck, setLastCheck] = useState<Date | null>(null);

  const signals = useLiveQuery(() => db.demand_signals.orderBy('timestamp').reverse().limit(50).toArray(), []);
  const leads = useLiveQuery(() => db.leads.orderBy('created_at').reverse().limit(50).toArray(), []);

  const checkVpsHealth = useCallback(async () => {
    setVpsStatus('checking');
    try {
      const res = await vpsClient.getHealth();
      setVpsStatus(res.status === 200 ? 'online' : 'offline');
    } catch {
      setVpsStatus('offline');
    }
    setLastCheck(new Date());
  }, []);

  useEffect(() => {
    checkVpsHealth();
    const interval = setInterval(checkVpsHealth, 60 * 1000);
    return () => clearInterval(interval);
  }, [checkVpsHealth]);

  const stats = {
    totalSignals: signals?.length || 0,
    totalLeads: leads?.length || 0,
    highScoreLeads: leads?.filter(l => l.ai_score >= 70).length || 0,
    recentSignals: signals?.filter(s => {
      const h24 = new Date(Date.now() - 24 * 60 * 60 * 1000);
      return new Date(s.timestamp) > h24;
    }).length || 0,
  };

  return {
    vpsStatus,
    lastCheck,
    signals: signals || [],
    leads: leads || [],
    stats,
    checkVpsHealth,
  };
}
