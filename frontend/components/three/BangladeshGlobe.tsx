'use client';

import React, { useRef, useMemo, Suspense } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, useTexture } from '@react-three/drei';
import * as THREE from 'three';
import type { RiskLevel } from '@/lib/types';
import { RISK_COLORS } from '@/lib/types';

const GLOBE_RADIUS = 2.0;

// Conversion helper: Equirectangular lat/lon to 3D Cartesian coordinates
function latLonToVec(lat: number, lon: number, radius = GLOBE_RADIUS): [number, number, number] {
  const phi = (90 - lat) * (Math.PI / 180);
  const theta = (lon + 180) * (Math.PI / 180);
  const x = -radius * Math.sin(phi) * Math.cos(theta);
  const y = radius * Math.cos(phi);
  const z = radius * Math.sin(phi) * Math.sin(theta);
  return [x, y, z];
}

// Telemetry node coordinates (NO flags, pure data points)
interface NodePoint {
  id: string;
  lat: number;
  lon: number;
  isHub?: boolean;
}

const TELEMETRY_NODES: NodePoint[] = [
  { id: 'bd', lat: 23.8103, lon: 90.4125, isHub: true },  // Bangladesh Hub
  { id: 'in', lat: 28.6139, lon: 77.2090 },               // India
  { id: 'np', lat: 28.3949, lon: 84.1240 },               // Nepal
  { id: 'cn', lat: 35.8617, lon: 104.1954 },              // China
  { id: 'ae', lat: 24.4539, lon: 54.3773 },               // UAE
  { id: 'be', lat: 50.8503, lon: 4.3517 },                // Europe
  { id: 'ss', lat: 6.8770, lon: 31.3070 },                // East Africa
  { id: 'my', lat: 4.2105, lon: 101.9758 },               // Malaysia
  { id: 'vn', lat: 14.0583, lon: 108.2772 },              // Vietnam
  { id: 'ph', lat: 12.8797, lon: 121.7740 },              // Philippines
  { id: 'kh', lat: 12.5657, lon: 104.9910 },              // Cambodia
];

// 3D Connection Arc with animated White Comet Pulse
function TrajectoryArc({
  startNode,
  endNode,
  speed = 0.25,
  offset = 0,
}: {
  startNode: NodePoint;
  endNode: NodePoint;
  speed?: number;
  offset?: number;
}) {
  const cometMeshRef = useRef<THREE.Mesh>(null!);

  const { curve, lineObject } = useMemo(() => {
    const v1 = new THREE.Vector3(...latLonToVec(startNode.lat, startNode.lon, GLOBE_RADIUS));
    const v2 = new THREE.Vector3(...latLonToVec(endNode.lat, endNode.lon, GLOBE_RADIUS));

    const distance = v1.distanceTo(v2);
    // Arc altitude scales with distance across Earth surface
    const altitude = Math.min(1.2, Math.max(0.3, distance * 0.35));

    const mid = v1.clone().add(v2).multiplyScalar(0.5);
    if (mid.length() > 0.001) {
      mid.normalize().multiplyScalar(GLOBE_RADIUS + altitude);
    } else {
      mid.set(0, GLOBE_RADIUS + altitude, 0);
    }

    const curve = new THREE.QuadraticBezierCurve3(v1, mid, v2);
    const points = curve.getPoints(50);
    const lineGeometry = new THREE.BufferGeometry().setFromPoints(points);
    const lineMaterial = new THREE.LineBasicMaterial({
      color: 0x38bdf8,
      transparent: true,
      opacity: 0.55,
    });
    const lineObject = new THREE.Line(lineGeometry, lineMaterial);

    return { curve, lineObject };
  }, [startNode, endNode]);

  useFrame(({ clock }) => {
    if (!cometMeshRef.current) return;
    const t = (clock.getElapsedTime() * speed + offset) % 1;
    const point = curve.getPointAt(t);
    const tangent = curve.getTangentAt(t);

    cometMeshRef.current.position.copy(point);
    cometMeshRef.current.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), tangent);
  });

  return (
    <group>
      {/* Base glowing trajectory line */}
      <primitive object={lineObject} />

      {/* Moving white comet laser pulse */}
      <mesh ref={cometMeshRef}>
        <cylinderGeometry args={[0.018, 0.012, 0.42, 8]} />
        <meshBasicMaterial color="#ffffff" />
      </mesh>
    </group>
  );
}

