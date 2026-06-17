import sympy as sp
x = sp.Symbol('x', real=True)
dx = sp.Symbol(r'\Delta x', real=True)
expr = (x+dx)**2 - x**2
print(sp.latex(dx))
print(sp.latex(expr))
