# src/resources/task_status_resource.py

import json
from typing import Tuple, Optional, Dict, Any
from urllib.parse import urlparse, parse_qs

from src.task_manager import TaskManager # Assuming TaskManager is accessible
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

# URI Scheme: openmm://tasks/{task_id}/status

async def read_task_status_resource(
    task_manager: TaskManager, 
    uri: str, 
    byte_range: Optional[Tuple[int, int]] = None # Usually not applicable for JSON status
) -> Tuple[bytes, str]: # (content_bytes, mime_type)
    """
    Reads the status resource for a given task.
    The URI is expected to be in the format: openmm://tasks/{task_id}/status
    """
    logger.info(f"Reading task status resource for URI: {uri}")

    parsed_uri = urlparse(uri)
    if parsed_uri.scheme != "openmm" or parsed_uri.netloc != "tasks":
        error_msg = f"Invalid URI scheme or netloc for task status resource: {uri}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg}).encode('utf-8'), "application/json"

    path_parts = parsed_uri.path.strip('/').split('/')
    # Expected path: {task_id}/status
    if len(path_parts) != 2 or path_parts[1] != "status":
        error_msg = f"Invalid URI path format for task status resource: {parsed_uri.path}. Expected /{{task_id}}/status"
        logger.error(error_msg)
        return json.dumps({"error": error_msg}).encode('utf-8'), "application/json"

    task_id = path_parts[0]

    try:
        status_info = await task_manager.get_task_status(task_id)
        # get_task_status already returns a Dict, which is good for JSON
        
        # Apply byte_range if provided and sensible (though unlikely for a status JSON)
        content_bytes = json.dumps(status_info, indent=4).encode('utf-8')
        
        if byte_range:
            start, end = byte_range
            content_bytes = content_bytes[start:end+1] # Slicing bytes
            logger.debug(f"Applied byte_range {byte_range} to task status for {task_id}")

        return content_bytes, "application/json"
        
    except ValueError as ve: # Task not found from get_task_status -> _get_task_or_raise
        logger.warning(f"Task not found for status URI {uri}: {ve}")
        return json.dumps({"error": str(ve), "task_id": task_id, "status": "not_found"}).encode('utf-8'), "application/json"
    except Exception as e:
        logger.error(f"Unexpected error reading task status for URI {uri}: {e}", exc_info=True)
        return json.dumps({"error": f"An unexpected server error occurred: {str(e)}"}).encode('utf-8'), "application/json"

# Example of how this might be dispatched in server.py's read_resource method:
#
# async def read_resource(uri: mcp_types.URI, byte_range: mcp_types.Range | None = None) -> tuple[bytes, str]:
#     parsed_uri = urlparse(uri)
#     if parsed_uri.scheme == "openmm" and parsed_uri.netloc == "tasks":
#         path_parts = parsed_uri.path.strip('/').split('/')
#         if len(path_parts) == 2 and path_parts[1] == "status":
#             # from .resources.task_status_resource import read_task_status_resource
#             return await read_task_status_resource(global_task_manager, uri, byte_range)
#         # ... handle other task-related resources like results, trajectory ...
#     
#     logger.error(f"Unsupported resource URI: {uri}")
#     return b"Resource not found or URI unsupported.", "text/plain"