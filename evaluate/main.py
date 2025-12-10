#!/usr/bin/env python3
"""Sample evaluation script using Langsmith and OpenEvals"""

import json
import logging
import sys
from dataclasses import dataclass

from deepagents import create_deep_agent  # type: ignore[import-untyped]
from langchain.chat_models import init_chat_model
from langchain.tools import tool
from langchain_community.callbacks import get_openai_callback
from langchain_openai import AzureChatOpenAI
from langsmith import Client
from langsmith.evaluation._runner import ComparativeExperimentResults
from langsmith.schemas import ExperimentResults
from openevals.llm import create_llm_as_judge
from openevals.prompts import CORRECTNESS_PROMPT

from ada.main import main as ada_main


@dataclass
class FeedbackLedger:
    """A simple ledger to store feedback during evaluation."""
    review_comments: list[str]

def generate_write_fedback_tool(ledger: FeedbackLedger):
    """Generate a tool to write feedback during evaluation."""
    @tool
    def write_feedback(feedback: list[str]):
        """A tool to write feedback during evaluation. Review comments should be a list of strings. Each comment should quote the relevant section and provide a suggested correction."""
        logging.info("Review Comments Recorded: %s", feedback)
        for comment in feedback:
            ledger.review_comments.append(comment)
        return f"Feedback for {feedback} recorded."
    return write_feedback


def create_sample_dataset(client: Client):
    """Create a sample dataset in LangSmith for spelling correction."""
    dataset = client.create_dataset(
        dataset_name="spellcheck-dataset", description="A sample dataset to test spelling corrections in LangSmith."
    )
    examples = [
        {
            "inputs": {"message": "Mont Kilmanjaro is locayted in Tanzaania."},
            "outputs": {"review_comments": ["Kilmanjaro -> Kilimanjaro", "locayted -> located", "Tanzaania -> Tanzania"]},
        },
        {
            "inputs": {"message": "Erth's lowest pint is The Dead See."},
            "outputs": {"review_comments": ["Erth's -> Earth's", "pint -> point", "See -> Sea"]},
        },
    ]
    client.create_examples(dataset_id=dataset.id, examples=examples)


def sample_orchestrator(user_message: str) -> dict:
    """This defines a sample application logic. In practice it will be replaced with our actual decision agent. Dataset inputs are handed as function inputs."""
    deployment = "pins-llm-gpt-5-mini-ada-dev"

    review_ledger = FeedbackLedger(review_comments=[])

    feedback_tool = generate_write_fedback_tool(review_ledger)

    model = init_chat_model(f"azure_openai:{deployment}")
    subagents = [
        # TODO: the agents will move to yml files and be interpolated
        {
            "name": "structure-reviewer",
            "description": "Reviews document content for structure of sentences and paragraphs.",
            "system_prompt": (
                "You are a content quality specialist. Review and highlight where sentences and paragraphs are too long\n"
                "use the feedback_tool to write a list of suggestions for improvements.\n\n"
            ),
            "model": model,
            "tools": [feedback_tool],
        },
        {
            "name": "spelling-reviewer",
            "description": "Reviews document content in terms of spelling, grammar and punctuation.",
            "system_prompt": (
                "You are a content quality specialist. Review and highlight any errors in spelling, grammar, or punctuation.\n"
                "use the feedback_tool to write a list of errors to be corrected. Do not provide explanations or additional commentary.\n\n"
            ),
            "model": model,
            "tools": [feedback_tool],
        },
    ]
    subagents = [agent for agent in subagents if agent.get("enabled", True)]
    subagent_descriptions = "\n".join([f"- {agent['name']}: {agent['description']}" for agent in subagents])
    agent = create_deep_agent(
        model=model,
        system_prompt=(
            "You are a document review orchestrator coordinating specialized review agents.\n\n"
            f"Available subagents:\n{subagent_descriptions}\n"
            "Delegate review tasks to all appropriate subagents. They have file tools to read the document. "
            "Each subagent will provide its list of suggestions for the document "
            "You should aggregate all suggestions into a comprehensive list of improvements. "
            "Do not provide any additional commentary or explanations beyond the aggregated list. "
            "Do not explain about the process or make reference to any of the subagents. "
            "Do not produce a new version of the docuemnt. "
            "Do not offer to do anything else or make any suggestions about further actions. "
            "Present the final output as a clean, organised list of improvements in a structured format only."
        ),
        subagents=subagents,
    )

    with get_openai_callback() as usage:
        response = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": f"Review the text provided:\n{user_message}",
                    },
                ]
            }
        )

    logging.info("response: %s", json.dumps(response, indent=2, default=repr))
    logging.info("cost: $%.6f", usage.total_cost)
    return {"review_comments": review_ledger.review_comments}

def ada_orchestrator(user_message_dict: dict) -> dict:
    """Orchestrator that runs ada_main with the user message as the decision file path
    and returns the result as a dictionary.
    Args:
        user_message: The text content to review (will be used as the decision file).
    Returns:
        Dictionary containing the output from ada_main.
    """

    print("Starting ada_orchestrator with user message.")
    user_message= user_message_dict.get("input", "")
    print("User message received:", user_message)

    # Set up arguments for ada.main()
    original_argv = sys.argv
    try:
        # Configure sys.argv for ada.main() to parse
        sys.argv = [
            "ada",
            str(user_message),
            "--logging", "info",
        ]

        # Run ada.main() which will handle the document review
        ada_main()

        # Return the result as a dictionary
        return {"review_output": "Ada orchestrator completed successfully"}
    finally:
        # Restore original argv
        sys.argv = original_argv

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
    """Run the evaluation experiment using ada.main()."""

    return client.evaluate(
        ada_orchestrator,
        data="ada-orchestrator-dataset",
        evaluators=[correctness_evaluator],
        experiment_prefix="spellcheck-eval",
        max_concurrency=2,
    )

if __name__ == "__main__":
    client = Client()
    results = main(client)
