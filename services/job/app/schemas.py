from pydantic import BaseModel, Field


class JobCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)
    skills: list[str] = []


class JobUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1)
    skills: list[str] | None = None


class JobOut(BaseModel):
    id: str
    title: str
    description: str
    skills: list[str]
    created_by: str
