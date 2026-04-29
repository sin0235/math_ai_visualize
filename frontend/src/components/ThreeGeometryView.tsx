import { Billboard, Line, OrbitControls, Text } from '@react-three/drei';
import { Canvas, ThreeEvent, useThree } from '@react-three/fiber';
import type { ComponentProps, ReactNode } from 'react';
import { useEffect, useMemo, useRef, useState } from 'react';
import * as THREE from 'three';

import type { Annotation, ThreeScene } from '../types/scene';

interface ThreeGeometryViewProps {
  scene: ThreeScene;
  interaction?: ThreeSceneInteraction;
  embedded?: boolean;
}

export interface ThreeSceneInteraction {
  mode: 'move' | 'connect' | 'project_to_segment' | 'add_point';
  selectedPoint: string | null;
  pointPlacementPlane: 'xy' | 'xz' | 'yz';
  pointPlacementDepth: number;
  onPointClick: (name: string) => void;
  onSegmentClick: (points: [string, string], point: Vec3) => void;
  onPointDragEnd: (name: string, point: Vec3) => void;
  onConnectPoints: (start: string, end: string) => void;
  onCanvasClick: (point: Vec3) => void;
}

type Vec3 = { x: number; y: number; z: number };
type SceneFrame = ReturnType<typeof getSceneFrame>;

export function ThreeGeometryView({ scene, interaction, embedded = false }: ThreeGeometryViewProps) {
  const [workingScene, setWorkingScene] = useState(scene);
  const [draggingPoint, setDraggingPoint] = useState<string | null>(null);
  const [hoveredPoint, setHoveredPoint] = useState<string | null>(null);
  const [connectStart, setConnectStart] = useState<string | null>(null);
  const [connectHover, setConnectHover] = useState<string | null>(null);
  const [connectPreview, setConnectPreview] = useState<Vec3 | null>(null);
  const [showAxes, setShowAxes] = useState(scene.view.show_axes);
  const frame = getSceneFrame(scene);
  const editingEnabled = Boolean(interaction);
  const controlsEnabled = !draggingPoint && !connectStart;
  const controlsMouseButtons = editingEnabled
    ? { MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.ROTATE }
    : { LEFT: THREE.MOUSE.ROTATE, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.PAN };

  useEffect(() => {
    setWorkingScene(scene);
    setDraggingPoint(null);
    setHoveredPoint(null);
    setConnectStart(null);
    setConnectHover(null);
    setConnectPreview(null);
    setShowAxes(scene.view.show_axes);
  }, [scene]);

  function updatePoint(name: string, point: Vec3) {
    setWorkingScene((current) => ({
      ...current,
      points: {
        ...current.points,
        [name]: point,
      },
    }));
  }

  function finishPointDrag(name: string, point: Vec3) {
    setDraggingPoint(null);
    interaction?.onPointDragEnd(name, point);
  }

  function beginConnect(name: string) {
    setConnectStart(name);
    setConnectHover(null);
    setConnectPreview(workingScene.points[name] ?? null);
  }

  function finishConnect(targetName?: string | null) {
    if (connectStart && targetName && targetName !== connectStart) {
      interaction?.onConnectPoints(connectStart, targetName);
    }
    setConnectStart(null);
    setConnectHover(null);
    setConnectPreview(null);
  }

  const content = (
    <Canvas camera={{ position: [5, 4, 6], fov: 48 }} className="three-view" style={{ display: 'block' }}>
      <color attach="background" args={["#f8fbff"]} />
      <ambientLight intensity={0.7} />
      <directionalLight position={[6, 10, 6]} intensity={0.85} />
      <OrbitControls makeDefault target={[0, 0, 0]} enabled={controlsEnabled} mouseButtons={controlsMouseButtons} />
      {workingScene.view.show_grid && <gridHelper args={[10, 10, '#d4ddec', '#e9eef7']} />}
      {showAxes && <OxyzAxes hideOriginLabel={hasPointAtOrigin(workingScene)} />}
      <group
        position={[-frame.center.x * frame.scale, -frame.center.y * frame.scale, -frame.center.z * frame.scale]}
        scale={frame.scale}
        onPointerDown={(event) => {
          if (interaction?.mode !== 'add_point') return;
          event.stopPropagation();

          const plane = addPointPlane(interaction.pointPlacementPlane, interaction.pointPlacementDepth, frame);
          const hit = event.ray.intersectPlane(plane, new THREE.Vector3());
          if (!hit) return;

          interaction.onCanvasClick(worldToScene(hit, frame));
        }}
        onPointerMove={(event) => {
          if (!connectStart || interaction?.mode !== 'connect') return;
          event.stopPropagation();
          setConnectPreview(worldToScene(event.point, frame));
        }}
        onPointerUp={(event) => {
          if (!connectStart) return;
          event.stopPropagation();
          finishConnect(connectHover);
        }}
        onPointerLeave={() => {
          if (!connectStart) return;
          setConnectPreview(null);
        }}
      >
        <Planes scene={workingScene} />
        <Faces scene={workingScene} />
        <Spheres scene={workingScene} />
        <Lines3D scene={workingScene} />
        <Segments scene={workingScene} frame={frame} interaction={interaction} />
        <Vectors scene={workingScene} />
        <ComputedIntersections scene={workingScene} />
        <ComputedMeasurements scene={workingScene} />
        <ConnectPreview scene={workingScene} start={connectStart} end={connectHover ? workingScene.points[connectHover] : connectPreview} />
        <Points
          scene={workingScene}
          frame={frame}
          draggingPoint={draggingPoint}
          connectStart={connectStart}
          connectHover={connectHover}
          interaction={interaction}
          onPointHover={setHoveredPoint}
          onConnectStart={beginConnect}
          onConnectHover={setConnectHover}
          onConnectEnd={finishConnect}
          onDragStart={setDraggingPoint}
          onDragEnd={finishPointDrag}
          onPointChange={updatePoint}
        />
        <Annotations scene={workingScene} />
      </group>
    </Canvas>
  );

  if (embedded) return content;

  return (
    <div className="viewer-card">
      <div className="viewer-header viewer-header-row">
        <span>Three.js Renderer</span>
        <div className="viewer-controls">
          <span className="viewer-hint">{viewerHint(interaction?.mode)}</span>
          <button type="button" className="viewer-toggle" onClick={() => setShowAxes((current) => !current)}>
            {showAxes ? 'Tắt hệ trục' : 'Bật hệ trục'}
          </button>
        </div>
      </div>
      {content}
    </div>
  );
}

