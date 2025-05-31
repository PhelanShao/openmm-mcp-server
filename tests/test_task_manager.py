# tests/test_task_manager.py

import asyncio
import os
import shutil
import json
import unittest
from unittest.mock import patch, MagicMock, AsyncMock, call

# Ensure imports for TaskManager and its dependencies are correct
# Adjust based on your project structure if TaskManager is not directly in src
try:
    from src.task_manager import TaskManager, Task
    from src.config import config as app_config
    from src.openmm_engine import OpenMMEngine # For mocking its methods
except ImportError as e:
    print(f"Error importing modules for test_task_manager: {e}")
    # Fallback mocks if imports fail (e.g., in a CI environment without full setup)
    TaskManager = MagicMock()
    Task = MagicMock()
    app_config = MagicMock()
    app_config.TASK_DATA_DIR = "test_task_data" # Default for tests
    OpenMMEngine = MagicMock()

# Dummy PDB content for task configurations
DUMMY_PDB_CONTENT_FOR_TASK = "ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  0.00           N\n"
DEFAULT_TASK_CONFIG = {
    "pdb_input_type": "content",
    "pdb_data": DUMMY_PDB_CONTENT_FOR_TASK,
    "forcefield_files": ["amber14-all.xml"],
    "steps": 100,
    "integrator": {"type": "LangevinMiddle", "temperature_K": 300, "step_size_ps": 0.001},
    "platform_name": "CPU",
    "output_config": {
        "dcd_reporter": {"file": "trajectory.dcd", "reportInterval": 10},
        "state_data_reporter": {"file": "stdout", "reportInterval": 10}
    }
}


