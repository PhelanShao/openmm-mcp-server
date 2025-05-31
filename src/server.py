# src/server.py
# Contains the OpenMMComputeServer (MCP Core Implementation)

from mcp.server.fastmcp import FastMCP
from mcp import types as mcp_types
import urllib.parse
import os # For path operations if needed for resources

from .task_manager import TaskManager
from .config import AppConfig
from .utils.logging_config import get_logger
from .abacus_engine import AbacusEngine # Added for Abacus integration

# Import tool execution functions and their schemas
from .tools.create_md_simulation import run_create_md_simulation, CREATE_MD_SIMULATION_SCHEMA
from .tools.control_simulation import run_control_simulation, CONTROL_SIMULATION_SCHEMA
from .tools.analyze_results import run_analyze_results, ANALYZE_RESULTS_SCHEMA
from .tools.create_dft_calculation import run_create_dft_calculation, CREATE_DFT_CALCULATION_SCHEMA

# Import resource reading functions
from .resources.task_status_resource import read_task_status_resource
from .resources.calculation_results_resource import read_calculation_results_resource
from .resources.trajectory_file_resource import read_trajectory_file_resource
from .resources.generic_file_resource import read_generic_task_file_resource


# Initialize logger for the server
logger = get_logger(__name__)

# Initialize FastMCP server
mcp_server = FastMCP(
    name="OpenMMComputeServer",
    version="0.1.0",
    description="MCP Server for OpenMM molecular dynamics simulations."
)

# Instantiate AppConfig and TaskManager
try:
    app_config = AppConfig()
    task_manager = TaskManager(config=app_config)
    logger.info("TaskManager initialized successfully.")

    # Instantiate AbacusEngine
    # It might take specific parts of app_config or the whole thing
    # For now, let's assume it can take the general app_config or handle None
    abacus_engine_config = getattr(app_config, 'ABACUS_ENGINE_CONFIG', {}) # Example: get specific config
    abacus_engine = AbacusEngine(config=abacus_engine_config)
    logger.info("AbacusEngine initialized successfully.")

except Exception as e:
    logger.error(f"Failed to initialize TaskManager or AbacusEngine: {e}", exc_info=True)
    task_manager = None
    abacus_engine = None # Ensure it's defined, even if initialization fails

# MCP Method Implementations

