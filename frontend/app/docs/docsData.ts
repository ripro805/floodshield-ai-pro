export interface TeamMember {
  id: string;
  name: string;
  role: string;
  email: string;
  phone?: string;
  image?: string;
  bio?: string;
  badge?: string;
}

export interface ApiEndpointDoc {
  method: 'GET' | 'POST' | 'PUT' | 'DELETE';
  path: string;
  description: string;
  auth: string;
  paramsOrBody: string;
  sampleResponse: string;
}

export interface FeatureItem {
  name: string;
  category: 'AI/ML' | 'GIS' | 'Operations' | 'Automation';
  status: 'Live' | 'Active' | 'Planned';
  description: string;
}

export interface DocsConfig {
  visibility: 'ON' | 'OFF';
  scheduleEnabled: boolean;
  startDate: string; // ISO string
  endDate: string;   // ISO string
  allowAdminBypass: boolean;
  lastUpdated: string;
}

export interface PitchDeckContent {
  problemHeading: string;
  problemSubheading: string;
  problemBody: string;
  solutionHeading: string;
  solutionSubheading: string;
  solutionBody: string;
  tam: string;
  sam: string;
  som: string;
  visionQuote: string;
  visionBody: string;
}

export const DEFAULT_PITCH_CONTENT: PitchDeckContent = {
  problemHeading: 'A Predictable Crisis Handled Unpredictably',
  problemSubheading: 'In Bangladesh’s low-lying delta, floods arrive every monsoon season. Disease outbreaks follow the same floods almost as reliably.',
  problemBody: 'Floodwater contaminates drinking water sources, damaged sanitation spreads pathogens, families crowd into shelters, and standing water breeds mosquitoes. The result is Cholera, Acute Watery Diarrhoea, Typhoid, Hepatitis A/E, skin infections, and Dengue. The response is stubbornly reactive.',
  solutionHeading: 'From Satellite to Survival: Autonomous Multi-Hazard Early-Warning',
  solutionSubheading: 'FloodShield AI Pro is an enterprise-grade disaster management and public health intelligence platform designed for all 64 districts of Bangladesh.',
  solutionBody: 'It unites cloud-penetrating Sentinel-1 SAR satellite radar imagery, an ensemble of 6 custom Machine Learning & LSTM deep learning models, and strict Role-Based Access Control across 6 specialized stakeholder portals.',
  tam: '$12.8B',
  sam: '$1.4B',
  som: '$42M',
  visionQuote: 'Zero Preventable Deaths from Flood-Induced Disease Outbreaks by 2030',
  visionBody: 'Equipping frontline clinics, municipal water engineers, and rural community health workers with advance intelligence to turn unpredictable natural catastrophes into systematically managed, pre-mitigated events across every river basin in Bangladesh.',
};

export const DEFAULT_DOCS_CONFIG: DocsConfig = {
  visibility: 'ON',
  scheduleEnabled: false,
  startDate: '2026-06-10T00:00:00.000Z',
  endDate: '2026-06-30T23:59:59.000Z',
  allowAdminBypass: true,
  lastUpdated: new Date().toISOString(),
};

export interface StakeholderRolePitch {
  roleNumber: number;
  title: string;
  badge: string;
  color: string;
  targetAudience: string;
  summary: string;
  capabilities: { title: string; desc: string }[];
}

