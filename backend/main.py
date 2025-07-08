import json

from pydantic import BaseModel, Field

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, END, MessagesState, StateGraph

from typing import List
from typing_extensions import TypedDict

from config.settings import Settings


class Request(BaseModel):
    message: str

class LabRequirements(BaseModel):
    """Requirements needed to create a lab."""

    topic: str = Field(description="The topic of the lab")
    target_persona: str = Field(description="Who s the lab for?")
    difficulty_level: int = Field(default=1, ge=1, le=7, description="Difficulty level of the lab")
    LearningOutcomes: List[str]


app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

llm = init_chat_model("gpt-4o-mini", model_provider="openai", api_key=Settings().openai_api_key)
llm_with_tool = llm.bind_tools([LabRequirements])

template = """Your job is to collect requirements from a user about the type of lab they want to create.

You should get the following information from them:

- Topic - What subject will the lab cover?
- Target Persona - Who is the lab for?
- Difficulty Level - What is the difficulty level of the lab? (1-7)
- Learning Outcomes - What should participants learn?

If you are not able to discern this info, ask them to clarify! Do not attempt to wildly guess.

After you are able to discern all the information, call the relevant tool.

If the user asks something unrelated to the lab requirements, respond kindly but do not answer their question. Instead, remind them that your job is to assist with creating a lab.

Respond using Markdown formatting where appropriate."""

prompt_system = """Based on the following requirements, generate a good title and description for the lab.:

{reqs}"""


def info_chain(state):
    messages = [SystemMessage(content=template)] + state["messages"]
    response = llm_with_tool.invoke(messages)
    return {"messages": [response]}

# Function to get the messages for the prompt
# Will only get messages AFTER the tool call
def get_prompt_messages(messages: list):
    tool_call = None
    other_msgs = []
    for m in messages:
        if isinstance(m, AIMessage) and m.tool_calls:
            tool_call = m.tool_calls[0]["args"]
        elif isinstance(m, ToolMessage):
            continue
        elif tool_call is not None:
            other_msgs.append(m)
    return [SystemMessage(content=prompt_system.format(reqs=tool_call))] + other_msgs

def prompt_gen_chain(state):
    messages = get_prompt_messages(state["messages"])
    response = llm.invoke(messages)
    return {"messages": [response]}

def add_tool_message(state: MessagesState):
    return {
        "messages": [
            ToolMessage(
                content="Prompt generated!",
                tool_call_id=state["messages"][-1].tool_calls[0]["id"],
            )
        ]
    }

def get_state(state):
    messages = state["messages"]
    if isinstance(messages[-1], AIMessage) and messages[-1].tool_calls:
        return "add_tool_message"
    elif not isinstance(messages[-1], HumanMessage):
        return END
    return "info"


workflow = StateGraph(MessagesState)
workflow.add_node("info", info_chain)
workflow.add_node("prompt", prompt_gen_chain)
workflow.add_node("add_tool_message", add_tool_message)

workflow.add_conditional_edges("info", get_state, ["add_tool_message", "info", END])
workflow.add_edge("add_tool_message", "prompt")
workflow.add_edge("prompt", END)
workflow.add_edge(START, "info")


# Add memory
memory = MemorySaver()

async def stream_response(message: str):
    graph = workflow.compile(checkpointer=memory)

    config = {"configurable": {"thread_id": "5"}}

    input_messages = [HumanMessage(message)]

    # Stream the workflow execution using messages mode
    async for message, metadata in graph.astream({"messages": input_messages}, config, stream_mode="messages"):

            # Check if it's an AI message with content
        yield f"data: {json.dumps({'type': 'thinking', 'content': message.content})}\n\n"


@app.post("/")
async def chat(request: Request):
    return StreamingResponse(stream_response(request.message), media_type="text/event-stream")
