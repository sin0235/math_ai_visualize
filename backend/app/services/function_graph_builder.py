from sympy import Symbol, lambdify, sympify

from app.renderers.geogebra_commands import build_geogebra_commands
from app.schemas.scene import Annotation, FunctionGraph, MathScene, Point2D, SceneView, Segment

x = Symbol("x", real=True)
m = Symbol("m", real=True)


def build_function_graph(analysis: dict) -> tuple[MathScene, list[str], list[dict[str, float]]]:
    objects = []
    annotations = []

    graph_expression = analysis.get("evaluated_expression") or analysis["expression"]
    objects.append(FunctionGraph(name="f", expression=_geogebra_expression(graph_expression)))

    for i, cp in enumerate(analysis.get("critical_points", [])):
        x_val = _safe_float(cp.get("x"))
        y_val = _safe_float(cp.get("y"))
        if x_val is None or y_val is None:
            continue
            
        point_name = f"E{i + 1}"
        objects.append(Point2D(name=point_name, x=x_val, y=y_val))
        
        # Friendly red label
        annotations.append(Annotation(
            type="coordinate_label",
            target=point_name,
            label=cp.get('kind_label', 'Cực trị'),
            color="#e63946"
        ))
        
        # Projection lines to axes
        p_x = f"ProjX{i}"
        p_y = f"ProjY{i}"
        objects.append(Point2D(name=p_x, x=x_val, y=0))
        objects.append(Point2D(name=p_y, x=0, y=y_val))
        
        objects.append(Segment(
            points=[point_name, p_x],
            style="dashed",
            color="#8b95a7",
            line_width=1
        ))
        objects.append(Segment(
            points=[point_name, p_y],
            style="dashed",
            color="#8b95a7",
            line_width=1
        ))

    for i, ip in enumerate(analysis.get("inflection_points", [])):
        point = _point_from_values(f"U{i + 1}", ip.get("x"), ip.get("y"))
        if point is not None:
            objects.append(point)
            annotations.append(Annotation(type="coordinate_label", target=point.name, label=f"U"))

    for i, va in enumerate(analysis.get("vertical_asymptotes", [])):
        x_val = _safe_float(va.get("x"))
        if x_val is None:
            continue
        p1 = f"VA{i}a"
        p2 = f"VA{i}b"
        objects.append(Point2D(name=p1, x=x_val, y=-50))
        objects.append(Point2D(name=p2, x=x_val, y=50))
        objects.append(Segment(name=f"va{i}", points=[p1, p2], style="dashed", color="#e07020"))

    for i, ha in enumerate(analysis.get("horizontal_asymptotes", [])):
        y_val = _safe_float(ha.get("value"))
        if y_val is None:
            continue
        p1 = f"HA{i}a"
        p2 = f"HA{i}b"
        objects.append(Point2D(name=p1, x=-50, y=y_val))
        objects.append(Point2D(name=p2, x=50, y=y_val))
        objects.append(Segment(name=f"ha{i}", points=[p1, p2], style="dashed", color="#2e8b57"))

    for i, xi in enumerate(analysis.get("x_intercepts", [])):
        x_val = _safe_float(xi)
        if x_val is not None:
            objects.append(Point2D(name=f"X{i + 1}", x=x_val, y=0))

    y_intercept = _safe_float(analysis.get("y_intercept"))
    if y_intercept is not None:
        objects.append(Point2D(name="Y", x=0, y=y_intercept))

    scene = MathScene(
        problem_text=f"Đồ thị y = {analysis['expression']}",
        topic="function_graph",
        renderer="geogebra_2d",
        objects=objects,
        annotations=annotations,
        view=SceneView(dimension="2d", show_axes=True, show_grid=True),
    )
    commands = build_geogebra_commands(scene)

    for i, cp in enumerate(analysis.get("critical_points", [])):
        name = f"E{i + 1}"
        commands.append(f'SetColor({name}, "#e63946")')
        commands.append(f"SetPointSize({name}, 6)")

    for i in range(len(analysis.get("inflection_points", []))):
        commands.append(f'SetColor(U{i + 1}, "#f4a261")')
        commands.append(f"SetPointSize(U{i + 1}, 4)")

    for obj in objects:
        if isinstance(obj, Point2D) and obj.name.startswith(("VA", "HA", "ProjX", "ProjY")):
            commands.append(f"SetVisibleInView({obj.name}, 1, false)")

    return scene, commands, _sample_graph_points(graph_expression)


def _sample_graph_points(expression: str) -> list[dict[str, float]]:
    try:
        expr = sympify(expression.replace("^", "**"), locals={"x": x, "m": m})
        fn = lambdify(x, expr, "math")
    except Exception:
        return []

    points: list[dict[str, float]] = []
    for i in range(161):
        x_val = -8 + i * 0.1
        try:
            y_val = float(fn(x_val))
        except (ValueError, ZeroDivisionError, OverflowError, TypeError):
            continue
        if y_val != y_val or y_val in (float("inf"), float("-inf")) or abs(y_val) > 1_000:
            continue
        points.append({"x": round(x_val, 4), "y": round(y_val, 4)})
    return points


def _geogebra_expression(expression: str) -> str:
    return expression.replace("**", "^").replace(" ", "")


def _point_from_values(name: str, raw_x, raw_y) -> Point2D | None:
    x_val = _safe_float(raw_x)
    y_val = _safe_float(raw_y)
    if x_val is None or y_val is None:
        return None
    return Point2D(name=name, x=x_val, y=y_val)


def _safe_float(value) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed != parsed or parsed in (float("inf"), float("-inf")):
        return None
    return parsed
