import uuid
from typing import Annotated, Sequence

from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, SystemMessage
from langgraph.graph import START, END, MessagesState, StateGraph
from langgraph.graph.ui import AnyUIMessage, ui_message_reducer, push_ui_message

from config import Settings


class AgentState(MessagesState):
    ui: Annotated[Sequence[AnyUIMessage], ui_message_reducer]

model = init_chat_model("gpt-4.1", model_provider="openai", api_key=Settings().openai_api_key)

def router(state: AgentState):
    if len(state["messages"]) == 0:
        return "intro"
    return "requirements"

def intro(state: AgentState):
    content = "Hi! I'm your Lab Builder assistant. How can I help today?"
    message = AIMessage(
        id=str(uuid.uuid4()),
        content=content,
    )

    push_ui_message(
        "QuickActions",
       {
           "actions": [
                { "label": "Build a lab from scratch", "message": "I want to build a lab from scratch" },
                { "label": "Review my existing lab", "message": "Review my lab" },
           ]
       },
        message=message
    )

    return { "messages": [message] }

async def requirements(state: AgentState):
    template = """You are an AI assistant for creating labs. At this stage, your ONLY job is to gather the requirements for the lab from the user.

You should get the following information from them:

- Topic - What subject will the lab cover?
- Target Persona - Who is the lab for?
- Difficulty Level - What is the difficulty level of the lab? (1-7)

Your instructions are as follows:

1. Ask the user for the information, one by one.
2. Once you have discerned all the necessary the information, call the `set_lab_requirements` tool.
3. After the requirements have been set, ask the user if they are happy to move on to the next step. You do not need to repeat the requirements back to them.
4. When the user confirms they want to move on, IMMEDIATELY call the `transfer_to_next_agent` tool to transfer to the next agent.
5. If the user changes their mind or requests changes, you should call the `set_lab_requirements` tool again.

Notes:

- If you are not able to discern this info, ask them to clarify! Do not attempt to wildly guess.
- If the user mentions something unrelated to the lab requirements, respond kindly but stay on topic. Remind them that your job is to gather requirements.
- IMPORTANT: Always call `transfer_to_next_agent` when the user wants to proceed to the next step. Do not ask for permission - just do it.
"""

    messages = [SystemMessage(content=template)] + state["messages"]
    # llm_with_tool = llm.bind_tools([set_lab_requirements, transfer_to_next_agent])
    response = await model.ainvoke(messages)
    return {"messages": [response]}

workflow = StateGraph(AgentState)
workflow.add_node(router)
workflow.add_node(intro)
workflow.add_node(requirements)

workflow.add_conditional_edges(START, router, ["intro", "requirements"])

graph = workflow.compile()
