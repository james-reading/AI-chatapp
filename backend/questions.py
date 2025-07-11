from pydantic import BaseModel, Field

from langchain.chat_models import init_chat_model
from langchain_core.messages import SystemMessage
from langgraph.graph import START, END, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from config.settings import Settings
from models import LabRequirements

llm = init_chat_model("gpt-4.1", model_provider="openai", api_key=Settings().openai_api_key)

class State(MessagesState):
    requirements: LabRequirements

def questions(state: State) -> State:
    print("questions node")
    template = """Tell a joke"""

    messages = [SystemMessage(content=template)] + state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response]}

workflow = StateGraph(State)
workflow.add_node("questions", questions)

workflow.add_edge(START, "questions")
workflow.add_edge("questions", END)

graph = workflow.compile()
