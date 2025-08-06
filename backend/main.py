import json

from typing import Annotated, Sequence
from pydantic import BaseModel, Field

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_core.tools import tool, InjectedToolCallId
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, END, MessagesState, StateGraph
from langgraph.graph.ui import AnyUIMessage, ui_message_reducer, push_ui_message
from langgraph.types import  Command
from langgraph.prebuilt import ToolNode

from requirements import graph as requirements_graph
from intro import graph as intro_graph

from config import Settings


class RequestParams(BaseModel):
    input: dict


class AgentState(MessagesState):
    ui: Annotated[Sequence[AnyUIMessage], ui_message_reducer]
    lab: dict

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

def router(state: AgentState):
    return state.get("step", "intro_graph")

workflow = StateGraph(AgentState)
workflow.add_node("intro_graph", intro_graph)
workflow.add_node("requirements_graph", requirements_graph)
# workflow.add_node("briefing_graph", briefing_graph)
# workflow.add_node("questions_graph", questions_graph)

workflow.add_conditional_edges(START, router, ["intro_graph"])

memory = MemorySaver()
graph = workflow.compile(checkpointer=memory)


async def stream_response(thread_id: str, request: RequestParams):
    if request.input.get("message"):
        messages = [HumanMessage(request.input["message"])]
    else:
        messages = []
    input = {"messages": messages, "lab": request.input["context"]["lab"]}
    config = {"configurable": {"thread_id": thread_id}}

    async for namespace, stream_mode, chunk in graph.astream(input, config, subgraphs=True, stream_mode=["messages", "custom"]):
        if stream_mode == "messages":
            (message, metadata) = chunk

            data = {
              "id": message.id,
              "type": "AIMessageChunk",
              "content": message.content,
            }

        elif stream_mode == "custom":
            if chunk.get("type") == "ui":
                data = {
                    "id": chunk["id"],
                    "type": "UIMessageChunk",
                    "name": chunk["name"],
                    "props": chunk["props"],
                    "metadata": chunk["metadata"]
                }

        yield f"{json.dumps(data)}\n"

@app.post("/thread/{thread_id}/stream")
async def stream_thread(thread_id: str, request: RequestParams):
    return StreamingResponse(stream_response(thread_id, request), media_type="text/event-stream")