export const STAKEHOLDER_ROLES_PITCH: StakeholderRolePitch[] = [
  {
    roleNumber: 1,
    title: 'Citizen Public Safety Portal',
    badge: 'Public & Communities',
    color: '#38BDF8',
    targetAudience: 'General public and residents living in flood-vulnerable upazilas across all 64 districts.',
    summary: 'Direct life-safety dashboard with real-time hazard status, Bengali alerts, and one-touch hospital finding.',
    capabilities: [
      { title: 'Interactive 64-District GIS Risk Map', desc: 'Real-time color-coded flood inundation and pathogen hazard levels.' },
      { title: 'GPS Hospital Finder', desc: 'Instantly locate nearest verified hospitals with distance, operational status, and available beds.' },
      { title: 'Crowdsourced Incident Reporting', desc: 'Submit geotagged field reports of rising floodwaters or contaminated tube-wells with photo uploads.' },
      { title: 'Report Tracking & Self-Withdrawal', desc: 'Monitor review status by authorities and withdraw unverified reports if floodwaters recede.' },
      { title: 'Bilingual Emergency Alerts', desc: 'Official government disaster announcements in clear, accessible Bengali and English.' },
    ],
  },
  {
    roleNumber: 2,
    title: 'Field Health Worker Portal',
    badge: 'Grassroots Responders',
    color: '#2DD4BF',
    targetAudience: 'Community health assistants, DGHS field workers, and mobile clinic volunteers.',
    summary: 'Mobile-first field command built for submerged char lands with zero internet connectivity.',
    capabilities: [
      { title: 'Field Task Dispatch Inbox', desc: 'Review, accept, and prioritize assigned door-to-door community inspection and vaccination missions.' },
      { title: 'Household Triage Surveys', desc: 'Mobile visit logs capturing water source hygiene, suspected pathogen symptoms, and vulnerable family members.' },
      { title: 'Offline-First Auto-Save', desc: 'Conduct surveys in remote char and marshlands with zero internet; data auto-syncs when connection restores.' },
      { title: 'Live Relief Distribution Counter', desc: 'Real-time decrementing ledger to monitor distributed ORS and water purification tablets (Halazone).' },
    ],
  },
  {
    roleNumber: 3,
    title: 'Hospital Operations Portal',
    badge: 'Clinical Centers',
    color: '#818CF8',
    targetAudience: 'Hospital directors, emergency superintendents, and chief medical storekeepers.',
    summary: 'Correlates 14-day LSTM disease surge forecasts with live pharmacy stocks and ICU beds.',
    capabilities: [
      { title: 'Emergency Bed & ICU Management', desc: 'Real-time monitoring of general admission beds, pediatric wards, and ICU ventilators with live meters.' },
      { title: 'Dynamic Pharmacy Inventory Control', desc: 'Multi-item catalog tracking IV Saline (Normal/Cholera), antibiotics, and snake antivenom with batch/expiry dates.' },
      { title: 'Atomic Stock Ledger', desc: 'Strict transaction ledger recording all supplies as RECEIVED, DISTRIBUTED, CONSUMED, DAMAGED, or EXPIRED.' },
      { title: '14-Day LSTM Surge Preparation', desc: 'Correlates incoming disease surge curves with existing stock levels to trigger supply restocking requests before emergency rooms are overrun.' },
    ],
  },
  {
    roleNumber: 4,
    title: 'NGO Humanitarian Operations Portal',
    badge: 'Relief Agencies',
    color: '#F59E0B',
    targetAudience: 'Red Crescent, BRAC, international humanitarian organizations, and disaster relief teams.',
    summary: 'Scientific resource allocation and transparent field campaign coordination.',
    capabilities: [
      { title: 'Relief Campaign Manager', desc: 'Create, fund, and manage targeted disaster relief operations across affected districts with defined timelines.' },
      { title: 'Field Warehouse Inventory', desc: 'Dedicated logistics tracking of dry food packages, water purification jerrycans, blankets, and dignity kits.' },
      { title: 'Task Dispatch & Accountability', desc: 'Assign distribution teams to designated shelters and log target versus actual reached beneficiaries.' },
      { title: 'AI-Assisted Quota Allocator', desc: 'Pulls composite risk rankings to scientifically recommend supply allocations, eliminating geographical bias and relief duplication.' },
    ],
  },
  {
    roleNumber: 5,
    title: 'Government Emergency Command Room',
    badge: 'Policy & Executive',
    color: '#C084FC',
    targetAudience: 'Ministry of Disaster Management, DGHS, District Commissioners (DC), and Civil Surgeons.',
    summary: 'Nationwide command dashboard for high-level oversight and inter-agency resource approval.',
    capabilities: [
      { title: 'National Situation Overview', desc: 'Executive command room tracking critical disaster zones, national bed deficits, and active NGO deployments.' },
      { title: 'Inter-Agency Requisition Approval', desc: 'Review supply and medical requisitions from field hospitals, approve with mandatory justification, and dispatch central stockpiles.' },
      { title: 'Emergency Bilingual Broadcasts', desc: 'Draft, review, and authorize official SMS and mobile push alerts in English and Bengali with a two-step verification protocol.' },
      { title: 'Cross-Agency Issue Rollup', desc: 'Unified filterable audit stream consolidating verified citizen reports, hospital supply alerts, and field worker escalations.' },
    ],
  },
  {
    roleNumber: 6,
    title: 'Super Administrator Portal',
    badge: 'System & Security',
    color: '#F43F5E',
    targetAudience: 'Lead System Engineers, National Disaster IT Directors, and Database Administrators.',
    summary: 'Enterprise RBAC, background automation monitors, and audit compliance.',
    capabilities: [
      { title: 'Enterprise RBAC Directory', desc: 'Inspect and manage all registered users, enforce role transitions (such as promoting verified health workers), and configure permissions.' },
      { title: 'Bulk Hospital Geo-Importer', desc: 'Batch upload CSV manifests of nationwide medical facilities with automated geocoding validation, duplicate-filtering, and DB sync.' },
      { title: 'n8n Workflow Automation Monitor', desc: 'Real-time orchestration of n8n event-driven workflows, webhook triggers, cron schedules, and emergency dispatch logs.' },
      { title: 'Tamper-Evident Security Audit Trail', desc: 'Immutable system-wide audit logging tracking every administrative action, resource approval, and status transition.' },
    ],
  },
];

