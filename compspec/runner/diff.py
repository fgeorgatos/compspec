__author__ = "Vanessa Sochat"
__copyright__ = "Copyright 2022, Vanessa Sochat"
__license__ = "MPL 2.0"

import compspec.solver
from compspec.solver import fn
from .base import CompositionBase, FactGenerator


class Difference(CompositionBase):
    """
    A composition is simply facts about one graph (object of interest).
    It uses a simple FactGenerator under the hood, and does not add any
    extra logic program (unless the user requests it).
    """

    _logic_programs = ["is-compatible.lp"]

    def __init__(self, A, B, out=None, namespaceA=None, namespaceB=None, quiet=False):
        self.driver = compspec.solver.PyclingoDriver(out=out)
        self.facts = DiffFactsGenerator(
            A, B, namespaceA=namespaceA, namespaceB=namespaceB
        )
        self.set_verbosity(out, quiet)


class DiffFactsGenerator(FactGenerator):
    """
    The DiffFactsGenerator generates facts for two graphs to compare.
    """

    def __init__(self, A, B, namespaceA=None, namespaceB=None):
        self.A = A
        self.B = B
        self.nsA = namespaceA or "A"
        self.nsB = namespaceB or "B"

    def setup(self, driver):
        """
        Setup data for one library
        """
        self.gen = driver
        self.gen.h1(f"Difference Betweeen {self.nsA} and {self.nsB}")

        # Set the library namespace
        self.gen.fact(fn.is_a(self.nsA))
        self.gen.fact(fn.is_b(self.nsB))
        self.gen.h2(f"Namespace {self.nsA}")
        self.generate_facts(self.A, self.nsA)
        self.generate_facts(self.B, self.nsB)
