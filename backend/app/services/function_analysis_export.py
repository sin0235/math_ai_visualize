from __future__ import annotations

import io
import json
import textwrap
from typing import Any

from app.schemas.analyzer_history import (
    AnalyzerExportDocument,
    AnalyzerExportSection,
    CurriculumProfile,
)
from app.services.function_analysis_curriculum import build_curriculum_presentation


def build_analyzer_export_document(
    result: dict[str, Any],
    *,
    engine_version: str,
    template: str,
    profile: CurriculumProfile,
) -> AnalyzerExportDocument:
    presentation = build_curriculum_presentation(profile, result)
    sections = [
        AnalyzerExportSection(
            key=str(step.get("key", "unknown")),
            title=str(step.get("title", "Bước phân tích")),
            status=str(step.get("status", "unknown")),
            formula_latex=step.get("formula_latex"),
            evidence=[str(item) for item in step.get("evidence", [])],
            warnings=[str(item) for item in step.get("warnings", [])],
        )
        for step in result.get("analysis_steps", [])
        if isinstance(step, dict)
    ]
    if template == "student_worksheet":
        sections = [section.model_copy(update={"evidence": []}) for section in sections]
    return AnalyzerExportDocument(
        template=template,
        title=_title(template),
        expression=str(result.get("expression", "")),
        expression_latex=result.get("expression_latex"),
        engine_version=engine_version,
        verification=result.get("verification") or {"status": "unverified"},
        exact_approx_metadata=_collect_exact_approx(result),
        curriculum=presentation,
        sections=sections,
        warnings=[str(item) for item in result.get("warnings", [])],
    )


def render_analyzer_export(document: AnalyzerExportDocument, fmt: str) -> tuple[bytes, str, str]:
    if fmt == "json":
        return document.model_dump_json(indent=2).encode("utf-8"), "application/json", "function-analysis.json"
    if fmt == "latex":
        return _latex(document).encode("utf-8"), "application/x-tex", "function-analysis.tex"
    if fmt == "pdf":
        return _pdf(document), "application/pdf", "function-analysis.pdf"
    return _markdown(document).encode("utf-8"), "text/markdown; charset=utf-8", "function-analysis.md"


def _markdown(document: AnalyzerExportDocument) -> str:
    lines = [f"# {document.title}", "", f"**Hàm số:** `{document.expression}`", f"**Engine:** `{document.engine_version}`", f"**Kiểm chứng:** `{document.verification.get('status', 'unverified')}`", ""]
    for section in document.sections:
        lines.extend([f"## {section.title}", f"Trạng thái: `{section.status}`"])
        if section.formula_latex:
            lines.extend(["", f"$${section.formula_latex}$$"])
        lines.extend(f"- {item}" for item in section.evidence)
        lines.extend(f"- Cảnh báo: {item}" for item in section.warnings)
        lines.append("")
    if document.curriculum.common_mistakes:
        lines.extend(["## Lỗi thường gặp", *[f"- {item}" for item in document.curriculum.common_mistakes], ""])
    if document.curriculum.predicted_questions:
        lines.extend(["## Câu hỏi dự đoán", *[f"- {item}" for item in document.curriculum.predicted_questions], ""])
    lines.extend(["## Cảnh báo", *([f"- {item}" for item in document.warnings] or ["- Không có."])])
    return "\n".join(lines) + "\n"


def _latex(document: AnalyzerExportDocument) -> str:
    body = [r"\documentclass[12pt]{article}", r"\usepackage[utf8]{inputenc}", r"\usepackage{amsmath}", r"\begin{document}", rf"\section*{{{_tex(document.title)}}}", rf"\textbf{{Expression:}} \texttt{{{_tex(document.expression)}}}\\", rf"\textbf{{Verification:}} {_tex(str(document.verification.get('status', 'unverified')))}"]
    for section in document.sections:
        body.append(rf"\subsection*{{{_tex(section.title)}}}")
        body.append(rf"Status: {_tex(section.status)}\\")
        if section.formula_latex:
            body.append(rf"\[{section.formula_latex}\]")
        if section.evidence or section.warnings:
            body.append(r"\begin{itemize}")
            body.extend(rf"\item {_tex(item)}" for item in section.evidence)
            body.extend(rf"\item Warning: {_tex(item)}" for item in section.warnings)
            body.append(r"\end{itemize}")
    body.extend([r"\section*{Warnings}", r"\begin{itemize}"])
    body.extend(rf"\item {_tex(item)}" for item in (document.warnings or ["None"]))
    body.extend([r"\end{itemize}", r"\end{document}"])
    return "\n".join(body) + "\n"


def _pdf(document: AnalyzerExportDocument) -> bytes:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    lines = _markdown(document).replace("`", "").replace("#", "").splitlines()
    wrapped = [part for line in lines for part in (textwrap.wrap(line, width=95) or [""])]
    buffer = io.BytesIO()
    with PdfPages(buffer) as pdf:
        for start in range(0, max(1, len(wrapped)), 48):
            fig = plt.figure(figsize=(8.27, 11.69))
            ax = fig.add_axes([0.06, 0.05, 0.88, 0.9])
            ax.axis("off")
            for index, line in enumerate(wrapped[start:start + 48]):
                ax.text(0, 0.98 - index * 0.02, line, transform=ax.transAxes, fontsize=9, family="DejaVu Sans", va="top")
            pdf.savefig(fig)
            plt.close(fig)
    return buffer.getvalue()


def _collect_exact_approx(value: Any, path: str = "result") -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if "exact" in value and ("approx" in value or "method" in value):
            found.append({"path": path, **{key: value.get(key) for key in ("exact", "latex", "approx", "precision", "method") if key in value}})
        for key, child in value.items():
            found.extend(_collect_exact_approx(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_collect_exact_approx(child, f"{path}[{index}]"))
    return found[:500]


def _title(template: str) -> str:
    return {"teacher_report": "Báo cáo khảo sát hàm số", "student_worksheet": "Phiếu bài tập khảo sát hàm số"}.get(template, "Kết quả khảo sát hàm số")


def _tex(value: str) -> str:
    return value.replace("\\", r"\textbackslash{}").replace("&", r"\&").replace("%", r"\%").replace("$", r"\$").replace("#", r"\#").replace("_", r"\_").replace("{", r"\{").replace("}", r"\}")