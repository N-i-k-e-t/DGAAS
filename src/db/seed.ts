import { db } from './database';

export const clearData = async () => {
  const tables = [
    db.travel_agents,
    db.nashik_tourism_db,
    db.coworking_startups,
    db.travel_influencers,
    db.competitors,
    db.listing_platforms,
    db.remote_startups,
    db.spiritual_sites,
    db.events_2026,
    db.nomad_communities,
    db.property_listings,
    db.travel_pr_journalists,
    db.wedding_event_planners,
    db.nashik_content_creators,
    db.maharashtra_tourism_govt,
    db.family_mom_influencers,
    db.photo_video_drone,
    db.bus_operators,
    db.wellness_yoga_retreats,
    db.real_estate_developers,
    db.demand_signals,
    db.leads,
    db.workflow_logs,
    db.campaign_logs,
    db.decision_logs
  ];
  for (const table of tables) {
    await table.clear();
  }
  console.log('Database cleared of all data.');
};

export const seedData = async () => {
  // Only seed campaign templates (structural data, not fake signals/leads)
  const campaignCount = await db.campaigns.count();
  if (campaignCount === 0) {
    await db.campaigns.bulkAdd([
      { name: "Pollution Escape", trigger: "AQI > 200 in feeder cities", status: "armed", is_active: true, cooldown_hours: 72, email_template: "<h1>Pollution Escape</h1><p>Hi {name}, escape the smog of {city} and breathe fresh in Nashik!</p>", whatsapp_template: "Hi {name}, the AQI in {city} is high today. Escape to Nashik for a fresh weekend!" },
      { name: "Clear Weekend Push", trigger: "Clear weekend forecast + 22-30\u00b0C", status: "armed", is_active: true, cooldown_hours: 168, email_template: "<h1>Perfect Weekend Ahead!</h1><p>Hi {name}, Nashik weather is beautiful this weekend.</p>", whatsapp_template: "Hi {name}, beautiful weather in Nashik this weekend! Ready for a wine tour?" },
      { name: "Trend Spike Alert", trigger: "Keyword volume > 30% WoW", status: "armed", is_active: true, cooldown_hours: 48, email_template: "<h1>Trending in Nashik</h1><p>Hi {name}, Nashik is trending! Book your stay now.</p>", whatsapp_template: "Hi {name}, Nashik is the place to be this weekend! Don't miss out." },
      { name: "Competitor Sellout", trigger: ">80% city occupancy", status: "armed", is_active: true, cooldown_hours: 120, email_template: "<h1>Hurry! Almost Sold Out</h1><p>Hi {name}, Nashik is filling up fast.</p>", whatsapp_template: "Hi {name}, only a few properties left in Nashik for this weekend!" }
    ]);
  }
  // No fake signals or leads are seeded - only real data from VPS sync
  console.log('Campaign templates initialized. No mock data seeded.');
};
