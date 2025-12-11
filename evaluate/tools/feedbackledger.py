"""Feedback ledger and tools for experiment evaluations."""

import logging
from dataclasses import dataclass

from langchain.tools import tool


@dataclass
class FeedbackLedger:
    """A simple ledger to store feedback during evaluation."""
    review_comments: list[str]


def generate_write_feedback_tool(ledger: FeedbackLedger):
    """Generate a tool to write feedback during evaluation."""
    @tool
    def write_feedback(feedback: list[str]):
        """A tool to write feedback during evaluation. Review comments should be a list of strings. Each comment should quote the relevant section and provide a suggested correction."""
        logging.info("Review Comments Recorded: %s", feedback)
        for comment in feedback:
            ledger.review_comments.append(comment)
        return f"Feedback for {feedback} recorded."
    return write_feedback
