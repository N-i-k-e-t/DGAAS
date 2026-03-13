import { db } from './database';

export const seedData = async () => {
  // 1. Seed Campaigns (Real scenarios from PDF)
  const campaignCount = await db.campaigns.count();
  if (campaignCount === 0) {
    await db.campaigns.bulkAdd([
      { name: "Pollution Escape", trigger: "AQI > 200 in feeder cities", status: "armed", is_active: true, cooldown_hours: 72, email_template: "<h1>Pollution Escape</h1><p>Hi {name}, escape the smog of {city} and breathe fresh in Nashik!</p>", whatsapp_template: "Hi {name}, the AQI in {city} is high today. Escape to Nashik for a fresh weekend!" },
      { name: "Clear Weekend Push", trigger: "Clear weekend forecast + 22-30°C", status: "armed", is_active: true, cooldown_hours: 168, email_template: "<h1>Perfect Weekend Ahead!</h1><p>Hi {name}, Nashik weather is beautiful this weekend.</p>", whatsapp_template: "Hi {name}, beautiful weather in Nashik this weekend! Ready for a wine tour?" },
      { name: "Trend Spike Alert", trigger: "Keyword volume > 30% WoW", status: "armed", is_active: true, cooldown_hours: 48, email_template: "<h1>Trending in Nashik</h1><p>Hi {name}, Nashik is trending! Book your stay now.</p>", whatsapp_template: "Hi {name}, Nashik is the place to be this weekend! Don't miss out." },
      { name: "Competitor Sellout", trigger: ">80% city occupancy", status: "armed", is_active: true, cooldown_hours: 120, email_template: "<h1>Hurry! Almost Sold Out</h1><p>Hi {name}, Nashik is filling up fast.</p>", whatsapp_template: "Hi {name}, only a few properties left in Nashik for this weekend!" }
    ]);
  }

  // 2. Seed some "Real" Leads (Aligned with Lead interface)
  const leadCount = await db.leads.count();
  if (leadCount === 0) {
    await db.leads.bulkAdd([
      { 
        name: "Amit Sharma", city: "Delhi", phone: "98102XXXXX", email: "amit.s@gmail.com", source: "Instagram", 
        ai_score: 92, status: "new", created_at: new Date().toISOString(), 
        life_event: "Pollution spike", ai_reasoning: "High intent due to AQI in Delhi", segment: "Family"
      },
      { 
        name: "Priya Iyer", city: "Mumbai", phone: "98700XXXXX", email: "priya.i@outlook.com", source: "Website", 
        ai_score: 88, status: "contacted", created_at: new Date().toISOString(),
        life_event: "Weekend getaway", ai_reasoning: "Frequent visitor", segment: "Couple"
      },
      { 
        name: "Rahul Verma", city: "Pune", phone: "91234XXXXX", email: "rahul.v@company.com", source: "LinkedIn", 
        ai_score: 95, status: "new", created_at: new Date().toISOString(),
        life_event: "Corporate retreat", ai_reasoning: "High budget potential", segment: "Corporate"
      }
    ]);
  }

  // 3. Seed "Real" Demand Signals (Aligned with DemandSignal interface)
  const signalCount = await db.demand_signals.count();
  if (signalCount === 0) {
    await db.demand_signals.bulkAdd([
      { 
        signal_type: "weather", source: "OpenWeather", urgency: "critical", timestamp: new Date().toISOString(),
        target_segment: "Delhi NCR", campaign_triggered: true, 
        raw_data: { aqi: 340 }, ai_classification: { mood: "escapism", intent: "high" }
      },
      { 
        signal_type: "trend", source: "Google Trends", urgency: "medium", timestamp: new Date().toISOString(),
        target_segment: "Mumbai / Pune", campaign_triggered: false,
        raw_data: { spike: "30% WoW" }, ai_classification: { mood: "curiosity", intent: "medium" }
      },
      { 
        signal_type: "competitor", source: "SerpApi", urgency: "high", timestamp: new Date().toISOString(),
        target_segment: "General", campaign_triggered: true,
        raw_data: { occupancy: "95%" }, ai_classification: { mood: "urgency", intent: "high" }
      }
    ]);
  }

  // 4. Seed status logs (Aligned with WorkflowLog interface)
  const logCount = await db.workflow_logs.count();
  if (logCount === 0) {
    await db.workflow_logs.bulkAdd([
      { workflow_name: "Weather Monitor", status: "success", duration_ms: 450, started_at: new Date().toISOString(), logs: "Checked Delhi, Mumbai, Pune. Triggered Delhi campaign." },
      { workflow_name: "Lead Scorer", status: "success", duration_ms: 1200, started_at: new Date().toISOString(), logs: "Processed 15 new leads. 3 flagged as 'Critical'." }
    ]);
  }
};
