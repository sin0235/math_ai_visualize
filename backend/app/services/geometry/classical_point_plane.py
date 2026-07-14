from __future__ import annotations

from typing import Any

import sympy as sp

from app.schemas.geometry_reasoning import (
    GeometryFact as ProofFact,
    GeometryGoal,
    GeometryProofPlan,
    GeometryProofStep,
    ProofClaim,
    VerificationEvidence,
)
from app.services.geometry.proof_search import replay_proof_plan
from app.services.geometry.orthogonal_frame import (
    OrthogonalFrame,
    ProjectionData,
    exact_expr,
    parse_point_plane_goal,
    resolve_point_plane_frame,
)
from app.services.geometry.solution_builder import SolverResult, SolverStep
from app.services.geometry_facts import GeometryFact, GeometryFactGraph, build_geometry_fact_graph, point_on_plane


def solve_classical_point_plane(
    scene: dict[str, Any],
    question: str,
    warnings: list[str] | None = None,
) -> SolverResult | None:
    goal = parse_point_plane_goal(question)
    if goal is None:
        return None
    source, plane = goal
    graph = build_geometry_fact_graph(scene)

    direct = _solve_direct_height(question, source, plane, graph, warnings or [])
    if direct is not None:
        return direct

    resolution = resolve_point_plane_frame(graph, source, plane)
    if resolution.solution is not None:
        solution = resolution.solution
        return _build_frame_result(
            question,
            source,
            plane,
            solution.frame,
            solution.projection,
            list(solution.construction_facts),
            warnings or [],
        )
    if resolution.declared_frame_seen and resolution.reason and (
        resolution.relevant_frame_seen or "độ dài ba phương" in resolution.reason
    ):
        return SolverResult(
            question,
            "Không đủ dữ kiện",
            [],
            [*(warnings or []), resolution.reason],
            confidence="insufficient",
            method="classical",
        )
    return None


def _solve_direct_height(
    question: str,
    source: str,
    plane: tuple[str, str, str],
    graph: GeometryFactGraph,
    warnings: list[str],
) -> SolverResult | None:
    plane_set = set(plane)
    for perpendicular in graph.by_type("perpendicular_line_plane"):
        line = perpendicular.args.get("line")
        fact_plane = perpendicular.args.get("plane")
        if not isinstance(line, tuple) or len(line) != 2 or source not in line:
            continue
        if set(fact_plane or ()) != plane_set:
            continue
        foot = line[1] if line[0] == source else line[0]
        if not point_on_plane(graph, foot, plane):
            continue
        length_fact = graph.length_fact(source, foot)
        if length_fact is None:
            continue
        value = exact_expr(length_fact.args.get("label"))
        if value is None:
            continue
        result_latex = sp.latex(sp.simplify(value))
        plane_name = "".join(plane)
        segment = f"{source}{foot}"
        answer = f"d({source},({plane_name})) = {result_latex}"
        steps = [
            SolverStep(
                1,
                "Xác định dữ kiện hình học",
                f"Xét điểm {source}, mặt phẳng ({plane_name}) và quan hệ vuông góc đã cho.",
                None,
                None,
                [source, foot, *plane],
                kind="input",
                claim=f"Đã xác định {segment} vuông góc ({plane_name}) và {segment} = {result_latex}",
                relation_ids=[perpendicular.id, length_fact.id],
            ),
            SolverStep(
                2,
                "Nhận ra đường cao",
                f"Vì {segment} vuông góc với mặt phẳng ({plane_name}) và {foot} thuộc ({plane_name}), nên {segment} là đoạn vuông góc kẻ từ {source} đến ({plane_name}). Do đó khoảng cách cần tìm là {segment}.",
                None,
                None,
                [source, foot, *plane],
                kind="distance_point_plane",
                formula_latex=rf"{segment}\perp({plane_name}),\ {foot}\in({plane_name})\Rightarrow d({source},({plane_name}))={segment}",
                theorem="Khoảng cách từ điểm đến mặt phẳng",
                theorem_id="distance.point_plane.perpendicular_segment",
                claim=f"d({source},({plane_name})) = {segment}",
                relation_ids=[perpendicular.id],
            ),
            SolverStep(
                3,
                "Kết luận",
                f"Mà {segment} = {result_latex}, nên d({source},({plane_name})) = {segment} = {result_latex}.",
                None,
                result_latex,
                [source, foot, *plane],
                kind="result",
                result_latex=result_latex,
                claim=answer,
                relation_ids=[perpendicular.id, length_fact.id],
            ),
        ]
        return _verified_result(
            question,
            answer,
            steps,
            [perpendicular, length_fact],
            [
                *warnings,
                "Mode Tương quan hình học đang dùng proof planner deterministic; template deterministic an toàn vẫn là fallback; AI không được phép tự thêm định lý, dữ kiện hoặc thay đổi kết quả.",
            ],
        )
    return None


