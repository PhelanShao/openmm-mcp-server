# OpenMM 分子动力学参数完整参考

## 🧬 基于OpenMM最新文档的完整参数支持

本MCP服务器现在支持OpenMM的所有主要功能和参数。以下是详细的参数说明：

## 🔧 高级MD工具

### `create_advanced_md_simulation`

这是最全面的MD模拟工具，支持OpenMM的所有功能：

#### 结构输入
- `pdb_file`: PDB文件内容（字符串）
- `pdb_file_path`: PDB文件路径
- `periodic_box_vectors`: 周期性边界条件向量

#### 力场配置
- `forcefield_files`: 力场XML文件列表
  - Amber: `["amber14-all.xml", "amber14/tip3pfb.xml"]`
  - Amber19: `["amber19-all.xml", "amber19/tip3pfb.xml"]`
  - CHARMM36: `["charmm36_2024.xml", "charmm36/water.xml"]`
- `custom_forcefield_params`: 自定义力场参数

#### 系统参数
- `nonbonded_method`: 非键相互作用方法
  - `"PME"`: 粒子网格Ewald（推荐用于周期性系统）
  - `"NoCutoff"`: 无截断（小系统）
  - `"CutoffNonPeriodic"`: 非周期性截断
  - `"CutoffPeriodic"`: 周期性截断
  - `"Ewald"`: 传统Ewald求和

- `nonbonded_cutoff_nm`: 非键截断距离（纳米）
- `switch_distance_nm`: 切换距离
- `constraints`: 约束类型
  - `"None"`: 无约束
  - `"HBonds"`: 氢键约束（推荐）
  - `"AllBonds"`: 所有键约束
  - `"HAngles"`: 氢角约束

#### 积分器配置
- `integrator_type`: 积分器类型
  - `"LangevinMiddle"`: Langevin中点积分器（推荐）
  - `"Verlet"`: Verlet积分器（NVE系综）
  - `"Brownian"`: 布朗动力学
  - `"VariableLangevin"`: 可变步长Langevin
  - `"VariableVerlet"`: 可变步长Verlet
  - `"NoseHoover"`: Nose-Hoover恒温器

- `temperature_K`: 温度（开尔文）
- `friction_coeff_ps`: 摩擦系数（ps⁻¹）
- `step_size_ps`: 时间步长（皮秒）

#### 压力控制（恒压模拟）
- `use_barostat`: 是否使用恒压器
- `barostat_type`: 恒压器类型
  - `"MonteCarloBarostat"`: 各向同性恒压
  - `"MonteCarloAnisotropicBarostat"`: 各向异性恒压
  - `"MonteCarloMembraneBarostat"`: 膜系统恒压

- `pressure_bar`: 压力（巴）
- `anisotropic_pressure`: 各向异性压力 `[px, py, pz]`
- `surface_tension_bar_nm`: 表面张力（膜系统）

#### 溶剂化
- `add_solvent`: 是否添加溶剂
- `solvent_model`: 水模型
  - `"tip3p"`: TIP3P水模型
  - `"tip3pfb"`: TIP3P-FB水模型（推荐）
  - `"tip4pew"`: TIP4P-Ew水模型
  - `"tip5p"`: TIP5P水模型
  - `"spce"`: SPC/E水模型

- `solvent_padding_nm`: 溶剂填充距离
- `ion_concentration_M`: 离子浓度（摩尔）
- `positive_ion`: 正离子类型（如"Na+"）
- `negative_ion`: 负离子类型（如"Cl-"）

#### 输出配置
- `trajectory_file`: 轨迹文件名
- `trajectory_interval`: 轨迹保存间隔
- `state_data_file`: 状态数据文件
- `state_data_interval`: 状态数据保存间隔
- `checkpoint_file`: 检查点文件
- `checkpoint_interval`: 检查点保存间隔

#### 报告选项
- `report_step`: 报告步数
- `report_time`: 报告时间
- `report_potential_energy`: 报告势能
- `report_kinetic_energy`: 报告动能
- `report_total_energy`: 报告总能量
- `report_temperature`: 报告温度
- `report_volume`: 报告体积
- `report_density`: 报告密度
- `report_progress`: 报告进度
- `report_speed`: 报告速度

