# Rail Brain - Intelligent Rail Network Conflict Resolution

A modular optimization system for resolving conflicts in complex rail networks. Rail Brain uses advanced metaheuristic algorithms, learned solver selection, and case-based reasoning to generate high-quality resolution plans for train scheduling conflicts.

## Overview

Rail Brain is designed for real-world rail network operations, particularly suited for large-scale networks like Lombardy. Given a conflict (trains competing for shared resources like platforms or track segments), it generates a ranked set of resolution plans with predicted impacts. The system can operate in multiple modes: pure optimization, selector-guided (AI picks best algorithm), or all-solvers (exhaustive comparison).

## Key Features

- **Multiple Optimization Algorithms**:
  - **Greedy Solver**: Fast heuristic for quick approximations
  - **Large Neighborhood Search (LNS)**: High-quality solutions with adaptive neighborhoods
  - **Simulated Annealing**: Probabilistic exploration to escape local optima
  - **Genetic Algorithm**: Population-based evolutionary search
  - **NSGA-II**: Multi-objective optimization for Pareto-optimal solutions
  - **Quantum-Enhanced LNS** (optional): Uses quantum QAOA for small critical subproblems

- **Intelligent Solver Selection**: Learns which algorithm performs best for each conflict type via neural network prediction

- **Case-Based Reasoning**: Leverages historical similar conflicts to suggest and evaluate resolutions

- **Delay Propagation Modeling**: Accurately predicts how delays cascade through the network under different resolutions

- **Multi-Objective Fitness Evaluation**: Balances delay minimization, passenger impact, network stability, and operational fairness

## Architecture

```
rail_brain/
├── data_structures.py      # Core data types (Conflict, Context, Resolution, etc.)
├── math.py                 # Mathematical models and optimization algorithms
├── gnn.py                  # Graph Neural Network for network embeddings
├── solver_selector.py      # AI model for intelligent solver selection
├── orchestrator.py         # Main coordination logic
├── quantum_solver.py       # Quantum-enhanced resolution (optional)
├── qubo_builder.py         # QUBO problem formulation for quantum solvers
├── conflict_adapter.py     # Data adapter for JSON-based conflict sources
├── example_lombardy.py     # Comprehensive example using Lombardy data
├── example_nour.py         # Example using real conflict data
└── tests/                  # Unit and integration tests
```

## Core Components

| Component | Role | Key Classes |
|-----------|------|-------------|
| `data_structures.py` | Core entities | Conflict, Context, Resolution, ResolutionPlan, HistoricalConflict, SimilarCase |
| `math.py` | Solvers & evaluation | GreedySolver, LNS, SimulatedAnnealing, GeneticAlgorithm, NSGAII, DelayPropagation, FitnessEvaluator |
| `orchestrator.py` | Main engine | ResolutionOrchestrator: coordinates solvers, selection, ranking |
| `solver_selector.py` | Algorithm selection | SolverSelectorNetwork: predicts best solver via neural network |
| `conflict_adapter.py` | Data conversion | Loads/maps conflicts from JSON (nour.json format) |
| `gnn.py` | Network encoding | GNNEmbedder: optional network topology encoder (uses simple features by default) |
| `quantum_solver.py` | Quantum enhancement | SimulatedQuantumQUBOSolver: QAOA repair for small subproblems (optional) |

## Quick Start
```bash
pip install requirements.txt
```

## Examples

```bash
python example_lombardy.py    # Realistic scenario with all solvers
python example_nour.py         # Real dataset conflicts
```

## Configuration

### OrchestratorConfig

Controls how conflicts are resolved:

```python
@dataclass
class OrchestratorConfig:
    # Solver selection strategy
    use_learned_selector: bool = True        # Use NN-based selector vs heuristic
    run_all_solvers: bool = False            # Run all solvers (exhaustive, slow but accurate)
    
    # Quality assurance
    fitness_threshold: float = 0.7           # Min acceptable fitness score (0-1)
    max_retries: int = 3                     # Retries with different solver if below threshold
    
    # Case-based reasoning
    use_similar_cases: bool = True           # Enable historical case matching
    similar_case_weight: float = 0.3         # How much to weight similar case suggestions
    
    # Quantum computing (optional)
    enable_quantum: bool = False             # Enable quantum QAOA repair in LNS
    quantum_min_trains: int = 4              # Min trains to trigger quantum (requires Qiskit)
```

**Modes**:
- `use_learned_selector=True`: NN predicts best solver (default, fast)
- `run_all_solvers=True`: Runs all 5 solvers, picks best (slow, accurate)
- `use_similar_cases=True`: Auto-retrieves and adapts historical similar conflicts
- `enable_quantum=True`: QAOA repair for small subproblems (requires Qiskit)

## Testing

```bash
python -m pytest tests/  # key: test_quantum_smoke.py
```

## Solver Performance