def _build_frame_result(
    question: str,
    source: str,
    plane: tuple[str, str, str],
    frame: OrthogonalFrame,
    projection: ProjectionData,
    midpoint_facts: list[GeometryFact],
    warnings: list[str],
) -> SolverResult:
    plane_name = "".join(plane)
    foot = _auxiliary_name({*frame.points, *plane, source})
    result_latex = sp.latex(projection.distance)
    answer = f"d({source},({plane_name})) = {result_latex}"
    alpha_latex = sp.latex(projection.alpha)
    beta_latex = sp.latex(projection.beta)
    origin, second, third = plane
    first_line = f"{foot}{projection.first_direction_point}"
    second_line = f"{foot}{projection.second_direction_point}"
    height = f"{source}{foot}"

    original_facts = [frame.fact, *midpoint_facts]
    original_ids = [fact.id for fact in original_facts]
    foot_fact = _derived_fact(
        "derived:point-on-plane:foot",
        "point_on_plane",
        [foot, *plane],
        f"{foot} thuộc ({plane_name})",
        "construction.point_on_plane.affine_combination",
    )
    first_perpendicular = _derived_fact(
        "derived:perpendicular:first-plane-line",
        "perpendicular_lines",
        [source, foot, projection.first_direction_point],
        f"{height} vuông góc {first_line}",
        "relation.perpendicular.orthogonal_frame_dot",
    )
    second_perpendicular = _derived_fact(
        "derived:perpendicular:second-plane-line",
        "perpendicular_lines",
        [source, foot, projection.second_direction_point],
        f"{height} vuông góc {second_line}",
        "relation.perpendicular.orthogonal_frame_dot",
    )
    line_plane = _derived_fact(
        "derived:perpendicular:height-plane",
        "perpendicular_line_plane",
        [source, foot, *plane],
        f"{height} vuông góc ({plane_name})",
        "perpendicular.line_plane.two_intersecting_lines",
    )
    length = _derived_fact(
        "derived:length:height",
        "length",
        [source, foot],
        result_latex,
        "metric.orthogonal_frame.segment_length",
    )
    proof_facts = [
        *(_proof_fact(fact) for fact in original_facts),
        foot_fact,
        first_perpendicular,
        second_perpendicular,
        line_plane,
        length,
    ]
    steps = [
        SolverStep(
            1,
            "Chuẩn hóa các premise hình học",
            "Dùng fact cấu trúc có ba phương cạnh đôi một vuông góc cùng các quan hệ incidence, midpoint và độ dài đã kiểm chứng.",
            None,
            None,
            [source, *plane],
            kind="input",
            claim="Các premise cấu trúc và metric cần thiết đã được kiểm chứng.",
            relation_ids=original_ids,
        ),
        SolverStep(
            2,
            "Dựng điểm thuộc mặt phẳng đích",
            f"Dựng {foot} trong ({plane_name}) bằng tổ hợp affine của hai phương {origin}{second} và {origin}{third}.",
            None,
            None,
            [foot, *plane],
            kind="construction",
            formula_latex=(
                rf"\overrightarrow{{{origin}{foot}}}={alpha_latex}\overrightarrow{{{origin}{second}}}"
                rf"+{beta_latex}\overrightarrow{{{origin}{third}}}"
            ),
            theorem="Điểm thuộc mặt phẳng theo tổ hợp affine",
            theorem_id="construction.point_on_plane.affine_combination",
            claim=f"{foot} thuộc ({plane_name})",
            relation_ids=[frame.fact.id],
            construction_actions=[{
                "action_id": "construct-point-plane-foot",
                "type": "project_point",
                "source_object_ids": [source, *plane],
                "result_object_id": f"aux-foot-{source}-{plane_name}",
                "parameters": {"label": foot, "alpha": alpha_latex, "beta": beta_latex},
            }],
        ),
        SolverStep(
            3,
            "Chứng minh vuông góc với phương thứ nhất",
            f"Khai triển theo ba phương cạnh đôi một vuông góc cho tích vô hướng bằng 0, nên {height} vuông góc {first_line}.",
            None,
            None,
            [source, foot, projection.first_direction_point],
            kind="perpendicular_lines",
            formula_latex=rf"\overrightarrow{{{foot}{source}}}\cdot\overrightarrow{{{foot}{projection.first_direction_point}}}=0",
            theorem="Tiêu chuẩn tích vô hướng bằng không",
            theorem_id="relation.perpendicular.orthogonal_frame_dot",
            claim=f"{height} vuông góc {first_line}",
            relation_ids=[frame.fact.id],
        ),
        SolverStep(
            4,
            "Chứng minh vuông góc với phương thứ hai",
            f"Tương tự, tích vô hướng với phương độc lập thứ hai bằng 0, nên {height} vuông góc {second_line}.",
            None,
            None,
            [source, foot, projection.second_direction_point],
            kind="perpendicular_lines",
            formula_latex=rf"\overrightarrow{{{foot}{source}}}\cdot\overrightarrow{{{foot}{projection.second_direction_point}}}=0",
            theorem="Tiêu chuẩn tích vô hướng bằng không",
            theorem_id="relation.perpendicular.orthogonal_frame_dot",
            claim=f"{height} vuông góc {second_line}",
            relation_ids=[frame.fact.id],
        ),
        SolverStep(
            5,
            "Suy ra vuông góc với mặt phẳng",
            f"Hai đường {first_line} và {second_line} cắt nhau tại {foot}, cùng thuộc ({plane_name}); do đó {height} vuông góc ({plane_name}).",
            None,
            None,
            [source, foot, *plane],
            kind="distance_point_plane",
            formula_latex=rf"{height}\perp {first_line},\ {height}\perp {second_line}\Rightarrow {height}\perp({plane_name})",
            theorem="Đường thẳng vuông góc với hai đường cắt nhau trong mặt phẳng",
            theorem_id="perpendicular.line_plane.two_intersecting_lines",
            claim=f"{height} vuông góc ({plane_name})",
            relation_ids=[first_perpendicular.fact_id, second_perpendicular.fact_id, foot_fact.fact_id],
        ),
        SolverStep(
            6,
            "Tính độ dài đoạn vuông góc",
            "Áp dụng định lý Pythagore mở rộng theo ba phương đôi một vuông góc và rút gọn biểu thức exact.",
            None,
            result_latex,
            [source, foot],
            kind="metric",
            formula_latex=rf"{height}={result_latex}",
            result_latex=result_latex,
            theorem="Độ dài trong ba phương đôi một vuông góc",
            theorem_id="metric.orthogonal_frame.segment_length",
            claim=f"{height} = {result_latex}",
            relation_ids=[frame.fact.id],
        ),
        SolverStep(
            7,
            "Kết luận",
            f"Vì {height} là đoạn vuông góc từ {source} đến ({plane_name}), khoảng cách cần tìm bằng {height}.",
            None,
            result_latex,
            [source, foot, *plane],
            kind="result",
            formula_latex=rf"d({source},({plane_name}))={height}={result_latex}",
            result_latex=result_latex,
            theorem="Khoảng cách từ điểm đến mặt phẳng",
            theorem_id="distance.point_plane.perpendicular_segment",
            claim=answer,
            relation_ids=[line_plane.fact_id, length.fact_id],
        ),
    ]
    return _verified_result(question, answer, steps, original_facts, warnings, proof_facts=proof_facts)


