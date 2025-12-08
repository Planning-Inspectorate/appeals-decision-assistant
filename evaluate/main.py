#!/usr/bin/env python3
"""Sample evaluation script using Langsmith and OpenEvals"""

import json
import logging

from langchain.agents import create_agent
from langchain_community.callbacks import get_openai_callback
from langchain_openai import AzureChatOpenAI
from langsmith import Client
from langsmith.evaluation._runner import ComparativeExperimentResults
from langsmith.schemas import ExperimentResults
from openevals.llm import create_llm_as_judge
from openevals.prompts import CORRECTNESS_PROMPT


def create_sample_dataset(client: Client):
    """Create a sample dataset in LangSmith for spelling correction."""
    dataset = client.create_dataset(
        dataset_name="spellcheck-dataset", description="A sample dataset to test spelling corrections in LangSmith."
    )
    examples = [
        {
            "inputs": {"message": "Mont Kilmanjaro is locayted in Tanzaania."},
            "outputs": {"corrected_message": "Mount Kilimanjaro is located in Tanzania."},
        },
        {
            "inputs": {"message": "Erth's lowest pint is The Dead See."},
            "outputs": {"corrected_message": "Earth's lowest point is The Dead Sea."},
        },
    ]
    client.create_examples(dataset_id=dataset.id, examples=examples)


def target(inputs: dict) -> dict:
    """This defines a sample application logic. In practice it will be replaced with our actual decision agent. Dataset inputs are handed as function inputs."""
    deployment = "pins-llm-gpt-5-mini-ada-dev"
    agent = create_agent(
        model=AzureChatOpenAI(azure_deployment=deployment),
        tools=[],
        system_prompt="You are a spelling and grammar correction assistant. Given an input message, you will provide a corrected version of the message with proper spelling and grammar.",
    )

    with get_openai_callback() as usage:
        response = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": inputs["message"],
                    }
                ]
            }
        )

    logging.info("response: %s", json.dumps(response, indent=2, default=repr))
    logging.info("cost: $%.6f", usage.total_cost)
    return {"answer": response["messages"][-1].content}

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

def main(client: Client) -> ExperimentResults | ComparativeExperimentResults:
    """Run the evaluation experiment."""

    return client.evaluate(
        target,
        data="spellcheck-dataset",
        evaluators=[correctness_evaluator],
        experiment_prefix="spellcheck-eval",
        max_concurrency=2,
    )

if __name__ == "__main__":
    client = Client()
    results = main(client)
