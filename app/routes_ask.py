"""Endpoint hỏi đáp /ask."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agent import AgentError, ask_agent
from app.db import get_session

router = APIRouter()


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)


class AskResponse(BaseModel):
    answer: str
    tool_calls: list[dict] = Field(description="Which tools the agent used and with what arguments")


@router.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest, session: Session = Depends(get_session)):
    try:
        result = ask_agent(session, payload.question)
    except AgentError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    return AskResponse(answer=result.answer, tool_calls=result.tool_calls)