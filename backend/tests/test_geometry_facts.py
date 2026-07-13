from app.services.classical_proof import build_classical_proof
from app.services.geometry_facts import build_geometry_fact_graph


def test_geometry_fact_graph_keeps_trusted_length_and_perpendicular_plane():
    scene = {
        "annotations": [{"type": "length", "target": "S-A", "label": "3", "metadata": {"source": "given"}}],
        "relations": [{"type": "perpendicular", "object_1": "SA", "object_2": "plane(ABC)", "metadata": {"source": "given"}}],
    }

    graph = build_geometry_fact_graph(scene)

    assert graph.length_label("S", "A") == "3"
    facts = graph.by_type("perpendicular_line_plane")
    assert len(facts) == 1
    assert facts[0].args == {"line": ("S", "A"), "plane": ("A", "B", "C")}
    assert facts[0].trusted is True


def test_geometry_fact_graph_rejects_failed_relation_verification():
    scene = {
        "relations": [
            {
                "type": "perpendicular",
                "object_1": "SA",
                "object_2": "plane(ABC)",
                "verification": {"status": "failed"},
                "metadata": {"source": "given"},
            }
        ]
    }

    graph = build_geometry_fact_graph(scene)

    assert graph.by_type("perpendicular_line_plane") == []


def test_classical_proof_uses_height_for_point_plane_distance():
    scene = {
        "annotations": [{"type": "length", "target": "S-A", "label": "3", "metadata": {"source": "given"}}],
        "relations": [{"type": "perpendicular", "object_1": "SA", "object_2": "plane(ABC)", "metadata": {"source": "given"}}],
    }

    proof = build_classical_proof(scene, "d(S,(ABC))", "distance_point_plane", ["S", "A", "B", "C"], "d(S,(ABC)) = 3", "3")

    assert proof is not None
    assert proof.steps[1].title == "Nhận ra đường cao"
    assert proof.steps[1].claim == "d(S,(ABC)) = SA"
    assert "Khoảng cách từ điểm đến mặt phẳng" in (proof.steps[1].theorem or "")


def test_classical_proof_returns_none_when_height_missing():
    proof = build_classical_proof({}, "d(S,(ABC))", "distance_point_plane", ["S", "A", "B", "C"], "d(S,(ABC)) = 3", "3")

    assert proof is None


def test_classical_proof_uses_verified_perpendicular_lines_for_angle():
    scene = {
        "relations": [
            {
                "id": "ab-perp-ac",
                "type": "perpendicular",
                "object_1": "AB",
                "object_2": "AC",
                "source": "given",
                "verification": {"status": "verified"},
            }
        ]
    }

    proof = build_classical_proof(scene, "Góc giữa AB và AC", "angle_line_line", ["A", "B", "C"], "90°", "90^\\circ")

    assert proof is not None
    assert proof.steps[1].claim == "Góc giữa AB và AC bằng 90°"
    assert proof.used_theorems


def test_classical_proof_derives_normal_section_for_plane_angle():
    scene = {
        "relations": [
            {
                "id": "sa-perp-base",
                "type": "perpendicular",
                "object_1": "SA",
                "object_2": "plane(ABC)",
                "source": "given",
                "verification": {"status": "verified"},
            },
            {
                "id": "ac-perp-ab",
                "type": "perpendicular",
                "object_1": "AC",
                "object_2": "AB",
                "source": "given",
                "verification": {"status": "verified"},
            },
        ]
    }

    proof = build_classical_proof(scene, "Góc giữa (SAB) và (ABC)", "angle_plane_plane", ["S", "A", "B", "C"], "90°", "90^\\circ")

    assert proof is not None
    assert proof.steps[1].title == "Dựng góc phẳng nhị diện"
    assert set(proof.steps[1].depends_on) == {"sa-perp-base", "ac-perp-ab"}