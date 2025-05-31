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

# Placeholder for actual task_id that might be created during tests
TEST_TASK_ID = "test-integration-task-123"

@pytest.fixture(scope="module")
def event_loop():
    """Overrides pytest-asyncio default event_loop to be module-scoped."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()

@pytest.fixture(scope="module")
async def test_app_config():
    """Provides a test AppConfig."""
    # Use default config or override as needed for tests
    return AppConfig()

@pytest.fixture(scope="module")
async def mock_task_manager_module(test_app_config):
    """
    Mocks the TaskManager instance used by the server for isolated testing.
    This fixture ensures that the global_task_manager in src.server is patched
    for the duration of the tests in this module.
    """
    if global_task_manager is None:
        # If the global_task_manager failed to initialize, we create a mock one for tests.
        # This situation should ideally be handled by ensuring server.py can always provide one,
        # or by directly instantiating one here for tests.
        # For now, let's assume we always want to patch it for controlled tests.
        pass

    mock_tm = MagicMock(spec=global_task_manager.__class__ if global_task_manager else MagicMock()) # Mock based on actual class if available
    
    # --- Mock TaskManager methods that will be called by server ---
    # create_task
    mock_tm.create_task = AsyncMock(return_value=TEST_TASK_ID)
    
    # control_simulation actions (start, pause, resume, stop, delete)
    mock_tm.start_task = AsyncMock(return_value=mcp_types.ToolResult(content={"status": "started", "task_id": TEST_TASK_ID}))
    mock_tm.pause_task = AsyncMock(return_value=mcp_types.ToolResult(content={"status": "paused", "task_id": TEST_TASK_ID}))
    mock_tm.resume_task = AsyncMock(return_value=mcp_types.ToolResult(content={"status": "resumed", "task_id": TEST_TASK_ID}))
    mock_tm.stop_task = AsyncMock(return_value=mcp_types.ToolResult(content={"status": "stopped", "task_id": TEST_TASK_ID}))
    mock_tm.delete_task = AsyncMock(return_value=mcp_types.ToolResult(content={"message": "Task deleted", "task_id": TEST_TASK_ID}))

    # get_task_status
    mock_tm.get_task_status = AsyncMock(return_value={"task_id": TEST_TASK_ID, "status": "completed", "progress": 100})
    
    # get_task_results
    mock_tm.get_task_results = AsyncMock(return_value={"task_id": TEST_TASK_ID, "data": {"energy": -1000}})
    
    # get_task_trajectory_file_path (or similar method that resource handler would use)
    # The trajectory resource handler in server.py calls read_trajectory_file_resource,
    # which itself might call something on task_manager or directly access files.
    # For simplicity, let's assume read_trajectory_file_resource is self-contained enough
    # or we mock the part of task_manager it relies on if it calls back.
    # If read_trajectory_file_resource directly calls task_manager.get_task_by_id().output_files['trajectory']
    mock_task = MagicMock(spec=Task)
    mock_task.task_id = TEST_TASK_ID
    mock_task.status = "completed"
    mock_task.output_files = {"trajectory_dcd": "path/to/fake.dcd"} # Example
    mock_tm.get_task_by_id = MagicMock(return_value=mock_task)


    # Patch the task_manager instance within the server module
    with patch('src.server.task_manager', new=mock_tm):
        yield mock_tm
    # Patching global_task_manager directly if it's the one used:
    # with patch.object(src.server, 'task_manager', new=mock_tm):
    #    yield mock_tm


@pytest.mark.asyncio
class TestServerIntegration:
    """Test suite for MCP server integration points."""

    async def test_list_tools(self, mock_task_manager_module):
        """Test the list_tools MCP method."""
        tools = await mcp_server.list_tools()
        assert isinstance(tools, list)
        assert len(tools) >= 3 # create_md_simulation, control_simulation, analyze_results
        tool_names = [tool.name for tool in tools]
        assert "create_md_simulation" in tool_names
        assert "control_simulation" in tool_names
        assert "analyze_results" in tool_names

    async def test_list_resources(self, mock_task_manager_module):
        """Test the list_resources MCP method."""
        resources = await mcp_server.list_resources()
        assert isinstance(resources, list)
        assert len(resources) >= 3 # status, results, trajectory
        resource_uris = [res.uri for res in resources]
        # These are templates, so direct match might be tricky. Check for key parts.
        assert any("tasks/{task_id}/status" in uri for uri in resource_uris)
        assert any("tasks/{task_id}/results" in uri for uri in resource_uris)
        assert any("tasks/{task_id}/trajectory" in uri for uri in resource_uris)

    # --- Tool Calling Tests ---
    async def test_call_create_md_simulation(self, mock_task_manager_module):
        """Test calling the create_md_simulation tool."""
        args = {
            "pdb_content": "ATOM...", "forcefields": ["amber14-all.xml"], "temperature": 298.0,
            "integrator": {"type": "LangevinMiddle", "dt_ps": 0.002, "friction_coeff_inv_ps": 1.0},
            "simulation_steps": 1000, "report_interval_steps": 100,
            "output_options": {"dcd": True, "xtc": False, "state_data": True, "checkpoint": True}
        }
        result = await mcp_server.call_tool(name="create_md_simulation", arguments=args)
        assert isinstance(result, mcp_types.ToolResult)
        # The tool run_create_md_simulation returns a dict with task_id
        assert result.content["task_id"] == TEST_TASK_ID
        mock_task_manager_module.create_task.assert_called_once()
        # Further assertions on args passed to create_task can be added

    async def test_call_control_simulation_start(self, mock_task_manager_module):
        """Test calling control_simulation tool with 'start' action."""
        args = {"task_id": TEST_TASK_ID, "action": "start"}
        result = await mcp_server.call_tool(name="control_simulation", arguments=args)
        assert isinstance(result, mcp_types.ToolResult)
        assert result.content["status"] == "started"
        mock_task_manager_module.start_task.assert_called_once_with(TEST_TASK_ID)

    async def test_call_analyze_results_energy(self, mock_task_manager_module):
        """Test calling analyze_results tool for energy."""
        # Mock the get_task_results part of analyze_results if it's complex
        # For now, assume run_analyze_results calls task_manager.get_task_results
        mock_task_manager_module.get_task_results.return_value = {
            "energy_kj_mol": -12345.6, "temperature_k": 298.1
        }
        args = {"task_id": TEST_TASK_ID, "analysis_type": "energy"}
        result = await mcp_server.call_tool(name="analyze_results", arguments=args)
        assert isinstance(result, mcp_types.ToolResult)
        assert "energy_summary" in result.content
        assert result.content["energy_summary"]["energy_kj_mol"] == -12345.6
        mock_task_manager_module.get_task_results.assert_called_once_with(TEST_TASK_ID)


    # --- Resource Reading Tests ---
    async def test_read_task_status_resource(self, mock_task_manager_module):
        """Test reading the task_status resource."""
        uri = f"openmm://tasks/{TEST_TASK_ID}/status"
        content, mime_type = await mcp_server.read_resource(uri=uri)
        
        assert mime_type == "application/json"
        import json
        data = json.loads(content.decode())
        assert data["task_id"] == TEST_TASK_ID
        assert data["status"] == "completed"
        mock_task_manager_module.get_task_status.assert_called_once_with(TEST_TASK_ID)

    async def test_read_calculation_results_resource(self, mock_task_manager_module):
        """Test reading the calculation_results resource."""
        uri = f"openmm://tasks/{TEST_TASK_ID}/results"
        content, mime_type = await mcp_server.read_resource(uri=uri)

        assert mime_type == "application/json"
        import json
        data = json.loads(content.decode())
        assert data["task_id"] == TEST_TASK_ID
        assert data["data"]["energy"] == -1000
        mock_task_manager_module.get_task_results.assert_called_once_with(TEST_TASK_ID)

    @patch('src.resources.trajectory_file_resource.open', new_callable=MagicMock)
    @patch('src.resources.trajectory_file_resource.os.path.exists', return_value=True)
    @patch('src.resources.trajectory_file_resource.os.path.getsize', return_value=1024)
    async def test_read_trajectory_file_resource(self, mock_getsize, mock_exists, mock_open_file, mock_task_manager_module):
        """Test reading the trajectory_file resource."""
        # This test is more complex due to file I/O.
        # We need to mock where read_trajectory_file_resource gets the file path
        # and the file operations themselves.
        
        # Mock the file content that would be read
        mock_file_content = b"This is dummy DCD trajectory data."
        mock_open_file.return_value.__enter__.return_value.read = MagicMock(return_value=mock_file_content)

        # The trajectory_file_resource.py uses task_manager.get_task_by_id(task_id)
        # to find the task and then task.output_files.get('trajectory_dcd') or similar.
        # This is already mocked in mock_task_manager_module fixture.
        
        uri = f"openmm://tasks/{TEST_TASK_ID}/trajectory" # This URI is handled by read_trajectory_file_resource
        
        content, mime_type = await mcp_server.read_resource(uri=uri)

        assert content == mock_file_content
        assert mime_type == "application/octet-stream" # or specific DCD/XTC type if detected
        
        # Check if task_manager.get_task_by_id was called by the resource handler
        mock_task_manager_module.get_task_by_id.assert_called_once_with(TEST_TASK_ID)
        # Check if os.path.exists and open were called with the expected path
        expected_path = "path/to/fake.dcd" # From mock_task_manager_module
        mock_exists.assert_called_once_with(expected_path)
        mock_open_file.assert_called_once_with(expected_path, 'rb')


    async def test_read_resource_not_found(self, mock_task_manager_module):
        """Test reading a non-existent resource URI."""
        uri = "openmm://tasks/unknown_task_id/status"
        mock_task_manager_module.get_task_status.side_effect = mcp_types.ResourceNotFoundError("Task not found")
        
        with pytest.raises(mcp_types.ResourceNotFoundError):
            await mcp_server.read_resource(uri=uri)

        uri_invalid_type = f"openmm://tasks/{TEST_TASK_ID}/unknown_type"
        with pytest.raises(mcp_types.ResourceNotFoundError): # Or MCPError depending on server.py's dispatch
            await mcp_server.read_resource(uri=uri_invalid_type)
            
        uri_invalid_scheme = f"http://tasks/{TEST_TASK_ID}/status"
        with pytest.raises(mcp_types.ResourceNotFoundError):
            await mcp_server.read_resource(uri=uri_invalid_scheme)


    async def test_call_tool_not_found(self, mock_task_manager_module):
        """Test calling a non-existent tool."""
        with pytest.raises(mcp_types.ToolNotFoundError):
            await mcp_server.call_tool(name="non_existent_tool", arguments={})

    # TODO: Add tests for other control_simulation actions (pause, resume, stop, delete)
    # TODO: Add tests for other analyze_results types
    # TODO: Add tests for error conditions in tool calls (e.g., invalid arguments)
    # TODO: Add tests for byte_range handling in resource reading if applicable at this level

# To run these tests:
# Ensure pytest and pytest-asyncio are installed.
# From the project root: pytest tests/test_server_integration.py