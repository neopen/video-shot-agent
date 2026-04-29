from penshot.neopen.task.workflow_registry import WorkflowRegistry


def test_workflow_registry_reuses_cached_instance():
    registry = WorkflowRegistry(max_cache_size=2)
    workflow = object()

    registry.put("cfg-a", workflow)

    assert registry.get("cfg-a") is workflow
    assert registry.keys() == ["cfg-a"]


def test_workflow_registry_evicts_oldest_entry():
    registry = WorkflowRegistry(max_cache_size=2)

    registry.put("cfg-a", "workflow-a")
    registry.put("cfg-b", "workflow-b")
    registry.put("cfg-c", "workflow-c")

    assert registry.get("cfg-a") is None
    assert registry.get("cfg-b") == "workflow-b"
    assert registry.get("cfg-c") == "workflow-c"