export const INITIAL_TEAM: TeamMember[] = [
  {
    id: '1',
    name: 'Md. Rifat Islam Rizvi',
    role: 'Project Lead and AI ML Engineer',
    email: 'rifatrizviofficial001@gmail.com',
    phone: '01305612767',
    badge: 'Project Lead',
    image: '/images/team/rifat.jpg',
    bio: 'Architected the end-to-end multi-hazard early warning system, 6 trained AI/ML models, Sentinel-1 SAR satellite pipeline, and scalable FastAPI/Next.js infrastructure.',
  },
  {
    id: '2',
    name: 'Md. Nahid Hossain',
    role: 'Data Scientist',
    email: 'nahidhossianofficial14@gmail.com',
    phone: '01859232959',
    badge: 'Data Scientist',
    image: '/images/team/nahid.jpg',
    bio: 'Expertise in delta hydrological datasets, epidemiological time-series analysis, feature engineering, and statistical predictive modeling for Bangladesh disaster management.',
  },
  {
    id: '3',
    name: 'Shabaj Islam Raad',
    role: 'Automation Engineer',
    email: 'shabaj.raad@dal.ca',
    phone: '+(1)-902-402-9652',
    badge: 'Automation Engineer',
    image: '/images/team/shabaj.png',
    bio: 'Specializing in end-to-end QA automation pipelines, Playwright test frameworks, n8n background workflow triggers, and continuous system reliability engineering.',
  },
  {
    id: '4',
    name: 'Arun Kumar Roy',
    role: 'Full Stack Developer',
    email: 'arunkumarroy.cse2021@gmail.com',
    phone: '01866999458',
    badge: 'Full Stack Developer',
    image: '/images/team/arun.jpg',
    bio: 'Building responsive Next.js/Tailwind client applications, state-synchronized dashboards, RESTful microservices, and interactive geospatial mapping interfaces.',
  },
  {
    id: '5',
    name: 'Asjad Ruhullah',
    role: 'Market Analyser',
    email: 'issacprosonno@gmail.com',
    phone: '0130822658',
    badge: 'Market Analyser',
    image: '/images/team/asjad.jpg',
    bio: 'Focusing on humanitarian market research, stakeholder adoption across government and NGOs, disaster impact metrics, and sustainable product-market strategy.',
  },
  {
    id: '6',
    name: 'Akifa Jahan Odry',
    role: 'Presentation and Communication Lead',
    email: 'akifaodrydocuments@gmail.com',
    phone: '01779298915',
    badge: 'Presentation and Communication Lead',
    image: '/images/team/akifa.jpg',
    bio: 'Leading project presentation, stakeholder communication, and clear documentation of FloodShield AI Pro’s mission, capabilities, and impact.',
  },
];

