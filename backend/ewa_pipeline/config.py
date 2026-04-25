from pathlib import Path
from pydantic import BaseModel
import yaml


class DeploymentsConfig(BaseModel):
    big: str
    medium: str
    small: str


class AzureConfig(BaseModel):
    endpoint: str
    api_key: str
    api_version: str
    deployments: DeploymentsConfig


class PageIndexConfig(BaseModel):
    model: str
    max_pages_per_node: int = 10
    max_tokens_per_node: int = 20000
    add_node_summary: bool = True
    add_doc_description: bool = False


class ModelPrice(BaseModel):
    input_per_1m: float = 0.0   # USD per million input tokens
    output_per_1m: float = 0.0  # USD per million output tokens


class Config(BaseModel):
    azure_openai: AzureConfig
    pageindex: PageIndexConfig
    pricing: dict[str, ModelPrice] = {}

    def pricing_dict(self) -> dict[str, dict[str, float]]:
        """Return pricing in the flat format CostTracker expects."""
        return {k: {"input_per_1m": v.input_per_1m, "output_per_1m": v.output_per_1m}
                for k, v in self.pricing.items()}


def load_config(path: Path | None = None) -> Config:
    if path and path.exists():
        config_path = path
    else:
        # Search order: CWD → backend/ directory (parent of ewa_pipeline/)
        candidates = [
            Path("config.yaml"),
            Path(__file__).resolve().parent.parent / "config.yaml",
        ]
        config_path = next((p for p in candidates if p.exists()), candidates[0])

    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return Config.model_validate(data)
