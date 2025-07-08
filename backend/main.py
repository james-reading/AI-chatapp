import json
from pydantic import BaseModel, Field
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from typing_extensions import TypedDict

from config.settings import Settings

class MultipleChoiceQuestionOption(BaseModel):
    value: str = Field(
        description="The text of the option.",
    )

class MultipleChoiceQuestion(BaseModel):
    title: str = Field(
        description="The question to be answered.",
    )
    options: list[MultipleChoiceQuestionOption] = Field(
        description="The options to choose from.",
    )
    correct_option: int = Field(
        description="The index of the correct option in the options list.",
    )

class MessageRequest(BaseModel):
    message: str

class TopicRequest(BaseModel):
    topic: str

class QuestionState(TypedDict):
    topic: str
    messages: list
    thinking: str
    question: MultipleChoiceQuestion | None

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

model = init_chat_model("gpt-4o-mini", model_provider="openai", api_key=Settings().openai_api_key)

workflow = StateGraph(state_schema=QuestionState)

question_instructions="""You are tasked with creating a multiple choice question about a specific topic.

The question should be clear and concise, and it should have a set of options for the user to choose from.
Only one of the options should be correct.

The topic is: {topic}
The maximum number of options is {max_options}."""

thinking_instructions="""You are an AI assistant that creates multiple choice questions. You should think out loud about your process of creating a good question on the given topic.

Topic: {topic}

Think through your process step by step, but keep it very brief, no longer than 1 or 2 sentences."""

def think_about_question(state):
    """Think out loud about creating the question"""
    topic = state['topic']

    # System message for thinking
    system_message = thinking_instructions.format(topic=topic)

    # Generate thinking response
    response = model.invoke([SystemMessage(content=system_message), HumanMessage(content="Think about how to create a good multiple choice question for this topic.")])

    return {"thinking": response.content}

def create_question(state):
    """Create question based on the thinking"""
    topic = state['topic']

    # Enforce structured output
    structured_model = model.with_structured_output(MultipleChoiceQuestion)

    # System message
    system_message = question_instructions.format(topic=topic, max_options=4)

    # Include the thinking in the context
    thinking_context = f"Based on my previous thinking: {state.get('thinking', '')}"

    # Generate question
    response = structured_model.invoke([
        SystemMessage(content=system_message),
        HumanMessage(content=f"{thinking_context}\n\nNow create the multiple choice question.")
    ])

    return {"question": response}


# Define the function that calls the model
def call_model(state: MessagesState):
    response = model.invoke(state["messages"])
    return {"messages": response}

# Define the nodes in the graph
workflow.add_edge(START, "think_about_question")
workflow.add_node("think_about_question", think_about_question)
workflow.add_edge("think_about_question", "create_question")
workflow.add_node("create_question", create_question)

# Add memory
memory = MemorySaver()

async def stream_response(topic: str):
    app = workflow.compile(checkpointer=memory)

    config = {"configurable": {"thread_id": "abc123"}}

    # Initial state with the topic
    initial_state = {
        "topic": topic,
        "messages": [],
        "thinking": "",
        "question": None
    }

    try:
        # Stream the workflow execution using messages mode
        async for chunk in app.astream(initial_state, config, stream_mode="messages"):
            # Check if this is a message chunk
            if isinstance(chunk, tuple) and len(chunk) == 2:
                message, metadata = chunk

                # Check if it's an AI message with content
                if hasattr(message, 'content') and message.content:
                    # Determine the type based on metadata or content structure
                    node_name = metadata.get('langgraph_node', '') if metadata else ''

                    if node_name == "think_about_question":
                        # Stream thinking content as it comes
                        yield f"data: {json.dumps({'type': 'thinking', 'content': message.content})}\n\n"
                    elif node_name == "create_question":
                        # This will be the structured output, we'll handle it in updates mode
                        continue

        # After streaming is complete, get the final state to extract the structured question
        final_state = await app.ainvoke(initial_state, config)
        if final_state.get("question"):
            question = final_state["question"]
            question_dict = {
                "title": question.title,
                "options": [{"value": opt.value} for opt in question.options],
                "correct_option": question.correct_option
            }
            yield f"data: {json.dumps({'type': 'question', 'content': question_dict})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"


@app.post("/")
async def create_question_by_topic(request: TopicRequest):
    """Create a question based on a specific topic"""
    return StreamingResponse(stream_response(request.topic), media_type="text/event-stream")
