import { Billboard, Edges, OrbitControls, Text } from '@react-three/drei';
import { Canvas } from '@react-three/fiber';
import { Suspense, useMemo } from 'react';
import * as THREE from 'three';

function uniqueVertices(geometry: THREE.BufferGeometry): THREE.Vector3[] {
  const positions = geometry.getAttribute('position');
  const out: THREE.Vector3[] = [];
  for (let i = 0; i < positions.count; i++) {
    const v = new THREE.Vector3().fromBufferAttribute(positions, i);
    if (!out.some((u) => u.distanceToSquared(v) < 1e-5)) out.push(v);
  }
  return out;
}

function TetrahedronModel() {
  const geometry = useMemo(() => new THREE.TetrahedronGeometry(1.55), []);

  const labelEntries = useMemo(() => {
    const verts = uniqueVertices(geometry);
    if (verts.length !== 4) return [];
    const sortedByY = [...verts].sort((a, b) => b.y - a.y);
    const s = sortedByY[0]!;
    const base = verts.filter((v) => v.distanceToSquared(s) > 1e-3).sort((a, b) => Math.atan2(a.z, a.x) - Math.atan2(b.z, b.x));
    if (base.length !== 3) return [];
    return [
      ['S', s.clone()],
      ['A', base[0]!.clone()],
      ['B', base[1]!.clone()],
      ['C', base[2]!.clone()],
    ] as const;
  }, [geometry]);

  return (
    <group rotation={[0.1, Math.PI / 12, -0.15]}>
      <mesh geometry={geometry}>
        <meshPhysicalMaterial color="#eaeaea" metalness={0.16} roughness={0.24} clearcoat={0.55} clearcoatRoughness={0.22} polygonOffset polygonOffsetFactor={1} polygonOffsetUnits={1} />
        <Edges color="#0a0a0a" threshold={50} />
      </mesh>
      {labelEntries.map(([letter, pt]: readonly [string, THREE.Vector3]) => {
        const outward = pt.clone().normalize().multiplyScalar(0.42);
        const pos: [number, number, number] = [pt.x + outward.x, pt.y + outward.y, pt.z + outward.z];
        return (
          <Billboard follow key={letter} position={pos}>
            <Text color="#171717" fontSize={0.36} anchorX="center" anchorY="middle" outlineWidth={0.02} outlineColor="#ffffff" outlineOpacity={1} letterSpacing={-0.04}>
              {letter}
            </Text>
          </Billboard>
        );
      })}
    </group>
  );
}

function Scene() {
  return (
    <>
      <ambientLight intensity={0.5} />
      <directionalLight position={[9, 12, 7]} intensity={1.08} />
      <directionalLight position={[-6, -4, -5]} intensity={0.42} />
      <Suspense fallback={null}>
        <TetrahedronModel />
      </Suspense>
      <OrbitControls enableDamping dampingFactor={0.06} rotateSpeed={0.75} enableZoom={false} enablePan={false} minPolarAngle={0.52} maxPolarAngle={Math.PI - 0.48} />
    </>
  );
}

export function HomeTetrahedronShowcase() {
  return (
    <div className="home-tetrahedron-wrap">
      <Canvas
        className="home-tetrahedron-canvas"
        dpr={[1, 2]}
        gl={{ antialias: true, alpha: true, stencil: false, depth: true, powerPreference: 'high-performance' }}
        camera={{ position: [0, 1.05, 5.1], near: 0.08, far: 64, fov: 40 }}
        onCreated={({ scene, gl }) => {
          scene.background = null;
          gl.setPixelRatio(Math.min(window.devicePixelRatio ?? 1, 2));
        }}
      >
        <Scene />
      </Canvas>
    </div>
  );
}
