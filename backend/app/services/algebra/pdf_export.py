"""Server-side algebra solution PDF (text-focused, matplotlib PdfPages)."""

from __future__ import annotations

import io
import textwrap

import matplotlib

matplotlib.use("Agg")

from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

from app.schemas.algebra import AlgebraSolveResponse


def build_algebra_pdf(response: AlgebraSolveResponse) -> bytes:
    buffer = io.BytesIO()
    lines: list[str] = [
        "Ket qua dai so / Algebra solution",
        f"Status: {response.status}  |  Topic: {response.topic}",
    ]
    if response.request_id:
        lines.append(f"Request ID: {response.request_id}")
    lines.extend([
        "",
        "Input:",
        response.input,
        "",
        "Canonical:",
        response.normalized_input,
        "",
        "Answer:",
        response.answer,
    ])
    if response.answer_latex:
        lines.extend(["", "LaTeX:", response.answer_latex])
    if response.assumptions:
        lines.append("")
        lines.append("Assumptions:")
        lines.extend(f"- {item}" for item in response.assumptions[:20])
    if response.warnings:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"- {item}" for item in response.warnings[:20])
    lines.append("")
    lines.append(f"Verification: {response.verification.status}")
    lines.append("")
    lines.append("Steps:")
    for step in response.steps:
        if step.kind == "conclusion":
            continue
        lines.append(f"{step.index}. {step.title}")
        if step.explanation:
            lines.append(f"   {step.explanation}")
        if step.after_latex:
            lines.append(f"   {step.after_latex}")

    wrapped: list[str] = []
    for line in lines:
        if not line:
            wrapped.append("")
            continue
        wrapped.extend(textwrap.wrap(line, width=95) or [""])

    with PdfPages(buffer) as pdf:
        per_page = 48
        for start in range(0, max(1, len(wrapped)), per_page):
            chunk = wrapped[start : start + per_page]
            fig = plt.figure(figsize=(8.27, 11.69))
            fig.patch.set_facecolor("white")
            ax = fig.add_axes([0.06, 0.05, 0.88, 0.9])
            ax.axis("off")
            y = 0.98
            for line in chunk:
                ax.text(0.0, y, line, transform=ax.transAxes, fontsize=9, family="DejaVu Sans", va="top")
                y -= 0.02
                if y < 0.02:
                    break
            pdf.savefig(fig)
            plt.close(fig)

    return buffer.getvalue()
