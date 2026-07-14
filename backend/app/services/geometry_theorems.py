from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class PremiseSpec:
    fact_type: str
    min_count: int = 1


@dataclass(frozen=True)
class TheoremSpec:
    theorem_id: str
    name: str
    statement: str
    grade: int
    cost: int = 1
    premises: tuple[PremiseSpec, ...] = ()
    conclusion: str = ""
    construction: tuple[str, ...] = ()


THEOREMS: dict[str, TheoremSpec] = {
    item.theorem_id: item
    for item in (
        TheoremSpec(
            "distance.point_plane.perpendicular_segment",
            "Khoảng cách từ điểm đến mặt phẳng",
            "Khoảng cách từ điểm đến mặt phẳng là độ dài đoạn vuông góc kẻ từ điểm đó đến mặt phẳng.",
            11,
        ),
        TheoremSpec(
            "distance.point_point.segment_length",
            "Khoảng cách giữa hai điểm",
            "Khoảng cách giữa hai điểm bằng độ dài đoạn thẳng nối hai điểm đó.",
            6,
        ),
        TheoremSpec(
            "distance.point_line.perpendicular_segment",
            "Khoảng cách từ điểm đến đường thẳng",
            "Khoảng cách từ một điểm đến đường thẳng là độ dài đoạn vuông góc kẻ từ điểm đó đến đường thẳng.",
            10,
        ),
        TheoremSpec(
            "perpendicular.line_plane.implies_line",
            "Đường vuông góc với mặt phẳng",
            "Đường thẳng vuông góc với mặt phẳng thì vuông góc với mọi đường trong mặt phẳng đi qua chân đường vuông góc.",
            11,
        ),
        TheoremSpec(
            "construction.point_on_plane.affine_combination",
            "Điểm thuộc mặt phẳng theo tổ hợp affine",
            "Một điểm biểu diễn được từ một điểm gốc cộng tổ hợp tuyến tính của hai phương không song song trong mặt phẳng thì thuộc mặt phẳng đó.",
            11,
            cost=2,
        ),
        TheoremSpec(
            "relation.perpendicular.orthogonal_frame_dot",
            "Tiêu chuẩn tích vô hướng bằng không",
            "Trong một hệ phương đôi một vuông góc đã kiểm chứng, hai vector có tích vô hướng bằng không thì hai đường mang chúng vuông góc.",
            10,
            cost=2,
        ),
        TheoremSpec(
            "perpendicular.line_plane.two_intersecting_lines",
            "Đường thẳng vuông góc với mặt phẳng",
            "Đường thẳng vuông góc với hai đường thẳng cắt nhau nằm trong một mặt phẳng thì vuông góc với mặt phẳng đó.",
            11,
            cost=2,
        ),
        TheoremSpec(
            "metric.orthogonal_frame.segment_length",
            "Độ dài trong ba phương đôi một vuông góc",
            "Bình phương độ dài một đoạn bằng tổng bình phương ba thành phần theo ba phương đôi một vuông góc.",
            10,
            cost=2,
        ),
        TheoremSpec(
            "angle.line_line.perpendicular",
            "Góc giữa hai đường vuông góc",
            "Hai đường thẳng vuông góc tạo với nhau một góc 90°.",
            10,
        ),
        TheoremSpec(
            "angle.line_plane.projection",
            "Góc giữa đường thẳng và mặt phẳng",
            "Góc giữa đường thẳng và mặt phẳng là góc giữa đường thẳng đó và hình chiếu của nó trên mặt phẳng.",
            11,
        ),
        TheoremSpec(
            "angle.line_plane.perpendicular",
            "Góc của đường vuông góc với mặt phẳng",
            "Đường thẳng vuông góc với mặt phẳng thì góc giữa đường thẳng và mặt phẳng bằng 90°.",
            11,
        ),
        TheoremSpec(
            "angle.plane_plane.normal_section",
            "Góc phẳng nhị diện",
            "Góc giữa hai mặt phẳng là góc giữa hai đường lần lượt nằm trong mỗi mặt phẳng và cùng vuông góc với giao tuyến tại một điểm.",
            11,
        ),
        TheoremSpec(
            "quadrilateral.metric.direct_formula",
            "Công thức metric tứ giác",
            "Diện tích và chu vi tứ giác đặc biệt được tính từ các kích thước exact theo công thức tương ứng.",
            8,
        ),
        TheoremSpec(
            "circle.metric.direct_formula",
            "Công thức metric đường tròn",
            "Chu vi đường tròn bằng 2πr và diện tích hình tròn bằng πr².",
            9,
        ),
        TheoremSpec(
            "triangle.congruence.sss",
            "Trường hợp bằng nhau cạnh-cạnh-cạnh",
            "Hai tam giác có ba cặp cạnh tương ứng bằng nhau thì bằng nhau.",
            7,
        ),
        TheoremSpec(
            "triangle.similarity.aa",
            "Trường hợp đồng dạng góc-góc",
            "Hai tam giác có hai cặp góc tương ứng bằng nhau thì đồng dạng.",
            8,
        ),
        TheoremSpec(
            "triangle.pythagoras.length",
            "Định lý Pythagore",
            "Trong tam giác vuông, bình phương cạnh huyền bằng tổng bình phương hai cạnh góc vuông.",
            8,
        ),
        TheoremSpec(
            "area.triangle.perpendicular_sides",
            "Diện tích tam giác vuông",
            "Diện tích tam giác vuông bằng một nửa tích độ dài hai cạnh góc vuông.",
            10,
        ),
        TheoremSpec(
            "volume.pyramid.base_height",
            "Thể tích khối chóp",
            "Thể tích khối chóp bằng một phần ba diện tích đáy nhân với chiều cao.",
            11,
        ),
        TheoremSpec(
            "incidence.intersection.given",
            "Giao điểm đã xác định",
            "Điểm cùng thuộc hai đối tượng cắt nhau là giao điểm của hai đối tượng đó.",
            10,
        ),
        TheoremSpec(
            "relation.parallel.given",
            "Quan hệ song song đã kiểm chứng",
            "Hai đường thẳng có quan hệ song song đã được kiểm chứng thì kết luận chúng song song.",
            10,
        ),
        TheoremSpec(
            "relation.collinear.given",
            "Quan hệ thẳng hàng đã kiểm chứng",
            "Các điểm cùng thuộc một đường thẳng thì thẳng hàng.",
            10,
        ),
        TheoremSpec(
            "relation.coplanar.given",
            "Quan hệ đồng phẳng đã kiểm chứng",
            "Các điểm cùng thuộc một mặt phẳng thì đồng phẳng.",
            10,
        ),
        TheoremSpec(
            "volume.prism.base_height",
            "Thể tích khối lăng trụ",
            "Thể tích khối lăng trụ bằng diện tích đáy nhân với chiều cao.",
            11,
        ),
    )
}


