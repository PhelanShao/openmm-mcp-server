# src/abacus_engine.py
# Contains the AbacusEngine for preparing, running, and parsing Abacus DFT calculations.

import asyncio
import os
import json
from typing import Dict, Any, Optional, List

from src.utils.logging_config import get_logger

class AbacusEngine:
    """
    Engine for managing Abacus (DFT) calculations.
    This class handles preparing inputs, running calculations (mocked),
    and retrieving results (mocked).
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initializes the AbacusEngine.
        Args:
            config: Configuration for the engine, e.g., Abacus executable path,
                    default working directory, cluster submission templates.
        """
        self.logger = get_logger(__name__)
        self.config: Dict[str, Any] = config if config is not None else {}
        self.abacus_command: str = self.config.get("abacus_command", "abacus")

        self.logger.info(
            f"AbacusEngine initialized. Command: '{self.abacus_command}'. "
            f"Config: {self.config}"
        )

    async def prepare_input(self, task_id: str, params: Dict[str, Any], work_dir: str) -> Dict[str, Any]:
        """
        Prepares all necessary input files for an Abacus calculation.
        (Mock Implementation)

        Args:
            task_id: Unique identifier for the task.
            params: Dictionary of parameters for the calculation.
                    (e.g., structure, k-points, XC functional, etc.)
            work_dir: The working directory for this calculation.

        Returns:
            A dictionary summarizing prepared inputs.
        """
        self.logger.info(f"Task [{task_id}]: Preparing Abacus input in '{work_dir}' with params: {params}")

        try:
            if not os.path.exists(work_dir):
                os.makedirs(work_dir, exist_ok=True)
                self.logger.info(f"Task [{task_id}]: Created working directory: {work_dir}")
        except OSError as e:
            self.logger.error(f"Task [{task_id}]: Failed to create working directory {work_dir}: {e}")
            raise # Re-raise the exception to be handled by the caller

        # Mock: Create a dummy INPUT file (typical for Abacus)
        input_file_path = os.path.join(work_dir, "INPUT")
        input_content = {
            "general_parameters": params.get("general_parameters", {}),
            "atomic_species": params.get("atomic_species", []),
            "k_points": params.get("k_points", {}),
            # Add other relevant sections based on params
        }
        try:
            with open(input_file_path, 'w') as f:
                json.dump(input_content, f, indent=4) # Using JSON for dummy INPUT for simplicity
            self.logger.info(f"Task [{task_id}]: Created dummy INPUT file at {input_file_path}")
        except IOError as e:
            self.logger.error(f"Task [{task_id}]: Failed to write INPUT file {input_file_path}: {e}")
            raise

        # Mock: Create a dummy structure file (e.g., STRU or atoms.json)
        stru_file_path = os.path.join(work_dir, "stru.json") # Example name
        structure_data = params.get("structure_data", {"comment": "No structure provided"})
        try:
            with open(stru_file_path, 'w') as f:
                json.dump(structure_data, f, indent=4)
            self.logger.info(f"Task [{task_id}]: Created dummy structure file at {stru_file_path}")
        except IOError as e:
            self.logger.error(f"Task [{task_id}]: Failed to write structure file {stru_file_path}: {e}")
            raise

        prepared_files = [os.path.basename(input_file_path), os.path.basename(stru_file_path)]
        
        return {
            "input_files": prepared_files,
            "work_dir": work_dir,
            "message": f"Input files prepared for task {task_id}."
        }

    async def run_calculation(self, task_id: str, work_dir: str, common_command: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes the Abacus calculation.
        (Mock Implementation)

        Args:
            task_id: Unique identifier for the task.
            work_dir: The working directory where input files are located.
            common_command: The command to run Abacus (e.g., "abacus", "mpirun -np 4 abacus").
                            If None, uses self.abacus_command.

        Returns:
            A dictionary indicating success or failure of the (mock) run.
        """
        effective_command = common_command if common_command is not None else self.abacus_command
        self.logger.info(f"Task [{task_id}]: Starting mock Abacus calculation in '{work_dir}' using command: {effective_command}")

        # Mock: Simulate Abacus execution time
        await asyncio.sleep(2) # Simulate some computation time

        # Mock: Create a dummy output log file
        # Example: OUT.ABACUS/running_scf.log (Abacus often creates subdirs for output)
        output_subdir = os.path.join(work_dir, "OUT.ABACUS")
        try:
            if not os.path.exists(output_subdir):
                os.makedirs(output_subdir, exist_ok=True)
        except OSError as e:
            self.logger.error(f"Task [{task_id}]: Failed to create output subdirectory {output_subdir}: {e}")
            # Continue without it for mock, or raise depending on desired strictness

        log_file_path = os.path.join(output_subdir, "running_scf.log")
        mock_log_content = (
            f"Mock ABACUS calculation for task {task_id}\n"
            "SCF calculation started.\n"
            "Iteration 1: Energy = -123.50 eV\n"
            "Iteration 2: Energy = -123.48 eV\n"
            "Convergence reached.\n"
            "Total Energy = -123.45 eV\n"
        )
        try:
            with open(log_file_path, 'w') as f:
                f.write(mock_log_content)
            self.logger.info(f"Task [{task_id}]: Created dummy output log at {log_file_path}")
        except IOError as e:
            self.logger.error(f"Task [{task_id}]: Failed to write mock output log {log_file_path}: {e}")
            # Not raising here as it's just a mock output, main process "succeeded"

        # Mock: Create a dummy results summary file (e.g. results.json)
        results_summary_path = os.path.join(work_dir, "results.json")
        mock_results = {
            "task_id": task_id,
            "final_energy_ev": -123.45,
            "converged": True,
            "iterations": 2,
            "warnings": []
        }
        try:
            with open(results_summary_path, 'w') as f:
                json.dump(mock_results, f, indent=4)
            self.logger.info(f"Task [{task_id}]: Created dummy results summary at {results_summary_path}")
        except IOError as e:
            self.logger.error(f"Task [{task_id}]: Failed to write results summary {results_summary_path}: {e}")


        self.logger.info(f"Task [{task_id}]: Mock Abacus calculation finished in '{work_dir}'.")
        return {"status": "completed", "message": f"Mock Abacus run for task {task_id} finished."}

    async def get_results(self, task_id: str, work_dir: str) -> Dict[str, Any]:
        """
        Parses output files and extracts key results from an Abacus calculation.
        (Mock Implementation)

        Args:
            task_id: Unique identifier for the task.
            work_dir: The working directory where output files are located.

        Returns:
            A dictionary of mock results.
        """
        self.logger.info(f"Task [{task_id}]: Retrieving results from '{work_dir}'.")

        # Mock: Read the dummy results.json file
        results_summary_path = os.path.join(work_dir, "results.json")
        if os.path.exists(results_summary_path):
            try:
                with open(results_summary_path, 'r') as f:
                    results = json.load(f)
                self.logger.info(f"Task [{task_id}]: Successfully read results from {results_summary_path}")
                return results
            except (IOError, json.JSONDecodeError) as e:
                self.logger.error(f"Task [{task_id}]: Failed to read or parse results file {results_summary_path}: {e}")
                return {"error": "Failed to parse results file.", "task_id": task_id}
        else:
            # Fallback if results.json doesn't exist, try parsing the log
            log_file_path = os.path.join(work_dir, "OUT.ABACUS", "running_scf.log")
            if os.path.exists(log_file_path):
                self.logger.warning(f"Task [{task_id}]: results.json not found, attempting to parse {log_file_path}")
                # Extremely simple mock parsing
                try:
                    with open(log_file_path, 'r') as f:
                        content = f.read()
                    if "Total Energy = -123.45 eV" in content and "Convergence reached" in content:
                        return {"energy": -123.45, "status": "converged", "task_id": task_id, "source": "log_fallback"}
                    else:
                        return {"energy": None, "status": "unknown_from_log", "task_id": task_id, "source": "log_fallback"}
                except IOError as e:
                    self.logger.error(f"Task [{task_id}]: Failed to read log file {log_file_path}: {e}")
                    return {"error": "Failed to read log file.", "task_id": task_id}
            else:
                self.logger.error(f"Task [{task_id}]: No output files (results.json or log) found in {work_dir} or {os.path.join(work_dir, 'OUT.ABACUS')}")
                return {"error": "No output files found.", "task_id": task_id}


    async def cleanup_calculation(self, task_id: str, work_dir: str) -> None:
        """
        Cleans up any intermediate files after calculation.
        (Mock Implementation)

        Args:
            task_id: Unique identifier for the task.
            work_dir: The working directory to clean up.
        """
        self.logger.info(f"Task [{task_id}]: Cleaning up calculation in '{work_dir}'.")

        # Example: remove a specific temporary file if it exists
        temp_file_example = os.path.join(work_dir, "TEMP_SCRATCH_FILE.tmp")
        if os.path.exists(temp_file_example):
            try:
                os.remove(temp_file_example)
                self.logger.info(f"Task [{task_id}]: Removed temporary file {temp_file_example}")
            except OSError as e:
                self.logger.error(f"Task [{task_id}]: Error removing temporary file {temp_file_example}: {e}")

        # For a full cleanup, one might use shutil.rmtree(work_dir),
        # but that should be handled carefully by the TaskManager or caller
        # depending on whether the work_dir is meant to be persistent or not.
        # For this mock, we'll just log that cleanup is "done".
        self.logger.info(f"Task [{task_id}]: Mock cleanup finished for '{work_dir}'. Workspace preservation depends on caller.")
        pass

# Example of how this engine might be used by a task manager or tool
async def _test_abacus_engine_methods():
    engine = AbacusEngine(config={"abacus_command": "abacus_mpi"})
    test_task_id = "test_dft_task_001"
    test_work_dir = f"/tmp/abacus_test_jobs/{test_task_id}" # More specific test work_dir

    # Ensure clean slate for test
    if os.path.exists(test_work_dir):
        import shutil
        shutil.rmtree(test_work_dir)

    test_params = {
        "general_parameters": {"calculation_type": "scf"},
        "atomic_species": [{"name": "Si", "pseudo_potential": "Si.UPF"}],
        "k_points": {"scheme": "gamma", "grid": [4,4,4]},
        "structure_data": {"comment": "Silicon test structure", "atoms": [{"element": "Si", "position": [0,0,0]}]}
    }

    try:
        print(f"--- Testing AbacusEngine for task: {test_task_id} ---")
        prep_info = await engine.prepare_input(test_task_id, test_params, test_work_dir)
        print(f"Preparation info: {prep_info}")

        run_info = await engine.run_calculation(test_task_id, test_work_dir)
        print(f"Run info: {run_info}")

        results_info = await engine.get_results(test_task_id, test_work_dir)
        print(f"Results info: {results_info}")

        await engine.cleanup_calculation(test_task_id, test_work_dir)
        print(f"Cleanup for task {test_task_id} called.")
        print(f"--- Test finished for task: {test_task_id} ---")

    except Exception as e:
        print(f"Error during AbacusEngine test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Optional: final cleanup of the test_work_dir parent if empty
        # Or leave it for manual inspection
        pass


if __name__ == "__main__":
    # Configure basic logging for the test
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    asyncio.run(_test_abacus_engine_methods())
