from fractions import Fraction
import pytest
from app.services.algebra.solvers.sequence_solver import _evaluate

def test_arithmetic_u2():
    calc = _evaluate("arithmetic(u1=2,u2=4,n=9)")
    assert calc.result == 18

def test_arithmetic_sum_u2():
    calc = _evaluate("arithmetic_sum(u1=2,u2=4,n=9)")
    assert calc.result == 90

def test_geometric_u2():
    calc = _evaluate("geometric(u1=2,u2=4,n=9)")
    assert calc.result == 512