type LabelTextProps = Omit<ComponentProps<typeof Text>, 'position'> & {
  position: [number, number, number];
  children: ReactNode;
};

function LabelText({ position, children, ...props }: LabelTextProps) {
  const textRef = useRef<any>(null);

  useEffect(() => {
    const material = textRef.current?.material;
    if (!material) return;
    material.depthTest = false;
    material.depthWrite = false;
    material.needsUpdate = true;
  }, []);

  return (
    <Billboard position={position} follow renderOrder={20}>
      <Text
        ref={textRef}
        outlineWidth={0.012}
        outlineColor="rgba(255,255,255,0.9)"
        fillOpacity={1}
        renderOrder={20}
        {...props}
      >
        {children}
      </Text>
    </Billboard>
  );
}

function OxyzAxes({ hideOriginLabel = false }: { hideOriginLabel?: boolean }) {
  const axisLen = 4.5;
  const arrowLen = 0.2;

  return (
    <group>
      <Line points={[[0, 0, 0], [axisLen, 0, 0]]} color="#e63946" lineWidth={2} />
      <Line points={[[axisLen, 0, 0], [axisLen - arrowLen, arrowLen * 0.5, 0]]} color="#e63946" lineWidth={2} />
      <Line points={[[axisLen, 0, 0], [axisLen - arrowLen, -arrowLen * 0.5, 0]]} color="#e63946" lineWidth={2} />
      <LabelText position={[axisLen + 0.3, 0, 0]} fontSize={0.32} color="#e63946" anchorX="left">x</LabelText>

      <Line points={[[0, 0, 0], [0, axisLen, 0]]} color="#2a9d8f" lineWidth={2} />
      <Line points={[[0, axisLen, 0], [arrowLen * 0.5, axisLen - arrowLen, 0]]} color="#2a9d8f" lineWidth={2} />
      <Line points={[[0, axisLen, 0], [-arrowLen * 0.5, axisLen - arrowLen, 0]]} color="#2a9d8f" lineWidth={2} />
      <LabelText position={[0, axisLen + 0.3, 0]} fontSize={0.32} color="#2a9d8f" anchorX="center">y</LabelText>

      <Line points={[[0, 0, 0], [0, 0, axisLen]]} color="#2563eb" lineWidth={2} />
      <Line points={[[0, 0, axisLen], [0, arrowLen * 0.5, axisLen - arrowLen]]} color="#2563eb" lineWidth={2} />
      <Line points={[[0, 0, axisLen], [0, -arrowLen * 0.5, axisLen - arrowLen]]} color="#2563eb" lineWidth={2} />
      <LabelText position={[0, 0, axisLen + 0.3]} fontSize={0.32} color="#2563eb" anchorX="center">z</LabelText>

      {!hideOriginLabel && <LabelText position={[-0.25, -0.25, 0]} fontSize={0.28} color="#475569" anchorX="right">O</LabelText>}
    </group>
  );
}

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

