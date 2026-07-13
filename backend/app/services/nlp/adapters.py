from __future__ import annotations

import re
from typing import Callable

from app.schemas.algebra import AlgebraSolveRequest
from app.schemas.geometry_reasoning import GeometryGoal
from app.schemas.nlp import (
    Ambiguity,
    Constraint,
    Entity,
    FieldConfidence,
    InputEnvelope,
    InterpretationCandidate,
    MathIntent,
    Provenance,
)
from app.services.algebra.interpreter import interpret_algebra_input
from app.services.nlp.normalization import NormalizedInput
from app.services.nlp.router import AdapterRegistry, infer_target
from app.services.problem_classifier import classify_render_problem, classify_solve_question
from app.services.safe_math_parser import SafeMathParseError, parse_safe_math_expression

ADAPTER_VERSION = "nlp-rules-v1"
_UNSUPPORTED_RE = re.compile(
    r"\b(ignore previous|reveal secrets?|select \*|dịch .* tiếng anh|dich .* tieng anh|viết bài văn|viet bai van|bỏ mọi quy tắc|bo moi quy tac)\b",
    re.IGNORECASE,
)
_RELATION_RE = re.compile(r"(?:<=|>=|!=|=|<|>)")
_VARIABLE_RE = re.compile(r"\b([a-zA-Z])\b")
_POINT_RE = re.compile(r"\b([A-Z])\b")
_PLANE_RE = re.compile(r"\(([A-Z]{3,4})\)")
_SEGMENT_RE = re.compile(r"\b([A-Z]{2})\b")
_SOLID_RE = re.compile(r"\b([A-Z]\.[A-Z]{3,5}|[A-Z]{4})\b")


def default_registry() -> AdapterRegistry:
    return AdapterRegistry.from_mapping(
        {
            "algebra": interpret_algebra,
            "render": interpret_render,
            "geometry_solve": interpret_geometry_solve,
            "analyzer": interpret_analyzer,
            "ocr": interpret_ocr,
        }
    )


def interpret_algebra(envelope: InputEnvelope, normalized: NormalizedInput) -> list[InterpretationCandidate]:
    unsupported = _unsupported_candidate(normalized)
    if unsupported:
        return [unsupported]
    request_data = {
        "input": normalized.text,
        "input_format": envelope.input_format,
        "save_history": False,
    }
    for field in ("topic", "expression_action", "variables", "parameters", "domain", "domain_source", "angle_unit", "interval"):
        if field in envelope.context:
            request_data[field] = envelope.context[field]
    try:
        request = AlgebraSolveRequest.model_validate(request_data)
    except ValueError:
        request = AlgebraSolveRequest(input=normalized.text, save_history=False)
    interpretation = interpret_algebra_input(request)
    topic = interpretation.topic_hint if interpretation.topic_hint != "auto" else "unknown"
    missing_fields: list[str] = []
    ambiguities: list[Ambiguity] = []
    if topic == "unknown":
        missing_fields.append("intent")
    if _asks_to_solve(normalized.text) and not _RELATION_RE.search(interpretation.canonical_input) and not _is_structured_operation(interpretation.canonical_input):
        missing_fields.append("relation_or_target")
        ambiguities.append(
            Ambiguity(
                code="MISSING_RELATION",
                field="canonical_text",
                message="Đề yêu cầu giải nhưng chưa có quan hệ hoặc mục tiêu đầy đủ.",
                provenance=[normalized.provenance()],
            )
        )
    entities = [
        Entity(
            kind="variable",
            name=variable,
            value=variable,
            confidence=0.9,
            provenance=[normalized.provenance()],
        )
        for variable in interpretation.variables
    ]
    constraints = []
    if "domain" in envelope.context:
        constraints.append(
            Constraint(
                kind="domain",
                arguments=interpretation.variables,
                value=interpretation.domain,
                confidence=1.0,
                provenance=[_rule_provenance("algebra")],
            )
        )
    confidence = 0.82 if topic != "unknown" and not missing_fields else 0.4
    task = interpretation.expression_action or _algebra_task(topic)
    return [
        InterpretationCandidate(
            candidate_id="algebra-1",
            intent=MathIntent(domain="algebra" if topic != "unknown" else "unknown", topic=topic, task=task),
            canonical_text=interpretation.canonical_input,
            canonical_payload={
                "input": interpretation.canonical_input,
                "input_format": (
                    "structured"
                    if interpretation.detected_format == "structured"
                    else "latex"
                    if interpretation.detected_format == "latex"
                    else "plain"
                ),
                "input_mode": envelope.input_mode,
                "topic": interpretation.topic_hint,
                "expression_action": interpretation.expression_action,
                "variables": interpretation.variables,
                "domain": interpretation.domain,
                "save_history": False,
            },
            entities=entities,
            constraints=constraints,
            ambiguities=ambiguities,
            field_confidences=[
                FieldConfidence(field="intent", confidence=confidence),
                FieldConfidence(field="canonical_text", confidence=0.88 if interpretation.canonical_input else 0.0),
            ],
            confidence=confidence,
            missing_fields=missing_fields,
            clarification_question="Bạn muốn giải quan hệ nào?" if "relation_or_target" in missing_fields else None,
            provenance=[_rule_provenance("algebra"), normalized.provenance()],
        )
    ]


