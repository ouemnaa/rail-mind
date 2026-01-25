# Data dictionary — creating-context

This document describes the station (`nodes`) and rail (`edges`) attributes used in the `creating-context` dataset (source: `network_graph.json`). It explains the meaning, real-world rationale and the components that consume each attribute.

## Nodes (Stations)

| Attribute                     |                                    Type | What it represents                                             | Why it exists (real-world logic)                          | Used by                             |
| ----------------------------- | --------------------------------------: | -------------------------------------------------------------- | --------------------------------------------------------- | ----------------------------------- |
| `platforms`                   |                                     int | Number of physical platforms at the station                    | Limits how many trains can stop simultaneously            | Deterministic detection, Simulation |
| `max_trains_at_once`          |                                     int | Max trains allowed simultaneously at station (operational cap) | Platforms ≠ full capacity (safety, operational limits)    | Deterministic detection             |
| `max_simultaneous_arrivals`   |                                     int | How many arrivals can occur at once                            | Signal and staffing constraints affect concurrency        | Deterministic detection             |
| `min_dwell_time_sec`          |                                     int | Minimum scheduled stop time for trains                         | Passenger flow and safety constraints                     | Simulation, Prediction              |
| `blocking_behavior`           |                    enum (`hard`,`soft`) | Whether station blocks through traffic when full               | Some stations allow bypassing while others block the line | Detection, Resolution               |
| `signal_control`              | enum (`local`,`regional`,`centralized`) | Level of signal/control management                             | Higher control levels enable coordinated decisions        | Prediction, Explainability          |
| `has_switchyard`              |                                    bool | Whether track switching/redistribution is available            | Enables rerouting and complex movements                   | Resolution, Simulation              |
| `hold_allowed`                |                                    bool | Whether trains may be held at the station                      | Not all stations permit holding (safety/scheduling)       | Resolution                          |
| `max_hold_time_sec`           |                                     int | Maximum permitted hold time                                    | Safety and timetable constraints for holding              | Resolution, Explainability          |
| `priority_station`            |                                    bool | Strategic importance flag for station                          | Major hubs receive priority handling                      | Conflict prioritization             |
| `priority_override_allowed`   |                                    bool | Whether priority rules can be overridden                       | Emergency handling and exceptional decisions              | Resolution, Explainability          |
| `historical_congestion_level` |            enum (`low`,`medium`,`high`) | Usual congestion profile for the station                       | Congestion patterns inform predictions                    | Prediction (Qdrant)                 |
| `avg_delay_sec`               |                                     int | Average observed delay at the station                          | Baseline expectation used for forecasting                 | Prediction, Explainability          |

Notes:

- Station `id` / `name` are canonical keys used to link trains routes (`station_name`) and graph edges.
- Coordinate fields (`lat`, `lon`) are provided for visualization and spatial reasoning.

## Edges (Rails)

| Attribute              |                                       Type | What it represents                                 | Why it exists (Real-World Logic)                       | Used by                       |
| ---------------------- | -----------------------------------------: | -------------------------------------------------- | ------------------------------------------------------ | ----------------------------- |
| `direction`            | enum (`bidirectional`,`single_track`, ...) | Travel directionality of the rail segment          | Single-track sections imply shared time windows        | Detection, Simulation         |
| `min_headway_sec`      |                                        int | Minimum safe time separation between trains        | Derived from braking distances and signalling          | Deterministic detection       |
| `max_speed_kmh`        |                                        int | Speed limit on the segment                         | Infrastructure constraint for timing and safety        | Prediction, Simulation        |
| `capacity`             |                                        int | Maximum trains allowed on the segment concurrently | Physical and operational capacity limit                | Detection                     |
| `current_load`         |                                        int | Currently active trains on the segment             | Real-time congestion indicator                         | Detection                     |
| `reroutable`           |                                       bool | Flag indicating if an alternative path exists      | Helps the resolution agent avoid bottlenecks           | Resolution                    |
| `priority_access`      |                                       list | Allowed train types or priority classes            | Operational rules (e.g., passenger vs freight)         | Detection, Resolution         |
| `risk_profile`         |               enum (`low`,`medium`,`high`) | Operational risk level for the segment             | Captures weather, maintenance or known weak points     | Prediction, Explainability    |
| `historical_incidents` |                                        int | Count of past incidents on the segment             | Historical failures inform similarity-based prediction | Qdrant similarity, Prediction |
| `distance_km`          |                                      float | Physical length of the segment                     | Used for timing, energy and simulation calculations    | Simulation                    |
| `travel_time_min`      |                                      float | Nominal travel time used in schedules              | Baseline used for prediction and scheduling            | Prediction                    |

Notes:

- Edge `source` and `target` match station `id` values.
- Attributes like `capacity`, `current_load`, `min_headway_sec` and `max_speed_kmh` are critical to deterministic safety checks.

## Usage recommendations

- Use station `platforms`, `max_trains_at_once` and `max_simultaneous_arrivals` to detect platform conflicts and capacity overloads.
- Use `min_headway_sec`, `capacity`, and `current_load` for detecting headway violations and segment congestion.
- Use `historical_*` fields and `risk_profile` as metadata for the predictive engine (Qdrant) to find similar past states.
- Do not infer or synthesize missing stations or edges — operations should be dropped or marked invalid if references are missing.

## File locations

- Stations & edges: `creating-context/network_graph.json`
- Trains (CSV): `creating-context/mileage_data_enriched.csv`
- Processed train JSON: `creating-context/lombardy_simulation_data.json`

If you want, I can also generate a short schema file (`creating-context/schema.json`) describing types for programmatic validation.
