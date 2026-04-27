import { Line, OrbitControls, Text } from '@react-three/drei';
import { Canvas, useThree } from '@react-three/fiber';
import { useMemo } from 'react';
import * as THREE from 'three';

import type { Annotation, ThreeScene } from '../types/scene';

/* ------------------------------------------------------------------ */
/*  Types                                                             */
/* ------------------------------------------------------------------ */

interface ThreeGeometryViewProps {
  scene: ThreeScene;
}

type Vec3 = { x: number; y: number; z: number };

/* ------------------------------------------------------------------ */
/*  Root component                                                    */
/* ------------------------------------------------------------------ */

export function ThreeGeometryView({ scene }: ThreeGeometryViewProps) {
  const frame = getSceneFrame(scene);

  return (
    <div className="viewer-card">
      <div className="viewer-header">Three.js Renderer</div>
      <Canvas camera={{ position: [5, 4, 6], fov: 48 }} className="three-view" style={{ display: 'block' }}>
        <color attach="background" args={["#f8fbff"]} />
        <ambientLight intensity={0.7} />
        <directionalLight position={[6, 10, 6]} intensity={0.85} />
        <OrbitControls makeDefault target={[0, 0, 0]} />
        {scene.view.show_grid && <gridHelper args={[10, 10, '#d4ddec', '#e9eef7']} />}
        {scene.view.show_axes && <OxyzAxes hideOriginLabel={hasPointAtOrigin(scene)} />}
        <group position={[-frame.center.x, -frame.center.y, -frame.center.z]} scale={frame.scale}>
          <Faces scene={scene} />
          <Spheres scene={scene} />
          <Segments scene={scene} />
          <Points scene={scene} />
          <Annotations scene={scene} />
        </group>
      </Canvas>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Oxyz Axes with labels                                             */
/* ------------------------------------------------------------------ */

function OxyzAxes({ hideOriginLabel = false }: { hideOriginLabel?: boolean }) {
  const axisLen = 4.5;
  const arrowLen = 0.2;

  return (
    <group>
      {/* X axis — red */}
      <Line points={[[0, 0, 0], [axisLen, 0, 0]]} color="#e63946" lineWidth={2} />
      <Line points={[[axisLen, 0, 0], [axisLen - arrowLen, arrowLen * 0.5, 0]]} color="#e63946" lineWidth={2} />
      <Line points={[[axisLen, 0, 0], [axisLen - arrowLen, -arrowLen * 0.5, 0]]} color="#e63946" lineWidth={2} />
      <Text position={[axisLen + 0.3, 0, 0]} fontSize={0.32} color="#e63946" anchorX="left">x</Text>

      {/* Y axis — green */}
      <Line points={[[0, 0, 0], [0, axisLen, 0]]} color="#2a9d8f" lineWidth={2} />
      <Line points={[[0, axisLen, 0], [arrowLen * 0.5, axisLen - arrowLen, 0]]} color="#2a9d8f" lineWidth={2} />
      <Line points={[[0, axisLen, 0], [-arrowLen * 0.5, axisLen - arrowLen, 0]]} color="#2a9d8f" lineWidth={2} />
      <Text position={[0, axisLen + 0.3, 0]} fontSize={0.32} color="#2a9d8f" anchorX="center">y</Text>

      {/* Z axis — blue */}
      <Line points={[[0, 0, 0], [0, 0, axisLen]]} color="#2563eb" lineWidth={2} />
      <Line points={[[0, 0, axisLen], [0, arrowLen * 0.5, axisLen - arrowLen]]} color="#2563eb" lineWidth={2} />
      <Line points={[[0, 0, axisLen], [0, -arrowLen * 0.5, axisLen - arrowLen]]} color="#2563eb" lineWidth={2} />
      <Text position={[0, 0, axisLen + 0.3]} fontSize={0.32} color="#2563eb" anchorX="center">z</Text>

      {!hideOriginLabel && <Text position={[-0.25, -0.25, 0]} fontSize={0.28} color="#475569" anchorX="right">O</Text>}
    </group>
  );
}

/* ------------------------------------------------------------------ */
/*  Scene frame calculation                                           */
/* ------------------------------------------------------------------ */

function getSceneFrame(scene: ThreeScene) {
  const points = Object.values(scene.points);
  if (points.length === 0) {
    return { center: { x: 0, y: 0, z: 0 }, scale: 1 };
  }

  const min = { x: Infinity, y: Infinity, z: Infinity };
  const max = { x: -Infinity, y: -Infinity, z: -Infinity };

  points.forEach((point) => {
    min.x = Math.min(min.x, point.x);
    min.y = Math.min(min.y, point.y);
    min.z = Math.min(min.z, point.z);
    max.x = Math.max(max.x, point.x);
    max.y = Math.max(max.y, point.y);
    max.z = Math.max(max.z, point.z);
  });

  const center = {
    x: (min.x + max.x) / 2,
    y: (min.y + max.y) / 2,
    z: (min.z + max.z) / 2,
  };
  const size = Math.max(max.x - min.x, max.y - min.y, max.z - min.z, 1);

  return { center, scale: 4.5 / size };
}

function hasPointAtOrigin(scene: ThreeScene) {
  return Object.values(scene.points).some((point) => Math.abs(point.x) < 1e-6 && Math.abs(point.y) < 1e-6 && Math.abs(point.z) < 1e-6);
}

/* ------------------------------------------------------------------ */
/*  Faces                                                             */
/* ------------------------------------------------------------------ */

function Faces({ scene }: ThreeGeometryViewProps) {
  return (
    <>
      {scene.faces.map((face) => {
        const vertices = face.points.map((name) => scene.points[name]).filter(Boolean);
        if (vertices.length < 3) return null;
        const geometry = new THREE.BufferGeometry();
        const first = vertices[0];
        const positions: number[] = [];
        for (let index = 1; index < vertices.length - 1; index += 1) {
          [first, vertices[index], vertices[index + 1]].forEach((point) => {
            positions.push(point.x, point.y, point.z);
          });
        }
        geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
        geometry.computeVertexNormals();
        return (
          <mesh key={face.name ?? face.points.join('-')} geometry={geometry}>
            <meshStandardMaterial color={face.color} opacity={face.opacity} transparent side={THREE.DoubleSide} />
          </mesh>
        );
      })}
    </>
  );
}

/* ------------------------------------------------------------------ */
/*  Spheres                                                           */
/* ------------------------------------------------------------------ */

function Spheres({ scene }: ThreeGeometryViewProps) {
  return (
    <>
      {(scene.spheres ?? []).map((sphere) => {
        const center = scene.points[sphere.center];
        if (!center) return null;
        return (
          <mesh key={sphere.name ?? sphere.center} position={[center.x, center.y, center.z]}>
            <sphereGeometry args={[sphere.radius, 48, 24]} />
            <meshStandardMaterial
              color={sphere.color}
              opacity={Math.min(sphere.opacity, 0.22)}
              transparent
              depthWrite={false}
              side={THREE.DoubleSide}
            />
          </mesh>
        );
      })}
    </>
  );
}

/* ------------------------------------------------------------------ */
/*  Segments                                                          */
/* ------------------------------------------------------------------ */

function Segments({ scene }: ThreeGeometryViewProps) {
  return (
    <>
      {scene.segments.map((segment, index) => {
        const [startName, endName] = segment.points;
        const start = scene.points[startName];
        const end = scene.points[endName];
        if (!start || !end) return null;
        return (
          <Line
            key={`${startName}-${endName}-${index}`}
            points={[
              [start.x, start.y, start.z],
              [end.x, end.y, end.z],
            ]}
            color={segment.hidden ? '#8b95a7' : '#1d3557'}
            dashed={segment.hidden}
            dashSize={0.12}
            gapSize={0.08}
            lineWidth={3}
          />
        );
      })}
    </>
  );
}

/* ------------------------------------------------------------------ */
/*  Points with labels & optional coordinates                         */
/* ------------------------------------------------------------------ */

function Points({ scene }: ThreeGeometryViewProps) {
  const showCoords = scene.view.show_coordinates;

  return (
    <>
      {Object.entries(scene.points).map(([name, point]) => {
        const coordText = `(${fmtN(point.x)}, ${fmtN(point.y)}, ${fmtN(point.z)})`;
        return (
          <group key={name} position={[point.x, point.y, point.z]}>
            <mesh>
              <sphereGeometry args={[0.08, 16, 16]} />
              <meshStandardMaterial color="#e63946" />
            </mesh>
            <Text position={[0.14, 0.18, 0]} fontSize={0.28} color="#1d3557" anchorX="left" anchorY="middle" fontWeight={700}>
              {name}
            </Text>
            {showCoords && (
              <Text position={[0.14, -0.12, 0]} fontSize={0.18} color="#64748b" anchorX="left" anchorY="middle">
                {coordText}
              </Text>
            )}
          </group>
        );
      })}
    </>
  );
}

/* ------------------------------------------------------------------ */
/*  Annotations                                                       */
/* ------------------------------------------------------------------ */

function Annotations({ scene }: ThreeGeometryViewProps) {
  const annotations = scene.annotations ?? [];

  return (
    <>
      {annotations.map((ann, index) => {
        switch (ann.type) {
          case 'right_angle':
            return <RightAngleMark key={`ra-${index}`} ann={ann} points={scene.points} />;
          case 'equal_marks':
            return <EqualMarks key={`em-${index}`} ann={ann} points={scene.points} />;
          case 'length':
            return <LengthLabel key={`ll-${index}`} ann={ann} points={scene.points} />;
          case 'angle':
            return <AngleLabel key={`al-${index}`} ann={ann} points={scene.points} />;
          default:
            return null;
        }
      })}
    </>
  );
}

/* ------------------------------------------------------------------ */
/*  Right-angle mark (small square)                                   */
/* ------------------------------------------------------------------ */

function RightAngleMark({ ann, points }: { ann: Annotation; points: Record<string, Vec3> }) {
  const vertex = points[ann.target];
  const arms = (ann.metadata?.arms as string[]) ?? [];
  if (!vertex || arms.length < 2) return null;

  const p1 = points[arms[0]];
  const p2 = points[arms[1]];
  if (!p1 || !p2) return null;

  const size = 0.22;

  const d1 = normalize(sub(p1, vertex));
  const d2 = normalize(sub(p2, vertex));

  const a = add(vertex, scale(d1, size));
  const corner = add(add(vertex, scale(d1, size)), scale(d2, size));
  const b = add(vertex, scale(d2, size));

  return (
    <Line
      points={[
        [a.x, a.y, a.z],
        [corner.x, corner.y, corner.z],
        [b.x, b.y, b.z],
      ]}
      color="#e63946"
      lineWidth={2}
    />
  );
}

/* ------------------------------------------------------------------ */
/*  Equal-length tick marks                                           */
/* ------------------------------------------------------------------ */

function EqualMarks({ ann, points }: { ann: Annotation; points: Record<string, Vec3> }) {
  const [startName, endName] = ann.target.split('-');
  const p1 = points[startName];
  const p2 = points[endName];
  if (!p1 || !p2) return null;

  const group = (ann.metadata?.group as number) ?? 1;
  const mid = midpoint(p1, p2);
  const dir = normalize(sub(p2, p1));

  // perpendicular in a visible direction — use cross with camera-ish up
  const up = { x: 0, y: 1, z: 0 };
  let perp = cross(dir, up);
  if (length(perp) < 0.01) {
    perp = cross(dir, { x: 1, y: 0, z: 0 });
  }
  perp = normalize(perp);

  const tickLen = 0.12;
  const spacing = 0.1;

  const ticks: JSX.Element[] = [];
  for (let i = 0; i < group; i++) {
    const offset = (i - (group - 1) / 2) * spacing;
    const center = add(mid, scale(dir, offset));
    const t1 = add(center, scale(perp, tickLen));
    const t2 = add(center, scale(perp, -tickLen));
    ticks.push(
      <Line
        key={i}
        points={[[t1.x, t1.y, t1.z], [t2.x, t2.y, t2.z]]}
        color={ann.color ?? '#e63946'}
        lineWidth={2.5}
      />
    );
  }

  return <>{ticks}</>;
}

/* ------------------------------------------------------------------ */
/*  Length label on a segment                                         */
/* ------------------------------------------------------------------ */

function LengthLabel({ ann, points }: { ann: Annotation; points: Record<string, Vec3> }) {
  const [startName, endName] = ann.target.split('-');
  const p1 = points[startName];
  const p2 = points[endName];
  if (!p1 || !p2 || !ann.label) return null;

  const mid = midpoint(p1, p2);
  const dir = normalize(sub(p2, p1));
  const up = { x: 0, y: 1, z: 0 };
  let perp = cross(dir, up);
  if (length(perp) < 0.01) {
    perp = cross(dir, { x: 1, y: 0, z: 0 });
  }
  perp = normalize(perp);

  const offset = add(mid, scale(perp, 0.28));

  return (
    <Text
      position={[offset.x, offset.y, offset.z]}
      fontSize={0.22}
      color={ann.color ?? '#7c3aed'}
      anchorX="center"
      anchorY="middle"
      fontWeight={700}
    >
      {ann.label}
    </Text>
  );
}

/* ------------------------------------------------------------------ */
/*  Angle label                                                       */
/* ------------------------------------------------------------------ */

function AngleLabel({ ann, points }: { ann: Annotation; points: Record<string, Vec3> }) {
  const vertex = points[ann.target];
  const arms = (ann.metadata?.arms as string[]) ?? [];
  if (!vertex || arms.length < 2 || !ann.label) return null;

  const p1 = points[arms[0]];
  const p2 = points[arms[1]];
  if (!p1 || !p2) return null;

  const d1 = normalize(sub(p1, vertex));
  const d2 = normalize(sub(p2, vertex));
  const bisector = normalize(add(d1, d2));
  const labelPos = add(vertex, scale(bisector, 0.5));

  return (
    <Text
      position={[labelPos.x, labelPos.y, labelPos.z]}
      fontSize={0.2}
      color={ann.color ?? '#b45309'}
      anchorX="center"
      anchorY="middle"
      fontWeight={700}
    >
      {ann.label}
    </Text>
  );
}

/* ------------------------------------------------------------------ */
/*  Vector math helpers                                               */
/* ------------------------------------------------------------------ */

function sub(a: Vec3, b: Vec3): Vec3 {
  return { x: a.x - b.x, y: a.y - b.y, z: a.z - b.z };
}

function add(a: Vec3, b: Vec3): Vec3 {
  return { x: a.x + b.x, y: a.y + b.y, z: a.z + b.z };
}

function scale(v: Vec3, s: number): Vec3 {
  return { x: v.x * s, y: v.y * s, z: v.z * s };
}

function length(v: Vec3): number {
  return Math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z);
}

function normalize(v: Vec3): Vec3 {
  const len = length(v);
  if (len < 1e-9) return { x: 0, y: 0, z: 0 };
  return { x: v.x / len, y: v.y / len, z: v.z / len };
}

function cross(a: Vec3, b: Vec3): Vec3 {
  return {
    x: a.y * b.z - a.z * b.y,
    y: a.z * b.x - a.x * b.z,
    z: a.x * b.y - a.y * b.x,
  };
}

function midpoint(a: Vec3, b: Vec3): Vec3 {
  return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, z: (a.z + b.z) / 2 };
}

function fmtN(n: number): string {
  return Number.isInteger(n) ? n.toString() : n.toFixed(1);
}
