from app.schemas.algebra import AlgebraSolveRequest
from app.services.algebra.ai_extraction import AlgebraExtractionPayload, merge_extraction_request


def test_merge_keeps_user_domain_topic_and_variables():
    base = AlgebraSolveRequest(input="raw", topic="system", domain="Z", variables=["y"])
    payload = AlgebraExtractionPayload(
        input="x+y=3; x-y=1",
        input_format="plain",
        topic="equation",
        variables=["x"],
        domain="R",
    )
    req, warnings = merge_extraction_request(base, payload)
    assert req.topic == "system"
    assert req.domain == "Z"
    assert req.variables == ["y"]
    assert req.input == "x+y=3; x-y=1"
    assert any("topic" in warning.lower() or "Giữ topic" in warning for warning in warnings)
    assert any("miền" in warning or "biến" in warning for warning in warnings)


def test_merge_fills_auto_fields_from_ai():
    base = AlgebraSolveRequest(input="raw", topic="auto", domain="R", variables=[])
    payload = AlgebraExtractionPayload(
        input="x^2-1=0",
        input_format="plain",
        topic="equation",
        variables=["x"],
        domain="R",
    )
    req, warnings = merge_extraction_request(base, payload)
    assert req.topic == "equation"
    assert req.variables == ["x"]
    assert req.domain == "R"
    assert req.input == "x^2-1=0"
    assert warnings == []


def test_merge_keeps_default_domain_r_over_ai():
    base = AlgebraSolveRequest(input="raw", topic="auto", domain="R", variables=[])
    payload = AlgebraExtractionPayload(
        input="x^2-1=0",
        input_format="plain",
        topic="equation",
        variables=["x"],
        domain="C",
    )
    req, warnings = merge_extraction_request(base, payload)
    assert req.domain == "R"
    assert any("miền" in warning for warning in warnings)


def test_merge_preserves_expression_action_domain_source_angle_unit():
    base = AlgebraSolveRequest(
        input="raw",
        topic="auto",
        expression_action="factor",
        domain="R",
        domain_source="user",
        angle_unit="degree",
        variables=["x"],
    )
    payload = AlgebraExtractionPayload(
        input="x^2-1",
        input_format="plain",
        topic="equation",
        variables=["x"],
        domain="C",
    )
    req, warnings = merge_extraction_request(base, payload)
    assert req.expression_action == "factor"
    assert req.domain_source == "user"
    assert req.angle_unit == "degree"
    assert req.domain == "R"
    assert any("miền" in warning for warning in warnings)
