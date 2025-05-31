# OpenMM MCP Server 使用指南

## 快速开始

### 1. 安装依赖

```bash
# 安装Python依赖
pip install -r requirements.txt

# 推荐：使用conda安装OpenMM（可选，用于实际模拟）
conda install -c conda-forge openmm
```

### 2. 运行服务器

```bash
# 方法1: 直接运行
python -m src.server_new

# 方法2: 使用FastMCP CLI
fastmcp run src/server_new.py:mcp

# 方法3: 开发模式（包含MCP Inspector）
fastmcp dev src/server_new.py:mcp
```

### 3. 测试功能

```bash
python test_mcp_server.py
```

## MCP工具使用

### 创建MD模拟任务

```python
# 使用MCP客户端
from fastmcp import Client

async with Client("src/server_new.py:mcp") as client:
    result = await client.call_tool("create_md_simulation", {
        "pdb_file": """HETATM    1  O   HOH A   1      -0.778   0.000   0.000  1.00  0.00           O  
HETATM    2  H1  HOH A   1      -0.178   0.759   0.000  1.00  0.00           H  
HETATM    3  H2  HOH A   1      -0.178  -0.759   0.000  1.00  0.00           H  
END""",
        "forcefield": ["amber14-all.xml", "amber14/tip3pfb.xml"],
        "steps": 10000,
        "integrator": {
            "type": "LangevinMiddle",
            "temperature_K": 300,
            "friction_coeff_ps": 1.0,
            "step_size_ps": 0.002
        },
        "minimize_energy": True,
        "platform_name": "CPU"
    })
    print(result[0].text)
```

### 创建DFT计算任务

```python
async with Client("src/server_new.py:mcp") as client:
    result = await client.call_tool("create_dft_calculation", {
        "input_structure": """H2O molecule
1.0
10.0 0.0 0.0
0.0 10.0 0.0
0.0 0.0 10.0
O H
1 2
Cartesian
0.0 0.0 0.0
0.757 0.586 0.0
-0.757 0.586 0.0""",
        "calculation_parameters": {
            "calculation": "scf",
            "ecutwfc": 50,
            "kpoints": [1, 1, 1],
            "smearing": "gaussian",
            "degauss": 0.01
        }
    })
    print(result[0].text)
```

### 控制任务

```python
# 启动任务
await client.call_tool("control_simulation", {
    "task_id": "your-task-id",
    "action": "start"
})

# 暂停任务
await client.call_tool("control_simulation", {
    "task_id": "your-task-id", 
    "action": "pause"
})

# 停止任务
await client.call_tool("control_simulation", {
    "task_id": "your-task-id",
    "action": "stop"
})
```

### 查询任务状态

```python
# 获取特定任务状态
status = await client.call_tool("get_task_status", {
    "task_id": "your-task-id"
})

# 列出所有任务
tasks = await client.call_tool("list_all_tasks", {})
```

### 分析结果

```python
# 能量分析
analysis = await client.call_tool("analyze_results", {
    "task_id": "your-task-id",
    "analysis_type": "energy"
})

# 轨迹信息
trajectory_info = await client.call_tool("analyze_results", {
    "task_id": "your-task-id", 
    "analysis_type": "trajectory_info"
})
```

## 配置选项

### 环境变量

```bash
# 任务数据目录
export TASK_DATA_DIR="./simulation_data"

# 最大并发任务数
export MAX_CONCURRENT_TASKS=4

# OpenMM平台
export DEFAULT_OPENMM_PLATFORM="CUDA"

# 日志级别
export LOG_LEVEL="DEBUG"

# 日志文件
export LOG_FILE="./mcp_server.log"
```

### 配置文件 (.env)

```env
TASK_DATA_DIR=./simulation_data
MAX_CONCURRENT_TASKS=4
DEFAULT_OPENMM_PLATFORM=CUDA
LOG_LEVEL=INFO
LOG_FILE=./mcp_server.log
```

## 集成到Claude Desktop

### 1. 安装服务器

```bash
# 安装到Claude Desktop
fastmcp install src/server_new.py:mcp -n "OpenMM Simulation Server"
```

### 2. 配置文件

在Claude Desktop的配置中添加：

```json
{
  "mcpServers": {
    "openmm-server": {
      "command": "python",
      "args": ["-m", "src.server_new"],
      "cwd": "/path/to/openmm-mcp-server",
      "env": {
        "TASK_DATA_DIR": "./simulation_data",
        "MAX_CONCURRENT_TASKS": "2"
      }
    }
  }
}
```

## 故障排除

### 常见问题

1. **OpenMM未安装**
   - 症状：看到 "OpenMM not found" 警告
   - 解决：`conda install -c conda-forge openmm`

2. **任务创建失败**
   - 检查PDB文件格式
   - 验证力场文件名
   - 确认参数完整性

3. **服务器启动失败**
   - 检查端口是否被占用
   - 验证Python环境
   - 查看日志文件

### 调试模式

```bash
# 启用详细日志
export LOG_LEVEL=DEBUG

# 使用开发模式
fastmcp dev src/server_new.py:mcp
```

## 性能优化

### 1. 硬件配置
- 使用GPU加速（CUDA/OpenCL）
- 充足的内存
- 快速存储（SSD）

### 2. 软件配置
- 调整并发任务数
- 优化检查点间隔
- 配置适当的输出频率

### 3. 任务管理
- 合理设置模拟步数
- 使用适当的时间步长
- 定期清理完成的任务

## 扩展开发

### 添加新工具

```python
@mcp.tool()
async def your_new_tool(param1: str, param2: int) -> str:
    """Your tool description."""
    # 实现逻辑
    return "Result"
```

### 添加新资源

```python
@mcp.resource("your://resource/{id}")
async def your_resource(id: str) -> dict:
    """Your resource description."""
    # 实现逻辑
    return {"data": "value"}
```

## 支持和贡献

- 报告问题：创建GitHub Issue
- 功能请求：提交Feature Request
- 代码贡献：提交Pull Request
- 文档改进：更新相关文档

## 许可证

请查看项目根目录的LICENSE文件了解许可证信息。