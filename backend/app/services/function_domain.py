from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import sympy as sp


@dataclass(frozen=True)
class DomainComponent:
    start: Any
    end: Any
    left_open: bool
    right_open: bool

    @classmethod
    def from_interval(cls, interval: Any) -> "DomainComponent":
        return cls(interval.start, interval.end, bool(interval.left_open), bool(interval.right_open))


@dataclass(frozen=True)
class PeriodicFamily:
    variable: str
    expression: Any
    parameter: str = "k"
    domain: str = "Z"
    label: str = ""


@dataclass(frozen=True)
class DomainPartition:
    components: tuple[DomainComponent, ...]
    excluded_points: tuple[Any, ...]
    excluded_families: tuple[PeriodicFamily, ...]
    status: str
    warnings: tuple[str, ...] = ()

    def model_payload(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "components": [
                {
                    "start": str(component.start),
                    "end": str(component.end),
                    "left_open": component.left_open,
                    "right_open": component.right_open,
                }
                for component in self.components
            ],
            "excluded_points": [str(point) for point in self.excluded_points],
            "excluded_families": [
                {
                    "variable": family.variable,
                    "expression": str(family.expression),
                    "parameter": family.parameter,
                    "domain": family.domain,
                    "label": family.label,
                }
                for family in self.excluded_families
            ],
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class FunctionDomain:
    set: Any | None
    components: tuple[Any, ...]
    breakpoints: tuple[float, ...]
    partition: DomainPartition | None = None

    @classmethod
    def from_set(cls, domain_set: Any | None) -> "FunctionDomain":
        components = tuple(_interval_components(domain_set))
        breakpoints = tuple(sorted(_finite_interval_bounds(components)))
        partition = build_domain_partition(domain_set, components)
        return cls(domain_set, components, breakpoints, partition)


def build_domain_partition(domain_set: Any | None, components: tuple[Any, ...] | None = None) -> DomainPartition:
    interval_components = tuple(_interval_components(domain_set)) if components is None else components
    excluded_points: list[Any] = []
    excluded_families: list[PeriodicFamily] = []
    warnings: list[str] = []

    if domain_set is None:
        return DomainPartition((), (), (), "unknown", ("Không có tập xác định để phân rã.",))
    if domain_set == sp.S.Reals or interval_components:
        return DomainPartition(tuple(DomainComponent.from_interval(component) for component in interval_components), (), (), "complete")

    try:
        args = getattr(domain_set, "args", ())
        if domain_set.func == sp.Complement and args and args[0] == sp.S.Reals:
            excluded = args[1]
            families = _periodic_families_from_set(excluded)
            if families:
                return DomainPartition((DomainComponent(-sp.oo, sp.oo, True, True),), (), tuple(families), "periodic")
            if isinstance(excluded, sp.FiniteSet):
                excluded_points = list(excluded)
                return DomainPartition((DomainComponent(-sp.oo, sp.oo, True, True),), tuple(excluded_points), (), "complete")
    except (TypeError, ValueError, AttributeError, NotImplementedError):
        pass

    warnings.append("Chưa phân rã được tập xác định thành các miền liên thông hữu hạn.")
    return DomainPartition((), (), (), "unknown", tuple(warnings))


def _periodic_families_from_set(value_set: Any) -> list[PeriodicFamily]:
    families: list[PeriodicFamily] = []
    if isinstance(value_set, sp.ImageSet):
        family = _periodic_family_from_imageset(value_set)
        if family is not None:
            families.append(family)
        return families
    if isinstance(value_set, sp.Union):
        for part in value_set.args:
            if isinstance(part, sp.ImageSet):
                family = _periodic_family_from_imageset(part)
                if family is not None:
                    families.append(family)
    return families


def _periodic_family_from_imageset(value_set: Any) -> PeriodicFamily | None:
    try:
        lam = value_set.lamda
        expr = sp.simplify(lam.expr)
        variables = list(lam.variables)
        if not variables:
            return None
        variable = str(variables[0])
        label = f"{expr}, {variable} ∈ Z"
        return PeriodicFamily(variable=variable, expression=expr, label=label)
    except (TypeError, ValueError, AttributeError, NotImplementedError):
        return None


def _interval_components(domain_set: Any | None) -> list[Any]:
    if domain_set is None:
        return []
    if domain_set == sp.S.Reals:
        return [sp.Interval(-sp.oo, sp.oo)]
    if isinstance(domain_set, sp.Interval):
        return [domain_set]
    if isinstance(domain_set, sp.Union):
        return [part for part in domain_set.args if isinstance(part, sp.Interval)]
    return []


def _finite_interval_bounds(components: tuple[Any, ...]) -> set[float]:
    values: set[float] = set()
    for interval in components:
        for bound in (interval.start, interval.end):
            if getattr(bound, "is_finite", False):
                try:
                    values.add(float(bound.evalf()))
                except (TypeError, ValueError, AttributeError):
                    continue
    return values


def in_domain(domain: FunctionDomain | Any | None, value: Any) -> bool:
    domain_set = domain.set if isinstance(domain, FunctionDomain) else domain
    if domain_set is None:
        return True
    try:
        candidate = sp.sympify(value)
        membership = domain_set.contains(candidate)
        if membership is sp.S.true:
            return True
        if membership is sp.S.false:
            return False
        simplified = sp.simplify(membership)
        if simplified is sp.S.true:
            return True
        if simplified is sp.S.false:
            return False
    except (TypeError, ValueError, AttributeError, NotImplementedError):
        pass
    try:
        numeric = float(sp.N(value))
    except (TypeError, ValueError, AttributeError):
        return False
    for interval in _interval_components(domain_set):
        left_ok = numeric > float(interval.start) if interval.left_open and interval.start.is_finite else True
        if not interval.left_open and interval.start.is_finite:
            left_ok = numeric >= float(interval.start)
        right_ok = numeric < float(interval.end) if interval.right_open and interval.end.is_finite else True
        if not interval.right_open and interval.end.is_finite:
            right_ok = numeric <= float(interval.end)
        if left_ok and right_ok:
            return True
    return False


def filter_domain_values(values: list[Any], domain: FunctionDomain | Any | None) -> list[Any]:
    return [value for value in values if in_domain(domain, value)]


def intersect_domain(value_set: Any, domain: FunctionDomain | Any | None) -> Any:
    domain_set = domain.set if isinstance(domain, FunctionDomain) else domain
    if domain_set is None:
        return value_set
    try:
        return value_set.intersect(domain_set)
    except (TypeError, ValueError, AttributeError, NotImplementedError):
        return value_set


def removable_holes(original_expr: Any, simplified_expr: Any, variable: Any, original_domain: FunctionDomain | Any | None) -> list[dict[str, Any]]:
    domain_set = original_domain.set if isinstance(original_domain, FunctionDomain) else original_domain
    if domain_set is None:
        return []
    try:
        simplified_domain = sp.Interval(-sp.oo, sp.oo).intersect(sp.calculus.util.continuous_domain(simplified_expr, variable, sp.S.Reals))
        missing = simplified_domain - domain_set
    except (TypeError, ValueError, AttributeError, NotImplementedError):
        return []
    if not isinstance(missing, sp.FiniteSet):
        return []
    holes: list[dict[str, Any]] = []
    for point in sorted(missing, key=sp.default_sort_key):
        try:
            y_value = sp.simplify(simplified_expr.subs(variable, point))
            if y_value in (sp.oo, -sp.oo, sp.zoo, sp.nan, sp.S.NaN):
                continue
            holes.append({"x": point, "y": y_value})
        except (TypeError, ValueError, AttributeError, ZeroDivisionError):
            continue
    return holes