from pydantic import BaseModel, Field

from langchain.chat_models import init_chat_model
from langchain_core.messages import SystemMessage
from langchain_core.tools import tool

from langgraph.graph import START, END, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import Command

from config.settings import Settings
from models import LabRequirements

llm = init_chat_model("gpt-4.1", model_provider="openai", api_key=Settings().openai_api_key)

class State(MessagesState):
    requirements: LabRequirements

@tool
def transfer_to_next_agent() -> "Command":
    """Go to to the next agent."""
    return Command(
        goto="questions_graph",
        graph=Command.PARENT,
    )

def acknowledge(state: State) -> State:
    print("briefing acknowledge node")
    template = """A previous agent has gathered the following requirements for a lab:
    {requirements}

    Acknowledge that you have received these requirements, and will now move on to generating the lab briefing."""

    messages = [SystemMessage(content=template.format(requirements=state["requirements"]))] + state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response]}

def briefing(state: State) -> State:
    print("briefing node")
    template = """A previous agent has gathered the following requirements for a lab:
    {requirements}
    Your job is to create a briefing for the lab based on these requirements. The briefing is a short summary that outlines the key points of the lab.

    It is at most one paragraph long

    Use markdown formatting where appropriate."""

    messages = [SystemMessage(content=template.format(requirements=state["requirements"]))] + state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response]}

def feedback(state: State) -> State:
    print("briefing feedback node")
    template = """A previous agent has gathered the following requirements for a lab:
    {requirements}

    And from these requirements you have created a briefing. Now your job is to take on board a feedback from the user and update the briefing accordingly.

    Tell the user they should let you know if they are happy with the briefing, and when they are you should call the relevant tool to pass to the next agent.

    You do not need to generate a new briefing, or summarize it, you just ask and respond to feedback """

    messages = [SystemMessage(content=template.format(requirements=state["requirements"]))] + state["messages"]
    llm_with_tool = llm.bind_tools([transfer_to_next_agent])
    response = llm.invoke(messages)
    return {"messages": [response]}

def should_continue(state):
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        return "tools"
    return END

workflow = StateGraph(State)
workflow.add_node("acknowledge", acknowledge)
workflow.add_node("briefing", briefing)
workflow.add_node("feedback", feedback)
workflow.add_node("tools", ToolNode([transfer_to_next_agent]))

workflow.add_edge(START, "acknowledge")
workflow.add_edge(START, "briefing")
workflow.add_edge("acknowledge", END)
workflow.add_edge("briefing", "feedback")
workflow.add_conditional_edges("feedback", should_continue, ["tools", END])

graph = workflow.compile()