function Planes({ scene }: ThreeGeometryViewProps) {
  const allPoints = Object.values(scene.points);

  return (
    <>
      {(scene.planes ?? []).map((plane) => {
        const anchors = plane.points.map((name) => scene.points[name]).filter(Boolean);
        const vertices = expandedPlaneVertices(anchors, allPoints);
        const geometry = polygonGeometry(vertices);
        if (!geometry) return null;
        const center = centroid(vertices);
        return (
          <group key={plane.name ?? plane.points.join('-')}>
            <mesh geometry={geometry}>
              <meshStandardMaterial color={plane.color} opacity={Math.min(plane.opacity, 0.18)} transparent side={THREE.DoubleSide} depthWrite={false} />
            </mesh>
            {plane.name && (
              <LabelText position={[center.x, center.y + 0.14, center.z]} fontSize={0.2} color={plane.color} anchorX="center" anchorY="middle" fontWeight={700}>
                {plane.name}
              </LabelText>
            )}
          </group>
        );
      })}
    </>
  );
}

function Faces({ scene }: ThreeGeometryViewProps) {
  return (
    <>
      {scene.faces.map((face) => {
        const vertices = face.points.map((name) => scene.points[name]).filter(Boolean);
        const geometry = polygonGeometry(vertices);
        if (!geometry) return null;
        return (
          <mesh key={face.name ?? face.points.join('-')} geometry={geometry}>
            <meshStandardMaterial color={face.color} opacity={face.opacity} transparent side={THREE.DoubleSide} depthWrite={false} />
          </mesh>
        );
      })}
    </>
  );
}

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

function Lines3D({ scene }: ThreeGeometryViewProps) {
  return (
    <>
      {(scene.lines ?? []).map((line, index) => {
        const [startName, endName] = line.through;
        const start = scene.points[startName];
        const end = scene.points[endName];
        if (!start || !end) return null;
        const direction = normalize(sub(end, start));
        if (length(direction) < 1e-9) return null;
        const mid = midpoint(start, end);
        const extent = 5;
        const p1 = add(mid, scale(direction, -extent));
        const p2 = add(mid, scale(direction, extent));
        return (
          <Line
            key={`${line.name ?? startName + endName}-${index}`}
            points={[[p1.x, p1.y, p1.z], [p2.x, p2.y, p2.z]]}
            color={line.color ?? '#334155'}
            lineWidth={2}
            dashed
            dashSize={0.18}
            gapSize={0.1}
          />
        );
      })}
    </>
  );
}

function Segments({ scene, frame, interaction }: ThreeGeometryViewProps & { frame: SceneFrame; interaction?: ThreeSceneInteraction }) {
  return (
    <>
      {scene.segments.map((segment, index) => {
        const [startName, endName] = segment.points;
        const start = scene.points[startName];
        const end = scene.points[endName];
        if (!start || !end) return null;
        const dashed = segment.hidden || segment.style === 'dashed' || segment.style === 'dotted';
        return (
          <Line
            key={`${startName}-${endName}-${index}`}
            points={[
              [start.x, start.y, start.z],
              [end.x, end.y, end.z],
            ]}
            color={segment.color ?? (segment.hidden ? '#8b95a7' : '#1d3557')}
            dashed={dashed}
            dashSize={segment.style === 'dotted' ? 0.04 : 0.12}
            gapSize={segment.style === 'dotted' ? 0.08 : 0.08}
            lineWidth={interaction ? Math.max(segment.line_width ?? 3, 5) : segment.line_width ?? 3}
            onClick={(event) => {
              if (interaction?.mode !== 'project_to_segment') return;
              event.stopPropagation();
              interaction.onSegmentClick(segment.points, worldToScene(event.point, frame));
            }}
            onPointerOver={(event) => {
              if (interaction?.mode !== 'project_to_segment') return;
              event.stopPropagation();
              document.body.style.cursor = 'crosshair';
            }}
            onPointerOut={() => {
              if (interaction?.mode !== 'project_to_segment') return;
              document.body.style.cursor = '';
            }}
          />
        );
      })}
    </>
  );
}

