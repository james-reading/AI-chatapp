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
def transfer_to_next_agent(requirements: LabRequirements) -> "Command":
    """Pass the requirements to the next agent."""
    return Command(
        goto="briefing_graph",
        update={"requirements": requirements},
        graph=Command.PARENT,
    )

def gather_requirements(state: State) -> State:
    print("gather_requirements node")
    template = """Your job is to collect requirements from a user about the type of lab they want to create.

You should get the following information from them:

- Topic - What subject will the lab cover?
- Target Persona - Who is the lab for?
- Difficulty Level - What is the difficulty level of the lab? (1-7)

If you are not able to discern this info, ask them to clarify! Do not attempt to wildly guess.

After you are able to discern all the information, call the relevant tool to pass the requirements to the next agent.

If the user asks something unrelated to the lab requirements, respond kindly but do not answer their question. Instead, remind them that your job is to gather requirements.

Respond using Markdown formatting where appropriate."""

    messages = [SystemMessage(content=template)] + state["messages"]
    llm_with_tool = llm.bind_tools([transfer_to_next_agent])
    response = llm_with_tool.invoke(messages)
    return {"messages": [response]}

def should_continue(state):
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        return "tools"
    return END

workflow = StateGraph(State)
workflow.add_node("gather_requirements", gather_requirements)
workflow.add_node("tools", ToolNode([transfer_to_next_agent]))

workflow.add_edge(START, "gather_requirements")
workflow.add_conditional_edges("gather_requirements", should_continue, ["tools", END])

graph = workflow.compile()
