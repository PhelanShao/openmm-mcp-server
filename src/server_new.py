# src/server_new.py
# 新的OpenMM MCP Server实现，使用最新的FastMCP API

from fastmcp import FastMCP
import asyncio
import json
import os
from typing import Dict, Any, Optional

from .task_manager import TaskManager
from .config import AppConfig
from .utils.logging_config import get_logger
from .abacus_engine import AbacusEngine
from .advanced_md_tools import register_advanced_md_tools

# Initialize logger
logger = get_logger(__name__)

# Create FastMCP server instance
mcp = FastMCP(
    name="OpenMMComputeServer",
    description="MCP Server for OpenMM molecular dynamics simulations and DFT calculations."
)

# Initialize components
try:
    app_config = AppConfig()
    task_manager = TaskManager()
    abacus_engine = AbacusEngine()
    
    # 注册高级MD工具
    advanced_tools = register_advanced_md_tools(mcp, task_manager)
    logger.info(f"Registered {len(advanced_tools)} advanced MD tools")
    
    logger.info("Server components initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize server components: {e}", exc_info=True)
    task_manager = None
    abacus_engine = None

# Tool definitions using FastMCP decorators
@mcp.tool()
async def create_md_simulation(
    pdb_file: str,
    forcefield: list[str],
    steps: int,
    integrator: dict,
    platform_name: Optional[str] = None,
    output_config: Optional[dict] = None,
    minimize_energy: bool = False,
    nonbonded_method: str = "PME",
    nonbonded_cutoff_nm: float = 1.0,
    constraints: str = "HBonds"
) -> str:
    """
    Creates a molecular dynamics simulation task.
    
    Args:
        pdb_file: PDB file content as string
        forcefield: List of force field XML files
        steps: Number of simulation steps
        integrator: Integrator configuration dict
        platform_name: OpenMM platform name (CUDA, OpenCL, CPU, etc.)
        output_config: Output configuration for reporters
        minimize_energy: Whether to perform energy minimization
        nonbonded_method: Nonbonded method (PME, NoCutoff, etc.)
        nonbonded_cutoff_nm: Nonbonded cutoff in nanometers
        constraints: Constraint type (HBonds, AllBonds, None)
    
    Returns:
        Task ID of the created simulation
    """
    if not task_manager:
        raise Exception("TaskManager not available")
    
    config = {
        "task_type": "md",
        "pdb_data": pdb_file,
        "pdb_input_type": "content",
        "forcefield_files": forcefield,
        "steps": steps,
        "integrator": integrator,
        "platform_name": platform_name,
        "output_config": output_config or {},
        "minimize_energy": minimize_energy,
        "nonbonded_method": nonbonded_method,
        "nonbonded_cutoff_nm": nonbonded_cutoff_nm,
        "constraints": constraints
    }
    
    try:
        task_id = await task_manager.create_task(config)
        logger.info(f"Created MD simulation task: {task_id}")
        return f"MD simulation task created successfully. Task ID: {task_id}"
    except Exception as e:
        logger.error(f"Failed to create MD simulation: {e}")
        raise Exception(f"Failed to create MD simulation: {str(e)}")

@mcp.tool()
async def create_dft_calculation(
    input_structure: str,
    calculation_parameters: dict,
    compute_resources: Optional[dict] = None
) -> str:
    """
    Creates a DFT calculation task using Abacus.
    
    Args:
        input_structure: Structure file content (POSCAR format)
        calculation_parameters: DFT calculation parameters
        compute_resources: Computational resource specifications
    
    Returns:
        Task ID of the created DFT calculation
    """
    if not task_manager:
        raise Exception("TaskManager not available")
    
    config = {
        "task_type": "dft",
        "input_structure": input_structure,
        "dft_params": calculation_parameters,
        "compute_resources": compute_resources or {}
    }
    
    try:
        task_id = await task_manager.create_task(config)
        logger.info(f"Created DFT calculation task: {task_id}")
        return f"DFT calculation task created successfully. Task ID: {task_id}"
    except Exception as e:
        logger.error(f"Failed to create DFT calculation: {e}")
        raise Exception(f"Failed to create DFT calculation: {str(e)}")

