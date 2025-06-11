import json
import asyncio
import os
from pathlib import Path
from typing import Dict,List,Any

from pydantic import AnyUrl
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types
from dataclasses import dataclass
import logging

logging.basicConfig(level=logging.INFO)
logger=logging.getLogger(__name__)

class ResourceManager:
    def __init__(self):
        self.resources={}
        self.data_dir=Path("./data")
        self.load_json_resources() # 修正了方法名拼写错误

    def load_json_resources(self): # 修正了方法名拼写错误
        """从data目录加载所有JSON文件"""
        try:
            if not self.data_dir.exists():
                logger.warning(f"数据目录 '{self.data_dir.absolute()}' 不存在，请创建并放置JSON文件。")
                return
            json_files=list(self.data_dir.glob("*.json"))
            if not json_files:
                logger.warning(f"在数据目录 '{self.data_dir.absolute()}' 中未找到任何JSON文件。")
                return

            for json_file in json_files:
                try:
                    with open(json_file,'r',encoding='utf-8') as f:
                        data=json.load(f)

                    resource_id=json_file.stem
                    # 使用相对路径，或者确保file://URI在客户端是可访问的，否则客户端可能无法直接读取
                    # 对于MCP工具，通常不需要 file:// URI，因为内容是通过read_resource提供的
                    resource_uri=f"mcp://json_data/{resource_id}" # 建议使用更规范的MCP URI

                    resource={
                        'id':resource_id,
                        'uri':resource_uri,
                        'name':resource_id.replace('_', ' ').title(),
                        'content':data,
                        'description':f"从 {json_file.name} 加载的JSON数据",
                        'mime_type':'application/json'
                    }

                    self.resources[resource_uri]=resource
                    logger.info(f"成功加载资源: {resource_id} -> {resource_uri}")
                except json.JSONDecodeError as e:
                    logger.error(f"JSON解析错误文件 {json_file}: {e}")
                except Exception as e:
                    logger.error(f"加载文件错误 {json_file}: {e}")
                    
        except Exception as e:
            logger.error(f"扫描目录错误: {e}")

    async def get_resource(self,uri:str)->Dict[str,Any]:
        """根据URI获取资源"""
        if uri in self.resources:
            logger.info(f"获取资源: {uri}")
            return self.resources[uri]
        else:
            raise ValueError(f"资源不存在: {uri}")
        
    async def list_all_resources(self) -> List[Dict[str, Any]]:
        """列出所有可用资源"""
        # print(list(self.resources.values())) # 在这里打印可能干扰MCP客户端的输出
        return list(self.resources.values())

    async def search_resource_content(self, query: str) -> Dict[str, Any]:
        """在资源内容中搜索相关信息"""
        results={}
        query_lower=query.lower()
        
        for uri,resource in self.resources.items():
            content=resource['content']
            matching_sections={}

            def search_in_data(data,path=""):
                matches={}
                if isinstance(data,dict):
                    for key,value in data.items():
                        current_path = f"{path}.{key}" if path else key
                        if query_lower in str(key).lower() or query_lower in str(value).lower():
                            matches[current_path] = value
                        # 递归搜索嵌套结构
                        nested_matches = search_in_data(value, current_path)
                        matches.update(nested_matches)
                elif isinstance(data, list):
                    for i, item in enumerate(data):
                        current_path = f"{path}[{i}]"
                        if query_lower in str(item).lower():
                            matches[current_path] = item
                        nested_matches = search_in_data(item, current_path)
                        matches.update(nested_matches)
                return matches
            
            matching_sections = search_in_data(content)
            if matching_sections:
                results[uri] = {
                    "resource_name": resource['name'],
                    "resource_id": resource['id'],
                    "matching_content": matching_sections
                }
        logger.info(f"搜索查询 '{query}' 得到 {len(results)} 个结果。")
        return results

# 创建资源管理器实例
resource_manager=ResourceManager()

# 创建MCP服务器
app=Server('json-resource-server')

@app.list_resources()
async def list_resources()->List[types.Resource]:
    """MCP标准接口 - 列出所有资源"""
    try:
        resource_data=await resource_manager.list_all_resources()

        mcp_resources=[]
        for resource in resource_data:
            mcp_resource=types.Resource(
                uri=resource['uri'],
                name=resource['name'],
                description=resource['description'],
                mimeType=resource['mime_type']
            )
            mcp_resources.append(mcp_resource)
        logger.info(f"返回 {len(mcp_resources)} 个{mcp_resources}资源")
        return mcp_resources
    except Exception as e:
        logger.error(f"列出资源时出错: {e}")
        return []

@app.read_resource()
async def read_resource(uri: AnyUrl) -> str:
    """MCP标准接口 - 读取指定资源内容"""
    try:
        resource=await resource_manager.get_resource(uri)

        content=json.dumps(resource['content'],ensure_ascii=False, indent=2) # 格式化输出
        logger.info(f"成功读取资源: {uri}{content}")
        return content
    except ValueError as e:
        logger.error(f"资源不存在: {e}")
        raise # 重新抛出，让MCP客户端知道资源不存在
    except Exception as e:
        logger.error(f"读取资源时出错: {e}")
        raise # 重新抛出，让MCP客户端知道发生了错误