function Vectors({ scene }: ThreeGeometryViewProps) {
  const explicitVectors = (scene.vectors ?? []).map((vector) => {
    const from = scene.points[vector.from_point];
    const to = scene.points[vector.to_point];
    if (!from || !to) return null;
    return { name: vector.name, from, to, color: vector.color };
  }).filter(Boolean) as Array<{ name?: string | null; from: Vec3; to: Vec3; color: string }>;

  const computedVectors = (scene.computed?.vectors ?? []).map((vector) => ({
    name: vector.name,
    from: vector.from,
    to: vector.to,
    color: vector.color,
  }));

  return (
    <>
      {[...explicitVectors, ...computedVectors].map((vector, index) => (
        <ArrowVector key={`${vector.name ?? 'vector'}-${index}`} from={vector.from} to={vector.to} color={vector.color} label={vector.name ?? undefined} />
      ))}
    </>
  );
}

function ComputedIntersections({ scene }: ThreeGeometryViewProps) {
  return (
    <>
      {(scene.computed?.intersections ?? []).map((intersection, index) => {
        if (intersection.status !== 'intersect' || !intersection.point) return null;
        const point = intersection.point;
        const label = intersection.type === 'line_line'
          ? `I(${intersection.object_1},${intersection.object_2})`
          : `I(${intersection.line},${intersection.plane})`;
        return (
          <group key={`intersection-${index}`} position={[point.x, point.y, point.z]}>
            <mesh>
              <sphereGeometry args={[0.1, 16, 16]} />
              <meshStandardMaterial color="#f59e0b" />
            </mesh>
            <LabelText position={[0.14, 0.18, 0]} fontSize={0.2} color="#b45309" anchorX="left" anchorY="middle" fontWeight={700}>
              {label}
            </LabelText>
          </group>
        );
      })}
    </>
  );
}

function ComputedMeasurements({ scene }: ThreeGeometryViewProps) {
  return (
    <>
      {(scene.computed?.measurements ?? []).map((measurement, index) => {
        if (measurement.type !== 'sphere_plane_distance' || measurement.minimum_distance == null) return null;
        const label = `dmin = ${fmtN(measurement.minimum_distance)}`;
        const start = measurement.nearest_sphere_point;
        const end = measurement.plane_foot;
        if (measurement.minimum_distance > 1e-6 && start && end) {
          const mid = midpoint(start, end);
          return (
            <group key={`measurement-${index}`}>
              <Line points={[[start.x, start.y, start.z], [end.x, end.y, end.z]]} color="#f59e0b" lineWidth={3} dashed dashSize={0.1} gapSize={0.06} />
              <mesh position={[start.x, start.y, start.z]}>
                <sphereGeometry args={[0.09, 16, 16]} />
                <meshStandardMaterial color="#f59e0b" />
              </mesh>
              <mesh position={[end.x, end.y, end.z]}>
                <sphereGeometry args={[0.07, 16, 16]} />
                <meshStandardMaterial color="#2563eb" />
              </mesh>
              <LabelText position={[mid.x, mid.y + 0.2, mid.z]} fontSize={0.22} color="#b45309" anchorX="center" anchorY="middle" fontWeight={700}>
                {label}
              </LabelText>
            </group>
          );
        }
        if (!end) return null;
        return (
          <LabelText key={`measurement-${index}`} position={[end.x, end.y + 0.24, end.z]} fontSize={0.22} color="#b45309" anchorX="center" anchorY="middle" fontWeight={700}>
            {label}
          </LabelText>
        );
      })}
    </>
  );
}

function ArrowVector({ from, to, color, label }: { from: Vec3; to: Vec3; color: string; label?: string }) {
  const direction = normalize(sub(to, from));
  const size = length(sub(to, from));
  if (size < 1e-9) return null;
  const arrow = new THREE.ArrowHelper(
    new THREE.Vector3(direction.x, direction.y, direction.z),
    new THREE.Vector3(from.x, from.y, from.z),
    size,
    color,
    Math.min(size * 0.22, 0.25),
    Math.min(size * 0.1, 0.12),
  );
  const labelPos = add(to, scale(direction, 0.14));
  return (
    <group>
      <primitive object={arrow} />
      {label && (
        <LabelText position={[labelPos.x, labelPos.y, labelPos.z]} fontSize={0.2} color={color} anchorX="center" anchorY="middle" fontWeight={700}>
          {label}
        </LabelText>
      )}
    </group>
  );
}

