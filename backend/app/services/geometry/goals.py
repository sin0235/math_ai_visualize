from __future__ import annotations


def infer_geometry_goal(question: str) -> str:
    text = question.lower()
    markers = {
        "distance": ("khoảng cách", "distance", "d("),
        "angle": ("góc", "angle"),
        "circle_metric": ("hình tròn", "đường tròn", "circle"),
        "quadrilateral_metric": ("hình chữ nhật", "hình vuông", "hình bình hành", "hình thang", "rectangle", "square", "parallelogram", "trapezoid"),
        "area": ("diện tích", "area", "s("),
        "perimeter": ("chu vi", "perimeter", "p("),
        "triangle_congruence": ("bằng nhau", "congruent", "≅", "≡"),
        "triangle_similarity": ("đồng dạng", "similar", "∼"),
        "pythagoras": ("pythagor", "pi-ta-go", "tính cạnh", "tìm cạnh", "calculate side", "find side"),
        "volume": ("thể tích", "volume", "v("),
        "equation": ("phương trình", "equation", "pt "),
        "projection": ("hình chiếu", "projection"),
        "reflection": ("đối xứng", "reflection"),
        "intersection": ("giao điểm", "giao tuyến", "intersection"),
        "vector": ("vector", "vectơ", " dot(", "cross(", " × ", " . "),
        "proof": ("chứng minh", "song song", "vuông góc", "parallel", "perpendicular"),
        "relation": ("thẳng hàng", "đồng phẳng", "collinear", "coplanar"),
    }
    return next((task for task, terms in markers.items() if any(term in text for term in terms)), "unknown")