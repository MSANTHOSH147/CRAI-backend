def test_phase5_observation_workflow_smoke():
    from app.services.observation_service import clear_test_data, create_observation, build_observation_graph
    clear_test_data()
    uav, _ = create_observation(
        farm_id="1", zone_id="A1", source="UAV", scale="FIELD",
        capture_mode="FIELD_SCAN", latitude=13.1, longitude=80.2,
        observation_id="OBS-UAV-DEMO"
    )
    phone, _ = create_observation(
        farm_id="1", zone_id="A1", source="PHONE", scale="PLANT",
        capture_mode="TARGETED_INSPECTION", latitude=13.1, longitude=80.2,
        parent_observation_id=uav["observation_id"],
        observation_id="OBS-PHONE-DEMO"
    )
    graph = build_observation_graph(uav["observation_id"])
    assert graph["observation"]["source"] == "UAV"
    assert graph["children"][0]["source"] == "PHONE"
    assert graph["children"][0]["parent_observation_id"] == "OBS-UAV-DEMO"
