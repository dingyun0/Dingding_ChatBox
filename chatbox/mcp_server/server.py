import json
import asyncio
import os
from pathlib import Path
from typing import Dict,List,Any
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
        self.load_json_rescources()

    def load_json_rescources(self):
        """从data目录加载所有JSON文件"""
        try:
            if not self.data_dir.exists():
                logger.warning(f"数据目录不存在")
                return
            json_files=list(self.data_dir.glob("*.json"))
            for json_file in json_files:
                try:
                    with open(json_file,'r',encoding='utf-8') as f:
                        data=json.load(f)

                    resource_id=json_file.stem
                    resource_uri=f"file://{json_file.absolute()}"

                    resource={
                        'id':resource_id,
                        'uri':resource_uri,
                        'name':resource_id.replace('_', ' ').title(),
                        'content':data,
                        'description':f"从{json_file.name}加载的JSON数据",
                        'mime_type':'application/json'
                    }

                    self.resources[resource_uri]=resource
                    logger.info(f"成功加载资源: {resource_id} -> {resource_uri}")
                except json.JSONDecodeError as e:
                    logger.error(f"JSON解析错误 {json_file}: {e}")
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
async def read_resource(uri: str) -> str:
    """MCP标准接口 - 读取指定资源内容"""
    try:
        resource=await resource_manager.get_resource(uri)

        content=json.dumps(resource['content'],ensure_ascii=False)
        logger.info(f"成功读取资源: {uri}")
        return content
    except ValueError as e:
        logger.error(f"资源不存在: {e}")
        raise
    except Exception as e:
        logger.error(f"读取资源时出错: {e}")
        raise


async def main():
    """启动MCP服务器"""
    logger.info("启动JSON资源MCP服务器...")

    resource_manager.load_json_rescources()
    async with stdio_server() as streams:
        await app.run(
            streams[0],
            streams[1],
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
