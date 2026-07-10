from sympy import Symbol, lambdify

from app.renderers.geogebra_commands import build_geogebra_commands
from app.schemas.scene import Annotation, FunctionGraph, MathScene, Point2D, SceneView, Segment
from app.services.function_domain import in_domain

x = Symbol("x", real=True)
m = Symbol("m", real=True)


def build_function_graph(analysis: dict) -> tuple[MathScene, list[str], list[dict[str, float]]]:
    objects = []
    annotations = []

    graph_expression = analysis.get("_graph_expr") or analysis.get("evaluated_expression") or analysis["expression"]
    interval_analysis = analysis.get("interval_analysis")
    
    domain = None
    if interval_analysis:
        a = interval_analysis["a"]
        b = interval_analysis["b"]
        domain = (a, b)

    graph_domains = [domain] if domain is not None else _graph_domains_from_analysis(analysis)
    if graph_domains:
        for index, graph_domain in enumerate(graph_domains):
            graph_name = "f" if len(graph_domains) == 1 else f"f{index + 1}"
            objects.append(FunctionGraph(name=graph_name, expression=_geogebra_expression(graph_expression), domain=graph_domain))
    else:
        objects.append(FunctionGraph(name="f", expression=_geogebra_expression(graph_expression), domain=None))

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

    for i, hole in enumerate(analysis.get("removable_holes", [])):
        point = _point_from_values(f"H{i + 1}", hole.get("x"), hole.get("y"))
        if point is not None:
            point.metadata["kind"] = "removable_hole"
            objects.append(point)
            annotations.append(Annotation(type="coordinate_label", target=point.name, label=hole.get("label", "điểm khuyết"), color="#dc2626"))

    scene = MathScene(
        problem_text=f"Đồ thị y = {analysis['expression']}",
        topic="function_graph",
        renderer="geogebra_2d",
        objects=objects,
        annotations=annotations,
        view=SceneView(dimension="2d", show_axes=True, show_grid=True),
    )
    commands = build_geogebra_commands(scene)
    line_analysis = analysis.get("line_analysis")
    if line_analysis:
        commands.append(f'g(x)={line_analysis["k"]}*x+{line_analysis["b"]}')
        commands.append('SetColor(g, "#2563eb")')
        commands.append('SetLineThickness(g, 4)')
    transform_preview = analysis.get("transform_preview")
    if transform_preview:
        commands.append(f'h(x)={_geogebra_expression(transform_preview["expression"])}')
        commands.append('SetColor(f, "#94a3b8")')
        commands.append('SetLineThickness(f, 2)')
        commands.append('SetColor(h, "#111827")')
        commands.append('SetLineThickness(h, 5)')

    for i, cp in enumerate(analysis.get("critical_points", [])):
        name = f"E{i + 1}"
        commands.append(f'SetColor({name}, "#e63946")')
        commands.append(f"SetPointSize({name}, 6)")

    for i in range(len(analysis.get("removable_holes", []))):
        name = f"H{i + 1}"
        commands.append(f'SetColor({name}, "#dc2626")')
        commands.append(f"SetPointStyle({name}, 2)")
        commands.append(f"SetPointSize({name}, 6)")

    for i in range(len(analysis.get("inflection_points", []))):
        commands.append(f'SetColor(U{i + 1}, "#f4a261")')
        commands.append(f"SetPointSize(U{i + 1}, 4)")

    for obj in objects:
        if isinstance(obj, Point2D) and obj.name.startswith(("VA", "HA", "ProjX", "ProjY")):
            commands.append(f"SetVisibleInView({obj.name}, 1, false)")

    sample_expr = analysis.get("_evaluated_expr") or analysis.get("_parsed_expr")
    return scene, commands, _sample_graph_points(sample_expr, analysis.get("_domain_info"))


def _sample_graph_points(expr, domain_info=None) -> list[dict[str, float]]:
    if expr is None:
        return []
    try:
        fn = lambdify(x, expr, "math")
    except Exception:
        return []

    points: list[dict[str, float]] = []
    for i in range(161):
        x_val = -8 + i * 0.1
        if not in_domain(domain_info, x_val):
            continue
        try:
            y_val = float(fn(x_val))
        except (ValueError, ZeroDivisionError, OverflowError, TypeError):
            continue
        if y_val != y_val or y_val in (float("inf"), float("-inf")) or abs(y_val) > 1_000:
            continue
        points.append({"x": round(x_val, 4), "y": round(y_val, 4)})
    return points


def _graph_domains_from_analysis(analysis: dict) -> list[tuple[float | str, float | str]]:
    domain_info = analysis.get("_domain_info")
    components = getattr(domain_info, "components", ())
    domains: list[tuple[float | str, float | str]] = []
    for component in components:
        start = _geogebra_bound(component.start)
        end = _geogebra_bound(component.end)
        if start is None or end is None:
            continue
        domains.append((start, end))
    return domains


def _geogebra_bound(value) -> float | str | None:
    text = str(value)
    if text in ("-oo", "-∞"):
        return "-∞"
    if text in ("oo", "+∞", "∞"):
        return "+∞"
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _geogebra_expression(expression: str) -> str:
    return expression.replace("**", "^").replace("Abs(", "abs(").replace(" ", "")


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
