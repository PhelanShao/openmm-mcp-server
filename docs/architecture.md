# OpenMM MCP Server Architecture

This document outlines the architecture of the OpenMM MCP Server, a server designed to manage and execute molecular dynamics simulations using OpenMM via the Model Context Protocol (MCP).

## 1. Overview

The server allows clients (e.g., scripting environments, user interfaces) to create, control, monitor, and retrieve results from OpenMM simulations. It also includes preliminary support for Abacus DFT calculations. Communication is handled via MCP, with the server exposing a set of tools and resources.

## 2. Main Components

The server is composed of several key Python modules and classes:

### 2.1. Server Core (`src/server.py`)

-   **`OpenMMComputeServer` (MCP Endpoint)**:
    -   Implemented using `FastMCP` from the `mcp.server.fastmcp` library.
    -   Handles incoming MCP requests and dispatches them to the appropriate handlers.
    -   **MCP Methods Implemented**:
        -   `list_tools()`: Lists available computational tools.
        -   `call_tool(name, arguments)`: Executes a specified tool (e.g., create simulation, control simulation).
        -   `list_resources()`: Lists available data resources (e.g., task status, results).
        -   `read_resource(uri, byte_range)`: Reads data from a specified resource.
        -   (Prompts-related methods are present but not actively used).
    -   Instantiates and holds references to `TaskManager` and `AbacusEngine`.

### 2.2. Task Management (`src/task_manager.py`)

-   **`Task` Class**:
    -   Represents a single computation task (e.g., an OpenMM simulation).
    -   Stores task ID, configuration, status (`pending`, `initializing`, `running`, `paused`, `completed`, `failed`, `interrupted`), progress, results, and error messages.
    -   Includes `to_dict()` and `from_dict()` methods for JSON serialization/deserialization (for persistence).
    -   Holds runtime references to the OpenMM `Simulation` object and the `asyncio.Task` handle for the running simulation.
-   **`TaskManager` Class**:
    -   Manages the lifecycle of OpenMM simulation tasks.
    -   `_tasks`: A dictionary storing all `Task` objects, keyed by `task_id`.
    -   **Concurrency Control**: Uses an `asyncio.Semaphore` (`_concurrency_semaphore`) to limit the number of concurrently running OpenMM simulations based on `app_config.MAX_CONCURRENT_TASKS`.
    -   **Persistence**:
        -   Saves task information (status, config, results) to JSON files (`task_info.json`) within a dedicated directory for each task (`TASK_DATA_DIR/<task_id>/`).
        -   Uses "write-temporary-then-rename" for atomic file saving (`_save_task_to_disk`, `_save_task_to_disk_sync`).
        -   Loads tasks from disk upon initialization (`_load_tasks_from_disk`), resetting previously running tasks to "interrupted".
    -   **Core Methods**:
        -   `create_task(config)`: Creates a new task, assigns a UUID, and saves it.
        -   `start_task(task_id)`: Initiates the execution of a task by creating an `asyncio.Task` that runs `_run_simulation_task`.
        -   `pause_task(task_id)`: Sets a task's status to "paused". The running simulation loop checks this status.
        -   `resume_task(task_id)`: Effectively calls `start_task` for a paused task.
        -   `stop_task(task_id)`: Sets a task's status to "stopped" and cancels its `asyncio.Task` handle.
        -   `delete_task(task_id)`: Stops a task if running, removes it from memory, and deletes its data directory from disk.
        -   `get_task_status(task_id)`, `get_task_progress(task_id)`, `get_task_results(task_id)`: Query task information.
        -   `_run_simulation_task(task)`: The core asynchronous method that orchestrates the entire lifecycle of a single OpenMM simulation using `OpenMMEngine`. This includes setup, minimization, running steps in chunks, and collecting results.
        -   `_process_output_paths(task_id, output_config)`: Ensures reporter output files are placed in task-specific directories.
    -   Uses an `asyncio.Lock` (`_lock`) to protect concurrent modifications to the `_tasks` dictionary.

### 2.3. OpenMM Engine (`src/openmm_engine.py`)

