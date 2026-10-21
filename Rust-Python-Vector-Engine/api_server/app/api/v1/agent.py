from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from api_server.app.services.agent_service import agent_service
from api_server.app.tools.registry import tool_registry

router = APIRouter(prefix="/agent", tags=["Autonomous Agent (Tool Calling)"])

class AgentChatRequest(BaseModel):
    query: str
    max_tokens: int = 300

class AgentChatResponse(BaseModel):
    query: str
    answer: str
    tool_used: Optional[Dict[str, Any]] = None
    tool_result: Optional[Any] = None

@router.get("/tools")
def list_tools():
    """Kullanılabilir tüm araçların JSON şemalarını listeler."""
    return [t.to_schema() for t in tool_registry.get_all_tools()]

@router.post("/chat", response_model=AgentChatResponse)
def agent_chat(req: AgentChatRequest):
    """
    Otonom Ajan sohbet uç noktası. Model kullanıcının isteğine göre
    hesap makinesi, web araması, sistem bilgisi veya Python kod çalıştırma
    araçlarını otomatik olarak çağırabilir.
    """
    try:
        res = agent_service.run(user_query=req.query, max_tokens=req.max_tokens)
        return AgentChatResponse(**res)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ajan çalışma hatası: {str(e)}")

from fastapi.responses import StreamingResponse
import json

@router.post("/chat/stream")
def agent_chat_stream(req: AgentChatRequest):
    """
    Kullanıcıya daktilo efektiyle harf harf yanıt akıtan Streaming (SSE) uç noktası.
    """
    from api_server.app.services.inference_engine import production_engine

    def event_stream():
        prompt = (
            "<|im_start|>system\n"
            "Sen yardımsever, yetenekli ve Türkçe konuşan yerel bir yapay zeka asistanısın.<|im_end|>\n"
            f"<|im_start|>user\n{req.query}<|im_end|>\n"
            "<|im_start|>assistant\n"
        )
        try:
            for token in production_engine.generate_stream(prompt=prompt, max_tokens=req.max_tokens):
                payload = json.dumps({"token": token}, ensure_ascii=False)
                yield f"data: {payload}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            err_payload = json.dumps({"error": str(e)}, ensure_ascii=False)
            yield f"data: {err_payload}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


from api_server.app.schemas.agent import (
    ReActChatRequest,
    ReActChatResponse,
    ActionDecisionRequest,
    ActionDecisionResponse
)
from api_server.app.services.react_agent_service import react_agent_service

@router.post("/react", response_model=ReActChatResponse)
def react_agent_chat(req: ReActChatRequest):
    """
    Çok Adımlı Muhakeme & Planlama yapan ReAct (Reasoning + Acting) Ajan uç noktası.
    Kritik eylemlerde require_approval=True ise kullanıcı onayı bekler.
    """
    try:
        res = react_agent_service.run(
            user_query=req.query,
            max_steps=req.max_steps,
            require_approval=req.require_approval
        )
        return ReActChatResponse(**res)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ReAct Ajan hatası: {str(e)}")

@router.post("/action/decision", response_model=ActionDecisionResponse)
def handle_action_decision(req: ActionDecisionRequest):
    """
    Human-In-The-Loop: Bekleyen kritik eylem için kullanıcının onay veya red kararını uygular.
    """
    try:
        res = react_agent_service.execute_decision(
            action_id=req.action_id,
            approved=req.approved,
            rejection_reason=req.rejection_reason
        )
        return ActionDecisionResponse(**res)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Karar uygulama hatası: {str(e)}")


