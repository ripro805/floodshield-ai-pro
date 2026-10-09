# FloodShield AI Frontend

Premium, futuristic AI-powered flood and disease early-warning platform for Bangladesh.

## Features

- **6 Trained ML Models**: Flood prediction, disease outbreak risk, composite risk scoring, recommendations, satellite detection, and 7/14-day forecasting
- **Real-Time Data**: Live weather integration from OpenWeatherMap
- **Satellite Integration**: Sentinel-1 SAR flood detection with GeoJSON overlays
- **Role-Based Access**: 6 user roles (citizen, health_worker, hospital, ngo, government, admin) with granular permissions
- **Premium UI**: Glassmorphism design with 3D interactive elements, Framer Motion animations, and real-time data visualization
- **Fully Responsive**: Mobile-first design, optimized for all screen sizes

## Tech Stack

- **Framework**: Next.js 14 (App Router, TypeScript)
- **Styling**: TailwindCSS with custom design tokens
- **3D Graphics**: React Three Fiber + drei
- **Animation**: Framer Motion
- **Data Fetching**: TanStack Query (React Query)
- **Forms**: React Hook Form + Zod validation
- **Charts**: Recharts (7/14-day forecasts)
- **Maps**: Leaflet + react-leaflet (district risk maps, satellite overlays)
- **Icons**: Lucide React
- **Notifications**: react-hot-toast
- **HTTP Client**: Axios with Bearer token authentication

## Quick Start

### Prerequisites

- Node.js 18+ (LTS recommended)
- npm, yarn, pnpm, or bun

### Installation

1. **Install dependencies**:
   ```bash
   npm install
   # or
   yarn install
   pnpm install
   bun install
   ```

2. **Set up environment**:
   ```bash
   cp .env.example .env.local
   # Edit .env.local and set NEXT_PUBLIC_API_URL to your backend URL
   ```

3. **Start dev server**:
   ```bash
   npm run dev
   # Frontend will be at http://localhost:3000
   ```

