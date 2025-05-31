# src/tools/analyze_results.py

from typing import Dict, Any, Optional
from src.task_manager import TaskManager # Assuming TaskManager is accessible
from src.utils.logging_config import get_logger
# Potentially import analysis libraries like MDAnalysis, numpy, matplotlib in the future
# import os
# import mdtraj as md # Example for trajectory analysis

logger = get_logger(__name__)

async def run_analyze_results(task_manager: TaskManager, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyzes the results of a completed simulation task.

    Args:
        task_manager: An instance of the TaskManager.
        arguments: A dictionary containing "task_id", "analysis_type", and optional "parameters".
                   "analysis_type" can be one of ["energy", "rmsd", "rdf", "trajectory"].
    
    Returns:
        A dictionary containing the analysis results or an error message.
    """
    task_id = arguments.get("task_id")
    analysis_type = arguments.get("analysis_type")
    analysis_params = arguments.get("parameters", {})

    logger.info(f"Running 'analyze_results' tool for task_id: {task_id}, type: {analysis_type}, params: {analysis_params}")

    if not task_id or not analysis_type:
        error_msg = "Missing required arguments: task_id or analysis_type."
        logger.error(error_msg)
        return {"error": error_msg, "status_code": 400}

    allowed_analysis_types = ["energy", "rmsd", "rdf", "trajectory_info"] # Renamed trajectory to trajectory_info
    if analysis_type not in allowed_analysis_types:
        error_msg = f"Invalid analysis_type '{analysis_type}'. Allowed types are: {', '.join(allowed_analysis_types)}."
        logger.error(error_msg)
        return {"error": error_msg, "status_code": 400}

    try:
        task_info = await task_manager.get_task_status(task_id) # Get basic task info
        task_status = task_info.get("status")

        if analysis_type == "energy":
            if task_status != "completed":
                error_msg = f"Energy analysis requires the task to be completed. Task {task_id} status is '{task_status}'."
                logger.error(error_msg)
                return {"error": error_msg, "status_code": 400} # Bad request, task not in correct state
        elif task_status != "completed": # For other types, a warning is still good
            warn_msg = f"Task {task_id} is not yet completed (status: '{task_status}'). Analysis may be based on partial data."
            logger.warning(warn_msg)
            # Allow analysis on non-completed tasks for some types (e.g. trajectory_info).

        task_results_data = await task_manager.get_task_results(task_id)
        # Check for results, especially if task was expected to be complete for this analysis type
        if not task_results_data or (analysis_type == "energy" and "final_state" not in task_results_data):
            if task_info.get("status") == "completed": # Should have results if completed
                 error_msg = f"No results found for completed task {task_id}."
                 logger.error(error_msg)
                 return {"error": error_msg, "status_code": 404}
            # If not completed, results might be partial or non-existent
            # Fall through to specific analysis types that might handle this

        analysis_result: Dict[str, Any] = {"task_id": task_id, "analysis_type": analysis_type}

        if analysis_type == "energy":
            final_state = task_results_data.get("final_state", {})
            potential_energy = final_state.get("potential_energy_kj_mol")
            kinetic_energy = final_state.get("kinetic_energy_kj_mol")
            
            if potential_energy is not None:
                analysis_result["potential_energy_kj_mol"] = potential_energy
            if kinetic_energy is not None:
                analysis_result["kinetic_energy_kj_mol"] = kinetic_energy
            if not analysis_result.get("potential_energy_kj_mol") and not analysis_result.get("kinetic_energy_kj_mol"):
                 analysis_result["message"] = "Energy data not found in task results."
            logger.info(f"Energy analysis for {task_id}: {analysis_result}")

        elif analysis_type == "trajectory_info":
            # This might return paths to trajectory files or metadata.
            output_files = task_results_data.get("output_files", {})
            traj_files = {}
            for key, path in output_files.items():
                if "dcd_reporter_file" in key or "xtc_reporter_file" in key:
                    traj_files[key] = path
            
            if traj_files:
                analysis_result["trajectory_files"] = traj_files
                # Further metadata like number of frames would require dedicated trajectory parsing libraries (e.g., MDTraj, MDAnalysis),
                # which can be added as a future enhancement if needed.
            else:
                analysis_result["message"] = "No trajectory files found in task results."
            logger.info(f"Trajectory info for {task_id}: {analysis_result}")
            
        elif analysis_type in ["rmsd", "rdf"]:
            # These require more complex calculations, often needing trajectory files
            # and potentially other libraries (MDAnalysis, mdtraj).
            # Placeholder for now.
            # FUTURE: When implementing these, add robust validation for 'analysis_params'.
            # This includes checking for required keys, correct data types, and secure handling
            # of any file paths (e.g., reference PDB for RMSD) to prevent path traversal.
            output_files = task_results_data.get("output_files", {})
            analysis_result["message"] = (
                f"Analysis type '{analysis_type}' is complex and requires trajectory processing. "
                f"Available output files: {output_files}. "
                "Full implementation pending. Please provide specific parameters if applicable (e.g., in 'parameters' field)."
            )
            logger.info(analysis_result["message"])
            # Example of what might be needed for RMSD:
            # ref_pdb_path = analysis_params.get("reference_pdb_path") # Must be validated!
            # atom_selection = analysis_params.get("atom_selection", "backbone")
            # trajectory_file_key = analysis_params.get("trajectory_file_key", "dcd_reporter_file")
            # traj_path = output_files.get(trajectory_file_key)
            # if not traj_path or not ref_pdb_path:
            #     analysis_result["error"] = "Missing trajectory or reference PDB for RMSD."
            # else:
            #     # ... actual RMSD calculation ...
            #     analysis_result["rmsd_values"] = [...] 

        return analysis_result

    except ValueError as ve: # Raised by _get_task_or_raise if task_id not found
        logger.error(f"ValueError in 'analyze_results' for task {task_id}, type {analysis_type}: {ve}")
        return {"error": str(ve), "status_code": 404}
    except Exception as e:
        logger.error(f"Unexpected error in 'analyze_results' for task {task_id}, type {analysis_type}: {e}", exc_info=True)
        return {"error": f"An unexpected server error occurred: {str(e)}", "status_code": 500}