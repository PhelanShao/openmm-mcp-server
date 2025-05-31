# src/advanced_md_tools.py
# 高级分子动力学工具，支持OpenMM的完整功能

from fastmcp import FastMCP
from typing import Dict, Any, Optional, List, Union
import json

def register_advanced_md_tools(mcp: FastMCP, task_manager):
    """注册高级MD工具到FastMCP服务器"""
    
    @mcp.tool()
    async def create_advanced_md_simulation(
        # 基本结构输入
        pdb_file: Optional[str] = None,
        pdb_file_path: Optional[str] = None,
        
        # 力场配置
        forcefield_files: List[str] = ["amber19-all.xml", "amber19/tip3pfb.xml"],
        custom_forcefield_params: Optional[Dict] = None,
        
        # 系统设置
        nonbonded_method: str = "PME",  # PME, NoCutoff, CutoffNonPeriodic, CutoffPeriodic, Ewald
        nonbonded_cutoff_nm: float = 1.0,
        switch_distance_nm: Optional[float] = None,
        constraints: str = "HBonds",  # None, HBonds, AllBonds, HAngles
        rigid_water: bool = True,
        constraint_tolerance: float = 1e-6,
        
        # 积分器配置
        integrator_type: str = "LangevinMiddle",  # LangevinMiddle, Verlet, Brownian, VariableLangevin, VariableVerlet, NoseHoover
        temperature_K: float = 300.0,
        friction_coeff_ps: float = 1.0,
        step_size_ps: float = 0.002,
        
        # Nose-Hoover特定参数
        collision_frequency_ps: Optional[float] = None,
        chain_length: Optional[int] = None,
        num_mts: Optional[int] = None,
        num_yoshidasuzuki: Optional[int] = None,
        
        # 平台设置
        platform_name: Optional[str] = None,  # CUDA, OpenCL, CPU, Reference
        platform_properties: Optional[Dict[str, str]] = None,
        
        # 模拟参数
        steps: int = 10000,
        run_chunk_size: int = 1000,
        
        # 能量最小化
        minimize_energy: bool = True,
        minimize_max_iterations: int = 1000,
        minimize_tolerance_kj_mol_nm: Optional[float] = None,
        
        # 初始条件
        set_velocities_to_temperature: bool = True,
        velocity_seed: Optional[int] = None,
        
        # 压力控制（恒压模拟）
        use_barostat: bool = False,
        barostat_type: str = "MonteCarloBarostat",  # MonteCarloBarostat, MonteCarloAnisotropicBarostat, MonteCarloMembraneBarostat
        pressure_bar: float = 1.0,
        pressure_frequency: int = 25,
        
        # 各向异性压力控制
        anisotropic_pressure: Optional[List[float]] = None,  # [px, py, pz]
        
        # 膜压力控制
        surface_tension_bar_nm: Optional[float] = None,
        membrane_axis: str = "Z",  # X, Y, Z
        
        # 输出配置
        trajectory_file: str = "trajectory.dcd",
        trajectory_interval: int = 1000,
        state_data_file: str = "state_data.csv",
        state_data_interval: int = 1000,
        checkpoint_file: Optional[str] = None,
        checkpoint_interval: int = 10000,
        
        # 状态数据输出选项
        report_step: bool = True,
        report_time: bool = True,
        report_potential_energy: bool = True,
        report_kinetic_energy: bool = True,
        report_total_energy: bool = True,
        report_temperature: bool = True,
        report_volume: bool = False,
        report_density: bool = False,
        report_progress: bool = True,
        report_remaining_time: bool = True,
        report_speed: bool = True,
        
        # 高级输出
        save_positions: bool = False,
        save_velocities: bool = False,
        save_forces: bool = False,
        
        # 重启和恢复
        restart_from_checkpoint: Optional[str] = None,
        
        # 自由能计算
        use_free_energy: bool = False,
        lambda_schedule: Optional[List[float]] = None,
        
        # 增强采样
        use_metadynamics: bool = False,
        metadynamics_config: Optional[Dict] = None,
        
        # 约束和限制
        position_restraints: Optional[List[Dict]] = None,
        distance_restraints: Optional[List[Dict]] = None,
        
        # 溶剂化
        add_solvent: bool = False,
        solvent_model: str = "tip3p",  # tip3p, tip4pew, tip5p, spce
        solvent_padding_nm: float = 1.0,
        ion_concentration_M: float = 0.0,
        positive_ion: str = "Na+",
        negative_ion: str = "Cl-",
        
        # 周期性边界条件
        periodic_box_vectors: Optional[List[List[float]]] = None,
        
        # 计算精度
        precision: str = "mixed",  # single, mixed, double
        
        # 其他高级选项
        remove_cm_motion: bool = True,
        hydrogen_mass_amu: Optional[float] = None,
        use_dispersion_correction: bool = True,
        
    ) -> str:
        """
        创建高级分子动力学模拟任务，支持OpenMM的完整功能。
        
        这个工具支持OpenMM的所有主要功能，包括：
        - 多种积分器（Langevin, Verlet, Nose-Hoover等）
        - 压力控制（各向同性、各向异性、膜系统）
        - 约束和限制
        - 自由能计算
        - 增强采样方法
        - 溶剂化
        - 高精度计算
        """
        
        if not task_manager:
            raise Exception("TaskManager not available")
        
        # 验证输入
        if not pdb_file and not pdb_file_path:
            raise ValueError("必须提供pdb_file或pdb_file_path")
        
        # 构建完整的配置
        config = {
            "task_type": "md",
            
            # 结构输入
            "pdb_data": pdb_file,
            "pdb_file_path": pdb_file_path,
            "pdb_input_type": "content" if pdb_file else "file_path",
            
            # 力场
            "forcefield_files": forcefield_files,
            "custom_forcefield_params": custom_forcefield_params,
            
            # 系统参数
            "nonbonded_method": nonbonded_method,
            "nonbonded_cutoff_nm": nonbonded_cutoff_nm,
            "switch_distance_nm": switch_distance_nm,
            "constraints": constraints,
            "rigid_water": rigid_water,
            "constraint_tolerance": constraint_tolerance,
            
            # 积分器
            "integrator": {
                "type": integrator_type,
                "temperature_K": temperature_K,
                "friction_coeff_ps": friction_coeff_ps,
                "step_size_ps": step_size_ps,
                "collision_frequency_ps": collision_frequency_ps,
                "chain_length": chain_length,
                "num_mts": num_mts,
                "num_yoshidasuzuki": num_yoshidasuzuki,
            },
            
            # 平台
            "platform_name": platform_name,
            "platform_properties": platform_properties or {},
            
            # 模拟
            "steps": steps,
            "run_chunk_size": run_chunk_size,
            
            # 能量最小化
            "minimize_energy": minimize_energy,
            "minimize_max_iterations": minimize_max_iterations,
            "minimize_tolerance_kj_mol_nm": minimize_tolerance_kj_mol_nm,
            
            # 初始条件
            "set_velocities_to_temperature": set_velocities_to_temperature,
            "velocity_seed": velocity_seed,
            
            # 压力控制
            "barostat": {
                "use_barostat": use_barostat,
                "type": barostat_type,
                "pressure_bar": pressure_bar,
                "frequency": pressure_frequency,
                "anisotropic_pressure": anisotropic_pressure,
                "surface_tension_bar_nm": surface_tension_bar_nm,
                "membrane_axis": membrane_axis,
            } if use_barostat else None,
            
            # 输出配置
            "output_config": {
                "trajectory": {
                    "file": trajectory_file,
                    "interval": trajectory_interval,
                    "save_positions": save_positions,
                    "save_velocities": save_velocities,
                    "save_forces": save_forces,
                },
                "state_data": {
                    "file": state_data_file,
                    "interval": state_data_interval,
                    "step": report_step,
                    "time": report_time,
                    "potential_energy": report_potential_energy,
                    "kinetic_energy": report_kinetic_energy,
                    "total_energy": report_total_energy,
                    "temperature": report_temperature,
                    "volume": report_volume,
                    "density": report_density,
                    "progress": report_progress,
                    "remaining_time": report_remaining_time,
                    "speed": report_speed,
                },
                "checkpoint": {
                    "file": checkpoint_file,
                    "interval": checkpoint_interval,
                } if checkpoint_file else None,
            },
            
            # 重启
            "restart_from_checkpoint": restart_from_checkpoint,
            
            # 自由能
            "free_energy": {
                "use_free_energy": use_free_energy,
                "lambda_schedule": lambda_schedule,
            } if use_free_energy else None,
            
            # 增强采样
            "metadynamics": metadynamics_config if use_metadynamics else None,
            
            # 约束
            "restraints": {
                "position_restraints": position_restraints,
                "distance_restraints": distance_restraints,
            } if position_restraints or distance_restraints else None,
            
            # 溶剂化
            "solvation": {
                "add_solvent": add_solvent,
                "model": solvent_model,
                "padding_nm": solvent_padding_nm,
                "ion_concentration_M": ion_concentration_M,
                "positive_ion": positive_ion,
                "negative_ion": negative_ion,
            } if add_solvent else None,
            
            # 周期性
            "periodic_box_vectors": periodic_box_vectors,
            
            # 计算设置
            "precision": precision,
            "remove_cm_motion": remove_cm_motion,
            "hydrogen_mass_amu": hydrogen_mass_amu,
            "use_dispersion_correction": use_dispersion_correction,
        }
        
        try:
            task_id = await task_manager.create_task(config)
            return f"高级MD模拟任务创建成功。任务ID: {task_id}\n配置摘要:\n- 积分器: {integrator_type}\n- 温度: {temperature_K}K\n- 步数: {steps}\n- 压力控制: {'是' if use_barostat else '否'}\n- 溶剂化: {'是' if add_solvent else '否'}"
        except Exception as e:
            raise Exception(f"创建高级MD模拟失败: {str(e)}")

    @mcp.tool()
    async def setup_protein_simulation(
        pdb_file: str,
        simulation_type: str = "equilibration",  # equilibration, production, heating, cooling
        duration_ns: float = 1.0,
        temperature_K: float = 300.0,
        pressure_bar: float = 1.0,
        force_field: str = "amber19",  # amber14, amber19, charmm36
        water_model: str = "tip3pfb",  # tip3p, tip3pfb, tip4pew, spce
        ion_concentration_M: float = 0.15,
        gpu_acceleration: bool = True,
    ) -> str:
        """
        设置标准蛋白质模拟的预配置模板。
        
        这是一个高级工具，为常见的蛋白质模拟场景提供预配置的参数。
        """
        
        # 根据模拟类型设置参数
        if simulation_type == "equilibration":
            steps = int(duration_ns * 500000)  # 2fs步长
            step_size = 0.002
            temperature_coupling = True
            pressure_coupling = True
        elif simulation_type == "production":
            steps = int(duration_ns * 500000)
            step_size = 0.002
            temperature_coupling = True
            pressure_coupling = True
        elif simulation_type == "heating":
            steps = int(duration_ns * 500000)
            step_size = 0.001  # 更小的步长
            temperature_coupling = True
            pressure_coupling = False
        elif simulation_type == "cooling":
            steps = int(duration_ns * 500000)
            step_size = 0.001
            temperature_coupling = True
            pressure_coupling = False
        else:
            raise ValueError(f"不支持的模拟类型: {simulation_type}")
        
        # 选择力场文件
        if force_field == "amber14":
            ff_files = ["amber14-all.xml", f"amber14/{water_model}.xml"]
        elif force_field == "amber19":
            ff_files = ["amber19-all.xml", f"amber19/{water_model}.xml"]
        elif force_field == "charmm36":
            ff_files = ["charmm36_2024.xml", "charmm36/water.xml"]
        else:
            raise ValueError(f"不支持的力场: {force_field}")
        
        # 调用高级MD工具
        return await create_advanced_md_simulation(
            pdb_file=pdb_file,
            forcefield_files=ff_files,
            integrator_type="LangevinMiddle",
            temperature_K=temperature_K,
            step_size_ps=step_size,
            steps=steps,
            use_barostat=pressure_coupling,
            pressure_bar=pressure_bar,
            add_solvent=True,
            solvent_model=water_model,
            ion_concentration_M=ion_concentration_M,
            platform_name="CUDA" if gpu_acceleration else "CPU",
            minimize_energy=True,
            trajectory_interval=5000,
            state_data_interval=1000,
            checkpoint_interval=50000,
        )

    @mcp.tool()
    async def setup_membrane_simulation(
        membrane_pdb: str,
        protein_pdb: Optional[str] = None,
        lipid_type: str = "POPC",  # POPC, POPE, DPPC, etc.
        membrane_thickness_nm: float = 4.0,
        water_thickness_nm: float = 2.0,
        temperature_K: float = 310.0,  # 生理温度
        pressure_bar: float = 1.0,
        surface_tension_bar_nm: float = 0.0,
        duration_ns: float = 10.0,
    ) -> str:
        """
        设置膜蛋白或脂质双分子层模拟。
        """
        
        steps = int(duration_ns * 500000)  # 2fs步长
        
        return await create_advanced_md_simulation(
            pdb_file=membrane_pdb,
            forcefield_files=["amber19-all.xml", "amber19/tip3pfb.xml"],
            integrator_type="LangevinMiddle",
            temperature_K=temperature_K,
            step_size_ps=0.002,
            steps=steps,
            use_barostat=True,
            barostat_type="MonteCarloMembraneBarostat",
            pressure_bar=pressure_bar,
            surface_tension_bar_nm=surface_tension_bar_nm,
            membrane_axis="Z",
            platform_name="CUDA",
            minimize_energy=True,
            trajectory_interval=10000,
            state_data_interval=2000,
            checkpoint_interval=100000,
            report_volume=True,
            report_density=True,
        )

    return [
        create_advanced_md_simulation,
        setup_protein_simulation, 
        setup_membrane_simulation
    ]