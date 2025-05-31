# src/tools/control_simulation.py

from typing import Dict, Any
from src.task_manager import TaskManager # Assuming TaskManager is accessible
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

CONTROL_SIMULATION_SCHEMA = {
    "type": "object",
    "properties": {
        "task_id": {"type": "string", "description": "ID of the task to control."},
        "action": {
            "type": "string",
            "enum": ["start", "pause", "resume", "stop", "delete"],
            "description": "The control action to perform on the task."
        }
        # "parameters": { # Optional field for future extensions, not currently used
        #     "type": "object",
        #     "description": "Optional parameters for the control action."
        # }
    },
    "required": ["task_id", "action"]
}

async def run_control_simulation(task_manager: TaskManager, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Controls the execution of a simulation task (start, pause, resume, stop).

    Args:
        task_manager: An instance of the TaskManager.
        arguments: A dictionary containing "task_id" and "action".
                   "action" can be one of ["start", "pause", "resume", "stop", "delete"].
                   "parameters" is an optional field for future extensions.
    
    Returns:
        A dictionary indicating success or failure.
    """
    task_id = arguments.get("task_id")
    action = arguments.get("action")
    # params = arguments.get("parameters", {}) # Reserved for future use

    logger.info(f"Running 'control_simulation' tool for task_id: {task_id}, action: {action}")

    if not task_id or not action:
        error_msg = "Missing required arguments: task_id or action."
        logger.error(error_msg)
        return {"error": error_msg, "status_code": 400}

    allowed_actions = ["start", "pause", "resume", "stop", "delete"]
    if action not in allowed_actions:
        error_msg = f"Invalid action '{action}'. Allowed actions are: {', '.join(allowed_actions)}."
        logger.error(error_msg)
        return {"error": error_msg, "status_code": 400}

    try:
        message = "" # Initialize message
        if action == "start":
            await task_manager.start_task(task_id)
            message = f"Task {task_id} start initiated."
        elif action == "pause":
            await task_manager.pause_task(task_id)
            message = f"Task {task_id} pause initiated."
        elif action == "resume":
            await task_manager.resume_task(task_id) # resume_task calls start_task internally
            message = f"Task {task_id} resume initiated."
        elif action == "stop":
            await task_manager.stop_task(task_id)
            message = f"Task {task_id} stop initiated."
        elif action == "delete":
            await task_manager.delete_task(task_id)
            message = f"Task {task_id} delete initiated and processed."
            logger.info(message)
            # For delete action, task status is no longer relevant as it's gone.
            return {
                "task_id": task_id,
                "action_taken": action,
                "message": message,
                "current_status": "deleted"
            }
        # No 'else' needed here as invalid actions are caught above.
        
        logger.info(message)
        # Fetch current status to return for actions other than delete
        current_status_info = await task_manager.get_task_status(task_id)
        return {
            "task_id": task_id,
            "action_taken": action,
            "message": message,
            "current_status": current_status_info.get("status", "unknown")
        }

    except ValueError as ve: # Raised by _get_task_or_raise if task_id not found (or for delete if already deleted before this call)
        logger.error(f"ValueError in 'control_simulation' for task {task_id}, action {action}: {ve}")
        return {"error": str(ve), "status_code": 404} # Not found
    except Exception as e:
        logger.error(f"Unexpected error in 'control_simulation' for task {task_id}, action {action}: {e}", exc_info=True)
        return {"error": f"An unexpected server error occurred: {str(e)}", "status_code": 500}