#!/usr/bin/env python3
"""Weather assistant LangChain sample."""

import json
import logging
import sys
from argparse import SUPPRESS, ArgumentParser

import requests
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_community.callbacks import get_openai_callback
from langchain_openai import AzureChatOpenAI


@tool(description="Get the weather in a location.")
def get_weather(location: str) -> str:
    """Get the weather in a location."""
    response = requests.get(f"https://wttr.in/{location}?format=j1", timeout=120)
    return response.json()["current_condition"]


def weather(location: str, deployment="pins-llm-gpt-5-mini-ada-dev"):
    """Run the weather assistant and return the response."""
    agent = create_agent(
        model=AzureChatOpenAI(deployment_name=deployment),
        tools=[get_weather],
        system_prompt="You are a helpful weather assistant who always cracks jokes and is humorous while remaining professional.",
    )

    with get_openai_callback() as usage:
        response = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": f"What is the weather in {location}?",
                    }
                ]
            }
        )
    logging.info("response: %s", json.dumps(response, indent=2, default=repr))
    logging.info("cost: $%.6f", usage.total_cost)
    return response["messages"][-1].content


def main():
    parser = ArgumentParser(description="", argument_default=SUPPRESS)
    parser.add_argument("-l", "--logging", type=str, default="info", help="Logging level.")
    parser.add_argument("-d", "--deployment", type=str, help="Deployment name.")
    parser.add_argument("location", nargs="*", help="Location.")
    keywords = vars(parser.parse_args())

    logging.basicConfig(
        level=getattr(logging, keywords.pop("logging").upper()),
        format="%(asctime)s:%(levelname)s: %(message)s",
    )

    print(weather(" ".join(keywords.pop("location")), **keywords))


if __name__ == "__main__":
    sys.exit(main())
