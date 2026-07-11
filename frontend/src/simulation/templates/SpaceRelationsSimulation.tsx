import { Canvas } from '@react-three/fiber';
import { OrbitControls, Line, Text, Html } from '@react-three/drei';
import { useMemo, useState } from 'react';
import * as THREE from 'three';
import { KatexSpan } from '../../components/KatexSpan';
import { formatNumber } from '../../utils/calculusNumerics';

type Props = { step: number; progress: number };

type State = {
  // line 1: A + t u
  ax: number; ay: number; az: number;
  ux: number; uy: number; uz: number;
  // line 2: B + s v
  bx: number; by: number; bz: number;
  vx: number; vy: number; vz: number;
  // plane: point P, normal n
  px: number; py: number; pz: number;
  nx: number; ny: number; nz: number;
  showPlane: boolean;
  showL2: boolean;
};

/**
 * Hình học không gian lớp 11: song song / vuông góc đường–đường, đường–mp, mp–mp.
 */
export function SpaceRelationsSimulation({ step, progress }: Props) {
  const [state, setState] = useState<State>({
    ax: 0, ay: 0, az: 0,
    ux: 1, uy: 0, uz: 0,
    bx: 0, by: 1, bz: 0,
    vx: 1, vy: 0, vz: 0.2,
    px: 0, py: 0, pz: 0,
    nx: 0, ny: 0, nz: 1,
    showPlane: true,
    showL2: true,
  });

  const rel = useMemo(() => analyze(state), [state]);
  // animate highlight on step 3
  const pulse = step === 3 ? 0.4 + 0.6 * progress : 1;

  return (
    <div className="csim-module-grid csim-module-grid-wide sim-deep-grid">
      <aside className="csim-control-stack">
        <div className="csim-card">
          <div className="csim-card-head"><strong>Song song · vuông góc KG</strong><span>Lớp 11</span></div>
          <fieldset className="sim-fieldset">
            <legend>Đường <KatexSpan tex="\\Delta_1: A+t\\vec u" /></legend>
            <Vec3 labels={['A', '', '']} values={[state.ax, state.ay, state.az]} onChange={([ax, ay, az]) => setState({ ...state, ax, ay, az })} />
            <Vec3 labels={['u', '', '']} values={[state.ux, state.uy, state.uz]} onChange={([ux, uy, uz]) => setState({ ...state, ux, uy, uz })} />
          </fieldset>
          <fieldset className="sim-fieldset">
            <legend>Đường <KatexSpan tex="\\Delta_2: B+s\\vec v" /></legend>
            <Vec3 labels={['B', '', '']} values={[state.bx, state.by, state.bz]} onChange={([bx, by, bz]) => setState({ ...state, bx, by, bz })} />
            <Vec3 labels={['v', '', '']} values={[state.vx, state.vy, state.vz]} onChange={([vx, vy, vz]) => setState({ ...state, vx, vy, vz })} />
          </fieldset>
          <fieldset className="sim-fieldset">
            <legend>Mặt phẳng (P): P · n</legend>
            <Vec3 labels={['P', '', '']} values={[state.px, state.py, state.pz]} onChange={([px, py, pz]) => setState({ ...state, px, py, pz })} />
            <Vec3 labels={['n', '', '']} values={[state.nx, state.ny, state.nz]} onChange={([nx, ny, nz]) => setState({ ...state, nx, ny, nz })} />
          </fieldset>
          <div className="sim-toggle-grid">
            <label className="csim-check"><input type="checkbox" checked={state.showL2} onChange={(e) => setState({ ...state, showL2: e.target.checked })} /> Hiện <KatexSpan tex="\\Delta_2" /></label>
            <label className="csim-check"><input type="checkbox" checked={state.showPlane} onChange={(e) => setState({ ...state, showPlane: e.target.checked })} /> Hiện mp</label>
          </div>
          <div className="sim-preset-row">
            <button type="button" className="csim-chip" onClick={() => setState({
              ax: 0, ay: 0, az: 0, ux: 1, uy: 0, uz: 0,
              bx: 0, by: 1, bz: 0, vx: 1, vy: 0, vz: 0,
              px: 0, py: 0, pz: 0, nx: 0, ny: 0, nz: 1,
              showL2: true, showPlane: true,
            })}><KatexSpan tex={String.raw`\Delta_1\parallel\Delta_2,\quad \Delta_1\perp(Oxy)`} /></button>
            <button type="button" className="csim-chip" onClick={() => setState({
              ax: 0, ay: 0, az: 0, ux: 1, uy: 0, uz: 0,
              bx: 0, by: 0, bz: 0, vx: 0, vy: 1, vz: 0,
              px: 0, py: 0, pz: 0, nx: 1, ny: 0, nz: 0,
              showL2: true, showPlane: true,
            })}><KatexSpan tex={String.raw`\Delta_1\perp\Delta_2`} /></button>
            <button type="button" className="csim-chip" onClick={() => setState({
              ax: 1, ay: 0, az: 1, ux: 1, uy: 1, uz: 0,
              bx: 0, by: 0, bz: 0, vx: 0, vy: 1, vz: 1,
              px: 0, py: 0, pz: 0, nx: 0, ny: 1, nz: 0,
              showL2: true, showPlane: true,
            })}>Chéo nhau</button>
          </div>
        </div>

        <div className="csim-card">
          <div className="csim-card-head"><strong>Quan hệ</strong><span>vectơ</span></div>
          <div className="sim-kv-list">
            <div className="sim-kv-row highlight"><span><KatexSpan tex="\\Delta_1" /> và <KatexSpan tex="\\Delta_2" /></span><strong>{rel.lines}</strong></div>
            <div className="sim-kv-row"><span><KatexSpan tex="\\vec u\\cdot\\vec v" /></span><strong>{formatNumber(rel.udotv, 4)}</strong></div>
            <div className="sim-kv-row"><span><KatexSpan tex="|\\vec u\\times\\vec v|" /></span><strong>{formatNumber(rel.ucrossv, 4)}</strong></div>
            <div className="sim-kv-row"><span>Góc <KatexSpan tex="(\\vec u,\\vec v)" /></span><strong><KatexSpan tex={`${formatNumber(rel.angleUV, 1)}^\\circ`} /></strong></div>
            <div className="sim-kv-row highlight"><span><KatexSpan tex="\\Delta_1" /> và mặt phẳng</span><strong>{rel.linePlane}</strong></div>
            <div className="sim-kv-row"><span><KatexSpan tex={String.raw`\dfrac{|\vec u\cdot\vec n|}{|\vec u||\vec n|}`} /></span><strong>{formatNumber(rel.cosLineNormal, 4)}</strong></div>
            <div className="sim-kv-row"><span>Góc đường–mặt phẳng</span><strong><KatexSpan tex={`${formatNumber(rel.angleLinePlane, 1)}^\\circ`} /></strong></div>
            <div className="sim-kv-row"><span><KatexSpan tex="d(A,(P))" /></span><strong>{formatNumber(rel.distA, 4)}</strong></div>
            <div className="sim-kv-row"><span><KatexSpan tex="\\Delta_1\\parallel(P)" />?</span><strong>{rel.lineParallelPlane ? <KatexSpan tex="\\vec u\\perp\\vec n" /> : 'không'}</strong></div>
          </div>
        </div>
      </aside>

      <section className="csim-visual-stack">
        <div className="sim-three-wrap">
          <Canvas camera={{ position: [6, 5, 7], fov: 42 }} dpr={[1, 1.75]}>
            <color attach="background" args={['#f4f6f8']} />
            <ambientLight intensity={0.8} />
            <directionalLight position={[4, 8, 3]} intensity={0.9} />
            <Axes />
            <Line points={linePts(state.ax, state.ay, state.az, state.ux, state.uy, state.uz)} color="#2563eb" lineWidth={3 * pulse} />
            {state.showL2 && step >= 2 && (
              <Line points={linePts(state.bx, state.by, state.bz, state.vx, state.vy, state.vz)} color="#dc2626" lineWidth={2.5} />
            )}
            <Point p={[state.ax, state.ay, state.az]} label="A" color="#1d4ed8" />
            {state.showL2 && step >= 2 && <Point p={[state.bx, state.by, state.bz]} label="B" color="#b91c1c" />}
            {state.showPlane && step >= 3 && (
              <PlaneMesh point={[state.px, state.py, state.pz]} normal={[state.nx, state.ny, state.nz]} />
            )}
            <OrbitControls makeDefault />
          </Canvas>
        </div>
        <div className="csim-card csim-step-copy">
          <strong>{titles[step - 1] ?? titles[0]}</strong>
          <p>{copies[step - 1] ?? copies[0]}</p>
          <ul className="sim-mono-list">
            <li><KatexSpan tex={String.raw`\Delta\parallel\Delta'\Leftrightarrow\vec u\times\vec v=\vec0`} />.</li>
            <li><KatexSpan tex={String.raw`\Delta\perp\Delta'\Leftrightarrow\vec u\cdot\vec v=0`} />.</li>
            <li><KatexSpan tex={String.raw`\Delta\parallel(P)\Leftrightarrow\vec u\cdot\vec n=0`} />.</li>
            <li>Hai đường chéo: không song song, không đồng phẳng.</li>
          </ul>
        </div>
      </section>
    </div>
  );
}

