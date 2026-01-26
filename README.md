# RailMind

RailMind is a memory-driven system for real-time rail conflict detection and resolution. It combines deterministic safety rules, graph-based network models, and a vector memory store (Qdrant) to predict, detect, and resolve operational conflicts with explainable actions.

## What this project does

- Detects platform and routing conflicts in real time
- Forecasts short-term (3–10 minute) risks using historical cases
- Stores and retrieves past conflict cases in a vector database for similarity-based prediction
- Suggests constraint-aware resolution actions (holds, reroutes, priority changes)
- Provides explainability by linking decisions to triggers and similar historical events

## High-level architecture

Sensor Simulation → Network State Builder → Conflict Detection (deterministic + predictive) → Conflict Aggregator → Resolution Agent → API / Operator UI

## Key components

- **Sensor Simulation** — synthesizes train positions, station occupancy and rail utilization for testing
- **Network Context** — graph model of stations (nodes) and rails (edges), enriched with constraints and historical metrics
- **Deterministic Detection** — rule-based checks for headways, capacity, directional conflicts
- **Predictive Detection** — uses Qdrant to find similar past states and forecast emerging conflicts
- **Resolution Agent** — proposes actions that respect infrastructure, train capabilities and policies
- **Explainability** — each action links to triggers, constraints, and historical analogues for operator trust

## Train & Data model

Trains are first-class agents with planned routes, schedule info and real-time state. Train CSVs are transformed into simulation-ready JSON (routes, station order, coordinates, distances). The network graph JSON contains station metadata and rail attributes.

## Project layout

```
railmind/
├── data/              # preprocessing, train CSVs, network graph
├── simulation/        # sensor simulation and scenario runners
├── detection/         # deterministic and predictive detection engines
├── resolution/        # action planners and policy logic
├── explainability/    # trace and audit helpers
├── frontend/          # operator UI and visualization
└── docs/              # diagrams and component READMEs
```

## Simulation & testing

Supports synthetic timetable generation, load/stress tests, failure injection, and comparative evaluation of resolution strategies (what-if scenarios).

## Safety, privacy and transparency

- No personal data is used in this project
- Decisions are auditable and accompanied by explanations
- Historical bias is monitored and documented

## Next steps / roadmap

- Add multimodal inputs (weather, maintenance logs)
- Develop learning-based resolution policies with human-in-the-loop validation
- Integrate real sensor feeds for near real-time operation

---

