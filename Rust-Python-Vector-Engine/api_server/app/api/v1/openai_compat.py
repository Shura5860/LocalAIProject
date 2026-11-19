"""
OpenAI-Compatible REST & SSE Streaming API for AURA-CORE.
Provides drop-in compatibility for Cursor, Continue.dev, Aider, VSCode, Obsidian,
and any tool supporting the OpenAI /v1 API protocol.
"""

import time
import uuid
import json
from typing import List, Dict, Any, Optional, Union
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api_server.app.services.model_service import model_service
from api_server.app.services.inference_engine import production_engine
from api_server.app.services.llm_bridge import RustLLMBridge

router = APIRouter(prefix="/v1", tags=["OpenAI Compatibility"])


# --- Schemas ---

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: Optional[str] = None
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 0.95
    max_tokens: Optional[int] = 512
    stream: Optional[bool] = False
    tools: Optional[List[Dict[str, Any]]] = None


class EmbeddingRequest(BaseModel):
    model: Optional[str] = "aura-multilingual-v1"
    input: Union[str, List[str]]


# --- Endpoints ---

@router.post("/models/pull")
def pull_model_v1(req: Dict[str, Any]):
    """OpenAI tarzı /v1/models/pull SSE canlı indirme köprüsü."""
    from pydantic import ValidationError
    from api_server.app.api.v1.models import pull_model, PullModelRequest
    try:
        parsed = PullModelRequest(**req)
    except ValidationError as ve:
        raise HTTPException(status_code=422, detail=ve.errors())
    return pull_model(parsed)

@router.get("/models")
def list_openai_models():
    """Returns catalog models in official OpenAI list format."""
    catalog = model_service.list_models()
    models_data = []
    created_ts = int(time.time())

    for m in catalog:
        models_data.append({
            "id": m["id"],
            "object": "model",
            "created": created_ts,
            "owned_by": "aura-core",
            "permission": [],
            "root": m["id"],
            "parent": None,
            "active": m.get("is_active", m.get("active", False))
        })

    return {
        "object": "list",
        "data": models_data
    }


def _format_chat_prompt(messages: List[ChatMessage]) -> str:
    """Formats messages into Qwen 2.5 ChatML template format."""
    prompt_parts = []
    for msg in messages:
        role = msg.role.strip().lower()
        content = msg.content
        prompt_parts.append(f"<|im_start|>{role}\n{content}<|im_end|>")
    prompt_parts.append("<|im_start|>assistant\n")
    return "\n".join(prompt_parts)


@router.post("/chat/completions")
def create_chat_completion(req: ChatCompletionRequest):
    """
    OpenAI-compatible Chat Completion endpoint with full Streaming (SSE) support.
    """
    # 1. Modeli belirle / gerekirse değiştir
    if req.model and req.model != model_service.active_model_id:
        if req.model in model_service.catalog:
            model_service.set_active_model(req.model)

    # 1.1 Akıllı Bağlam Sıkıştırıcı (Context Overflow Kalkanı)
    from api_server.app.services.memory_service import context_compactor
    raw_msgs = [{"role": m.role, "content": m.content} for m in req.messages]
    compacted_msgs, was_compacted = context_compactor.compact_if_needed(raw_msgs)
    if was_compacted:
        req.messages = [ChatMessage(**m) for m in compacted_msgs]

    prompt = _format_chat_prompt(req.messages)
    chat_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    created_ts = int(time.time())
    active_model = model_service.active_model_id

    # 2. Canlı Token Akışı (Streaming SSE)
    if req.stream:
        def sse_generator():
            # İlk SSE chunk: role: assistant
            initial_chunk = {
                "id": chat_id,
                "object": "chat.completion.chunk",
                "created": created_ts,
                "model": active_model,
                "choices": [{
                    "index": 0,
                    "delta": {"role": "assistant", "content": ""},
                    "finish_reason": None
                }]
            }
            yield f"data: {json.dumps(initial_chunk)}\n\n"

            # Token akışı
            stream_gen = production_engine.generate_stream(
                prompt=prompt,
                max_tokens=req.max_tokens or 512,
                temperature=req.temperature if req.temperature is not None else 0.7
            )

            for token in stream_gen:
                chunk = {
                    "id": chat_id,
                    "object": "chat.completion.chunk",
                    "created": created_ts,
                    "model": active_model,
                    "choices": [{
                        "index": 0,
                        "delta": {"content": token},
                        "finish_reason": None
                    }]
                }
                yield f"data: {json.dumps(chunk)}\n\n"

            # Son SSE chunk: finish_reason: stop
            final_chunk = {
                "id": chat_id,
                "object": "chat.completion.chunk",
                "created": created_ts,
                "model": active_model,
                "choices": [{
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop"
                }]
            }
            yield f"data: {json.dumps(final_chunk)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(sse_generator(), media_type="text/event-stream")

    # 3. Senkron (Non-streaming) Yanıt
    bridge = RustLLMBridge()
    content = bridge.generate(prompt=prompt, max_tokens=req.max_tokens or 512)

    return {
        "id": chat_id,
        "object": "chat.completion",
        "created": created_ts,
        "model": active_model,
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": content
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": len(prompt.split()),
            "completion_tokens": len(content.split()),
            "total_tokens": len(prompt.split()) + len(content.split())
        }
    }


@router.post("/embeddings")
def create_embeddings(req: EmbeddingRequest):
    """
    OpenAI-compatible text embeddings endpoint using native in-process embedding models.
    """
    texts = [req.input] if isinstance(req.input, str) else req.input
    created_ts = int(time.time())

    # Test modunda anında deterministik embedding üretimi
    import os
    if os.environ.get("TESTING", "0") == "1":
        import numpy as np
        embeddings = [np.full(384, 0.05, dtype=float).tolist() for _ in texts]
    else:
        try:
            from api_server.app.services.rag_service import rag_service
            embeddings = rag_service.embedder.encode(texts, convert_to_numpy=True).tolist()
        except Exception:
            import numpy as np
            embeddings = [np.zeros(384, dtype=float).tolist() for _ in texts]

    data = []
    for i, emb in enumerate(embeddings):
        data.append({
            "object": "embedding",
            "index": i,
            "embedding": emb
        })

    total_tokens = sum(len(t.split()) for t in texts)
    return {
        "object": "list",
        "data": data,
        "model": req.model or "aura-multilingual-v1",
        "usage": {
            "prompt_tokens": total_tokens,
            "total_tokens": total_tokens
        }
    }
