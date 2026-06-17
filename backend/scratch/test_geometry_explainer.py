import asyncio
from app.db.session import get_database
from app.services.solver_service import SolverResult, SolverStep
from app.services.solver_explainer import explain_solver_result
from app.core.config import get_settings

async def main():
    settings = get_settings()
    result = SolverResult(
        question="Tính khoảng cách từ S đến (ABC)",
        answer="4",
        steps=[
            SolverStep(
                index=1,
                title="Dữ liệu điểm",
                explanation="S(0, 0, 4), A(0, 3, 0), B(4, 0, 0), C(0, 0, 0)",
                expression=None,
                result=None,
                highlight=["S", "A", "B", "C"],
            ),
            SolverStep(
                index=2,
                title="Tính khoảng cách",
                explanation="Khoảng cách từ S đến mặt phẳng (ABC) là 4",
                expression="4",
                result="4",
                highlight=[],
                formula_latex=r"d(S, (ABC)) = \frac{|Ax_S + By_S + Cz_S + D|}{\sqrt{A^2 + B^2 + C^2}}",
                substitution_latex=r"d(S, (ABC)) = \frac{|0 + 0 + 4 - 0|}{\sqrt{0^2 + 0^2 + 1^2}}",
                result_latex="4",
            )
        ],
        warnings=[]
    )
    scene = {
        "objects": [
            {"type": "point_3d", "name": "S", "x": 0, "y": 0, "z": 4},
            {"type": "point_3d", "name": "A", "x": 0, "y": 3, "z": 0},
            {"type": "point_3d", "name": "B", "x": 4, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 0, "y": 0, "z": 0},
        ]
    }
    
    explained = await explain_solver_result(result, scene, settings)
    import json
    print(json.dumps(explained.to_dict(), indent=2, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(main())
