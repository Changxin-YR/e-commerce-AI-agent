from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from backend.app.metrics.contracts import SeriesParams


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class CreateRun(Strict):
    dataset_id: str = Field(min_length=1, max_length=64)
    variant: Literal["B1", "B2"] = "B2"
    question: str = Field(min_length=1, max_length=4000)
    idempotency_key: str = Field(min_length=1, max_length=128)
    constraints: SeriesParams | None = None
    conversation_parent_run_id: str | None = Field(default=None, min_length=1, max_length=64)


class ResumeRun(Strict):
    revision: int = Field(ge=0)
    idempotency_key: str = Field(min_length=1, max_length=128)


class AnswerRun(ResumeRun):
    answers: dict[str, str] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def bounded_answers(self):
        if any(not k.strip() or len(k)>64 or not v.strip() or len(v)>2000 for k,v in self.answers.items()):
            raise ValueError("Answers must be nonempty bounded text")
        return self


class Claim(Strict):
    tool_call_id: str = Field(min_length=1, max_length=80)
    field_path: str = Field(min_length=1, max_length=200)
    label: str = Field(min_length=1, max_length=200)
    value: str | int


class Decision(Strict):
    action: Literal["answer", "clarify", "unsupported"]
    message: str = Field(min_length=1, max_length=3000)
    fields: list[str] = Field(default_factory=list, max_length=8)
    claims: list[Claim] = Field(default_factory=list, max_length=40)

    @model_validator(mode="after")
    def correct_shape(self):
        if self.action == "clarify":
            if not self.fields or len(set(self.fields)) != len(self.fields) or any(not x or len(x)>64 for x in self.fields):
                raise ValueError("Clarification requires unique bounded fields")
        elif self.fields:
            raise ValueError("Only clarification may request fields")
        if self.action != "answer" and self.claims:
            raise ValueError("Only an answer may contain claims")
        return self
