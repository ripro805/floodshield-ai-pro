'use client';

import { useRef, Suspense } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Sphere, MeshDistortMaterial } from '@react-three/drei';
import * as THREE from 'three';
import type { RiskLevel } from '@/lib/types';
import { RISK_COLORS } from '@/lib/types';

interface MarkerProps {
  position: [number, number, number];
  riskLevel: RiskLevel;
  label: string;
}

function PulsingMarker({ position, riskLevel }: MarkerProps) {
  const meshRef = useRef<THREE.Mesh>(null!);
  const color = RISK_COLORS[riskLevel];

  useFrame(({ clock }) => {
    // Respect prefers-reduced-motion: disable animation if user prefers reduced motion
    const prefersReducedMotion = typeof window !== 'undefined' 
      ? window.matchMedia('(prefers-reduced-motion: reduce)').matches 
      : false;
    
    if (!prefersReducedMotion) {
      const t = clock.getElapsedTime();
      meshRef.current.scale.setScalar(0.9 + Math.sin(t * 2) * 0.15);
    } else {
      meshRef.current.scale.setScalar(1);  // Static scale
    }
  });

  return (
    <group position={position}>
      <mesh ref={meshRef}>
        <sphereGeometry args={[0.055, 16, 16]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={2.5}
          transparent
          opacity={0.9}
        />
      </mesh>
      {/* Outer glow ring */}
      <mesh>
        <torusGeometry args={[0.09, 0.012, 8, 32]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={1.5}
          transparent
          opacity={0.4}
        />
      </mesh>
    </group>
  );
}

function Globe({ markers }: { markers: MarkerProps[] }) {
  const globeRef = useRef<THREE.Mesh>(null!);

  useFrame(({ clock }) => {
    globeRef.current.rotation.y = clock.getElapsedTime() * 0.08;
  });

  // Convert lat/lon to 3D sphere position (r=1.55)
  const latLonToVec = (lat: number, lon: number): [number, number, number] => {
    const phi = (90 - lat) * (Math.PI / 180);
    const theta = (lon + 180) * (Math.PI / 180);
    const r = 1.55;
    return [
      -r * Math.sin(phi) * Math.cos(theta),
      r * Math.cos(phi),
      r * Math.sin(phi) * Math.sin(theta),
    ];
  };

  // Bangladesh approximate centre + key high-risk districts
  const districtMarkers: MarkerProps[] = markers.length > 0 ? markers : [
    { position: latLonToVec(22.5, 90.4), riskLevel: 'Critical', label: 'Feni' },
    { position: latLonToVec(24.9, 91.9), riskLevel: 'High', label: 'Sylhet' },
    { position: latLonToVec(25.1, 91.6), riskLevel: 'High', label: 'Sunamganj' },
    { position: latLonToVec(24.8, 90.4), riskLevel: 'Medium', label: 'Netrokona' },
    { position: latLonToVec(24.9, 89.9), riskLevel: 'Medium', label: 'Jamalpur' },
    { position: latLonToVec(23.7, 90.4), riskLevel: 'Low', label: 'Dhaka' },
  ];

  return (
    <group>
      {/* Core globe */}
      <mesh ref={globeRef}>
        <sphereGeometry args={[1.5, 64, 64]} />
        <MeshDistortMaterial
          color="#0B1730"
          emissive="#0B2040"
          emissiveIntensity={0.4}
          wireframe={false}
          distort={0.08}
          speed={0.5}
          roughness={0.2}
          metalness={0.6}
        />
      </mesh>
      {/* Wireframe overlay */}
      <mesh ref={globeRef}>
        <sphereGeometry args={[1.52, 32, 32]} />
        <meshBasicMaterial color="#38BDF8" wireframe transparent opacity={0.06} />
      </mesh>
      {/* Risk markers */}
      {districtMarkers.map((m, i) => (
        <PulsingMarker key={i} {...m} />
      ))}
    </group>
  );
}

interface BangladeshGlobeProps {
  markers?: MarkerProps[];
  className?: string;
}

export default function BangladeshGlobe({ markers = [], className = '' }: BangladeshGlobeProps) {
  return (
    <div className={`w-full h-full ${className}`} aria-label="3D globe showing Bangladesh flood risk markers">
      <Canvas camera={{ position: [0, 0, 4], fov: 45 }} dpr={[1, 2]}>
        <ambientLight intensity={0.3} />
        <pointLight position={[5, 5, 5]} intensity={1.5} color="#38BDF8" />
        <pointLight position={[-5, -5, -5]} intensity={0.5} color="#2DD4BF" />
        <Suspense fallback={null}>
          <Globe markers={markers} />
        </Suspense>
        <OrbitControls
          enableZoom={false}
          enablePan={false}
          minPolarAngle={Math.PI / 4}
          maxPolarAngle={(3 * Math.PI) / 4}
          autoRotate={false}
        />
      </Canvas>
    </div>
  );
}
