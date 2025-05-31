# src/resources/generic_file_resource.py

import asyncio
import json
import os
import mimetypes # For guessing MIME types
from typing import Tuple, Optional

from src.task_manager import TaskManager
from src.utils.logging_config import get_logger
from src.config import config as app_config # For TASK_DATA_DIR
from mcp import types as mcp_types # For mcp_types.Range if needed, though byte_range is standard tuple

logger = get_logger(__name__)

async def read_generic_task_file_resource(
    task_manager: TaskManager,
    task_id: str,
    file_category: str, # e.g., "checkpoint", "outputs/logs", or "" for files directly in "outputs"
    filename: str,
    byte_range: Optional[Tuple[int, int]] = None
) -> Tuple[bytes, str]: # (content_bytes, mime_type)
    """
    Reads a generic file associated with a task, such as checkpoints or other output files.
    file_category can specify a subfolder within the task's "outputs" directory,
    or indicate a special type like "checkpoint".
    """
    logger.info(f"Reading generic file '{filename}' in category '{file_category}' for task ID: {task_id}")

    try:
        # Ensure task exists
        task = task_manager._get_task_or_raise(task_id) # Raises ValueError if not found

        expected_base_dir_abs: str
        file_path: str

        if file_category.startswith("dft_"):
            # For DFT tasks, files are located in TASK_DATA_DIR/{task_id}/dft_calc/
            # The 'filename' argument might include subdirectories like "OUT.ABACUS/running_scf.log".
            # The specific dft_ sub-category (e.g., dft_input, dft_logs) is mainly for URI routing
            # and doesn't necessarily form part of the directory structure if 'filename' is comprehensive.
            base_dir_for_dft = os.path.join(app_config.TASK_DATA_DIR, task_id, "dft_calc")
            file_path = os.path.join(base_dir_for_dft, filename)
            expected_base_dir_abs = os.path.abspath(base_dir_for_dft)
            logger.debug(f"Task [{task_id}] DFT file: category='{file_category}', resolved base='{expected_base_dir_abs}', full path='{file_path}'")
        else:
            # For MD tasks or other generic files expected under the "outputs" directory
            md_outputs_dir = os.path.join(app_config.TASK_DATA_DIR, task_id, "outputs")
            expected_base_dir_abs = os.path.abspath(md_outputs_dir)

            if file_category == "checkpoint": # Checkpoints are directly in "outputs"
                file_path = os.path.join(md_outputs_dir, filename)
            elif file_category: # Other categories form subdirectories under "outputs"
                file_path = os.path.join(md_outputs_dir, file_category, filename)
            else: # Empty category means file is directly in "outputs"
                file_path = os.path.join(md_outputs_dir, filename)
            logger.debug(f"Task [{task_id}] MD/Output file: category='{file_category}', resolved base='{expected_base_dir_abs}', full path='{file_path}'")

        # Security check: Ensure the resolved path is under the determined base directory
        resolved_file_path_abs = os.path.abspath(file_path)
        if not resolved_file_path_abs.startswith(expected_base_dir_abs):
            error_msg = f"Access denied: File path '{resolved_file_path_abs}' is outside the allowed base directory '{expected_base_dir_abs}' for task {task_id}."
            logger.error(error_msg)
            return json.dumps({"error": error_msg, "task_id": task_id}).encode('utf-8'), "application/json"

        if not os.path.exists(resolved_file_path_abs) or not os.path.isfile(resolved_file_path_abs):
            error_msg = f"File not found at path: {resolved_file_path_abs}"
            logger.error(error_msg)
            return json.dumps({"error": error_msg, "task_id": task_id}).encode('utf-8'), "application/json"

        # Determine MIME type
        mime_type, _ = mimetypes.guess_type(resolved_file_path_abs)
        if mime_type is None:
            if filename.endswith(".log"): # Common case not always in mimetypes db
                mime_type = "text/plain"
            else:
                mime_type = "application/octet-stream" # Default

        # Read file content
        def read_file_chunk():
            with open(resolved_file_path_abs, 'rb') as f:
                if byte_range:
                    start, end = byte_range
                    f.seek(start)
                    length_to_read = (end - start) + 1
                    return f.read(length_to_read)
                else:
                    return f.read()

        content_bytes = await asyncio.to_thread(read_file_chunk)
        logger.info(f"Successfully read {len(content_bytes)} bytes from {resolved_file_path_abs} for task {task_id}.")
        return content_bytes, mime_type

    except ValueError as ve: # Task not found (from _get_task_or_raise)
        logger.warning(f"Task {task_id} not found when trying to read file '{filename}' (category: '{file_category}'): {ve}")
        return json.dumps({"error": str(ve), "task_id": task_id, "status": "not_found"}).encode('utf-8'), "application/json"
    except Exception as e:
        logger.error(f"Unexpected error reading file '{filename}' (category: '{file_category}') for task {task_id}: {e}", exc_info=True)
        return json.dumps({"error": f"An unexpected server error occurred: {str(e)}"}).encode('utf-8'), "application/json"
