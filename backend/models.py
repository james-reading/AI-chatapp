from pydantic import BaseModel, Field


class LabRequirements(BaseModel):
    """Requirements needed to create a lab."""

    topic: str = Field(description="The topic of the lab")
    target_persona: str = Field(description="Who s the lab for?")
    difficulty_level: int = Field(default=1, ge=1, le=7, description="Difficulty level of the lab")
