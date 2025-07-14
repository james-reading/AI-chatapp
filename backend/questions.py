from typing import Annotated
from pydantic import BaseModel, Field
from operator import add

from langchain.chat_models import init_chat_model
from langchain_core.messages import SystemMessage, ToolMessage
from langchain_core.tools import tool, InjectedToolCallId
from langgraph.graph import START, END, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, InjectedState
from langgraph.types import Command

from config.settings import Settings
from models import LabRequirements, Question

llm = init_chat_model("gpt-4.1", model_provider="openai", api_key=Settings().openai_api_key)

class State(MessagesState):
    step: str
    requirements: LabRequirements
    briefing: str
    questions: Annotated[list[Question], add]

@tool
def create_question(
    question: Question,
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> "Command":
    """Create a new question."""
    print(f"Creating question: {question}")

    return Command(update={
        "questions": [question],
        "messages": [
            ToolMessage(f"Question created successfully", tool_call_id=tool_call_id)
        ]
    })

def questions(state: State) -> State:
    print("questions node")
    template = """You are an AI assistant tasked with creating questions for a lab.

The questions should be relevant to the lab requirements, and the briefing.

- Call the `create_question` tool to create a question, do this until you have created 3 questions.
- Ask the user for feedback, are they happy with the questions created so far?
- If the user requests more questions, you can create them using the `create_question` tool.
- Once the user has confirmed they are happy with the questions, you should respond with "Great!".

Notes:
 - Only ever call the `create_question` tool once at a time.
 - You should never respond directly with the questions you have created, you only need to use the tool.

The requirements are as follows:
{requirements}

The lab briefing is as follows:
{briefing}

The current set of questions is:
{questions}"""

    content = template.format(
        requirements=state["requirements"],
        briefing=state["briefing"],
        questions=state.get("questions", [])
    )

    messages = [SystemMessage(content=content)] + state["messages"]
    llm_with_tools = llm.bind_tools([create_question])
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}

def should_continue(state):
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        return "tools"
    return END

workflow = StateGraph(State)
workflow.add_node("questions", questions)
workflow.add_node("tools", ToolNode([create_question]))

workflow.add_edge(START, "questions")
workflow.add_conditional_edges("questions", should_continue, ["tools", END])
workflow.add_edge("tools", "questions")

graph = workflow.compile()
