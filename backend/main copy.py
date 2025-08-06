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

from config import Settings


class RequestParams(BaseModel):
    input: dict


# class QuestionOption(BaseModel):
#     """Model for a multiple-choice option."""
#     value: str = Field(..., description="The text of the option.")


# class Question(BaseModel):
#     """Model for a question."""
#     title: str = Field(..., description="The title of the question.")
#     options: list[QuestionOption] = Field(..., description="List of multiple-choice options for the question.")
#     correct_option_index: int = Field(..., description="Index of the correct option, starting from 0.")

# class Lab(BaseModel):
#     topic: str = Field(..., description="The topic of the lab.")
#     questions: list[Question] = Field(..., description="List of questions in the lab.")

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

model = init_chat_model("gpt-4.1", model_provider="openai", api_key=Settings().openai_api_key)

# @tool("questions_agent", description="Assign task to a questions agent.")
# def handoff_tool(
#     tools_call_id: Annotated[str, InjectedToolCallId]
# ) -> Command:
#     tool_message = ToolMessage(content="Successfully transferred to questions_agent", tool_call_id=tools_call_id)

#     return Command(
#         update={"messages": [tool_message]},
#         goto="questions_agent"
#     )

def router(state: AgentState):
    if

async def supervisor(state: AgentState):
    prompt = """You are the Lab Builder AI Assistant. You help users to create cyber security labs."""

    messages = [SystemMessage(content=prompt)] + state["messages"]
    response = await model.ainvoke(messages)

    return {"messages": [response]}

# def should_continue(state):
#     messages = state["messages"]
#     last_message = messages[-1]
#     if last_message.tool_calls:
#         return "tools"
#     return END

# async def questions_agent(state: AgentState):
#     prompt = """You are an AI assistant that helps create trivia questions for a quiz.

# Your task is to analyze the current quiz state and plan the next question strategically.

# Your Response should include the type of question you will create next and why, the specific aspect of the topic it will cover,
# and it complements the existing questions

# Do NOT create the actual question yet - only explain your planned approach.

# Keep your response VERY brief, no more than a sentence.

# Quiz State:
# {quiz}"""

#     content = prompt.format(quiz=state["lab"])

#     messages = [SystemMessage(content=content)]
#     # model_with_tools = model.bind_tools([transfer_to_question_agent])
#     response = await model.ainvoke(messages)
#     return {"messages": [response]}

# async def create_question(state: AgentState):
#     prompt = """You are an AI assistant that helps create trivia questions for a quiz.

# Your task is to analyze the current quiz state and create next question strategically.

# You should review your planned approach from the last response.

# Quiz State:
# {quiz}"""
#     messages = [SystemMessage(content=prompt)] + state["messages"]
#     model_with_tools = model.bind_tools([Question], tool_choice="Question", parallel_tool_calls=False)
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
#     ui_message = push_ui_message(
#         tool_call["name"],
#         tool_call["args"],
#         id=ui_message["id"],
#         message=message,
#         metadata={
#             "complete": True
#         }
#     )

#     tool_message = ToolMessage(content="Question created", tool_call_id=message.tool_calls[0]["id"])

#     return {"messages": [message, tool_message]}

workflow = StateGraph(AgentState)
workflow.add_node(supervisor)
# workflow.add_node(questions_agent)
# workflow.add_node(create_question)
# workflow.add_node("tools", ToolNode([handoff_tool]))
workflow.add_edge(START, "supervisor")
# workflow.add_conditional_edges("supervisor", should_continue, ["tools", END])
# workflow.add_edge("questions_agent", "create_question")


memory = MemorySaver()
graph = workflow.compile(checkpointer=memory)

def graph_input(request: RequestParams):
    if request.input.get("message"):
        input_messages = [HumanMessage(request.input["message"])]

        return {"messages": input_messages, "lab": Lab(**request.input["context"]["lab"])}

    if request.input.get("command"):
        return Command(update=request.input["command"]["update"], resume={"foo": "bar"})

    return {"messages": [], "lab": Lab(**request.input["context"]["lab"])}

def serialize_values(values):
    messages = []
    for message in values.get("messages", []):
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
    return {"messages": messages, "ui": values.get("ui", [])}

async def stream_response(thread_id: str, request: RequestParams):
    input = graph_input(request)
    config = {"configurable": {"thread_id": thread_id}}

    async for namespace, stream_mode, chunk in graph.astream(input, config, subgraphs=True, stream_mode=["messages", "custom", "values"]):
        if stream_mode == "messages":
            (message, metadata) = chunk

            data = {
              "id": message.id,
              "type": message.type,
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

        if stream_mode == "values":
            data = { "type": "values", "values": serialize_values(chunk) }

        yield f"{json.dumps(data)}\n"

@app.post("/thread/{thread_id}/stream")
async def stream_thread(thread_id: str, request: RequestParams):
    return StreamingResponse(stream_response(thread_id, request), media_type="text/event-stream")

@app.get("/thread/{thread_id}")
async def get_thread(thread_id: str):
    state = graph.get_state({"configurable": {"thread_id": thread_id}})
    return serialize_values(state.values)
