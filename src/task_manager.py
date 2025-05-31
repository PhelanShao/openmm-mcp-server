# src/task_manager.py
# Contains the TaskManager for OpenMM simulations

import asyncio
import uuid
from typing import Dict, Any, Optional

# Engine imports
from .openmm_engine import OpenMMEngine
from .abacus_engine import AbacusEngine # Added for DFT tasks

from .config import AppConfig
from src.config import config as app_config # For task data directory, etc.
import os
import json # For JSON operations
import traceback # For logging exceptions
from src.utils.logging_config import get_logger # Added for logging

class Task:
    """Represents a single computation task."""
    def __init__(self, task_id: str, config: Dict[str, Any]):
        self.task_id: str = task_id
        self.config: Dict[str, Any] = config
        self.task_type: str = config.get("task_type", "md") # Default to "md"
        self.status: str = "pending"  # e.g., pending, running, paused, completed, failed
        self.progress: Dict[str, Any] = {"current_step": 0, "total_steps": config.get("steps", 0)}
        # For DFT tasks, "steps" might not be directly applicable in the same way.
        # Progress reporting for DFT might be based on SCF cycles or other metrics.
        # This might need adjustment if DFT tasks have a different concept of "total_steps".
        # For now, initialize progress, but it might be primarily updated by MD tasks.
        if self.task_type == "dft" and "steps" not in config: # DFT tasks might not have "steps"
            self.progress["total_steps"] = 1 # Placeholder for DFT progress (e.g., 1 for the whole calc)


        self.results: Optional[Dict[str, Any]] = None
        self.error_message: Optional[str] = None
        self.simulation_instance: Any = None # Will hold the OpenMM Simulation object or similar
        self.async_task_handle: Optional[asyncio.Task] = None # To manage the running asyncio task

    def update_status(self, status: str, error_message: Optional[str] = None):
        self.status = status
        if error_message:
            self.error_message = error_message

    def update_progress(self, current_step: int, total_steps: Optional[int] = None):
        self.progress["current_step"] = current_step
        if total_steps is not None:
            self.progress["total_steps"] = total_steps

    def set_results(self, results: Dict[str, Any]):
        self.results = results

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the task object to a dictionary for JSON storage."""
        # Exclude non-serializable fields like simulation_instance and async_task_handle
        return {
            "task_id": self.task_id,
            "config": self.config,
            "task_type": self.task_type,
            "status": self.status,
            "progress": self.progress,
            "results": self.results,
            "error_message": self.error_message,
            # Do not store simulation_instance or async_task_handle
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Task':
        """Deserializes a dictionary back into a Task object."""
        task_id = data.get("task_id")
        config = data.get("config")
        if not task_id or not config:
            raise ValueError("Task data is missing task_id or config.")
        
        # task_type is now part of config, but also stored explicitly
        # Ensure config in Task object is the source of truth for task_type upon creation
        # For deserialization, we can get it from the persisted task_type field
        # or default from config if task_type field is missing (for backward compatibility)

        task = cls(task_id=task_id, config=config) # task_type is set from config here
        task.status = data.get("status", "pending")

        # If 'task_type' exists in the persisted data, it overrides the one from config during from_dict
        # This ensures that loaded tasks retain their specific persisted type.
        # The Task.__init__ already sets task_type from config.get("task_type", "md").
        # If data["task_type"] is present, it means it was explicitly saved.
        # We need to ensure that the task.task_type reflects the *saved* type.
        # The config inside the task object should also reflect this.
        persisted_task_type = data.get("task_type")
        if persisted_task_type:
            task.task_type = persisted_task_type
            # Also ensure the config within the task reflects this persisted type
            # if it's not already there or different.
            if task.config.get("task_type") != persisted_task_type:
                task.config["task_type"] = persisted_task_type


        # Adjust progress initialization for DFT if necessary
        default_total_steps = config.get("steps", 0)
        if task.task_type == "dft" and "steps" not in config:
            default_total_steps = 1 # Placeholder for DFT

        task.progress = data.get("progress", {"current_step": 0, "total_steps": default_total_steps})
        task.results = data.get("results")
        task.error_message = data.get("error_message")
        # simulation_instance and async_task_handle are runtime objects and not restored directly
        return task

class TaskManager:
    """Manages the lifecycle of OpenMM computation tasks."""

    def __init__(self, config: Optional[AppConfig] = None):
        self.logger = get_logger(__name__)
        self.config = config or app_config
        self._tasks: Dict[str, Task] = {}
        self._openmm_engine = OpenMMEngine()
        self._abacus_engine = AbacusEngine() # Instantiate AbacusEngine
        self._task_queue = asyncio.Queue() # For managing tasks to be run (can be used for more advanced scheduling)
        self._concurrency_semaphore = asyncio.Semaphore(self.config.MAX_CONCURRENT_TASKS)
        self.logger.info(f"Task manager initialized with MAX_CONCURRENT_TASKS={self.config.MAX_CONCURRENT_TASKS}")
        self._lock = asyncio.Lock() # For concurrent access to _tasks dictionary
        
        task_data_dir = self.config.TASK_DATA_DIR
        if not os.path.exists(task_data_dir):
            try:
                os.makedirs(task_data_dir, exist_ok=True)
                self.logger.info(f"Task data directory created: {task_data_dir}")
            except OSError as e:
                self.logger.error(f"Failed to create task data directory {task_data_dir}: {e}")
        else:
            self.logger.info(f"Task data directory already exists: {task_data_dir}")
        
        self._load_tasks_from_disk()


    def _load_tasks_from_disk(self):
        """Loads all persisted task information from disk when TaskManager initializes."""
        self.logger.info(f"Attempting to load tasks from disk: {app_config.TASK_DATA_DIR}")
        if not os.path.exists(app_config.TASK_DATA_DIR) or not os.path.isdir(app_config.TASK_DATA_DIR):
            self.logger.warning(f"Task data directory not found or not a directory: {app_config.TASK_DATA_DIR}. No tasks loaded.")
            return

        for task_id_dir_name in os.listdir(app_config.TASK_DATA_DIR):
            task_dir_path = os.path.join(app_config.TASK_DATA_DIR, task_id_dir_name)
            if not os.path.isdir(task_dir_path):
                continue

            task_info_file = os.path.join(task_dir_path, "task_info.json")
            if os.path.exists(task_info_file):
                try:
                    with open(task_info_file, 'r') as f:
                        task_data = json.load(f)
                    
                    task = Task.from_dict(task_data)
                    
                    # Handle tasks that were running/initializing during a previous server shutdown
                    if task.status in ["running", "initializing"]:
                        self.logger.warning(f"Task {task.task_id} was '{task.status}' before shutdown. Resetting to 'interrupted'.")
                        task.update_status("interrupted")
                        self._save_task_to_disk_sync(task) # Immediately save the updated status
                    
                    # Although _load_tasks_from_disk is called in __init__ (single-threaded context at that point),
                    # using a lock here for consistency if it were ever called elsewhere or if __init__ becomes async.
                    # However, for __init__, it's not strictly necessary for this specific modification.
                    # For simplicity and focusing on runtime modifications, I'll omit the lock here for now,
                    # assuming _load_tasks_from_disk remains an __init__-only synchronous setup step before async event loop starts.
                    # If _tasks were to be modified by other async methods during _load_tasks_from_disk, a lock would be needed.
                    # Let's assume _tasks is populated here before any concurrent access.
                    self._tasks[task.task_id] = task
                    self.logger.info(f"Loaded task {task.task_id} from disk with status '{task.status}'.")
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to decode JSON for task in {task_info_file}: {e}")
                except ValueError as e: # From Task.from_dict
                    self.logger.error(f"Failed to load task from data in {task_info_file} (missing fields?): {e}")
                except Exception as e:
                    self.logger.error(f"Unexpected error loading task from {task_info_file}: {e}", exc_info=True)
            else:
                self.logger.debug(f"No task_info.json found in directory: {task_dir_path}")
        self.logger.info(f"Finished loading tasks. Total tasks in memory: {len(self._tasks)}")


    async def create_task(self, config: Dict[str, Any]) -> str:
        """
        Creates a new computation task.
        Config must include "task_type" ("md" or "dft").
        Other parameters depend on the task_type.
        """
        task_id = str(uuid.uuid4())

        task_type = config.get("task_type")
        if not task_type or task_type not in ["md", "dft"]:
            raise ValueError(f"Task configuration must include a valid 'task_type' ('md' or 'dft'). Found: {task_type}")

        # Basic validation for MD tasks (can be expanded)
        if task_type == "md":
            # Check for either pdb_file or pdb_data
            has_pdb = config.get("pdb_file") or config.get("pdb_data")
            # Check for either forcefield_files or forcefield
            has_forcefield = config.get("forcefield_files") or config.get("forcefield")
            if not has_pdb or not has_forcefield or config.get("steps") is None:
                raise ValueError("MD task configuration missing required fields (pdb_file/pdb_data, forcefield_files/forcefield, steps).")
        # Basic validation for DFT tasks (can be expanded)
        elif task_type == "dft":
            if not config.get("dft_params") or not isinstance(config.get("dft_params"), dict):
                 raise ValueError("DFT task configuration missing required 'dft_params' dictionary.")
            # Further checks for specific keys within dft_params can be added here or in AbacusEngine.

        task = Task(task_id=task_id, config=config) # Task.__init__ now handles task_type from config
        async with self._lock:
            self._tasks[task_id] = task
        await self._save_task_to_disk(task) # Save task upon creation
        # await self._task_queue.put(task) # Optionally, put in a queue to be picked up by a worker
        self.logger.info(f"Task {task_id} created and saved with config: {config}")
        return task_id

    async def _save_task_to_disk(self, task: Task):
        """Saves a single task's information to a JSON file using a temporary file for atomicity."""
        task_dir = os.path.join(app_config.TASK_DATA_DIR, task.task_id)
        os.makedirs(task_dir, exist_ok=True) # Ensure directory exists
        
        task_file_path = os.path.join(task_dir, "task_info.json")
        tmp_task_file_path = task_file_path + ".tmp"

        def _save_atomically():
            try:
                with open(tmp_task_file_path, 'w') as f:
                    json.dump(task.to_dict(), f, indent=4)
                # If write to tmp is successful, then rename
                os.rename(tmp_task_file_path, task_file_path)
                self.logger.debug(f"Task {task.task_id} information saved to {task_file_path}")
            except IOError as e: # Covers issues with open, write, rename
                self.logger.error(f"IOError during atomic save for task {task.task_id} to {task_file_path}: {e}")
                if os.path.exists(tmp_task_file_path): # Clean up .tmp file on error
                    try: os.remove(tmp_task_file_path)
                    except OSError: self.logger.error(f"Failed to remove temporary file {tmp_task_file_path} after save error.")
                raise # Re-raise to be caught by the outer try-except if needed, or handled by caller
            except TypeError as e: # json.dump serialization error
                self.logger.error(f"TypeError (serialization issue?) during atomic save for task {task.task_id}: {e}", exc_info=True)
                if os.path.exists(tmp_task_file_path):
                    try: os.remove(tmp_task_file_path)
                    except OSError: self.logger.error(f"Failed to remove temporary file {tmp_task_file_path} after type error.")
                raise
            except Exception as e: # Catch any other unexpected error during the process
                self.logger.error(f"Unexpected error during atomic save for task {task.task_id}: {e}", exc_info=True)
                if os.path.exists(tmp_task_file_path):
                    try: os.remove(tmp_task_file_path)
                    except OSError: self.logger.error(f"Failed to remove temporary file {tmp_task_file_path} after unexpected error.")
                raise

        try:
            await asyncio.to_thread(_save_atomically)
        except Exception:
            # Errors are already logged in _save_atomically.
            # This outer catch is to prevent unhandled exceptions from asyncio.to_thread.
            # Depending on desired behavior, we might re-raise or handle differently.
            # For now, logging in the sync helper is sufficient.
            pass


    def _save_task_to_disk_sync(self, task: Task):
        """Synchronously saves a single task's information to a JSON file using a temporary file for atomicity."""
        task_dir = os.path.join(app_config.TASK_DATA_DIR, task.task_id)
        os.makedirs(task_dir, exist_ok=True) # Ensure directory exists

        task_file_path = os.path.join(task_dir, "task_info.json")
        tmp_task_file_path = task_file_path + ".tmp"
        
        try:
            with open(tmp_task_file_path, 'w') as f:
                json.dump(task.to_dict(), f, indent=4)
            os.rename(tmp_task_file_path, task_file_path)
            self.logger.debug(f"Task {task.task_id} information saved synchronously to {task_file_path}")
        except IOError as e:
            self.logger.error(f"IOError while saving task {task.task_id} (sync) to {task_file_path}: {e}")
            if os.path.exists(tmp_task_file_path):
                try: os.remove(tmp_task_file_path)
                except OSError: self.logger.error(f"Failed to remove temporary file {tmp_task_file_path} after sync IOError.")
        except TypeError as e:
            self.logger.error(f"TypeError (serialization issue?) while saving task {task.task_id} (sync) to {task_file_path}: {e}", exc_info=True)
            if os.path.exists(tmp_task_file_path):
                try: os.remove(tmp_task_file_path)
                except OSError: self.logger.error(f"Failed to remove temporary file {tmp_task_file_path} after sync TypeError.")
        except Exception as e: # Catch-all for other errors during sync save
            self.logger.error(f"An unexpected error occurred while saving task {task.task_id} (sync): {e}", exc_info=True)
            if os.path.exists(tmp_task_file_path):
                try: os.remove(tmp_task_file_path)
                except OSError: self.logger.error(f"Failed to remove temporary file {tmp_task_file_path} after sync Exception.")

    async def _execute_task_loop(self, task: Task):
        """Internal task execution loop, dispatching to MD or DFT runners."""
        async with self._concurrency_semaphore:
            self.logger.info(f"Task [{task.task_id} - {task.task_type.upper()}]: Acquired semaphore. Active tasks: {app_config.MAX_CONCURRENT_TASKS - self._concurrency_semaphore._value}/{app_config.MAX_CONCURRENT_TASKS}")

            if task.status != "running":
                self.logger.warning(f"Task [{task.task_id}]: Status changed to '{task.status}' before execution could start. Aborting.")
                return

            task.update_status("initializing")
            await self._save_task_to_disk(task) # Persist initializing status, important for DFT too
            self.logger.info(f"Task [{task.task_id} - {task.task_type.upper()}]: Initializing...")

            try:
                if task.task_type == "md":
                    await self._run_md_task(task)
                elif task.task_type == "dft":
                    await self._run_dft_task(task)
                else:
                    self.logger.error(f"Task [{task.task_id}]: Unknown task_type '{task.task_type}'. Cannot execute.")
                    task.update_status("failed", f"Unknown task_type: {task.task_type}")
                    await self._save_task_to_disk(task)

            except asyncio.CancelledError:
                self.logger.info(f"Task [{task.task_id} - {task.task_type.upper()}]: Execution was cancelled by request.")
                task.update_status("stopped", "Task was cancelled during execution.")
                await self._save_task_to_disk(task)
            except Exception as e:
                self.logger.error(f"Task [{task.task_id} - {task.task_type.upper()}]: Error during execution - {str(e)}", exc_info=True)
                task.update_status("failed", error_message=str(e))
                await self._save_task_to_disk(task)
            finally:
                if task.task_type == "md" and task.simulation_instance: # Specific to MD tasks
                    self.logger.info(f"Task [{task.task_id} - MD]: Cleaning up OpenMM simulation instance.")
                    await self._openmm_engine.cleanup_simulation(task.simulation_instance)
                    task.simulation_instance = None
                # DFT tasks might have their own cleanup via abacus_engine if needed, or handled by work_dir persistence strategy.

                self.logger.info(f"Task [{task.task_id} - {task.task_type.upper()}]: Execution loop finished with final status '{task.status}'.")
                active_tasks_count = app_config.MAX_CONCURRENT_TASKS - (self._concurrency_semaphore._value +1 if self._concurrency_semaphore._value < app_config.MAX_CONCURRENT_TASKS else self._concurrency_semaphore._value)
                self.logger.info(f"Task [{task.task_id}]: Releasing semaphore. Active tasks: {active_tasks_count}/{app_config.MAX_CONCURRENT_TASKS}")

    async def _run_md_task(self, task: Task):
        """Handles the execution of an MD task."""
        self.logger.info(f"Task [{task.task_id} - MD]: Starting MD task execution.")
        # --- This is the original _run_simulation_task logic for OpenMM ---
        pdb_input_type = task.config.get("pdb_input_type", "content")
        pdb_data = task.config.get("pdb_data")
        pdb_file_content_for_engine: Optional[str] = None
        pdb_file_path_for_engine: Optional[str] = None
        if pdb_input_type == "content": pdb_file_content_for_engine = pdb_data
        elif pdb_input_type == "file_path": pdb_file_path_for_engine = pdb_data
        else: raise ValueError(f"Invalid pdb_input_type: {pdb_input_type}")

        forcefield_files = task.config.get("forcefield_files", ["amber14-all.xml", "amber14/tip3pfb.xml"])

        topology, positions, openmm_system = await self._openmm_engine.setup_system(
            pdb_file_content=pdb_file_content_for_engine,
            pdb_file_path=pdb_file_path_for_engine,
            forcefield_files=forcefield_files,
            nonbonded_method_str=task.config.get("nonbonded_method", "PME"),
            nonbonded_cutoff_nm=float(task.config.get("nonbonded_cutoff_nm", 1.0)),
            constraints_str=task.config.get("constraints", "HBonds")
        )

        integrator_cfg = task.config.get("integrator", {"type": "LangevinMiddle", "temperature_K": 300, "friction_coeff_ps": 1.0, "step_size_ps": 0.002})
        platform_name = task.config.get("platform_name", app_config.DEFAULT_OPENMM_PLATFORM)
        platform_props = task.config.get("platform_properties")

        task.simulation_instance = await self._openmm_engine.create_simulation(
            topology=topology, system=openmm_system, integrator_config=integrator_cfg,
            platform_name=platform_name, platform_properties=platform_props
        )

        if positions and task.simulation_instance:
            await self._openmm_engine.set_initial_positions(task.simulation_instance, positions)

        output_config = task.config.get("output_config", {})
        processed_output_config = self._process_output_paths(task.task_id, output_config) # Uses task_id for path construction
        await self._openmm_engine.configure_reporters(task.simulation_instance, processed_output_config)

        if task.config.get("minimize_energy", False):
            self.logger.info(f"Task [{task.task_id} - MD]: Performing energy minimization...")
            minimize_max_iter = int(task.config.get("minimize_max_iterations", 0))
            minimize_tolerance_kj_mol_nm = task.config.get("minimize_tolerance_kj_mol_nm")
            if minimize_tolerance_kj_mol_nm is not None: minimize_tolerance_kj_mol_nm = float(minimize_tolerance_kj_mol_nm)
            await self._openmm_engine.minimize_energy(
                task.simulation_instance, tolerance_kj_mol_nm=minimize_tolerance_kj_mol_nm, max_iterations=minimize_max_iter)
            self.logger.info(f"Task [{task.task_id} - MD]: Energy minimization complete.")

        if task.config.get("set_velocities_to_temperature", False) and task.simulation_instance:
            temp_kelvin = float(integrator_cfg.get("temperature_K", 300))
            await self._openmm_engine.set_velocities_to_temperature(task.simulation_instance, temp_kelvin)

        if task.status != "running" and task.status != "initializing":
             self.logger.warning(f"Task [{task.task_id} - MD]: Status changed to '{task.status}' during setup. Aborting run loop.")
             return # Exit MD task run, finally in _execute_task_loop will handle cleanup.

        task.update_status("running") # Set to running if it was initializing
        # No immediate save here, as start_task already saved "running" status.
        # Subsequent saves will happen at end of chunks or final states.

        total_steps = int(task.config.get("steps", 0))
        self.logger.info(f"Task [{task.task_id} - MD]: Running simulation for {total_steps} steps...")
        run_chunk_size = int(task.config.get("run_chunk_size", 1000))
        checkpoint_interval_steps = int(task.config.get("checkpoint_interval_steps", 0))

        checkpoint_file_path = None
        if checkpoint_interval_steps > 0:
            cp_reporter_cfg = task.config.get("output_config", {}).get("checkpoint_reporter", {})
            processed_cp_cfg_item = self._process_output_paths(task.task_id, {"checkpoint_reporter": cp_reporter_cfg}).get("checkpoint_reporter", {})
            if isinstance(processed_cp_cfg_item, dict): checkpoint_file_path = processed_cp_cfg_item.get("file")
            if not checkpoint_file_path and cp_reporter_cfg.get("file"):
                 checkpoint_file_path = os.path.join(app_config.TASK_DATA_DIR, task.task_id, "outputs", os.path.basename(cp_reporter_cfg.get("file")))
            elif not checkpoint_file_path:
                checkpoint_file_path = os.path.join(app_config.TASK_DATA_DIR, task.task_id, "outputs", "checkpoint.chk")
            if checkpoint_file_path: os.makedirs(os.path.dirname(checkpoint_file_path), exist_ok=True)

        current_simulation_step = 0
        while current_simulation_step < total_steps:
            if task.status != "running":
                self.logger.info(f"Task [{task.task_id} - MD]: Simulation loop interrupted (status: {task.status}).")
                break
            steps_to_run_this_chunk = min(run_chunk_size, total_steps - current_simulation_step)
            if not task.simulation_instance:
                self.logger.error(f"Task [{task.task_id} - MD]: Simulation instance became unavailable.")
                raise Exception("MD Simulation instance is not available.")
            await self._openmm_engine.run_simulation_steps(task.simulation_instance, steps_to_run_this_chunk)
            current_simulation_step += steps_to_run_this_chunk
            task.update_progress(current_simulation_step) # total_steps is already set
            self.logger.debug(f"Task [{task.task_id} - MD]: Progress {current_simulation_step}/{total_steps}")
            if checkpoint_file_path and checkpoint_interval_steps > 0 and \
               (current_simulation_step % checkpoint_interval_steps == 0 or current_simulation_step == total_steps):
                if task.simulation_instance:
                    self.logger.info(f"Task [{task.task_id} - MD]: Saving checkpoint at step {current_simulation_step} to {checkpoint_file_path}")
                    await self._openmm_engine.save_checkpoint(task.simulation_instance, checkpoint_file_path)

        if task.status == "running": # If loop finished and task wasn't stopped/paused
            task.update_status("completed")
            # await self._save_task_to_disk(task) # This will be done in the main _execute_task_loop finally or success
            final_state_info = {}
            if task.simulation_instance:
                final_state_info = await self._openmm_engine.get_current_state_info(task.simulation_instance, get_energy=True)
            results_summary = {"final_state": final_state_info}
            output_files_summary = {}
            processed_output_config_for_results = self._process_output_paths(task.task_id, task.config.get("output_config", {}))
            for reporter_type, cfg_item_or_list_results in processed_output_config_for_results.items():
                cfgs_to_check = cfg_item_or_list_results if isinstance(cfg_item_or_list_results, list) else [cfg_item_or_list_results]
                for cfg_r in cfgs_to_check:
                    if isinstance(cfg_r, dict) and "file" in cfg_r and cfg_r["file"].lower() not in ["stdout", "stderr"]:
                        rel_path = os.path.relpath(cfg_r["file"], app_config.TASK_DATA_DIR)
                        output_files_summary[f"{reporter_type}_file"] = rel_path
            if output_files_summary: results_summary["output_files"] = output_files_summary
            if checkpoint_file_path and (current_simulation_step == total_steps):
                results_summary["checkpoint_file"] = os.path.relpath(checkpoint_file_path, app_config.TASK_DATA_DIR)
            task.set_results(results_summary)
            self.logger.info(f"Task [{task.task_id} - MD]: MD simulation completed. Results: {results_summary}")
        elif task.status == "stopped":
            self.logger.info(f"Task [{task.task_id} - MD]: MD simulation stopped by user.")
        # Other statuses (failed, paused) will be handled by the main loop or specific control actions.

    async def _run_dft_task(self, task: Task):
        """Handles the execution of a DFT task using AbacusEngine."""
        self.logger.info(f"Task [{task.task_id} - DFT]: Starting DFT task execution.")

        work_dir = os.path.join(app_config.TASK_DATA_DIR, task.task_id, "dft_calc")
        dft_params = task.config.get("dft_params", {})
        abacus_cmd = task.config.get("abacus_command") # May be None, AbacusEngine will use its default

        # Ensure work_dir exists (AbacusEngine's prepare_input also does this, but good to be sure)
        try:
            os.makedirs(work_dir, exist_ok=True)
        except OSError as e:
            self.logger.error(f"Task [{task.task_id} - DFT]: Failed to create DFT working directory {work_dir}: {e}")
            task.update_status("failed", f"Failed to create DFT work_dir: {e}")
            # No need to save here, will be saved in _execute_task_loop's except block
            raise # Re-raise to be caught by _execute_task_loop's main try-except

        # 1. Prepare input files
        self.logger.info(f"Task [{task.task_id} - DFT]: Preparing input files...")
        # Progress update: before input preparation
        task.update_progress(current_step=0, total_steps=3) # 3 steps: prepare, run, get_results

        prep_info = await self._abacus_engine.prepare_input(task.task_id, dft_params, work_dir)
        self.logger.info(f"Task [{task.task_id} - DFT]: Input preparation complete. Info: {prep_info}")
        # Progress update: after input preparation
        task.update_progress(current_step=1)


        # 2. Run calculation
        if task.status != "running": # Check if task was paused/stopped during input prep
            self.logger.info(f"Task [{task.task_id} - DFT]: Task status '{task.status}'. Aborting before run.")
            return

        self.logger.info(f"Task [{task.task_id} - DFT]: Running Abacus calculation...")
        run_result = await self._abacus_engine.run_calculation(task.task_id, work_dir, abacus_cmd)
        self.logger.info(f"Task [{task.task_id} - DFT]: Calculation run complete. Result: {run_result}")
        # Progress update: after run calculation
        task.update_progress(current_step=2)

        if run_result.get("status") != "completed": # Based on AbacusEngine's mock return
            error_msg = run_result.get("message", "DFT calculation execution failed.")
            self.logger.error(f"Task [{task.task_id} - DFT]: {error_msg}")
            task.update_status("failed", error_msg)
            # No need to save here, will be saved in _execute_task_loop's except block
            # Raise an exception to ensure it's caught by the main try-except for consistent error handling
            raise Exception(error_msg)

        # 3. Get results
        if task.status != "running": # Check if task was paused/stopped during run
            self.logger.info(f"Task [{task.task_id} - DFT]: Task status '{task.status}'. Aborting before get_results.")
            return

        self.logger.info(f"Task [{task.task_id} - DFT]: Retrieving results...")
        results = await self._abacus_engine.get_results(task.task_id, work_dir)
        task.set_results(results)
        self.logger.info(f"Task [{task.task_id} - DFT]: Results retrieved: {results}")
        # Progress update: after get_results
        task.update_progress(current_step=3)

        task.update_status("completed") # Final status for a successful run
        # No need to save here, will be saved in _execute_task_loop after successful completion.

    async def start_task(self, task_id: str) -> None:
        """Starts or resumes a computation task."""
        task = self._get_task_or_raise(task_id)

        if task.status == "running":
            self.logger.info(f"Task [{task_id}] is already running.")
            return
        if task.status == "completed" or task.status == "failed":
            self.logger.warning(f"Task [{task_id}] is already {task.status}. Cannot restart/resume.")
            return

        if task.async_task_handle and not task.async_task_handle.done():
             self.logger.warning(f"Task [{task_id}] (status: {task.status}) has an existing async_task_handle that is not done. This might indicate an issue or a previous unclean stop.")
        
        if task.status == "pending" or task.status == "paused" or task.status == "interrupted":
            original_status = task.status
            task.update_status("running")
            await self._save_task_to_disk(task)
            self.logger.info(f"Task [{task_id}] (status: {original_status}) starting/resuming execution, now 'running'.")
            task.async_task_handle = asyncio.create_task(self._execute_task_loop(task)) # Changed to _execute_task_loop
        else:
            self.logger.warning(f"Task [{task_id}] cannot be started/resumed from its current status: {task.status}. Only pending, paused, or interrupted tasks can be started.")


    async def pause_task(self, task_id: str) -> None:
        """Pauses a running computation task."""
        task = self._get_task_or_raise(task_id)
        if task.status == "running":
            task.update_status("paused")
            await self._save_task_to_disk(task) # Save after status update
            self.logger.info(f"Task {task_id} paused.")
            # The _run_simulation_task loop should check task.status and stop processing.
            # True pause might involve more complex state saving with OpenMM if supported.
        else:
            self.logger.warning(f"Task {task_id} is not running (status: {task.status}), cannot pause.")

    async def resume_task(self, task_id: str) -> None:
        """Resumes a paused computation task."""
        # This is essentially the same as start_task in this simplified model
        # if the task was properly 'paused' by setting its status.
        await self.start_task(task_id)

    async def stop_task(self, task_id: str) -> None:
        """Stops a computation task."""
        task = self._get_task_or_raise(task_id)
        if task.status in ["running", "paused", "pending", "initializing"]:
            original_status = task.status
            task.update_status("stopped")
            await self._save_task_to_disk(task) # Save after status update
            self.logger.info(f"Task {task_id} stopping (was {original_status})...")
            if task.async_task_handle and not task.async_task_handle.done():
                task.async_task_handle.cancel() # Request cancellation
                try:
                    await task.async_task_handle # Wait for cancellation to complete
                except asyncio.CancelledError:
                    self.logger.info(f"Task {task_id} async run successfully cancelled.")
                except Exception as e:
                    self.logger.error(f"Task {task.task_id}: Error during task cancellation/cleanup: {str(e)}", exc_info=True)
            # Further cleanup might be needed here or in _run_simulation_task's finally block
            self.logger.info(f"Task {task_id} stopped.")
        else:
            self.logger.warning(f"Task {task_id} is not in a stoppable state (status: {task.status}).")


    async def delete_task(self, task_id: str) -> None:
        """Deletes a task and its associated data."""
        task = self._get_task_or_raise(task_id)
        if task.status in ["running", "initializing"]:
            await self.stop_task(task_id) # Ensure task is stopped before deleting

        async with self._lock:
            if task_id in self._tasks:
                del self._tasks[task_id]
                # Log deletion from in-memory store inside the lock if other checks depend on it
                # or if the act of deletion itself needs to be atomic with other _tasks operations.
            else:
                # This case should ideally be caught by _get_task_or_raise if called prior,
                # but if delete_task is called directly with an unknown ID after a concurrent delete.
                self.logger.warning(f"Task {task_id} not found in _tasks for deletion (already deleted or never existed).")
                return # Exit if not found in memory to prevent further operations

        self.logger.info(f"Task {task_id} deleted from in-memory store.") # Log after lock released
        task_dir_to_delete = os.path.join(app_config.TASK_DATA_DIR, task_id)
        if os.path.exists(task_dir_to_delete):
            try:
                import shutil # Import moved here to be specific to this usage
                await asyncio.to_thread(shutil.rmtree, task_dir_to_delete)
                self.logger.info(f"Successfully deleted task data directory: {task_dir_to_delete}")
            except Exception as e:
                self.logger.error(f"Failed to delete task data directory {task_dir_to_delete}: {e}", exc_info=True)
        else:
            self.logger.warning(f"Task data directory not found for deletion: {task_dir_to_delete}")
        # The case where task_id was not in self._tasks during the lock is handled within the lock block by returning.

    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Gets the status of a specific task."""
        task = self._get_task_or_raise(task_id)
        return {
            "task_id": task.task_id,
            "status": task.status,
            "error_message": task.error_message,
            "config": task.config # Optionally return config for context
        }

    async def get_task_progress(self, task_id: str) -> Dict[str, Any]:
        """Gets the progress of a specific task."""
        task = self._get_task_or_raise(task_id)
        return {
            "task_id": task.task_id,
            "status": task.status, # Include status for context
            "progress": task.progress
        }

    async def get_task_results(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Gets the results of a completed task."""
        task = self._get_task_or_raise(task_id)
        if task.status == "completed":
            return task.results
        elif task.status == "failed":
            return {"error": task.error_message or "Task failed without specific error message."}
        else:
            return {"message": f"Task {task_id} is not yet completed (status: {task.status})."}

    def _get_task_or_raise(self, task_id: str) -> Task:
        """
        Helper to get a task by ID or raise an error if not found.
        This method is synchronous as it's often called from async methods
        before an await point, and dict.get is atomic.
        If it were async and locked, it would need to be awaited everywhere.
        The lock primarily protects modifications to the _tasks dict structure.
        Reading a task reference is safe, but the caller must be aware that
        the task object's state might be modified by its own async_task_handle.
        """
        # Consider if lock is needed here. If only for reading a reference,
        # and assuming task_id is valid and present, direct access is fine.
        # The main concern is if another coroutine deletes the task_id from _tasks
        # between this get and its usage.
        # For now, not locking read-only access that doesn't iterate.
        task = self._tasks.get(task_id)
        if not task:
            # This log helps if the error is not caught and propagated clearly by caller
            self.logger.warning(f"_get_task_or_raise: Task with ID '{task_id}' not found in self._tasks.")
            raise ValueError(f"Task with ID '{task_id}' not found.")
        return task

    def get_all_tasks(self) -> list[Task]:
        """Returns a list of all task objects."""
        # Consider if a lock is needed if tasks can be added/deleted concurrently
        # with this call. For now, assuming _tasks.values() provides a reasonably
        # consistent snapshot for iteration. If _tasks itself is being modified
        # (e.g. re-assigned or cleared), a lock would be more critical.
        # list() creates a copy, so the list itself is safe from concurrent modification.
        return list(self._tasks.values())

    # Optional: A worker coroutine if using _task_queue for processing
    # async def worker(self):
    #     while True:
    #         task_to_run = await self._task_queue.get()
    #         print(f"Worker picked up task {task_to_run.task_id}")
    #         await self._run_simulation_task(task_to_run)
    #         self._task_queue.task_done()

    def _process_output_paths(self, task_id: str, output_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ensures output file paths in reporter configurations are relative to the task's data directory.
        Example: "output.dcd" becomes "TASK_DATA_DIR/task_id/output.dcd"
        """
        processed_config = output_config.copy()
        task_specific_data_dir = os.path.join(app_config.TASK_DATA_DIR, task_id, "outputs")
        os.makedirs(task_specific_data_dir, exist_ok=True)

        for reporter_type, cfg_list in processed_config.items():
            if not isinstance(cfg_list, list): # Handle single dict config too
                cfg_list = [cfg_list]
            
            new_cfg_list = []
            for cfg_item in cfg_list:
                if isinstance(cfg_item, dict) and "file" in cfg_item:
                    original_file = cfg_item["file"]
                    if original_file and original_file.lower() not in ["stdout", "stderr"]:
                        # Make path relative to task's output directory
                        base_filename = os.path.basename(original_file)
                        cfg_item["file"] = os.path.join(task_specific_data_dir, base_filename)
                new_cfg_list.append(cfg_item)
            
            if len(new_cfg_list) == 1 and not isinstance(output_config.get(reporter_type), list):
                 processed_config[reporter_type] = new_cfg_list[0]
            else:
                processed_config[reporter_type] = new_cfg_list
        return processed_config


# Example of how TaskManager might be initialized and a worker started (if using queue)
# async def main():
#     task_manager = TaskManager()
#     # Start worker if using a queue-based approach
#     # asyncio.create_task(task_manager.worker())

#     # Example usage (would typically be called from server.py tool handlers)
#     # Note: PDB data would need to be actual content or a valid path
#     pdb_content_example = "ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  0.00           N\n"
#     config1 = {
#         "pdb_input_type": "content",
#         "pdb_data": pdb_content_example,
#         "forcefield_files": ["amber14-all.xml"],
#         "steps": 100,
#         "integrator": {"type": "LangevinMiddle", "temperature_K": 300, "step_size_ps": 0.001},
#         "platform_name": "CPU", # Or "CUDA", "OpenCL" if available
#         "minimize_energy": True,
#         "output_config": {
#             "dcd_reporter": {"file": "trajectory.dcd", "reportInterval": 10},
#             "state_data_reporter": {"file": "stdout", "reportInterval": 10, "step": True, "potentialEnergy": True}
#         }
#     }
#     task_id1 = await task_manager.create_task(config1)
#     await task_manager.start_task(task_id1)
#     # ... wait or do other things ...
#     await asyncio.sleep(5) # Let it run for a bit
#     status = await task_manager.get_task_status(task_id1)
#     print(f"Status of task {task_id1}: {status}")
#     progress = await task_manager.get_task_progress(task_id1)
#     print(f"Progress of task {task_id1}: {progress}")
#     # await task_manager.stop_task(task_id1) # Example stop
#     # results = await task_manager.get_task_results(task_id1)
#     # print(f"Results of task {task_id1}: {results}")


# if __name__ == "__main__":
#     # This example needs OpenMM installed and configured to run properly.
#     # Ensure OpenMMEngine's OPENMM_AVAILABLE is True.
#     asyncio.run(main())