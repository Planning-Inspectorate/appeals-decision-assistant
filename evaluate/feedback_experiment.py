"""Feedback experiment using deep agents for document review."""

import json
import logging

from deepagents import create_deep_agent  # type: ignore[import-untyped]
from langchain.chat_models import init_chat_model
from langchain_community.callbacks import get_openai_callback

from evaluate.tools.feedbackledger import FeedbackLedger, generate_write_feedback_tool


def sample_orchestrator(user_message: str) -> dict:
    """This defines a sample application logic. In practice it will be replaced with our actual decision agent. Dataset inputs are handed as function inputs."""
    deployment = "pins-llm-gpt-5-mini-ada-dev"

    review_ledger = FeedbackLedger(review_comments=[])

    feedback_tool = generate_write_feedback_tool(review_ledger)

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
