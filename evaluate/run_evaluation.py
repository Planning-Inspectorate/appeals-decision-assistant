#!/usr/bin/env python3
"""Sample evaluation script using Langsmith and OpenEvals"""

import logging
import sys

from langsmith import Client
from langsmith.evaluation._runner import ComparativeExperimentResults
from langsmith.schemas import ExperimentResults

from ada.main import main as ada_main
from evaluate.dataset import create_sample_dataset, get_dataset_name
from evaluate.evaluators import correctness_evaluator

# Configure logging for the module
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)

def ada_orchestrator(user_message_dict: dict) -> dict:
    """Orchestrator that runs ada_main with the user message as the decision file path
    and returns the result as a dictionary.
    Args:
        user_message: The text content to review (will be used as the decision file).
    Returns:
        Dictionary containing the output from ada_main.
    """

    logging.info("Starting ada_orchestrator with user message.")
    user_message= user_message_dict.get("path", "")
    logging.info("User message received: %s", user_message)

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
        return {"review_output": ada_main()}

    finally:
        # Restore original argv
        sys.argv = original_argv

def main(client: Client) -> ExperimentResults | ComparativeExperimentResults:
    """Run the evaluation experiment using ada.main()."""
    dataset_name = get_dataset_name()
    print("Using dataset:", dataset_name)

    return client.evaluate(
        ada_orchestrator,
        data=dataset_name,
        evaluators=[correctness_evaluator],
        experiment_prefix="spellcheck-eval",
        max_concurrency=2,
    )

if __name__ == "__main__":
    client = Client()
    create_sample_dataset(client)
    results = main(client)
