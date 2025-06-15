from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
import uvicorn

from chatbox import chatbot

# 创建FastAPI应用
app = FastAPI(
    title="王锭云个人助手API",
    description="基于LangChain和LangGraph的对话机器人，专门回答关于王锭云的问题",
    version="1.0.0"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 定义请求模型
class ChatRequest(BaseModel):
    message: str = Field(..., description="用户发送的消息")

# 定义响应模型
class ChatResponse(BaseModel):
    response: str = Field(..., description="助手的回复")

# 定义健康检查端点
@app.get("/health")
async def health_check() -> Dict[str, str]:
    """健康检查端点"""
    return {"status": "healthy"}

# 定义聊天端点
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """处理聊天请求"""
    try:
        # 调用聊天机器人处理消息
        response = chatbot.chat(request.message)
        return ChatResponse(response=response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理消息时出错: {str(e)}")

# 主函数
def main():
    """启动FastAPI应用"""
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    main()

