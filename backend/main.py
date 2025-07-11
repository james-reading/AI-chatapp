from pydantic import BaseModel, Field

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, END, MessagesState, StateGraph

from requirements import graph as requirements_graph
from briefing import graph as briefing_graph
from questions import graph as questions_graph
from config.settings import Settings
from models import LabRequirements

class RequestParams(BaseModel):
    message: str

class State(MessagesState):
    requirements: LabRequirements

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

workflow = StateGraph(State)
workflow.add_node("requirements_graph", requirements_graph)
workflow.add_node("briefing_graph", briefing_graph)
workflow.add_node("questions_graph", questions_graph)

workflow.add_edge(START, "requirements_graph")

memory = MemorySaver()

@app.post("/")
async def chat(request: RequestParams):
    graph = workflow.compile(checkpointer=memory)
    config = {"configurable": {"thread_id": "1"}}
    messages = [HumanMessage(request.message)]
    output = graph.invoke({"messages": messages},config)
    return output
