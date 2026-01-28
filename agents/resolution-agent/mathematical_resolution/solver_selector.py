"""
AI model for selecting the best solver based on conflict characteristics.
Uses learned embeddings to predict which optimization algorithm will perform best.
"""
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

from .data_structures import Conflict, Context, ResolutionPlan


class SolverType(Enum):
    GREEDY = "greedy"
    LNS = "lns"
    SIMULATED_ANNEALING = "simulated_annealing"
    NSGA2 = "nsga2"


@dataclass
class SolverPerformance:
    """Historical performance of a solver on a conflict type."""
    solver: SolverType
    avg_fitness: float
    avg_time_ms: float
    success_rate: float


class SolverSelectorNetwork:
    """
    Neural network that predicts the best solver for a given conflict.
    
    Architecture:
        conflict_embedding -> hidden layers -> solver probabilities
    
    Trained on historical (conflict, solver, performance) tuples.
    """
    
    def __init__(
        self,
        embedding_dim: int = 128,
        hidden_dim: int = 64,
        num_solvers: int = 4
    ):
        self.embedding_dim = embedding_dim
        self.hidden_dim = hidden_dim
        self.num_solvers = num_solvers
        self.solver_names = [s.value for s in SolverType]
        
        # Network weights
        self.W1 = np.random.randn(embedding_dim, hidden_dim) * 0.1
        self.b1 = np.zeros(hidden_dim)
        self.W2 = np.random.randn(hidden_dim, hidden_dim) * 0.1
        self.b2 = np.zeros(hidden_dim)
        self.W_out = np.random.randn(hidden_dim, num_solvers) * 0.1
        self.b_out = np.zeros(num_solvers)
        
        # Training history
        self.training_data: List[Tuple[np.ndarray, int, float]] = []
    
    def forward(self, embedding: np.ndarray) -> np.ndarray:
        """
        Forward pass: embedding -> solver probabilities.
        
        Args:
            embedding: (embedding_dim,) conflict embedding
        
        Returns:
            probs: (num_solvers,) probability distribution over solvers
        """
        # Hidden layer 1
        h1 = np.maximum(0, embedding @ self.W1 + self.b1)  # ReLU
        
        # Hidden layer 2
        h2 = np.maximum(0, h1 @ self.W2 + self.b2)
        
        # Output layer
        logits = h2 @ self.W_out + self.b_out
        
        # Softmax
        exp_logits = np.exp(logits - np.max(logits))
        probs = exp_logits / np.sum(exp_logits)
        
        return probs
    
    def predict(self, embedding: np.ndarray) -> SolverType:
        """
        Predict best solver for given conflict embedding.
        
        Args:
            embedding: Conflict embedding from GNN
        
        Returns:
            Best solver type
        """
        probs = self.forward(embedding)
        best_idx = np.argmax(probs)
        return SolverType(self.solver_names[best_idx])
    
    def predict_with_confidence(
        self,
        embedding: np.ndarray
    ) -> Tuple[SolverType, float, Dict[str, float]]:
        """
        Predict solver with confidence scores.
        
        Returns:
            (best_solver, confidence, all_probabilities)
        """
        probs = self.forward(embedding)
        best_idx = np.argmax(probs)
        
        prob_dict = {name: float(p) for name, p in zip(self.solver_names, probs)}
        
        return (
            SolverType(self.solver_names[best_idx]),
            float(probs[best_idx]),
            prob_dict
        )
    
    def record_outcome(
        self,
        embedding: np.ndarray,
        solver_used: SolverType,
        fitness_achieved: float
    ):
        """Record training example for online learning."""
        solver_idx = self.solver_names.index(solver_used.value)
        self.training_data.append((embedding, solver_idx, fitness_achieved))
    
    def train_step(self, learning_rate: float = 0.01):
        """
        Single training step using recent data.
        Uses simple gradient descent on cross-entropy loss.
        """
        if len(self.training_data) < 10:
            return
        
        # Sample batch
        batch_size = min(32, len(self.training_data))
        indices = np.random.choice(len(self.training_data), batch_size, replace=False)
        
        for idx in indices:
            embedding, target_solver, fitness = self.training_data[idx]
            
            # Forward pass
            h1 = np.maximum(0, embedding @ self.W1 + self.b1)
            h2 = np.maximum(0, h1 @ self.W2 + self.b2)
            logits = h2 @ self.W_out + self.b_out
            exp_logits = np.exp(logits - np.max(logits))
            probs = exp_logits / np.sum(exp_logits)
            
            # Compute gradient (simplified cross-entropy)
            target = np.zeros(self.num_solvers)
            target[target_solver] = 1.0
            
            # Weight by fitness (better fitness = stronger signal)
            grad_out = (probs - target) * fitness
            
            # Backprop (simplified)
            self.W_out -= learning_rate * np.outer(h2, grad_out)
            self.b_out -= learning_rate * grad_out
            
            # Deeper layers (simplified gradient)
            grad_h2 = grad_out @ self.W_out.T
            grad_h2 = grad_h2 * (h2 > 0)  # ReLU derivative
            
            self.W2 -= learning_rate * np.outer(h1, grad_h2)
            self.b2 -= learning_rate * grad_h2


