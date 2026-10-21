from pydantic import BaseModel
from typing import List, Dict, Optional, Any

class PendingAction(BaseModel):
    action_id: str
    tool: str
    args: Dict[str, Any]
    description: str

class ReActChatRequest(BaseModel):
    query: str
    max_steps: int = 5
    require_approval: bool = True

class StepTrace(BaseModel):
    step_number: int
    thought: str
    action: Optional[str] = None
    action_input: Optional[Dict[str, Any]] = None
    observation: Optional[Any] = None

class ReActChatResponse(BaseModel):
    query: str
    final_answer: str
    total_steps: int
    trace: List[StepTrace]
    status: str = "COMPLETED"  # "COMPLETED" veya "WAITING_APPROVAL"
    pending_action: Optional[PendingAction] = None

class ActionDecisionRequest(BaseModel):
    action_id: str
    approved: bool
    rejection_reason: Optional[str] = None

class ActionDecisionResponse(BaseModel):
    action_id: str
    status: str  # "EXECUTED" veya "CANCELLED"
    result: Any
    message: str