def interpret_render(_envelope: InputEnvelope, normalized: NormalizedInput) -> list[InterpretationCandidate]:
    unsupported = _unsupported_candidate(normalized)
    if unsupported:
        return [unsupported]
    classification = classify_render_problem(normalized.text)
    entities, constraints = _geometry_structure(normalized)
    if classification.topic == "unknown" and not entities:
        return []
    missing_fields = ["geometry_constraints"] if classification.topic == "unknown" else []
    confidence = classification.confidence if classification.topic != "unknown" else 0.35
    return [
        InterpretationCandidate(
            candidate_id="render-1",
            intent=MathIntent(
                domain=classification.domain,
                topic=classification.topic,
                task="render_scene",
                subtype=classification.sub_type,
            ),
            entities=entities,
            constraints=constraints,
            field_confidences=[FieldConfidence(field="intent", confidence=confidence)],
            confidence=confidence,
            missing_fields=missing_fields,
            clarification_question="Bạn cần bổ sung quan hệ nào để xác định hình?" if missing_fields else None,
            provenance=[_rule_provenance("render"), normalized.provenance()],
        )
    ]


def interpret_geometry_solve(envelope: InputEnvelope, normalized: NormalizedInput) -> list[InterpretationCandidate]:
    unsupported = _unsupported_candidate(normalized)
    if unsupported:
        return [unsupported]
    canonical_text = _canonical_geometry_question(normalized.text)
    scene_topic = str(envelope.context.get("scene_topic") or "unknown")
    classification = classify_solve_question(normalized.text, {"topic": scene_topic})
    entities, constraints = _geometry_structure(
        NormalizedInput(raw=normalized.raw, text=canonical_text, source_indices=normalized.source_indices)
        if len(canonical_text) == len(normalized.text)
        else normalized
    )
    polygon_task = classification.task_type == "perimeter" or (
        classification.task_type == "area" and scene_topic == "plane_geometry"
    )
    if polygon_task:
        entities = list({
            ("polygon" if entity.kind in {"solid", "plane"} else entity.kind, entity.name): (
                entity.model_copy(update={"kind": "polygon", "confidence": 0.9})
                if entity.kind in {"solid", "plane"}
                else entity
            )
            for entity in entities
        }.values())
    if classification.task_type in {"triangle_congruence", "triangle_similarity"}:
        entities = [
            Entity(
                kind="triangle",
                name=match.group(1).upper(),
                confidence=0.95,
                provenance=[normalized.provenance()],
            )
            for match in re.finditer(
                r"(?:tam\s*gi[aá]c|triangle|[△∆])\s*([A-Z]{3})",
                normalized.text,
                re.IGNORECASE,
            )
        ]
    missing_fields: list[str] = []
    if classification.task_type == "unknown":
        missing_fields.append("target")
    elif classification.task_type in {"triangle_congruence", "triangle_similarity"} and len(entities) != 2:
        missing_fields.append("target_triangles")
    elif classification.task_type == "pythagoras" and len(entities) < 1:
        missing_fields.append("target_objects")
    elif classification.task_type in {"distance", "angle", "projection", "reflection", "equation"} and len(entities) < 2:
        missing_fields.append("target_objects")

    target_object_ids, resolution_ambiguities = _resolve_geometry_entities(entities, envelope.context)
    if resolution_ambiguities:
        missing_fields.append("scene_object_resolution")
    ambiguities = [
        Ambiguity(
            code="SCENE_OBJECT_UNRESOLVED",
            field="target_objects",
            message=f"Không ánh xạ duy nhất đối tượng {name} vào hình đã dựng.",
            alternatives=alternatives,
            provenance=[normalized.provenance()],
        )
        for name, alternatives in resolution_ambiguities
    ]
    task = _geometry_goal_task(classification.task_type or "unknown")
    goal_subtype = classification.sub_type or _geometry_subtype_from_entities(classification.task_type or "unknown", entities)
    method = str(envelope.context.get("geometry_method") or envelope.context.get("method") or "classical")
    if method not in {"classical", "oxyz"}:
        method = "classical"
    geometry_goal = None
    if task and target_object_ids and not resolution_ambiguities:
        geometry_goal = GeometryGoal(
            task=task,
            subtype=goal_subtype or "general",
            target_object_ids=target_object_ids,
            relation_type=goal_subtype if task in {"prove", "relation"} else None,
            method=method,
        ).model_dump(mode="json")
    confidence = classification.confidence if not missing_fields else min(classification.confidence, 0.45)
    canonical_payload = {
        "question": canonical_text,
        "input_mode": envelope.input_mode,
        "method": method,
    }
    if isinstance(envelope.context.get("scene_objects"), list):
        canonical_payload.update({
            "target_object_ids": target_object_ids,
            "geometry_goal": geometry_goal,
        })
    return [
        InterpretationCandidate(
            candidate_id="geometry-solve-1",
            intent=MathIntent(
                domain=classification.domain,
                topic=classification.topic,
                task=classification.task_type or "unknown",
                subtype=goal_subtype,
            ),
            canonical_text=canonical_text,
            canonical_payload=canonical_payload,
            entities=entities,
            constraints=constraints,
            ambiguities=ambiguities,
            field_confidences=[FieldConfidence(field="intent", confidence=confidence)],
            confidence=confidence,
            missing_fields=missing_fields,
            clarification_question="Bạn muốn tính hoặc chứng minh đại lượng nào, giữa các đối tượng nào?" if missing_fields else None,
            provenance=[_rule_provenance("geometry-solve"), normalized.provenance()],
        )
    ]