@mcp_server.list_resources()
async def list_resources() -> list[mcp_types.Resource]:
    """Lists available computation resources or task-related resources."""
    global task_manager # Ensure we are using the global task_manager instance

    resources: list[mcp_types.Resource] = []

    if task_manager is None:
        logger.error("TaskManager not available, cannot list dynamic resources.")
        # Optionally, return a predefined error resource or an empty list.
        # For now, returning an empty list.
        return []

    try:
        tasks = task_manager.get_all_tasks()
        task_id_for_logging = "UNKNOWN_TASK" # For logging in case of error before task_id is set
        for task in tasks:
            task_id_for_logging = task.task_id # Update for current task
            task_id = task.task_id
            task_type_str = task.task_type.upper()

            # Common resources for all task types
            resources.append(mcp_types.Resource(
                uri=f"openmm://tasks/{task_id}/status",
                name=f"Task {task_id} ({task_type_str}) Status",
                description=f"Status of {task_type_str} task {task_id}.",
                mime_type="application/json",
                methods=["read"]
            ))

            resources.append(mcp_types.Resource(
                uri=f"openmm://tasks/{task_id}/results",
                name=f"Task {task_id} ({task_type_str}) Results",
                description=f"Results of {task_type_str} task {task_id}.",
                mime_type="application/json",
                methods=["read"]
            ))

            # Type-specific resources
            if task.task_type == "md":
                # MD-specific trajectory resource
                md_trajectory_uri = f"openmm://tasks/{task_id}/trajectory/main.dcd" # Default
                md_trajectory_name = f"Task {task_id} (MD) Trajectory (DCD)"
                md_trajectory_desc = f"Main trajectory file (DCD) for MD task {task_id}."
                if task.results and isinstance(task.results.get("output_files"), dict):
                    for key, path_val in task.results["output_files"].items():
                        if isinstance(path_val, str) and path_val.endswith(".dcd"):
                            filename = os.path.basename(path_val)
                            md_trajectory_uri = f"openmm://tasks/{task_id}/trajectory/{filename}"
                            md_trajectory_name = f"Task {task_id} (MD) Trajectory ({filename})"
                            md_trajectory_desc = f"Trajectory file ({filename}) for MD task {task_id}."
                            break
                resources.append(mcp_types.Resource(
                    uri=md_trajectory_uri, name=md_trajectory_name, description=md_trajectory_desc,
                    mime_type="application/vnd.chemdoodle.trajectory.dcd", methods=["read"]
                ))

                # MD-specific checkpoint resource
                if task.results and isinstance(task.results.get("checkpoint_file"), str):
                    chk_filename = os.path.basename(task.results["checkpoint_file"])
                    resources.append(mcp_types.Resource(
                        uri=f"openmm://tasks/{task_id}/checkpoint/{chk_filename}",
                        name=f"Task {task_id} (MD) Checkpoint ({chk_filename})",
                        description=f"Checkpoint file ({chk_filename}) for MD task {task_id}.",
                        mime_type="application/octet-stream", methods=["read"]
                    ))

            elif task.task_type == "dft":
                # DFT-specific output files based on AbacusEngine mock structure
                # Work directory for DFT: TASK_DATA_DIR/{task_id}/dft_calc/
                # AbacusEngine mock files: INPUT, stru.json, OUT.ABACUS/running_scf.log, results.json

                dft_files_to_list = [
                    {"filename": "INPUT", "category": "input", "mime": "application/json"}, # Mocked as JSON
                    {"filename": "stru.json", "category": "input", "mime": "application/json"},
                    {"filename": "running_scf.log", "category": "output_logs", "sub_path": "OUT.ABACUS", "mime": "text/plain"},
                    {"filename": "results.json", "category": "results_files", "mime": "application/json"},
                ]

                for dft_file_info in dft_files_to_list:
                    file_display_name = dft_file_info["filename"]
                    # If AbacusEngine puts files in subdirectories of 'outputs', reflect that in URI category
                    # Example: 'outputs/input/INPUT', 'outputs/output_logs/OUT.ABACUS/running_scf.log'
                    # The generic_file_resource handler takes 'file_category' which is the part between 'outputs/' and the filename.
                    # If there's a sub_path like OUT.ABACUS, it needs to be part of the 'filename' argument for the handler,
                    # and the 'category' in the URI reflects the top-level classification.

                    uri_filename_part = dft_file_info["filename"]
                    if "sub_path" in dft_file_info: # e.g. OUT.ABACUS/running_scf.log
                        uri_filename_part = f"{dft_file_info['sub_path']}/{dft_file_info['filename']}"

                    resources.append(mcp_types.Resource(
                        uri=f"openmm://tasks/{task_id}/outputs/{dft_file_info['category']}/{uri_filename_part}",
                        name=f"Task {task_id} (DFT) - {file_display_name}",
                        description=f"DFT file: {dft_file_info.get('description', file_display_name)} for task {task_id}.",
                        mime_type=dft_file_info["mime"],
                        methods=["read"]
                    ))
                # Add other DFT specific files if any (e.g. band structure data, density files)
                # These would require AbacusEngine to report their existence and paths.

    except Exception as e:
        logger.error(f"Error dynamically listing resources for task {task_id_for_logging}: {e}", exc_info=True)
        # Optionally, return a specific error resource or fall back safely.
        # For now, returns any resources gathered so far, or an empty list if error was early.
        # Consider if returning a partial list is desirable or if it should be all or nothing.

    return resources

