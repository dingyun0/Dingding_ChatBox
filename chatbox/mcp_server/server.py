import json
import asyncio
import os
from pathlib import Path
from typing import Dict, List, Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataManager:
    def __init__(self):
        self.data_dir = Path("D:\projects\Dingding_ChatBox\chatbox\mcp_server\data\person_profile")
        self.data = {}
        self.load_json_data()

    def load_json_data(self):
        """从data/person_profile目录加载所有JSON文件"""
        try:
            if not self.data_dir.exists():
                logger.warning(f"数据目录 '{self.data_dir.absolute()}' 不存在，请创建并放置JSON文件。")
                # 创建示例目录和文件
                self.create_sample_data()
                return
            
            json_files = list(self.data_dir.glob("*.json"))
            if not json_files:
                logger.warning(f"在数据目录 '{self.data_dir.absolute()}' 中未找到任何JSON文件。")
                # 创建示例文件
                self.create_sample_data()
                return

            for json_file in json_files:
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    file_id = json_file.stem
                    self.data[file_id] = data
                    logger.info(f"成功加载数据文件: {json_file.name}")
                    # 打印文件内容概要
                    logger.info(f"文件 {json_file.name} 包含的顶级键: {list(data.keys()) if isinstance(data, dict) else 'non-dict data'}")
                    
                except json.JSONDecodeError as e:
                    logger.error(f"JSON解析错误文件 {json_file}: {e}")
                except Exception as e:
                    logger.error(f"加载文件错误 {json_file}: {e}")
                    
        except Exception as e:
            logger.error(f"扫描目录错误: {e}")

    def create_sample_data(self):
        """创建示例数据文件"""
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            
            # 创建示例数据
            sample_data = {
                "张三": {
                    "姓名": "张三",
                    "昵称": ["老三", "小三"],
                    "年龄": 25,
                    "职业": "程序员",
                    "爱好": ["编程", "游戏", "阅读"],
                    "联系方式": {
                        "电话": "123-456-7890",
                        "邮箱": "zhangsan@example.com"
                    }
                },
                "李四": {
                    "姓名": "李四",
                    "昵称": ["老四", "小四"],
                    "年龄": 30,
                    "职业": "设计师",
                    "爱好": ["绘画", "摄影"],
                    "联系方式": {
                        "电话": "098-765-4321",
                        "邮箱": "lisi@example.com"
                    }
                },
                "王五": {
                    "姓名": "王五",
                    "昵称": ["老五", "小五"],
                    "年龄": 28,
                    "职业": "教师",
                    "爱好": ["读书", "旅游", "音乐"],
                    "联系方式": {
                        "电话": "555-123-4567",
                        "邮箱": "wangwu@example.com"
                    }
                }
            }
            
            sample_file = self.data_dir / "sample_profiles.json"
            with open(sample_file, 'w', encoding='utf-8') as f:
                json.dump(sample_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"已创建示例数据文件: {sample_file}")
            
            # 重新加载数据
            self.data["sample_profiles"] = sample_data
            
        except Exception as e:
            logger.error(f"创建示例数据时出错: {e}")

    async def search_content(self, query: str) -> Dict[str, Any]:
        """在所有加载的数据中搜索相关信息"""
        results = {}
        query_lower = query.lower()
        
        logger.info(f"开始搜索查询: '{query}'")
        logger.info(f"当前加载的数据文件: {list(self.data.keys())}")
        
        for file_id, content in self.data.items():
            logger.info(f"正在搜索文件: {file_id}")
            matching_sections = {}

            def search_in_data(data, path=""):
                matches = {}
                try:
                    if isinstance(data, dict):
                        for key, value in data.items():
                            current_path = f"{path}.{key}" if path else key
                            
                            # 检查键名是否匹配
                            if query_lower in str(key).lower():
                                matches[current_path] = value
                                logger.info(f"匹配键名: {current_path}")
                            
                            # 检查值是否匹配
                            if isinstance(value, (str, int, float)):
                                if query_lower in str(value).lower():
                                    matches[current_path] = value
                                    logger.info(f"匹配值: {current_path} = {value}")
                            elif isinstance(value, list):
                                # 搜索列表中的每个元素
                                for i, item in enumerate(value):
                                    if query_lower in str(item).lower():
                                        matches[f"{current_path}[{i}]"] = item
                                        logger.info(f"匹配列表项: {current_path}[{i}] = {item}")
                            
                            # 递归搜索嵌套结构
                            nested_matches = search_in_data(value, current_path)
                            matches.update(nested_matches)
                    
                    elif isinstance(data, list):
                        for i, item in enumerate(data):
                            current_path = f"{path}[{i}]" if path else f"[{i}]"
                            if query_lower in str(item).lower():
                                matches[current_path] = item
                                logger.info(f"匹配列表项: {current_path} = {item}")
                            nested_matches = search_in_data(item, current_path)
                            matches.update(nested_matches)
                    
                    else:
                        # 对于其他类型的数据，直接转换为字符串搜索
                        if query_lower in str(data).lower():
                            matches[path or "root"] = data
                            logger.info(f"匹配数据: {path or 'root'} = {data}")
                
                except Exception as e:
                    logger.error(f"搜索数据时出错 (path: {path}): {e}")
                
                return matches
            
            matching_sections = search_in_data(content)
            if matching_sections:
                results[file_id] = {
                    "file_name": f"{file_id}.json",
                    "matching_content": matching_sections
                }
                logger.info(f"文件 {file_id} 中找到 {len(matching_sections)} 个匹配项")
            else:
                logger.info(f"文件 {file_id} 中未找到匹配项")
        
        logger.info(f"搜索查询 '{query}' 得到 {len(results)} 个结果。")
        return results

    async def get_all_data(self) -> Dict[str, Any]:
        """获取所有加载的数据"""
        logger.info(f"返回所有数据，共 {len(self.data)} 个文件")
        return self.data

    async def get_file_data(self, file_id: str) -> Dict[str, Any]:
        """获取指定文件的数据"""
        if file_id in self.data:
            logger.info(f"找到文件数据: {file_id}")
            return {file_id: self.data[file_id]}
        else:
            logger.warning(f"未找到文件: {file_id}")
            return {}

    def get_data_summary(self) -> str:
        """获取数据摘要，用于调试"""
        summary = []
        for file_id, content in self.data.items():
            summary.append(f"文件: {file_id}.json")
            if isinstance(content, dict):
                summary.append(f"  - 顶级键: {list(content.keys())}")
                for key, value in content.items():
                    if isinstance(value, dict):
                        summary.append(f"    - {key}: {list(value.keys())}")
                    elif isinstance(value, list):
                        summary.append(f"    - {key}: 列表 (长度: {len(value)})")
                    else:
                        summary.append(f"    - {key}: {type(value).__name__}")
            else:
                summary.append(f"  - 类型: {type(content).__name__}")
        return "\n".join(summary)

