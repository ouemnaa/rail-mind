"""
Main orchestrator that ties everything together.
Coordinates GNN encoding, solver selection, and resolution generation.
Uses similar historical conflicts for case-based reasoning.
"""
import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from .data_structures import (
    Conflict, Context, Resolution, ResolutionPlan, RailGraph,
    HistoricalConflict, SimilarCase
)
from .math import (
    DelayPropagation, DelayParams, FitnessEvaluator,
    GreedySolver, LargeNeighborhoodSearch, SimulatedAnnealing, NSGAII,
    GeneticAlgorithm
)
from .gnn import GNNEmbedder, GNNConfig, build_rail_graph
from .solver_selector import (
    SolverSelectorNetwork, EnsembleSolverSelector, SolverType
)


@dataclass
class OrchestratorConfig:
    """Configuration for the orchestrator."""
    use_learned_selector: bool = True  # Use NN selector vs ensemble
    run_all_solvers: bool = False      # Run all and pick best (slow but accurate)
    fitness_threshold: float = 0.7     # Threshold for "good" solution
    max_retries: int = 3               # Retries with different solver if below threshold
    use_similar_cases: bool = True     # Use historical similar conflicts
    similar_case_weight: float = 0.3   # How much to weight similar case suggestions
    # Quantum-enhanced LNS settings
    enable_quantum: bool = False       # Enable quantum repair in LNS (requires Qiskit)
    quantum_min_trains: int = 4        # Min trains to trigger quantum repair