interface PointsProps extends ThreeGeometryViewProps {
  frame: SceneFrame;
  draggingPoint: string | null;
  connectStart: string | null;
  connectHover: string | null;
  interaction?: ThreeSceneInteraction;
  onPointHover: (name: string | null) => void;
  onConnectStart: (name: string) => void;
  onConnectHover: (name: string | null) => void;
  onConnectEnd: (name?: string | null) => void;
  onDragStart: (name: string) => void;
  onDragEnd: (name: string, point: Vec3) => void;
  onPointChange: (name: string, point: Vec3) => void;
}

function Points({
  scene,
  frame,
  draggingPoint,
  connectStart,
  connectHover,
  interaction,
  onPointHover,
  onConnectStart,
  onConnectHover,
  onConnectEnd,
  onDragStart,
  onDragEnd,
  onPointChange,
}: PointsProps) {
  const showCoords = scene.view.show_coordinates;
  const sortedPoints = useMemo(() => Object.entries(scene.points).sort(([nameA], [nameB]) => nameA.localeCompare(nameB)), [scene.points]);

  return (
    <>
      {sortedPoints.map(([name, point], index) => {
        const coordText = `(${fmtN(point.x)}, ${fmtN(point.y)}, ${fmtN(point.z)})`;
        const labelOffset = pointLabelOffset(index);
        return (
          <DraggablePoint
            key={name}
            name={name}
            point={point}
            coordText={coordText}
            labelOffset={labelOffset}
            frame={frame}
            isDragging={draggingPoint === name}
            isSelected={interaction?.selectedPoint === name}
            isConnectSource={connectStart === name}
            isConnectHover={connectHover === name}
            showCoords={showCoords}
            dimension={scene.view.dimension}
            mode={interaction?.mode ?? 'move'}
            onPointClick={interaction?.onPointClick}
            onPointHover={onPointHover}
            onConnectStart={onConnectStart}
            onConnectHover={onConnectHover}
            onConnectEnd={onConnectEnd}
            onDragStart={onDragStart}
            onDragEnd={onDragEnd}
            onPointChange={onPointChange}
          />
        );
      })}
    </>
  );
}

interface DraggablePointProps {
  name: string;
  point: Vec3;
  coordText: string;
  labelOffset: Vec3;
  frame: SceneFrame;
  isDragging: boolean;
  isSelected: boolean;
  isConnectSource: boolean;
  isConnectHover: boolean;
  showCoords: boolean;
  dimension: '2d' | '3d';
  mode: ThreeSceneInteraction['mode'];
  onPointClick?: (name: string) => void;
  onPointHover: (name: string | null) => void;
  onConnectStart: (name: string) => void;
  onConnectHover: (name: string | null) => void;
  onConnectEnd: (name?: string | null) => void;
  onDragStart: (name: string) => void;
  onDragEnd: (name: string, point: Vec3) => void;
  onPointChange: (name: string, point: Vec3) => void;
}

