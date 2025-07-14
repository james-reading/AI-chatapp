from typing import Annotated
from pydantic import BaseModel, Field
from operator import add

from langchain.chat_models import init_chat_model
from langchain_core.messages import SystemMessage, ToolMessage, RemoveMessage
from langchain_core.tools import tool, InjectedToolCallId

from langgraph.graph import START, END, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, InjectedState
from langgraph.types import Command
from langgraph.graph.message import REMOVE_ALL_MESSAGES

from config.settings import Settings
from models import LabRequirements, Question

llm = init_chat_model("gpt-4.1", model_provider="openai", api_key=Settings().openai_api_key)

class State(MessagesState):
    step: str
    requirements: LabRequirements
    briefing: str
    questions: Annotated[list[Question], add]

@tool
def set_briefing(
    briefing: str,
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> "Command":
    """Set the lab briefing."""
    print(f"Setting briefing: {briefing}")
    return Command(update={
        "briefing": briefing,
        "messages": [
            ToolMessage("Briefing was set successfully", tool_call_id=tool_call_id)
        ]
    })

@tool
def transfer_to_next_agent() -> "Command":
    """Go to the next agent."""
    print("Transferring to questions agent")
    return Command(
        update={"step": "questions_graph", "messages": [RemoveMessage(REMOVE_ALL_MESSAGES)]},
        goto="questions_graph",
        graph=Command.PARENT,
    )

# @tool
# def update_briefing(
#     tool_call_id: Annotated[str, InjectedToolCallId],
#     edits: list[str] = Field(description="List of edits to apply to the briefing, using sed-like syntax")
# ) -> "Command":
#     """Make changes to the lab briefing."""

#     print(f"update_briefing: {edits}")
#     return Command(update={
#         "messages": [
#             ToolMessage("Edits applied successfully", tool_call_id=tool_call_id)
#         ]
#     })

def briefing(state: State) -> State:
    print("briefing node")
    template = """You are an AI assistant tasked with creating a briefing for a lab based on the following requirements:
{requirements}

These requirements have been gathered by a previous agent and are now available for you to use.

Your instructions are as follows:
    1. Call the `set_briefing` tool to set the briefing for the lab.
    2. After the briefing has been set, ask the user if they are happy to move on to the next step. You do not need to repeat the briefing back to them.
    3. When the user confirms they want to move on, IMMEDIATELY call the `transfer_to_next_agent` tool to transfer to the next agent.
    4. If the user  requests changes, you should call the `set_briefing` tool again.

Notes:
    - The briefing should be concise and to the point.
    - You should never respond directly with the briefing text, only use the `set_briefing` tool to set it.

The current briefing is:
{briefing}"""

    content = template.format(requirements=state["requirements"], briefing=state.get("briefing", "NOT SET"))
    messages = [SystemMessage(content=content)] + state["messages"]
    llm_with_tools = llm.bind_tools([set_briefing, transfer_to_next_agent])
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}

def should_continue(state):
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        return "tools"
    return END

workflow = StateGraph(State)
workflow.add_node("briefing", briefing)
workflow.add_node("tools", ToolNode([set_briefing, transfer_to_next_agent]))

workflow.add_edge(START, "briefing")
workflow.add_conditional_edges("briefing", should_continue, ["tools", END])
workflow.add_edge("tools", "briefing")

graph = workflow.compile()
