from typing import Annotated, Sequence


from langchain.chat_models import init_chat_model
from langchain_core.messages import ToolMessage, SystemMessage
from langchain_core.tools import tool, InjectedToolCallId
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, END, MessagesState, StateGraph
from langgraph.graph.ui import AnyUIMessage, ui_message_reducer
from langgraph.types import  Command
from langgraph.prebuilt import ToolNode

from config import Settings


class AgentState(MessagesState):
    ui: Annotated[Sequence[AnyUIMessage], ui_message_reducer]
    lab: dict


model = init_chat_model("gpt-4.1", model_provider="openai", api_key=Settings().openai_api_key)

@tool("questions_agent", description="Assign task to a questions agent.")
def handoff_tool(
    tools_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    tool_message = ToolMessage(content="Successfully transferred to questions_agent", tool_call_id=tools_call_id)

    return Command(
        update={"messages": [tool_message]},
        goto="questions_agent"
    )

async def supervisor(state: AgentState):
    prompt = """You are a supervisor managing one agent:
- The question agent, which creates trivia questions.

Assign work to one agent at a time, do not call agents in parallel.
Do not do any work yourself."""

    messages = [SystemMessage(content=prompt)] + state["messages"]
    model_with_tools = model.bind_tools([handoff_tool])
    response = await model_with_tools.ainvoke(messages)

    return {"messages": [response]}

def should_continue(state):
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        return "tools"
    return END

async def questions_agent(state: AgentState):
    prompt = """Tell a joke"""

    messages = [SystemMessage(content=prompt)] + state["messages"]
    # model_with_tools = model.bind_tools([transfer_to_question_agent])
    response = await model.ainvoke(messages)
    return {"messages": [response]}

workflow = StateGraph(AgentState)
workflow.add_node(supervisor)
workflow.add_node(questions_agent)
workflow.add_node("tools", ToolNode([handoff_tool]))

workflow.add_edge(START, "supervisor")
workflow.add_conditional_edges("supervisor", should_continue, ["tools", END])

memory = MemorySaver()
graph = workflow.compile()
