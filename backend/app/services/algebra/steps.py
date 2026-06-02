from __future__ import annotations

import sympy as sp

from app.schemas.algebra import AlgebraSolveStep
from app.services.algebra.parser import ParsedAlgebraProblem


def normalize_step(problem: ParsedAlgebraProblem) -> AlgebraSolveStep:
    expression_latex = sp.latex(problem.relation) if problem.relation is not None else sp.latex(problem.expression)
    return AlgebraSolveStep(
        index=1,
        title="Chuẩn hóa đề bài",
        explanation="Đưa đề bài về một dạng thống nhất để các bước sau đều làm việc trên cùng một biểu thức.",
        goal="Đọc đúng đề và viết lại bài toán dưới dạng đại số chuẩn.",
        why="Nếu chưa chuẩn hóa, các ký hiệu khác nhau có thể làm solver hiểu sai phép toán hoặc quan hệ cần giải.",
        rule="Chuẩn hóa ký hiệu",
        operation="Giữ nguyên ý nghĩa đề bài, đổi ký hiệu nhập vào thành dạng symbolic.",
        before_latex=None,
        after_latex=expression_latex,
        pitfall="Không được đổi dấu hoặc tự thêm điều kiện trong bước chuẩn hóa; bước này chỉ đổi cách viết.",
        check="Biểu thức chuẩn phải vẫn biểu diễn đúng đề ban đầu.",
        expression=problem.normalized_input,
        expression_latex=expression_latex,
        kind="normalize",
        confidence="symbolic",
    )


def domain_step(index: int, assumptions: list[str]) -> AlgebraSolveStep:
    has_assumptions = bool(assumptions)
    return AlgebraSolveStep(
        index=index,
        title="Điều kiện xác định",
        explanation="; ".join(assumptions) if has_assumptions else "Chưa phát hiện điều kiện loại trừ đặc biệt trong phạm vi solver hiện tại.",
        goal="Xác định những giá trị biến được phép dùng trước khi biến đổi.",
        why="Nghiệm cuối cùng chỉ hợp lệ nếu thỏa điều kiện xác định của biểu thức gốc.",
        rule="Điều kiện xác định",
        operation="Ghi lại các điều kiện từ mẫu số, căn chẵn, logarit hoặc ràng buộc miền nghiệm.",
        pitfall="Không được bỏ qua điều kiện này khi kết luận; nhiều nghiệm ngoại lai xuất hiện vì quên kiểm tra điều kiện.",
        check="Mỗi nghiệm tìm được ở cuối bài phải được đối chiếu với các điều kiện trên." if has_assumptions else "Nếu không có mẫu số, căn chẵn hoặc logarit theo biến, ta có thể tiếp tục với miền đã chọn.",
        kind="domain",
        confidence="symbolic",
    )


def conclusion_step(index: int, answer: str, answer_latex: str | None) -> AlgebraSolveStep:
    return AlgebraSolveStep(
        index=index,
        title="Kết luận",
        explanation=answer,
        goal="Viết tập nghiệm cuối cùng sau khi đã giải và kiểm tra.",
        why="Kết luận phải tổng hợp đúng nghiệm hợp lệ, không chỉ là kết quả trung gian.",
        rule="Kết luận tập nghiệm",
        operation="Ghi nghiệm hoặc khoảng nghiệm theo ký hiệu tập nghiệm.",
        after_latex=answer_latex,
        check="So sánh kết luận với điều kiện xác định và báo cáo kiểm chứng.",
        result=answer,
        result_latex=answer_latex,
        kind="conclusion",
        confidence="verified",
    )
