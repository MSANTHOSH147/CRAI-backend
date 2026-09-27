from fastapi import APIRouter, HTTPException
from app.schemas.observation import ObservationCreateRequest, ObservationAssociateRequest, ObservationQueueRequest
from app.services.observation_service import (
    create_observation, get_observation, list_observations, update_observation,
    associate_event, attach_visual_evidence, attach_sensor_evidence,
    enqueue_observation, retry_observation, list_queue, build_observation_graph
)

router = APIRouter(prefix="/api/observations", tags=["observations"])


@router.post("")
def create(request: ObservationCreateRequest):
    try:
        record, duplicate = create_observation(**request.model_dump())
        return {"ok": True, "duplicate": duplicate, "observation": record}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{observation_id}")
def get(observation_id: str):
    record = get_observation(observation_id)
    if not record:
        raise HTTPException(status_code=404, detail="Observation not found")
    graph = build_observation_graph(observation_id)
    return {"ok": True, **graph}


@router.get("/farm/{farm_id}")
def farm(farm_id: str):
    return {"ok": True, "observations": list_observations(farm_id=farm_id)}


@router.get("/zone/{zone_id}")
def zone(zone_id: str):
    return {"ok": True, "observations": list_observations(zone_id=zone_id)}


@router.get("/event/{event_id}")
def event(event_id: str):
    return {"ok": True, "observations": list_observations(event_id=event_id)}


@router.post("/{observation_id}/associate")
def associate(observation_id: str, request: ObservationAssociateRequest):
    if not get_observation(observation_id):
        raise HTTPException(status_code=404, detail="Observation not found")
    result = None
    if request.event_id:
        result = associate_event(observation_id, request.event_id)
    if request.image_id:
        result = attach_visual_evidence(observation_id, request.image_id)
    if request.sensor_id:
        result = attach_sensor_evidence(observation_id, request.sensor_id)
    if not result:
        result = get_observation(observation_id)
    return {"ok": True, "observation": result}


@router.post("/{observation_id}/queue")
def queue(observation_id: str, request: ObservationQueueRequest):
    try:
        item, duplicate = enqueue_observation(observation_id, request.file_reference)
        return {"ok": True, "duplicate": duplicate, "queue": item}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{observation_id}/retry")
def retry(observation_id: str):
    item = retry_observation(observation_id)
    if not item:
        raise HTTPException(status_code=404, detail="No queue item found")
    return {"ok": True, "queue": item, "observation": get_observation(observation_id)}


@router.get("/{observation_id}/queue")
def queue_status(observation_id: str):
    return {"ok": True, "queue": list_queue(observation_id)}
