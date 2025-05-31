# OpenMM MCP Server

MCP Server for managing, executing, and monitoring OpenMM molecular dynamics simulations. This server allows clients to interact with OpenMM simulations programmatically via the Model Context Protocol (MCP), and includes preliminary support for Abacus DFT calculations.

## Features

-   **OpenMM Simulation Management**: Create, start, pause, resume, and stop OpenMM simulations.
-   **Task Persistence**: Simulation task configurations, status, and results are persisted to disk.
-   **Concurrency Control**: Limits the number of concurrently running OpenMM simulations.
-   **MCP Interface**: Exposes tools and resources for:
    -   Creating MD simulations (`create_md_simulation`)
    -   Controlling simulation lifecycle (`control_simulation`)
    -   Analyzing basic results (`analyze_results`)
    -   (Placeholder) Creating DFT calculations (`create_dft_calculation`)
    -   Accessing task status, results, and trajectory files.
-   **Configurable**: Server behavior can be configured via environment variables.
-   **Extensible**: Designed with a modular `OpenMMEngine` and a placeholder `AbacusEngine` for future computational backends.

## Architecture

For a detailed understanding of the server's internal components, workflow, and design, please refer to the [Architecture Document](./docs/architecture.md).

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

## Configuration

The server is configured using environment variables, typically loaded from a `.env` file in the project root. Create a `.env` file by copying `.env.example` (if one is provided, otherwise create it manually) and customize the values.

Key configuration variables (see [`src/config.py`](./src/config.py) for more details):

-   `TASK_DATA_DIR`: Path to the directory where task data (configs, results, outputs) will be stored. Default: `./task_data`
-   `MAX_CONCURRENT_TASKS`: Maximum number of OpenMM simulations that can run concurrently. Default: `2`
-   `DEFAULT_OPENMM_PLATFORM`: Default OpenMM platform to use (e.g., "CUDA", "OpenCL", "CPU", "Reference"). Default: `None` (OpenMM chooses best available).
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
    -   *Arguments*: PDB content, forcefield files, simulation steps, integrator settings, output configuration, etc.
-   **`control_simulation`**: Controls an existing MD task.
    -   *Arguments*: `task_id`, `action` ("start", "pause", "resume", "stop").
-   **`analyze_results`**: Performs basic analysis on MD task results.
    -   *Arguments*: `task_id`, `analysis_type` ("energy", "trajectory_info", etc.).
-   **`create_dft_calculation`** (Placeholder): Intended for creating Abacus DFT calculation tasks.

### Available Resources (URI examples):

-   Task Status: `openmm://tasks/{task_id}/status`
-   Task Results: `openmm://tasks/{task_id}/results`
-   Task Trajectory: `openmm://tasks/{task_id}/trajectory` (actual trajectory file content)

An example Python client script demonstrating interaction with these tools and resources will be provided in `examples/basic_simulation_example.py`.

## Development & Testing

(This section can be expanded with details on setting up a development environment, running tests, linters, etc.)

-   **Tests**: (To be implemented) Unit and integration tests will be located in the `tests/` directory and can be run using `pytest`.
    ```bash
    # pip install pytest pytest-asyncio
    # pytest
    ```

## Contributing

(Details on how to contribute to the project, coding standards, pull request process, etc.)

## License

(Specify the license for the project, e.g., MIT, Apache 2.0. If not yet decided, state "License TBD".)