import argparse
import asyncio
import subprocess
import sys
import os
from pathlib import Path

def start_api_server():
    """启动API服务器"""
    print("启动王锭云个人助手API服务器...")
    backend_dir = Path(__file__).parent / "backend"
    subprocess.Popen(
        [sys.executable, str(backend_dir / "app.py")],
        cwd=str(backend_dir),
    )
    print("API服务器已启动，访问 http://localhost:8000/docs 查看API文档")

def start_mcp_server():
    """启动MCP服务器"""
    print("启动MCP服务器...")
    mcp_server_dir = Path(__file__).parent / "mcp_server"
    subprocess.Popen(
        [sys.executable, str(mcp_server_dir / "server.py")],
        cwd=str(mcp_server_dir),
    )
    print("MCP服务器已启动")

def start_chat_cli():
    """启动命令行聊天界面"""
    from backend.chatbox import chatbot
    
    print("\n=== 王锭云个人助手 ===")
    print("输入问题来了解关于王锭云的信息，输入'退出'结束对话")
    
    while True:
        user_input = input("\n您: ").strip()
        if user_input.lower() in ["退出", "quit", "exit"]:
            print("谢谢使用，再见！")
            break
        
        if not user_input:
            continue
            
        try:
            response = chatbot.chat(user_input)
            print(f"\n助手: {response}")
        except Exception as e:
            print(f"\n出错了: {str(e)}")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="王锭云个人助手")
    parser.add_argument("--api", action="store_true", help="启动API服务器")
    parser.add_argument("--mcp", action="store_true", help="启动MCP服务器")
    parser.add_argument("--chat", action="store_true", help="启动命令行聊天界面")
    
    args = parser.parse_args()
    
    if args.api:
        start_api_server()
    elif args.mcp:
        start_mcp_server()
    elif args.chat:
        start_chat_cli()
    else:
        # 默认启动命令行聊天界面
        start_chat_cli()

if __name__ == "__main__":
    main()
