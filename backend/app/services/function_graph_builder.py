from sympy import Symbol

from app.renderers.geogebra_commands import build_geogebra_commands
from app.schemas.scene import Annotation, FunctionGraph, MathScene, Point2D, SceneView, Segment
from app.services.function_graph_sampling import build_graph_analysis, flatten_graph_points

x = Symbol("x", real=True)
m = Symbol("m", real=True)


def build_function_graph(analysis: dict) -> tuple[MathScene, list[str], list[dict[str, float]]]:
    objects = []
    annotations = []

    graph_expression = analysis.get("_graph_expr") or analysis.get("evaluated_expression") or analysis["expression"]
    interval_analysis = analysis.get("interval_analysis")
    requested_interval = None
    if interval_analysis:
        requested_interval = {
            "a": interval_analysis["a"],
            "b": interval_analysis["b"],
            "open_a": interval_analysis.get("open_a", False),
            "open_b": interval_analysis.get("open_b", False),
        }
    graph_analysis = build_graph_analysis(
        analysis.get("_evaluated_expr") or analysis.get("_parsed_expr"),
        x,
        analysis.get("_domain_info"),
        analysis,
        requested_interval=requested_interval,
    )
    analysis["graph_analysis_v2"] = graph_analysis

    graph_segments = graph_analysis.get("segments", [])
    excluded_endpoint_xs = {
        str(item.get("exact")) for item in graph_analysis.get("singularities", [])
    }
    if graph_segments:
        for index, segment in enumerate(graph_segments):
            graph_name = "f" if len(graph_segments) == 1 else f"f{index + 1}"
            start = segment["start"]["exact"]
            end = segment["end"]["exact"]
            left_window_clipped = bool(segment.get("left_window_clipped"))
            right_window_clipped = bool(segment.get("right_window_clipped"))
            objects.append(FunctionGraph(
                name=graph_name,
                expression=_geogebra_expression(segment.get("expression_exact") or graph_expression),
                domain=None if left_window_clipped and right_window_clipped else (start, end),
                left_open=bool(segment.get("left_open")),
                right_open=bool(segment.get("right_open")),
                component_id=segment.get("component_id"),
            ))
            _append_endpoint_marker(objects, annotations, segment, index, "left", excluded_endpoint_xs)
            _append_endpoint_marker(objects, annotations, segment, index, "right", excluded_endpoint_xs)
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

    active_exact = (analysis.get("parameters") or {}).get("active_exact") or {}
    parameter_suffix = f", m = {active_exact['m']}" if "m" in active_exact else ""
    scene = MathScene(
        problem_text=f"Đồ thị y = {analysis.get('evaluated_expression') or analysis['expression']}{parameter_suffix}",
        topic="function_graph",
        renderer="geogebra_2d",
        objects=objects,
        annotations=annotations,
        view=SceneView(dimension="2d", show_axes=True, show_grid=True),
    )
    commands = build_geogebra_commands(scene)
    line_analysis = analysis.get("line_analysis")
    if line_analysis:
        line_expressions = line_analysis.get("graph_expressions") or (
            [line_analysis["graph_expression"]] if line_analysis.get("graph_expression") else []
        )
        is_vertical = line_analysis.get("kind") == "vertical" and line_analysis.get("x0_exact") is not None
        if is_vertical:
            line_expressions = [f"x={line_analysis['x0_exact']}"]
        for index, expression in enumerate(line_expressions):
            name = "g" if len(line_expressions) == 1 else f"g{index + 1}"
            definition = f"{name}: {_geogebra_expression(expression)}" if is_vertical else f"{name}(x)={_geogebra_expression(expression)}"
            commands.append(definition)
            commands.append(f'SetColor({name}, "#2563eb")')
            commands.append(f'SetLineThickness({name}, 4)')
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
        if isinstance(obj, Point2D) and obj.metadata.get("kind") in {"open_endpoint", "closed_endpoint"}:
            commands.append(f'SetColor({obj.name}, "#2563eb")')
            commands.append(f"SetPointStyle({obj.name}, {2 if obj.metadata['kind'] == 'open_endpoint' else 0})")
            commands.append(f"SetPointSize({obj.name}, 5)")

    for obj in objects:
        if isinstance(obj, Point2D) and obj.name.startswith(("VA", "HA", "ProjX", "ProjY")):
            commands.append(f"SetVisibleInView({obj.name}, 1, false)")

    return scene, commands, flatten_graph_points(graph_analysis)


def _geogebra_expression(expression: str) -> str:
    return expression.replace("**", "^").replace("Abs(", "abs(").replace(" ", "")


def _append_endpoint_marker(
    objects: list,
    annotations: list,
    segment: dict,
    segment_index: int,
    side: str,
    excluded_xs: set[str],
) -> None:
    endpoint = segment.get(f"{side}_endpoint") or {}
    if segment.get(f"{side}_window_clipped"):
        return
    exact_x = str(endpoint.get("exact"))
    x_value = _safe_float(endpoint.get("approx"))
    y_value = _safe_float(endpoint.get("y"))
    if exact_x in excluded_xs or x_value is None or y_value is None:
        return
    name = f"D{segment_index + 1}{'L' if side == 'left' else 'R'}"
    point = Point2D(name=name, x=x_value, y=y_value)
    point.metadata["kind"] = "open_endpoint" if endpoint.get("open") else "closed_endpoint"
    point.metadata["component_id"] = segment.get("component_id")
    objects.append(point)
    annotations.append(Annotation(
        type="coordinate_label",
        target=name,
        label="biên mở" if endpoint.get("open") else "biên đóng",
        color="#2563eb",
    ))


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
