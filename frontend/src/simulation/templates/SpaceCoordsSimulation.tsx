import { Canvas } from '@react-three/fiber';
import { OrbitControls, Line, Text, Html } from '@react-three/drei';
import { useMemo, useState } from 'react';
import * as THREE from 'three';
import { KatexSpan } from '../../components/KatexSpan';
import { SliderInput } from '../../components/calculus/AreaBetweenCurvesSimulation';
import { formatNumber } from '../../utils/calculusNumerics';

type Props = { step: number; progress: number; freeMode?: boolean };

type State = {
  // point A
  ax: number; ay: number; az: number;
  // vector u (direction of line)
  ux: number; uy: number; uz: number;
  // plane: ax+by+cz+d = 0 via normal n and point P on plane
  nx: number; ny: number; nz: number;
  px: number; py: number; pz: number;
  // sphere
  cx: number; cy: number; cz: number;
  radius: number;
  showLine: boolean;
  showPlane: boolean;
  showSphere: boolean;
  showVector: boolean;
};

/**
 * Lab Oxyz dày: điểm, vectơ, đường thẳng, mặt phẳng, mặt cầu, khoảng cách, giao.
 */
export function SpaceCoordsSimulation({ step, progress, freeMode = false }: Props) {
  const [state, setState] = useState<State>({
    ax: 1, ay: 2, az: 1,
    ux: 1, uy: 0.5, uz: -0.3,
    nx: 0, ny: 0, nz: 1,
    px: 0, py: 0, pz: 0,
    cx: 0, cy: 0, cz: 0,
    radius: 2.2,
    showLine: true,
    showPlane: true,
    showSphere: true,
    showVector: true,
  });

  const geo = useMemo(() => analyzeSpace(state), [state]);
  // animate sphere radius slightly on step 4
  const radiusDraw = step === 4 ? state.radius * (0.4 + 0.6 * progress) : state.radius;
  const canA = freeMode || step >= 1;
  const canU = freeMode || step >= 2;
  const canPlane = freeMode || step >= 3;
  const canSphere = freeMode || step >= 4;

  return (
    <div className="csim-module-grid csim-module-grid-wide sim-deep-grid">
      <aside className="csim-control-stack">
        <div className="csim-card">
          <div className="csim-card-head"><strong>Oxyz · đường · mặt · cầu</strong><span>Kéo xoay khung 3D</span></div>

          <fieldset className={`sim-fieldset${!canA ? ' is-step-locked' : ''}`}>
            <legend>Điểm A {canA ? '' : '(bước 1)'}</legend>
            <Vec3Inputs
              labels={['Aₓ', 'Aᵧ', 'A_z']}
              values={[state.ax, state.ay, state.az]}
              disabled={!canA}
              onChange={([ax, ay, az]) => setState({ ...state, ax, ay, az })}
            />
          </fieldset>
          <fieldset className={`sim-fieldset${!canU ? ' is-step-locked' : ''}`}>
            <legend>Vectơ chỉ phương <KatexSpan tex="\vec u" /> {canU ? '' : '(bước 2)'}</legend>
            <Vec3Inputs
              labels={['uₓ', 'uᵧ', 'u_z']}
              values={[state.ux, state.uy, state.uz]}
              disabled={!canU}
              onChange={([ux, uy, uz]) => setState({ ...state, ux, uy, uz })}
            />
          </fieldset>

          <fieldset className={`sim-fieldset${!canPlane ? ' is-step-locked' : ''}`}>
            <legend>Mặt phẳng qua P, pháp tuyến <KatexSpan tex="\vec n" /> {canPlane ? '' : '(bước 3)'}</legend>
            <Vec3Inputs
              labels={['Pₓ', 'Pᵧ', 'P_z']}
              values={[state.px, state.py, state.pz]}
              disabled={!canPlane}
              onChange={([px, py, pz]) => setState({ ...state, px, py, pz })}
            />
            <Vec3Inputs
              labels={['nₓ', 'nᵧ', 'n_z']}
              values={[state.nx, state.ny, state.nz]}
              disabled={!canPlane}
              onChange={([nx, ny, nz]) => setState({ ...state, nx, ny, nz })}
            />
          </fieldset>

          <fieldset className={`sim-fieldset${!canSphere ? ' is-step-locked' : ''}`}>
            <legend>Mặt cầu tâm I, bán kính R {canSphere ? '' : '(bước 4)'}</legend>
            <Vec3Inputs
              labels={['Iₓ', 'Iᵧ', 'I_z']}
              values={[state.cx, state.cy, state.cz]}
              disabled={!canSphere}
              onChange={([cx, cy, cz]) => setState({ ...state, cx, cy, cz })}
            />
            <SliderInput label="R" value={state.radius} min={0.4} max={4.5} step={0.1} onChange={(radius) => setState({ ...state, radius })} disabled={!canSphere} />
          </fieldset>

          <div className="sim-toggle-grid">
            <label className="csim-check"><input type="checkbox" checked={state.showVector} onChange={(e) => setState({ ...state, showVector: e.target.checked })} /> Vectơ</label>
            <label className="csim-check"><input type="checkbox" checked={state.showLine} onChange={(e) => setState({ ...state, showLine: e.target.checked })} /> Đường thẳng</label>
            <label className="csim-check"><input type="checkbox" checked={state.showPlane} onChange={(e) => setState({ ...state, showPlane: e.target.checked })} /> Mặt phẳng</label>
            <label className="csim-check"><input type="checkbox" checked={state.showSphere} onChange={(e) => setState({ ...state, showSphere: e.target.checked })} /> Mặt cầu</label>
          </div>

          <div className="sim-preset-row">
            <button type="button" className="csim-chip" onClick={() => setState({
              ax: 0, ay: 0, az: 2, ux: 1, uy: 1, uz: 0,
              nx: 0, ny: 0, nz: 1, px: 0, py: 0, pz: 0,
              cx: 0, cy: 0, cz: 0, radius: 2,
              showLine: true, showPlane: true, showSphere: true, showVector: true,
            })}>Cầu đơn vị · mp Oxy</button>
            <button type="button" className="csim-chip" onClick={() => setState({
              ax: 2, ay: 0, az: 0, ux: 0, uy: 1, uz: 1,
              nx: 1, ny: 1, nz: 1, px: 1, py: 0, pz: 0,
              cx: 0, cy: 0, cz: 1, radius: 1.5,
              showLine: true, showPlane: true, showSphere: true, showVector: true,
            })}>Giao chéo</button>
          </div>
        </div>

        <div className="csim-card">
          <div className="csim-card-head"><strong>Công thức & số</strong><span>CAS số phía client</span></div>
          <div className="sim-kv-list">
            <div className="sim-kv-row"><span>Phương trình mp</span><strong className="sim-mono">{geo.planeEq}</strong></div>
            <div className="sim-kv-row"><span>PT đường (tham số)</span><strong className="sim-mono">{geo.lineEq}</strong></div>
            <div className="sim-kv-row"><span>PT mặt cầu</span><strong className="sim-mono">{geo.sphereEq}</strong></div>
            <div className="sim-kv-row"><span>d(A, mp)</span><strong>{formatNumber(geo.distPointPlane, 4)}</strong></div>
            <div className="sim-kv-row"><span>d(I, mp)</span><strong>{formatNumber(geo.distCenterPlane, 4)}</strong></div>
            <div className="sim-kv-row"><span>Góc đường–mp</span><strong>{formatNumber(geo.linePlaneAngleDeg, 2)}°</strong></div>
            <div className="sim-kv-row highlight"><span>Mp ∩ cầu</span><strong>{geo.spherePlaneRelation}</strong></div>
            <div className="sim-kv-row"><span>Bán kính giao tuyến</span><strong>{formatNumber(geo.intersectCircleRadius, 4)}</strong></div>
            <div className="sim-kv-row"><span>d(A, I)</span><strong>{formatNumber(geo.distAI, 4)}</strong></div>
            <div className="sim-kv-row"><span>A so với cầu</span><strong>{geo.pointSphereRelation}</strong></div>
          </div>
        </div>
      </aside>

      <section className="csim-visual-stack">
        <div className="sim-three-wrap">
          <Canvas camera={{ position: [6.5, 5.2, 7.2], fov: 42 }} dpr={[1, 1.75]}>
            <color attach="background" args={['#f4f6f8']} />
            <ambientLight intensity={0.75} />
            <directionalLight position={[5, 8, 4]} intensity={0.85} />
            <Axes />
            {state.showVector && (
              <Arrow from={[0, 0, 0]} to={[state.ax, state.ay, state.az]} color="#2563eb" />
            )}
            {state.showVector && (
              <Arrow from={[state.ax, state.ay, state.az]} to={[state.ax + state.ux, state.ay + state.uy, state.az + state.uz]} color="#7c3aed" />
            )}
            <PointMark position={[state.ax, state.ay, state.az]} label="A" color="#1d4ed8" />
            <PointMark position={[state.cx, state.cy, state.cz]} label="I" color="#b45309" />
            {state.showLine && step >= 2 && (
              <Line
                points={geo.linePoints}
                color="#0f766e"
                lineWidth={2.5}
              />
            )}
            {state.showPlane && step >= 3 && (
              <PlaneMesh point={[state.px, state.py, state.pz]} normal={[state.nx, state.ny, state.nz]} />
            )}
            {state.showSphere && step >= 4 && (
              <mesh position={[state.cx, state.cy, state.cz]}>
                <sphereGeometry args={[radiusDraw, 32, 24]} />
                <meshStandardMaterial color="#38bdf8" transparent opacity={0.28} roughness={0.4} metalness={0.05} />
              </mesh>
            )}
            {state.showSphere && step >= 4 && (
              <mesh position={[state.cx, state.cy, state.cz]}>
                <sphereGeometry args={[radiusDraw, 24, 16]} />
                <meshBasicMaterial color="#0284c7" wireframe transparent opacity={0.35} />
              </mesh>
            )}
            {geo.intersectCircleRadius > 0 && state.showPlane && state.showSphere && step >= 5 && (
              <IntersectionCircle
                center={geo.circleCenter}
                normal={[state.nx, state.ny, state.nz]}
                radius={geo.intersectCircleRadius}
              />
            )}
            <OrbitControls makeDefault />
          </Canvas>
        </div>

        <div className="csim-card csim-step-copy">
          <strong>{titles[step - 1] ?? titles[0]}</strong>
          <p>{copies[step - 1] ?? copies[0]}</p>
          <ul className="sim-mono-list">
            <li>Khoảng cách điểm–mp: <KatexSpan tex={String.raw`d=\dfrac{|ax_0+by_0+cz_0+d|}{\sqrt{a^2+b^2+c^2}}`} /></li>
            <li>Mp & cầu: so sánh d(I, mp) với R → không giao / tiếp xúc / cắt (đường tròn).</li>
            <li>Góc đường–mp: <KatexSpan tex={String.raw`\sin\theta=\dfrac{|\vec u\cdot\vec n|}{|\vec u||\vec n|}`} /></li>
          </ul>
        </div>
      </section>
    </div>
  );
}

