import pytest
from app.schemas.algebra import AlgebraSolveRequest
from app.services.algebra.interpreter import interpret_algebra_input

def test_interpret_inequality():
    req = AlgebraSolveRequest(input="giải bpt x^2 - 4 > 0")
    interpretation = interpret_algebra_input(req)
    assert interpretation.topic_hint == "inequality"
    assert interpretation.canonical_input == "x^2-4>0"

def test_interpret_exponential():
    req = AlgebraSolveRequest(input="2^{x-1} = 8")
    interpretation = interpret_algebra_input(req)
    assert interpretation.topic_hint == "exponential_log"
    assert interpretation.canonical_input == "2^{x-1}=8"

def test_interpret_exponential_asterisk():
    req = AlgebraSolveRequest(input="2**(x-1) = 8")
    interpretation = interpret_algebra_input(req)
    assert interpretation.topic_hint == "exponential_log"
    assert interpretation.canonical_input == "2**(x-1)=8"

def test_interpret_trigonometry():
    req = AlgebraSolveRequest(input="arcsin(x) = pi/6")
    interpretation = interpret_algebra_input(req)
    assert interpretation.topic_hint == "trigonometry"
    assert interpretation.canonical_input == "arcsin(x)=pi/6"

def test_interpret_combinatorics_probability():
    req = AlgebraSolveRequest(input="hoán vị của 5")
    interpretation = interpret_algebra_input(req)
    assert interpretation.topic_hint == "combinatorics_probability"
    assert interpretation.canonical_input == "5!"

def test_interpret_parameter():
    req = AlgebraSolveRequest(input="tìm m để phương trình x^2 - 2mx + m^2 - 1 = 0 có 2 nghiệm phân biệt")
    interpretation = interpret_algebra_input(req)
    assert interpretation.topic_hint == "parameter"
    assert interpretation.canonical_input == "quadratic_has_two_roots(a=1,b=-2*m,c=+m^2-1,var=x,param=m)"

def test_interpret_combinatorics_structured():
    req = AlgebraSolveRequest(input="tổ hợp chập 3 của 5")
    interpretation = interpret_algebra_input(req)
    assert interpretation.topic_hint == "combinatorics_probability"
    assert interpretation.canonical_input == "C(5,3)"

def test_interpret_sequence():
    req = AlgebraSolveRequest(input="dãy số u1 = 2, q = 3, n = 5")
    interpretation = interpret_algebra_input(req)
    assert interpretation.topic_hint == "sequence"
    assert interpretation.canonical_input == "geometric(u1=2,q=3,n=5)"
