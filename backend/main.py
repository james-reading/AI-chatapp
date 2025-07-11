import json

from pydantic import BaseModel, Field

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langchain_core.tools import tool, InjectedToolCallId
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, END, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import Command

from typing import Annotated

from config.settings import Settings

class LabRequirements(BaseModel):
    """Requirements needed to create a lab."""

    topic: str = Field(description="The topic of the lab")
    target_persona: str = Field(description="Who s the lab for?")
    difficulty_level: int = Field(default=1, ge=1, le=7, description="Difficulty level of the lab")

class Lab(BaseModel):
    """A cybersecurity lab."""
    title: str = Field(description="The title of the lab")

class State(MessagesState):
    step: str
    requirements: LabRequirements
    lab: Lab

class RequestParams(BaseModel):
    message: str
    lab: Lab

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

@tool
def set_lab_requirements(
    requirements: LabRequirements,
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """Update lab requirements."""
    return Command(update={
        "requirements": requirements,
        "messages": [
            ToolMessage(f"Updated requirements", tool_call_id=tool_call_id)
        ]
    })

@tool
def set_lab_title(
    lab: Lab,
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """Update lab title."""
    return Command(update={
        "lab": lab,
        "messages": [
            ToolMessage(f"Updated lab title", tool_call_id=tool_call_id)
        ]
    })

def gather_requirements(state):
    print("Node: gather_requirements")
    template = """Your job is to collect requirements from a user about the type of lab they want to create.

You should get the following information from them:

- Topic - What subject will the lab cover?
- Target Persona - Who is the lab for?
- Difficulty Level - What is the difficulty level of the lab? (1-7)

If you are not able to discern this info, ask them to clarify! Do not attempt to wildly guess.

After you are able to discern all the information, call the relevant tool.

If the user asks something unrelated to the lab requirements, respond kindly but do not answer their question. Instead, remind them that your job is to assist with creating a lab.

Respond using Markdown formatting where appropriate."""

    messages = [SystemMessage(content=template)] + state["messages"]
    llm_with_tool = llm.bind_tools([set_lab_requirements])
    response = llm_with_tool.invoke(messages)
    return {"messages": [response]}

def generate_title(state):
    print("Node: generate_title")
    template = """Based on the following requirements, generate a good title for the lab.:

{reqs}"""

    print("Generating title with requirements:", state["requirements"])

    messages = [SystemMessage(content=template.format(reqs=state["requirements"]))]
    llm_with_tool = llm.bind_tools([set_lab_title], tool_choice="set_lab_title")
    response = llm_with_tool.invoke(messages)
    return {"messages": [response]}

def explain_title(state):
    print("Node: explain_title")
    template = """You have just generated a title of a lab based on the user's requirements.
Acknowledge this, and tell the user they can ask for any changes they would like to make or if you should proceed with the lab creation process.

The requirements were:
{reqs}

The generated lab:
{lab}"""
    content = template.format(reqs=state["requirements"], lab=state["lab"])

    messages = [SystemMessage(content=content)]
    response = llm.invoke(messages)
    return {"messages": [response], "step": "title_feedback"}

def title_feedback(state):
    print("Node: title_feedback")
    template = """You have just generated a title for a lab based on the user's requirements, and asked for feedback.

    You should now respond to the user's feedback.

    If the user requests changes, you should respond with the appropriate tool call.

    If the user is satisfied with the title, you should respond with "Great! Let's proceed with creating the lab.

    If the user requests changes that are not related to the original requirements, kindly remind them that your job is to assist with feedback on the lab title, and that if they are happy they should request to move on.

    If they respond with something unrelated title feedback, kindly remind them that your job is to assist with feedback on the lab title, and that if they are happy they should request to move on."

The requirements were:
{reqs}

The generated lab:
{lab}"""
    content = template.format(reqs=state["requirements"], lab=state["lab"])

    messages = [SystemMessage(content=content)] + state["messages"]
    llm_with_tool = llm.bind_tools([set_lab_title])
    response = llm_with_tool.invoke(messages)
    print(response)
    return {"messages": [response]}

def after_gather_requirements(state):
    if state.get("requirements") is None:
        return END
    return "generate_title"

def router(state):
    print("Router state:", state.get("step", ""))
    return state.get("step", "gather_requirements")


workflow = StateGraph(State)
workflow.add_node("gather_requirements", gather_requirements)
workflow.add_node("set_requirements", ToolNode([set_lab_requirements]))
workflow.add_node("generate_title", generate_title)
workflow.add_node("set_title", ToolNode([set_lab_title]))
workflow.add_node("set_title_feedback", ToolNode([set_lab_title]))
workflow.add_node("explain_title", explain_title)
workflow.add_node("title_feedback", title_feedback)

workflow.add_conditional_edges(START, router, ["gather_requirements", "title_feedback"])
workflow.add_edge("gather_requirements", "set_requirements")
workflow.add_conditional_edges("set_requirements", after_gather_requirements, ["generate_title", END])
workflow.add_edge("generate_title", "set_title")
workflow.add_edge("set_title", "explain_title")
workflow.add_edge("explain_title", END)
workflow.add_edge("title_feedback", "set_title_feedback")
workflow.add_edge("set_title_feedback", END)

memory = MemorySaver()

async def stream_response(request: RequestParams):
    graph = workflow.compile(checkpointer=memory)
    config = {"configurable": {"thread_id": "1"}}
    input_messages = [HumanMessage(request.message)]

    async for stream_mode, step in graph.astream({"messages": input_messages, "lab": request.lab}, config, stream_mode=["messages", "values"]):
        if stream_mode == "messages":
            message = step[0]
            if isinstance(message, AIMessage):
                if message.tool_calls:
                    for tool_call in message.tool_calls:
                        yield f"data: {json.dumps({'type': 'tool', 'name': tool_call['name'], 'id': tool_call['id']})}\n\n"
                elif message.tool_call_chunks:
                    continue
                else:
                    yield f"data: {json.dumps({'type': 'thinking', 'content': step[0].content})}\n\n"

        if stream_mode == "values":
            last_message = step['messages'][-1]
            if isinstance(last_message, AIMessage) and last_message.tool_calls:
                for tool_call in last_message.tool_calls:
                        yield f"data: {json.dumps({'type': 'tool', 'name': tool_call['name'], 'id': tool_call['id'], 'args': tool_call['args']})}\n\n"
@app.post("/")
async def chat(request: RequestParams):
    return StreamingResponse(stream_response(request), media_type="text/event-stream")
