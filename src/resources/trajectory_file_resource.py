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

# URI Scheme: openmm://tasks/{task_id}/trajectory
# Optional query param: ?type=dcd (or xtc, etc.) to specify which trajectory file if multiple exist.
# Or, the server can have a default (e.g., prefer DCD if available).

async def read_trajectory_file_resource(
    task_manager: TaskManager,
    uri: str,
    byte_range: Optional[Tuple[int, int]] = None
) -> Tuple[bytes, str]: # (content_bytes, mime_type)
    """
    Reads a trajectory file resource for a given task.
    The URI is expected to be in the format: openmm://tasks/{task_id}/trajectory[?type=dcd]
    """
    logger.info(f"Reading trajectory file resource for URI: {uri}")

    parsed_uri = urlparse(uri)
    if parsed_uri.scheme != "openmm" or parsed_uri.netloc != "tasks":
        error_msg = f"Invalid URI scheme or netloc for trajectory resource: {uri}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg}).encode('utf-8'), "application/json"

    path_parts = parsed_uri.path.strip('/').split('/')
    # Expected path: {task_id}/trajectory
    if len(path_parts) != 2 or path_parts[1] != "trajectory":
        error_msg = f"Invalid URI path format for trajectory resource: {parsed_uri.path}. Expected /{{task_id}}/trajectory"
        logger.error(error_msg)
        return json.dumps({"error": error_msg}).encode('utf-8'), "application/json"

    task_id = path_parts[0]
    
    query_params = parse_qs(parsed_uri.query)
    requested_traj_type = query_params.get("type", [None])[0] # e.g., 'dcd', 'xtc'

    try:
        task_results = await task_manager.get_task_results(task_id)
        if not task_results or task_results.get("error"):
            error_msg = task_results.get("error") if isinstance(task_results, dict) else f"Results for task {task_id} not found or task not completed."
            logger.warning(error_msg)
            return json.dumps({"error": error_msg, "task_id": task_id}).encode('utf-8'), "application/json"

        output_files = task_results.get("output_files", {})
        
        trajectory_file_path = None
        mime_type = "application/octet-stream" # Default

        if requested_traj_type:
            key_to_find = f"{requested_traj_type}_reporter_file"
            if key_to_find in output_files:
                trajectory_file_path = os.path.join(app_config.TASK_DATA_DIR, output_files[key_to_find])
                if requested_traj_type == "dcd":
                    mime_type = "chemical/x-dcd"
                elif requested_traj_type == "xtc":
                    mime_type = "chemical/x-xtc" # Common, though not official IANA
        else:
            # Default search order if type not specified
            if "dcd_reporter_file" in output_files:
                trajectory_file_path = os.path.join(app_config.TASK_DATA_DIR, output_files["dcd_reporter_file"])
                mime_type = "chemical/x-dcd"
            elif "xtc_reporter_file" in output_files:
                trajectory_file_path = os.path.join(app_config.TASK_DATA_DIR, output_files["xtc_reporter_file"])
                mime_type = "chemical/x-xtc"
        
        if not trajectory_file_path:
            error_msg = f"No suitable trajectory file found for task {task_id} (requested type: {requested_traj_type}). Available output: {output_files}"
            logger.warning(error_msg)
            return json.dumps({"error": error_msg, "task_id": task_id}).encode('utf-8'), "application/json"

        if not os.path.exists(trajectory_file_path):
            error_msg = f"Trajectory file not found at path: {trajectory_file_path}"
            logger.error(error_msg)
            return json.dumps({"error": error_msg, "task_id": task_id}).encode('utf-8'), "application/json"

        # Read file content (potentially large, so use async file I/O and byte_range)
        def read_file_chunk():
            with open(trajectory_file_path, 'rb') as f:
                if byte_range:
                    start, end = byte_range
                    f.seek(start)
                    # Read up to end byte (inclusive), so length is end - start + 1
                    # However, read takes length, not end position.
                    length_to_read = (end - start) + 1
                    return f.read(length_to_read)
                else:
                    return f.read()

        content_bytes = await asyncio.to_thread(read_file_chunk)
        logger.info(f"Successfully read {len(content_bytes)} bytes from trajectory {trajectory_file_path} for task {task_id}.")
        return content_bytes, mime_type

    except ValueError as ve: # Task not found
        logger.warning(f"Task not found for trajectory URI {uri}: {ve}")
        return json.dumps({"error": str(ve), "task_id": task_id, "status": "not_found"}).encode('utf-8'), "application/json"
    except Exception as e:
        logger.error(f"Unexpected error reading trajectory for URI {uri}: {e}", exc_info=True)
        return json.dumps({"error": f"An unexpected server error occurred: {str(e)}"}).encode('utf-8'), "application/json"