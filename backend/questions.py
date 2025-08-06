import json, typing

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


class QuestionOption(BaseModel):
    """Model for a multiple-choice option."""
    value: str = Field(..., description="The text of the option.")


class Question(BaseModel):
    """Model for a question."""
    title: str = Field(..., description="The title of the question.")
    options: list[QuestionOption] = Field(..., description="List of multiple-choice options for the question.")
    correct_option_index: int = Field(..., description="Index of the correct option, starting from 0.")


class AgentState(MessagesState):
    ui: Annotated[Sequence[AnyUIMessage], ui_message_reducer]
    lab: dict


model = init_chat_model("gpt-4.1", model_provider="openai", api_key=Settings().openai_api_key)

# @tool
# def transfer_to_question_agent(
#     tools_call_id: Annotated[str, InjectedToolCallId]
# ) -> Command:
#     """Transfer the conversation to the next agent."""

#     return Command(
#         update={
#             "messages": [ToolMessage(content="Transferring to question agent", tool_call_id=tools_call_id)]
#         },
#         goto="create"
#     )

async def agent(state: AgentState):
    prompt = """Tell a joke"""

    messages = [SystemMessage(content=prompt)] + state["messages"]
    # model_with_tools = model.bind_tools([transfer_to_question_agent])
    response = await model.ainvoke(messages)
    return {"messages": [response]}

# async def create(state: AgentState):
#     prompt = """Create a trivia question on the topic {topic}"""
#     content = prompt.format(topic=state["lab"]["topic"])

#     messages = [SystemMessage(content=content)]
#     model_with_tools = model.bind_tools([Question], tool_choice="Question")
#     content_stream = model_with_tools.astream(messages)

#     message = None
#     ui_message = None
#     tool_call = None
#     async for chunk in content_stream:
#         message = message + chunk if message else chunk

#         tool_call = message.tool_calls[0]

#         ui_message = push_ui_message(
#             tool_call["name"],
#             tool_call["args"],
#             id=ui_message["id"] if ui_message else None,
#             message=message
#         )

#     push_ui_message(
#         tool_call["name"],
#         tool_call["args"],
#         id=ui_message["id"],
#         message=message,
#         metadata={
#             "complete": True
#         }
#     )

#     return {
#         "messages": [message, ToolMessage(content="Question created", tool_call_id=message.tool_calls[0]["id"])]
#     }

# async def feedback(state: AgentState):
#     pass


# def should_continue(state):
#     messages = state["messages"]
#     last_message = messages[-1]
#     if last_message.tool_calls:
#         return "tools"
#     return END


workflow = StateGraph(AgentState)

workflow.add_node(agent)
# workflow.add_node(create)
# workflow.add_node(feedback)

# workflow.add_node("tools", ToolNode([transfer_to_question_agent]))

workflow.add_edge(START, "agent")
workflow.add_edge("agent", END)
# workflow.add_conditional_edges("intro", should_continue, ["tools", END])

graph = workflow.compile()