@mcp.tool()
async def control_simulation(
    task_id: str,
    action: str
) -> str:
    """
    Controls a simulation task execution.
    
    Args:
        task_id: ID of the task to control
        action: Action to perform (start, pause, resume, stop, delete)
    
    Returns:
        Status message
    """
    if not task_manager:
        raise Exception("TaskManager not available")
    
    valid_actions = ["start", "pause", "resume", "stop", "delete"]
    if action not in valid_actions:
        raise ValueError(f"Invalid action '{action}'. Must be one of: {valid_actions}")
    
    try:
        if action == "start":
            await task_manager.start_task(task_id)
            message = f"Task {task_id} started successfully"
        elif action == "pause":
            await task_manager.pause_task(task_id)
            message = f"Task {task_id} paused successfully"
        elif action == "resume":
            await task_manager.resume_task(task_id)
            message = f"Task {task_id} resumed successfully"
        elif action == "stop":
            await task_manager.stop_task(task_id)
            message = f"Task {task_id} stopped successfully"
        elif action == "delete":
            await task_manager.delete_task(task_id)
            message = f"Task {task_id} deleted successfully"
        
        logger.info(f"Control action '{action}' executed for task {task_id}")
        return message
    except Exception as e:
        logger.error(f"Failed to execute control action '{action}' for task {task_id}: {e}")
        raise Exception(f"Failed to execute action '{action}': {str(e)}")

@mcp.tool()
async def analyze_results(
    task_id: str,
    analysis_type: str = "energy"
) -> str:
    """
    Analyzes simulation results.
    
    Args:
        task_id: ID of the task to analyze
        analysis_type: Type of analysis to perform
    
    Returns:
        Analysis results as JSON string
    """
    if not task_manager:
        raise Exception("TaskManager not available")
    
    try:
        # Get task results
        results = await task_manager.get_task_results(task_id)
        if not results:
            return f"No results available for task {task_id}"
        
        # Perform basic analysis based on type
        if analysis_type == "energy":
            final_state = results.get("final_state", {})
            energy = final_state.get("potential_energy")
            if energy:
                analysis = {
                    "analysis_type": "energy",
                    "task_id": task_id,
                    "potential_energy": energy,
                    "unit": "kJ/mol"
                }
            else:
                analysis = {
                    "analysis_type": "energy",
                    "task_id": task_id,
                    "message": "No energy data available"
                }
        elif analysis_type == "trajectory_info":
            output_files = results.get("output_files", {})
            trajectory_file = output_files.get("dcd_reporter_file")
            analysis = {
                "analysis_type": "trajectory_info",
                "task_id": task_id,
                "trajectory_file": trajectory_file,
                "available_files": list(output_files.keys())
            }
        else:
            analysis = {
                "analysis_type": analysis_type,
                "task_id": task_id,
                "message": f"Analysis type '{analysis_type}' not implemented",
                "available_types": ["energy", "trajectory_info"]
            }
        
        logger.info(f"Analysis completed for task {task_id}, type: {analysis_type}")
        return json.dumps(analysis, indent=2)
    except Exception as e:
        logger.error(f"Failed to analyze results for task {task_id}: {e}")
        raise Exception(f"Failed to analyze results: {str(e)}")

@mcp.tool()
async def get_task_status(task_id: str) -> str:
    """
    Gets the status of a specific task.
    
    Args:
        task_id: ID of the task
    
    Returns:
        Task status information as JSON string
    """
    if not task_manager:
        raise Exception("TaskManager not available")
    
    try:
        status = await task_manager.get_task_status(task_id)
        return json.dumps(status, indent=2)
    except Exception as e:
        logger.error(f"Failed to get status for task {task_id}: {e}")
        raise Exception(f"Failed to get task status: {str(e)}")

@mcp.tool()
async def list_all_tasks() -> str:
    """
    Lists all tasks in the system.
    
    Returns:
        List of all tasks as JSON string
    """
    if not task_manager:
        raise Exception("TaskManager not available")
    
    try:
        tasks = task_manager.get_all_tasks()
        task_list = []
        for task in tasks:
            task_info = {
                "task_id": task.task_id,
                "task_type": task.task_type,
                "status": task.status,
                "progress": task.progress
            }
            task_list.append(task_info)
        
        return json.dumps({"tasks": task_list}, indent=2)
    except Exception as e:
        logger.error(f"Failed to list tasks: {e}")
        raise Exception(f"Failed to list tasks: {str(e)}")

# Resource definitions
@mcp.resource("openmm://tasks/{task_id}/status")
async def get_task_status_resource(task_id: str) -> dict:
    """Get task status as a resource."""
    if not task_manager:
        raise Exception("TaskManager not available")
    
    try:
        status = await task_manager.get_task_status(task_id)
        return status
    except Exception as e:
        logger.error(f"Failed to get task status resource for {task_id}: {e}")
        raise Exception(f"Failed to get task status: {str(e)}")

@mcp.resource("openmm://tasks/{task_id}/results")
async def get_task_results_resource(task_id: str) -> dict:
    """Get task results as a resource."""
    if not task_manager:
        raise Exception("TaskManager not available")
    
    try:
        results = await task_manager.get_task_results(task_id)
        return results or {"message": "No results available"}
    except Exception as e:
        logger.error(f"Failed to get task results resource for {task_id}: {e}")
        raise Exception(f"Failed to get task results: {str(e)}")

# Main execution
if __name__ == "__main__":
    logger.info("Starting OpenMM MCP Server...")
    mcp.run()