_THEOREM_CONTRACTS: dict[str, dict[str, object]] = {
    "distance.point_plane.perpendicular_segment": {
        "premises": (PremiseSpec("perpendicular_line_plane"),),
        "conclusion": "distance_equals_perpendicular_segment",
        "construction": ("project_point",),
    },
    "distance.point_point.segment_length": {
        "premises": (PremiseSpec("length"),),
        "conclusion": "distance_equals_segment_length",
    },
    "distance.point_line.perpendicular_segment": {
        "premises": (PremiseSpec("perpendicular_lines|perpendicular_line_plane"),),
        "conclusion": "distance_equals_perpendicular_segment",
        "construction": ("project_point",),
    },
    "perpendicular.line_plane.implies_line": {
        "premises": (PremiseSpec("perpendicular_line_plane"), PremiseSpec("point_on_plane")),
        "conclusion": "perpendicular_lines",
    },
    "construction.point_on_plane.affine_combination": {
        "premises": (PremiseSpec("orthogonal_frame|derived_orthogonal_frame"),),
        "conclusion": "point_on_plane",
        "construction": ("add_point", "connect_points"),
    },
    "relation.perpendicular.orthogonal_frame_dot": {
        "premises": (PremiseSpec("orthogonal_frame|derived_orthogonal_frame"),),
        "conclusion": "perpendicular_lines",
    },
    "perpendicular.line_plane.two_intersecting_lines": {
        "premises": (PremiseSpec("perpendicular_lines", 2), PremiseSpec("point_on_plane")),
        "conclusion": "perpendicular_line_plane",
    },
    "metric.orthogonal_frame.segment_length": {
        "premises": (PremiseSpec("orthogonal_frame|derived_orthogonal_frame"),),
        "conclusion": "segment_length",
    },
    "angle.line_line.perpendicular": {
        "premises": (PremiseSpec("perpendicular_lines"),),
        "conclusion": "angle_measure_90",
    },
    "angle.line_plane.projection": {
        "premises": (PremiseSpec("perpendicular_line_plane"),),
        "conclusion": "line_plane_angle_equals_projection_angle",
        "construction": ("project_point", "connect_points"),
    },
    "angle.line_plane.perpendicular": {
        "premises": (PremiseSpec("perpendicular_line_plane"),),
        "conclusion": "line_plane_angle_90",
    },
    "angle.plane_plane.normal_section": {
        "premises": (PremiseSpec("perpendicular_lines|perpendicular_line_plane", 2),),
        "conclusion": "plane_angle_equals_normal_section_angle",
        "construction": ("add_auxiliary_line",),
    },
    "quadrilateral.metric.direct_formula": {
        "premises": (PremiseSpec("scalar_measure"),),
        "conclusion": "quadrilateral_metric",
    },
    "circle.metric.direct_formula": {
        "premises": (PremiseSpec("scalar_measure"),),
        "conclusion": "circle_metric",
    },
    "triangle.congruence.sss": {
        "premises": (PremiseSpec("equal_length", 3),),
        "conclusion": "triangle_congruence",
    },
    "triangle.similarity.aa": {
        "premises": (PremiseSpec("angle_measure", 2),),
        "conclusion": "triangle_similarity",
    },
    "triangle.pythagoras.length": {
        "premises": (PremiseSpec("right_angle|perpendicular_lines"), PremiseSpec("length", 2)),
        "conclusion": "triangle_side_length",
    },
    "area.triangle.perpendicular_sides": {
        "premises": (PremiseSpec("perpendicular_lines"), PremiseSpec("length", 2)),
        "conclusion": "triangle_area",
    },
    "volume.pyramid.base_height": {
        "premises": (PremiseSpec("perpendicular_line_plane"),),
        "conclusion": "pyramid_volume",
    },
    "incidence.intersection.given": {
        "premises": (PremiseSpec("intersection"),),
        "conclusion": "intersection",
    },
    "relation.parallel.given": {
        "premises": (PremiseSpec("parallel_lines"),),
        "conclusion": "parallel_lines",
    },
    "relation.collinear.given": {
        "premises": (PremiseSpec("collinear"),),
        "conclusion": "collinear",
    },
    "relation.coplanar.given": {
        "premises": (PremiseSpec("coplanar|plane_points"),),
        "conclusion": "coplanar",
    },
    "volume.prism.base_height": {
        "premises": (PremiseSpec("perpendicular_line_plane"),),
        "conclusion": "prism_volume",
    },
}

THEOREMS = {
    theorem_id: replace(spec, **_THEOREM_CONTRACTS[theorem_id])
    for theorem_id, spec in THEOREMS.items()
}


def theorem(theorem_id: str) -> TheoremSpec:
    return THEOREMS[theorem_id]
