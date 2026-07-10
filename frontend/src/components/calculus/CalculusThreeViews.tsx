import { OrbitControls, Text } from '@react-three/drei';
import { Canvas } from '@react-three/fiber';
import { useMemo } from 'react';
import * as THREE from 'three';

import type { CompiledExpression } from '../../utils/calculusExpression';
import { safeEval } from '../../utils/calculusNumerics';

type SurfaceProps = {
  f: CompiledExpression;
  g?: CompiledExpression | null;
  a: number;
  b: number;
  sweep: number;
  sliceX: number;
  visibleDisks?: number;
  totalDisks?: number;
  showDiskStack?: boolean;
  showSelectedSlice?: boolean;
  showSurface?: boolean;
  /** Ox: disk/washer quanh Ox. Oy: vỏ trụ (shell) quanh Oy — geometry map trục. */
  axis?: 'Ox' | 'Oy';
};

type CrossSectionProps = {
  areaAt: (x: number) => number;
  a: number;
  b: number;
  sliceX: number;
  visibleSlices: number;
  totalSlices: number;
  shape: 'square' | 'rectangle' | 'triangle' | 'circle';
  ratio?: number;
  showSelectedSlice?: boolean;
};

export function RevolutionThreeView(props: SurfaceProps) {
  return (
    <div className="csim-three-card">
      <Canvas camera={{ position: [6.4, 4.1, 6.9], fov: 45 }} gl={{ antialias: true, alpha: false }} dpr={[1, 2]} className="csim-three-canvas" onCreated={({ gl }) => gl.setClearColor('#f6f6f4', 1)}>
        <color attach="background" args={["#f6f6f4"]} />
        <ambientLight intensity={0.9} />
        <directionalLight position={[5, 8, 6]} intensity={1.1} />
        <OrbitControls makeDefault target={[0, 0, 0]} />
        <gridHelper args={[8, 12, '#d6deeb', '#ecf1f8']} />
        <RevolutionScene {...props} />
      </Canvas>
    </div>
  );
}

export function CrossSectionThreeView(props: CrossSectionProps) {
  return (
    <div className="csim-three-card">
      <Canvas camera={{ position: [5.5, 4.2, 6], fov: 45 }} gl={{ antialias: true, alpha: false }} dpr={[1, 2]} className="csim-three-canvas" onCreated={({ gl }) => gl.setClearColor('#f6f6f4', 1)}>
        <color attach="background" args={["#f6f6f4"]} />
        <ambientLight intensity={0.9} />
        <directionalLight position={[5, 8, 6]} intensity={1.1} />
        <OrbitControls makeDefault target={[0, 0, 0]} />
        <gridHelper args={[8, 12, '#d6deeb', '#ecf1f8']} />
        <CrossSectionScene {...props} />
      </Canvas>
    </div>
  );
}

