# src/resources/calculation_results_resource.py

import json
from typing import Tuple, Optional, Dict, Any
from urllib.parse import urlparse

from src.task_manager import TaskManager # Assuming TaskManager is accessible
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

# URI Scheme: openmm://tasks/{task_id}/results

async def read_calculation_results_resource(
    task_manager: TaskManager,
    uri: str,
    byte_range: Optional[Tuple[int, int]] = None # Usually not applicable for JSON results summary
) -> Tuple[bytes, str]: # (content_bytes, mime_type)
    """
    Reads the calculation results resource for a given task.
    The URI is expected to be in the format: openmm://tasks/{task_id}/results
    """
    logger.info(f"Reading calculation results resource for URI: {uri}")

    parsed_uri = urlparse(uri)
    if parsed_uri.scheme != "openmm" or parsed_uri.netloc != "tasks":
        error_msg = f"Invalid URI scheme or netloc for calculation results resource: {uri}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg}).encode('utf-8'), "application/json"

    path_parts = parsed_uri.path.strip('/').split('/')
    # Expected path: {task_id}/results
    if len(path_parts) != 2 or path_parts[1] != "results":
        error_msg = f"Invalid URI path format for calculation results resource: {parsed_uri.path}. Expected /{{task_id}}/results"
        logger.error(error_msg)
        return json.dumps({"error": error_msg}).encode('utf-8'), "application/json"

    task_id = path_parts[0]

    try:
        # TaskManager.get_task_results already returns a Dict or None/error dict
        results_data = await task_manager.get_task_results(task_id)
        
        if results_data is None: # Should be handled by get_task_results if task not completed
            message = f"Results for task {task_id} are not available or task not found/completed."
            logger.warning(message)
            # get_task_results returns a specific message for non-completed tasks.
            # If it strictly returns None only on error or truly no data for completed:
            return json.dumps({"error": message, "task_id": task_id}).encode('utf-8'), "application/json"

        content_bytes = json.dumps(results_data, indent=4).encode('utf-8')
        
        if byte_range:
            start, end = byte_range
            content_bytes = content_bytes[start:end+1]
            logger.debug(f"Applied byte_range {byte_range} to calculation results for {task_id}")

        return content_bytes, "application/json"
        
    except ValueError as ve: # Task not found from get_task_results -> _get_task_or_raise
        logger.warning(f"Task not found for results URI {uri}: {ve}")
        return json.dumps({"error": str(ve), "task_id": task_id, "status": "not_found"}).encode('utf-8'), "application/json"
    except Exception as e:
        logger.error(f"Unexpected error reading calculation results for URI {uri}: {e}", exc_info=True)
        return json.dumps({"error": f"An unexpected server error occurred: {str(e)}"}).encode('utf-8'), "application/json"

# Example of how this might be dispatched in server.py's read_resource method:
#
# elif len(path_parts) == 2 and path_parts[1] == "results":
#     # from .resources.calculation_results_resource import read_calculation_results_resource
#     return await read_calculation_results_resource(global_task_manager, uri, byte_range)