@mcp_server.read_resource()
async def read_resource(uri: mcp_types.URI, byte_range: mcp_types.Range | None = None) -> tuple[bytes, str]:
    """Reads the content of a specified resource by dispatching to appropriate handlers."""
    logger.info(f"Received read_resource request for URI: {uri}, byte_range: {byte_range}")
    # TODO: If future resources do not depend on task_manager (e.g., Abacus-specific resources
    # not managed by the OpenMM TaskManager, or server-level resources), this initial check
    # for task_manager might need to be conditional based on the resource type derived from the URI.
    if not task_manager: # Assuming all current resources are related to TaskManager
        logger.error("TaskManager not initialized. Cannot read resource.")
        raise mcp_types.MCPError("Server error: TaskManager not available.")

    parsed_uri = urllib.parse.urlparse(uri)
    path_parts = parsed_uri.path.strip('/').split('/') # e.g. ["tasks", task_id, "status"]

    if parsed_uri.scheme != "openmm" or not path_parts or path_parts[0] != "tasks":
        logger.warning(f"Invalid or unsupported URI scheme or base path: {uri}")
        raise mcp_types.ResourceNotFoundError(f"Invalid or unsupported URI: {uri}")

    # Minimum path parts: tasks/{task_id}/{resource_category} -> 3 parts
    if len(path_parts) < 3:
        logger.warning(f"URI path too short: {uri}. Expected at least 'tasks/{{task_id}}/{{category}}'.")
        raise mcp_types.ResourceNotFoundError(f"Incomplete resource URI: {uri}")

    task_id = path_parts[1]
    resource_category = path_parts[2] # e.g., "status", "results", "trajectory", "checkpoint", "outputs"

    try:
        if resource_category == "status" and len(path_parts) == 3:
            return await read_task_status_resource(task_manager, task_id, byte_range)

        elif resource_category == "results" and len(path_parts) == 3:
            return await read_calculation_results_resource(task_manager, task_id, byte_range)

        elif resource_category == "trajectory" and len(path_parts) == 4:
            # URI: openmm://tasks/{task_id}/trajectory/{filename}
            filename = path_parts[3]
            return await read_trajectory_file_resource(task_manager, task_id, filename, byte_range)

        elif resource_category == "checkpoint" and len(path_parts) == 4:
            # URI: openmm://tasks/{task_id}/checkpoint/{filename}
            # The generic reader will handle path construction. Category "checkpoint" is special cue.
            filename = path_parts[3]
            return await read_generic_task_file_resource(task_manager, task_id, "checkpoint", filename, byte_range)

        elif resource_category == "outputs" and len(path_parts) == 5:
            # URI: openmm://tasks/{task_id}/outputs/{type_subdir}/{filename}
            # e.g., openmm://tasks/123/outputs/logs/output.log
            type_subdir = path_parts[3] # This is the 'file_category' for generic reader
            filename = path_parts[4]
            return await read_generic_task_file_resource(task_manager, task_id, type_subdir, filename, byte_range)

        # Optional: Handle case for files directly in "outputs" if URI is .../outputs/{filename} (len 4)
        # This depends on whether such URIs are generated by list_resources or expected.
        # For now, the generic "outputs" requires a category sub-directory.
        # If a file "foo.txt" is directly in "outputs", its URI could be .../outputs//foo.txt (empty category)
        # or a new rule: .../outputs/{filename} -> path_parts[2] == "outputs", len(path_parts) == 4
        # Let's add this for files directly under 'outputs' dir:
        elif resource_category == "outputs" and len(path_parts) == 4:
            # URI: openmm://tasks/{task_id}/outputs/{filename} (file directly in outputs folder)
            filename = path_parts[3]
            # Pass empty string for file_category to indicate it's directly in "outputs"
            return await read_generic_task_file_resource(task_manager, task_id, "", filename, byte_range)

        else:
            logger.warning(f"Unknown or malformed resource URI structure: {uri}. Category: '{resource_category}', Parts: {len(path_parts)}")
            raise mcp_types.ResourceNotFoundError(f"Unknown or malformed resource URI: {uri}")

    except mcp_types.ResourceNotFoundError as e: # Catch specific ResourceNotFoundError to re-raise
        logger.warning(f"Resource not found for URI {uri}: {e}")
        raise # Re-raise it as is
    except ValueError as ve: # Catch ValueErrors that might come from _get_task_or_raise
        logger.warning(f"Value error while processing resource URI {uri}: {ve}")
        # This often implies task_id not found or other validation error.
        raise mcp_types.ResourceNotFoundError(f"Invalid request for resource URI {uri}: {ve}")
    except Exception as e:
        logger.error(f"Unexpected error reading resource {uri}: {e}", exc_info=True)
        raise mcp_types.MCPError(f"Internal server error while reading resource: {uri}")

@mcp_server.list_tools()
async def list_tools() -> list[mcp_types.ToolDefinition]:
    """Lists available tools for computation and task management."""
    # For now, return placeholders based on the plan, using imported schema for DFT tool
    tools = [
        mcp_types.ToolDefinition(
            name="create_md_simulation",
            description="Creates a molecular dynamics simulation task.",
            input_schema=CREATE_MD_SIMULATION_SCHEMA
        ),
        mcp_types.ToolDefinition(
            name="control_simulation",
            description="Controls a simulation task execution (start, pause, resume, stop, delete).",
            input_schema=CONTROL_SIMULATION_SCHEMA
        ),
        mcp_types.ToolDefinition(
            name="analyze_results",
            description="Analyzes simulation results.",
            input_schema=ANALYZE_RESULTS_SCHEMA
        ),
        mcp_types.ToolDefinition(
            name="create_dft_calculation",
            description="Creates an Abacus DFT (Density Functional Theory) calculation task.",
            input_schema=CREATE_DFT_CALCULATION_SCHEMA # Using imported schema
        )
    ]
    return tools

