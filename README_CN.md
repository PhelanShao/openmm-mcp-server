# OpenMM MCP 服务器

### 🧬 OpenMM & Abacus 分子动力学模拟服务器

一个全面的模型上下文协议(MCP)服务器，用于使用OpenMM进行分子动力学模拟和使用Abacus进行DFT计算。该服务器通过LLM集成为复杂的分子模拟提供自然语言界面。

## ✨ 功能特性

- **完整的OpenMM集成**：支持所有OpenMM功能，包括高级积分器、恒压器和约束
- **DFT计算**：集成Abacus DFT引擎进行量子力学计算
- **预配置模板**：为蛋白质模拟、膜系统等提供即用型设置
- **高级采样**：Metadynamics、自由能计算和增强采样方法
- **GPU加速**：支持CUDA和OpenCL平台进行高性能计算
- **任务管理**：异步任务执行，具有持久化和监控功能
- **自然语言界面**：使用简单的中文命令与复杂模拟交互

## 🚀 快速开始

### 安装

```bash
# 克隆仓库
git clone <repository_url>
cd openmm-mcp-server

# 安装依赖
pip install -r requirements.txt

# 可选：安装OpenMM用于实际模拟
conda install -c conda-forge openmm

# 测试安装
python test_mcp_server.py
```

### Code 集成

在您的Code/Cline/Claude MCP MCP设置中添加：

```json
{
  "mcpServers": {
    "openmm-server": {
      "command": "python",
      "args": ["run_openmm_server.py"],
      "cwd": "Path_to\\openmm-mcp-server",
      "alwaysAllow": [
        "create_md_simulation",
        "create_advanced_md_simulation",
        "setup_protein_simulation",
        "setup_membrane_simulation",
        "create_dft_calculation",
        "control_simulation",
        "get_task_status",
        "list_all_tasks",
        "analyze_results"
      ]
    }
  }
}
```

**重要**：将路径替换为您的实际项目路径！

## 🛠️ 可用工具

### 基础工具
- `create_md_simulation` - 创建简单的MD模拟
- `create_dft_calculation` - 创建DFT计算
- `control_simulation` - 控制模拟执行（启动/停止/暂停）
- `get_task_status` - 检查任务状态
- `list_all_tasks` - 列出所有任务
- `analyze_results` - 分析模拟结果

### 高级工具
- `create_advanced_md_simulation` - 完整OpenMM功能支持（50+参数）
- `setup_protein_simulation` - 预配置蛋白质模拟模板
- `setup_membrane_simulation` - 膜蛋白模拟设置

## 💬 使用示例

### 简单水分子模拟
```
"运行一个水分子的分子动力学模拟，温度300K，10000步"
```

### 高级蛋白质模拟
```
"设置一个蛋白质的生产模拟，100纳秒，310K生理温度，使用Amber19力场和TIP3P-FB水模型，0.15M盐浓度，GPU加速"
```

### 膜蛋白模拟
```
"创建一个POPC膜中的蛋白质模拟，50纳秒，包含表面张力控制"
```

### 检查任务状态
```
"列出所有模拟任务的状态"
```

### 启动模拟
```
"启动刚才创建的模拟任务"
```

### 分析结果
```
"分析模拟的能量结果"
```

## 📊 OpenMM参数完整参考

### 积分器类型
- `LangevinMiddle` - Langevin中点积分器（推荐）
- `Verlet` - Verlet积分器（NVE系综）
- `Brownian` - 布朗动力学
- `VariableLangevin` - 可变步长Langevin
- `VariableVerlet` - 可变步长Verlet
- `NoseHoover` - Nose-Hoover恒温器

### 力场选择
- **Amber14**: `["amber14-all.xml", "amber14/tip3pfb.xml"]`
- **Amber19**: `["amber19-all.xml", "amber19/tip3pfb.xml"]`
- **CHARMM36**: `["charmm36_2024.xml", "charmm36/water.xml"]`

### 水模型
- `tip3p` - TIP3P水模型
- `tip3pfb` - TIP3P-FB水模型（推荐）
- `tip4pew` - TIP4P-Ew水模型
- `tip5p` - TIP5P水模型
- `spce` - SPC/E水模型

### 计算平台
- `CUDA` - NVIDIA GPU（最快）
- `OpenCL` - 通用GPU
- `CPU` - CPU计算
- `Reference` - 参考实现（最精确但最慢）

