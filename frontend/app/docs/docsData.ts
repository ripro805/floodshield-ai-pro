export interface TeamMember {
  id: string;
  name: string;
  role: string;
  email: string;
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

export const DEFAULT_DOCS_CONFIG: DocsConfig = {
  visibility: 'ON',
  scheduleEnabled: false,
  startDate: '2026-06-10T00:00:00.000Z',
  endDate: '2026-06-30T23:59:59.000Z',
  allowAdminBypass: true,
  lastUpdated: new Date().toISOString(),
};

export const INITIAL_TEAM: TeamMember[] = [
  {
    id: '1',
    name: 'Md. Rifat Hossain',
    role: 'Lead AI Architect & Full-Stack System Engineer',
    email: 'lead.architect@floodshield-ai.org',
    badge: 'Founder / Core Tech',
    bio: 'Specialist in Hydrological Remote Sensing, Deep Learning Pipelines, and Resilient Next.js/FastAPI Architectures.',
  },
  {
    id: '2',
    name: 'Disaster Domain Specialist',
    role: 'Hydrological Modeling & Epidemiological Lead',
    email: 'epidemiology@floodshield-ai.org',
    badge: 'Domain Expert',
    bio: 'Expertise in Delta Hydrology, DGHS Clinical Protocols, and Waterborne Pathogen Modeling in Bangladesh.',
  },
  {
    id: '3',
    name: 'Healthcare Operations Lead',
    role: 'Clinical Surge & Hospital Logistics Coordinator',
    email: 'clinical.logistics@floodshield-ai.org',
    badge: 'Operations',
    bio: 'Dedicated to rural health facility readiness, emergency saline buffer supply chains, and triage workflows.',
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
    name: 'Native Automation Engine (5 Daemons)',
    category: 'Automation',
    status: 'Live',
    description: 'Self-contained FastAPI background loops executing weather ingestion, ML risk recomputation, and SMS dispatch.',
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
    title: 'Multi-Model Full Assessment V2 & Native Automation Engine',
    details: [
      'Chained Model 1 (Flood RF), Model 2 (Outbreak), Model 2B (6-Pathogen XGBoost), and Model 3 (LSTM) into unified /assessment/{district} pipeline.',
      'Embedded native background automation loop executing continuous OpenWeatherMap ingestion and auto-prediction daemons.',
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