class ResolutionOrchestrator:
    """
    Main orchestrator for rail network conflict resolution.
    
    Given:
        - Pre-computed conflict embeddings (or raw conflict data)
        - Rail network graph
        - Operational context
        - Similar historical conflicts (optional but recommended)
    
    Returns:
        - Ranked list of resolution plans with explanations
    """
    
    def __init__(self, config: Optional[OrchestratorConfig] = None):
        self.config = config or OrchestratorConfig()
        
        # Initialize components
        self.gnn = GNNEmbedder(GNNConfig())
        self.delay_model = DelayPropagation(DelayParams())
        self.fitness_evaluator = FitnessEvaluator(self.delay_model)
        
        # Solver selector
        if self.config.use_learned_selector:
            self.selector = SolverSelectorNetwork()
        else:
            self.selector = EnsembleSolverSelector()
        
        # Initialize solvers (now includes GA)
        self.solvers = {
            SolverType.GREEDY: GreedySolver(self.fitness_evaluator),
            SolverType.LNS: LargeNeighborhoodSearch(
                self.fitness_evaluator,
                enable_quantum=self.config.enable_quantum,
                quantum_min_trains=self.config.quantum_min_trains,
            ),
            SolverType.SIMULATED_ANNEALING: SimulatedAnnealing(self.fitness_evaluator),
            SolverType.NSGA2: NSGAII(self.fitness_evaluator),
        }
        
        # Add GA solver
        self.ga_solver = GeneticAlgorithm(self.fitness_evaluator)
    
    def resolve(
        self,
        conflict: Conflict,
        context: Context,
        adjacency: Dict[str, List[str]],
        graph: Optional[RailGraph] = None,
        similar_cases: Optional[List[SimilarCase]] = None
    ) -> List[ResolutionPlan]:
        """
        Generate resolution plans for a conflict.
        
        Args:
            conflict: The conflict to resolve (may include pre-computed embedding)
            context: Operational context
            adjacency: Train connectivity graph (train_id -> connected trains)
            graph: Rail network graph (optional, for GNN embedding)
            similar_cases: List of similar historical conflicts with resolutions
        
        Returns:
            List of resolution plans, ranked by fitness
        """
        # Get embedding (use pre-computed or generate)
        embedding = self._get_embedding(conflict, context, graph)
        
        plans = []
        
        # If we have similar cases, create a plan from their successful resolutions
        if similar_cases and self.config.use_similar_cases:
            case_based_plan = self._plan_from_similar_cases(
                conflict, context, adjacency, similar_cases
            )
            if case_based_plan:
                plans.append(case_based_plan)
        
        if self.config.run_all_solvers:
            # Run all solvers and collect results
            print("  [DEBUG] Running all solvers...")
            for solver_type, solver in self.solvers.items():
                plan = self._run_solver(solver_type, conflict, context, adjacency)
                plans.append(plan)
                print(f"    - {solver_type.value}: fitness={plan.overall_fitness:.3f}, actions={len(plan.actions)}, delay={plan.total_delay:.1f}min")
            # Also run GA
            ga_plan = self.ga_solver.solve(conflict, context, adjacency)
            plans.append(ga_plan)
            print(f"    - genetic_algorithm: fitness={ga_plan.overall_fitness:.3f}, actions={len(ga_plan.actions)}, delay={ga_plan.total_delay:.1f}min")
        else:
            # Use selector to pick solver
            selected = self._select_solver(embedding, context)
            plan = self._run_solver(selected, conflict, context, adjacency)
            plans.append(plan)
            
            # Retry if below threshold
            retries = 0
            while plan.overall_fitness < self.config.fitness_threshold and retries < self.config.max_retries:
                # Try a different solver
                other_solvers = [s for s in SolverType if s != selected]
                if not other_solvers:
                    break
                    
                selected = np.random.choice(list(other_solvers))
                plan = self._run_solver(selected, conflict, context, adjacency)
                plans.append(plan)
                retries += 1
        
        # Rank by fitness
        plans.sort(key=lambda p: p.overall_fitness, reverse=True)
        
        # Update selector with outcome
        if plans:
            best = plans[0]
            self._update_selector(
                embedding, 
                SolverType(best.solver_used) if best.solver_used in [s.value for s in SolverType] else SolverType.GREEDY,
                best.overall_fitness,
                context
            )
        
        return plans
    
    def _plan_from_similar_cases(
        self,
        conflict: Conflict,
        context: Context,
        adjacency: Dict[str, List[str]],
        similar_cases: List[SimilarCase]
    ) -> Optional[ResolutionPlan]:
        """
        Create a resolution plan based on what worked in similar past conflicts.
        Adapts historical resolutions to current conflict.
        """
        if not similar_cases:
            return None
        
        # Weight suggestions by similarity and success score
        weighted_actions: Dict[str, List[Tuple[Resolution, float]]] = {}
        
        for case in similar_cases:
            weight = case.similarity * case.historical.success_score
            
            for action in case.get_suggested_actions():
                # Try to map to current conflict's trains
                # If exact train not in conflict, skip or find similar
                if action.target_train_id in conflict.train_ids:
                    target = action.target_train_id
                elif conflict.train_ids:
                    # Map to train with similar delay
                    target = self._find_similar_train(
                        action.target_train_id,
                        conflict,
                        case.historical.conflict
                    )
                else:
                    continue
                
                if target:
                    adapted_action = Resolution(
                        action_type=action.action_type,
                        target_train_id=target,
                        parameters=action.parameters
                    )
                    
                    if target not in weighted_actions:
                        weighted_actions[target] = []
                    weighted_actions[target].append((adapted_action, weight))
        
        # Select best action for each train
        final_actions = []
        for train_id, action_weights in weighted_actions.items():
            # Pick highest weighted action
            best_action, _ = max(action_weights, key=lambda x: x[1])
            final_actions.append(best_action)
        
        if not final_actions:
            return None
        
        # Evaluate the case-based plan
        plan = self.fitness_evaluator.evaluate(
            conflict, final_actions, context, adjacency
        )
        plan.solver_used = "case_based"
        
        return plan
    
    def _find_similar_train(
        self,
        original_train: str,
        current_conflict: Conflict,
        historical_conflict: Conflict
    ) -> Optional[str]:
        """Map a train from historical conflict to current conflict by delay similarity."""
        original_delay = historical_conflict.delay_values.get(original_train, 0)
        
        # Find train with closest delay
        best_match = None
        best_diff = float('inf')
        
        for train_id, delay in current_conflict.delay_values.items():
            diff = abs(delay - original_delay)
            if diff < best_diff:
                best_diff = diff
                best_match = train_id
        
        return best_match
    
    def resolve_with_explanation(
        self,
        conflict: Conflict,
        context: Context,
        adjacency: Dict[str, List[str]],
        graph: Optional[RailGraph] = None,
        similar_cases: Optional[List[SimilarCase]] = None
    ) -> Tuple[ResolutionPlan, str]:
        """
        Generate resolution with human-readable explanation.
        
        Returns:
            (best_plan, explanation_text)
        """
        plans = self.resolve(conflict, context, adjacency, graph, similar_cases)
        
        if not plans:
            return None, "No resolution found."
        
        best = plans[0]
        explanation = self._generate_explanation(conflict, context, best, similar_cases)
        
        return best, explanation
    
    def _get_embedding(
        self,
        conflict: Conflict,
        context: Context,
        graph: Optional[RailGraph]
    ) -> np.ndarray:
        """Get or compute conflict embedding."""
        if conflict.embedding is not None:
            # Use pre-computed embedding
            return conflict.embedding
        
        if graph is not None:
            # Compute using GNN
            return self.gnn.embed_conflict(
                graph, 
                conflict.station_ids, 
                context
            )
        
        # Fallback: simple feature vector
        return self._simple_embedding(conflict, context)
    
    def _simple_embedding(self, conflict: Conflict, context: Context) -> np.ndarray:
        """Simple embedding without GNN (fallback)."""
        features = [
            conflict.severity,
            len(conflict.train_ids) / 10.0,
            len(conflict.station_ids) / 10.0,
            np.mean(list(conflict.delay_values.values())) / 60.0 if conflict.delay_values else 0,
            np.max(list(conflict.delay_values.values())) / 60.0 if conflict.delay_values else 0,
        ]
        features.extend(context.to_vector().tolist())
        
        # Pad to expected dimension
        while len(features) < 128:
            features.append(0.0)
        
        return np.array(features[:128])
    
    def _select_solver(self, embedding: np.ndarray, context: Context) -> SolverType:
        """Select solver using the configured method."""
        if isinstance(self.selector, SolverSelectorNetwork):
            return self.selector.predict(embedding)
        else:
            return self.selector.select(context)
    
    def _run_solver(
        self,
        solver_type: SolverType,
        conflict: Conflict,
        context: Context,
        adjacency: Dict[str, List[str]]
    ) -> ResolutionPlan:
        """Run specific solver."""
        solver = self.solvers[solver_type]
        return solver.solve(conflict, context, adjacency)
    
    def _update_selector(
        self,
        embedding: np.ndarray,
        solver: SolverType,
        fitness: float,
        context: Context
    ):
        """Update selector with outcome for learning."""
        if isinstance(self.selector, SolverSelectorNetwork):
            self.selector.record_outcome(embedding, solver, fitness)
            self.selector.train_step()
        else:
            success = fitness >= self.config.fitness_threshold
            self.selector.update(solver, success, context)
    
    def _generate_explanation(
        self,
        conflict: Conflict,
        context: Context,
        plan: ResolutionPlan,
        similar_cases: Optional[List[SimilarCase]] = None
    ) -> str:
        """Generate human-readable explanation."""
        lines = [
            f"=== Conflict Resolution Report ===",
            f"",
            f"Conflict: {conflict.conflict_id}",
            f"Type: {conflict.conflict_type}",
            f"Severity: {conflict.severity:.2f}",
            f"Affected trains: {', '.join(conflict.train_ids)}",
            f"Affected stations: {', '.join(conflict.station_ids)}",
            f"",
            f"Context:",
            f"  - Time: {context.time_of_day:.1f}h ({'Peak' if context.is_peak_hour else 'Off-peak'})",
            f"  - Weather: {context.weather_condition}",
            f"  - Network load: {context.network_load:.1%}",
        ]
        
        # Add similar cases info if available
        if similar_cases:
            lines.extend([
                f"",
                f"Similar Historical Cases: {len(similar_cases)}",
            ])
            for i, case in enumerate(similar_cases[:3], 1):  # Show top 3
                lines.append(
                    f"  {i}. {case.historical.conflict.conflict_id} "
                    f"(similarity: {case.similarity:.1%}, success: {case.historical.success_score:.1%})"
                )
        
        lines.extend([
            f"",
            f"Resolution (using {plan.solver_used}):",
        ])
        
        for i, action in enumerate(plan.actions, 1):
            lines.append(f"  {i}. {action.action_type.value.upper()} - Train {action.target_train_id}")
            for k, v in action.parameters.items():
                if isinstance(v, float):
                    lines.append(f"      {k}: {v:.2f}")
                else:
                    lines.append(f"      {k}: {v}")
        
        lines.extend([
            f"",
            f"Expected Outcomes:",
            f"  - Total delay: {plan.total_delay:.1f} minutes",
            f"  - Passenger impact: {plan.passenger_impact:.0f} passenger-minutes",
            f"  - Propagation depth: {plan.propagation_depth} trains",
            f"  - Recovery smoothness: {plan.recovery_smoothness:.2f}",
            f"  - Overall fitness: {plan.overall_fitness:.3f}",
        ])
        
        return "\n".join(lines)


# Convenience function for quick usage
def resolve_conflict(
    conflict: Conflict,
    context: Context,
    adjacency: Dict[str, List[str]],
    stations: Optional[List[dict]] = None,
    connections: Optional[List[dict]] = None
) -> Tuple[ResolutionPlan, str]:
    """
    Quick function to resolve a conflict.
    
    Args:
        conflict: Conflict to resolve
        context: Operational context
        adjacency: Train connectivity
        stations: Optional station data for GNN
        connections: Optional connection data for GNN
    
    Returns:
        (best_plan, explanation)
    """
    orchestrator = ResolutionOrchestrator()
    
    graph = None
    if stations and connections:
        graph = build_rail_graph(stations, connections, conflict.delay_values)
    
    return orchestrator.resolve_with_explanation(conflict, context, adjacency, graph)