-   **`OpenMMEngine` Class**:
    -   Wraps all direct interactions with the OpenMM library.
    -   Makes blocking OpenMM calls asynchronous using `await asyncio.to_thread()`.
    -   **Core Methods**:
        -   `setup_system()`: Creates OpenMM `Topology` and `System` objects from PDB (content or path via `io.StringIO`) and force field files.
        -   `create_simulation()`: Creates an OpenMM `Simulation` object with a specified integrator and platform.
        -   `configure_reporters()`: Adds various reporters (DCD, XTC, StateData, Checkpoint) to the simulation. Includes error handling for individual reporter setup.
        -   `minimize_energy()`: Performs energy minimization.
        -   `run_simulation_steps()`: Runs the simulation for a specified number of steps.
        -   `get_current_state_info()`: Retrieves current state data (positions, energy, forces).
        -   `save_checkpoint()`, `load_checkpoint()`: Manages simulation checkpoints.
        -   `set_initial_positions()`, `set_velocities_to_temperature()`: Modifies simulation context.
        -   `cleanup_simulation()`: Placeholder for any explicit cleanup of OpenMM objects if needed.
    -   Includes mock OpenMM objects to allow the server to run (for non-simulation tasks) even if OpenMM is not installed.

### 2.4. Abacus Engine (`src/abacus_engine.py`) - Placeholder

-   **`AbacusEngine` Class**:
    -   Intended for managing Abacus DFT calculations. Currently, its methods are placeholders.
    -   Defines an interface for:
        -   `submit_calculation(task_config)`
        -   `get_calculation_status(job_id)`
        -   `get_calculation_results(job_id)`
        -   `cancel_calculation(job_id)`
        -   `cleanup_workspace(job_id)`
    -   Inherits from an abstract `ComputeEngine` (which might be refactored or removed as `AbacusEngine` evolves).

### 2.5. MCP Tools (`src/tools/`)

Individual Python modules implement the logic for each MCP tool:
-   **`create_md_simulation.py` (`run_create_md_simulation`)**:
    -   Validates input arguments (PDB content is required; server-side path specification is disabled for security).
    -   Constructs a `task_config` dictionary.
    -   Calls `task_manager.create_task(task_config)`.
-   **`control_simulation.py` (`run_control_simulation`)**:
    -   Validates `task_id` and `action` (start, pause, resume, stop).
    -   Calls the corresponding `task_manager` methods (e.g., `task_manager.start_task()`).
-   **`analyze_results.py` (`run_analyze_results`)**:
    -   Validates `task_id` and `analysis_type` (energy, trajectory_info, rmsd, rdf - last two are placeholders).
    -   Fetches task results/status from `TaskManager`.
    -   Performs basic analysis (e.g., extracts energy, lists trajectory files). For "energy" analysis, task must be completed.
-   **`create_dft_calculation.py` (`run_create_dft_calculation`)**:
    -   Validates input arguments against its schema, including nested parameters for `calculation_parameters` and `compute_resources`.
    -   Assumes `input_structure` is content.
    -   Constructs `dft_task_config`.
    -   (Placeholder) Interacts with `AbacusEngine` (passed from `server.py`).

### 2.6. MCP Resources (`src/resources/`)

Individual Python modules implement the logic for reading MCP resources:
-   **`task_status_resource.py` (`read_task_status_resource`)**: Calls `task_manager.get_task_status()`.
-   **`calculation_results_resource.py` (`read_calculation_results_resource`)**: Calls `task_manager.get_task_results()`.
-   **`trajectory_file_resource.py` (`read_trajectory_file_resource`)**: Locates and streams trajectory file content based on task results.

### 2.7. Configuration (`src/config.py`)

-   **`AppConfig` Class**:
    -   Loads server configuration from environment variables (using `python-dotenv`) and provides them as attributes.
    -   Examples: `TASK_DATA_DIR`, `MAX_CONCURRENT_TASKS`, `DEFAULT_OPENMM_PLATFORM`.

### 2.8. Utilities (`src/utils/`)

-   **`logging_config.py`**: Sets up application-wide logging (console and optional file output).

## 3. Workflow Example: Creating and Running an MD Simulation