class TestTaskManager(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        """Set up for each test: ensure a clean task data directory."""
        self.test_task_data_dir = "test_task_data_taskmanager"
        app_config.TASK_DATA_DIR = self.test_task_data_dir # Override config for tests
        if os.path.exists(self.test_task_data_dir):
            shutil.rmtree(self.test_task_data_dir)
        os.makedirs(self.test_task_data_dir, exist_ok=True)

        # Patch OpenMMEngine to avoid actual OpenMM calls during TaskManager tests
        self.openmm_engine_patcher = patch('src.task_manager.OpenMMEngine', spec=OpenMMEngine)
        self.MockOpenMMEngineClass = self.openmm_engine_patcher.start()
        self.mock_engine_instance = self.MockOpenMMEngineClass.return_value

        # Configure async methods of the mocked engine instance
        self.mock_engine_instance.setup_system = AsyncMock(return_value=(MagicMock(), MagicMock(), MagicMock()))
        self.mock_engine_instance.create_simulation = AsyncMock(return_value=MagicMock())
        self.mock_engine_instance.set_initial_positions = AsyncMock()
        self.mock_engine_instance.configure_reporters = AsyncMock()
        self.mock_engine_instance.minimize_energy = AsyncMock()
        self.mock_engine_instance.set_velocities_to_temperature = AsyncMock()
        self.mock_engine_instance.run_simulation_steps = AsyncMock()
        self.mock_engine_instance.get_current_state_info = AsyncMock(return_value={"energy": -100.0})
        self.mock_engine_instance.save_checkpoint = AsyncMock()
        self.mock_engine_instance.cleanup_simulation = AsyncMock()
        
        self.task_manager = TaskManager() # Initialize TaskManager after patching OpenMMEngine

    def tearDown(self):
        """Clean up after each test."""
        self.openmm_engine_patcher.stop()
        if os.path.exists(self.test_task_data_dir):
            shutil.rmtree(self.test_task_data_dir)

    async def test_create_task_success(self):
        """Test successful task creation and initial save."""
        task_id = await self.task_manager.create_task(DEFAULT_TASK_CONFIG)
        self.assertIn(task_id, self.task_manager._tasks)
        task = self.task_manager._tasks[task_id]
        self.assertEqual(task.status, "pending")
        
        # Verify task_info.json was created
        task_info_path = os.path.join(self.test_task_data_dir, task_id, "task_info.json")
        self.assertTrue(os.path.exists(task_info_path))
        with open(task_info_path, 'r') as f:
            saved_data = json.load(f)
        self.assertEqual(saved_data["task_id"], task_id)
        self.assertEqual(saved_data["status"], "pending")

    async def test_create_task_missing_fields_failure(self):
        """Test task creation failure due to missing required fields."""
        incomplete_config = {"steps": 100}
        with self.assertRaisesRegex(ValueError, "Task configuration missing required fields"):
            await self.task_manager.create_task(incomplete_config)

    async def test_start_task_and_run_simulation_flow(self):
        """Test the basic flow of starting a task and its simulation run (mocked)."""
        task_id = await self.task_manager.create_task(DEFAULT_TASK_CONFIG)
        
        # Mock _save_task_to_disk to check its calls without actual file I/O during this test part
        self.task_manager._save_task_to_disk = AsyncMock()

        await self.task_manager.start_task(task_id)
        
        # Allow the task to run (it's mocked, so it should be quick)
        # We need to ensure the asyncio task created by start_task gets a chance to run.
        # For a fully mocked _run_simulation_task, this might not be strictly necessary,
        # but if _run_simulation_task itself has awaits, we need to let them proceed.
        if self.task_manager._tasks[task_id].async_task_handle:
             try:
                await asyncio.wait_for(self.task_manager._tasks[task_id].async_task_handle, timeout=1.0)
             except asyncio.TimeoutError:
                self.fail("_run_simulation_task did not complete in time (mocked scenario).")

        task = self.task_manager._tasks[task_id]
        # Check if status progressed as expected (mocked engine calls)
        # The exact status depends on how _run_simulation_task is mocked or proceeds.
        # With the current full mock of OpenMMEngine, _run_simulation_task will complete quickly.
        self.assertIn(task.status, ["completed", "running"]) # It might be "completed" if mocked run is instant

        # Verify OpenMMEngine methods were called
        self.mock_engine_instance.setup_system.assert_called_once()
        self.mock_engine_instance.create_simulation.assert_called_once()
        self.mock_engine_instance.set_initial_positions.assert_called_once()
        self.mock_engine_instance.configure_reporters.assert_called_once()
        # minimize_energy is optional, check if config had it
        if DEFAULT_TASK_CONFIG.get("minimize_energy", False):
             self.mock_engine_instance.minimize_energy.assert_called_once()
        self.mock_engine_instance.run_simulation_steps.assert_called() # Called at least once
        self.mock_engine_instance.get_current_state_info.assert_called_once()
        self.mock_engine_instance.cleanup_simulation.assert_called_once()

        # Check if _save_task_to_disk was called for status/progress updates
        # This requires more intricate mocking of Task.update_status/progress or checking save calls
        self.assertTrue(self.task_manager._save_task_to_disk.called)
        # Example: check for specific status saves
        # calls = [
        #     call(unittest.mock.ANY), # For "initializing"
        #     call(unittest.mock.ANY), # For "running"
        #     call(unittest.mock.ANY), # For progress
        #     call(unittest.mock.ANY)  # For "completed" / results
        # ]
        # self.task_manager._save_task_to_disk.assert_has_calls(calls, any_order=False)


    async def test_pause_stop_task(self):
        """Test pausing and stopping a task."""
        task_id = await self.task_manager.create_task(DEFAULT_TASK_CONFIG)
        task = self.task_manager._tasks[task_id]

        # Start the task (it will run in the background)
        async def dummy_run_sim(task_obj): # A mock for _run_simulation_task
            self.task_manager.logger.info(f"Dummy run for {task_obj.task_id} started.")
            while task_obj.status == "running":
                await asyncio.sleep(0.01) # Simulate work
            self.task_manager.logger.info(f"Dummy run for {task_obj.task_id} ended with status {task_obj.status}.")

        with patch.object(self.task_manager, '_run_simulation_task', new=dummy_run_sim):
            await self.task_manager.start_task(task_id)
            await asyncio.sleep(0.05) # Let it start running
            self.assertEqual(task.status, "running")

            await self.task_manager.pause_task(task_id)
            self.assertEqual(task.status, "paused")
            task_info_path = os.path.join(self.test_task_data_dir, task_id, "task_info.json")
            with open(task_info_path, 'r') as f: saved_data = json.load(f)
            self.assertEqual(saved_data["status"], "paused")

            await self.task_manager.resume_task(task_id) # This will call start_task again
            await asyncio.sleep(0.05)
            self.assertEqual(task.status, "running")

            await self.task_manager.stop_task(task_id)
            self.assertEqual(task.status, "stopped")
            with open(task_info_path, 'r') as f: saved_data = json.load(f)
            self.assertEqual(saved_data["status"], "stopped")
            
            # Ensure the async task handle is cancelled or completed
            if task.async_task_handle:
                self.assertTrue(task.async_task_handle.done())


    async def test_delete_task(self):
        """Test deleting a task."""
        task_id = await self.task_manager.create_task(DEFAULT_TASK_CONFIG)
        self.assertIn(task_id, self.task_manager._tasks)
        task_dir = os.path.join(self.test_task_data_dir, task_id)
        self.assertTrue(os.path.exists(task_dir))

        await self.task_manager.delete_task(task_id)
        self.assertNotIn(task_id, self.task_manager._tasks)
        self.assertFalse(os.path.exists(task_dir)) # Check if directory is deleted

    async def test_load_tasks_from_disk_on_init(self):
        """Test that tasks are loaded from disk when TaskManager is initialized."""
        # 1. Create a dummy task file manually
        task_id = "test-load-task-123"
        task_dir = os.path.join(self.test_task_data_dir, task_id)
        os.makedirs(task_dir, exist_ok=True)
        task_info_file = os.path.join(task_dir, "task_info.json")
        
        dummy_task_data = {
            "task_id": task_id,
            "config": DEFAULT_TASK_CONFIG,
            "status": "completed",
            "progress": {"current_step": 100, "total_steps": 100},
            "results": {"energy": -200.0},
            "error_message": None
        }
        with open(task_info_file, 'w') as f:
            json.dump(dummy_task_data, f)

        # 2. Create another task that was "running"
        task_id_running = "test-load-task-running-456"
        task_dir_running = os.path.join(self.test_task_data_dir, task_id_running)
        os.makedirs(task_dir_running, exist_ok=True)
        task_info_file_running = os.path.join(task_dir_running, "task_info.json")
        dummy_task_running_data = {
            "task_id": task_id_running, "config": DEFAULT_TASK_CONFIG, "status": "running",
            "progress": {"current_step": 50, "total_steps": 100}, "results": None, "error_message": None
        }
        with open(task_info_file_running, 'w') as f:
            json.dump(dummy_task_running_data, f)
        
        # 3. Initialize a new TaskManager - it should load these tasks
        new_task_manager = TaskManager() # _load_tasks_from_disk is called in __init__
        
        self.assertIn(task_id, new_task_manager._tasks)
        loaded_task = new_task_manager._tasks[task_id]
        self.assertEqual(loaded_task.status, "completed")
        self.assertEqual(loaded_task.results["energy"], -200.0)

        self.assertIn(task_id_running, new_task_manager._tasks)
        loaded_running_task = new_task_manager._tasks[task_id_running]
        self.assertEqual(loaded_running_task.status, "interrupted") # Should be reset
        # Check if the interrupted task was re-saved with the new status
        with open(task_info_file_running, 'r') as f:
            re_saved_data = json.load(f)
        self.assertEqual(re_saved_data["status"], "interrupted")


    # TODO: Add more tests for edge cases in persistence (corrupted files, etc.)
    # TODO: Add tests for _process_output_paths
    # TODO: Add tests for concurrency limiting with semaphore if possible to test reliably

if __name__ == '__main__':
    # This allows running tests directly from this file
    # Ensure src is in PYTHONPATH or run with `python -m unittest tests.test_task_manager`
    unittest.main()