# 全局变量，延迟初始化
data_manager = None

# 创建MCP服务器
app = Server('person-profile-server')

def get_data_manager():
    """获取数据管理器实例，延迟初始化"""
    global data_manager
    if data_manager is None:
        logger.info("初始化数据管理器...")
        data_manager = DataManager()
    return data_manager

@app.list_tools()
async def list_tools() -> List[types.Tool]:
    """MCP标准接口 - 列出所有可用工具"""
    return [
        types.Tool(
            name="search_person_profiles",
            description="在person_profile数据中搜索内容。可以搜索键名和值，支持嵌套结构的深度搜索。",
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
        ),
        types.Tool(
            name="get_all_profiles",
            description="获取所有person_profile数据。",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        types.Tool(
            name="get_profile_by_file",
            description="根据文件名获取特定的person_profile数据。",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "JSON文件的名称（不包含.json扩展名）"
                    }
                },
                "required": ["file_id"]
            }
        ),
        types.Tool(
            name="get_data_summary",
            description="获取数据结构摘要，用于调试和了解数据格式。",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> List[types.TextContent]:
    """MCP标准接口 - 调用工具"""
    
    # 获取数据管理器实例
    dm = get_data_manager()
    
    if name == "search_person_profiles":
        query = arguments.get("query")
        if not query:
            return [types.TextContent(
                type="text",
                text=json.dumps({"error": "缺少必需的参数 'query'"}, ensure_ascii=False, indent=2)
            )]
        
        logger.info(f"搜索请求: {query}")
        try:
            results = await dm.search_content(query)
            logger.info(f"搜索结果: {results}")
            return [types.TextContent(
                type="text",
                text=json.dumps(results, ensure_ascii=False, indent=2)
            )]
        except Exception as e:
            logger.error(f"搜索时出错: {e}")
            return [types.TextContent(
                type="text",
                text=json.dumps({"error": f"搜索时发生错误: {str(e)}"}, ensure_ascii=False, indent=2)
            )]
    
    elif name == "get_all_profiles":
        logger.info("获取所有profile数据请求")
        try:
            all_data = await dm.get_all_data()
            return [types.TextContent(
                type="text",
                text=json.dumps(all_data, ensure_ascii=False, indent=2)
            )]
        except Exception as e:
            logger.error(f"获取所有数据时出错: {e}")
            return [types.TextContent(
                type="text",
                text=json.dumps({"error": f"获取数据时发生错误: {str(e)}"}, ensure_ascii=False, indent=2)
            )]
    
    elif name == "get_profile_by_file":
        file_id = arguments.get("file_id")
        if not file_id:
            return [types.TextContent(
                type="text",
                text=json.dumps({"error": "缺少必需的参数 'file_id'"}, ensure_ascii=False, indent=2)
            )]
        
        logger.info(f"获取文件数据请求: {file_id}")
        try:
            file_data = await dm.get_file_data(file_id)
            if not file_data:
                return [types.TextContent(
                    type="text",
                    text=json.dumps({"error": f"未找到文件: {file_id}.json"}, ensure_ascii=False, indent=2)
                )]
            
            return [types.TextContent(
                type="text",
                text=json.dumps(file_data, ensure_ascii=False, indent=2)
            )]
        except Exception as e:
            logger.error(f"获取文件数据时出错: {e}")
            return [types.TextContent(
                type="text",
                text=json.dumps({"error": f"获取文件数据时发生错误: {str(e)}"}, ensure_ascii=False, indent=2)
            )]
    
    elif name == "get_data_summary":
        logger.info("获取数据摘要请求")
        try:
            summary = dm.get_data_summary()
            return [types.TextContent(
                type="text",
                text=summary
            )]
        except Exception as e:
            logger.error(f"获取数据摘要时出错: {e}")
            return [types.TextContent(
                type="text",
                text=f"获取数据摘要时发生错误: {str(e)}"
            )]
    
    else:
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": f"未知的工具: {name}"}, ensure_ascii=False, indent=2)
        )]