def interpret_analyzer(_envelope: InputEnvelope, normalized: NormalizedInput) -> list[InterpretationCandidate]:
    unsupported = _unsupported_candidate(normalized)
    if unsupported:
        return [unsupported]
    expression, task = _extract_analyzer_expression(normalized.text)
    ambiguities: list[Ambiguity] = []
    missing_fields: list[str] = []
    if re.search(r"\b(?:hay|hoặc|hoac)\b", normalized.text, re.IGNORECASE):
        ambiguities.append(
            Ambiguity(
                code="MULTIPLE_EXPRESSIONS",
                field="expression",
                message="Đầu vào có nhiều biểu thức thay thế.",
                alternatives=[part.strip() for part in re.split(r"\b(?:hay|hoặc|hoac)\b", normalized.text, flags=re.IGNORECASE) if part.strip()][:4],
                provenance=[normalized.provenance()],
            )
        )
    canonical = None
    parse_error: str | None = None
    if not expression:
        missing_fields.append("expression")
    else:
        try:
            parsed = parse_safe_math_expression(expression)
            canonical = parsed.normalized.replace(" ", "").replace("**", "^")
        except SafeMathParseError as error:
            parse_error = str(error)
            missing_fields.append("valid_expression")
    confidence = 0.9 if canonical and not ambiguities else 0.4
    return [
        InterpretationCandidate(
            candidate_id="analyzer-1",
            intent=MathIntent(domain="function", topic="function_analysis", task=task),
            canonical_text=canonical,
            canonical_payload={"expression": canonical, "requested_tools": [task]} if canonical else None,
            entities=[
                Entity(kind="variable", name="x", value="x", confidence=1.0, provenance=[normalized.provenance()])
            ] if canonical and re.search(r"\bx\b", canonical) else [],
            ambiguities=ambiguities,
            field_confidences=[
                FieldConfidence(field="intent", confidence=0.9),
                FieldConfidence(field="expression", confidence=confidence),
            ],
            confidence=confidence,
            missing_fields=missing_fields,
            clarification_question=(f"Biểu thức chưa hợp lệ: {parse_error}" if parse_error else "Bạn muốn phân tích biểu thức nào?") if missing_fields else None,
            provenance=[_rule_provenance("analyzer"), normalized.provenance()],
        )
    ]


