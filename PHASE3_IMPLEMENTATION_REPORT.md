# CRAI Backend Phase 3 — Farm Intelligence Simulation & Event Layer

## Scope

This phase extends the existing CRAI FastAPI backend without replacing the existing deterministic intelligence pipeline.

The existing visual AI, evidence engine, adaptive evidence, fusion risk, decision engine, judge intelligence, advisory and real sensor acquisition paths are preserved.

## Implemented

### 1. Production-capable field sensor schema

Existing sensor payloads remain backward compatible. Optional fields now support:

- soil_temperature
- soil_ph
- soil_ec
- leaf_wetness
- latitude / longitude / altitude
- battery
- signal_strength
- gateway_id
- sequence_number

`source` remains constrained to REAL / SIMULATED / ESTIMATED / USER_ENTERED.

### 2. Field simulator

New service: `app/services/field_simulator_service.py`

Scenarios:

- NORMAL
- DEVELOPING_STRESS
- DISEASE_RISK
- SEVERE_EVENT
- RECOVERY

Simulation is deterministic for a supplied seed and always produces `source=SIMULATED`.

### 3. Simulator APIs

- `GET /api/simulator/status`
- `POST /api/simulator/start`
- `POST /api/simulator/stop`
- `POST /api/simulator/scenario`
- `POST /api/simulator/step`
- `POST /api/simulator/evaluate`

The evaluate endpoint does not fabricate an image-model result. A visual prediction is explicitly supplied for simulation, then passed through the existing `analysis_service` and its authoritative evidence/fusion/decision pipeline.

### 4. Farm event engine

New model: `FarmEvent`

New service: `app/services/farm_event_service.py`

Event states supported:

- DETECTED
- CONFIRMED
- ACTIVE
- RECOVERING
- RESOLVED

The event layer consumes authoritative CRAI analysis output; it does not calculate risk itself.

### 5. Before / During / After

Event snapshots preserve real available evidence and explicitly use `NOT_AVAILABLE` when a phase does not exist. No missing historical values are fabricated.

### 6. Evidence package

Each event can produce a structured package containing:

- time
- farm / zone
- crop
- sensor evidence
- visual finding
- risk
- decision
- action
- evidence provenance
- before / during / after state

A SHA-256 integrity hash is generated from a canonical event representation.

The hash is an integrity mechanism only. It is not blockchain and does not prove that an observation is truthful.

### 7. Farm and event APIs

- `GET /api/farms/{farm_id}/state`
- `GET /api/farms/{farm_id}/zones/{zone_id}/state`
- `GET /api/events`
- `GET /api/events/active`
- `GET /api/events/{event_id}`
- `GET /api/events/{event_id}/timeline`
- `GET /api/events/{event_id}/evidence`
- `POST /api/evidence/verify?event_id=...`

### 8. External context boundary

Live weather/satellite APIs were deliberately not added in this phase. This keeps the backend runnable without credentials and avoids claiming live integrations that are not deployed.

### 9. SQLite preserved

SQLite remains the default. The event/evidence layer is isolated so the persistence layer can later be moved toward Supabase PostgreSQL.

## Validation

- `python -m compileall app tests -q` — PASS
- `pytest -q` — **24 passed**
- FastAPI application import — PASS
- Uvicorn smoke test — PASS
- `/api/health` — HTTP 200
- `/api/ai/status` — HTTP 200, CRAI Tomato Specialist ready
- `/api/advisory/status` — HTTP 200; availability depends on whether local Ollama is running
- `/api/simulator/status` — HTTP 200
- simulator scenario/start/step — PASS
- simulator evaluation through existing CRAI analysis — PASS
- event creation — PASS
- event timeline — PASS
- evidence package — PASS
- SHA-256 verification — PASS

## Known limitation

The current event package is only as strong as the evidence actually available. If no prior stable event state exists, `before_state` remains `NOT_AVAILABLE`. The simulator never claims its values are physical observations.

Physical ESP32-S3 / Raspberry Pi / LoRa integration remains a later replacement of the simulator input layer using the same field-sensor contract.