function analyzeSpace(s: State) {
  const nLen = Math.hypot(s.nx, s.ny, s.nz) || 1e-9;
  const nnx = s.nx / nLen;
  const nny = s.ny / nLen;
  const nnz = s.nz / nLen;
  // plane: n·(X - P) = 0 => n·X + d = 0 with d = -n·P
  const d = -(s.nx * s.px + s.ny * s.py + s.nz * s.pz);
  const planeEq = formatPlane(s.nx, s.ny, s.nz, d);

  const uLen = Math.hypot(s.ux, s.uy, s.uz) || 1e-9;
  const lineEq = `x=${fmt(s.ax)}+${fmt(s.ux)}t; y=${fmt(s.ay)}+${fmt(s.uy)}t; z=${fmt(s.az)}+${fmt(s.uz)}t`;
  const sphereEq = `(x-${fmt(s.cx)})²+(y-${fmt(s.cy)})²+(z-${fmt(s.cz)})²=${fmt(s.radius)}²`;

  const distPointPlane = Math.abs(s.nx * s.ax + s.ny * s.ay + s.nz * s.az + d) / nLen;
  const distCenterPlane = Math.abs(s.nx * s.cx + s.ny * s.cy + s.nz * s.cz + d) / nLen;

  const cosAlpha = Math.abs(s.ux * s.nx + s.uy * s.ny + s.uz * s.nz) / (uLen * nLen);
  // angle between line and plane: sin θ = |cos alpha| where alpha is angle line-normal
  const sinTheta = Math.min(1, Math.max(0, cosAlpha));
  const linePlaneAngleDeg = (Math.asin(sinTheta) * 180) / Math.PI;

  let spherePlaneRelation = 'không giao';
  let intersectCircleRadius = 0;
  const gap = distCenterPlane - s.radius;
  if (Math.abs(gap) < 1e-6) {
    spherePlaneRelation = 'tiếp xúc (1 điểm)';
    intersectCircleRadius = 0;
  } else if (distCenterPlane < s.radius) {
    spherePlaneRelation = 'cắt nhau (đường tròn)';
    intersectCircleRadius = Math.sqrt(Math.max(0, s.radius ** 2 - distCenterPlane ** 2));
  }

  // circle center = I - dist * unit normal (sign toward plane)
  const signed = (s.nx * s.cx + s.ny * s.cy + s.nz * s.cz + d) / nLen;
  const circleCenter: [number, number, number] = [
    s.cx - nnx * signed,
    s.cy - nny * signed,
    s.cz - nnz * signed,
  ];

  const distAI = Math.hypot(s.ax - s.cx, s.ay - s.cy, s.az - s.cz);
  let pointSphereRelation = 'trên mặt cầu';
  if (distAI < s.radius - 1e-6) pointSphereRelation = 'trong mặt cầu';
  else if (distAI > s.radius + 1e-6) pointSphereRelation = 'ngoài mặt cầu';

  const linePoints: [number, number, number][] = [];
  for (let t = -4; t <= 4; t += 0.25) {
    linePoints.push([s.ax + s.ux * t, s.ay + s.uy * t, s.az + s.uz * t]);
  }

  return {
    planeEq,
    lineEq,
    sphereEq,
    distPointPlane,
    distCenterPlane,
    linePlaneAngleDeg,
    spherePlaneRelation,
    intersectCircleRadius,
    circleCenter,
    distAI,
    pointSphereRelation,
    linePoints,
  };
}

