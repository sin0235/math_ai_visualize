import sympy as sp

from app.services.algebra.parser import parse_algebra_problem
from app.services.algebra.verifier import verify_finite_solutions


def test_verifier_accepts_correct_candidate():
    problem = parse_algebra_problem("x^2 - 5*x + 6 = 0")
    report = verify_finite_solutions(problem, [sp.Integer(2), sp.Integer(3)])

    assert report.status == "verified"
    assert all(check.status == "pass" for check in report.checks)


def test_verifier_rejects_wrong_candidate():
    problem = parse_algebra_problem("x^2 - 5*x + 6 = 0")
    report = verify_finite_solutions(problem, [sp.Integer(4)])

    assert report.status == "failed"
    assert report.checks[0].status == "fail"
