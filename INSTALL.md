# OpenMM MCP Server 安装指南

## 🚀 快速安装

### 1. 克隆项目
```bash
git clone <repository_url>
cd openmm-mcp-server
```

### 2. 安装依赖
```bash
# 安装Python依赖
pip install -r requirements.txt

# 可选：安装OpenMM（用于实际模拟）
conda install -c conda-forge openmm
```

### 3. 测试安装
```bash
python test_mcp_server.py
```

如果看到 "✅ 所有测试通过!" 说明安装成功。

## 🔧 Roo Code 配置

### 方法1: 简单配置（推荐）

在Roo Code的MCP设置中添加：

```json
{
  "mcpServers": {
    "openmm-server": {
      "command": "python",
      "args": ["run_openmm_server.py"],
      "cwd": "/path/to/openmm-mcp-server",
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

**重要**: 将 `/path/to/openmm-mcp-server` 替换为实际的项目路径！

### 方法2: 使用FastMCP CLI

```json
{
  "mcpServers": {
    "openmm-server": {
      "command": "fastmcp",
      "args": ["run", "src/server_new.py:mcp"],
      "cwd": "/path/to/openmm-mcp-server",
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

## 📝 使用示例

配置完成后，您可以在Roo Code中这样与LLM交互：

### 创建MD模拟
```
我想运行一个水分子的分子动力学模拟，温度300K，运行10000步。

PDB内容：
HETATM    1  O   HOH A   1      -0.778   0.000   0.000  1.00  0.00           O  
HETATM    2  H1  HOH A   1      -0.178   0.759   0.000  1.00  0.00           H  
HETATM    3  H2  HOH A   1      -0.178  -0.759   0.000  1.00  0.00           H  
END
```

### 检查任务状态
```
列出所有模拟任务的状态
```

### 启动模拟
```
启动刚才创建的模拟任务
```

### 分析结果
```
分析模拟的能量结果
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

运行以下命令验证配置：
```bash
# 测试服务器启动
python run_openmm_server.py

# 测试MCP功能
python test_mcp_server.py
```

## 📁 项目结构

```
openmm-mcp-server/
├── run_openmm_server.py      # 启动脚本
├── test_mcp_server.py        # 测试脚本
├── requirements.txt          # 依赖列表
├── src/
│   ├── server_new.py         # 主服务器
│   ├── task_manager.py       # 任务管理
│   ├── openmm_engine.py      # OpenMM引擎
│   └── ...
├── task_data/                # 任务数据目录（自动创建）
└── docs/                     # 文档
```

## 🎯 下一步

1. 配置完成后重启Roo Code
2. 尝试上述使用示例
3. 查看 `ROO_CODE_INTEGRATION.md` 了解更多交互方式
4. 查看 `USAGE_GUIDE.md` 了解高级功能

## 📞 支持

如果遇到问题：
1. 检查日志文件（如果配置了LOG_FILE）
2. 运行测试脚本诊断问题
3. 查看项目文档
4. 提交Issue报告问题

祝您使用愉快！🎉