function formatPlane(a: number, b: number, c: number, d: number) {
  return `${fmt(a)}x + ${fmt(b)}y + ${fmt(c)}z + ${fmt(d)} = 0`;
}

function fmt(n: number) {
  return formatNumber(n, 2).replace(',', '.');
}

function Vec3Inputs({
  labels,
  values,
  onChange,
  disabled = false,
}: {
  labels: [string, string, string];
  values: [number, number, number];
  onChange: (v: [number, number, number]) => void;
  disabled?: boolean;
}) {
  return (
    <div className={`sim-vec3${disabled ? ' is-step-locked' : ''}`}>
      {labels.map((label, i) => (
        <label key={label} className="csim-field">
          <span>{label}</span>
          <input
            type="number"
            step={0.1}
            disabled={disabled}
            value={values[i]}
            onChange={(e) => {
              const next = [...values] as [number, number, number];
              next[i] = Number(e.target.value);
              onChange(next);
            }}
          />
        </label>
      ))}
    </div>
  );
}

function Axes() {
  const len = 5;
  return (
    <group>
      <Line points={[[-len, 0, 0], [len, 0, 0]]} color="#94a3b8" lineWidth={1} />
      <Line points={[[0, -len, 0], [0, len, 0]]} color="#94a3b8" lineWidth={1} />
      <Line points={[[0, 0, -len], [0, 0, len]]} color="#94a3b8" lineWidth={1} />
      <Text position={[len + 0.2, 0, 0]} fontSize={0.28} color="#334155">x</Text>
      <Text position={[0, len + 0.2, 0]} fontSize={0.28} color="#334155">y</Text>
      <Text position={[0, 0, len + 0.2]} fontSize={0.28} color="#334155">z</Text>
      <gridHelper args={[10, 10, '#cbd5e1', '#e2e8f0']} rotation={[0, 0, 0]} />
    </group>
  );
}