def _verified_result(
    question: str,
    answer: str,
    steps: list[SolverStep],
    facts: list[GeometryFact],
    warnings: list[str],
    *,
    proof_facts: list[ProofFact] | None = None,
) -> SolverResult:
    plan = _proof_plan(question, answer, steps, proof_facts or [_proof_fact(fact) for fact in facts])
    replay = replay_proof_plan(plan)
    if not replay.accepted:
        return SolverResult(
            question,
            "Không đủ dữ kiện",
            [],
            [*warnings, f"Proof certificate không hợp lệ: {replay.reason or 'unknown'}"],
            confidence="insufficient",
            method="classical",
        )
    theorem_ids = list(dict.fromkeys(step.theorem_id for step in steps if step.theorem_id))
    theorem_names = {step.theorem_id: step.theorem for step in steps if step.theorem_id}
    result = SolverResult(
        question,
        answer,
        steps,
        warnings,
        confidence="verified",
        method="classical",
        used_theorems=[{"id": theorem_id, "name": theorem_names.get(theorem_id) or theorem_id} for theorem_id in theorem_ids],
    )
    result.proof_plan = plan.model_dump(mode="json")
    return result


def _proof_plan(question: str, answer: str, steps: list[SolverStep], facts: list[ProofFact]) -> GeometryProofPlan:
    fact_ids = {fact.fact_id for fact in facts}
    proof_steps: list[GeometryProofStep] = []
    previous_claim: str | None = None
    for index, step in enumerate(steps, start=1):
        claim_id = f"claim-{index}-{step.theorem_id or step.kind or 'step'}".replace(".", "-")
        referenced = [fact_id for fact_id in step.relation_ids if fact_id in fact_ids]
        proof_steps.append(GeometryProofStep(
            index=index,
            title=step.title,
            explanation=step.explanation,
            claim=ProofClaim(
                claim_id=claim_id,
                text=step.claim or step.explanation,
                fact_ids=referenced,
                theorem_id=step.theorem_id,
                depends_on=[previous_claim] if previous_claim else [],
            ),
            highlight_object_ids=step.highlight_object_ids,
            relation_ids=referenced,
            construction_actions=step.construction_actions,
        ))
        previous_claim = claim_id
    return GeometryProofPlan(
        goal=GeometryGoal(
            task="distance",
            subtype="distance_point_plane",
            target_object_ids=list(dict.fromkeys(name for step in steps for name in step.highlight))[:12] or ["scene"],
            method="classical",
        ),
        facts=facts,
        steps=proof_steps,
        answer=answer,
        verification_state="verified",
    )