function DraggablePoint({ name, point, coordText, labelOffset, frame, isDragging, isSelected, isConnectSource, isConnectHover, showCoords, dimension, mode, onPointClick, onPointHover, onConnectStart, onConnectHover, onConnectEnd, onDragStart, onDragEnd, onPointChange }: DraggablePointProps) {
  const { camera, gl } = useThree();
  const [hovered, setHovered] = useState(false);
  const dragPlaneRef = useRef<THREE.Plane | null>(null);
  const intersectionRef = useRef(new THREE.Vector3());

  function beginDrag(event: ThreeEvent<PointerEvent>) {
    event.stopPropagation();
    if (mode === 'add_point') {
      // Ở chế độ chấm để thêm điểm, click lên điểm hiện có không kéo/không tạo điểm mới ở đây.
      return;
    }
    if (mode === 'project_to_segment') {
      onPointClick?.(name);
      return;
    }
    if (mode === 'connect') {
      gl.domElement.style.cursor = 'crosshair';
      onConnectStart(name);
      return;
    }
    gl.domElement.setPointerCapture(event.pointerId);
    gl.domElement.style.cursor = 'grabbing';
    onDragStart(name);

    const worldPoint = sceneToWorld(point, frame);
    if (dimension === '2d') {
      dragPlaneRef.current = new THREE.Plane(new THREE.Vector3(0, 0, 1), -worldPoint.z);
      return;
    }

    const normal = new THREE.Vector3();
    camera.getWorldDirection(normal);
    dragPlaneRef.current = new THREE.Plane().setFromNormalAndCoplanarPoint(normal, worldPoint);
  }

  function drag(event: ThreeEvent<PointerEvent>) {
    if (!isDragging || !dragPlaneRef.current) return;
    event.stopPropagation();
    const hit = event.ray.intersectPlane(dragPlaneRef.current, intersectionRef.current);
    if (!hit) return;
    onPointChange(name, worldToScene(hit, frame));
  }

  function endDrag(event: ThreeEvent<PointerEvent>) {
    if (mode === 'connect') {
      event.stopPropagation();
      gl.domElement.style.cursor = hovered ? 'crosshair' : '';
      onConnectEnd(isConnectHover ? name : null);
      return;
    }
    if (!isDragging) return;
    event.stopPropagation();
    if (gl.domElement.hasPointerCapture(event.pointerId)) {
      gl.domElement.releasePointerCapture(event.pointerId);
    }
    dragPlaneRef.current = null;
    gl.domElement.style.cursor = hovered ? 'grab' : '';
    onDragEnd(name, point);
  }

  return (
    <group position={[point.x, point.y, point.z]}>
      <mesh
        onPointerDown={beginDrag}
        onPointerMove={drag}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onPointerOver={(event) => {
          event.stopPropagation();
          setHovered(true);
          onPointHover(name);
          if (mode === 'connect') onConnectHover(name);
          gl.domElement.style.cursor = mode === 'connect' || mode === 'add_point' ? 'crosshair' : 'grab';
        }}
        onPointerOut={() => {
          setHovered(false);
          onPointHover(null);
          if (mode === 'connect') onConnectHover(null);
          if (!isDragging) gl.domElement.style.cursor = '';
        }}
      >
        <sphereGeometry args={[hovered || isDragging || isSelected || isConnectSource || isConnectHover ? 0.13 : 0.08, 16, 16]} />
        <meshStandardMaterial color={pointColor({ isSelected, isDragging, isConnectSource, isConnectHover, hovered })} />
      </mesh>
      <LabelText position={[labelOffset.x, labelOffset.y, labelOffset.z]} fontSize={0.28} color="#1d3557" anchorX="center" anchorY="middle" fontWeight={700}>
        {name}
      </LabelText>
      {showCoords && (
        <LabelText position={[labelOffset.x, labelOffset.y - 0.22, labelOffset.z]} fontSize={0.18} color="#64748b" anchorX="center" anchorY="middle">
          {coordText}
        </LabelText>
      )}
    </group>
  );
}

function pointLabelOffset(index: number): Vec3 {
  const offsets = [
    { x: 0.2, y: 0.24, z: 0.04 },
    { x: -0.2, y: 0.24, z: 0.04 },
    { x: 0.22, y: -0.2, z: 0.04 },
    { x: -0.22, y: -0.2, z: 0.04 },
    { x: 0, y: 0.32, z: 0.08 },
    { x: 0.28, y: 0.04, z: 0.08 },
    { x: -0.28, y: 0.04, z: 0.08 },
    { x: 0, y: -0.3, z: 0.08 },
  ];
  return offsets[index % offsets.length];
}

function ConnectPreview({ scene, start, end }: { scene: ThreeScene; start: string | null; end: Vec3 | null }) {
  if (!start || !end) return null;
  const startPoint = scene.points[start];
  if (!startPoint) return null;
  return (
    <Line
      points={[[startPoint.x, startPoint.y, startPoint.z], [end.x, end.y, end.z]]}
      color="#f97316"
      lineWidth={3}
      dashed
      dashSize={0.12}
      gapSize={0.08}
    />
  );
}

function pointColor({ isSelected, isDragging, isConnectSource, isConnectHover, hovered }: { isSelected: boolean; isDragging: boolean; isConnectSource: boolean; isConnectHover: boolean; hovered: boolean }) {
  if (isConnectHover) return '#f97316';
  if (isConnectSource) return '#2563eb';
  if (isSelected) return '#2563eb';
  if (isDragging) return '#111111';
  if (hovered) return '#f97316';
  return '#e63946';
}

