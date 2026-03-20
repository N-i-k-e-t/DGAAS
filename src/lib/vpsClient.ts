const VPS_API = import.meta.env.VITE_VPS_API_URL || '/vps';

export interface VpsSignal {
  id: number;
  raw_signal_id: number;
  segment: string;
  score: number;
  urgency: string;
  created_at: string;
}

export interface VpsLead {
  id: number;
  signal_id: number;
  segment: string;
  score: number;
  urgency: string;
  platform: string;
  handle: string;
  ai_message: string;
  original_url: string;
  created_at: string;
  status: string;
}

export interface VpsStats {
  total_signals: number;
  total_leads: number;
  hot_leads: number;
  recent_signals_24h: number;
  top_segments: Array<{ segment: string; cnt: number }>;
}

async function fetchVps<T>(endpoint: string): Promise<T> {
  const res = await fetch(`${VPS_API}/${endpoint}`);
  if (!res.ok) throw new Error(`VPS API error: ${res.status}`);
  return res.json();
}

export const vpsClient = {
  getHealth: () => fetchVps<{ status: string; signals: number; leads: number; ts: string }>('health'),
  getStats: () => fetchVps<VpsStats>('stats'),
  getSignals: async (limit = 50): Promise<VpsSignal[]> => {
    const res = await fetchVps<{ data: VpsSignal[]; count: number }>(`signals?limit=${limit}`);
    return res.data || [];
  },
  getLeads: async (limit = 50): Promise<VpsLead[]> => {
    const res = await fetchVps<{ data: VpsLead[]; count: number }>(`leads?limit=${limit}`);
    return res.data || [];
  },
};