function PointMark({ position, label, color }: { position: [number, number, number]; label: string; color: string }) {
  return (
    <group position={position}>
      <mesh>
        <sphereGeometry args={[0.1, 16, 16]} />
        <meshStandardMaterial color={color} />
      </mesh>
      <Html distanceFactor={10} style={{ pointerEvents: 'none' }}>
        <span className="sim-html-label">{label}</span>
      </Html>
    </group>
  );
}

function Arrow({ from, to, color }: { from: [number, number, number]; to: [number, number, number]; color: string }) {
  return <Line points={[from, to]} color={color} lineWidth={2.5} />;
}

function PlaneMesh({ point, normal }: { point: [number, number, number]; normal: [number, number, number] }) {
  const quat = useMemo(() => {
    const n = new THREE.Vector3(...normal).normalize();
    const q = new THREE.Quaternion();
    q.setFromUnitVectors(new THREE.Vector3(0, 0, 1), n);
    return q;
  }, [normal]);
  return (
    <mesh position={point} quaternion={quat}>
      <planeGeometry args={[7, 7]} />
      <meshStandardMaterial color="#a78bfa" transparent opacity={0.32} side={THREE.DoubleSide} />
    </mesh>
  );
}

function IntersectionCircle({
  center,
  normal,
  radius,
}: {
  center: [number, number, number];
  normal: [number, number, number];
  radius: number;
}) {
  const points = useMemo(() => {
    const n = new THREE.Vector3(...normal).normalize();
    let a = new THREE.Vector3(1, 0, 0);
    if (Math.abs(n.dot(a)) > 0.9) a = new THREE.Vector3(0, 1, 0);
    const u = new THREE.Vector3().crossVectors(n, a).normalize();
    const v = new THREE.Vector3().crossVectors(n, u).normalize();
    const pts: [number, number, number][] = [];
    for (let i = 0; i <= 64; i += 1) {
      const t = (i / 64) * Math.PI * 2;
      const p = new THREE.Vector3(...center)
        .addScaledVector(u, Math.cos(t) * radius)
        .addScaledVector(v, Math.sin(t) * radius);
      pts.push([p.x, p.y, p.z]);
    }
    return pts;
  }, [center, normal, radius]);
  return <Line points={points} color="#dc2626" lineWidth={2.5} />;
}

