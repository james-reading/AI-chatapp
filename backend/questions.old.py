import json, asyncio

from uuid import uuid4
from typing import Annotated, Sequence, TypedDict
from pydantic import BaseModel, Field

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, AIMessage, AIMessageChunk, BaseMessage
from langchain_core.tools import tool, InjectedToolCallId
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, END, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, InjectedState
from langgraph.types import Command
from langgraph.config import get_stream_writer
from langgraph.graph.ui import AnyUIMessage, ui_message_reducer, push_ui_message
from langchain.load.dump import dumps
from langgraph.types import interrupt, Command

from config import Settings


class AgentState(MessagesState):
    ui: Annotated[Sequence[AnyUIMessage], ui_message_reducer]


class QuestionOption(BaseModel):
    """Model for a multiple-choice option."""
    value: str = Field(..., description="The text of the option.")


class Question(BaseModel):
    """Model for a question."""
    title: str = Field(..., description="The title of the question.")
    options: list[QuestionOption] = Field(..., description="List of multiple-choice options for the question.")
    correct_option_index: int = Field(..., description="Index of the correct option, starting from 0.")


model = init_chat_model("gpt-4.1", model_provider="openai", api_key=Settings().openai_api_key)


def human_approval(state: AgentState):
    is_approved = interrupt(
        {
            "question": "Is this good?",
            # Surface the output that should be
            # reviewed and approved by the human.
        }
    )

    print(f"Human approval received: {is_approved}")
    return Command(goto="chat")

async def chat(state: AgentState):
    prompt = """You are a helpful AI assistant whose job is to help write trivia questions.

You must do so by using the relevant tools provided to you.

If the user asks for multiple questions, you must call the tool once at time. Call the tool again immediately after receiving the response from the tool call."""
    messages = [SystemMessage(content=prompt)] + state["messages"]
    model_with_tools = model.bind_tools([Question])
    content_stream = model_with_tools.astream(messages)

    message = None
    ui_message = None
    async for chunk in content_stream:
        message = message + chunk if message else chunk

        for tool_call in message.tool_calls:
            ui_message = push_ui_message(
                tool_call["name"],
                tool_call["args"],
                id=ui_message["id"] if ui_message else None,
                message=message
            )

    return {"messages": [message]}

def should_continue(state):
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        return "tools"
    return END

workflow = StateGraph(AgentState)
workflow.add_node(chat)
workflow.add_node(human_approval)
workflow.add_node("tools", ToolNode([Question]))

workflow.add_edge(START, "chat")
workflow.add_conditional_edges("chat", should_continue, ["tools", END])
workflow.add_edge("tools", "human_approval")

memory = MemorySaver()
graph = workflow.compile(checkpointer=memory)
