from app.services.observation_service import (
    clear_test_data, create_observation, get_observation, build_observation_graph,
    enqueue_observation, retry_observation
)

def test_observation_create_and_idempotency(tmp_path):
    clear_test_data()
    first, duplicate1 = create_observation("1", "A1", "UAV", "FIELD", observation_id="OBS-TEST-1")
    second, duplicate2 = create_observation("1", "A1", "UAV", "FIELD", observation_id="OBS-TEST-1")
    assert duplicate1 is False
    assert duplicate2 is True
    assert first["observation_id"] == second["observation_id"]

def test_uav_phone_parent_relationship():
    clear_test_data()
    uav, _ = create_observation("1", "A1", "UAV", "FIELD", observation_id="OBS-UAV-1")
    phone, _ = create_observation("1", "A1", "PHONE", "PLANT", parent_observation_id=uav["observation_id"], observation_id="OBS-PHONE-1")
    graph = build_observation_graph(uav["observation_id"])
    assert phone["parent_observation_id"] == uav["observation_id"]
    assert graph["children"][0]["observation_id"] == "OBS-PHONE-1"

def test_offline_queue_and_retry():
    clear_test_data()
    obs, _ = create_observation("1", "A1", "PHONE", "PLANT", observation_id="OBS-QUEUE-1")
    item, duplicate = enqueue_observation(obs["observation_id"], "local://image.jpg")
    assert duplicate is False
    assert item["status"] == "PENDING"
    retried = retry_observation(obs["observation_id"])
    assert retried["status"] == "UPLOADED"
    assert retried["attempt_count"] == 1
    assert get_observation(obs["observation_id"])["status"] == "UPLOADED"
