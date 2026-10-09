'use client';

import { useRef, useEffect } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import type { RiskLevel } from '@/lib/types';
import { RISK_COLORS } from '@/lib/types';

const RISK_TO_COLOR = {
  low: RISK_COLORS.Low,
  medium: RISK_COLORS.Medium,
  high: RISK_COLORS.High,
  critical: RISK_COLORS.Critical,
};

interface GaugeMeshProps {
  value: number; // 0–1
  riskLevel: 'low' | 'medium' | 'high' | 'critical';
}

function GaugeMesh({ value, riskLevel }: GaugeMeshProps) {
  const fillRef = useRef<THREE.Mesh>(null!);
  const fillHeight = useRef(0);
  const targetHeight = value * 2.8; // max fill height 2.8 units
  const color = RISK_TO_COLOR[riskLevel];

  useFrame(() => {
    // Animate fill rising on mount
    if (fillHeight.current < targetHeight) {
      fillHeight.current = Math.min(fillHeight.current + 0.025, targetHeight);
      fillRef.current.scale.y = fillHeight.current / 2.8;
      fillRef.current.position.y = -1.4 + (fillHeight.current / 2);
    }
  });

  return (
    <group>
      {/* Outer glass cylinder */}
      <mesh>
        <cylinderGeometry args={[0.22, 0.22, 3, 32, 1, true]} />
        <meshPhysicalMaterial
          color="#ffffff"
          transparent
          opacity={0.08}
          roughness={0}
          metalness={0}
          transmission={0.9}
          side={THREE.DoubleSide}
        />
      </mesh>
      {/* Glass top cap */}
      <mesh position={[0, 1.5, 0]}>
        <circleGeometry args={[0.22, 32]} />
        <meshPhysicalMaterial color="#ffffff" transparent opacity={0.1} roughness={0} />
      </mesh>
      {/* Glass bottom cap */}
      <mesh position={[0, -1.5, 0]} rotation={[Math.PI, 0, 0]}>
        <circleGeometry args={[0.22, 32]} />
        <meshPhysicalMaterial color="#ffffff" transparent opacity={0.1} roughness={0} />
      </mesh>
      {/* Liquid fill */}
      <mesh ref={fillRef} position={[0, -1.4, 0]}>
        <cylinderGeometry args={[0.18, 0.18, 2.8, 32]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={1.8}
          transparent
          opacity={0.85}
        />
      </mesh>
      {/* Tick marks on glass */}
      {[0, 0.25, 0.5, 0.75, 1].map((t, i) => (
        <mesh key={i} position={[0.21, -1.4 + t * 2.8, 0]}>
          <boxGeometry args={[0.06, 0.015, 0.015]} />
          <meshBasicMaterial color="#ffffff" transparent opacity={0.3} />
        </mesh>
      ))}
    </group>
  );
}

type GaugeSize = 'sm' | 'md' | 'lg';

// Dimension presets per size
const SIZE_DIMS: Record<GaugeSize, { canvasW: number; canvasH: number; labelClass: string; valueClass: string }> = {
  sm: { canvasW: 40, canvasH: 90,  labelClass: 'text-[10px]', valueClass: 'text-xs' },
  md: { canvasW: 56, canvasH: 120, labelClass: 'text-xs',     valueClass: 'text-sm' },
  lg: { canvasW: 72, canvasH: 160, labelClass: 'text-xs',     valueClass: 'text-sm' },
};

interface RiskGaugeTubeProps {
  value: number;           // 0–1
  riskLevel: 'low' | 'medium' | 'high' | 'critical';
  label?: string;
  /** @deprecated Use size prop instead. Still honoured when size="lg". */
  height?: number;         // canvas height px override (legacy)
  /** Visual size preset. Defaults to 'lg' to preserve existing behaviour. */
  size?: GaugeSize;
}

export default function RiskGaugeTube({
  value,
  riskLevel,
  label,
  height,
  size = 'lg',
}: RiskGaugeTubeProps) {
  const color = RISK_TO_COLOR[riskLevel];
  const dims = SIZE_DIMS[size];
  // Legacy: explicit height prop overrides the preset only for 'lg'
  const canvasH = (size === 'lg' && height != null) ? height : dims.canvasH;

  return (
    <div className="flex flex-col items-center gap-1">
      <div style={{ height: canvasH, width: dims.canvasW }}>
        <Canvas
          camera={{ position: [0, 0, 4.5], fov: 40 }}
          dpr={[1, 2]}
          onCreated={({ gl }) => {
            // Restore context automatically if it's lost (e.g. during Fast Refresh)
            gl.domElement.addEventListener('webglcontextlost', (e) => {
              e.preventDefault();
            }, { once: false });
            gl.domElement.addEventListener('webglcontextrestored', () => {
              gl.setSize(gl.domElement.width, gl.domElement.height);
            }, { once: false });
          }}
        >
          <ambientLight intensity={0.4} />
          <pointLight position={[2, 2, 2]} intensity={1.2} color={color} />
          <pointLight position={[-2, -2, -2]} intensity={0.5} color="#38BDF8" />
          <GaugeMesh value={value} riskLevel={riskLevel} />
        </Canvas>
      </div>
      {label && (
        <span className={`font-medium text-white/60 uppercase tracking-wider text-center ${dims.labelClass}`}>
          {label}
        </span>
      )}
      <span
        className={`font-mono font-bold tabular-nums ${dims.valueClass}`}
        style={{ color }}
      >
        {Math.round(value * 100)}%
      </span>
    </div>
  );
}