function analyze(s: State) {
  const u = new THREE.Vector3(s.ux, s.uy, s.uz);
  const v = new THREE.Vector3(s.vx, s.vy, s.vz);
  const n = new THREE.Vector3(s.nx, s.ny, s.nz);
  const A = new THREE.Vector3(s.ax, s.ay, s.az);
  const B = new THREE.Vector3(s.bx, s.by, s.bz);
  const P = new THREE.Vector3(s.px, s.py, s.pz);

  const udotv = u.dot(v);
  const cross = new THREE.Vector3().crossVectors(u, v);
  const ucrossv = cross.length();
  const angleUV = u.length() * v.length() > 1e-12
    ? (Math.acos(Math.min(1, Math.max(-1, udotv / (u.length() * v.length())))) * 180) / Math.PI
    : NaN;

  let lines = 'không xác định';
  if (u.length() < 1e-9 || v.length() < 1e-9) lines = 'vectơ chỉ phương suy biến';
  else if (ucrossv < 1e-6) {
    // parallel — check same line / distinct
    const AB = new THREE.Vector3().subVectors(B, A);
    const abxu = new THREE.Vector3().crossVectors(AB, u);
    lines = abxu.length() < 1e-5 ? 'trùng / cùng đường' : 'song song phân biệt';
  } else if (Math.abs(udotv) < 1e-6) {
    lines = 'vuông góc (u·v=0)';
  } else {
    // coplanar? scalar triple [AB,u,v]=0
    const AB = new THREE.Vector3().subVectors(B, A);
    const triple = Math.abs(AB.dot(cross));
    lines = triple < 1e-5 ? 'cắt nhau (đồng phẳng, không ∥)' : 'chéo nhau';
  }

  const nLen = n.length() || 1e-9;
  const uLen = u.length() || 1e-9;
  const cosLineNormal = Math.abs(u.dot(n)) / (uLen * nLen);
  const angleLinePlane = (Math.asin(Math.min(1, cosLineNormal)) * 180) / Math.PI;
  const lineParallelPlane = Math.abs(u.dot(n)) < 1e-6;
  const d = -n.dot(P);
  const distA = Math.abs(n.dot(A) + d) / nLen;

  let linePlane = 'cắt mp';
  if (lineParallelPlane) {
    linePlane = distA < 1e-5 ? 'nằm trong mp' : 'song song mp (không cắt)';
  } else if (cosLineNormal > 0.999) {
    linePlane = 'vuông góc mp';
  }

  return {
    lines,
    udotv,
    ucrossv,
    angleUV,
    linePlane,
    cosLineNormal,
    angleLinePlane,
    distA,
    lineParallelPlane,
  };
}

