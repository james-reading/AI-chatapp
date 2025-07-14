from pydantic import BaseModel, Field


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
