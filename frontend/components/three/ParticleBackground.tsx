'use client';

import { useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import * as THREE from 'three';

function Particles({ count = 800 }: { count?: number }) {
  const mesh = useRef<THREE.Points>(null!);

  const [positions, velocities] = useMemo(() => {
    const pos = new Float32Array(count * 3);
    const vel = new Float32Array(count);
    for (let i = 0; i < count; i++) {
      pos[i * 3] = (Math.random() - 0.5) * 60;
      pos[i * 3 + 1] = (Math.random() - 0.5) * 40;
      pos[i * 3 + 2] = (Math.random() - 0.5) * 20;
      vel[i] = 0.008 + Math.random() * 0.012;
    }
    return [pos, vel];
  }, [count]);

  useFrame(() => {
    const posArray = mesh.current.geometry.attributes.position.array as Float32Array;
    for (let i = 0; i < count; i++) {
      posArray[i * 3 + 1] += velocities[i];
      if (posArray[i * 3 + 1] > 20) {
        posArray[i * 3 + 1] = -20;
      }
    }
    mesh.current.geometry.attributes.position.needsUpdate = true;
  });

  return (
    <points ref={mesh}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[positions, 3]}
        />
      </bufferGeometry>
      <pointsMaterial
        size={0.08}
        color="#38BDF8"
        transparent
        opacity={0.35}
        sizeAttenuation
      />
    </points>
  );
}

export default function ParticleBackground() {
  // Respect prefers-reduced-motion: show static background if user prefers reduced motion
  const prefersReducedMotion = typeof window !== 'undefined' 
    ? window.matchMedia('(prefers-reduced-motion: reduce)').matches 
    : false;

  if (prefersReducedMotion) {
    // Static background without animations for accessibility
    return (
      <div
        className="fixed inset-0 -z-10 pointer-events-none"
        aria-hidden="true"
        style={{ background: 'linear-gradient(135deg, #060B14 0%, #0B1730 100%)' }}
      />
    );
  }

  return (
    <div
      className="fixed inset-0 -z-10 pointer-events-none"
      aria-hidden="true"
      style={{ background: 'linear-gradient(135deg, #060B14 0%, #0B1730 100%)' }}
    >
      <Canvas
        camera={{ position: [0, 0, 30], fov: 60 }}
        gl={{ antialias: false, alpha: true }}
        dpr={[1, 1.5]}
      >
        <ambientLight intensity={0.2} />
        <Particles />
      </Canvas>
    </div>
  );
}