async def main():
    """启动MCP服务器"""
    logger.info("启动Person Profile MCP服务器...")

    # 初始化数据管理器
    dm = get_data_manager()

    # 记录加载的数据文件
    loaded_files = list(dm.data.keys())
    logger.info(f"服务器启动完成，共加载 {len(loaded_files)} 个数据文件。")
    
    if loaded_files:
        logger.info("=== 加载的数据文件列表 ===")
        for i, file_id in enumerate(loaded_files, 1):
            logger.info(f"  {i}. {file_id}.json")
        
        # 打印数据摘要
        logger.info("=== 数据结构摘要 ===")
        logger.info(dm.get_data_summary())
    
    # 记录暴露的工具
    logger.info("=== 暴露的工具列表 ===")
    tools = await list_tools()
    for i, tool in enumerate(tools, 1):
        logger.info(f"工具 {i}:")
        logger.info(f"  - 名称: {tool.name}")
        logger.info(f"  - 描述: {tool.description}")
    
    logger.info("=== 服务器准备就绪，等待客户端连接 ===")

    async with stdio_server() as streams:
        await app.run(
            streams[0],  # stdin
            streams[1],  # stdout
            app.create_initialization_options()
        )

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("服务器已停止")
    except Exception as e:
        logger.error(f"服务器启动失败: {e}")
        raise