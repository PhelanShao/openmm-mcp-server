import pytest
import asyncio
import os
import json
import uuid
import shutil
from unittest.mock import AsyncMock, MagicMock, patch

# Module to be tested
from src.task_manager import TaskManager, Task
from src.config import AppConfig
from src.openmm_engine import OpenMMEngine # To mock its methods
from src.abacus_engine import AbacusEngine # To mock its methods

# --- Test Configuration & Fixtures ---

@pytest.fixture
def test_data_dir(tmp_path_factory):
    """Creates a temporary data directory for testing."""
    data_dir = tmp_path_factory.mktemp("task_manager_test_data")
    return data_dir

@pytest.fixture
def test_app_config(test_data_dir):
    """Provides an AppConfig instance pointing to a temporary TASK_DATA_DIR."""
    class TestConfig(AppConfig):
        def __init__(self):
            super().__init__()
            self.TASK_DATA_DIR = str(test_data_dir)
            self.MAX_CONCURRENT_TASKS = 2
            self.LOG_LEVEL = "DEBUG"
    config = TestConfig()
    if not os.path.exists(config.TASK_DATA_DIR): # Ensure dir exists
        os.makedirs(config.TASK_DATA_DIR)
    return config

@pytest.fixture
async def task_manager_instance(test_app_config, mocker):
    """
    Provides a TaskManager instance with mocked engines and clean data directory.
    Also handles cleanup of the TASK_DATA_DIR.
    """
    mock_openmm_engine = AsyncMock(spec=OpenMMEngine)
    mock_openmm_engine.setup_system = AsyncMock(return_value=(MagicMock(), MagicMock(), MagicMock()))
    mock_simulation_obj = AsyncMock()
    mock_simulation_obj.reporters = []
    mock_openmm_engine.create_simulation = AsyncMock(return_value=mock_simulation_obj)
    mock_openmm_engine.configure_reporters = AsyncMock()
    mock_openmm_engine.minimize_energy = AsyncMock()
    mock_openmm_engine.run_simulation_steps = AsyncMock()
    mock_openmm_engine.get_current_state_info = AsyncMock(return_value={"energy": 0.0})
    mock_openmm_engine.save_checkpoint = AsyncMock()
    mock_openmm_engine.cleanup_simulation = AsyncMock()

    mock_abacus_engine = AsyncMock(spec=AbacusEngine)
    mock_abacus_engine.prepare_input = AsyncMock(return_value={"input_files": ["INPUT"], "work_dir": "dummy_work_dir"})
    mock_abacus_engine.run_calculation = AsyncMock(return_value={"status": "completed", "message": "Mock Abacus run finished."})
    mock_abacus_engine.get_results = AsyncMock(return_value={"energy": -100.0})
    mock_abacus_engine.cleanup_calculation = AsyncMock()

    # Patch the global app_config imported by task_manager.py
    # and the engine classes themselves at the point of import by task_manager.py
    with patch('src.task_manager.app_config', test_app_config), \
         patch('src.task_manager.OpenMMEngine', return_value=mock_openmm_engine) as mocked_omm_constructor, \
         patch('src.task_manager.AbacusEngine', return_value=mock_abacus_engine) as mocked_abacus_constructor:
        
        tm = TaskManager()
        # The TaskManager's __init__ will use the patched app_config and create
        # instances of the (now mocked) OpenMMEngine and AbacusEngine.
        # We can assert that the constructors were called if needed.
        # mocked_omm_constructor.assert_called_once()
        # mocked_abacus_constructor.assert_called_once()
        # tm._openmm_engine and tm._abacus_engine are now the mocks.

    yield tm

    if os.path.exists(test_app_config.TASK_DATA_DIR):
        shutil.rmtree(test_app_config.TASK_DATA_DIR)

# --- Test Cases ---

@pytest.mark.asyncio
async def test_task_manager_initialization(task_manager_instance: TaskManager, test_app_config: AppConfig):
    assert task_manager_instance is not None
    assert task_manager_instance._app_config.TASK_DATA_DIR == test_app_config.TASK_DATA_DIR
    assert isinstance(task_manager_instance._openmm_engine, AsyncMock)
    assert isinstance(task_manager_instance._abacus_engine, AsyncMock)
    assert os.path.exists(test_app_config.TASK_DATA_DIR)

@pytest.mark.asyncio
async def test_create_md_task(task_manager_instance: TaskManager, test_app_config: AppConfig):
    tm = task_manager_instance
    md_config = {
        "task_type": "md", "pdb_file": "dummy_pdb_content",
        "forcefield_files": ["amber14-all.xml"], "steps": 1000,
        "integrator": {"type": "LangevinMiddle", "temperature_K": 300, "step_size_ps": 0.002},
        "output_config": {"dcd_reporter": {"file": "output.dcd", "reportInterval": 100}}
    }
    task_id = await tm.create_task(md_config)
    assert isinstance(task_id, str)
    assert task_id in tm._tasks
    task_obj = tm._tasks[task_id]
    assert task_obj.task_type == "md" and task_obj.status == "pending" and task_obj.config == md_config
    task_info_file = os.path.join(test_app_config.TASK_DATA_DIR, task_id, "task_info.json")
    assert os.path.isfile(task_info_file)
    with open(task_info_file, 'r') as f: saved_data = json.load(f)
    assert saved_data["task_id"] == task_id and saved_data["task_type"] == "md"