export const FEATURE_MATRIX: FeatureItem[] = [
  {
    name: 'Model 1: Binary Flood Classifier',
    category: 'AI/ML',
    status: 'Live',
    description: 'Ensemble Random Forest & XGBoost predicting flood probability (0-100%) from real-time precipitation and river stage.',
  },
  {
    name: 'Model 2 & 2B: Outbreak Risk & 6 Diseases',
    category: 'AI/ML',
    status: 'Live',
    description: 'Epidemic severity classifier + 6 independent regressors forecasting Cholera, Diarrhea, Typhoid, Hepatitis, Dengue, Malaria.',
  },
  {
    name: 'Model 3: Time-Series LSTM Forecasting',
    category: 'AI/ML',
    status: 'Live',
    description: 'Keras/TensorFlow recurrent neural network recursively forecasting 7-day and 14-day patient admission surges.',
  },
  {
    name: 'Model 4: Sentinel-1 SAR Radar U-Net',
    category: 'GIS',
    status: 'Live',
    description: 'Google Earth Engine Synthetic Aperture Radar pipeline penetrating 100% monsoon clouds for pixel-level water extents.',
  },
  {
    name: 'Model 5: Multi-Hazard Composite Matrix',
    category: 'AI/ML',
    status: 'Live',
    description: 'Dynamic ranking of all 64 districts using weighted multi-hazard formulation + DBSCAN spatial disease cluster detection.',
  },
  {
    name: 'Model 6: Operational Recommendations Engine',
    category: 'Operations',
    status: 'Live',
    description: 'Policy inference engine mapping clinical forecasts against hospital inventories to prescribe action checklists.',
  },
  {
    name: 'RAG Clinical Emergency Chatbot',
    category: 'AI/ML',
    status: 'Live',
    description: 'Multilingual grounded conversational AI citing WHO & DGHS clinical guidelines in Bangla, Banglish, and English.',
  },
  {
    name: 'n8n Workflow Automation Engine',
    category: 'Automation',
    status: 'Live',
    description: 'Enterprise event-driven n8n workflow engine orchestrating 5-min weather cron polls, ML prediction webhooks, and automated multi-channel SMS alerts.',
  },
  {
    name: '6 Role-Based Command Portals',
    category: 'Operations',
    status: 'Live',
    description: 'Tailored command centers for Citizen, Field Health Worker, Hospital Administrator, NGO, Government, and Super-Admin.',
  },
  {
    name: 'Offline-First Field Visit Logging',
    category: 'Operations',
    status: 'Live',
    description: 'Local storage caching for rural community triage surveys with zero data loss during marshland cellular dropouts.',
  },
  {
    name: 'Transboundary Upstream Radar Pipeline',
    category: 'GIS',
    status: 'Active',
    description: 'Expanding precipitation radar coverage into Assam, Meghalaya, and Tripura to extend lead times to 21 days.',
  },
  {
    name: 'Parametric Climate Micro-Insurance API',
    category: 'Automation',
    status: 'Planned',
    description: 'Smart contract triggers executing instant mobile financial compensation (bKash/Nagad) to farmers upon river crest.',
  },
];

