import { db } from '../db/database';
import { vpsClient } from './vpsClient';

export async function syncVpsToLocal(): Promise<{ synced: number; error?: string }> {
  try {
    const [signals, leads] = await Promise.all([
      vpsClient.getSignals(200),
      vpsClient.getLeads(200),
    ]);

    let added = 0;

    for (const sig of signals) {
      const existing = await db.demand_signals.where('timestamp').equals(sig.found_at).first();
      if (!existing) {
        await db.demand_signals.add({
          timestamp: sig.found_at,
          signal_type: 'social_mention',
          source: sig.source_site,
          urgency: 'medium',
          target_segment: 'Wine Enthusiast',
          campaign_triggered: false,
          raw_data: { url: sig.url, snippet: sig.text_snippet },
          ai_classification: { classified: sig.classified },
        });
        added++;
      }
    }

    for (const ld of leads) {
      const existing = await db.leads.where('email').equals(`vps-${ld.id}@signal`).first();
      if (!existing) {
        await db.leads.add({
          source: ld.platform || 'reddit',
          name: ld.handle || `Lead #${ld.id}`,
          email: `vps-${ld.id}@signal`,
          phone: '',
          city: 'Nashik',
          life_event: ld.segment,
          ai_score: ld.score,
          ai_reasoning: ld.ai_message || `Score: ${ld.score}, Urgency: ${ld.urgency}`,
          segment: ld.segment,
          status: ld.score >= 70 ? 'new' : 'nurturing',
          created_at: ld.created_at,
        });
        added++;
      }
    }

    return { synced: added };
  } catch (e: any) {
    return { synced: 0, error: e.message };
  }
}