def interpret_ocr(envelope: InputEnvelope, normalized: NormalizedInput) -> list[InterpretationCandidate]:
    delegated_target = infer_target(normalized.text)
    delegated: Callable[[InputEnvelope, NormalizedInput], list[InterpretationCandidate]] = {
        "algebra": interpret_algebra,
        "render": interpret_render,
        "geometry_solve": interpret_geometry_solve,
        "analyzer": interpret_analyzer,
    }[delegated_target]
    delegated_candidates = delegated(envelope.model_copy(update={"target": delegated_target}), normalized)
    minimum_confidence = _minimum_ocr_confidence(envelope)
    for candidate in delegated_candidates:
        candidate.provenance.append(
            Provenance(
                source="ocr",
                adapter="ocr-structured",
                version=ADAPTER_VERSION,
                provider=_optional_string(envelope.context.get("provider")),
                model=_optional_string(envelope.context.get("model")),
            )
        )
        if minimum_confidence is not None:
            candidate.field_confidences.append(FieldConfidence(field="ocr", confidence=minimum_confidence))
            candidate.confidence = min(candidate.confidence, minimum_confidence)
        if minimum_confidence is not None and minimum_confidence < 0.95:
            candidate.ambiguities.append(
                Ambiguity(
                    code="LOW_OCR_CONFIDENCE",
                    field="text",
                    message="OCR có vùng nhận dạng chưa đủ chắc chắn.",
                    provenance=[candidate.provenance[-1]],
                )
            )
            candidate.clarification_question = "Hãy kiểm tra lại phần OCR có độ tin cậy thấp."
    return delegated_candidates


