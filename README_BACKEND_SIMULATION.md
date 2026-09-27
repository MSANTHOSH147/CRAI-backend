# CRAI Backend — Farm Intelligence Simulation

This extension keeps the existing CRAI deterministic intelligence pipeline intact and adds a software-only field simulation/event layer for development when physical hardware is unavailable.

## Core rule

Simulator observations are always marked:

`source = SIMULATED`

They are never converted into `REAL` evidence.

## Main flow

```text
SIMULATED FIELD SENSOR
        ↓
Field Sensor API / simulator
        ↓
Current farm state
        ↓
Existing CRAI analysis_service
        ↓
Existing evidence / adaptive evidence / fusion / decision
        ↓
Farm Event Engine
        ↓
BEFORE → DURING → AFTER
        ↓
Evidence Package
        ↓
SHA-256 integrity hash
```

## Simulator APIs

- `GET /api/simulator/status`
- `POST /api/simulator/start`
- `POST /api/simulator/stop`
- `POST /api/simulator/scenario`
- `POST /api/simulator/step`
- `POST /api/simulator/evaluate`

The `/api/simulator/evaluate` endpoint requires an explicit visual prediction. It does not fabricate an image-model result. Production image inference remains `POST /api/analysis/image`.

## Farm state / event APIs

- `GET /api/farms/{farm_id}/state`
- `GET /api/farms/{farm_id}/zones/{zone_id}/state`
- `GET /api/events`
- `GET /api/events/active`
- `GET /api/events/{event_id}`
- `GET /api/events/{event_id}/timeline`
- `GET /api/events/{event_id}/evidence`
- `POST /api/evidence/verify?event_id=...`

## Scenarios

- `NORMAL`
- `DEVELOPING_STRESS`
- `DISEASE_RISK`
- `SEVERE_EVENT`
- `RECOVERY`

The scenario generator supports production-oriented optional fields such as soil temperature, soil pH, soil EC, leaf wetness, GNSS, gateway metadata and sequence numbers.

## Storage

SQLite remains the default. Event/evidence services are isolated so the persistence layer can later be moved to Supabase PostgreSQL without moving CRAI's intelligence logic.
