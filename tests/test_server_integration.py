# tests/test_server_integration.py
# Integration tests for the OpenMMComputeServer MCP functionalities

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

# Assuming the server instance and types are accessible for testing
# This might require adjustments based on how the server is structured for testability
from src.server import mcp_server, task_manager as global_task_manager # Direct import for simplicity
from mcp import types as mcp_types
from src.task_manager import Task # For creating mock task objects
from src.config import AppConfig # For task_manager if re-instantiated

import os
import json
import shutil
import uuid # For generating unique task IDs for tests

# For mocking engines and config within TaskManager for server tests
from src.task_manager import TaskManager
from src.config import AppConfig
from src.openmm_engine import OpenMMEngine
from src.abacus_engine import AbacusEngine

# For using TestClient with FastAPI/Starlette based apps
from fastapi.testclient import TestClient


# Placeholder for actual task_id that might be created during tests
# TEST_TASK_ID = "test-integration-task-123" # Not needed if tasks are created per test

# Scope event_loop to session to avoid issues if some fixtures are module/session scoped
@pytest.fixture(scope="session")
def event_loop():
    """Overrides pytest-asyncio default event_loop to be session-scoped."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function") # Changed to function scope for cleaner tests
def test_integration_app_config(tmp_path_factory):
    """Provides an AppConfig instance pointing to a temporary TASK_DATA_DIR for server integration tests."""
    data_dir = tmp_path_factory.mktemp("server_integration_test_data")
    class TestIntegrationConfig(AppConfig):
        def __init__(self):
            super().__init__()
            self.TASK_DATA_DIR = str(data_dir)
            self.MAX_CONCURRENT_TASKS = 1 # Simplify concurrency for tests
            self.LOG_LEVEL = "DEBUG"

    config = TestIntegrationConfig()
    if not os.path.exists(config.TASK_DATA_DIR):
        os.makedirs(config.TASK_DATA_DIR)
    return config

@pytest.fixture(scope="function") # Changed to function scope
def patched_task_manager_for_server(test_integration_app_config, mocker):
    """
    Provides a REAL TaskManager instance configured with a test AppConfig and MOCKED engines.
    This TaskManager instance is then patched into src.server.task_manager.
    """
    # Mock OpenMMEngine methods
    mock_openmm_engine = AsyncMock(spec=OpenMMEngine)
    mock_openmm_engine.setup_system = AsyncMock(return_value=(MagicMock(), MagicMock(), MagicMock()))
    mock_simulation_obj = AsyncMock()
    mock_simulation_obj.reporters = []
    mock_openmm_engine.create_simulation = AsyncMock(return_value=mock_simulation_obj)
    mock_openmm_engine.run_simulation_steps = AsyncMock() # Simulate steps completing fast
    mock_openmm_engine.get_current_state_info = AsyncMock(return_value={"potential_energy": -12345.0}) # Example result
    # Add other necessary mocks if TaskManager calls them during the tool operations

    # Mock AbacusEngine methods
    mock_abacus_engine = AsyncMock(spec=AbacusEngine)
    mock_abacus_engine.prepare_input = AsyncMock(return_value={"input_files": ["INPUT"], "work_dir": "dummy"})
    mock_abacus_engine.run_calculation = AsyncMock(return_value={"status": "completed", "message": "Mock Abacus run finished."})
    mock_abacus_engine.get_results = AsyncMock(return_value={"total_energy": -500.0, "converged": True})

    # Patch the global app_config imported by task_manager.py
    # Patch the engine classes imported by task_manager.py
    with patch('src.task_manager.app_config', test_integration_app_config), \
         patch('src.task_manager.OpenMMEngine', return_value=mock_openmm_engine), \
         patch('src.task_manager.AbacusEngine', return_value=mock_abacus_engine):

        # Create a real TaskManager instance; it will use the patched config and mocked engines
        real_tm_instance = TaskManager()

        # Now, patch this specific, configured TaskManager instance into src.server
        with patch('src.server.task_manager', real_tm_instance) as patched_tm_in_server:
            yield patched_tm_in_server # This is what tests will use if they need to inspect the TM

    # Cleanup the temporary directory after tests using this fixture are done
    if os.path.exists(test_integration_app_config.TASK_DATA_DIR):
        shutil.rmtree(test_integration_app_config.TASK_DATA_DIR)


@pytest.fixture(scope="function")
def test_client(patched_task_manager_for_server):
    """
    Provides a TestClient for the mcp_server, ensuring the server uses
    a TaskManager with mocked engines and a test-specific data directory.
    """
    # mcp_server from src.server will now use the patched_task_manager_for_server
    from src.server import mcp_server # mcp_server is initialized when src.server is imported
                                      # Patches must be active before this import happens effectively
                                      # or ensure mcp_server re-evaluates its task_manager if it's global
    
    # The patching of src.server.task_manager should ensure this client interacts
    # with the correctly patched TaskManager.
    client = TestClient(mcp_server.sse_app())
    return client


@pytest.mark.asyncio
# Class structure removed for simplicity with function-scoped fixtures
# async def test_list_tools(test_client: TestClient): # Old test using MagicMock TM
async def test_list_tools_integration(test_client: TestClient): # Renamed for clarity
    """Test the list_tools MCP method via HTTP client."""
    response = test_client.post("/mcp/list_tools", json={}) # Assuming POST, adjust if GET
    assert response.status_code == 200
    tools = response.json().get("tools", []) # Assuming FastMCP wraps result in "tools"
    assert isinstance(tools, list)
    # Based on current server.py, we expect 4 tools
    assert len(tools) >= 4
    tool_names = [tool["name"] for tool in tools]
    assert "create_md_simulation" in tool_names
    assert "create_dft_calculation" in tool_names


@pytest.mark.asyncio
async def test_create_md_simulation_tool_call_integration(test_client: TestClient, patched_task_manager_for_server: TaskManager):
    """Test calling create_md_simulation tool via HTTP client and verify backend state."""
    # Arguments should match CREATE_MD_SIMULATION_SCHEMA
    # from src.tools.create_md_simulation import CREATE_MD_SIMULATION_SCHEMA # For reference
    md_args = {
        "pdb_file": "ATOM...", # Minimal PDB content
        "pdb_input_type": "content", # Explicitly set
        "forcefield": ["amber14-all.xml"], # Schema expects array
        "steps": 10,
        "integrator": {"type": "LangevinMiddle", "temperature_K": 300, "step_size_ps": 0.001},
        # Optional fields, add if schema requires or for more thoroughness:
        # "platform_name": "CPU",
        # "output_config": {"state_data_reporter": {"file": "stdout", "reportInterval": 1}}
    }

    request_payload = {
        "tool_name": "create_md_simulation",
        "arguments": md_args
    }

    response = test_client.post("/mcp/call_tool", json=request_payload)
    assert response.status_code == 200

    response_json = response.json()
    # Assuming ToolResult structure { "status_code": 0, "data": {"task_id": ..., "message": ...}}
    assert response_json.get("status_code") == 0
    assert "data" in response_json
    task_id = response_json["data"].get("task_id")
    assert isinstance(task_id, str)

    # Verify task creation in the (patched) TaskManager
    assert task_id in patched_task_manager_for_server._tasks
    task_obj = patched_task_manager_for_server._tasks[task_id]
    assert task_obj.task_type == "md"
    assert task_obj.status == "pending"
    assert task_obj.config["steps"] == 10 # Check one of the args

    # Verify task_info.json persistence
    task_dir = os.path.join(patched_task_manager_for_server._app_config.TASK_DATA_DIR, task_id)
    assert os.path.isdir(task_dir)
    task_info_file = os.path.join(task_dir, "task_info.json")
    assert os.path.isfile(task_info_file)
    with open(task_info_file, 'r') as f:
        saved_data = json.load(f)
    assert saved_data["task_id"] == task_id
    assert saved_data["task_type"] == "md"
    assert saved_data["config"]["steps"] == 10

# Remove or adapt other tests from the old TestServerIntegration class for now,
# as they relied on direct server method calls and a fully mocked TaskManager.
# This new structure focuses on HTTP client interaction with a real TaskManager (mocked engines).