def _canonical_geometry_question(text: str) -> str:
    question = re.sub(r"\s+", " ", text).strip()
    question = re.sub(
        r"\b(?:k/c|kc|khoang\s+cach|khoảng\s+cách)\b",
        "d",
        question,
        flags=re.IGNORECASE,
    )
    question = re.sub(r"\b(?:den|đến|toi|tới|tu|từ|cua|của)\b", " ", question, flags=re.IGNORECASE)
    question = re.sub(
        r"\b(?:mp|mat\s+phang|mặt\s+phẳng)\s+(\([A-Za-z0-9'\s]+\)|[A-Za-z](?:\s*[A-Za-z0-9']\s*){2,})",
        lambda match: f"({_compact_geometry_points(match.group(1))})",
        question,
        flags=re.IGNORECASE,
    )
    question = re.sub(
        r"\b(?:dien\s+tich|diện\s+tích)\s+([A-Za-z](?:\s*[A-Za-z0-9']\s*){2,})",
        lambda match: f"S({_compact_geometry_points(match.group(1))})",
        question,
        flags=re.IGNORECASE,
    )
    question = re.sub(
        r"\b(?:chu\s+vi|perimeter)\s+([A-Za-z](?:\s*[A-Za-z0-9']\s*){2,})",
        lambda match: f"P({_compact_geometry_points(match.group(1))})",
        question,
        flags=re.IGNORECASE,
    )
    question = re.sub(
        r"\b(?:the\s+tich|thể\s+tích)\s+([A-Za-z][A-Za-z0-9']*(?:\s*\.\s*)?[A-Za-z](?:\s*[A-Za-z0-9']\s*){2,})",
        lambda match: f"V({_compact_geometry_solid(match.group(1))})",
        question,
        flags=re.IGNORECASE,
    )
    question = re.sub(
        r"\bd\s+([A-Za-z](?:[0-9]+|')?)\s+(\([A-Za-z0-9'\s]+\)|[A-Za-z](?:\s*[A-Za-z0-9']\s*){1,})",
        lambda match: f"d({match.group(1).upper()},{_compact_geometry_target(match.group(2))})",
        question,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", question).strip()


def _compact_geometry_points(value: str) -> str:
    return "".join(match.group(0).upper() for match in re.finditer(r"[A-Za-z](?:[0-9]+|')?", value))


def _compact_geometry_target(value: str) -> str:
    target = value.strip()
    if target.startswith("(") and target.endswith(")"):
        return f"({_compact_geometry_points(target[1:-1])})"
    return _compact_geometry_points(target)


def _compact_geometry_solid(value: str) -> str:
    cleaned = re.sub(r"\s+", "", value)
    if "." in cleaned:
        left, right = cleaned.split(".", 1)
        return f"{_compact_geometry_points(left)}.{_compact_geometry_points(right)}"
    compact = _compact_geometry_points(cleaned)
    return f"{compact[0]}.{compact[1:]}" if len(compact) >= 4 else compact


def _geometry_subtype_from_entities(task: str, entities: list[Entity]) -> str | None:
    kinds = [entity.kind for entity in entities if entity.kind != "solid"]
    if task in {"distance", "angle"} and len(kinds) >= 2:
        pair = kinds[:2]
        if pair == ["point", "point"]:
            return "point_point"
        if set(pair) == {"point", "line"}:
            return "point_line"
        if set(pair) == {"point", "plane"}:
            return "point_plane"
        if pair == ["line", "line"]:
            return "line_line"
        if set(pair) == {"line", "plane"}:
            return "line_plane"
        if pair == ["plane", "plane"]:
            return "plane_plane"
    if task in {"area", "perimeter"}:
        return "polygon"
    if task == "volume":
        return "solid"
    return None


def _geometry_goal_task(task: str) -> str | None:
    return {
        "proof": "prove",
        "distance": "distance",
        "angle": "angle",
        "area": "area",
        "perimeter": "perimeter",
        "pythagoras": "pythagoras",
        "triangle_congruence": "triangle_congruence",
        "triangle_similarity": "triangle_similarity",
        "quadrilateral_metric": "quadrilateral_metric",
        "circle_metric": "circle_metric",
        "volume": "volume",
        "projection": "projection",
        "reflection": "reflection",
        "equation": "equation",
        "relation": "relation",
        "intersection": "intersection",
        "construct": "construct",
    }.get(task)


def _resolve_geometry_entities(
    entities: list[Entity],
    context: dict[str, object],
) -> tuple[list[str], list[tuple[str, list[str]]]]:
    catalog = context.get("scene_objects")
    if not isinstance(catalog, list):
        return [], []
    objects = [item for item in catalog if isinstance(item, dict) and isinstance(item.get("id"), str)]
    point_labels = {
        str(item["id"]): _geometry_alias(str(item.get("label") or item["id"]))
        for item in objects
        if item.get("type") in {"point_2d", "point_3d"}
    }
    aliases: dict[tuple[str, str], list[str]] = {}
    for item in objects:
        object_id = str(item["id"])
        kind = _catalog_geometry_kind(str(item.get("type") or ""))
        if kind is None:
            continue
        label = _geometry_alias(str(item.get("label") or ""))
        if not label:
            label = _derived_object_label(item, point_labels)
        if label:
            aliases.setdefault((kind, label), []).append(object_id)

    resolved: list[str] = []
    ambiguities: list[tuple[str, list[str]]] = []
    for entity in entities:
        if entity.kind in {"solid", "polygon", "triangle"}:
            point_ids = [
                ids[0]
                for point_name in re.findall(r"[A-Z](?:[0-9]+|')?", entity.name.upper())
                if len(ids := aliases.get(("point", point_name), [])) == 1
            ]
            if point_ids:
                resolved.extend(point_ids)
            else:
                ambiguities.append((entity.name, []))
            continue
        candidates = aliases.get((entity.kind, _geometry_alias(entity.name)), [])
        if len(candidates) == 1:
            resolved.append(candidates[0])
        else:
            ambiguities.append((entity.name, candidates[:8]))
    return list(dict.fromkeys(resolved)), ambiguities


def _catalog_geometry_kind(object_type: str) -> str | None:
    if object_type in {"point_2d", "point_3d"}:
        return "point"
    if object_type in {"segment", "line_2d", "line_3d", "vector_2d", "vector_3d"}:
        return "line"
    if object_type in {"face", "plane"}:
        return "plane"
    return None


def _geometry_alias(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9']", "", value).upper()


def _derived_object_label(item: dict, point_labels: dict[str, str]) -> str:
    point_ids = item.get("point_ids")
    if isinstance(point_ids, (list, tuple)):
        return "".join(point_labels.get(str(point_id), "") for point_id in point_ids)
    from_id = item.get("from_point_id")
    to_id = item.get("to_point_id")
    if from_id and to_id:
        return point_labels.get(str(from_id), "") + point_labels.get(str(to_id), "")
    return ""


def _geometry_structure(normalized: NormalizedInput) -> tuple[list[Entity], list[Constraint]]:
    provenance = [normalized.provenance()]
    entities: dict[tuple[str, str], Entity] = {}
    occupied_spans: list[tuple[int, int]] = []
    for match in _SOLID_RE.finditer(normalized.text):
        name = match.group(1)
        occupied_spans.append(match.span(1))
        entities[("solid", name)] = Entity(kind="solid", name=name, confidence=0.88, provenance=provenance)
    for match in _PLANE_RE.finditer(normalized.text):
        name = match.group(1)
        occupied_spans.append(match.span(1))
        entities[("plane", name)] = Entity(kind="plane", name=name, confidence=0.92, provenance=provenance)
    for match in _SEGMENT_RE.finditer(normalized.text):
        name = match.group(1)
        occupied_spans.append(match.span(1))
        entities[("line", name)] = Entity(kind="line", name=name, confidence=0.82, provenance=provenance)
    for match in _POINT_RE.finditer(normalized.text):
        name = match.group(1)
        start, end = match.span(1)
        if any(start >= occupied_start and end <= occupied_end for occupied_start, occupied_end in occupied_spans):
            continue
        if name in {"S", "V"} and re.match(r"\s*\(", normalized.text[end:]):
            continue
        entities[("point", name)] = Entity(kind="point", name=name, confidence=0.75, provenance=provenance)
    constraints: list[Constraint] = []
    if re.search(r"vu[oô]ng\s+g[oó]c|\bperp\b|⊥", normalized.text, re.IGNORECASE):
        arguments = [entity.name for entity in entities.values() if entity.kind in {"line", "plane"}][:2]
        constraints.append(Constraint(kind="perpendicular", arguments=arguments, confidence=0.75, provenance=provenance))
    if re.search(r"song\s+song|parallel|∥", normalized.text, re.IGNORECASE):
        arguments = [entity.name for entity in entities.values() if entity.kind in {"line", "plane"}][:2]
        constraints.append(Constraint(kind="parallel", arguments=arguments, confidence=0.75, provenance=provenance))
    ordered_entities = sorted(
        entities.values(),
        key=lambda entity: (
            normalized.text.find(entity.name) if normalized.text.find(entity.name) >= 0 else len(normalized.text),
            entity.kind,
        ),
    )
    return ordered_entities, constraints


def _extract_analyzer_expression(text: str) -> tuple[str, str]:
    lowered = text.lower()
    task = "analyze"
    if "cực trị" in lowered or "cuc tri" in lowered:
        task = "extrema"
    elif "tiệm cận" in lowered or "tiem can" in lowered:
        task = "asymptotes"
    elif lowered.startswith(("vẽ", "ve ")):
        task = "plot"
    expression = re.sub(
        r"(?i)^\s*(?:khảo\s+sát\s+hàm\s+số|khao\s+sat\s+ham\s+so|tìm\s+cực\s+trị\s+của|tim\s+cuc\s+tri\s+cua|tìm\s+tiệm\s+cận\s+của|tim\s+tiem\s+can\s+cua|vẽ\s+hàm\s+số|ve\s+ham\s+so)\s*",
        "",
        text,
    ).strip()
    expression = re.sub(r"(?i)^(?:y|f\s*\(\s*x\s*\))\s*=\s*", "", expression).strip()
    return expression, task


def _minimum_ocr_confidence(envelope: InputEnvelope) -> float | None:
    values = []
    for line in envelope.context.get("lines", []):
        if isinstance(line, dict) and isinstance(line.get("confidence"), (int, float)):
            values.append(float(line["confidence"]))
    confidence = envelope.context.get("confidence")
    if isinstance(confidence, (int, float)):
        values.append(float(confidence))
    return min(values) if values else None


def _unsupported_candidate(normalized: NormalizedInput) -> InterpretationCandidate | None:
    if not _UNSUPPORTED_RE.search(normalized.text):
        return None
    return InterpretationCandidate(
        candidate_id="unsupported-1",
        intent=MathIntent(domain="unknown", topic="unknown", task="unknown"),
        confidence=1.0,
        unsupported_reason="Yêu cầu nằm ngoài phạm vi diễn giải bài toán toán học.",
        provenance=[_rule_provenance("safety-scope"), normalized.provenance()],
    )


def _asks_to_solve(text: str) -> bool:
    return bool(re.search(r"\b(?:giải|giai|tìm nghiệm|tim nghiem)\b", text, re.IGNORECASE))


def _is_structured_operation(text: str) -> bool:
    return bool(re.match(r"^(?:gcd|lcm|power|divisible|percent(?:_ratio|_base)?|ratio|word_(?:inventory|product|share)|C|A|P|P_not|P_and|Punion|stats|derivative|limit|integral|quadratic_)\b", text))


def _algebra_task(topic: str) -> str:
    return {
        "calculus_derivative": "differentiate",
        "calculus_limit": "limit",
        "calculus_integral": "integrate",
        "parameter": "solve_parameter",
        "combinatorics_probability": "evaluate_probability",
    }.get(topic, "solve" if topic != "unknown" else "unknown")


def _rule_provenance(adapter: str) -> Provenance:
    return Provenance(source="rule", adapter=adapter, version=ADAPTER_VERSION)


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None