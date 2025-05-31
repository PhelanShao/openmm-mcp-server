# OpenMM & Abacus (DFT) MCP Server

MCP Server for managing, executing, and monitoring OpenMM molecular dynamics simulations, with integrated support for creating and managing (mock) Abacus DFT calculation tasks.

## Features

-   **OpenMM Simulation Management**: Create, start, pause, resume, and stop OpenMM simulations.
-   **DFT Calculation Management (Mock)**: Create and manage DFT calculation tasks via a mock `AbacusEngine`. Allows testing the workflow for DFT calculations.
-   **Task Persistence**: Task configurations, status, `task_type` (MD or DFT), and results are persisted to disk. Task loading handles interrupted ("running" or "initializing") tasks by setting them to "interrupted" status.
-   **Concurrency Control**: Limits the number of concurrently running computation tasks.
-   **Dynamic Resource Listing**: Resources for tasks, including specific output files for both MD and DFT calculations, are listed dynamically.
-   **MCP Interface**: Exposes tools and resources for:
    -   Creating MD simulations (`create_md_simulation`)
    -   (Experimental) Creating DFT calculations (`create_dft_calculation`) using a mock engine.
    -   Controlling simulation lifecycle (`control_simulation`) for all task types.
    -   Analyzing basic results (`analyze_results`) (currently MD-focused).
    -   Accessing task status, results, and output files (including trajectories for MD, and various input/output files for DFT).
-   **Configurable**: Server behavior can be configured via environment variables.
-   **Extensible**: Designed with a modular `OpenMMEngine` and `AbacusEngine` (currently mock) for different computational backends, managed by a unified `TaskManager`.

## Architecture

The server is built around the Model Context Protocol. A central `TaskManager` is responsible for managing the lifecycle of computational tasks, which can be either Molecular Dynamics (MD) simulations handled by `OpenMMEngine`, or Density Functional Theory (DFT) calculations handled by `AbacusEngine`. `OpenMMEngine` interfaces with the OpenMM library for MD computations. `AbacusEngine` currently provides a mock implementation for DFT workflows. Task configurations and states are persisted on disk.

For a more detailed understanding of the server's internal components, workflow, and design, please refer to the [Architecture Document](./docs/architecture.md).

## Prerequisites

-   Python 3.9+
-   OpenMM: It is highly recommended to install OpenMM via Conda for optimal performance, GPU support (if applicable), and easier management of its complex dependencies.
    ```bash
    conda install -c conda-forge openmm
    ```
-   `pip` for installing Python packages.

## Installation

1.  **Clone the repository (or download the source code):**
    ```bash
    git clone <repository_url>
    cd openmm-mcp-server
    ```

2.  **Create and activate a Python virtual environment (recommended):**
    ```bash
    python -m venv .venv
    # On Windows
    # .venv\Scripts\activate
    # On macOS/Linux
    # source .venv/bin/activate
    ```

3.  **Install dependencies:**
    Ensure OpenMM is installed (preferably via Conda as mentioned above). Then, install other Python packages:
    ```bash
    pip install -r requirements.txt
    ```
    The [`requirements.txt`](./requirements.txt) file includes:
    -   `mcp-sdk`: For the MCP server framework.
    -   `openmm`: (If not installed via Conda, pip will attempt to install it).
    -   `python-dotenv`: For loading environment variable configurations.
    -   `uvicorn`: For running the ASGI server.
    -   `pytest`, `pytest-asyncio`, `httpx` (for running tests).

## Configuration

The server is configured using environment variables, typically loaded from a `.env` file in the project root. Create a `.env` file by copying `.env.example` (if one is provided, otherwise create it manually) and customize the values.

Key configuration variables (see [`src/config.py`](./src/config.py) for more details):

-   `TASK_DATA_DIR`: Path to the directory where task data (configs, results, outputs) will be stored. Default: `./task_data`
-   `MAX_CONCURRENT_TASKS`: Maximum number of tasks (MD or DFT) that can run concurrently. Default: `2`
-   `DEFAULT_OPENMM_PLATFORM`: Default OpenMM platform to use for MD simulations (e.g., "CUDA", "OpenCL", "CPU", "Reference"). If not set, OpenMM attempts to choose the fastest available platform. This setting is used by `OpenMMEngine`.
-   `LOG_LEVEL`: Logging level (e.g., INFO, DEBUG). Default: `INFO`
-   `LOG_FILE`: Optional path to a file for logging output. If not set, logs to console.

Example `.env` file:
```env
TASK_DATA_DIR=./simulation_tasks
MAX_CONCURRENT_TASKS=4
DEFAULT_OPENMM_PLATFORM=CUDA
LOG_LEVEL=DEBUG
# LOG_FILE=./server.log
```