class EnsembleSolverSelector:
    """
    Ensemble approach: run multiple solvers and learn from results.
    Uses Thompson Sampling for exploration/exploitation.
    """
    
    def __init__(self):
        # Beta distribution parameters for each solver
        # (alpha, beta) - higher alpha = more successes
        self.solver_stats: Dict[SolverType, Tuple[float, float]] = {
            SolverType.GREEDY: (1.0, 1.0),
            SolverType.LNS: (1.0, 1.0),
            SolverType.SIMULATED_ANNEALING: (1.0, 1.0),
            SolverType.NSGA2: (1.0, 1.0),
        }
        
        # Context-specific stats
        self.context_stats: Dict[str, Dict[SolverType, Tuple[float, float]]] = {}
    
    def select(
        self,
        context: Optional[Context] = None,
        explore: bool = True
    ) -> SolverType:
        """
        Select solver using Thompson Sampling.
        
        Args:
            context: Operational context for context-specific selection
            explore: If True, sample from distribution; if False, use mean
        """
        stats = self.solver_stats
        
        # Use context-specific stats if available
        if context is not None:
            context_key = self._context_key(context)
            if context_key in self.context_stats:
                stats = self.context_stats[context_key]
        
        if explore:
            # Thompson Sampling: sample from Beta distributions
            samples = {
                solver: np.random.beta(alpha, beta)
                for solver, (alpha, beta) in stats.items()
            }
        else:
            # Exploitation: use expected value (alpha / (alpha + beta))
            samples = {
                solver: alpha / (alpha + beta)
                for solver, (alpha, beta) in stats.items()
            }
        
        return max(samples, key=samples.get)
    
    def update(
        self,
        solver: SolverType,
        success: bool,
        context: Optional[Context] = None
    ):
        """
        Update solver statistics based on outcome.
        
        Args:
            solver: Solver that was used
            success: True if solver performed well (above threshold)
            context: Operational context
        """
        # Update global stats
        alpha, beta = self.solver_stats[solver]
        if success:
            self.solver_stats[solver] = (alpha + 1, beta)
        else:
            self.solver_stats[solver] = (alpha, beta + 1)
        
        # Update context-specific stats
        if context is not None:
            context_key = self._context_key(context)
            if context_key not in self.context_stats:
                self.context_stats[context_key] = {
                    s: (1.0, 1.0) for s in SolverType
                }
            
            alpha, beta = self.context_stats[context_key][solver]
            if success:
                self.context_stats[context_key][solver] = (alpha + 1, beta)
            else:
                self.context_stats[context_key][solver] = (alpha, beta + 1)
    
    def _context_key(self, context: Context) -> str:
        """Generate key for context-specific bucketing."""
        peak = "peak" if context.is_peak_hour else "offpeak"
        weather = context.weather_condition
        return f"{peak}_{weather}"
    
    def get_stats(self) -> Dict[str, Dict[str, float]]:
        """Get current solver performance statistics."""
        return {
            solver.value: {
                "success_rate": alpha / (alpha + beta),
                "confidence": alpha + beta,
                "alpha": alpha,
                "beta": beta
            }
            for solver, (alpha, beta) in self.solver_stats.items()
        }
