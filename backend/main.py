import json
from typing import Annotated
from pydantic import BaseModel, Field

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, AIMessageChunk
from langchain_core.tools import tool, InjectedToolCallId
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, END, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, InjectedState
from langgraph.types import Command

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

llm = init_chat_model("gpt-4.1", model_provider="openai", api_key=Settings().openai_api_key)

class Question(BaseModel):
    """A multiple choice question."""
    title: str = Field(..., description="The question title")
    options: list[str] = Field(..., description="The options for the question")
    correct_option_index: int = Field(..., description="The index of the correct option, starting from 0")

@tool
def create_question(
    question: str,
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> "Command":
    """Set the lab requirements."""
    return Command(update={
        "messages": [
            ToolMessage(f"Question created successfully", tool_call_id=tool_call_id)
        ]
    })

async def chat(state: MessagesState) -> MessagesState:
    template = """If the user requests a question on a specific topic, create a question by calling the tool

After calling the tool, DO NOT repeat the question, just ask if they would like another"""

    messages = [SystemMessage(content=template)] + state["messages"]
    llm_with_tool = llm.bind_tools([create_question])
    response = await llm_with_tool.ainvoke(messages)
    return {"messages": [response]}

def should_continue(state):
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        return "tools"
    return END

workflow = StateGraph(MessagesState)
workflow.add_node("chat", chat)
workflow.add_node("tools", ToolNode([create_question]))

workflow.add_edge(START, "chat")
workflow.add_conditional_edges("chat", should_continue, ["tools", END])
workflow.add_edge("tools", "chat")

memory = MemorySaver()

async def stream_response(request: RequestParams):
    graph = workflow.compile(checkpointer=memory)
    config = {"configurable": {"thread_id": request.thread_id}}
    input_messages = [HumanMessage(request.message)]

    async for chunk, metadata in graph.astream({"messages": input_messages}, config, stream_mode="messages"):
        if isinstance(chunk, AIMessageChunk):
            print(chunk.tool_call_chunks)
            # Yield each chunk as a JSON object
        yield f"{json.dumps({'type': 'stream', 'token': chunk.content})}\n"


@app.post("/")
async def chat(request: RequestParams):
    return StreamingResponse(stream_response(request), media_type="text/event-stream")