function RevolutionScene({ f, g, a, b, sweep, sliceX, visibleDisks = 0, totalDisks = 36, showDiskStack = false, showSelectedSlice = true, showSurface = true, axis = 'Ox' }: SurfaceProps) {
  const frame = useMemo(() => buildRevolutionFrame(f, g, a, b), [f, g, a, b]);
  const outerGeometry = useMemo(
    () => buildSurfaceGeometry(f, a, b, Math.max(0.02, sweep), frame.scale, frame.radiusScale, axis),
    [f, a, b, sweep, frame, axis],
  );
  const innerGeometry = useMemo(
    () => (g ? buildSurfaceGeometry(g, a, b, Math.max(0.02, sweep), frame.scale, frame.radiusScale, axis) : null),
    [g, a, b, sweep, frame, axis],
  );
  const caps = useMemo(() => [buildWasherSlice(f, g, a, frame.scale, frame.radiusScale), buildWasherSlice(f, g, b, frame.scale, frame.radiusScale)], [f, g, a, b, frame]);
  const disks = useMemo(() => buildRevolutionDisks(f, g, a, b, totalDisks, visibleDisks, frame.scale, frame.radiusScale), [f, g, a, b, totalDisks, visibleDisks, frame]);
  const slice = useMemo(() => buildWasherSlice(f, g, sliceX, frame.scale, frame.radiusScale), [f, g, sliceX, frame]);
  const offset = axis === 'Oy'
    ? ([0, -frame.centerX * frame.scale, 0] as const)
    : ([-frame.centerX * frame.scale, 0, 0] as const);
  const slicePos = (xScaled: number): [number, number, number] => (axis === 'Oy' ? [0, xScaled, 0] : [xScaled, 0, 0]);
  const sliceRot: [number, number, number] = axis === 'Oy' ? [Math.PI / 2, 0, 0] : [0, Math.PI / 2, 0];
  const labelPos: [number, number, number] = axis === 'Oy'
    ? [(slice?.outer ?? 1) + 0.35, slice?.x ?? 0, 0]
    : [slice?.x ?? 0, (slice?.outer ?? 1) + 0.35, 0];

  return (
    <group position={[...offset]}>
      <Axes3D />
      {showSurface && (
        <>
          <mesh geometry={outerGeometry}>
            <meshStandardMaterial color="#111111" opacity={0.42} transparent side={THREE.DoubleSide} roughness={0.45} />
          </mesh>
          {innerGeometry && (
            <mesh geometry={innerGeometry}>
              <meshStandardMaterial color="#f97316" opacity={0.22} transparent side={THREE.DoubleSide} roughness={0.5} />
            </mesh>
          )}
          {axis === 'Ox' && caps.map((cap, index) => cap && (
            <mesh key={`cap-${index}`} geometry={cap.geometry} position={slicePos(cap.x)} rotation={sliceRot}>
              <meshStandardMaterial color="#64748b" opacity={0.24} transparent side={THREE.DoubleSide} roughness={0.55} />
            </mesh>
          ))}
        </>
      )}
      {showDiskStack && disks.map((disk, index) => (
        <mesh key={`disk-${index}`} geometry={disk.geometry} position={slicePos(disk.x)} rotation={sliceRot}>
          <meshStandardMaterial color={axis === 'Oy' ? '#0d9488' : '#64748b'} opacity={0.28} transparent side={THREE.DoubleSide} roughness={0.55} />
        </mesh>
      ))}
      {showSelectedSlice && slice && (
        <mesh geometry={slice.geometry} position={slicePos(slice.x)} rotation={sliceRot}>
          <meshStandardMaterial color="#0f172a" opacity={0.54} transparent side={THREE.DoubleSide} roughness={0.45} />
        </mesh>
      )}
      {showSelectedSlice && (
        <Text position={labelPos} fontSize={0.22} color="#166534" anchorX="center">
          x = {sliceX.toFixed(2)}
        </Text>
      )}
    </group>
  );
}

function CrossSectionScene({ areaAt, a, b, sliceX, visibleSlices, totalSlices, shape, ratio = 1.5, showSelectedSlice = false }: CrossSectionProps) {
  const width = 5.2;
  const center = (a + b) / 2;
  const scale = width / Math.max(b - a, 1e-6);
  const shapeScale = useMemo(() => computeCrossSectionScale(areaAt, a, b, shape, ratio), [areaAt, a, b, shape, ratio]);
  const slices = useMemo(() => {
    const count = Math.max(1, totalSlices);
    const dx = (b - a) / count;
    return Array.from({ length: Math.min(visibleSlices, count) }, (_, index) => {
      const sourceX = a + (index + 0.5) * dx;
      return { x: (sourceX - center) * scale, sourceX, thickness: Math.max(dx * scale * 0.72, 0.015) };
    });
  }, [a, b, center, scale, totalSlices, visibleSlices]);
  const selectedArea = Math.max(0, areaAt(sliceX));
  const selectedX = (sliceX - center) * scale;
  const selectedGeometry = useMemo(() => buildSectionFaceGeometry(selectedArea, shape, ratio, shapeScale), [selectedArea, shape, ratio, shapeScale]);
  return (
    <group>
      <Axes3D />
      {slices.map((slice, index) => (
        <SectionSlab key={index} area={Math.max(0, areaAt(slice.sourceX))} x={slice.x} thickness={slice.thickness} shape={shape} ratio={ratio} scale={shapeScale} />
      ))}
      {showSelectedSlice && (
        <mesh geometry={selectedGeometry} position={[selectedX, 0, 0]} rotation={[0, Math.PI / 2, 0]}>
          <meshStandardMaterial color="#0f172a" opacity={0.44} transparent side={THREE.DoubleSide} roughness={0.45} />
        </mesh>
      )}
      {showSelectedSlice && (
        <Text position={[selectedX, 2.2, 0]} fontSize={0.22} color="#111111" anchorX="center">
          S(x) = {selectedArea.toFixed(3)}
        </Text>
      )}
    </group>
  );
}

