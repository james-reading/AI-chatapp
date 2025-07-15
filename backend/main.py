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
from langgraph.config import get_stream_writer

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
    question: Question,
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> "Command":
    """Set the lab requirements."""
    return Command(update={
        "messages": [
            ToolMessage(f"Question created successfully", tool_call_id=tool_call_id)
        ]
    })

@tool
def transfer_to_story_agent(tool_call_id: Annotated[str, InjectedToolCallId]) -> Command:
    """Transfer to story agent."""
    return Command(
        goto="story",
        update={
            "messages": [
                ToolMessage(f"Transferred to story agent", tool_call_id=tool_call_id)
            ]
        }
    )

async def chat(state: MessagesState) -> MessagesState:
    print("CHAT NODE")
    template = """If the user requests a question on a specific topic, create a question by calling the `create_question` tool

If the user requests a story, transfer to the `story` agent by calling the `transfer_to_story_agent` tool"""

    messages = [SystemMessage(content=template)] + state["messages"]
    llm_with_tool = llm.bind_tools([create_question, transfer_to_story_agent])
    response = await llm_with_tool.ainvoke(messages)
    return {"messages": [response]}

async def story(state: MessagesState) -> MessagesState:
    writer = get_stream_writer()
    template = """Write a very short story about trees"""

    messages = [SystemMessage(content=template)] + state["messages"]
    writer({"type": "story", "key": "Story start", "id": "123"})
    response = await llm.ainvoke(messages, {"metadata": {"foo": {"type": "story", "id": "123"}}})
    writer({"type": "story", "key": "Story end", "id": "123"})
    return {"messages": [response]}

def should_continue(state):
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        return "tools"
    return END

workflow = StateGraph(MessagesState)
workflow.add_node("chat", chat)
workflow.add_node("story", story)
workflow.add_node("tools", ToolNode([create_question, transfer_to_story_agent]))

workflow.add_edge(START, "chat")
workflow.add_conditional_edges("chat", should_continue, ["tools", END])
workflow.add_edge("tools", END)
workflow.add_edge("story", END)

memory = MemorySaver()

async def stream_response(request: RequestParams):
    graph = workflow.compile(checkpointer=memory)
    config = {"configurable": {"thread_id": request.thread_id}}
    input_messages = [HumanMessage(request.message)]

    first = True
    async for stream_mode, chunk in graph.astream({"messages": input_messages}, config, stream_mode=["messages", "updates", "custom"]):
        print("---")
        if stream_mode == "messages":
            (message, metadata) = chunk

            if isinstance(message, AIMessageChunk):
                if message.tool_call_chunks:
                    # print("tool_call_chunks")
                    # print(message.tool_call_chunks)
                    if first:
                        gathered = message
                        first = False
                    else:
                        gathered = gathered + message

                    for tool_call_chunk in message.tool_call_chunks:
                        yield f"{json.dumps(gathered.tool_calls[tool_call_chunk['index']])}\n"
                else:
                    print("NO tool_call_chunks")
                    first = True

                    if metadata.get("foo", {}).get("type") == "story":
                        yield f"{json.dumps({'type': 'story', 'token': message.content})}\n"
                    else:
                        yield f"{json.dumps({'type': 'stream', 'token': message.content})}\n"

        elif stream_mode == "updates":
            print(chunk)
        elif stream_mode == "custom":
            print("Custom stream mode:")
            print(chunk)


@app.post("/")
async def chat(request: RequestParams):
    return StreamingResponse(stream_response(request), media_type="text/event-stream")