#### 平台设置
- `platform_name`: 计算平台
  - `"CUDA"`: NVIDIA GPU（最快）
  - `"OpenCL"`: 通用GPU
  - `"CPU"`: CPU计算
  - `"Reference"`: 参考实现（最慢但最精确）

- `precision`: 计算精度
  - `"mixed"`: 混合精度（推荐）
  - `"single"`: 单精度
  - `"double"`: 双精度

## 🧪 预配置模拟模板

### `setup_protein_simulation`

蛋白质模拟的预配置模板：

```python
# 平衡模拟
await client.call_tool("setup_protein_simulation", {
    "pdb_file": protein_pdb_content,
    "simulation_type": "equilibration",
    "duration_ns": 5.0,
    "temperature_K": 300.0,
    "force_field": "amber19",
    "water_model": "tip3pfb",
    "ion_concentration_M": 0.15
})

# 生产模拟
await client.call_tool("setup_protein_simulation", {
    "pdb_file": protein_pdb_content,
    "simulation_type": "production", 
    "duration_ns": 100.0,
    "temperature_K": 310.0,
    "gpu_acceleration": True
})
```

### `setup_membrane_simulation`

膜蛋白模拟的预配置模板：

```python
await client.call_tool("setup_membrane_simulation", {
    "membrane_pdb": membrane_system_pdb,
    "protein_pdb": protein_pdb,  # 可选
    "lipid_type": "POPC",
    "temperature_K": 310.0,
    "surface_tension_bar_nm": 0.0,
    "duration_ns": 50.0
})
```

## 📊 常用参数组合

### 快速测试
```python
{
    "steps": 10000,
    "temperature_K": 300,
    "step_size_ps": 0.002,
    "trajectory_interval": 1000,
    "minimize_energy": True
}
```

### 蛋白质平衡
```python
{
    "steps": 2500000,  # 5ns
    "temperature_K": 300,
    "step_size_ps": 0.002,
    "use_barostat": True,
    "pressure_bar": 1.0,
    "add_solvent": True,
    "ion_concentration_M": 0.15
}
```

### 膜蛋白模拟
```python
{
    "steps": 25000000,  # 50ns
    "temperature_K": 310,
    "use_barostat": True,
    "barostat_type": "MonteCarloMembraneBarostat",
    "surface_tension_bar_nm": 0.0,
    "platform_name": "CUDA"
}
```

### 自由能计算
```python
{
    "use_free_energy": True,
    "lambda_schedule": [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
    "steps": 5000000,  # 每个lambda窗口
}
```

## 🔬 高级功能

### 约束和限制
```python
{
    "position_restraints": [
        {
            "atoms": [1, 2, 3],  # 原子索引
            "force_constant": 1000,  # kJ/mol/nm²
            "reference_positions": [[0, 0, 0], [1, 0, 0], [0, 1, 0]]
        }
    ],
    "distance_restraints": [
        {
            "atom1": 10,
            "atom2": 20,
            "distance_nm": 0.5,
            "force_constant": 1000
        }
    ]
}
```

### 增强采样（Metadynamics）
```python
{
    "use_metadynamics": True,
    "metadynamics_config": {
        "collective_variables": [
            {
                "type": "distance",
                "atoms": [1, 10],
                "sigma": 0.1,
                "height": 2.0
            }
        ],
        "deposition_frequency": 500
    }
}
```

## 💡 使用建议

### 1. 系统准备
- 始终进行能量最小化
- 逐步加热系统
- 平衡后再进行生产模拟

### 2. 参数选择
- 使用混合精度以平衡速度和精度
- 对于生物系统，推荐使用PME和HBonds约束
- GPU加速可显著提高性能

### 3. 输出管理
- 合理设置输出频率以平衡存储和分析需求
- 定期保存检查点以防止数据丢失

### 4. 性能优化
- 使用CUDA平台获得最佳性能
- 调整chunk大小以优化内存使用
- 考虑使用多GPU并行计算

这个完整的参数支持使得MCP服务器能够处理从简单的教学示例到复杂的研究级模拟的各种需求。