from typing import Annotated
from operator import add
from pydantic import BaseModel, Field

from langchain.chat_models import init_chat_model
from langchain_core.messages import SystemMessage, ToolMessage, AIMessage, RemoveMessage
from langchain_core.tools import tool, InjectedToolCallId
# from langchain_core.callbacks import BaseCallbackHandler
from langgraph.graph.message import REMOVE_ALL_MESSAGES


from langgraph.graph import START, END, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, InjectedState
from langgraph.types import Command

from config import Settings

llm = init_chat_model("gpt-4.1", model_provider="openai", api_key=Settings().openai_api_key)

class LabRequirements(BaseModel):
    """Requirements needed to create a lab."""

    topic: str = Field(description="The topic of the lab")
    target_persona: str = Field(description="Who s the lab for?")
    difficulty_level: int = Field(default=1, ge=1, le=7, description="Difficulty level of the lab")

class QuestionOption(BaseModel):
    """An option for a question."""
    value: str = Field(description="The text of the option")

class Question(BaseModel):
    """A question to ask the user."""

    title: str = Field(description="The title of the question")
    options: list[QuestionOption] = Field(description="The multiple-choice options for the question")
    correct_option: int = Field(
        ge=0, description="The index of the correct option in the options list"
    )

class State(MessagesState):
    step: str
    requirements: LabRequirements
    briefing: str
    questions: Annotated[list[Question], add]

@tool
def set_lab_requirements(
    requirements: LabRequirements,
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> "Command":
    """Set the lab requirements."""
    return Command(update={
        "requirements": requirements,
        "messages": [
            ToolMessage(f"Updated requirements to {requirements}", tool_call_id=tool_call_id)
        ]
    })

@tool
def transfer_to_next_agent() -> "Command":
    """Go to the next agent."""
    return Command(
        update={"step": "briefing_graph", "messages": [RemoveMessage(REMOVE_ALL_MESSAGES)]},
        goto="briefing_graph",
        graph=Command.PARENT,
    )

async def gather_requirements(state: State) -> State:
    print("gather_requirements node")
    template = """You are an AI assistant for creating labs. At this stage, your ONLY job is to gather the requirements for the lab from the user.

You should get the following information from them:

- Topic - What subject will the lab cover?
- Target Persona - Who is the lab for?
- Difficulty Level - What is the difficulty level of the lab? (1-7)

Your instructions are as follows:

1. Ask the user for the information.
2. Once you have discerned all the necessary the information, call the `set_lab_requirements` tool.
3. After the requirements have been set, ask the user if they are happy to move on to the next step. You do not need to repeat the requirements back to them.
4. When the user confirms they want to move on, IMMEDIATELY call the `transfer_to_next_agent` tool to transfer to the next agent.
5. If the user changes their mind or requests changes, you should call the `set_lab_requirements` tool again.

Notes:

- If you are not able to discern this info, ask them to clarify! Do not attempt to wildly guess.
- If the user mentions something unrelated to the lab requirements, respond kindly but stay on topic. Remind them that your job is to gather requirements.
- Respond using Markdown formatting where appropriate.
- IMPORTANT: Always call `transfer_to_next_agent` when the user wants to proceed to the next step. Do not ask for permission - just do it.

The current requirements are: {requirements}"""

    content = template.format(requirements=state.get("requirements", "Not set yet"))
    messages = [SystemMessage(content=content)] + state["messages"]
    llm_with_tool = llm.bind_tools([set_lab_requirements, transfer_to_next_agent])
    response = await llm_with_tool.ainvoke(messages, { "metadata": {"foo": "bar"}, "tags": ["floo"] })
    return {"messages": [response]}

def should_continue(state):
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        return "tools"
    return END

workflow = StateGraph(State)
workflow.add_node("gather_requirements", gather_requirements)
workflow.add_node("tools", ToolNode([set_lab_requirements, transfer_to_next_agent]))

workflow.add_edge(START, "gather_requirements")
workflow.add_conditional_edges("gather_requirements", should_continue, ["tools", END])
workflow.add_edge("tools", "gather_requirements")

graph = workflow.compile()
