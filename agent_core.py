# agent_core.py
from fastapi import FastAPI
from pydantic import BaseModel
from openai import OpenAI
import uvicorn

app = FastAPI(title="GSF-Claw Core API")

# --- 新增：读取 SOUL 文件的函数 ---
def load_soul():
    soul_path = os.path.join(os.path.dirname(__file__), 'SOUL.md')
    try:
        with open(soul_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print("⚠️ 未找到 SOUL.md，使用默认人格。")
        return "你是一个有用的桌面 AI 助手。"

# 在应用启动时加载 SOUL
SYSTEM_SOUL = load_soul()

memory_db = {}

class ChatRequest(BaseModel):
    user_id: str      # 区分是桌面端(Gadget)还是手机端(Telegram)
    text: str         # 用户说的话
    api_key: str      # 暂时由客户端传过来
    base_url: str = None
    model: str = "gpt-4o-mini"

class ChatResponse(BaseModel):
    reply: str

@app.post("/chat", response_model=ChatResponse)
def chat_with_agent(req: ChatRequest)
    if req.user_id not in memory_db:
        memory_db[req.user_id] = [
            {"role": "system", "content": "你是一个全能的AI Agent。你要记住上下文。"}
        ]
    
    messages = memory_db[req.user_id]
    messages.append({"role": "user", "content": req.text})

    try:
        client = OpenAI(api_key=req.api_key, base_url=req.base_url)
        response = client.chat.completions.create(
            model=req.model,
            messages=messages
        )
        reply_text = response.choices[0].message.content
        
        messages.append({"role": "assistant", "content": reply_text})
        
        return ChatResponse(reply=reply_text)

    except Exception as e:
        return ChatResponse(reply=f"Agent 核心报错: {str(e)}")

if __name__ == "__main__":
    print("启动 Agent Core 成功！监听端口 8000...")
    uvicorn.run(app, host="127.0.0.1", port=8000)