export const API_ENDPOINTS: ApiEndpointDoc[] = [
  {
    method: 'GET',
    path: '/backend-api/health',
    description: 'System health check and live operational heartbeat verification.',
    auth: 'Public',
    paramsOrBody: 'None',
    sampleResponse: '{"status": "ok", "app": "FloodShield AI", "version": "1.2.0"}',
  },
  {
    method: 'POST',
    path: '/backend-api/auth/login',
    description: 'Authenticate user across 6 RBAC roles and receive JWT bearer token.',
    auth: 'Public',
    paramsOrBody: '{"email": "string", "password": "string"}',
    sampleResponse: '{"access_token": "eyJhbGci...", "token_type": "bearer", "role": "admin"}',
  },
  {
    method: 'GET',
    path: '/backend-api/weather?district={name}',
    description: 'Live meteorological telemetry, 1h precipitation, humidity, river water level.',
    auth: 'Public',
    paramsOrBody: 'Query: district (e.g. "Feni")',
    sampleResponse: '{"district": "Feni", "rainfall": 45.2, "river_level_m": 8.5, "humidity": 92}',
  },
  {
    method: 'POST',
    path: '/backend-api/predict/flood',
    description: 'Execute Model 1 Machine Learning Flood Inundation Classifier.',
    auth: 'Bearer JWT',
    paramsOrBody: '{"location": "Feni", "river_level_m": 8.5, "rainfall_mm": 45.2}',
    sampleResponse: '{"flood_probability": 0.924, "flood_risk_level": "Critical", "confidence": 0.95}',
  },
  {
    method: 'GET',
    path: '/backend-api/assessment/{district}',
    description: 'Auto-running Multi-Model Full Assessment (Models 1, 2, 2B, 3, 5, 6 chained).',
    auth: 'Bearer JWT',
    paramsOrBody: 'Path: district name',
    sampleResponse: '{"district": "Feni", "flood": {...}, "disease_outbreak": {...}, "disease_breakdown": {...}, "forecast": {...}}',
  },
  {
    method: 'GET',
    path: '/backend-api/reports/forecast?district={name}',
    description: 'Model 3 LSTM 7-day and 14-day recursive patient caseload forecasting.',
    auth: 'Bearer JWT',
    paramsOrBody: 'Query: district name',
    sampleResponse: '{"district": "Feni", "forecast_next_7_days_cases": 142.0, "forecast_next_14_days_cases": 198.0}',
  },
  {
    method: 'POST',
    path: '/backend-api/recommend',
    description: 'Model 6 Policy Recommendation Engine for hospital beds and resource quotas.',
    auth: 'Operational Roles',
    paramsOrBody: '{"district": "Feni", "risk_level": "Critical"}',
    sampleResponse: '{"hospital_beds_available": 2076, "occupancy_percent": 47.9, "recommendations": ["Deploy Emergency Medical Team", "Prepare Emergency Shelter"]}',
  },
  {
    method: 'POST',
    path: '/backend-api/satellite/segment',
    description: 'Model 4 U-Net SAR Satellite Inundation Segmentation on Sentinel-1 radar.',
    auth: 'Bearer JWT',
    paramsOrBody: 'Query: district name',
    sampleResponse: '{"district": "Feni", "flood_pixels": 48210, "inundated_area_sqkm": 182.4, "geojson": {...}}',
  },
  {
    method: 'POST',
    path: '/backend-api/predict/disease-breakdown',
    description: 'Model 2B 6-Pathogen Quantitative Regressors (Cholera, Diarrhea, Typhoid, Hepatitis, Dengue, Malaria).',
    auth: 'Bearer JWT',
    paramsOrBody: '{"district": "Feni", "flood_duration_days": 4, "wqi": 48.5}',
    sampleResponse: '{"cholera_cases": 45, "diarrhea_cases": 128, "typhoid_cases": 18, "hepatitis_cases": 9, "dengue_cases": 32, "malaria_cases": 14}',
  },
  {
    method: 'POST',
    path: '/backend-api/chatbot/query',
    description: 'RAG Clinical Chatbot querying WHO and DGHS medical guidelines in English, Bangla, or Banglish.',
    auth: 'Public',
    paramsOrBody: '{"query": "How to treat cholera dehydration in children?", "language": "en"}',
    sampleResponse: '{"reply": "Immediately administer Oral Rehydration Solution (ORS)...", "sources": ["DGHS Cholera Treatment Protocol 2024", "WHO Waterborne Guidelines"]}',
  },
  {
    method: 'GET',
    path: '/backend-api/government/command-overview',
    description: 'High-level inter-agency situational metrics for national disaster ministers.',
    auth: 'Government / Admin',
    paramsOrBody: 'None',
    sampleResponse: '{"total_districts": 64, "critical_districts": 3, "open_requisitions": 5, "active_campaigns": 12}',
  },
];

export const CHANGELOG_ITEMS = [
  {
    version: 'v1.2.0',
    date: 'November 2026',
    title: 'Multi-Model Full Assessment V2 & n8n Workflow Automation Engine',
    details: [
      'Chained Model 1 (Flood RF), Model 2 (Outbreak), Model 2B (6-Pathogen XGBoost), and Model 3 (LSTM) into unified /assessment/{district} pipeline.',
      'Integrated n8n workflow orchestration executing continuous OpenWeatherMap ingestion, webhook-based ML re-prediction, and emergency alert dispatches.',
      'Released hospital inventory batch ledger and interactive 64-district GeoJSON GIS maps.',
    ],
  },
  {
    version: 'v1.1.0',
    date: 'October 2026',
    title: 'Sentinel-1 SAR Radar & Role-Based Access Control',
    details: [
      'Integrated Google Earth Engine Sentinel-1 Synthetic Aperture Radar (SAR) U-Net segmentation.',
      'Implemented 6-tier RBAC architecture for Citizens, Health Workers, Hospitals, NGOs, Government, and Super-Admins.',
      'Shipped offline-first mobile survey module for marshland health workers.',
    ],
  },
  {
    version: 'v1.0.0',
    date: 'September 2026',
    title: 'Genesis Architecture & Core Predictors',
    details: [
      'Initial release of Bangladesh delta flood classification model trained on BWDB hydrology datasets.',
      'Launched public landing page with 3D interactive WebGL globe and real-time OpenWeatherMap streams.',
      'Integrated WHO & DGHS medical guidance into multilingual RAG assistant.',
    ],
  },
];
