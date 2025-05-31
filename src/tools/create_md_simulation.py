# src/tools/create_md_simulation.py

from typing import Dict, Any, List, Union
from src.task_manager import TaskManager # Assuming TaskManager is accessible
# from src.server import mcp_server # If using FastMCP decorators directly in tool files (alternative)
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

# This tool would typically be registered with the MCP server (e.g., in server.py)
# For now, we define the function that would be called by the server's call_tool handler.

async def run_create_md_simulation(task_manager: TaskManager, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Creates a new molecular dynamics simulation task.

    Args:
        task_manager: An instance of the TaskManager.
        arguments: A dictionary containing the parameters for the simulation task,
                   matching the inputSchema of the "create_md_simulation" tool.
                   Expected keys: "pdb_file", "forcefield", "steps", and optional
                   "temperature", "pressure", "timestep", "platform", "output_config".
    
    Returns:
        A dictionary containing the result of the tool call, typically the task_id.
    """
    logger.info(f"Running 'create_md_simulation' tool with arguments: {arguments}")

    try:
        # Validate required arguments (basic check, schema validation is by MCP server)
        pdb_input = arguments.get("pdb_file") # Can be content or path
        forcefield_input = arguments.get("forcefield") # Can be a single ffxml name or list of names
        steps = arguments.get("steps")

        if not pdb_input or not forcefield_input or steps is None:
            error_msg = "Missing required arguments: pdb_file, forcefield, or steps."
            logger.error(error_msg)
            # In a real MCP tool, you'd return a ToolResult with an error
            # For now, raising ValueError or returning error dict
            return {"error": error_msg, "status_code": 400}


        # --- Prepare TaskManager config from tool arguments ---
        task_config: Dict[str, Any] = {}

        # PDB input: determine if it's content or a path
        # A simple heuristic: if it contains newlines or ends with .pdb and isn't an existing file, assume content.
        # More robustly, the client/caller should specify or the tool should try to resolve.
        # For this implementation, let's assume if it looks like a path and exists, it's a path.
        # Otherwise, if it's a string, it's content.
        # This part might need refinement based on how PDBs are provided.
        if isinstance(pdb_input, str):
            # A more robust check for path vs content might be needed.
            # For now, if it doesn't look like a multi-line string, assume it could be a path.
            # If it's a path, it should be accessible by the server.
            # If it's content, it's passed directly.
            pdb_input_type = arguments.get("pdb_input_type", "content") # "content" or "file_path"
            
            if pdb_input_type == "file_path":
                # SECURITY: Allowing client-specified file paths is a significant security risk (path traversal).
                # For now, this feature is explicitly disabled.
                # Future implementation would require strict path validation against a secure base directory.
                error_msg = "Specifying PDB by server-side 'file_path' is currently not supported for security reasons. Please provide PDB content directly."
                logger.error(error_msg)
                return {"error": error_msg, "status_code": 400}
            elif pdb_input_type == "content":
                task_config["pdb_input_type"] = "content"
                task_config["pdb_data"] = pdb_input
            else:
                error_msg = f"Invalid 'pdb_input_type': {pdb_input_type}. Must be 'content'."
                logger.error(error_msg)
                return {"error": error_msg, "status_code": 400}
        else:
            # Handle cases where pdb_input might be structured (e.g. from another tool)
            # For now, assume string.
            error_msg = "pdb_file argument must be a string."
            logger.error(error_msg)
            return {"error": error_msg, "status_code": 400}


        # Forcefield input
        if isinstance(forcefield_input, str):
            task_config["forcefield_files"] = [forcefield_input]
        elif isinstance(forcefield_input, list):
            task_config["forcefield_files"] = forcefield_input
        else:
            error_msg = "forcefield argument must be a string or a list of strings."
            logger.error(error_msg)
            return {"error": error_msg, "status_code": 400}

        task_config["steps"] = int(steps)

        # Integrator config
        integrator_config: Dict[str, Any] = arguments.get("integrator", {}) # Allow full integrator dict
        if not integrator_config: # Fallback to individual params if integrator dict not provided
            integrator_config["type"] = arguments.get("integrator_type", "LangevinMiddle")
            if arguments.get("temperature") is not None:
                integrator_config["temperature_K"] = float(arguments["temperature"])
            if arguments.get("timestep") is not None:
                integrator_config["step_size_ps"] = float(arguments["timestep"])
            # friction_coeff_ps for Langevin/Brownian can be added if needed
        task_config["integrator"] = integrator_config

        # Platform
        if arguments.get("platform"):
            task_config["platform_name"] = arguments["platform"]
        if arguments.get("platform_properties"): # e.g. {"Precision":"mixed"}
            task_config["platform_properties"] = arguments["platform_properties"]


        # Output configuration
        if arguments.get("output_config"):
            task_config["output_config"] = arguments["output_config"]
        
        # Optional flags for TaskManager's _run_simulation_task
        if arguments.get("minimize_energy") is not None:
            task_config["minimize_energy"] = bool(arguments["minimize_energy"])
        if arguments.get("minimize_max_iterations") is not None:
            task_config["minimize_max_iterations"] = int(arguments["minimize_max_iterations"])
        if arguments.get("minimize_tolerance_kj_mol_nm") is not None:
            task_config["minimize_tolerance_kj_mol_nm"] = float(arguments["minimize_tolerance_kj_mol_nm"])
            
        if arguments.get("set_velocities_to_temperature") is not None:
             task_config["set_velocities_to_temperature"] = bool(arguments["set_velocities_to_temperature"])

        if arguments.get("run_chunk_size") is not None:
            task_config["run_chunk_size"] = int(arguments["run_chunk_size"])
        if arguments.get("checkpoint_interval_steps") is not None:
            task_config["checkpoint_interval_steps"] = int(arguments["checkpoint_interval_steps"])


        # --- Create task using TaskManager ---
        task_id = await task_manager.create_task(task_config)
        logger.info(f"Task {task_id} created successfully by 'create_md_simulation' tool.")

        # Optional: Automatically start the task?
        # The tool definition doesn't specify, so for now, it only creates.
        # If auto-start is desired:
        # await task_manager.start_task(task_id)
        # logger.info(f"Task {task_id} automatically started.")

        return {"task_id": task_id, "status": "pending", "message": "MD simulation task created successfully."}

    except ValueError as ve:
        logger.error(f"ValueError in 'create_md_simulation': {ve}")
        return {"error": str(ve), "status_code": 400}
    except Exception as e:
        logger.error(f"Unexpected error in 'create_md_simulation': {e}", exc_info=True)
        return {"error": f"An unexpected server error occurred: {str(e)}", "status_code": 500}

# Example of how this tool might be registered in server.py with FastMCP
# @mcp_server.tool_handler("create_md_simulation")
# async def handle_create_md_simulation(arguments: Dict[str, Any]):
#     # Assuming task_manager is accessible, e.g., as a global or passed via context
#     # from .main_server_module import global_task_manager # Example
#     return await run_create_md_simulation(global_task_manager, arguments)