// Glowing Surface Node Dot with subtle pulsing ring (No flags)
function SurfaceNode({ node }: { node: NodePoint }) {
  const ringRef = useRef<THREE.Mesh>(null!);
  const pos = useMemo(() => latLonToVec(node.lat, node.lon, GLOBE_RADIUS), [node.lat, node.lon]);

  useFrame(({ clock }) => {
    if (ringRef.current) {
      const t = clock.getElapsedTime() * 2 + (node.isHub ? 0 : 1);
      const scale = 1 + (Math.sin(t) + 1) * 0.3;
      ringRef.current.scale.setScalar(scale);
    }
  });

  return (
    <group position={pos}>
      {/* Surface pinpoint dot */}
      <mesh>
        <sphereGeometry args={[node.isHub ? 0.05 : 0.032, 16, 16]} />
        <meshStandardMaterial
          color={node.isHub ? '#38BDF8' : '#2DD4BF'}
          emissive={node.isHub ? '#38BDF8' : '#2DD4BF'}
          emissiveIntensity={2.5}
        />
      </mesh>

      {/* Pulsing beacon ring on surface */}
      <mesh ref={ringRef} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[node.isHub ? 0.06 : 0.04, node.isHub ? 0.09 : 0.055, 32]} />
        <meshBasicMaterial
          color={node.isHub ? '#38BDF8' : '#2DD4BF'}
          transparent
          opacity={node.isHub ? 0.8 : 0.45}
          side={THREE.DoubleSide}
        />
      </mesh>
    </group>
  );
}

