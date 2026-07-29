"""Parameter Search Space definitions for strategy optimization."""

from __future__ import annotations
from dataclasses import dataclass, field
import itertools
from typing import Any, Sequence


@dataclass
class ParamRange:
    """Base parameter range contract."""
    name: str

    def get_values(self) -> list[Any]:
        raise NotImplementedError


@dataclass
class IntParam(ParamRange):
    """Integer parameter range [start, stop, step]."""
    start: int
    stop: int
    step: int = 1

    def get_values(self) -> list[int]:
        return list(range(self.start, self.stop + 1, self.step))


@dataclass
class FloatParam(ParamRange):
    """Float parameter range [start, stop, num_steps]."""
    start: float
    stop: float
    num_steps: int = 10

    def get_values(self) -> list[float]:
        if self.num_steps <= 1:
            return [self.start]
        step = (self.stop - self.start) / (self.num_steps - 1)
        return [round(self.start + i * step, 6) for i in range(self.num_steps)]


@dataclass
class ChoiceParam(ParamRange):
    """Categorical choice parameter range."""
    choices: list[Any]

    def get_values(self) -> list[Any]:
        return list(self.choices)


@dataclass
class ParameterSpace:
    """Container for strategy parameter search grid."""
    params: list[ParamRange] = field(default_factory=list)

    def add(self, param: ParamRange) -> ParameterSpace:
        self.params.append(param)
        return self

    def generate_grid(self) -> list[dict[str, Any]]:
        """Generate full Cartesian product grid of parameter combinations."""
        if not self.params:
            return [{}]
        names = [p.name for p in self.params]
        value_lists = [p.get_values() for p in self.params]
        
        combinations = list(itertools.product(*value_lists))
        return [dict(zip(names, combo)) for combo in combinations]
