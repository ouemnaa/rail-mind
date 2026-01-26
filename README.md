# RailMind

RailMind is a memory-driven system for real-time rail conflict detection and resolution built on Italy's real rail network data. It combines deterministic algorithms and safety rules, graph-based network models, and a vector memory store (Qdrant) to predict, detect, and resolve operational conflicts with explainable actions.

<img width="1871" height="869" alt="rail_img_front" src="https://github.com/user-attachments/assets/8d64dbec-9495-41e2-bf0e-4f6f45ab420a" />


## What this project does

- Detects platform and routing conflicts in real time
- Forecasts short-term (3–10 minute) risks using historical cases
- Stores and retrieves past conflict cases in a vector database for similarity-based prediction
- Suggests constraint-aware resolution actions (holds, reroutes, priority changes)
- Provides explainability by linking decisions to triggers and similar historical events

## Tech Stack
- Python (simulation & data processing)
- NetworkX (railway network graph)
- Qdrant (vector database for semantic search)
- Other dependencies: pandas, datetime, etc.

## Setup & Run
   ```bash
   git clone <repo_url>
   cd <repo_folder>
   cd frontend
   npm install
   npm run
  ```
## Data Pipeline
<div align="center">
  <img width="240" height="664" alt="image" src="https://github.com/user-attachments/assets/e2160f09-0b7a-48e8-8c52-7dbe5841e7a0" />
</div>

## High-level architecture
<div align="center">
  <img width="276" height="333" alt="image" src="https://github.com/user-attachments/assets/99047d2f-00e4-439c-82ac-e85f2a9a6219" />
</div>

## Key components

- **Sensor Simulation** — synthesizes train positions, station occupancy and rail utilization for testing
- **Network Context** — graph model of stations (nodes) and rails (edges), enriched with constraints and historical metrics
- **Deterministic Detection** — rule-based checks for headways, capacity, directional conflicts
- **Predictive Detection** — finds similar past states and forecasts emerging conflicts
- **Resolution Agent** — proposes actions that respect infrastructure, train capabilities and policies and updates the new Qdrant database
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

## authors 

-Emna Ouertani 
-Ela Sarhani 
-Nour Mustapha 
-Farah Baraket 
-Asma Raies