4. **Open in browser**:
   - Navigate to [http://localhost:3000](http://localhost:3000)
   - Sign up or log in with test credentials

### Build for Production

```bash
npm run build
npm start
```

## Project Structure

```
frontend/
├── app/
│   ├── (public)/              # Public pages (landing, login, signup)
│   │   ├── page.tsx           # Landing page (hero, 3D globe)
│   │   ├── login/page.tsx     # Login form
│   │   └── signup/page.tsx    # Signup form
│   ├── dashboard/             # Protected dashboard pages
│   │   ├── page.tsx           # District risk map
│   │   ├── [district]/page.tsx # District detail (flood, disease, forecast)
│   │   ├── alerts/page.tsx    # Live 30-sec alerts
│   │   ├── reports/page.tsx   # 7/14-day forecasts (export CSV)
│   │   ├── resources/page.tsx # Hospital recommendations (ops only)
│   │   ├── admin/page.tsx     # Admin panel (admin only)
│   │   └── layout.tsx         # Dashboard layout with sidebar + navbar
│   ├── globals.css            # Design tokens, animations, utilities
│   └── layout.tsx             # Root layout with providers
├── components/
│   ├── three/                 # 3D components (React Three Fiber)
│   │   ├── BangladeshGlobe.tsx        # 3D rotating globe with markers
│   │   ├── RiskGaugeTube.tsx          # 3D glass gauge (signature element)
│   │   └── ParticleBackground.tsx     # Animated particle field
│   ├── map/                   # Leaflet maps
│   │   ├── DistrictRiskMap.tsx        # District-level risk map
│   │   └── SatelliteOverlay.tsx       # Satellite flood extent overlay
│   ├── charts/
│   │   └── ForecastChart.tsx          # Recharts: historical + dashed forecast
│   ├── cards/                 # Reusable glass card components
│   │   ├── GlassCard.tsx              # Base frosted-glass wrapper
│   │   ├── RiskSummaryCard.tsx        # Flood risk with animated gauge
│   │   ├── RecommendationCard.tsx     # AI recommendations list
│   │   └── HospitalStockCard.tsx      # Mini-gauges for supply levels
│   ├── layout/
│   │   ├── AuthGuard.tsx      # Route protection + role validation
│   │   ├── Navbar.tsx         # Top navigation with user badge
│   │   ├── Sidebar.tsx        # Role-aware navigation menu
│   │   └── Providers.tsx      # TanStack Query + Toaster setup
│   └── chat/
│       └── ChatbotWidget.tsx  # Floating FAQ assistant
├── lib/
│   ├── api.ts         # Axios client with Bearer token + error handling
│   ├── auth.ts        # Token storage + useAuth() hook
│   └── types.ts       # Full TypeScript schemas (matches backend exactly)
├── hooks/
│   └── index.ts       # TanStack Query hooks (all 6 models + satellite + weather)
├── package.json
├── tsconfig.json
├── tailwind.config.ts
├── postcss.config.mjs
├── next.config.mjs
├── .env.example       # Environment template
└── .gitignore
```

## Environment Variables

Create a `.env.local` file in the root and set:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

On production, set this in your hosting platform's environment settings (Vercel, Railway, etc.).

## API Integration

All API calls go through `lib/api.ts`:

- **Auth**: Signup, login, get current user
- **Model 1**: Flood probability prediction
- **Model 2**: Disease outbreak risk
- **Model 3**: 7/14-day disease case forecast
- **Model 4**: Satellite flood detection (Sentinel-1 SAR)
- **Model 5**: Composite risk scoring
- **Model 6**: AI recommendations (ops roles only)
- **Weather**: Live OpenWeatherMap integration

The API client:
1. Automatically attaches `Authorization: Bearer <token>` to every request
2. On 401, clears token and redirects to `/login`
3. On 403, shows inline error (user is logged in, just not permitted)
4. Provides typed responses matching backend schemas

## Role-Based Access

| Page | Public | Citizen | Health Worker | Hospital | NGO | Government | Admin |
|------|--------|---------|---------------|----------|-----|------------|-------|
| Landing | ✅ | - | - | - | - | - | - |
| Login/Signup | ✅ | - | - | - | - | - | - |
| District Map | - | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| District Detail | - | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Alerts | - | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Reports | - | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Hospital Resources | - | ✗ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Admin Panel | - | ✗ | ✗ | ✗ | ✗ | ✗ | ✅ |

## Design System

### Colors (Semantic Risk Levels)

- **Low**: `#2DD4BF` (teal) — Safe
- **Medium**: `#FBBF24` (amber) — Caution
- **High**: `#FB923C` (orange) — Alert
- **Critical**: `#F43F5E` (red) — Immediate action
- **Accent**: `#38BDF8` (electric blue) — Primary CTA

### Typography

- **Display**: Space Grotesk (bold headings, wide letter-spacing)
- **Body**: Inter (legible, open sans-serif)
- **Data**: JetBrains Mono (numbers, metrics)

### Glass Morphism

All cards use:
- Backdrop blur: 24px
- Background: `rgba(255,255,255,0.05)`
- Border: Subtle gradient (`rgba(255,255,255,0.10)` → `0.06`)
- Hover: Lift + enhanced glow

### Animations

- Page load: Staggered fade+rise (60-100ms per card)
- Numbers: Count-up animation (1.2s ease-out)
- Hover: Cards lift 4px + glow intensifies
- Critical alerts: Pulsing red glow ring
- Route transitions: Smooth crossfade

## Performance Optimizations

- **Image**: Next.js Image component for optimization
- **Code Splitting**: Dynamic imports for 3D components (no SSR)
- **Query Caching**: TanStack Query default 5-min stale time
- **Lazy Loading**: Maps, charts, and 3D rendered only on client
- **Font Loading**: Google Fonts with display=swap
- **Tree Shaking**: ES modules + dead code elimination

## Accessibility

- ✅ Semantic HTML (nav, main, section)
- ✅ ARIA labels on interactive elements
- ✅ Keyboard focus states (ring-2 ring-blue-400)
- ✅ Color contrast (WCAG AA minimum)
- ✅ Reduced motion support (`prefers-reduced-motion`)
- ✅ Alt text on images
- ✅ Form labels + error messages

## Testing

To add tests (future):

```bash
npm install --save-dev @testing-library/react jest
# Create tests in __tests__/ or *.test.tsx alongside components
```

## Troubleshooting

### "Module not found" errors

Run `npm install` again and restart dev server.

### API calls fail with 401/403

Check `.env.local` has correct `NEXT_PUBLIC_API_URL` pointing to running backend.

### 3D globe not showing

- Check browser console for WebGL errors
- 3D is disabled on very old browsers (graceful fallback)
- Refresh page if stuck on loading spinner

### TailwindCSS not applying

Rebuild CSS:

```bash
npm run dev
# CSS should rebuild automatically when you edit .tsx files
```

## Deployment

### Vercel (Recommended)

1. Push code to GitHub
2. Connect repo on [vercel.com](https://vercel.com)
3. Set `NEXT_PUBLIC_API_URL` in "Environment Variables"
4. Deploy

### Docker

```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package.json .
RUN npm ci
COPY . .
RUN npm run build
CMD npm start
EXPOSE 3000
```

Build and run:

```bash
docker build -t floodshield-frontend .
docker run -p 3000:3000 -e NEXT_PUBLIC_API_URL=https://api.your-domain.com floodshield-frontend
```

## Contributing

1. Create a feature branch: `git checkout -b feature/my-feature`
2. Commit changes: `git commit -m "Add feature X"`
3. Push branch: `git push origin feature/my-feature`
4. Open a pull request

## License

Proprietary — FloodShield AI, 2024.

## Support

For issues, questions, or feature requests, contact the FloodShield team.

---

**Version**: 1.0.0  
**Last Updated**: September 2024  
**Status**: Production Ready ✅