1.  **Client**: Sends a `call_tool` request to the MCP server with `name="create_md_simulation"` and arguments (PDB content, force field, steps, etc.).
2.  **`src/server.py` (`call_tool`)**:
    -   Receives the request.
    -   Dispatches to `run_create_md_simulation(task_manager, arguments)`.
3.  **`src/tools/create_md_simulation.py` (`run_create_md_simulation`)**:
    -   Validates arguments.
    -   Constructs `task_config`.
    -   Calls `await task_manager.create_task(task_config)`.
4.  **`src/task_manager.py` (`create_task`)**:
    -   Creates a `Task` object with a new `task_id`.
    -   Stores the task in `self._tasks` (under `asyncio.Lock`).
    -   Saves the task state to `TASK_DATA_DIR/<task_id>/task_info.json` (atomically).
    -   Returns `task_id`.
5.  **Client**: Receives `task_id`. Sends another `call_tool` request with `name="control_simulation"`, `task_id`, and `action="start"`.
6.  **`src/server.py` (`call_tool`)**: Dispatches to `run_control_simulation(task_manager, arguments)`.
7.  **`src/tools/control_simulation.py` (`run_control_simulation`)**: Calls `await task_manager.start_task(task_id)`.
8.  **`src/task_manager.py` (`start_task`)**:
    -   Retrieves the `Task` object.
    -   Updates task status to "running".
    -   Creates an `asyncio.Task` to execute `self._run_simulation_task(task)`.
9.  **`src/task_manager.py` (`_run_simulation_task`)**:
    -   Acquires the `_concurrency_semaphore`.
    -   Updates task status to "initializing".
    -   Calls `self._openmm_engine.setup_system()`.
    -   Calls `self._openmm_engine.create_simulation()`.
    -   Calls `self._openmm_engine.configure_reporters()`.
    -   Optionally calls `self._openmm_engine.minimize_energy()`.
    -   Updates task status to "running".
    -   Enters a loop, calling `self._openmm_engine.run_simulation_steps()` in chunks.
    -   Updates task progress and saves checkpoints periodically.
    -   Upon completion or interruption, updates status, collects results, and saves final state.
    -   Cleans up `simulation_instance`.
    -   Releases the semaphore.
10. **Client**: Can periodically poll for status using `read_resource` with URI `openmm://tasks/{task_id}/status` or fetch results with `openmm://tasks/{task_id}/results` once completed.

## 4. Data Flow and Persistence

-   **Task Configuration & Metadata**: Stored as JSON in `TASK_DATA_DIR/<task_id>/task_info.json`.
-   **Simulation Output Files**: (DCD, XTC, checkpoints, logs) Stored in `TASK_DATA_DIR/<task_id>/outputs/`. Paths are managed by `TaskManager._process_output_paths`.
-   **In-memory State**: `TaskManager._tasks` holds current `Task` objects. `AbacusEngine` (future) would manage its own job states.

## 5. Error Handling

-   **Tool/Resource Functions**: Validate inputs and raise specific `mcp_types` exceptions (e.g., `InvalidToolArgumentsError`, `ResourceNotFoundError`) or return error dictionaries for client feedback.
-   **`src/server.py`**: Catches exceptions from tool/resource handlers and wraps unexpected errors in `mcp_types.MCPError`.
-   **`TaskManager` / `OpenMMEngine`**: Log errors extensively. `TaskManager` updates task status to "failed" with an error message upon encountering exceptions during simulation execution.
-   **File Persistence**: Uses "write-temporary-then-rename" for saving task state to reduce data corruption risk. Interrupted tasks are marked on startup.

## 6. Security Considerations (Preliminary)

-   **Input Validation**: Implemented at the tool level for required parameters and basic types. Schema validation is expected from the MCP framework.
-   **Path Traversal**: Mitigated in `create_md_simulation` by disallowing client-specified server-side PDB paths (content is required). Output paths are server-controlled. `input_structure` for DFT is assumed to be content.
-   **Resource Limits**: Concurrency of OpenMM tasks is limited by `MAX_CONCURRENT_TASKS` semaphore.
-   (Authentication/Authorization are not currently implemented).

This architecture provides a modular and extensible framework for managing OpenMM simulations and can be expanded for other computational engines like Abacus.