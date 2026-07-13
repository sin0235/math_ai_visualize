from app.services.solver_service import solve

SCENE = {
    "problem_text": "Cho hình lập phương ABCD.MNPQ có cạnh bằng 18. M, N, P, Q nằm trên các đường vuông góc với (ABCD) tại A, B, C, D. F là trung điểm CD. Tính khoảng cách từ M đến mặt phẳng (PFB).",
    "topic": "solid_geometry",
    "objects": [
        {"object_id": "point-a", "type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
        {"object_id": "point-b", "type": "point_3d", "name": "B", "x": 18, "y": 0, "z": 0},
        {"object_id": "point-c", "type": "point_3d", "name": "C", "x": 18, "y": 18, "z": 0},
        {"object_id": "point-d", "type": "point_3d", "name": "D", "x": 0, "y": 18, "z": 0},
        {"object_id": "point-m", "type": "point_3d", "name": "M", "x": 0, "y": 0, "z": 18},
        {"object_id": "point-n", "type": "point_3d", "name": "N", "x": 18, "y": 0, "z": 18},
        {"object_id": "point-p", "type": "point_3d", "name": "P", "x": 18, "y": 18, "z": 18},
        {"object_id": "point-q", "type": "point_3d", "name": "Q", "x": 0, "y": 18, "z": 18},
        {"object_id": "point-f", "type": "point_3d", "name": "F", "x": 9, "y": 18, "z": 0},
        {"object_id": "face-abcd", "type": "face", "name": "ABCD", "points": ["A", "B", "C", "D"]},
        {"object_id": "plane-pfb", "type": "plane", "name": "PFB", "points": ["P", "F", "B"]}
    ],
    "relations": [
        {
            "id": "abcd-coplanar",
            "type": "coplanar",
            "operand_names": ["A", "B", "C", "D"],
            "object_1": "A",
            "object_2": "B",
            "metadata": {"source": "given", "confidence": "verified"},
            "verification": {"status": "verified"},
        },
        {
            "id": "ma-perp-abcd",
            "type": "perpendicular",
            "object_1": "MA",
            "object_2": "plane(ABCD)",
            "metadata": {"source": "given", "confidence": "verified"},
            "verification": {"status": "verified"},
        }
    ],
    "annotations": [
        {"id": "len-ab", "type": "length", "target": "A-B", "label": "18", "metadata": {"source": "given", "confidence": "verified"}},
        {"id": "len-ad", "type": "length", "target": "A-D", "label": "18", "metadata": {"source": "given", "confidence": "verified"}},
        {"id": "len-am", "type": "length", "target": "A-M", "label": "18", "metadata": {"source": "given", "confidence": "verified"}}
    ]
}

result = solve(SCENE, "d(M,(PFB))", geometry_method="oxyz")
print(result.__dict__)