### 非键相互作用方法
- `PME` - 粒子网格Ewald（推荐用于周期性系统）
- `NoCutoff` - 无截断（小系统）
- `CutoffNonPeriodic` - 非周期性截断
- `CutoffPeriodic` - 周期性截断
- `Ewald` - 传统Ewald求和

### 约束类型
- `None` - 无约束
- `HBonds` - 氢键约束（推荐）
- `AllBonds` - 所有键约束
- `HAngles` - 氢角约束

### 恒压器类型
- `MonteCarloBarostat` - 各向同性压力控制
- `MonteCarloAnisotropicBarostat` - 各向异性压力控制
- `MonteCarloMembraneBarostat` - 膜系统压力控制

### 计算精度
- `mixed` - 混合精度（推荐）
- `single` - 单精度
- `double` - 双精度

## 🔧 环境配置

### 环境变量
```bash
export TASK_DATA_DIR="./simulation_data"
export MAX_CONCURRENT_TASKS=4
export DEFAULT_OPENMM_PLATFORM="CUDA"
export LOG_LEVEL="INFO"
export LOG_FILE="./mcp_server.log"
```

### .env配置文件
```env
TASK_DATA_DIR=./simulation_data
MAX_CONCURRENT_TASKS=4
DEFAULT_OPENMM_PLATFORM=CUDA
LOG_LEVEL=INFO
LOG_FILE=./mcp_server.log
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

### 蛋白质平衡模拟
```python
{
    "steps": 2500000,  # 5纳秒
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
    "steps": 25000000,  # 50纳秒
    "temperature_K": 310,
    "use_barostat": True,
    "barostat_type": "MonteCarloMembraneBarostat",
    "surface_tension_bar_nm": 0.0,
    "platform_name": "CUDA"
}
```

## 📁 项目结构

```
openmm-mcp-server/
├── run_openmm_server.py      # 启动脚本
├── test_mcp_server.py        # 测试脚本
├── requirements.txt          # 依赖列表
├── README.md                 # 英文文档
├── README_CN.md              # 中文文档
├── src/
│   ├── server_new.py         # 主服务器
│   ├── advanced_md_tools.py  # 高级MD工具
│   ├── task_manager.py       # 任务管理
│   ├── openmm_engine.py      # OpenMM引擎
│   ├── abacus_engine.py      # Abacus DFT引擎
│   ├── config.py             # 配置管理
│   ├── tools/                # MCP工具实现
│   ├── resources/            # MCP资源实现
│   └── utils/                # 工具函数
├── tests/                    # 测试文件
├── examples/                 # 示例代码
├── docs/                     # 文档
└── task_data/                # 任务数据目录（自动创建）
```

## 🔍 故障排除

### 常见问题

1. **"OpenMM not found" 警告**
   - 这是正常的，服务器会使用mock模式运行
   - 如需实际模拟，请安装OpenMM: `conda install -c conda-forge openmm`

2. **"command not found" 错误**
   - 检查Python是否在PATH中
   - 确认项目路径正确
   - 尝试使用绝对路径

3. **权限错误**
   - 确保有读写项目目录的权限
   - 检查task_data目录是否可写

### 验证配置

```bash
# 测试服务器启动
python run_openmm_server.py

# 测试MCP功能
python test_mcp_server.py
```

## 💡 使用技巧

### 1. 高效的提示词
- 明确指定温度、步数等参数
- 提供完整的结构文件内容
- 说明想要的分析类型

### 2. 性能优化
- 使用CUDA平台获得最佳性能
- 调整chunk大小以优化内存使用
- 合理设置输出频率

### 3. 系统准备
- 始终进行能量最小化
- 逐步加热系统
- 平衡后再进行生产模拟

## 📚 相关文档

- [安装指南](INSTALL.md) - 详细安装说明
- [使用指南](USAGE_GUIDE.md) - 全面使用示例
- [Roo Code集成](ROO_CODE_INTEGRATION.md) - 详细集成指南
- [项目分析](PROJECT_ANALYSIS.md) - 技术分析和改进

## 🆘 支持

如果遇到问题：
1. 运行测试脚本诊断问题: `python test_mcp_server.py`
2. 查看项目文档
3. 检查日志文件（如果配置了LOG_FILE）
4. 在GitHub上提交Issue

## 🤝 贡献

1. Fork 仓库
2. 创建功能分支
3. 进行更改
4. 添加测试
5. 提交拉取请求

## 📄 许可证

详情请参见LICENSE文件。

---

祝您使用愉快！🎉