from langchain_openai import AzureChatOpenAI
from ewa_pipeline.config import Config


def get_orchestrator_model(config: Config) -> AzureChatOpenAI:
    return AzureChatOpenAI(
        azure_deployment=config.azure_openai.deployments.big,
        azure_endpoint=config.azure_openai.endpoint,
        api_key=config.azure_openai.api_key,
        api_version=config.azure_openai.api_version,
        use_responses_api=True,
        temperature=0.1,
        max_retries=6,
    )


def get_subagent_model(config: Config) -> AzureChatOpenAI:
    return AzureChatOpenAI(
        azure_deployment=config.azure_openai.deployments.medium,
        azure_endpoint=config.azure_openai.endpoint,
        api_key=config.azure_openai.api_key,
        api_version=config.azure_openai.api_version,
        use_responses_api=True,
        temperature=0.1,
        max_retries=6,
    )


def get_cross_ref_model(config: Config) -> AzureChatOpenAI:
    return AzureChatOpenAI(
        azure_deployment=config.azure_openai.deployments.big,
        azure_endpoint=config.azure_openai.endpoint,
        api_key=config.azure_openai.api_key,
        api_version=config.azure_openai.api_version,
        use_responses_api=True,
        temperature=0.1,
        max_retries=6,
    )


def get_indexer_model_name(config: Config) -> str:
    return f"azure/{config.azure_openai.deployments.small}"
