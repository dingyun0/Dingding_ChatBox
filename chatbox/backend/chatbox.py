import json
import os
from typing import Dict, List, Any, TypedDict, Annotated, Literal
from pathlib import Path

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain.memory import ConversationBufferMemory

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

from dotenv import load_dotenv

load_dotenv()

# 定义状态类型
class AgentState(TypedDict):
    messages: List[Any]
    context: Dict[str, Any]
    next: Literal["retrieve", "generate", "end"]

# 加载王锭云的个人资料
def load_profile_data() -> Dict[str, Any]:
    """加载王锭云的个人资料数据"""
    data_path = Path(__file__).parent.parent / "mcp_server" / "data" / "person_profile" / "sample_profiles.json"
    
    try:
        with open(data_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as e:
        print(f"加载个人资料数据失败: {e}")
        return {}

# 创建检索函数
def retrieve(state: AgentState) -> AgentState:
    """根据用户问题检索相关信息"""
    profile_data = load_profile_data()
    
    # 获取最后一条用户消息
    last_message = state["messages"][-1]
    if not isinstance(last_message, HumanMessage):
        return {**state, "next": "generate"}
    
    query = last_message.content
    
    # 简单的关键词匹配逻辑
    keywords = {
        "教育": profile_data.get("教育背景", {}),
        "学校": profile_data.get("教育背景", {}).get("学校", ""),
        "专业": profile_data.get("教育背景", {}).get("专业", ""),
        "工作": profile_data.get("工作经历", []),
        "实习": profile_data.get("工作经历", []),
        "项目": profile_data.get("项目经历", []),
        "技能": profile_data.get("专业技能", []),
        "个人": profile_data.get("个人总结", []),
        "联系": profile_data.get("邮箱", ""),
        "邮箱": profile_data.get("邮箱", ""),
        "年龄": profile_data.get("年龄", ""),
        "性别": profile_data.get("性别", ""),
    }
    
    # 特定项目名称匹配
    project_names = [project.get("项目名称", "") for project in profile_data.get("项目经历", [])]
    for name in project_names:
        if name:
            keywords[name] = next((p for p in profile_data.get("项目经历", []) if p.get("项目名称") == name), {})
    
    # 特定公司名称匹配
    company_names = [work.get("公司", "") for work in profile_data.get("工作经历", [])]
    for name in company_names:
        if name:
            keywords[name] = next((w for w in profile_data.get("工作经历", []) if w.get("公司") == name), {})
    
    # 检索相关信息
    relevant_info = {}
    for key, value in keywords.items():
        if key.lower() in query.lower():
            relevant_info[key] = value
    
    # 如果没有找到特定信息，返回整个简历
    if not relevant_info:
        relevant_info = profile_data
    
    # 更新上下文
    state["context"] = {"profile_info": relevant_info}
    
    return {**state, "next": "generate"}

# 创建回答生成函数
def generate(state: AgentState) -> AgentState:
    """生成回答"""
    # 创建提示模板
    system_prompt = """你是王锭云的个人助手，你的任务是回答关于王锭云的问题。
    
    请根据提供的个人资料信息回答问题。如果问题与王锭云无关，请礼貌地引导用户询问关于王锭云的信息。
    
    回答时要遵循以下规则:
    1. 回答要简洁、准确、专业
    2. 只使用提供的资料信息回答问题，不要编造信息,不要使用markdown语法
    3. 如果资料中没有相关信息，请直接说明"抱歉，我没有这方面的信息"
    4. 保持活泼的语气，适当增加emoji，引导用户阅读兴趣
    5. 回答要有条理
    
    个人资料信息:
    {profile_info}
    """
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="messages"),
    ])
    
    # 创建LLM
    model = ChatOpenAI(
        model="gpt-4o",
        temperature=0.7,
    )
    
    # 创建链
    chain = (
        prompt
        | model
        | StrOutputParser()
    )
    
    # 运行链
    response = chain.invoke({
        "messages": state["messages"],
        "profile_info": json.dumps(state["context"]["profile_info"], ensure_ascii=False, indent=2)
    })
    
    # 添加AI回复到消息历史
    state["messages"].append(AIMessage(content=response))
    
    return {**state, "next": "end"}

# 创建对话图
def create_agent() -> StateGraph:
    """创建对话代理"""
    # 创建工作流
    workflow = StateGraph(AgentState)
    
    # 添加节点
    workflow.add_node("retrieve", retrieve)
    workflow.add_node("generate", generate)
    
    # 设置入口
    workflow.set_entry_point("retrieve")
    
    # 添加边
    workflow.add_edge("retrieve", "generate")
    workflow.add_edge("generate", END)
    
    # 编译工作流
    return workflow.compile()

# 创建对话接口
class ChatBot:
    def __init__(self):
        self.agent = create_agent()
        self.state = {
            "messages": [
                SystemMessage(content="你是王锭云的个人助手，请根据提供的资料回答关于王锭云的问题。")
            ],
            "context": {},
            "next": "retrieve"
        }
    
    def chat(self, message: str) -> str:
        """处理用户消息并返回回复"""
        # 添加用户消息
        self.state["messages"].append(HumanMessage(content=message))
        
        # 运行代理
        self.state = self.agent.invoke(self.state)
        
        # 返回最后一条AI消息
        for msg in reversed(self.state["messages"]):
            if isinstance(msg, AIMessage):
                return msg.content
        
        return "抱歉，处理您的问题时出现了错误。"

# 创建聊天机器人实例
chatbot = ChatBot()

