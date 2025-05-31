#!/usr/bin/env python3
"""
OpenMM MCP Server 启动脚本
用于在Roo Code中作为MCP服务器运行
"""

import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

try:
    from src.server_new import mcp
    
    if __name__ == "__main__":
        print("🚀 Starting OpenMM MCP Server...")
        mcp.run()
        
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("请确保已安装所有依赖: pip install -r requirements.txt")
    sys.exit(1)
except Exception as e:
    print(f"❌ Server startup error: {e}")
    sys.exit(1)