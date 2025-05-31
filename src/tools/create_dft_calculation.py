# src/tools/create_dft_calculation.py
# Tool for creating Abacus DFT calculation tasks.

from mcp import types as mcp_types
from src.utils.logging_config import get_logger
from src.task_manager import TaskManager # Import TaskManager
# from src.abacus_engine import AbacusEngine # AbacusEngine is used by TaskManager

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
    task_manager: TaskManager,
    arguments: dict
) -> mcp_types.ToolResult:
    """
    Handles the creation of a new DFT calculation task via the TaskManager.

    Args:
        task_manager: The TaskManager instance.
        arguments: A dictionary containing the tool arguments, conforming to CREATE_DFT_CALCULATION_SCHEMA.

    Returns:
        A ToolResult object containing the task_id or an error.
    """
    logger.info(f"Running create_dft_calculation with arguments: {arguments}")

    # 1. Validate arguments against the schema (FastMCP might do some validation)
    # 1. Argument validation (FastMCP might do basic validation based on schema)
    #    The schema defines 'input_structure' and 'calculation_parameters' as required.
    #    Additional detailed validation can be done here if needed.
    #    The existing validation logic is quite good and can be largely kept.

    try:
        if not all(key in arguments for key in CREATE_DFT_CALCULATION_SCHEMA["required"]):
            logger.warning("Missing required arguments for create_dft_calculation.")
            raise mcp_types.InvalidToolArgumentsError("Missing required arguments based on schema.")

        input_structure_content = arguments["input_structure"] # String content
        calculation_params = arguments["calculation_parameters"] # Object/dict
        compute_resources = arguments.get("compute_resources", {}) # Optional

        # Validate calculation_parameters structure (example, can be more detailed)
        if not isinstance(calculation_params, dict):
            raise mcp_types.InvalidToolArgumentsError("'calculation_parameters' must be an object.")
        required_calc_keys = CREATE_DFT_CALCULATION_SCHEMA["properties"]["calculation_parameters"].get("required", [])
        for key in required_calc_keys:
            if key not in calculation_params:
                raise mcp_types.InvalidToolArgumentsError(f"Missing required key '{key}' in 'calculation_parameters'.")
        
        # Further type checks as in original code...
        if "ecutwfc" in calculation_params and not isinstance(calculation_params["ecutwfc"], (int, float)):
             raise mcp_types.InvalidToolArgumentsError("'calculation_parameters.ecutwfc' must be a number.")
        if "kpoints" in calculation_params and not isinstance(calculation_params["kpoints"], str): # As per schema
             raise mcp_types.InvalidToolArgumentsError("'calculation_parameters.kpoints' must be a string.")


        # 2. Construct task configuration for TaskManager
        #    This includes the task_type and DFT-specific parameters.
        task_config = {
            "task_type": "dft",
            "dft_params": { # Nest all DFT related parameters under a specific key
                "input_structure": input_structure_content,
                "calculation_parameters": calculation_params,
                "compute_resources": compute_resources
            },
            # Include other parameters that might be relevant for AbacusEngine via TaskManager
            # For example, if Abacus command needs to be specified per task:
            # "abacus_command": arguments.get("abacus_command_override")
        }

        # 3. Create task using TaskManager
        task_id = await task_manager.create_task(task_config)

        logger.info(f"DFT calculation task created successfully with ID: {task_id}")
        return mcp_types.ToolResult(
            status_code=0, # Using 0 for success as per common conventions if not specified otherwise
            data={ # Changed from 'content' to 'data' to align with potential ToolResult evolution
                "task_id": task_id,
                "status": "pending", # Initial status after creation
                "message": "DFT calculation task created successfully."
            }
        )

    except mcp_types.InvalidToolArgumentsError as e:
        logger.warning(f"Invalid arguments for create_dft_calculation: {e}")
        raise # Re-raise for FastMCP to handle and return appropriate error to client
    except ValueError as ve: # Catch ValueErrors from task_manager.create_task
        logger.error(f"ValueError during DFT task creation: {ve}", exc_info=True)
        # Return as a generic MCPError or a more specific one if available
        raise mcp_types.MCPError(f"Failed to create DFT task due to invalid configuration: {ve}")
    except Exception as e:
        logger.error(f"Unexpected error during DFT task creation: {e}", exc_info=True)
        # Generic error for unexpected issues
        raise mcp_types.MCPError(f"An unexpected error occurred while creating the DFT task: {e}")

# Example of how this tool's definition could be registered if not hardcoded in server.py
# def get_tool_definition() -> mcp_types.ToolDefinition:
#     return mcp_types.ToolDefinition(
#         name="create_dft_calculation",
#         description="Creates an Abacus DFT (Density Functional Theory) calculation task.",
#         input_schema=CREATE_DFT_CALCULATION_SCHEMA
#     )