def _proof_fact(fact: GeometryFact) -> ProofFact:
    provenance = "given" if fact.source == "given" else "symbolically_verified" if fact.trusted else "derived"
    status = "given" if fact.source == "given" else "verified" if fact.trusted else "derived"
    return ProofFact(
        fact_id=fact.id,
        type=fact.type,
        object_ids=_fact_objects(fact),
        value=str(fact.args.get("label")) if fact.args.get("label") is not None else None,
        provenance=provenance,
        evidence=[VerificationEvidence(
            source="derived_fact" if fact.type.startswith("derived_") else "relation",
            ref_id=fact.id,
            status=status,
            verifier="geometry_fact_graph" if status == "verified" else None,
            details={"source": fact.source, "text": fact.text},
        )],
    )


def _derived_fact(
    fact_id: str,
    fact_type: str,
    object_ids: list[str],
    value: str,
    theorem_id: str,
) -> ProofFact:
    return ProofFact(
        fact_id=fact_id,
        type=fact_type,
        object_ids=object_ids,
        value=value,
        provenance="symbolically_verified",
        evidence=[VerificationEvidence(
            source="theorem",
            ref_id=theorem_id,
            status="verified",
            verifier="classical_point_plane_engine",
            details={"theorem_id": theorem_id},
        )],
    )


def _fact_objects(fact: GeometryFact) -> list[str]:
    result: list[str] = []
    for key, value in fact.args.items():
        if key in {"label", "value", "axis_lengths", "source_ids", "structure"}:
            continue
        if isinstance(value, str):
            result.append(value)
        elif isinstance(value, tuple | list):
            result.extend(str(item) for item in value)
    return list(dict.fromkeys(result))[:12]


def _auxiliary_name(used: set[str]) -> str:
    if "H" not in used:
        return "H"
    index = 1
    while f"H_{index}" in used:
        index += 1
    return f"H_{index}"
