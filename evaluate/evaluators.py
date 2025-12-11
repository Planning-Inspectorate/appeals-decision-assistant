"""Evaluators for experiment assessments."""

from langchain_openai import AzureChatOpenAI
from openevals.llm import create_llm_as_judge
from openevals.prompts import CORRECTNESS_PROMPT


def correctness_evaluator(inputs: dict, outputs: dict, reference_outputs: dict):
    """Evaluate correctness of the output using an LLM-as-a-judge."""
    deployment = "pins-llm-gpt-5-mini-ada-dev"
    evaluator = create_llm_as_judge(
        prompt=CORRECTNESS_PROMPT,
        judge=AzureChatOpenAI(azure_deployment=deployment),
        feedback_key="correctness",
    )
    return evaluator(
        inputs=inputs, outputs=outputs, reference_outputs=reference_outputs
    )