function SectionSlab({ area, x, thickness, shape, ratio, scale }: { area: number; x: number; thickness: number; shape: CrossSectionProps['shape']; ratio: number; scale: number }) {
  const geometry = useMemo(() => buildSectionExtrudeGeometry(area, shape, ratio, scale, thickness), [area, shape, ratio, scale, thickness]);
  return (
    <mesh geometry={geometry} position={[x, 0, 0]} rotation={[0, Math.PI / 2, 0]}>
      <meshStandardMaterial color="#475569" opacity={0.24} transparent side={THREE.DoubleSide} roughness={0.55} />
    </mesh>
  );
}

function computeCrossSectionScale(areaAt: (x: number) => number, a: number, b: number, shape: CrossSectionProps['shape'], ratio: number) {
  let maxExtent = 1;
  for (let i = 0; i <= 80; i += 1) {
    const x = a + ((b - a) * i) / 80;
    const dims = sectionDimensions(Math.max(0, areaAt(x)), shape, ratio);
    maxExtent = Math.max(maxExtent, dims.height, dims.depth, dims.radius * 2);
  }
  return 2.5 / maxExtent;
}

function sectionDimensions(area: number, shape: CrossSectionProps['shape'], ratio: number) {
  if (!Number.isFinite(area) || area <= 0) return { height: 0.001, depth: 0.001, radius: 0.001 };
  if (shape === 'square') {
    const side = Math.sqrt(area);
    return { height: side, depth: side, radius: side / Math.SQRT2 };
  }
  if (shape === 'rectangle') {
    const width = Math.sqrt(area / Math.max(ratio, 1e-6));
    return { height: width * ratio, depth: width, radius: Math.hypot(width * ratio, width) / 2 };
  }
  if (shape === 'triangle') {
    const side = Math.sqrt((4 * area) / Math.sqrt(3));
    return { height: (Math.sqrt(3) / 2) * side, depth: side, radius: side / Math.sqrt(3) };
  }
  const radius = Math.sqrt(area / Math.PI);
  return { height: radius * 2, depth: radius * 2, radius };
}

function buildSectionShape(area: number, shape: CrossSectionProps['shape'], ratio: number, scale: number) {
  const dims = sectionDimensions(area, shape, ratio);
  const s = new THREE.Shape();
  if (shape === 'circle') {
    s.absarc(0, 0, dims.radius * scale, 0, Math.PI * 2, false);
    return s;
  }
  if (shape === 'triangle') {
    const h = dims.height * scale;
    const w = dims.depth * scale;
    s.moveTo(0, (2 * h) / 3);
    s.lineTo(-w / 2, -h / 3);
    s.lineTo(w / 2, -h / 3);
    s.closePath();
    return s;
  }
  const h = dims.height * scale;
  const w = dims.depth * scale;
  s.moveTo(-w / 2, -h / 2);
  s.lineTo(w / 2, -h / 2);
  s.lineTo(w / 2, h / 2);
  s.lineTo(-w / 2, h / 2);
  s.closePath();
  return s;
}

function buildSectionFaceGeometry(area: number, shape: CrossSectionProps['shape'], ratio: number, scale: number) {
  const geometry = new THREE.ShapeGeometry(buildSectionShape(area, shape, ratio, scale), 48);
  geometry.computeVertexNormals();
  return geometry;
}

function buildSectionExtrudeGeometry(area: number, shape: CrossSectionProps['shape'], ratio: number, scale: number, thickness: number) {
  const geometry = new THREE.ExtrudeGeometry(buildSectionShape(area, shape, ratio, scale), { depth: thickness, bevelEnabled: false, curveSegments: 48 });
  geometry.translate(0, 0, -thickness / 2);
  geometry.computeVertexNormals();
  return geometry;
}

function buildRevolutionFrame(f: CompiledExpression, g: CompiledExpression | null | undefined, a: number, b: number) {
  let maxRadius = 1;
  for (let i = 0; i <= 120; i += 1) {
    const x = a + ((b - a) * i) / 120;
    maxRadius = Math.max(maxRadius, Math.abs(safeEval(f, x)), g ? Math.abs(safeEval(g, x)) : 0);
  }
  return { centerX: (a + b) / 2, scale: 4.8 / Math.max(b - a, 1e-6), radiusScale: 2.2 / maxRadius };
}