function viewerHint(mode?: ThreeSceneInteraction['mode']) {
  if (mode === 'connect') return 'Chuột trái kéo nối đoạn, chuột phải xoay hình';
  if (mode === 'project_to_segment') return 'Chuột trái chọn điểm/đoạn, chuột phải xoay hình';
  if (mode === 'add_point') return 'Chuột trái click để thêm điểm, chuột phải xoay hình';
  return 'Chuột trái kéo điểm, chuột phải xoay hình';
}

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
            return <AngleMark key={`al-${index}`} ann={ann} points={scene.points} />;
          default:
            return null;
        }
      })}
    </>
  );
}

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

function EqualMarks({ ann, points }: { ann: Annotation; points: Record<string, Vec3> }) {
  const [startName, endName] = ann.target.split('-');
  const p1 = points[startName];
  const p2 = points[endName];
  if (!p1 || !p2) return null;

  const group = (ann.metadata?.group as number) ?? 1;
  const mid = midpoint(p1, p2);
  const dir = normalize(sub(p2, p1));

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
    <LabelText
      position={[offset.x, offset.y, offset.z]}
      fontSize={0.22}
      color={ann.color ?? '#7c3aed'}
      anchorX="center"
      anchorY="middle"
      fontWeight={700}
    >
      {ann.label}
    </LabelText>
  );
}

function AngleMark({ ann, points }: { ann: Annotation; points: Record<string, Vec3> }) {
  const vertex = points[ann.target];
  const arms = (ann.metadata?.arms as string[]) ?? [];
  if (!vertex || arms.length < 2) return null;

  const p1 = points[arms[0]];
  const p2 = points[arms[1]];
  if (!p1 || !p2) return null;

  const d1 = normalize(sub(p1, vertex));
  const d2 = normalize(sub(p2, vertex));
  if (length(d1) < 1e-9 || length(d2) < 1e-9) return null;

  const color = ann.color ?? '#b45309';
  const radius = metadataNumber(ann.metadata?.radius, 0.42);
  const labelRadius = metadataNumber(ann.metadata?.label_radius, radius + 0.18);
  const segmentCount = Math.max(8, Math.min(48, metadataNumber(ann.metadata?.segments, 24)));
  const arcEnabled = ann.metadata?.arc !== false;
  const arcPoints = arcEnabled ? angleArcPoints(vertex, d1, d2, radius, segmentCount) : [];
  const labelDir = angleLabelDirection(d1, d2, arcPoints);
  const labelPos = add(vertex, scale(labelDir, labelRadius));

  return (
    <>
      {arcPoints.length >= 2 && <Line points={arcPoints.map((point) => [point.x, point.y, point.z])} color={color} lineWidth={2.5} />}
      {ann.label && (
        <LabelText
          position={[labelPos.x, labelPos.y, labelPos.z]}
          fontSize={0.2}
          color={color}
          anchorX="center"
          anchorY="middle"
          fontWeight={700}
        >
          {ann.label}
        </LabelText>
      )}
    </>
  );
}

function angleArcPoints(vertex: Vec3, d1: Vec3, d2: Vec3, radius: number, segmentCount: number): Vec3[] {
  const dotValue = Math.max(-1, Math.min(1, dot(d1, d2)));
  const angle = Math.acos(dotValue);
  if (angle < 1e-4 || Math.PI - angle < 1e-4) return [];
  const normal = normalize(cross(d1, d2));
  if (length(normal) < 1e-9) return [];
  const v = normalize(cross(normal, d1));
  const steps = Math.max(2, Math.ceil(segmentCount * angle / Math.PI));
  const points: Vec3[] = [];
  for (let index = 0; index <= steps; index += 1) {
    const t = angle * index / steps;
    const direction = add(scale(d1, Math.cos(t)), scale(v, Math.sin(t)));
    points.push(add(vertex, scale(direction, radius)));
  }
  return points;
}

function angleLabelDirection(d1: Vec3, d2: Vec3, arcPoints: Vec3[]): Vec3 {
  const bisector = normalize(add(d1, d2));
  if (length(bisector) >= 1e-9) return bisector;
  if (arcPoints.length > 0) return normalize(sub(arcPoints[Math.floor(arcPoints.length / 2)], arcPoints[0]));
  return d1;
}

function metadataNumber(value: unknown, fallback: number): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}

