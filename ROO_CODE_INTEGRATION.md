# OpenMM MCP Server - Roo Code 集成指南

## 📋 用户准备清单

### 1. 系统要求
- Python 3.9+ 
- 推荐：Anaconda/Miniconda（用于OpenMM安装）
- 足够的磁盘空间（模拟文件可能较大）

### 2. 必需的文件准备

#### 分子结构文件
用户需要准备以下格式之一的分子结构：

**PDB格式示例** (推荐):
```pdb
HETATM    1  O   HOH A   1      -0.778   0.000   0.000  1.00  0.00           O  
HETATM    2  H1  HOH A   1      -0.178   0.759   0.000  1.00  0.00           H  
HETATM    3  H2  HOH A   1      -0.178  -0.759   0.000  1.00  0.00           H  
END
```

**或者从PDB数据库下载**:
- 访问 https://www.rcsb.org/
- 搜索蛋白质ID（如1UBQ）
- 下载PDB文件

#### DFT计算结构文件
**POSCAR格式示例**:
```
H2O molecule
1.0
10.0 0.0 0.0
0.0 10.0 0.0
0.0 0.0 10.0
O H
1 2
Cartesian
0.0 0.0 0.0
0.757 0.586 0.0
-0.757 0.586 0.0
```

### 3. 常用力场选择
- **蛋白质**: `amber14-all.xml`, `amber19-all.xml`
- **水模型**: `amber14/tip3pfb.xml`, `amber19/tip3pfb.xml`
- **小分子**: 需要OpenFF工具生成参数

## 🔧 Roo Code MCP 配置

### 方法1: 本地安装配置

在Roo Code的MCP设置中添加以下配置：

```json
{
  "mcpServers": {
    "openmm-server": {
      "command": "python",
      "args": [
        "-m", 
        "src.server_new"
      ],
      "cwd": "/path/to/openmm-mcp-server",
      "env": {
        "TASK_DATA_DIR": "./simulation_data",
        "MAX_CONCURRENT_TASKS": "2",
        "LOG_LEVEL": "INFO"
      },
      "alwaysAllow": [
        "create_md_simulation",
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

### 方法2: 使用FastMCP CLI配置

```json
{
  "mcpServers": {
    "openmm-server": {
      "command": "fastmcp",
      "args": [
        "run",
        "/path/to/openmm-mcp-server/src/server_new.py:mcp"
      ],
      "env": {
        "TASK_DATA_DIR": "./simulation_data",
        "MAX_CONCURRENT_TASKS": "2"
      },
      "alwaysAllow": [
        "create_md_simulation",
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

### 方法3: 使用uvx运行（推荐）

首先创建一个可执行的包装脚本：

**创建 `run_openmm_server.py`**:
```python
#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from src.server_new import mcp

if __name__ == "__main__":
    mcp.run()
```

**Roo Code配置**:
```json
{
  "mcpServers": {
    "openmm-server": {
      "command": "uvx",
      "args": [
        "--from", 
        "/path/to/openmm-mcp-server",
        "python",
        "run_openmm_server.py"
      ],
      "alwaysAllow": [
        "create_md_simulation",
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

## 💬 与LLM交互示例

### 1. 创建简单的水分子MD模拟

**用户提示**:
```
我想运行一个水分子的分子动力学模拟，温度300K，运行10000步，使用Amber力场。

PDB内容：
HETATM    1  O   HOH A   1      -0.778   0.000   0.000  1.00  0.00           O  
HETATM    2  H1  HOH A   1      -0.178   0.759   0.000  1.00  0.00           H  
HETATM    3  H2  HOH A   1      -0.178  -0.759   0.000  1.00  0.00           H  
END
```

**LLM会调用**:
```
create_md_simulation({
  "pdb_file": "HETATM    1  O   HOH A   1      -0.778   0.000   0.000  1.00  0.00           O\nHETATM    2  H1  HOH A   1      -0.178   0.759   0.000  1.00  0.00           H\nHETATM    3  H2  HOH A   1      -0.178  -0.759   0.000  1.00  0.00           H\nEND",
  "forcefield": ["amber14-all.xml", "amber14/tip3pfb.xml"],
  "steps": 10000,
  "integrator": {
    "type": "LangevinMiddle",
    "temperature_K": 300,
    "friction_coeff_ps": 1.0,
    "step_size_ps": 0.002
  },
  "minimize_energy": true
})
```

### 2. 检查模拟状态

**用户提示**:
```
检查我刚才创建的模拟任务状态
```

**LLM会调用**:
```
list_all_tasks({})
```
然后根据返回的任务ID调用：
```
get_task_status({"task_id": "返回的任务ID"})
```

### 3. 启动模拟

**用户提示**:
```
启动任务ID为 abc123 的模拟
```

**LLM会调用**:
```
control_simulation({
  "task_id": "abc123",
  "action": "start"
})
```

### 4. 创建DFT计算

**用户提示**:
```
我想对水分子进行DFT计算，使用PBE泛函，截断能50 Ry

结构文件：
H2O molecule
1.0
10.0 0.0 0.0
0.0 10.0 0.0
0.0 0.0 10.0
O H
1 2
Cartesian
0.0 0.0 0.0
0.757 0.586 0.0
-0.757 0.586 0.0
```

**LLM会调用**:
```
create_dft_calculation({
  "input_structure": "H2O molecule\n1.0\n10.0 0.0 0.0\n0.0 10.0 0.0\n0.0 0.0 10.0\nO H\n1 2\nCartesian\n0.0 0.0 0.0\n0.757 0.586 0.0\n-0.757 0.586 0.0",
  "calculation_parameters": {
    "calculation": "scf",
    "ecutwfc": 50,
    "kpoints": [1, 1, 1],
    "smearing": "gaussian",
    "degauss": 0.01
  }
})
```

### 5. 分析结果

**用户提示**:
```
分析任务 abc123 的能量结果
```

**LLM会调用**:
```
analyze_results({
  "task_id": "abc123",
  "analysis_type": "energy"
})
```

## 📦 安装步骤

### 1. 下载项目
```bash
git clone <repository_url>
cd openmm-mcp-server
```

### 2. 安装依赖
```bash
# 安装Python依赖
pip install -r requirements.txt

# 安装OpenMM（推荐使用conda）
conda install -c conda-forge openmm

# 或使用pip
pip install openmm
```

### 3. 测试安装
```bash
python test_mcp_server.py
```

### 4. 配置Roo Code
- 打开Roo Code设置
- 找到MCP服务器配置
- 添加上述配置之一
- 重启Roo Code

## 🎯 使用技巧

### 1. 高效的提示词
- 明确指定温度、步数等参数
- 提供完整的结构文件内容
- 说明想要的分析类型

### 2. 常见参数组合

**快速测试**:
- 步数: 1000-5000
- 温度: 300K
- 时间步长: 0.002 ps

**生产运行**:
- 步数: 100000-1000000
- 温度: 根据实验条件
- 时间步长: 0.002-0.004 ps

**能量最小化**:
- 总是启用 `minimize_energy: true`
- 最大迭代次数: 1000

### 3. 故障排除
- 如果任务创建失败，检查PDB格式
- 如果模拟不启动，检查OpenMM安装
- 查看任务状态了解错误信息

## 🔍 监控和管理

### 查看所有任务
```
列出所有正在运行的模拟任务
```

### 停止任务
```
停止任务ID为 abc123 的模拟
```

### 查看结果
```
显示任务 abc123 的轨迹信息
```

这样配置后，用户就可以通过自然语言与LLM交互来运行分子动力学模拟和DFT计算了！