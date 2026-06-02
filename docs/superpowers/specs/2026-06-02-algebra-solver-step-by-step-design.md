# Algebra Solver Step-by-Step Teaching Design

Date: 2026-06-02

## Goal

Upgrade `/algebra-solver` so it teaches students how to solve one-variable equations and inequalities, not just returns an answer. The first implementation scope is:

- One-variable equations.
- One-variable inequalities.
- Existing answer verification must remain the source of truth.
- Other algebra topics keep their current behavior unless they can reuse the new display safely.

## Problem

The current solver response has basic step fields: title, explanation, expression, result, kind, and confidence. This is enough to show a calculation trail, but not enough for learning. Students need to see:

- What the step is trying to achieve.
- Why this transformation is valid.
- Which rule or theorem is being used.
- What changed from the previous line to the next line.
- Which conditions must be kept.
- How to check the result.
- What common mistake to avoid.

AI explanation currently rewrites only title and explanation. It should not be the core learning layer because it is harder to test and can over-explain beyond the verified symbolic result.

## Recommended Approach

Add a deterministic teaching layer to the algebra solver, then render that structure in the UI. AI explanation can remain optional, but only as a style rewrite over safe fields.

This approach is preferred because it is testable, predictable, and keeps SymPy plus the verifier as the correctness boundary.

## Backend Design

Extend `AlgebraSolveStep` with optional learning fields:

- `goal`: What this step is trying to accomplish.
- `why`: Why this step is needed or valid.
- `rule`: The rule, theorem, or method being applied.
- `operation`: The concrete algebraic action taken.
- `before_latex`: The expression before the action.
- `after_latex`: The expression after the action.
- `pitfall`: A common mistake to avoid.
- `check`: A short self-check for the student.

Keep existing fields for backward compatibility:

- `title`
- `explanation`
- `expression`
- `expression_latex`
- `result`
- `result_latex`
- `kind`
- `confidence`

Create helper constructors in `backend/app/services/algebra/steps.py` so solver modules do not duplicate teaching text. Suggested helpers:

- `normalize_step`
- `domain_step`
- `transform_step`
- `rule_step`
- `solution_step`
- `verification_step`
- `conclusion_step`

For equations, add richer steps for:

- Normalization into a canonical equation.
- Domain restrictions from denominators, radicals, logs, or other detected constraints.
- Moving all terms to one side.
- Quadratic form and discriminant.
- Formula substitution with coefficients shown.
- Radicals and extraneous solution filtering.
- Empty solution sets.
- Verification by substitution for finite solutions.

For inequalities, add richer steps for:

- Normalization into a relation.
- Domain restrictions.
- Critical points.
- Sign chart or interval reasoning.
- Interval selection based on the inequality sign.
- Verification with representative sample values where available.

## AI Explanation Boundaries

If `options.ai_explanation` is enabled, AI may rewrite only human-language learning fields:

- `title`
- `explanation`
- `goal`
- `why`
- `rule`
- `operation`
- `pitfall`
- `check`

AI must not modify:

- `expression`
- `expression_latex`
- `result`
- `result_latex`
- `before_latex`
- `after_latex`
- `answer`
- `answer_latex`
- `solution_set`
- `verification`

If verification is not `verified` or `partially_verified`, skip AI explanation and keep deterministic wording.

## Frontend Design

Update the algebra step timeline to prioritize learning fields.

Each step card should show:

- Step number and title.
- Goal.
- Why this step is valid.
- Formula or before/after expression when present.
- Result.
- Rule badge if present.
- Pitfall and check notes when present.

The answer card stays visible, but the step-by-step section should become the main learning surface. The layout should remain compact and readable on mobile.

For older responses without the new fields, the UI falls back to the existing title, explanation, expression, and result fields.

## Data Flow

1. User submits an algebra problem from `/algebra-solver`.
2. Backend interprets and parses the input.
3. Deterministic solver computes the result.
4. Deterministic teaching layer adds structured learning fields.
5. Verifier checks finite solutions or symbolic set consistency.
6. Optional AI explanation rewrites only safe language fields.
7. Frontend renders a teaching timeline.

## Error Handling

- Unsupported topics keep the current unsupported response.
- Parse errors keep the current error response, with user-facing warnings.
- If AI explanation fails, keep deterministic steps and add a warning.
- If verification fails, mark the response as error or partial according to existing behavior and avoid confident teaching language.

## Testing

Backend tests should assert that one-variable equation and inequality responses include learning fields, not only answers.

Required focused tests:

- Quadratic equation includes goal, rule, why, coefficient substitution, and check.
- Equation with denominator includes domain explanation and pitfall.
- Radical equation includes extraneous-solution filtering explanation.
- Empty solution set includes a clear reason.
- Inequality includes interval/sign-chart reasoning.
- AI explanation cannot alter formula/result fields.

Frontend tests are optional if the project lacks a frontend test setup. At minimum, run the existing build and verify TypeScript types.

## Out Of Scope

- Full teaching templates for sequence, combinatorics, complex numbers, systems, and parameter problems.
- Replacing SymPy with another CAS.
- Free-form AI solving.
- Multi-turn tutoring or student quiz mode.

## Acceptance Criteria

- `/algebra-solver` returns richer step-by-step learning data for equations and inequalities.
- Existing consumers of `AlgebraSolveStep` still work.
- UI displays goal, why, rule, operation, pitfall, and check when present.
- Solver correctness remains tied to symbolic solving and verification.
- Existing algebra tests still pass, with new tests covering the teaching fields.
