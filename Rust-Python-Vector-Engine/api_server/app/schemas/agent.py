from pydantic import BaseModel
from typing import List, Dict, Optional, Any

class PendingAction(BaseModel):
    action_id: str
    tool: str
    args: Dict[str, Any]
    description: str
    diff_preview: Optional[Dict[str, Any]] = None

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
    snapshot_id: Optional[str] = None
    diff_preview: Optional[Dict[str, Any]] = None

class UndoChangeRequest(BaseModel):
    snapshot_id: str

class UndoChangeResponse(BaseModel):
    status: str
    snapshot_id: str
    restored_files: List[str]
    message: str

class SwarmRequest(BaseModel):
    task: str
    max_correction_loops: int = 2
    auto_rollback_on_failure: bool = True

class SwarmResponse(BaseModel):
    task: str
    status: str
    total_events: int
    events: List[Dict[str, Any]]
    final_answer: str