@pytest.mark.asyncio
async def test_create_dft_task(task_manager_instance: TaskManager, test_app_config: AppConfig):
    tm = task_manager_instance
    dft_config = {
        "task_type": "dft",
        "dft_params": {"input_structure": "Si", "calculation_parameters": {"kpoints": "4 4 4", "ecutwfc": 50}}
    }
    task_id = await tm.create_task(dft_config)
    assert isinstance(task_id, str)
    assert task_id in tm._tasks
    task_obj = tm._tasks[task_id]
    assert task_obj.task_type == "dft" and task_obj.status == "pending" and task_obj.config == dft_config
    task_info_file = os.path.join(test_app_config.TASK_DATA_DIR, task_id, "task_info.json")
    assert os.path.isfile(task_info_file)
    with open(task_info_file, 'r') as f: saved_data = json.load(f)
    assert saved_data["task_id"] == task_id and saved_data["task_type"] == "dft"

@pytest.mark.asyncio
async def test_task_persistence_and_load(test_app_config: AppConfig, mocker):
    md_config = {"task_type": "md", "pdb_file": "c", "forcefield_files": ["ff.xml"], "steps": 100}
    task_id_original = None
    original_task_data_dict = {}

    with patch('src.task_manager.app_config', test_app_config), \
         patch('src.task_manager.OpenMMEngine', return_value=AsyncMock(spec=OpenMMEngine)), \
         patch('src.task_manager.AbacusEngine', return_value=AsyncMock(spec=AbacusEngine)):
        tm1 = TaskManager()
        task_id_original = await tm1.create_task(md_config)
        original_task_data_dict = tm1._tasks[task_id_original].to_dict()

    with patch('src.task_manager.app_config', test_app_config), \
         patch('src.task_manager.OpenMMEngine', return_value=AsyncMock(spec=OpenMMEngine)), \
         patch('src.task_manager.AbacusEngine', return_value=AsyncMock(spec=AbacusEngine)):
        tm2 = TaskManager()
        assert task_id_original in tm2._tasks
        loaded_task = tm2._tasks[task_id_original]
        assert loaded_task.to_dict() == original_task_data_dict

@pytest.mark.asyncio
async def test_delete_task(task_manager_instance: TaskManager, test_app_config: AppConfig):
    tm = task_manager_instance
    md_config = {"task_type": "md", "pdb_file": "c", "forcefield_files": ["f"], "steps": 10}
    task_id = await tm.create_task(md_config)
    task_dir = os.path.join(test_app_config.TASK_DATA_DIR, task_id)
    assert os.path.isdir(task_dir)
    await tm.delete_task(task_id)
    assert task_id not in tm._tasks
    assert not os.path.exists(task_dir)

@pytest.mark.asyncio
async def test_interrupted_task_loading(test_app_config: AppConfig, mocker):
    task_id = str(uuid.uuid4())
    task_dir = os.path.join(test_app_config.TASK_DATA_DIR, task_id)
    os.makedirs(task_dir, exist_ok=True)
    config_for_interrupted = {"task_type": "md", "pdb_file": "test", "forcefield_files":["ff"], "steps": 100}
    task_info_content = {"task_id": task_id, "config": config_for_interrupted, "task_type": "md", "status": "running"}
    with open(os.path.join(task_dir, "task_info.json"), 'w') as f: json.dump(task_info_content, f)

    with patch('src.task_manager.app_config', test_app_config), \
         patch('src.task_manager.OpenMMEngine', return_value=AsyncMock(spec=OpenMMEngine)), \
         patch('src.task_manager.AbacusEngine', return_value=AsyncMock(spec=AbacusEngine)):
        tm = TaskManager()
        assert task_id in tm._tasks
        assert tm._tasks[task_id].status == "interrupted"
        with open(os.path.join(task_dir, "task_info.json"), 'r') as f: saved_data = json.load(f)
        assert saved_data["status"] == "interrupted"

