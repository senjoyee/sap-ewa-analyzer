from typing import Any
from langchain_core.callbacks import BaseCallbackHandler
from pydantic import BaseModel


class TokenUsage(BaseModel):
    phase0_input_tokens: int = 0
    phase0_output_tokens: int = 0
    phase1_input_tokens: int = 0
    phase1_output_tokens: int = 0
    phase2_input_tokens: int = 0
    phase2_output_tokens: int = 0

    @property
    def total_input_tokens(self) -> int:
        return self.phase0_input_tokens + self.phase1_input_tokens + self.phase2_input_tokens

    @property
    def total_output_tokens(self) -> int:
        return self.phase0_output_tokens + self.phase1_output_tokens + self.phase2_output_tokens

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens


class TokenTracker(BaseCallbackHandler):
    def __init__(self, phase: str):
        super().__init__()
        self.phase = phase
        self.input_tokens = 0
        self.output_tokens = 0

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        if hasattr(response, "llm_output") and response.llm_output:
            usage = response.llm_output.get("token_usage", {})
            self.input_tokens += usage.get("prompt_tokens", 0)
            self.output_tokens += usage.get("completion_tokens", 0)
        for gen_list in response.generations:
            for gen in gen_list:
                if hasattr(gen, "generation_info") and gen.generation_info:
                    usage = gen.generation_info.get("usage", {})
                    if usage:
                        self.input_tokens += usage.get("input_tokens", 0)
                        self.output_tokens += usage.get("output_tokens", 0)

    def snapshot(self) -> dict[str, int]:
        return {"input": self.input_tokens, "output": self.output_tokens}