function buildSurfaceGeometry(
  fn: CompiledExpression,
  a: number,
  b: number,
  sweep: number,
  xScale: number,
  radiusScale: number,
  axis: 'Ox' | 'Oy' = 'Ox',
) {
  const xSegments = 96;
  const thetaSegments = Math.max(3, Math.floor(56 * (sweep / (Math.PI * 2))));
  const positions: number[] = [];
  const indices: number[] = [];
  for (let i = 0; i <= xSegments; i += 1) {
    const x = a + ((b - a) * i) / xSegments;
    const radius = Math.max(0, safeEval(fn, x)) * radiusScale;
    for (let j = 0; j <= thetaSegments; j += 1) {
      const theta = (sweep * j) / thetaSegments;
      // Ox: quay quanh trục x → (x, r cos, r sin)
      // Oy: quay quanh trục y → (r cos, x, r sin) — vỏ trụ / solid quanh Oy
      if (axis === 'Oy') positions.push(Math.cos(theta) * radius, x * xScale, Math.sin(theta) * radius);
      else positions.push(x * xScale, Math.cos(theta) * radius, Math.sin(theta) * radius);
    }
  }
  const row = thetaSegments + 1;
  for (let i = 0; i < xSegments; i += 1) {
    for (let j = 0; j < thetaSegments; j += 1) {
      const a0 = i * row + j;
      const b0 = a0 + row;
      indices.push(a0, b0, a0 + 1, b0, b0 + 1, a0 + 1);
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  return geometry;
}

function buildRevolutionDisks(f: CompiledExpression, g: CompiledExpression | null | undefined, a: number, b: number, total: number, visible: number, xScale: number, radiusScale: number) {
  const count = Math.max(1, Math.floor(total));
  const shown = Math.max(0, Math.min(count, Math.floor(visible)));
  const dx = (b - a) / count;
  return Array.from({ length: shown }, (_, index) => {
    const x = a + (index + 0.5) * dx;
    return buildWasherDisk(f, g, x, dx * xScale * 0.74, xScale, radiusScale);
  }).filter(Boolean) as Array<{ x: number; geometry: THREE.BufferGeometry }>;
}

function buildWasherDisk(f: CompiledExpression, g: CompiledExpression | null | undefined, x: number, thickness: number, xScale: number, radiusScale: number) {
  const shape = buildWasherShape(f, g, x, radiusScale);
  if (!shape) return null;
  const geometry = new THREE.ExtrudeGeometry(shape.shape, { depth: Math.max(thickness, 0.012), bevelEnabled: false, curveSegments: 56 });
  geometry.translate(0, 0, -Math.max(thickness, 0.012) / 2);
  geometry.computeVertexNormals();
  return { x: x * xScale, outer: shape.outer, geometry };
}

function buildWasherSlice(f: CompiledExpression, g: CompiledExpression | null | undefined, x: number, xScale: number, radiusScale: number) {
  const shape = buildWasherShape(f, g, x, radiusScale);
  if (!shape) return null;
  const geometry = new THREE.ShapeGeometry(shape.shape, 56);
  geometry.computeVertexNormals();
  return { x: x * xScale, outer: shape.outer, geometry };
}

function buildWasherShape(f: CompiledExpression, g: CompiledExpression | null | undefined, x: number, radiusScale: number) {
  const outerRaw = Math.max(0, safeEval(f, x), g ? safeEval(g, x) : 0);
  const innerRaw = g ? Math.max(0, Math.min(safeEval(f, x), safeEval(g, x))) : 0;
  const outer = outerRaw * radiusScale;
  const inner = innerRaw * radiusScale;
  if (!Number.isFinite(outer) || outer <= 0) return null;
  const shape = new THREE.Shape();
  shape.absarc(0, 0, outer, 0, Math.PI * 2, false);
  if (inner > 0.001) {
    const hole = new THREE.Path();
    hole.absarc(0, 0, inner, 0, Math.PI * 2, true);
    shape.holes.push(hole);
  }
  return { shape, outer };
}

function Axes3D() {
  return (
    <group>
      <lineSegments>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[new Float32Array([-3, 0, 0, 3, 0, 0, 0, -2.4, 0, 0, 2.4, 0, 0, 0, -2.4, 0, 0, 2.4]), 3]} />
        </bufferGeometry>
        <lineBasicMaterial color="#94a3b8" />
      </lineSegments>
      <Text position={[3.15, 0, 0]} fontSize={0.22} color="#e11d48">x</Text>
      <Text position={[0, 2.55, 0]} fontSize={0.22} color="#16a34a">y</Text>
      <Text position={[0, 0, 2.55]} fontSize={0.22} color="#111111">z</Text>
    </group>
  );
}