@pytest.mark.asyncio
async def test_task_status_transitions_control(task_manager_instance: TaskManager, test_app_config: AppConfig):
    tm = task_manager_instance
    md_config = {"task_type": "md", "pdb_file": "c", "forcefield_files": ["f"], "steps": 100}
    task_id = await tm.create_task(md_config)
    task = tm._get_task_or_raise(task_id)

    async def short_sleep_then_return(*args, **kwargs): await asyncio.sleep(0.01)
    tm._openmm_engine.run_simulation_steps = short_sleep_then_return
    tm._abacus_engine.run_calculation = short_sleep_then_return # For DFT if tested similarly

    await tm.start_task(task_id)
    await asyncio.sleep(0.05) # Allow task to enter running/initializing
    assert task.status in ["running", "initializing"]

    await tm.pause_task(task_id)
    assert task.status == "paused"
    with open(os.path.join(test_app_config.TASK_DATA_DIR, task_id, "task_info.json"), 'r') as f: saved_data = json.load(f)
    assert saved_data["status"] == "paused"

    await tm.resume_task(task_id)
    await asyncio.sleep(0.05) # Allow task to resume
    assert task.status == "running"
    with open(os.path.join(test_app_config.TASK_DATA_DIR, task_id, "task_info.json"), 'r') as f: saved_data = json.load(f)
    assert saved_data["status"] == "running"

    await tm.stop_task(task_id)
    if task.async_task_handle:
        try: await asyncio.wait_for(task.async_task_handle, timeout=0.5)
        except (asyncio.CancelledError, asyncio.TimeoutError): pass
    assert task.status == "stopped"
    with open(os.path.join(test_app_config.TASK_DATA_DIR, task_id, "task_info.json"), 'r') as f: saved_data = json.load(f)
    assert saved_data["status"] == "stopped"

@pytest.mark.asyncio
async def test_task_execution_md_completes(task_manager_instance: TaskManager, test_app_config: AppConfig):
    tm = task_manager_instance
    tm._openmm_engine.run_simulation_steps = AsyncMock()
    tm._openmm_engine.get_current_state_info = AsyncMock(return_value={"potential_energy": -12345.0})
    md_config = {"task_type": "md", "pdb_file": "c", "forcefield_files": ["f"], "steps": 10}
    task_id = await tm.create_task(md_config)
    await tm.start_task(task_id)
    task = tm._get_task_or_raise(task_id)
    for _ in range(100): # Max wait 1s
        if task.status == "completed": break
        await asyncio.sleep(0.01)
    assert task.status == "completed"
    assert task.results["final_state"]["potential_energy"] == -12345.0

@pytest.mark.asyncio
async def test_task_execution_dft_completes(task_manager_instance: TaskManager, test_app_config: AppConfig):
    tm = task_manager_instance
    tm._abacus_engine.get_results = AsyncMock(return_value={"total_energy": -500.0, "converged": True})
    dft_config = {"task_type": "dft", "dft_params": {"structure": "test"}}
    task_id = await tm.create_task(dft_config)
    await tm.start_task(task_id)
    task = tm._get_task_or_raise(task_id)
    for _ in range(100): # Max wait 1s
        if task.status == "completed": break
        await asyncio.sleep(0.01)
    assert task.status == "completed"
    assert task.results["total_energy"] == -500.0

@pytest.mark.asyncio
async def test_task_execution_md_fails(task_manager_instance: TaskManager, test_app_config: AppConfig):
    tm = task_manager_instance
    tm._openmm_engine.run_simulation_steps = AsyncMock(side_effect=Exception("OpenMM Kaboom!"))
    md_config = {"task_type": "md", "pdb_file": "c", "forcefield_files": ["f"], "steps": 10}
    task_id = await tm.create_task(md_config)
    await tm.start_task(task_id)
    task = tm._get_task_or_raise(task_id)
    for _ in range(100): # Max wait 1s
        if task.status == "failed": break
        await asyncio.sleep(0.01)
    assert task.status == "failed"
    assert task.error_message == "OpenMM Kaboom!"

@pytest.mark.asyncio
async def test_create_task_invalid_type(task_manager_instance: TaskManager):
    tm = task_manager_instance
    invalid_config = {"task_type": "unknown", "params": {}}
    with pytest.raises(ValueError, match="Task configuration must include a valid 'task_type'"):
        await tm.create_task(invalid_config)

@pytest.mark.asyncio
async def test_create_md_task_missing_fields(task_manager_instance: TaskManager):
    tm = task_manager_instance
    md_config_missing = {"task_type": "md", "pdb_file": "c", "forcefield_files": ["f"]} # Missing steps
    with pytest.raises(ValueError, match="MD task configuration missing required fields"):
        await tm.create_task(md_config_missing)

@pytest.mark.asyncio
async def test_create_dft_task_missing_fields(task_manager_instance: TaskManager):
    tm = task_manager_instance
    dft_config_missing = {"task_type": "dft"} # Missing 'dft_params'
    with pytest.raises(ValueError, match="DFT task configuration missing required 'dft_params' dictionary"):
        await tm.create_task(dft_config_missing)
    dft_config_invalid_params = {"task_type": "dft", "dft_params": "not_a_dict"}
    with pytest.raises(ValueError, match="DFT task configuration missing required 'dft_params' dictionary"):
        await tm.create_task(dft_config_invalid_params)