| Solver | Speed | Quality | Best For |
|--------|-------|---------|----------|
| Greedy | ⚡⚡⚡ | ⭐⭐ | Fast approximations |
| LNS | ⚡⚡ | ⭐⭐⭐ | Default (production) |
| Simulated Annealing | ⚡ | ⭐⭐⭐ | High quality |
| Genetic Algorithm | ⚡ | ⭐⭐⭐ | Diverse solutions |
| NSGA-II | ⚡ | ⭐⭐⭐⭐ | Multi-objective |
| Quantum-LNS | ⚡⚡ | ⭐⭐⭐⭐ | Small critical subproblems |

## Advanced Features

### Delay Propagation Model

Rail Brain models how delays cascade through the network:

```
arrival_delay[i+1] = max(0, departure_delay[i] + run_delta + weather_penalty)
departure_delay[i+1] = max(0, arrival_delay[i+1] - absorption + dwell_delta)
```

Key factors:
- **Weather penalty**: Rain adds 5% delay, snow 15%, fog 8%
- **Absorption**: Trains recover portion of delay at each stop (default 10%)
- **Headway conflicts**: When trains are too close, spacing them out provides cascading benefit to other trains
- **Capacity conflicts**: Holding one train at a platform frees resources for others

### Resolution Actions

| Action | Effect | Use |
|--------|--------|-----|
| HOLD | Delay departure to free resources | Platform/track conflicts |
| SPEED_ADJUST | Change speed (0.8-1.2x) | Reduce delay or create spacing |
| REROUTE | Change track/platform | Avoid conflict |
| CANCEL | Remove train | Emergency only |
| PLATFORM_CHANGE | Reassign platform | Station conflicts |

### Fitness Evaluation

Four-component score (weights: 0.4 delay, 0.3 passenger, 0.2 propagation, 0.1 recovery):
```
fitness = w_delay(1 - delay/max_delay) + w_passenger(1 - impact/max_impact) 
        + w_prop(1 - depth/num_trains) + w_recovery * smoothness
```

### Case-Based Reasoning

Automatic retrieval of similar historical conflicts:
1. **Match**: Find conflicts with similar trains, stations, delays
2. **Adapt**: Map historical actions to current trains (by delay similarity)
3. **Rank**: Include adapted resolution in results (evaluated via fitness)

## Workflow Overview

### Typical Resolution Flow

```
┌─────────────────────────────┐
│ Input: Conflict + Context   │
│ + Train Adjacency           │
└──────────────┬──────────────┘
               │
               ▼
        ┌──────────────┐
        │   Embedding  │  ← Uses simple feature vector
        │  (128 dims)  │     (not GNN by default)
        └──────┬───────┘
               │
               ▼
        ┌─────────────────────┐
        │  Solver Selection   │  ← NN predicts: Greedy/LNS/SA/GA/NSGA2
        │ (or all-solvers)    │
        └──────┬──────────────┘
               │
               ├─→ GreedySolver ──┐
               ├─→ LNS ────────────┤
               ├─→ Simulated Ann ──┼─→ Rank by Fitness ─→ Top 5 Plans
               ├─→ GeneticAlg ────┤
               └─→ NSGA-II ────────┘
               
        Optional: Case-based plan if similar cases available
               │
               ▼
        ┌─────────────────────┐
        │  Delay Propagation  │  ← Predict cascade effects
        │  + Fitness Eval     │
        └──────┬──────────────┘
               │
               ▼
        ┌─────────────────────┐
        │ Ranked Solutions    │
        │ (sorted by fitness) │
        └─────────────────────┘
```

### Input/Output

**In**: Conflict + Context + train adjacency (+ optional similar_cases, rail_graph)  
**Out**: ResolutionPlan[] with fitness, actions, delay, passenger_impact, propagation_depth

## Dependencies

- **NumPy**: Numerical computations
- **Qiskit**: Quantum computing (optional, for quantum-enhanced features)
- **Python 3.8+**: Core language requirement

## Data Formats

**Conflict**: conflict_id, station_ids, train_ids, delay_values, timestamp, severity, conflict_type  
**Context**: time_of_day (0-24h), day_of_week (0-6), is_peak_hour, weather_condition, network_load (0-1)  
**ResolutionPlan**: actions[], overall_fitness, total_delay, passenger_impact, propagation_depth, solver_used

**JSON (nour.json)**:
```json
{
  "conflicts": [{
    "conflict_id": "CF_001", "conflict_type": "headway_violation",
    "severity": "high", "timestamp": "2024-01-15T08:30:00Z",
    "location": {"edge_id": "MILANO--MONZA"},
    "involved_trains": ["IC_123", "REG_456"],
    "metadata": {"actual_headway_sec": 120, "required_headway_sec": 180}
  }]
}
```
**Mapped types**: headway_violation→headway, delay_propagation_risk→delay, high_risk_edge_stress→capacity

## Contributing & Documentation

**Extending Rail Brain**:
1. Add data types to `data_structures.py`
2. Implement solvers in `math.py`
3. Add tests in `tests/`
4. Follow modular design pattern

**Related docs**: Engineering Blueprint, problem_statement, proposed_plan, specific_component_architecture
