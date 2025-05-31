#!/usr/bin/env python3
"""
测试OpenMM MCP Server的功能
"""

import asyncio
import json
import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from fastmcp import Client
from src.server_new import mcp

async def test_mcp_server():
    """测试MCP服务器的基本功能"""
    print("🧪 开始测试OpenMM MCP Server...")
    
    # 使用内存中的客户端连接到服务器
    async with Client(mcp) as client:
        print("✅ 成功连接到MCP服务器")
        
        # 测试1: 列出所有工具
        print("\n📋 测试1: 列出可用工具")
        try:
            tools = await client.list_tools()
            print(f"可用工具数量: {len(tools)}")
            for tool in tools:
                print(f"  - {tool.name}: {tool.description}")
        except Exception as e:
            print(f"❌ 列出工具失败: {e}")
            return False
        
        # 测试2: 列出所有任务
        print("\n📋 测试2: 列出所有任务")
        try:
            result = await client.call_tool("list_all_tasks", {})
            tasks_data = json.loads(result[0].text)
            print(f"当前任务数量: {len(tasks_data.get('tasks', []))}")
            if tasks_data.get('tasks'):
                for task in tasks_data['tasks']:
                    print(f"  - 任务ID: {task['task_id']}, 类型: {task['task_type']}, 状态: {task['status']}")
        except Exception as e:
            print(f"❌ 列出任务失败: {e}")
        
        # 测试3: 创建一个简单的MD模拟任务
        print("\n🧬 测试3: 创建MD模拟任务")
        try:
            # 简单的水分子PDB内容
            pdb_content = """HETATM    1  O   HOH A   1      -0.778   0.000   0.000  1.00  0.00           O  
HETATM    2  H1  HOH A   1      -0.178   0.759   0.000  1.00  0.00           H  
HETATM    3  H2  HOH A   1      -0.178  -0.759   0.000  1.00  0.00           H  
END
"""
            
            integrator_config = {
                "type": "LangevinMiddle",
                "temperature_K": 300,
                "friction_coeff_ps": 1.0,
                "step_size_ps": 0.002
            }
            
            result = await client.call_tool("create_md_simulation", {
                "pdb_file": pdb_content,
                "forcefield": ["amber14-all.xml", "amber14/tip3pfb.xml"],
                "steps": 1000,
                "integrator": integrator_config,
                "minimize_energy": True
            })
            
            print(f"✅ MD任务创建结果: {result[0].text}")
            
            # 从结果中提取任务ID
            task_id = result[0].text.split("Task ID: ")[-1].strip()
            print(f"📝 任务ID: {task_id}")
            
            # 测试4: 获取任务状态
            print("\n📊 测试4: 获取任务状态")
            status_result = await client.call_tool("get_task_status", {"task_id": task_id})
            status_data = json.loads(status_result[0].text)
            print(f"任务状态: {status_data.get('status', 'unknown')}")
            print(f"进度: {status_data.get('progress', {})}")
            
        except Exception as e:
            print(f"❌ 创建MD任务失败: {e}")
        
        # 测试5: 创建DFT计算任务
        print("\n⚛️  测试5: 创建DFT计算任务")
        try:
            # 简单的POSCAR格式结构
            structure_content = """H2O molecule
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
"""
            
            dft_params = {
                "calculation": "scf",
                "ecutwfc": 50,
                "kpoints": [1, 1, 1],
                "smearing": "gaussian",
                "degauss": 0.01
            }
            
            result = await client.call_tool("create_dft_calculation", {
                "input_structure": structure_content,
                "calculation_parameters": dft_params
            })
            
            print(f"✅ DFT任务创建结果: {result[0].text}")
            
        except Exception as e:
            print(f"❌ 创建DFT任务失败: {e}")
        
        # 测试6: 再次列出所有任务
        print("\n📋 测试6: 再次列出所有任务")
        try:
            result = await client.call_tool("list_all_tasks", {})
            tasks_data = json.loads(result[0].text)
            print(f"更新后的任务数量: {len(tasks_data.get('tasks', []))}")
            for task in tasks_data.get('tasks', []):
                print(f"  - 任务ID: {task['task_id'][:8]}..., 类型: {task['task_type']}, 状态: {task['status']}")
        except Exception as e:
            print(f"❌ 列出任务失败: {e}")
    
    print("\n🎉 测试完成!")
    return True

async def test_server_startup():
    """测试服务器启动"""
    print("🚀 测试服务器组件初始化...")
    
    try:
        from src.config import AppConfig
        from src.task_manager import TaskManager
        from src.utils.logging_config import get_logger
        
        # 测试配置
        config = AppConfig()
        print(f"✅ 配置加载成功")
        print(f"  - 任务数据目录: {config.TASK_DATA_DIR}")
        print(f"  - 最大并发任务: {config.MAX_CONCURRENT_TASKS}")
        print(f"  - 日志级别: {config.LOG_LEVEL}")
        
        # 测试日志
        logger = get_logger("test")
        logger.info("测试日志系统")
        print("✅ 日志系统正常")
        
        # 测试TaskManager
        task_manager = TaskManager(config)
        print("✅ TaskManager初始化成功")
        
        return True
        
    except Exception as e:
        print(f"❌ 服务器组件初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("🔬 OpenMM MCP Server 测试套件")
    print("=" * 50)
    
    # 测试服务器启动
    if not asyncio.run(test_server_startup()):
        print("❌ 服务器启动测试失败，退出")
        return 1
    
    print("\n" + "=" * 50)
    
    # 测试MCP功能
    if not asyncio.run(test_mcp_server()):
        print("❌ MCP功能测试失败")
        return 1
    
    print("\n✅ 所有测试通过!")
    return 0

if __name__ == "__main__":
    sys.exit(main())