## Running the Server

You can run the server using Uvicorn, which is suitable for development and production:

```bash
uvicorn src.server:mcp_server.sse_app --host 0.0.0.0 --port 8000 --reload
```
Or, for a simple test run directly via Python (as shown in `src/server.py`'s `if __name__ == "__main__":` block):
```bash
python -m src.server
```
This will typically start the server on `http://127.0.0.1:8000`.

## Basic Usage (MCP Interaction)

Once the server is running, MCP clients can connect to it (e.g., at `http://localhost:8000/mcp/sse` if using SSE).

### Available Tools:

-   **`create_md_simulation`**: Creates a new OpenMM MD simulation task.
    -   *Arguments*: `pdb_file` (string content), `forcefield` (list of XMLs), `steps` (integer), `integrator` (object with type, temperature, step_size), optional `platform_name`, `output_config`, etc. Refer to the schema for details (available via `list_tools`).
-   **`create_dft_calculation`**: Creates a new DFT calculation task (currently using a mock Abacus engine).
    -   *Arguments*: `input_structure` (string content of structure file like POSCAR), `calculation_parameters` (object with Abacus settings like `kpoints`, `ecutwfc`), optional `compute_resources`. Refer to schema.
-   **`control_simulation`**: Controls an existing task (MD or DFT).
    -   *Arguments*: `task_id`, `action` ("start", "pause", "resume", "stop", "delete").
-   **`analyze_results`**: Performs basic analysis on task results (currently MD-focused).
    -   *Arguments*: `task_id`, `analysis_type` ("energy", "trajectory_info", etc.).

### Available Resources (URI examples):

Resources are listed dynamically based on created tasks and their types. The name of status and results resources will indicate "(MD)" or "(DFT)".

-   **Common for MD & DFT tasks:**
    -   Task Status: `openmm://tasks/{task_id}/status`
    -   Task Results: `openmm://tasks/{task_id}/results`
-   **MD-Specific Examples:**
    -   Trajectory File: `openmm://tasks/{task_id}/trajectory/{filename.dcd}`
    -   Checkpoint File: `openmm://tasks/{task_id}/checkpoint/{checkpoint.chk}`
-   **DFT-Specific Examples (Mock Output):**
    -   Input Parameter File: `openmm://tasks/{task_id}/outputs/dft_input/INPUT`
    -   Input Structure File: `openmm://tasks/{task_id}/outputs/dft_input/stru.json`
    -   Main Log File: `openmm://tasks/{task_id}/outputs/dft_output_logs/OUT.ABACUS/running_scf.log`
    -   JSON Results Summary: `openmm://tasks/{task_id}/outputs/dft_results_files/results.json`

An example Python client script demonstrating interaction with these tools and resources will be provided in `examples/basic_simulation_example.py`.

## Development & Testing

-   **Tests**: Unit and integration tests are located in the `tests/` directory. Key test suites include:
    -   `tests/test_task_manager.py`: Unit tests for `TaskManager`, covering task creation (MD and DFT), persistence, status transitions, and loading. Uses mocked computation engines.
    -   `tests/test_server_integration.py`: Integration tests for the server's MCP tool endpoints, particularly for task creation (e.g., `create_md_simulation`) using an HTTP-like test client and a `TaskManager` with mocked engines.
    -   `tests/test_openmm_engine.py`: Unit tests for `OpenMMEngine` if OpenMM is available.
-   **Running Tests**:
    Install test dependencies and run `pytest`:
    ```bash
    pip install pytest pytest-asyncio httpx fastapi # httpx & fastapi for TestClient
    pytest
    ```

## Current Project Status & Known Limitations

-   **AbacusEngine is Mocked**: The current implementation of `AbacusEngine` for DFT calculations is a mock. It prepares dummy input/output files and simulates execution time but does not perform actual Abacus calculations. This allows for testing the full DFT task management workflow within the server.
-   **DFT Resource Reading**: The `read_generic_task_file_resource` handler has been updated to locate DFT files from their specific `dft_calc` directory based on URI categories like "dft_input", allowing these files to be read via MCP.
-   **Configuration for Engines**: Detailed configuration for `OpenMMEngine` (beyond platform selection) and `AbacusEngine` (e.g., executable paths for real runs, specific cluster submission templates) may require further enhancements to `AppConfig` and engine initialization logic for production use.

## Contributing

(Details on how to contribute to the project, coding standards, pull request process, etc. - To be added)

## License

(Specify the license for the project, e.g., MIT, Apache 2.0. If not yet decided, state "License TBD".)