function linePts(ax: number, ay: number, az: number, ux: number, uy: number, uz: number): [number, number, number][] {
  const pts: [number, number, number][] = [];
  for (let t = -3; t <= 3; t += 0.25) pts.push([ax + ux * t, ay + uy * t, az + uz * t]);
  return pts;
}

function Vec3({
  labels,
  values,
  onChange,
}: {
  labels: string[];
  values: [number, number, number];
  onChange: (v: [number, number, number]) => void;
}) {
  const axes = ['x', 'y', 'z'];
  return (
    <div className="sim-vec3">
      {axes.map((axis, i) => (
        <label key={axis} className="csim-field">
          <span>{labels[0]}{axis}</span>
          <input
            type="number"
            step={0.1}
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
  return (
    <group>
      <Line points={[[-4, 0, 0], [4, 0, 0]]} color="#94a3b8" />
      <Line points={[[0, -4, 0], [0, 4, 0]]} color="#94a3b8" />
      <Line points={[[0, 0, -4], [0, 0, 4]]} color="#94a3b8" />
      <gridHelper args={[8, 8, '#cbd5e1', '#e2e8f0']} />
      <Text position={[4.2, 0, 0]} fontSize={0.25} color="#334155">x</Text>
      <Text position={[0, 4.2, 0]} fontSize={0.25} color="#334155">y</Text>
      <Text position={[0, 0, 4.2]} fontSize={0.25} color="#334155">z</Text>
    </group>
  );
}

function Point({ p, label, color }: { p: [number, number, number]; label: string; color: string }) {
  return (
    <group position={p}>
      <mesh><sphereGeometry args={[0.1, 12, 12]} /><meshStandardMaterial color={color} /></mesh>
      <Html distanceFactor={10} style={{ pointerEvents: 'none' }}><span className="sim-html-label">{label}</span></Html>
    </group>
  );
}

function PlaneMesh({ point, normal }: { point: [number, number, number]; normal: [number, number, number] }) {
  const quat = useMemo(() => {
    const n = new THREE.Vector3(...normal).normalize();
    const q = new THREE.Quaternion();
    q.setFromUnitVectors(new THREE.Vector3(0, 0, 1), n.lengthSq() < 1e-8 ? new THREE.Vector3(0, 0, 1) : n);
    return q;
  }, [normal]);
  return (
    <mesh position={point} quaternion={quat}>
      <planeGeometry args={[6.5, 6.5]} />
      <meshStandardMaterial color="#a78bfa" transparent opacity={0.3} side={THREE.DoubleSide} />
    </mesh>
  );
}

const titles = [
  'Bước 1 — Hai đường: điểm và vectơ chỉ phương',
  'Bước 2 — So u, v: song song / vuông góc / chéo',
  'Bước 3 — Thêm mặt phẳng pháp tuyến n',
  'Bước 4 — Quan hệ đường–mặt phẳng',
  'Bước 5 — Góc và khoảng cách',
  'Bước 6 — Tổng hợp tiêu chuẩn vectơ',
];

const copies = [
  'Trong KG, đường thẳng xác định bởi điểm + phương. Đổi u, v để thử các cấu hình.',
  'u×v=0 ⇒ cùng phương. u·v=0 ⇒ vuông góc. Không ∥ và không đồng phẳng ⇒ chéo.',
  'Mp: điểm P và pháp tuyến n. Mọi vector trong mp vuông góc n.',
  'u·n=0 ⇒ đường ∥ mp (hoặc nằm trong). u∥n ⇒ đường ⊥ mp.',
  'sinθ = |u·n|/(|u||n|) cho góc đường–mp. d = |ax+by+cz+d₀|/√…',
  'Ghi nhớ bảng tiêu chuẩn — dùng khi giải bài tọa độ lớp 11–12.',
];
