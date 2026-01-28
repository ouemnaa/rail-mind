# quantum_backend.py
from typing import Dict

from qiskit_aer import Aer
from qiskit_algorithms.utils import algorithm_globals

# from qiskit.utils import algorithm_globals

from qiskit_algorithms.minimum_eigensolvers import QAOA
from qiskit_algorithms.optimizers import COBYLA

from qiskit_optimization import QuadraticProgram
from qiskit_optimization.algorithms import MinimumEigenOptimizer


class SimulatedQuantumQUBOSolver:
    """
    Simulated quantum backend using QAOA on Qiskit Aer.
    Intended for SMALL QUBOs (<= ~20 variables).
    """

    def __init__(self, reps: int = 2, seed: int = 42):
        self.reps = reps
        algorithm_globals.random_seed = seed
        self.backend = Aer.get_backend("aer_simulator")

    def solve(self, Q: Dict, num_vars: int) -> Dict[int, int]:
        qp = self._qubo_to_quadratic_program(Q, num_vars)

        optimizer = COBYLA(maxiter=100)

        qaoa = QAOA(
            optimizer=optimizer,
            reps=self.reps,
            backend=self.backend,
        )

        solver = MinimumEigenOptimizer(qaoa)
        result = solver.solve(qp)

        return {i: int(result.x[i]) for i in range(num_vars)}

    # -------------------------------------------------------------

    def _qubo_to_quadratic_program(self, Q, num_vars):
        qp = QuadraticProgram()

        for i in range(num_vars):
            qp.binary_var(name=f"x{i}")

        linear = {}
        quadratic = {}

        for (i, j), w in Q.items():
            if i == j:
                linear[f"x{i}"] = linear.get(f"x{i}", 0.0) + w
            else:
                quadratic[(f"x{i}", f"x{j}")] = (
                    quadratic.get((f"x{i}", f"x{j}"), 0.0) + w
                )

        qp.minimize(linear=linear, quadratic=quadratic)
        return qp


class ClassicalFallbackSolver:
    """
    Simple deterministic fallback if QAOA is too slow or fails.
    """

    def solve(self, Q, num_vars):
        solution = {i: 0 for i in range(num_vars)}

        # Greedy: activate variables with negative diagonal weight
        for (i, j), w in Q.items():
            if i == j and w < 0:
                solution[i] = 1

        return solution
class HybridQuantumSolver:
    """
    Single entry point for LNS.
    Uses QAOA when feasible, otherwise falls back to classical.
    """

    def __init__(self, use_quantum: bool = True, max_quantum_vars: int = 20):
        self.use_quantum = use_quantum
        self.max_quantum_vars = max_quantum_vars

        self.quantum_solver = SimulatedQuantumQUBOSolver()
        self.fallback_solver = ClassicalFallbackSolver()

    def solve(self, Q, num_vars):
        if not self.use_quantum or num_vars > self.max_quantum_vars:
            return self.fallback_solver.solve(Q, num_vars)

        try:
            return self.quantum_solver.solve(Q, num_vars)
        except Exception:
            return self.fallback_solver.solve(Q, num_vars)
