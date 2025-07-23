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

from config import Settings

class RequestParams(BaseModel):
    message: str
    thread_id: str

class AgentState(MessagesState):
    ui: Annotated[Sequence[AnyUIMessage], ui_message_reducer]
    topic: str

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

@tool
def create_story(tool_call_id: Annotated[str, InjectedToolCallId]) -> Command:
    """Create a story"""
    return Command(
        goto="story_agent",
        update={
            "messages": [
                ToolMessage(f"Transferred to story agent", tool_call_id=tool_call_id)
            ]
        }
    )

@tool
def create_question(topic: Annotated[str, "The topic of the question"], tool_call_id: Annotated[str, InjectedToolCallId]) -> Command:
    """Create a question"""
    return Command(
        goto="question_agent",
        update={
            "topic": topic,
            "messages": [
                ToolMessage(f"Transferred to question agent", tool_call_id=tool_call_id)
            ]
        }
    )

async def story_agent(state: AgentState):
    writer = get_stream_writer()

    content_stream = model.with_config({"tags": ["nostream"]}).astream(
        "Create a short story"
    )

    # Find the last AI message that called the tool
    calling_message = None
    for message in reversed(state["messages"]):
        if isinstance(message, AIMessage) and message.tool_calls:
            calling_message = message
            break


    ui_message = push_ui_message("story", { "content": ""}, message=calling_message)

    content = None
    async for chunk in content_stream:
        content = content + chunk if content else chunk

        writer({
            "type": "UIPropMessageChunk",
            "id": ui_message["id"],
            "name": "story",
            "prop": "content",
            "value": chunk.text(),
        })

    ui_message = push_ui_message("story", { "content": content.text(), "complete": True}, id=ui_message["id"], message=calling_message)

    return {"messages": [calling_message]}

async def question_agent(state: AgentState):
    class Question(BaseModel):
        """A trivia multiple-choice question."""

        title: str = Field(..., description="The title of the question")
        options: list[str] = Field(..., description="The options for the question")
        correct_option_index: int = Field(..., description="The index of the correct option")

    model_with_tools = model.bind_tools([Question], tool_choice="Question")
    content_stream = model_with_tools.with_config({"tags": ["nostream"]}).astream(
        f"Create a trivia question on the topic: {state['topic']}"
    )

    # Find the last AI message that called the tool
    calling_message = None
    for message in reversed(state["messages"]):
        if isinstance(message, AIMessage) and message.tool_calls:
            calling_message = message
            break

    ui_message = push_ui_message("question", {}, message=calling_message)

    content = None
    async for chunk in content_stream:
        content = content + chunk if content else chunk

        push_ui_message(
            "question",
            content.tool_calls[0]["args"],
            id=ui_message["id"],
            message=calling_message
        )

async def chat(state: AgentState):
    content = """Help the user create storys and questions. Do so by calling the relevant tools.

If the user asks for another story or question, call the relevant tool again."""
    messages = [SystemMessage(content=content)] + state["messages"]
    model_with_tools = model.bind_tools([create_story, create_question])
    message = await model_with_tools.ainvoke(state["messages"])
    return {"messages": [message]}

def should_continue(state):
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        return "tools"
    return END

workflow = StateGraph(AgentState)
workflow.add_node(chat)
workflow.add_node(story_agent)
workflow.add_node(question_agent)
workflow.add_node("tools", ToolNode([create_story, create_question]))

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

    async for stream_mode, chunk in graph.astream({"messages": input_messages}, config(request.thread_id), stream_mode=["messages", "custom"]):
        if stream_mode == "messages":
            (message, metadata) = chunk

            if not isinstance(message, AIMessageChunk):
                continue

            if len(message.tool_call_chunks) > 0:
                continue

            data = {
              "id": message.id,
              "type": message.type,
              "content": message.content,
            }

            yield f"{json.dumps(data)}\n"

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
            else:
                yield f"{json.dumps(chunk)}\n"

@app.post("/")
async def chat(request: RequestParams):
    return StreamingResponse(stream_response(request), media_type="text/event-stream")

@app.get("/thread/{thread_id}")
async def get_thread(thread_id: str):
    state = graph.get_state(config(thread_id))

    messages = []
    for message in state.values.get("messages", []):
        if isinstance(message, AIMessage):
            messages.append({
                "id": message.id,
                "type": "AIMessage",
                "content": message.content
            })
        if isinstance(message, HumanMessage):
            messages.append({
                "id": message.id,
                "type": "HumanMessage",
                "content": message.content
            })
    return {"messages": messages, "ui": state.values.get("ui", [])}
