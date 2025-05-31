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

# Import tool execution functions
from .tools.create_md_simulation import run_create_md_simulation
from .tools.control_simulation import run_control_simulation
from .tools.analyze_results import run_analyze_results
from .tools.create_dft_calculation import run_create_dft_calculation, CREATE_DFT_CALCULATION_SCHEMA # Added for Abacus

# Import resource reading functions
from .resources.task_status_resource import read_task_status_resource
from .resources.calculation_results_resource import read_calculation_results_resource
from .resources.trajectory_file_resource import read_trajectory_file_resource


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
    # TODO: Dynamically list resources based on active tasks from TaskManager/AbacusEngine once task management is further refined.
    # For now, return a placeholder list of resource types.
    return [
        mcp_types.Resource(
            uri="openmm://tasks/{task_id}/status", # Example URI
            name="Task Status",
            description="Real-time task status information.",
            mime_type="application/json",
            methods=["read"]
        ),
        mcp_types.Resource(
            uri="openmm://tasks/{task_id}/results", # Example URI
            name="Calculation Results",
            description="Simulation calculation result data.",
            mime_type="application/json",
            methods=["read"]
        ),
        mcp_types.Resource(
            uri="openmm://tasks/{task_id}/trajectory", # Example URI
            name="Molecular Trajectory",
            description="Molecular dynamics trajectory file.",
            mime_type="chemical/x-dcd", # Example, could be other formats
            methods=["read"]
        )
    ]

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
    path_parts = parsed_uri.path.strip('/').split('/')

    # Expected URI format: openmm://tasks/{task_id}/{resource_type}
    # or openmm://tasks/{task_id}/files/{filename} (for trajectory or other files)

    if parsed_uri.scheme != "openmm" or not path_parts or path_parts[0] != "tasks":
        logger.warning(f"Invalid or unsupported URI scheme/base path: {uri}")
        raise mcp_types.ResourceNotFoundError(f"Invalid or unsupported URI: {uri}")

    if len(path_parts) < 3:
        logger.warning(f"URI path too short: {uri}")
        raise mcp_types.ResourceNotFoundError(f"Incomplete resource URI: {uri}")

    task_id = path_parts[1]
    resource_type = path_parts[2]

    try:
        if resource_type == "status":
            return await read_task_status_resource(task_manager, task_id, byte_range)
        elif resource_type == "results":
            return await read_calculation_results_resource(task_manager, task_id, byte_range)
        elif resource_type == "trajectory":
            # Trajectory resource might need more specific handling if filename is part of URI
            # For now, assume task_id is enough and the handler knows which trajectory file.
            # If URI is like "openmm://tasks/{task_id}/trajectory/{filename}", adjust parsing.
            # The current trajectory_file_resource.py expects the URI to be just for the task,
            # and it infers the file. Let's adapt to a more specific URI if needed,
            # or confirm the handler's logic.
            # For now, we pass the full URI to the handler as it was designed.
            return await read_trajectory_file_resource(task_manager, uri, byte_range)
        # Example for a more specific file resource:
        # elif resource_type == "files" and len(path_parts) > 3:
        #     filename = path_parts[3]
        #     # return await read_specific_task_file_resource(task_manager, task_id, filename, byte_range)
        else:
            logger.warning(f"Unknown resource type '{resource_type}' in URI: {uri}")
            raise mcp_types.ResourceNotFoundError(f"Unknown resource type in URI: {uri}")
    except mcp_types.ResourceNotFoundError as e:
        logger.warning(f"Resource not found for URI {uri}: {e}")
        raise
    except Exception as e:
        logger.error(f"Error reading resource {uri}: {e}", exc_info=True)
        raise mcp_types.MCPError(f"Internal server error while reading resource: {uri}")

@mcp_server.list_tools()
async def list_tools() -> list[mcp_types.ToolDefinition]:
    """Lists available tools for computation and task management."""
    # For now, return placeholders based on the plan, using imported schema for DFT tool
    tools = [
        mcp_types.ToolDefinition(
            name="create_md_simulation",
            description="Creates a molecular dynamics simulation task.",
            input_schema={ # Consider moving this schema to its tool module too
                "type": "object",
                "properties": {
                    "pdb_file": {"type": "string", "description": "PDB file path or content"},
                    "forcefield": {"type": "string", "description": "Force field type"},
                    "temperature": {"type": "number", "description": "Simulation temperature (K)"},
                    "steps": {"type": "integer", "description": "Simulation steps"}
                },
                "required": ["pdb_file", "forcefield", "steps"]
            }
        ),
        mcp_types.ToolDefinition(
            name="control_simulation",
            description="Controls a simulation task execution (start, pause, resume, stop, delete).",
            input_schema={ # Consider moving this schema to its tool module
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "ID of the task to control"},
                    "action": {"type": "string", "enum": ["start", "pause", "resume", "stop", "delete"]}
                },
                "required": ["task_id", "action"]
            }
        ),
        mcp_types.ToolDefinition(
            name="analyze_results",
            description="Analyzes simulation results.",
            input_schema={ # Consider moving this schema to its tool module
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "ID of the task to analyze"},
                    "analysis_type": {"type": "string", "enum": ["energy", "rmsd", "trajectory"]}
                },
                "required": ["task_id", "analysis_type"]
            }
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
    if name in ["create_md_simulation", "control_simulation", "analyze_results"]:
        if not task_manager:
            logger.error(f"TaskManager not initialized. Cannot call MD tool: {name}.")
            raise mcp_types.MCPError(f"Server error: TaskManager not available for MD tool {name}.")
    elif name == "create_dft_calculation":
        if not abacus_engine: # Check if abacus_engine is initialized
            logger.error(f"AbacusEngine not initialized. Cannot call DFT tool: {name}.")
            raise mcp_types.MCPError(f"Server error: AbacusEngine not available for DFT tool {name}.")
    # else: # For tools not requiring specific engines, no check needed here or a generic one

    try:
        if name == "create_md_simulation":
            return await run_create_md_simulation(task_manager, arguments)
        elif name == "control_simulation":
            return await run_control_simulation(task_manager, arguments)
        elif name == "analyze_results":
            return await run_analyze_results(task_manager, arguments)
        elif name == "create_dft_calculation":
            # Pass abacus_engine instead of task_manager for this tool
            return await run_create_dft_calculation(abacus_engine, arguments)
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