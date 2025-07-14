import json
from typing import Annotated
from pydantic import BaseModel, Field
from operator import add

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, AIMessageChunk
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, END, MessagesState, StateGraph
from langgraph.graph.message import add_messages

from langchain_core.callbacks import BaseCallbackHandler

from requirements import graph as requirements_graph
from briefing import graph as briefing_graph
from questions import graph as questions_graph
from config.settings import Settings
from models import LabRequirements, Question

class RequestParams(BaseModel):
    message: str

class State(MessagesState):
    step: str
    requirements: LabRequirements
    briefing: str
    questions: Annotated[list[Question], add]

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

def router(state: State):
    return state.get("step", "requirements_graph")

workflow = StateGraph(State)
workflow.add_node("requirements_graph", requirements_graph)
workflow.add_node("briefing_graph", briefing_graph)
workflow.add_node("questions_graph", questions_graph)

workflow.add_conditional_edges(START, router, ["requirements_graph", "briefing_graph", "questions_graph"])

memory = MemorySaver()

async def stream_response(message: str):
    graph = workflow.compile(checkpointer=memory)
    config = {"configurable": {"thread_id": "1"}}
    input_messages = [HumanMessage(message)]

    first = True
    # Stream the workflow execution using messages mode
    async for namespace, (chunk, metadata) in graph.astream({"messages": input_messages}, config, subgraphs=True, stream_mode="messages"):
        print(chunk)
        if isinstance(chunk, AIMessageChunk):
            if chunk.tool_call_chunks:
                if first:
                    gathered = chunk
                    is_first = False
                else:
                    gathered = gathered + chunk


                yield f"data: {json.dumps({'type': 'tool', 'content': gathered.tool_calls})}\n\n"
            else:
                is_first = True # HACK: need a better way to isolate tool calls
                yield f"data: {json.dumps({'type': 'thinking', 'content': chunk.content})}\n\n"


@app.post("/")
async def chat(request: RequestParams):
    return StreamingResponse(stream_response(request.message), media_type="text/event-stream")
