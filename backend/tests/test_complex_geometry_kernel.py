from app.services.solver_service import solve

SCENE = {
    "problem_text": "Cho hình chóp S.ABCD có đáy ABCD là hình thoi tâm O cạnh bằng 12, góc BAD = 60 độ. SO vuông góc với đáy, SO = 8. M là trung điểm SB, N thuộc SD sao cho SN = 2ND. Tính góc giữa đường thẳng AM và mặt phẳng (SCD).",
    "topic": "solid_geometry",
    "objects": [
        {"object_id": "point-o", "type": "point_3d", "name": "O", "x": 0, "y": 0, "z": 0},
        {"object_id": "point-a", "type": "point_3d", "name": "A", "x": 0, "y": -10.3923048, "z": 0},
        {"object_id": "point-c", "type": "point_3d", "name": "C", "x": 0, "y": 10.3923048, "z": 0},
        {"object_id": "point-b", "type": "point_3d", "name": "B", "x": 6, "y": 0, "z": 0},
        {"object_id": "point-d", "type": "point_3d", "name": "D", "x": -6, "y": 0, "z": 0},
        {"object_id": "point-s", "type": "point_3d", "name": "S", "x": 0, "y": 0, "z": 8},
        {"object_id": "point-m", "type": "point_3d", "name": "M", "x": 3, "y": 0, "z": 4},
        {"object_id": "point-n", "type": "point_3d", "name": "N", "x": -4, "y": 0, "z": 2.6666667},
        {"object_id": "face-abcd", "type": "face", "name": "ABCD", "points": ["A", "B", "C", "D"]},
        {"object_id": "plane-scd", "type": "plane", "name": "SCD", "points": ["S", "C", "D"]}
    ],
    "relations": [
        {
            "id": "so-perp-abcd",
            "type": "perpendicular",
            "object_1": "SO",
            "object_2": "plane(ABCD)",
            "metadata": {"source": "given", "confidence": "verified"},
            "verification": {"status": "verified"}
        }
    ],
    "annotations": [
        {"id": "len-so", "type": "length", "target": "S-O", "label": "8", "metadata": {"source": "given", "confidence": "verified"}},
        {"id": "len-ab", "type": "length", "target": "A-B", "label": "12", "metadata": {"source": "given", "confidence": "verified"}},
        {"id": "ang-bad", "type": "angle", "target": "A", "metadata": {"arms": ["B", "D"], "value": 60, "source": "given", "confidence": "verified"}}
    ]
}

result_distance = solve(SCENE, "d(A,(SBC))", geometry_method="oxyz")
print("Distance A to (SBC):", result_distance.answer)

result_angle = solve(SCENE, "\\angle(AM,plane(SCD))", geometry_method="oxyz")
print("Angle AM to (SCD):", result_angle.answer)
