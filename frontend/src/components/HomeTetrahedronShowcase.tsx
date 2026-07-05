import { Edges, OrbitControls, Float, Grid, GizmoHelper, GizmoViewport, Sparkles } from '@react-three/drei';
import { Canvas, useFrame } from '@react-three/fiber';
import { Suspense, useMemo, useRef } from 'react';
import * as THREE from 'three';

function OrbitingElements() {
  const ringRef = useRef<THREE.Group>(null);
  const satelliteRef = useRef<THREE.Mesh>(null);

  useFrame((state) => {
    const t = state.clock.getElapsedTime();
    if (ringRef.current) {
      ringRef.current.rotation.x = Math.PI / 2 + Math.sin(t * 0.2) * 0.2;
      ringRef.current.rotation.y = t * 0.15;
    }
    if (satelliteRef.current) {
      satelliteRef.current.position.x = Math.cos(t * 0.8) * 3.5;
      satelliteRef.current.position.z = Math.sin(t * 0.8) * 3.5;
      satelliteRef.current.position.y = Math.sin(t * 0.5) * 1.2;
      satelliteRef.current.rotation.x += 0.02;
      satelliteRef.current.rotation.y += 0.02;
    }
  });

  return (
    <group>
      <group ref={ringRef}>
        <mesh>
          <torusGeometry args={[3.2, 0.015, 16, 100]} />
          <meshBasicMaterial color="#38bdf8" transparent opacity={0.3} />
        </mesh>
        <mesh rotation={[Math.PI / 2.5, 0, 0]}>
          <torusGeometry args={[3.8, 0.01, 16, 100]} />
          <meshBasicMaterial color="#f97316" transparent opacity={0.22} />
        </mesh>
      </group>
      
      <mesh ref={satelliteRef}>
        <tetrahedronGeometry args={[0.25]} />
        <meshStandardMaterial color="#fef08a" emissive="#facc15" emissiveIntensity={1.2} />
        <pointLight intensity={8} color="#facc15" distance={3} />
        <Edges color="#ffffff" threshold={10} />
      </mesh>
    </group>
  );
}

function PolyhedronFaces() {
  const groupRef = useRef<THREE.Group>(null);
  const palette = ['#2563eb', '#06b6d4', '#22c55e', '#84cc16', '#f59e0b', '#f97316', '#ef4444', '#ec4899', '#8b5cf6', '#6366f1'];
  const geometry = useMemo(() => {
    const shape = new THREE.IcosahedronGeometry(2.05, 0);
    shape.clearGroups();
    for (let face = 0; face < 20; face += 1) {
      shape.addGroup(face * 3, 3, face % palette.length);
    }
    return shape;
  }, [palette.length]);

  useFrame(() => {
    if (groupRef.current) {
      groupRef.current.rotation.y += 0.005;
    }
  });

  return (
    <group ref={groupRef}>
      <mesh geometry={geometry}>
        {palette.map((color, index) => (
          <meshPhysicalMaterial
            key={color}
            attach={`material-${index}`}
            color={color}
            transparent
            opacity={0.56}
            transmission={0.22}
            roughness={0.42}
            metalness={0.02}
            side={THREE.DoubleSide}
          />
        ))}
        <Edges color="#ffffff" threshold={10} opacity={0.78} transparent />
      </mesh>
      <pointLight intensity={12} color="#ffffff" distance={4} />
    </group>
  );
}

function BackgroundParticles() {
  const count = 60;
  const meshRef = useRef<THREE.Group>(null);
  
  const particles = useMemo(() => {
    const temp = [];
    for (let i = 0; i < count; i++) {
      const t = Math.random() * 100;
      const factor = 25 + Math.random() * 150;
      const speed = 0.005 + Math.random() / 300;
      const xFactor = -10 + Math.random() * 20;
      const yFactor = -10 + Math.random() * 20;
      const zFactor = -10 + Math.random() * 20;
      const type = Math.floor(Math.random() * 3); // 0: octa, 1: sphere, 2: cube
      temp.push({ t, factor, speed, xFactor, yFactor, zFactor, type, color: Math.random() > 0.5 ? '#38bdf8' : '#f472b6' });
    }
    return temp;
  }, [count]);

  useFrame((state) => {
    particles.forEach((particle, i) => {
      const { factor, xFactor, yFactor, zFactor } = particle;
      const s = state.clock.getElapsedTime();
      const p = meshRef.current?.children[i];
      if (p) {
        p.position.set(
          Math.cos(s * 0.15 + xFactor) * factor * 0.12,
          Math.sin(s * 0.15 + yFactor) * factor * 0.12,
          Math.sin(s * 0.15 + zFactor) * factor * 0.12
        );
        p.rotation.y += 0.01;
        p.rotation.z += 0.005;
      }
    });
  });

  return (
    <group ref={meshRef}>
      {particles.map((p, i) => (
        <mesh key={i}>
          {p.type === 0 ? <octahedronGeometry args={[0.07, 0]} /> : p.type === 1 ? <sphereGeometry args={[0.05, 8, 8]} /> : <boxGeometry args={[0.06, 0.06, 0.06]} />}
          <meshBasicMaterial color={p.color} transparent opacity={0.2} />
        </mesh>
      ))}
    </group>
  );
}