@app.list_tools()
async def list_tools() -> List[types.Tool]:
    """MCP标准接口 - 列出所有可用工具"""
    return [
        types.Tool(
            name="search_resources",
            description="在已加载的JSON资源中搜索内容。可以搜索键名和值，支持嵌套结构的深度搜索。",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "要搜索的关键词或短语"
                    }
                },
                "required": ["query"]
            }
        )
    ]

# 新增的MCP工具函数
@app.call_tool()
async def search_resources_tool(query: str) -> str:
    """
    搜索加载的JSON资源中的内容。
    Args:
        query: 要搜索的关键词。
    Returns:
        包含匹配内容的JSON字符串。
    """
    logger.info(f"MCP工具接收到搜索请求: {query}")
    try:
        results = await resource_manager.search_resource_content(query)
        # 将搜索结果转换为JSON字符串返回
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"搜索资源时出错: {e}")
        # 返回错误信息以便客户端处理
        return json.dumps({"error": f"搜索资源时发生错误: {str(e)}"}, ensure_ascii=False, indent=2)


async def main():
    """启动MCP服务器"""
    logger.info("启动JSON资源MCP服务器...")

    loaded_resources = await resource_manager.list_all_resources() # 获取已加载的资源列表
    
    logger.info(f"服务器启动完成，共加载 {len(loaded_resources)} 个资源。")
    import json
import asyncio
import os
from pathlib import Path
from typing import Dict,List,Any

from pydantic import AnyUrl
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types
from dataclasses import dataclass
import logging

logging.basicConfig(level=logging.INFO)
logger=logging.getLogger(__name__)

class ResourceManager:
    def __init__(self):
        self.resources={}
        self.data_dir=Path("./data")
        self.load_json_resources() # 修正了方法名拼写错误

    def load_json_resources(self): # 修正了方法名拼写错误
        """从data目录加载所有JSON文件"""
        try:
            if not self.data_dir.exists():
                logger.warning(f"数据目录 '{self.data_dir.absolute()}' 不存在，请创建并放置JSON文件。")
                return
            json_files=list(self.data_dir.glob("*.json"))
            if not json_files:
                logger.warning(f"在数据目录 '{self.data_dir.absolute()}' 中未找到任何JSON文件。")
                return

            for json_file in json_files:
                try:
                    with open(json_file,'r',encoding='utf-8') as f:
                        data=json.load(f)

                    resource_id=json_file.stem
                    # 使用相对路径，或者确保file://URI在客户端是可访问的，否则客户端可能无法直接读取
                    # 对于MCP工具，通常不需要 file:// URI，因为内容是通过read_resource提供的
                    resource_uri=f"mcp://json_data/{resource_id}" # 建议使用更规范的MCP URI

                    resource={
                        'id':resource_id,
                        'uri':resource_uri,
                        'name':resource_id.replace('_', ' ').title(),
                        'content':data,
                        'description':f"从 {json_file.name} 加载的JSON数据",
                        'mime_type':'application/json'
                    }

                    self.resources[resource_uri]=resource
                    logger.info(f"成功加载资源: {resource_id} -> {resource_uri}")
                except json.JSONDecodeError as e:
                    logger.error(f"JSON解析错误文件 {json_file}: {e}")
                except Exception as e:
                    logger.error(f"加载文件错误 {json_file}: {e}")
                    
        except Exception as e:
            logger.error(f"扫描目录错误: {e}")

    async def get_resource(self,uri:str)->Dict[str,Any]:
        """根据URI获取资源"""
        if uri in self.resources:
            logger.info(f"获取资源: {uri}")
            return self.resources[uri]
        else:
            raise ValueError(f"资源不存在: {uri}")
        
    async def list_all_resources(self) -> List[Dict[str, Any]]:
        """列出所有可用资源"""
        # print(list(self.resources.values())) # 在这里打印可能干扰MCP客户端的输出
        return list(self.resources.values())

    async def search_resource_content(self, query: str) -> Dict[str, Any]:
        """在资源内容中搜索相关信息"""
        results={}
        query_lower=query.lower()
        
        for uri,resource in self.resources.items():
            content=resource['content']
            matching_sections={}

            def search_in_data(data,path=""):
                matches={}
                if isinstance(data,dict):
                    for key,value in data.items():
                        current_path = f"{path}.{key}" if path else key
                        if query_lower in str(key).lower() or query_lower in str(value).lower():
                            matches[current_path] = value
                        # 递归搜索嵌套结构
                        nested_matches = search_in_data(value, current_path)
                        matches.update(nested_matches)
                elif isinstance(data, list):
                    for i, item in enumerate(data):
                        current_path = f"{path}[{i}]"
                        if query_lower in str(item).lower():
                            matches[current_path] = item
                        nested_matches = search_in_data(item, current_path)
                        matches.update(nested_matches)
                return matches
            
            matching_sections = search_in_data(content)
            if matching_sections:
                results[uri] = {
                    "resource_name": resource['name'],
                    "resource_id": resource['id'],
                    "matching_content": matching_sections
                }
        logger.info(f"搜索查询 '{query}' 得到 {len(results)} 个结果。")
        return results

