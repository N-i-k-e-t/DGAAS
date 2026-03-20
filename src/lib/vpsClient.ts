const VPS_API = import.meta.env.VITE_VPS_API_URL || 'http://46.202.160.119/api';

export interface VpsSignal {
  id: number;
  source_site: string;
  url: string;
  text_snippet: string;
  found_at: string;
  classified: boolean;
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
}

export interface VpsStats {
  total_signals: number;
  total_leads: number;
  hot_leads: number;
  by_source: Record<string, number>;
  by_segment: Record<string, number>;
}

async function fetchVps<T>(endpoint: string): Promise<T> {
  const res = await fetch(`${VPS_API}/${endpoint}`);
  if (!res.ok) throw new Error(`VPS API error: ${res.status}`);
  return res.json();
}

export const vpsClient = {
  getHealth: () => fetchVps<{ status: string; db_ok: boolean; signals: number; leads: number }>('health'),
  getStats: () => fetchVps<VpsStats>('stats'),
  getSignals: (limit = 50) => fetchVps<VpsSignal[]>(`signals?limit=${limit}`),
  getLeads: (limit = 50) => fetchVps<VpsLead[]>(`leads?limit=${limit}`),
};
