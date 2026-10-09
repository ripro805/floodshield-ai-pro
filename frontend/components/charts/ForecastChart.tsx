'use client';

import {
  ComposedChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Legend,
} from 'recharts';
import type { WeeklyObservation, ForecastResponse } from '@/lib/types';

interface ForecastChartProps {
  weeks: WeeklyObservation[];
  forecast?: ForecastResponse;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
  label?: string;
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  return (
    <div
      className="rounded-xl px-4 py-3 text-sm shadow-xl border"
      style={{
        background: 'rgba(6,11,20,0.92)',
        backdropFilter: 'blur(16px)',
        borderColor: 'rgba(255,255,255,0.12)',
      }}
    >
      <p className="text-white/50 text-xs mb-2 font-mono">{label}</p>
      {payload.map((p, i) => (
        <p key={i} className="font-mono font-semibold" style={{ color: p.color }}>
          {p.name}: {typeof p.value === 'number' ? p.value.toFixed(0) : p.value}
        </p>
      ))}
    </div>
  );
}

export default function ForecastChart({ weeks, forecast }: ForecastChartProps) {
  const historical = weeks.map((w, i) => ({
    label: `W-${8 - i}`,
    cases: Math.round(w.weekly_cases),
    rainfall: Math.round(w.rainfall_mm),
  }));

  // Append forecast points
  const chartData = [...historical];
  if (forecast) {
    chartData.push({
      label: 'W+1 (7d)',
      cases: Math.round(forecast.forecast_next_7_days_cases),
      rainfall: 0,
    });
    chartData.push({
      label: 'W+2 (14d)',
      cases: Math.round(forecast.forecast_next_14_days_cases),
      rainfall: 0,
    });
  }

  const forecastStart = forecast ? historical.length - 1 : undefined;

  return (
    <ResponsiveContainer width="100%" height={280}>
      <ComposedChart data={chartData} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" vertical={false} />
        <XAxis
          dataKey="label"
          tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 11, fontFamily: 'JetBrains Mono, monospace' }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 11, fontFamily: 'JetBrains Mono, monospace' }}
          axisLine={false}
          tickLine={false}
          width={40}
        />
        <Tooltip content={<CustomTooltip />} />
        <Legend
          wrapperStyle={{ fontSize: 12, color: 'rgba(255,255,255,0.5)', fontFamily: 'JetBrains Mono, monospace' }}
        />
        {/* Forecast separator */}
        {forecastStart !== undefined && (
          <ReferenceLine
            x={chartData[forecastStart].label}
            stroke="rgba(255,255,255,0.15)"
            strokeDasharray="4 4"
            label={{ value: 'Forecast →', fill: 'rgba(255,255,255,0.3)', fontSize: 10 }}
          />
        )}
        {/* Historical line — solid teal */}
        <Line
          type="monotone"
          dataKey="cases"
          name="Weekly Cases"
          stroke="#2DD4BF"
          strokeWidth={2.5}
          dot={{ fill: '#2DD4BF', r: 3 }}
          activeDot={{ r: 5, fill: '#2DD4BF', strokeWidth: 0 }}
          connectNulls
          isAnimationActive
          animationDuration={1200}
          animationEasing="ease-out"
          // Dashed after forecast start point
          strokeDasharray={forecast ? `${forecastStart! * 60} 10000` : undefined}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