# 创建资源管理器实例
resource_manager=ResourceManager()

# 创建MCP服务器
app=Server('json-resource-server')

@app.list_resources()
async def list_resources()->List[types.Resource]:
    """MCP标准接口 - 列出所有资源"""
    try:
        resource_data=await resource_manager.list_all_resources()

        mcp_resources=[]
        for resource in resource_data:
            
            mcp_resource=types.Resource(
                uri=resource['uri'],
                name=resource['name'],
                description=resource['description'],
                mimeType=resource['mime_type']
            )
            mcp_resources.append(mcp_resource)
        logger.info(f"返回 {len(mcp_resources)} 个资源")
        return mcp_resources
    except Exception as e:
        logger.error(f"列出资源时出错: {e}")
        return []

@app.read_resource()
async def read_resource(uri: AnyUrl) -> str:
    """MCP标准接口 - 读取指定资源内容"""
    try:
        resource=await resource_manager.get_resource(uri)

        content=json.dumps(resource['content'],ensure_ascii=False, indent=2) # 格式化输出
        logger.info(f"成功读取资源: {uri}")
        return content
    except ValueError as e:
        logger.error(f"资源不存在: {e}")
        raise # 重新抛出，让MCP客户端知道资源不存在
    except Exception as e:
        logger.error(f"读取资源时出错: {e}")
        raise # 重新抛出，让MCP客户端知道发生了错误

@app.list_tools()
async def list_tools() -> List[types.Tool]:
    """MCP标准接口 - 列出所有可用工具"""
    return [
        types.Tool(
            name="search_resources",
            description="在已加载的JSON资源中搜索内容。可以搜索键名和值，支持嵌套结构的深度搜索。",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "要搜索的关键词或短语"
                    }
                },
                "required": ["query"]
            }
        )
    ]

# 新增的MCP工具函数
@app.call_tool()
async def call_tool(name: str, arguments: dict) -> List[types.TextContent]:
    """MCP标准接口 - 调用工具"""
    if name == "search_resources":
        query = arguments.get("query")
        if not query:
            return [types.TextContent(
                type="text",
                text=json.dumps({"error": "缺少必需的参数 'query'"}, ensure_ascii=False, indent=2)
            )]
        
        logger.info(f"MCP工具接收到搜索请求: {query}")
        try:
            results = await resource_manager.search_resource_content(query)
            return [types.TextContent(
                type="text",
                text=json.dumps(results, ensure_ascii=False, indent=2)
            )]
        except Exception as e:
            logger.error(f"搜索资源时出错: {e}")
            return [types.TextContent(
                type="text",
                text=json.dumps({"error": f"搜索资源时发生错误: {str(e)}"}, ensure_ascii=False, indent=2)
            )]
    else:
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": f"未知的工具: {name}"}, ensure_ascii=False, indent=2)
        )]


async def main():
    """启动MCP服务器"""
    logger.info("启动JSON资源MCP服务器...")

    loaded_resources = await resource_manager.list_all_resources() # 获取已加载的资源列表
    
    logger.info(f"服务器启动完成，共加载 {len(loaded_resources)} {loaded_resources}个资源。")
    
    # 详细记录暴露的资源
    logger.info("=== 暴露的资源列表 ===")
    for i, resource in enumerate(loaded_resources, 1):
        logger.info(f"资源 {i}:")
        logger.info(f"  - ID: {resource['id']}")
        logger.info(f"  - URI: {resource['uri']}")
        logger.info(f"  - 名称: {resource['name']}")
        logger.info(f"  - 描述: {resource['description']}")
        logger.info(f"  - MIME类型: {resource['mime_type']}")
    
    # 记录暴露的工具
    logger.info("=== 暴露的工具列表 ===")
    tools = await list_tools()
    for i, tool in enumerate(tools, 1):
        logger.info(f"工具 {i}:")
        logger.info(f"  - 名称: {tool.name}")
        logger.info(f"  - 描述: {tool.description}")
        logger.info(f"  - 输入参数: {json.dumps(tool.inputSchema, ensure_ascii=False, indent=4)}")
    
    logger.info("=== 服务器准备就绪，等待客户端连接 ===")


    async with stdio_server() as streams:
        await app.run(
            streams[0], # stdin
            streams[1], # stdout
            app.create_initialization_options()
        )

if __name__=='__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("服务器已停止")
    except Exception as e:
        logger.error(f"服务器启动失败: {e}")
        raise