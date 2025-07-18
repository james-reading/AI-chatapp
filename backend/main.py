import json, asyncio
from typing import Annotated, Sequence, TypedDict
from pydantic import BaseModel, Field

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, AIMessageChunk, BaseMessage
from langchain_core.tools import tool, InjectedToolCallId
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, END, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, InjectedState
from langgraph.types import Command
from langgraph.config import get_stream_writer
from langgraph.graph.message import add_messages
from langgraph.graph.ui import AnyUIMessage, ui_message_reducer, push_ui_message
from langchain.load.dump import dumps

from config.settings import Settings

class RequestParams(BaseModel):
    message: str
    thread_id: str

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

model = init_chat_model("gpt-4.1", model_provider="openai", api_key=Settings().openai_api_key)

class AgentState(TypedDict):  # noqa: D101
    messages: Annotated[Sequence[BaseMessage], add_messages]
    ui: Annotated[Sequence[AnyUIMessage], ui_message_reducer]

@tool
async def search_the_web(
    query: Annotated[str, "The search query"],
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[AgentState, InjectedState]
) -> int:
    """Search the web"""

    messages = state["messages"]
    calling_message = messages[-1]  # The last message should be the AI message with tool calls

    ui_message = push_ui_message("web_search", {"query": query}, message=calling_message)

    await asyncio.sleep(2)

    push_ui_message("web_search", {}, id=ui_message["id"], message=calling_message, merge=True, metadata={"complete": True})

    return Command(
        update={"messages": [ToolMessage("No results", tool_call_id=tool_call_id)]},
    )

@tool
async def tell_joke(
    topic: Annotated[str, "The topic of the joke"],
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[AgentState, InjectedState]
) -> int:
    """Tell a joke on a given topic"""
    # Get the message that called this tool
    messages = state["messages"]
    calling_message = messages[-1]  # The last message should be the AI message with tool calls

    ui_message = push_ui_message("joke", {"topic": topic}, message=calling_message)

    content_stream = model.with_config({"tags": ["nostream"]}).astream(
        f"Create a short joke on the topic: {topic}"
    )

    content = None
    async for chunk in content_stream:
        content = content + chunk if content else chunk

        push_ui_message(
            "joke",
            {"content": content.text()},
            id=ui_message["id"],
            message=calling_message,
            merge=True,
        )

    push_ui_message(
        "joke",
        {"content": content.text()},
        message=calling_message,
        id=ui_message["id"],
        metadata={"complete": True},
    )

    return Command(
        update={"messages": [ToolMessage(content, tool_call_id=tool_call_id)]},
    )

async def chat(state: AgentState):
    content = """You tell jokes. If the user asks you to tell a joke, you MUST call the `tell_joke` tool."""
    messages = [SystemMessage(content=content)] + state["messages"]
    model_with_tools = model.bind_tools([tell_joke, search_the_web])
    message = await model_with_tools.ainvoke(messages)
    print(message.tool_calls)
    return {"messages": [message]}

def should_continue(state):
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        return "tools"
    return END

workflow = StateGraph(AgentState)
workflow.add_node(chat)
workflow.add_node("tools", ToolNode([tell_joke, search_the_web]))

workflow.add_edge(START, "chat")
workflow.add_conditional_edges("chat", should_continue, ["tools", END])
workflow.add_edge("tools", END)

memory = MemorySaver()
graph = workflow.compile(checkpointer=memory)

def config(thread_id):
    return {"configurable": {"thread_id": thread_id}}

def serialize_values(values):
    messages = [message.dict() for message in values.get("messages", []) if not isinstance(message, ToolMessage)]
    ui = values.get("ui", [])
    return {"messages": messages, "ui": ui}

async def stream_response(request: RequestParams):
    input_messages = [HumanMessage(request.message)]

    async for stream_mode, chunk in graph.astream({"messages": input_messages}, config(request.thread_id), stream_mode=["messages", "values", "custom"]):
        if stream_mode == "messages":
            (message, metadata) = chunk

            yield f"event: messages\ndata:{json.dumps([message.dict(), metadata])}\n\n"

        elif stream_mode == "values":
            yield f"event: values\ndata:{json.dumps(serialize_values(chunk))}\n\n"

        elif stream_mode == "custom":
            yield f"event: custom\ndata:{json.dumps(chunk)}\n\n"

@app.post("/")
async def chat(request: RequestParams):
    return StreamingResponse(stream_response(request), media_type="text/event-stream")

@app.get("/thread/{thread_id}")
async def get_thread(thread_id: str):
    state = graph.get_state(config(thread_id))
    return serialize_values(state.values)