const titles = [
  'Bước 1 — Hệ Oxyz, điểm A và vectơ',
  'Bước 2 — Đường thẳng tham số qua A phương u',
  'Bước 3 — Mặt phẳng: điểm + pháp tuyến',
  'Bước 4 — Mặt cầu tâm I bán kính R',
  'Bước 5 — Vị trí tương đối mp ∩ cầu, khoảng cách',
  'Bước 6 — Tổng hợp góc, khoảng cách, quan hệ điểm–cầu',
];

const copies = [
  'Làm quen trục tọa độ vuông góc trong không gian. Mỗi điểm là bộ ba (x; y; z).',
  'Đường thẳng: (x;y;z) = A + t u. Kéo u để đổi phương; điểm A cố định đường đi qua.',
  'Mặt phẳng xác định bởi điểm P và pháp tuyến n: n · (M − P) = 0.',
  'Mặt cầu: mọi điểm cách I một khoảng R. Xoay mô hình để thấy tính đối xứng.',
  'So sánh d(I, mp) với R. Nếu cắt nhau, giao tuyến là đường tròn nằm trên mặt phẳng.',
  'Đọc bảng số: khoảng cách, góc đường–mặt, điểm trong/trên/ngoài cầu. Đây là bộ công cụ tọa độ lớp 12.',
];
