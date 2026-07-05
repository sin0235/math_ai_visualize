import type { MathScene, Parameter, Point2D, Point3D, SceneObject, Sphere, ThreeScene } from '../types/scene';
import { trySafeEval } from './expressionEval';

export function getDefaultParamValues(parameters: Parameter[] | undefined | null): Record<string, number> {
  const out: Record<string, number> = {};
  for (const p of parameters || []) {
    if (Number.isFinite(p.default)) out[p.name] = p.default;
  }
  return out;
}

function evalAxis(rawValue: number, expr: string | null | undefined, vars: Record<string, number>): number {
  if (!expr || typeof expr !== 'string' || !expr.trim()) return rawValue;
  const v = trySafeEval(expr, vars);
  return v == null ? rawValue : v;
}

export function recomputeSceneWithParameters(
  scene: MathScene,
  paramValues: Record<string, number>,
): MathScene {
  if (!scene.parameters || scene.parameters.length === 0) return scene;
  const newObjects: SceneObject[] = scene.objects.map((obj) => {
    if (obj.type === 'point_2d') {
      const next: Point2D = {
        ...obj,
        x: evalAxis(obj.x, obj.x_expr, paramValues),
        y: evalAxis(obj.y, obj.y_expr, paramValues),
      };
      return next;
    }
    if (obj.type === 'point_3d') {
      const next: Point3D = {
        ...obj,
        x: evalAxis(obj.x, obj.x_expr, paramValues),
        y: evalAxis(obj.y, obj.y_expr, paramValues),
        z: evalAxis(obj.z, obj.z_expr, paramValues),
      };
      return next;
    }
    if (obj.type === 'sphere' && obj.radius_expr) {
      const r = trySafeEval(obj.radius_expr, paramValues);
      if (r != null) {
        const next: Sphere = { ...obj, radius: r };
        return next;
      }
    }
    if (obj.type === 'circle_2d' && obj.radius_expr) {
      const r = trySafeEval(obj.radius_expr, paramValues);
      if (r != null) return { ...obj, radius: r };
    }
    return obj;
  });
  return { ...scene, objects: newObjects };
}

/**
 * Recompute ThreeScene từ MathScene đã được recompute. Chỉ cập nhật toạ độ
 * điểm và radius của sphere — segment/face không đổi vì chúng tham chiếu
 * name. Function này nhanh, không tốn cost mạng.
 */
export function recomputeThreeScene(
  three: ThreeScene,
  recomputedMath: MathScene,
): ThreeScene {
  const newPoints: Record<string, { x: number; y: number; z: number; hidden?: boolean }> = {};
  for (const obj of recomputedMath.objects) {
    if (obj.type === 'point_3d') {
      newPoints[obj.name] = { x: obj.x, y: obj.y, z: obj.z, hidden: three.points[obj.name]?.hidden };
    } else if (obj.type === 'point_2d') {
      newPoints[obj.name] = { x: obj.x, y: obj.y, z: 0, hidden: three.points[obj.name]?.hidden };
    }
  }
  // giữ lại các điểm ThreeScene có nhưng MathScene không có (phòng trường hợp computed/auxiliary)
  const finalPoints: Record<string, { x: number; y: number; z: number }> = { ...three.points, ...newPoints };

  let finalSpheres = three.spheres;
  if (finalSpheres && finalSpheres.length > 0) {
    const radiusByCenter: Record<string, number> = {};
    for (const obj of recomputedMath.objects) {
      if (obj.type === 'sphere' && obj.radius_expr) {
        radiusByCenter[obj.center] = obj.radius;
      }
    }
    if (Object.keys(radiusByCenter).length > 0) {
      finalSpheres = finalSpheres.map((s) => {
        const r = radiusByCenter[s.center];
        return r != null ? { ...s, radius: r } : s;
      });
    }
  }

  return { ...three, points: finalPoints, spheres: finalSpheres };
}

export function clampParamValue(p: Parameter, value: number): number {
  if (!Number.isFinite(value)) return p.default;
  return Math.max(p.min, Math.min(p.max, value));
}

/**
 * Patch các lệnh GeoGebra "PointName = (x, y[, z])" cho khớp toạ độ mới sau khi
 * recompute parameter. Chỉ thay thế dòng định nghĩa toạ độ điểm — các lệnh
 * tham chiếu tên (Line, Circle, Polygon...) tự cập nhật theo trong applet.
 *
 * Cũng patch sphere/circle Circle(center, radius) khi radius_expr có giá trị mới.
 */
const POINT_DEF_RE = /^([A-Za-z][A-Za-z0-9_]*)\s*=\s*\(([^)]+)\)$/;

function fmtNum(v: number): string {
  if (!Number.isFinite(v)) return '0';
  // tối đa 3 chữ số sau dấu phẩy, bỏ trailing zero
  const fixed = v.toFixed(3);
  return fixed.replace(/\.?0+$/, '');
}

export function patchGeogebraCommandsForScene(
  commands: string[],
  scene: MathScene,
): string[] {
  if (!commands || commands.length === 0) return commands;
  const pointDefs: Record<string, string> = {};
  for (const obj of scene.objects) {
    if (obj.type === 'point_2d') {
      pointDefs[obj.name] = `(${fmtNum(obj.x)}, ${fmtNum(obj.y)})`;
    } else if (obj.type === 'point_3d') {
      pointDefs[obj.name] = `(${fmtNum(obj.x)}, ${fmtNum(obj.y)}, ${fmtNum(obj.z)})`;
    }
  }
  return commands.map((cmd) => {
    const match = cmd.match(POINT_DEF_RE);
    if (match) {
      const name = match[1];
      if (pointDefs[name]) {
        return `${name} = ${pointDefs[name]}`;
      }
    }
    return cmd;
  });
}