// 3D Earth Globe Model
function EarthGlobeModel({
  customMarkers = [],
}: {
  customMarkers?: { position: [number, number, number]; riskLevel: RiskLevel; label: string }[];
}) {
  const globeGroupRef = useRef<THREE.Group>(null!);

  // Load official NASA satellite Earth texture
  const earthMap = useTexture('/textures/earth_day.jpg');
  earthMap.colorSpace = THREE.SRGBColorSpace;

  const hubNode = TELEMETRY_NODES.find((n) => n.isHub) || TELEMETRY_NODES[0];
  const arcSources = TELEMETRY_NODES.filter((n) => !n.isHub);

  // Background regional interconnecting arcs
  const extraArcs = [
    { from: TELEMETRY_NODES[5], to: TELEMETRY_NODES[4], speed: 0.22, offset: 0.2 }, // Europe -> UAE
    { from: TELEMETRY_NODES[4], to: TELEMETRY_NODES[1], speed: 0.26, offset: 0.4 }, // UAE -> India
    { from: TELEMETRY_NODES[1], to: TELEMETRY_NODES[2], speed: 0.35, offset: 0.1 }, // India -> Nepal
    { from: TELEMETRY_NODES[3], to: TELEMETRY_NODES[8], speed: 0.24, offset: 0.6 }, // China -> Vietnam
    { from: TELEMETRY_NODES[8], to: TELEMETRY_NODES[7], speed: 0.28, offset: 0.8 }, // Vietnam -> Malaysia
    { from: TELEMETRY_NODES[7], to: TELEMETRY_NODES[9], speed: 0.30, offset: 0.3 }, // Malaysia -> Philippines
  ];

  return (
    // Rotated so South Asia, India, Bangladesh and regional telemetry face front-center
    <group ref={globeGroupRef} rotation={[-0.28, Math.PI + 0.08, 0]}>
      {/* Photorealistic Earth Sphere with Satellite Textures */}
      <mesh>
        <sphereGeometry args={[GLOBE_RADIUS, 64, 64]} />
        <meshStandardMaterial
          map={earthMap}
          roughness={0.55}
          metalness={0.05}
        />
      </mesh>

      {/* Atmospheric Soft Blue Outer Halo */}
      <mesh scale={[1.025, 1.025, 1.025]}>
        <sphereGeometry args={[GLOBE_RADIUS, 64, 64]} />
        <meshBasicMaterial
          color="#38BDF8"
          transparent
          opacity={0.2}
          side={THREE.BackSide}
        />
      </mesh>

      <mesh scale={[1.14, 1.14, 1.14]}>
        <sphereGeometry args={[GLOBE_RADIUS, 32, 32]} />
        <meshBasicMaterial
          color="#0284c7"
          transparent
          opacity={0.08}
          side={THREE.BackSide}
        />
      </mesh>

      {/* Primary Trajectory Arcs to Bangladesh Hub */}
      {arcSources.map((source, idx) => (
        <TrajectoryArc
          key={`arc-${source.id}`}
          startNode={source}
          endNode={hubNode}
          speed={0.2 + (idx % 4) * 0.05}
          offset={(idx * 0.15) % 1}
        />
      ))}

      {/* Regional Interconnecting Arcs */}
      {extraArcs.map((extra, idx) => (
        <TrajectoryArc
          key={`extra-${idx}`}
          startNode={extra.from}
          endNode={extra.to}
          speed={extra.speed}
          offset={extra.offset}
        />
      ))}

      {/* Glowing Surface Telemetry Nodes (No country flags) */}
      {TELEMETRY_NODES.map((node) => (
        <SurfaceNode key={node.id} node={node} />
      ))}

      {/* Custom district markers if provided */}
      {customMarkers.map((m, i) => (
        <group key={`custom-${i}`} position={m.position}>
          <mesh>
            <sphereGeometry args={[0.045, 16, 16]} />
            <meshStandardMaterial
              color={RISK_COLORS[m.riskLevel] || '#38BDF8'}
              emissive={RISK_COLORS[m.riskLevel] || '#38BDF8'}
              emissiveIntensity={2}
            />
          </mesh>
        </group>
      ))}
    </group>
  );
}

// Fallback sphere while texture is decoding
function FallbackSphere() {
  return (
    <mesh>
      <sphereGeometry args={[GLOBE_RADIUS, 32, 32]} />
      <meshStandardMaterial color="#0c2d48" roughness={0.5} />
    </mesh>
  );
}

export interface MarkerProps {
  position: [number, number, number];
  riskLevel: RiskLevel;
  label: string;
}

export interface BangladeshGlobeProps {
  markers?: MarkerProps[];
  className?: string;
  height?: string | number;
  autoRotate?: boolean;
}

export default function BangladeshGlobe({
  markers = [],
  className = '',
  autoRotate = true,
}: BangladeshGlobeProps) {
  return (
    <div
      className={`relative w-full h-full min-h-[380px] ${className}`}
      aria-label="Interactive 3D Earth Globe with Real-Time Telemetry Arcs to Bangladesh"
    >
      <Canvas
        camera={{ position: [0, 0.3, 5.2], fov: 45 }}
        dpr={[1, 2]}
        gl={{ antialias: true, alpha: true }}
      >
        <ambientLight intensity={1.05} />
        <directionalLight position={[4, 4, 4]} intensity={2.2} color="#ffffff" />
        <directionalLight position={[-4, 1, -4]} intensity={0.65} color="#38bdf8" />

        <Suspense fallback={<FallbackSphere />}>
          <EarthGlobeModel customMarkers={markers} />
        </Suspense>

        <OrbitControls
          enableZoom={true}
          enablePan={false}
          minDistance={3.2}
          maxDistance={8.5}
          minPolarAngle={Math.PI / 6}
          maxPolarAngle={(5 * Math.PI) / 6}
          autoRotate={autoRotate}
          autoRotateSpeed={0.25}
        />
      </Canvas>
    </div>
  );
}