@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict) -> mcp_types.ToolResult:
    """Calls a specified tool by dispatching to its handler."""
    logger.info(f"Received call_tool request for tool: {name} with arguments: {arguments}")

    # Check for specific engine/manager requirements per tool
    # All current tools that involve task creation or management rely on TaskManager.
    if name in ["create_md_simulation", "control_simulation", "analyze_results", "create_dft_calculation"]:
        if not task_manager:
            logger.error(f"TaskManager not initialized. Cannot call tool: {name}.")
            raise mcp_types.MCPError(f"Server error: TaskManager not available for tool {name}.")
    # Note: The AbacusEngine instance in server.py (self.abacus_engine) might still be used
    # by other potential future tools that interact directly with Abacus outside TaskManager's scope.
    # For now, create_dft_calculation goes through TaskManager.

    # else: # For tools not requiring specific engines, no check needed here or a generic one

    try:
        if name == "create_md_simulation":
            return await run_create_md_simulation(task_manager, arguments)
        elif name == "control_simulation":
            return await run_control_simulation(task_manager, arguments)
        elif name == "analyze_results":
            return await run_analyze_results(task_manager, arguments)
        elif name == "create_dft_calculation":
            # Pass task_manager to run_create_dft_calculation
            return await run_create_dft_calculation(task_manager, arguments)
        else:
            logger.warning(f"Unknown tool called: {name}")
            raise mcp_types.ToolNotFoundError(f"Tool '{name}' not found.")
    except mcp_types.ToolNotFoundError as e:
        logger.warning(f"Tool not found: {name}: {e}")
        raise
    except mcp_types.InvalidToolArgumentsError as e:
        logger.warning(f"Invalid arguments for tool {name}: {e}")
        raise # Re-raise to be handled by FastMCP
    except Exception as e:
        logger.error(f"Error calling tool {name}: {e}", exc_info=True)
        raise mcp_types.MCPError(f"Internal server error while calling tool: {name}")


@mcp_server.list_prompts()
async def list_prompts() -> list[mcp_types.Prompt]:
    """Lists available prompt templates."""
    # Prompts are not currently planned for this server.
    return [] # No prompts defined initially

@mcp_server.get_prompt()
async def get_prompt(name: str, arguments: dict | None = None) -> mcp_types.GetPromptResult:
    """Gets a specific prompt, optionally with arguments."""
    # Prompts are not currently planned for this server.
    raise NotImplementedError(f"Prompt '{name}' not found.")

# To run this server (example, actual run command might differ based on project setup):
# Ensure this file is executable or run with `python -m src.server` (if part of a package)
# or `uvicorn src.server:mcp_server.sse_app()` if using FastMCP's SSE app directly.
# The plan mentions `uv run mcp-simple-prompt` style commands, which implies
# pyproject.toml and a project structure recognized by `uv run`.

if __name__ == "__main__":
    # This is a basic way to run for testing; production might use a proper ASGI server.
    # For FastMCP, you typically run its ASGI app (e.g., mcp_server.sse_app())
    # or use the mcp CLI to serve it.
    print("Starting OpenMM MCP Server (basic test mode)...")
    # mcp_server.run() # This might be for a different server type or needs more setup.
    # Example using uvicorn if sse_app is standard for FastMCP
    try:
        import uvicorn
        # Assuming sse_app is the standard way to get the ASGI app from FastMCP
        # The port and host can be configured.
        uvicorn.run(mcp_server.sse_app(), host="127.0.0.1", port=8000)
    except ImportError:
        print("Uvicorn is not installed. Please install it to run this basic server example.")
    except AttributeError:
        print("mcp_server.sse_app() not found. Check FastMCP documentation for running the server.")

    # The plan's `uv run <script_name>` suggests a project setup where `uv`
    # can find and execute a script defined in `pyproject.toml`'s `[project.scripts]`.
    # For now, this `if __name__ == "__main__":` block is for very basic, direct execution testing.