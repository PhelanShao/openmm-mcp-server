# src/tools/create_dft_calculation.py
# Tool for creating Abacus DFT calculation tasks.

from mcp import types as mcp_types
from src.utils.logging_config import get_logger
# from src.task_manager import TaskManager # Or a new DftTaskManager
# from src.abacus_engine import AbacusEngine

logger = get_logger(__name__)

# Pre-defined schema (can be loaded from a file or defined here)
# This should match the schema in server.py's list_tools
CREATE_DFT_CALCULATION_SCHEMA = {
    "type": "object",
    "properties": {
        "input_structure": {
            "type": "string",
            "description": "Input structure file content or path (e.g., POSCAR, cif)."
        },
        "calculation_parameters": {
            "type": "object",
            "description": "Abacus-specific calculation parameters (e.g., KPOINTS, INCAR settings).",
            "properties": {
                "kpoints": {"type": "string", "description": "K-points definition."},
                "ecutwfc": {"type": "number", "description": "Plane-wave cutoff energy."},
                # Add other common Abacus parameters as needed
            },
            "required": ["kpoints", "ecutwfc"]
        },
        "compute_resources": {
            "type": "object",
            "description": "Requested compute resources (nodes, cores, walltime).",
            "properties": {
                "nodes": {"type": "integer", "default": 1},
                "cores_per_node": {"type": "integer", "default": 32},
                "walltime_hours": {"type": "number", "default": 1}
            }
        }
    },
    "required": ["input_structure", "calculation_parameters"]
}


async def run_create_dft_calculation(
    task_manager, # Placeholder: This might be a different TaskManager or AbacusEngine directly
    arguments: dict
) -> mcp_types.ToolResult:
    """
    Handles the creation of a new DFT calculation task using Abacus.

    Args:
        task_manager: The task manager instance (or Abacus engine).
        arguments: A dictionary containing the tool arguments, conforming to CREATE_DFT_CALCULATION_SCHEMA.

    Returns:
        A ToolResult object containing the task_id or an error.
    """
    logger.info(f"Running create_dft_calculation with arguments: {arguments}")

    # 1. Validate arguments against the schema (FastMCP might do some validation)
    #    For complex validation, consider using a library like jsonschema.
    #    Example basic check:
    if not all(key in arguments for key in CREATE_DFT_CALCULATION_SCHEMA["required"]):
        logger.warning("Missing required arguments for create_dft_calculation.")
        raise mcp_types.InvalidToolArgumentsError("Missing required arguments.")

    input_structure = arguments["input_structure"] # Expected to be string (content)
    calc_params = arguments["calculation_parameters"] # Expected to be an object
    compute_res = arguments.get("compute_resources", {}) # Optional, expected to be an object

    # --- Detailed validation for nested parameters ---

    # Validate calculation_parameters
    if not isinstance(calc_params, dict):
        raise mcp_types.InvalidToolArgumentsError("'calculation_parameters' must be an object.")
    
    required_calc_keys = CREATE_DFT_CALCULATION_SCHEMA["properties"]["calculation_parameters"].get("required", [])
    for key in required_calc_keys:
        if key not in calc_params:
            raise mcp_types.InvalidToolArgumentsError(f"Missing required key '{key}' in 'calculation_parameters'.")

    # Validate type for ecutwfc
    if "ecutwfc" in calc_params and not isinstance(calc_params["ecutwfc"], (int, float)):
        raise mcp_types.InvalidToolArgumentsError("'calculation_parameters.ecutwfc' must be a number.")
    # Validate type for kpoints (should be string as per schema)
    if "kpoints" in calc_params and not isinstance(calc_params["kpoints"], str):
        raise mcp_types.InvalidToolArgumentsError("'calculation_parameters.kpoints' must be a string.")

    # Validate compute_resources if provided
    if compute_res: # It defaults to {} if not provided, so this checks if it was actually given
        if not isinstance(compute_res, dict):
            raise mcp_types.InvalidToolArgumentsError("'compute_resources' must be an object if provided.")
        
        if "nodes" in compute_res and not isinstance(compute_res["nodes"], int):
            raise mcp_types.InvalidToolArgumentsError("'compute_resources.nodes' must be an integer.")
        if "cores_per_node" in compute_res and not isinstance(compute_res["cores_per_node"], int):
            raise mcp_types.InvalidToolArgumentsError("'compute_resources.cores_per_node' must be an integer.")
        if "walltime_hours" in compute_res and not isinstance(compute_res["walltime_hours"], (int, float)):
            raise mcp_types.InvalidToolArgumentsError("'compute_resources.walltime_hours' must be a number.")

    # SECURITY NOTE for input_structure:
    # The schema describes 'input_structure' as "content or path".
    # Currently, this tool passes it directly as 'input_structure_data' to AbacusEngine.
    # If AbacusEngine were to interpret this as a server-side file path without sanitization,
    # it would be a path traversal vulnerability.
    # For safety, this implementation assumes 'input_structure' is primarily intended as content.
    # If server-side path access is ever implemented, it MUST be done securely (e.g., restricted base directory).

    # 2. Prepare task configuration for AbacusEngine/TaskManager
    #    This will involve translating MCP tool arguments into a format
    #    that the AbacusEngine can understand.
    dft_task_config = {
        "type": "dft_abacus", # Differentiate from MD tasks
        "input_structure_data": input_structure,
        "abacus_parameters": calc_params,
        "requested_resources": compute_res,
        # Potentially add user info, submission time, etc.
    }

    # 3. Interact with AbacusEngine or a specialized TaskManager
    #    This part is highly dependent on AbacusEngine's design.
    #    For now, this is a placeholder.
    try:
        # Example:
        # if not hasattr(task_manager, 'submit_dft_task'): # Check if using a generic TM
        #     logger.error("TaskManager does not support DFT tasks or AbacusEngine not integrated.")
        #     raise NotImplementedError("DFT task submission not implemented in the current TaskManager/AbacusEngine.")
        #
        # task_id = await task_manager.submit_dft_task(dft_task_config)

        # Placeholder until AbacusEngine and its integration are defined:
        task_id = f"dft-task-placeholder-{hash(str(arguments))}"
        logger.info(f"Placeholder DFT task created with ID: {task_id}")
        
        # Simulate submission to an Abacus system (actual implementation will be async)
        # await abacus_engine.submit_calculation(dft_task_config)

        return mcp_types.ToolResult(
            content={
                "task_id": task_id,
                "status": "submitted_placeholder",
                "message": "DFT calculation task submitted (placeholder). Actual submission to Abacus backend pending."
            }
        )
    except mcp_types.InvalidToolArgumentsError:
        raise # Re-raise for FastMCP to handle
    except NotImplementedError as e:
        logger.error(f"Feature not implemented: {e}", exc_info=True)
        raise mcp_types.MCPError(f"Feature not implemented: {e}")
    except Exception as e:
        logger.error(f"Error during DFT task creation: {e}", exc_info=True)
        raise mcp_types.MCPError(f"Failed to create DFT task: {e}")

# Example of how this tool's definition could be registered if not hardcoded in server.py
# def get_tool_definition() -> mcp_types.ToolDefinition:
#     return mcp_types.ToolDefinition(
#         name="create_dft_calculation",
#         description="Creates an Abacus DFT (Density Functional Theory) calculation task.",
#         input_schema=CREATE_DFT_CALCULATION_SCHEMA
#     )