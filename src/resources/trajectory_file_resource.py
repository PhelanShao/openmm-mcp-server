# src/resources/trajectory_file_resource.py

import asyncio
import json
import os
from typing import Tuple, Optional, Dict, Any
from urllib.parse import urlparse, parse_qs

from src.task_manager import TaskManager # Assuming TaskManager is accessible
from src.utils.logging_config import get_logger
from src.config import config as app_config # For TASK_DATA_DIR

logger = get_logger(__name__)

# The filename will be provided directly from the parsed URI by the server's read_resource function.

async def read_trajectory_file_resource(
    task_manager: TaskManager,
    task_id: str,
    filename: str,
    byte_range: Optional[Tuple[int, int]] = None
) -> Tuple[bytes, str]: # (content_bytes, mime_type)
    """
    Reads a specific trajectory file for a given task.
    The filename is provided directly.
    """
    logger.info(f"Reading trajectory file '{filename}' for task ID: {task_id}")

    try:
        # Ensure task exists, which also implicitly checks if task_id is valid.
        # We don't necessarily need full task details unless validating filename against task's known outputs.
        # For now, directly construct path. Consider adding validation against task.results if needed.
        task = task_manager._get_task_or_raise(task_id) # Synchronous, raises ValueError if not found

        # Construct path based on conventions from TaskManager._process_output_paths
        # Assumes trajectory files are in TASK_DATA_DIR/{task_id}/outputs/{filename}
        trajectory_file_path = os.path.join(app_config.TASK_DATA_DIR, task_id, "outputs", filename)
        
        # Basic security check: ensure the resolved path is under the task's output directory
        # This helps prevent directory traversal if filename contained '..'
        expected_task_output_dir = os.path.abspath(os.path.join(app_config.TASK_DATA_DIR, task_id, "outputs"))
        resolved_file_path = os.path.abspath(trajectory_file_path)

        if not resolved_file_path.startswith(expected_task_output_dir):
            error_msg = f"Access denied: Trajectory file path '{filename}' is outside the allowed directory for task {task_id}."
            logger.error(error_msg)
            # Return as JSON error as per existing pattern, but status should indicate forbidden/bad request
            return json.dumps({"error": error_msg, "task_id": task_id}).encode('utf-8'), "application/json"


        if not os.path.exists(resolved_file_path) or not os.path.isfile(resolved_file_path):
            error_msg = f"Trajectory file not found at path: {resolved_file_path}"
            logger.error(error_msg)
            # Return as JSON error, consistent with how other errors are reported by this function
            return json.dumps({"error": error_msg, "task_id": task_id}).encode('utf-8'), "application/json"

        # Determine MIME type based on filename extension
        mime_type = "application/octet-stream" # Default
        if filename.endswith(".dcd"):
            mime_type = "application/vnd.chemdoodle.trajectory.dcd" # Or "chemical/x-dcd"
        elif filename.endswith(".xtc"):
            mime_type = "chemical/x-xtc" # Common, though not official IANA
        # Add other trajectory types if needed

        # Read file content (potentially large, so use async file I/O and byte_range)
        def read_file_chunk():
            with open(resolved_file_path, 'rb') as f:
                if byte_range:
                    start, end = byte_range
                    f.seek(start)
                    length_to_read = (end - start) + 1
                    return f.read(length_to_read)
                else:
                    return f.read()

        content_bytes = await asyncio.to_thread(read_file_chunk)
        logger.info(f"Successfully read {len(content_bytes)} bytes from trajectory {resolved_file_path} for task {task_id}.")
        return content_bytes, mime_type

    except ValueError as ve: # Task not found (from _get_task_or_raise)
        logger.warning(f"Task {task_id} not found when trying to read trajectory '{filename}': {ve}")
        return json.dumps({"error": str(ve), "task_id": task_id, "status": "not_found"}).encode('utf-8'), "application/json"
    except Exception as e:
        logger.error(f"Unexpected error reading trajectory '{filename}' for task {task_id}: {e}", exc_info=True)
        return json.dumps({"error": f"An unexpected server error occurred: {str(e)}"}).encode('utf-8'), "application/json"