function Scene({ hideHelpers = false }: { hideHelpers?: boolean }) {
  const lightRef = useRef<THREE.SpotLight>(null);
  useFrame((state) => {
    if (lightRef.current) {
      lightRef.current.position.x = Math.sin(state.clock.getElapsedTime() * 0.4) * 15;
      lightRef.current.position.z = Math.cos(state.clock.getElapsedTime() * 0.4) * 15;
    }
  });

  return (
    <>
      <ambientLight intensity={0.7} />
      <spotLight ref={lightRef} position={[15, 15, 15]} angle={0.2} penumbra={1} intensity={10} color="#e0f2fe" />
      <pointLight position={[-15, -15, -15]} intensity={5} color="#fce7f3" />
      
      <Sparkles count={80} scale={12} size={2} speed={0.5} opacity={0.42} color="#60a5fa" />
      
      <BackgroundParticles />
      <OrbitingElements />
      
      <Float speed={1.5} rotationIntensity={0.2} floatIntensity={0.4}>
        <PolyhedronFaces />
      </Float>

      {/* Far Background Large Wireframes */}
      <group>
        <mesh position={[-10, 8, -15]} rotation={[0.5, 0.5, 0.5]}>
          <boxGeometry args={[5, 5, 5]} />
          <meshBasicMaterial color="#60a5fa" wireframe transparent opacity={0.08} />
        </mesh>
        <mesh position={[12, -5, -18]} rotation={[-0.2, 0.8, 0.3]}>
          <dodecahedronGeometry args={[4]} />
          <meshBasicMaterial color="#c084fc" wireframe transparent opacity={0.08} />
        </mesh>
      </group>

      {/* Coordinate Grid */}
      {!hideHelpers && (
        <Grid
          infiniteGrid
          fadeDistance={25}
          fadeStrength={5}
          sectionSize={1.5}
          sectionColor="#38bdf8"
          sectionThickness={2}
          cellSize={0.75}
          cellColor="#c4b5fd"
          cellThickness={1}
          position={[0, -2.5, 0]}
        />
      )}

      {/* Axes Helper */}
      {!hideHelpers && <primitive object={new THREE.AxesHelper(4)} position={[0, -2.5, 0]} />}

      <OrbitControls 
        enableDamping 
        dampingFactor={0.06} 
        rotateSpeed={0.5} 
        enableZoom={false} 
        enablePan={false} 
        minPolarAngle={0.5} 
        maxPolarAngle={Math.PI - 0.5} 
      />
      
      {/* Visual Axis Indicator */}
      {!hideHelpers && (
        <GizmoHelper alignment="bottom-right" margin={[80, 80]}>
          <GizmoViewport axisColors={['#ef4444', '#22c55e', '#3b82f6']} labelColor="white" />
        </GizmoHelper>
      )}
    </>
  );
}

export function HomeTetrahedronShowcase({ hideHelpers = false }: { hideHelpers?: boolean }) {
  return (
    <div className="home-tetrahedron-wrap" style={{ cursor: 'grab', width: '100%', height: '100%' }}>
      <Canvas
        className="home-tetrahedron-canvas"
        dpr={[1, 2]}
        gl={{ 
          antialias: true, 
          alpha: true, 
          stencil: false, 
          depth: true, 
          powerPreference: 'high-performance' 
        }}
        camera={{ position: [5, 3.5, 6], fov: 40 }}
        onCreated={({ scene, gl }) => {
          scene.background = null;
          gl.setPixelRatio(Math.min(window.devicePixelRatio ?? 1, 2));
        }}
      >
        <Suspense fallback={null}>
          <Scene hideHelpers={hideHelpers} />
        </Suspense>
      </Canvas>
    </div>
  );
}