function expandedPlaneVertices(anchors: Vec3[], allPoints: Vec3[]): Vec3[] {
  if (anchors.length < 3) return anchors;
  const origin = centroid(anchors);
  const normal = planeNormal(anchors);
  if (length(normal) < 1e-9) return anchors;

  let u = normalize(sub(anchors[1], anchors[0]));
  if (length(u) < 1e-9) u = perpendicularAxis(normal);
  let v = normalize(cross(normal, u));
  if (length(v) < 1e-9) return anchors;

  const projected = allPoints.map((point) => {
    const relative = sub(point, origin);
    return { u: dot(relative, u), v: dot(relative, v) };
  });
  const anchorProjected = anchors.map((point) => {
    const relative = sub(point, origin);
    return { u: dot(relative, u), v: dot(relative, v) };
  });
  const pointsToCover = projected.length > 0 ? projected : anchorProjected;
  const minU = Math.min(...pointsToCover.map((point) => point.u), ...anchorProjected.map((point) => point.u));
  const maxU = Math.max(...pointsToCover.map((point) => point.u), ...anchorProjected.map((point) => point.u));
  const minV = Math.min(...pointsToCover.map((point) => point.v), ...anchorProjected.map((point) => point.v));
  const maxV = Math.max(...pointsToCover.map((point) => point.v), ...anchorProjected.map((point) => point.v));
  const spanU = Math.max(maxU - minU, 1);
  const spanV = Math.max(maxV - minV, 1);
  const pad = Math.max(spanU, spanV) * 0.18;

  return [
    add(origin, add(scale(u, minU - pad), scale(v, minV - pad))),
    add(origin, add(scale(u, maxU + pad), scale(v, minV - pad))),
    add(origin, add(scale(u, maxU + pad), scale(v, maxV + pad))),
    add(origin, add(scale(u, minU - pad), scale(v, maxV + pad))),
  ];
}

function planeNormal(points: Vec3[]): Vec3 {
  for (let i = 0; i < points.length - 2; i += 1) {
    for (let j = i + 1; j < points.length - 1; j += 1) {
      for (let k = j + 1; k < points.length; k += 1) {
        const normal = normalize(cross(sub(points[j], points[i]), sub(points[k], points[i])));
        if (length(normal) >= 1e-9) return normal;
      }
    }
  }
  return { x: 0, y: 0, z: 0 };
}

function perpendicularAxis(normal: Vec3): Vec3 {
  const axis = Math.abs(normal.y) < 0.9 ? { x: 0, y: 1, z: 0 } : { x: 1, y: 0, z: 0 };
  return normalize(cross(normal, axis));
}

function polygonGeometry(vertices: Vec3[]): THREE.BufferGeometry | null {
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
  return geometry;
}

function centroid(points: Vec3[]): Vec3 {
  return {
    x: points.reduce((sum, point) => sum + point.x, 0) / points.length,
    y: points.reduce((sum, point) => sum + point.y, 0) / points.length,
    z: points.reduce((sum, point) => sum + point.z, 0) / points.length,
  };
}

function sceneToWorld(point: Vec3, frame: SceneFrame): THREE.Vector3 {
  return new THREE.Vector3(
    (point.x - frame.center.x) * frame.scale,
    (point.y - frame.center.y) * frame.scale,
    (point.z - frame.center.z) * frame.scale,
  );
}

function worldToScene(point: THREE.Vector3, frame: SceneFrame): Vec3 {
  return {
    x: point.x / frame.scale + frame.center.x,
    y: point.y / frame.scale + frame.center.y,
    z: point.z / frame.scale + frame.center.z,
  };
}

function addPointPlane(planeName: ThreeSceneInteraction['pointPlacementPlane'], depth: number, frame: SceneFrame) {
  const fixed = Number.isFinite(depth) ? depth : 0;
  if (planeName === 'xy') return new THREE.Plane(new THREE.Vector3(0, 0, 1), -((fixed - frame.center.z) * frame.scale));
  if (planeName === 'xz') return new THREE.Plane(new THREE.Vector3(0, 1, 0), -((fixed - frame.center.y) * frame.scale));
  return new THREE.Plane(new THREE.Vector3(1, 0, 0), -((fixed - frame.center.x) * frame.scale));
}

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

function dot(a: Vec3, b: Vec3): number {
  return a.x * b.x + a.y * b.y + a.z * b.z;
}

function midpoint(a: Vec3, b: Vec3): Vec3 {
  return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, z: (a.z + b.z) / 2 };
}

function fmtN(n: number): string {
  return Number.isInteger(n) ? n.toString() : n.toFixed(1);
}
