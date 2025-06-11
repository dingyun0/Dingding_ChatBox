import asyncio
import os
import sys
import json
from typing import Optional
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()  # load environment variables from .env

class MCPClient:
    def __init__(self):
        # 检查 OpenAI API Key
        api_key = os.getenv('OPENAI_API_KEY')
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        
        if not api_key:
            raise ValueError("OPENAI_API_KEY 未设置。请检查 .env 文件")
        
        self.client = OpenAI(api_key=api_key)
        print("✅ OpenAI 客户端初始化完成")

    async def connect_to_server(self, server_script_path: str):
        """Connect to an MCP server"""
        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")

        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env=None
        )

        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        await self.session.initialize()

        # List available tools
        response = await self.session.list_tools()
        tools = response.tools
        print("\nConnected to server with tools:", [tool.name for tool in tools])

    def test_api_connection(self):
        """测试 OpenAI API 连接"""
        print("\n=== 测试 OpenAI API 连接 ===")
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=10
            )
            print("✅ API 连接测试成功!")
            return True
        except Exception as e:
            print(f"❌ API 连接测试失败: {e}")
            return False

    def convert_mcp_tools_to_openai_format(self, mcp_tools):
        """将 MCP 工具格式转换为 OpenAI 函数调用格式"""
        openai_tools = []
        for tool in mcp_tools:
            # 确保 input_schema 有正确的结构
            parameters = tool.get("input_schema", {})
            
            # 如果 parameters 没有 type 字段，添加默认的 object 类型
            if "type" not in parameters:
                parameters = {
                    "type": "object",
                    "properties": parameters.get("properties", {}),
                    "required": parameters.get("required", [])
                }
            
            openai_tool = {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": parameters
                }
            }
            openai_tools.append(openai_tool)
            
        return openai_tools

    async def process_query(self, query: str) -> str:
        """Process a query using OpenAI and available tools"""
        try:
            messages = [{"role": "user", "content": query}]

            response = await self.session.list_tools()
            available_tools = [{
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema
            } for tool in response.tools]

            # 转换为 OpenAI 格式
            openai_tools = self.convert_mcp_tools_to_openai_format(available_tools)
            
            print(f"发送请求到 OpenAI API...")
            print(f"可用工具数量: {len(openai_tools)}")
            
            # 如果没有工具，不传递 tools 参数
            if not openai_tools:
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    max_tokens=1000
                )
            else:
                # 调用 OpenAI API (带工具) - 注意：这是同步调用，不需要 await
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    tools=openai_tools,
                    tool_choice="auto",
                    max_tokens=1000
                )

            # 处理响应
            final_text = []
            assistant_message = response.choices[0].message
            
            # 添加助手的文本回复
            if assistant_message.content:
                final_text.append(assistant_message.content)
            
            # 处理工具调用
            if assistant_message.tool_calls:
                # 添加助手消息到对话历史
                messages.append({
                    "role": "assistant",
                    "content": assistant_message.content,
                    "tool_calls": [
                        {
                            "id": tool_call.id,
                            "type": tool_call.type,
                            "function": {
                                "name": tool_call.function.name,
                                "arguments": tool_call.function.arguments
                            }
                        } for tool_call in assistant_message.tool_calls
                    ]
                })
                
                # 执行每个工具调用
                for tool_call in assistant_message.tool_calls:
                    tool_name = tool_call.function.name
                    try:
                        tool_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError as e:
                        print(f"JSON 解析错误: {e}")
                        print(f"原始参数: {tool_call.function.arguments}")
                        tool_args = {}
                    
                    print(f"调用工具: {tool_name}，参数: {tool_args}")
                    final_text.append(f"[调用工具 {tool_name}，参数: {tool_args}]")
                    
                    # 调用 MCP 工具 - 这是异步调用，需要 await
                    try:
                        result = await self.session.call_tool(tool_name, tool_args)
                        tool_result = result.content
                        print(f"工具返回结果: {tool_result}")
                        
                        # 添加工具结果到对话历史
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": str(tool_result)
                        })
                        
                    except Exception as e:
                        error_msg = f"工具调用失败: {str(e)}"
                        print(f"❌ {error_msg}")
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": error_msg
                        })
                
                # 获取最终回复 - 同步调用，不需要 await
                try:
                    final_response = self.client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=messages,
                        tools=openai_tools,
                        tool_choice="auto",
                        max_tokens=1000
                    )
                    
                    if final_response.choices[0].message.content:
                        final_text.append(final_response.choices[0].message.content)
                except Exception as e:
                    print(f"获取最终回复时出错: {e}")
                    final_text.append("获取最终回复时出错")

            return "\n".join(final_text)
            
        except Exception as e:
            print(f"处理查询时出错: {e}")
            print(f"错误类型: {type(e)}")
            import traceback
            traceback.print_exc()
            raise

    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Client Started!")
        
        # 首先测试 API 连接
        if not self.test_api_connection():
            print("API 连接失败，无法继续。请检查 API Key 和网络连接。")
            return
            
        print("Type your queries or 'quit' to exit.")

        while True:
            try:
                query = input("\nQuery: ").strip()

                if query.lower() == 'quit':
                    break
                    
                if not query:
                    print("请输入有效的查询。")
                    continue

                response = await self.process_query(query)
                print("\n" + response)

            except Exception as e:
                print(f"\nError: {str(e)}")

    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()

async def main():
    if len(sys.argv) < 2:
        print("Usage: python client.py <path_to_server_script>")
        sys.exit(1)

    try:
        client = MCPClient()
        await client.connect_to_server(sys.argv[1])
        await client.chat_loop()
    except Exception as e:
        print(f"初始化失败: {e}")
    finally:
        if 'client' in locals():
            await client.cleanup()

if __name__ == "__main__":
    asyncio.run(main())