import Dexie, { type Table } from 'dexie';

export interface TravelAgent {
  id?: number;
  sr_no: string;
  company_name: string;
  contact_person: string;
  phone: string;
  mobile: string;
  email: string;
  address: string;
  city: string;
  state: string;
}

export interface NashikTourism {
  id?: number;
  business_name: string;
  category: string;
  address: string;
  phone: string;
  email: string;
  website: string;
  google_rating: string;
  instagram?: string;
}

export interface CoworkingStartup {
  id?: number;
  name: string;
  type: string;
  address: string;
  phone: string;
  email: string;
  website: string;
}

export interface TravelInfluencer {
  id?: number;
  name: string;
  platform: string;
  followers: string;
  engagement_rate: string;
}

export interface Competitor {
  id?: number;
  company_name: string;
  website: string;
  founded: string;
  funding: string;
  properties_count: number;
  price_range: string;
  target_audience: string;
}

export interface DemandSignal {
  id?: number;
  timestamp: string;
  signal_type: string;
  source: string;
  urgency: 'low' | 'medium' | 'high' | 'critical';
  target_segment: string;
  campaign_triggered: boolean;
  raw_data: any;
  ai_classification: any;
}

export interface Lead {
  id?: number;
  source: string;
  name: string;
  email: string;
  phone: string;
  city: string;
  life_event: string;
  ai_score: number;
  ai_reasoning: string;
  segment: string;
  status: 'new' | 'contacted' | 'nurturing' | 'booked' | 'lost';
  created_at: string;
}

export interface Campaign {
  id?: number;
  name: string;
  trigger: string;
  status: 'armed' | 'triggered' | 'cooldown';
  is_active: boolean;
  last_triggered?: string;
  cooldown_hours: number;
  email_template: string;
  whatsapp_template: string;
}

export interface WorkflowLog {
  id?: number;
  workflow_name: string;
  status: 'success' | 'error' | 'running';
  duration_ms: number;
  started_at: string;
  logs: string;
}

export class VayaViaDB extends Dexie {
  travel_agents!: Table<TravelAgent>;
  nashik_tourism_db!: Table<NashikTourism>;
  coworking_startups!: Table<CoworkingStartup>;
  travel_influencers!: Table<TravelInfluencer>;
  competitors!: Table<Competitor>;
  listing_platforms!: Table<any>;
  remote_startups!: Table<any>;
  spiritual_sites!: Table<any>;
  events_2026!: Table<any>;
  nomad_communities!: Table<any>;
  property_listings!: Table<any>;
  travel_pr_journalists!: Table<any>;
  wedding_event_planners!: Table<any>;
  nashik_content_creators!: Table<any>;
  maharashtra_tourism_govt!: Table<any>;
  family_mom_influencers!: Table<any>;
  photo_video_drone!: Table<any>;
  bus_operators!: Table<any>;
  wellness_yoga_retreats!: Table<any>;
  real_estate_developers!: Table<any>;
  
  journey_stage1_dream!: Table<any>;
  journey_stage2_research!: Table<any>;
  journey_stage3_shortlist!: Table<any>;
  journey_stage4_compare!: Table<any>;
  journey_stage5_book!: Table<any>;
  journey_stage6_experience!: Table<any>;
  journey_stage7_advocate!: Table<any>;
  
  traveler_segments!: Table<any>;
  country_analysis!: Table<any>;
  content_strategy_50!: Table<any>;
  social_media_calendar!: Table<any>;
  email_marketing!: Table<any>;
  flight_data_tools!: Table<any>;
  life_event_triggers!: Table<any>;
  weather_data_sources!: Table<any>;
  cost_analysis!: Table<any>;
  implementation_roadmap!: Table<any>;

  demand_signals!: Table<DemandSignal>;
  leads!: Table<Lead>;
  visitor_profiles!: Table<any>;
  competitor_prices!: Table<any>;
  weekly_forecasts!: Table<any>;
  workflow_logs!: Table<WorkflowLog>;
  campaign_logs!: Table<any>;
  decision_logs!: Table<any>;
  campaigns!: Table<Campaign>;

  constructor() {
    super('VayaViaDemandEngine');
    this.version(1).stores({
      travel_agents: '++id, company_name, city, email',
      nashik_tourism_db: '++id, business_name, category',
      coworking_startups: '++id, name',
      travel_influencers: '++id, name, platform',
      competitors: '++id, company_name',
      listing_platforms: '++id, platform',
      remote_startups: '++id, company_name',
      spiritual_sites: '++id, temple_site',
      events_2026: '++id, event_name',
      nomad_communities: '++id, community_name',
      property_listings: '++id, name',
      travel_pr_journalists: '++id, name',
      wedding_event_planners: '++id, company_name',
      nashik_content_creators: '++id, creator_name',
      maharashtra_tourism_govt: '++id, department',
      family_mom_influencers: '++id, name',
      photo_video_drone: '++id, name',
      bus_operators: '++id, operator_name',
      wellness_yoga_retreats: '++id, center_name',
      real_estate_developers: '++id, developer_name',
      
      journey_stage1_dream: '++id, platform_channel',
      journey_stage2_research: '++id, search_query',
      journey_stage3_shortlist: '++id, destination',
      journey_stage4_compare: '++id, platform',
      journey_stage5_book: '++id, concern_area',
      journey_stage6_experience: '++id, touchpoint',
      journey_stage7_advocate: '++id, channel',
      
      traveler_segments: '++id, segment_name',
      country_analysis: '++id, country',
      content_strategy_50: '++id, title',
      social_media_calendar: '++id, date, platform',
      email_marketing: '++id, subject_line',
      flight_data_tools: '++id, tool_name',
      life_event_triggers: '++id, event_type',
      weather_data_sources: '++id, source',
      cost_analysis: '++id, category',
      implementation_roadmap: '++id, week',

      demand_signals: '++id, timestamp, signal_type, urgency',
      leads: '++id, source, email, ai_score, status',
      visitor_profiles: '++id, session_id',
      competitor_prices: '++id, property_name',
      weekly_forecasts: '++id, forecast_period_start',
      workflow_logs: '++id, workflow_name, status, started_at',
      campaign_logs: '++id, campaign_name',
      decision_logs: '++id, decision_type',
      campaigns: '++id, name, status, is_active'
    });
  }
}

export const db = new VayaViaDB();
