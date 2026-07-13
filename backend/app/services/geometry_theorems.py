from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TheoremSpec:
    theorem_id: str
    name: str
    statement: str
    grade: int
    cost: int = 1


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
            "volume.prism.base_height",
            "Thể tích khối lăng trụ",
            "Thể tích khối lăng trụ bằng diện tích đáy nhân với chiều cao.",
            11,
        ),
    )
}


def theorem(theorem_id: str) -> TheoremSpec:
    return THEOREMS[theorem_id]