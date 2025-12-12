#!/usr/bin/env python3
"""DeepAgent orchestrator with document review subagents."""

import json
import logging
import sys
from argparse import SUPPRESS, ArgumentParser
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import yaml
from deepagents import create_deep_agent  # type: ignore[import-untyped]
from deepagents.backends import FilesystemBackend  # type: ignore[import-untyped]
from langchain.chat_models import init_chat_model
from langchain_community.callbacks import get_openai_callback
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from tiktoken import encoding_for_model, get_encoding

from ada.utility import deindent


def count_tokens(text: str, model: str) -> int:
    """Return count of tokens in text."""
    if ":" in model:
        model = model.split(":")[-1]
    try:
        encoding = encoding_for_model(model)
    except KeyError:
        # Use cl100k_base for unknown models as a reasonable approximation
        encoding = get_encoding("cl100k_base")
    return len(encoding.encode(text))


def read_text_pages(path: Path, kind: str | None = None) -> list[Document]:
    """Load document according to extension (or explicitly provied) kind and return pages."""
    loaders = {
        ".pdf": PyMuPDFLoader,
    }
    loader = loaders[kind or path.suffix.lower()]
    return loader(path).load()


def chunk_document(pages: list[Document], token_limit: int, chunk_overlap: int = 500) -> Iterator[str]:
    """Split document into chunks"""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=token_limit * 2,  # Tokens to characers (use lower estimate)
        chunk_overlap=chunk_overlap * 4,  # # Tokens to characers (use upper estimate)
        separators=["\n\n", "\n", ". ", " ", ""],
        keep_separator=True,
    )
    for page in pages:
        yield from splitter.split_text(page.page_content)


def upload(kind: str, path: Path, backend: FilesystemBackend, token_limit: int, model: str) -> str:
    """Upload the file of `kind` purpose at `path` to the `backend`, splitting into chunks if over `token_limit`.
    Return a descriptive manifest message about the upload result for use in prompts"""
    pages = read_text_pages(path)
    text = "\n".join(page.page_content for page in pages)
    token_count = count_tokens(text, model)
    logging.info("loaded: %s (%d pages, %d tokens)", path, len(pages), token_count)

    workspace = Path(kind)

    if token_count <= token_limit:
        # Expected case: content fits within token limit
        backend.write(str(workspace / "document.txt"), text)
        return f"The {kind} document is available at: {workspace / 'document.txt'}"

    # Content exceeds limit: split into chunks from constituent pages
    chunks = list(chunk_document(pages, token_limit))
    logging.warning(
        "%s document %s exceeds token limit (%d > %d), splitting into %d chunks",
        kind,
        path,
        token_count,
        token_limit,
        len(chunks),
    )
    for index, chunk in enumerate(chunks, 1):
        backend.write(str(workspace / f"chunk_{index:03d}.txt"), chunk)
    return (
        f"The {kind} document has been split into {len(chunks)} chunks at: {workspace}\n"
        f"Use `ls {workspace}` to see files, then `read_file` to read each chunk."
    )


def load_agents(
    defaults: dict[str, Any],
    interpolate: dict[str, Any],
    tools: Iterable[Callable] = (),
    directory: str = "agents",
) -> list[dict]:
    """Load agents from yml files in `directory` with `defaults` applied.
    The `interpolate` dictionary is used to interpolate any placeholders in the agent's system prompt.
    If `tools` is provided, they are added to each agent's `tools` list for any agent that has uses the tool
    Return a list of agents."""
    tools_map = {tool.__name__: tool for tool in tools}

    def load_agent(path: Path) -> dict | None:
        with open(path) as stream:
            agent = yaml.safe_load(stream)
        if agent.pop("disabled", False):
            return None
        agent["system_prompt"] = agent["system_prompt"].format(**interpolate)
        if "tools" in agent:
            agent["tools"] = [tools_map[tool] for tool in agent["tools"]]
        return {**defaults, **agent}

    return [
        agent
        for path
        in Path(directory).glob("*.yml")
        if (agent := load_agent(path))
    ]  # fmt: skip


def orchestrate(
    directory: str,
    decision: Path,
    deployment: str = "pins-llm-gpt-5-mini-ada-dev",
    model_name: str = "gpt-5-mini",
    token_limit: int = 400_000,
) -> str:
    """Run the DeepAgent orchestrator with document review subagents."""
    backend = FilesystemBackend(root_dir=directory, virtual_mode=True)
    inputs = (
        ("decision", decision),
        # TODO: assemble other inputs
    )
    manifest = "\n".join(upload(kind, path, backend, token_limit, model_name) for kind, path in inputs)
    model = init_chat_model(f"azure_openai:{deployment}")
    subagents = load_agents(defaults={"model": model}, interpolate={"manifest": manifest})
    subagent_descriptions = "\n".join([f"- {agent['name']}: {agent['description']}" for agent in subagents])
    prompt = deindent(f"""
        You are a document review orchestrator coordinating specialized review agents.
        Available subagents:
        {subagent_descriptions}
        Delegate review tasks to all appropriate subagents. They have file tools to read the document.
        Instruct each subagent to provide its output as a JSON list of suggestions.
        The following format should be used for each suggestion:
        {{
            "type": "<category of issue>",
            "location": "<line number range>",
            "problem": "<brief description of the issue>",
            "original": "<snippet of the original text>",
            "suggested": "<either the suggested corrected verison, or a description of the correction to make>"
        }}
        You should aggregate all suggestions into a comprehensive list of improvements.
        Do not provide any additional commentary or explanations beyond the aggregated list.
        Do not explain about the process or make reference to any of the subagents.
        Do not produce a new version of the docuemnt.
        Do not offer to do anything else or make any suggestions about further actions.
        Only use the subagents provided.
        Present the final output as a clean, organised list of improvements in a structured format only.
    """)
    logging.info("agent system prompt:\n%s", prompt)
    logging.info("input manifest:\n%s", manifest)
    agent = create_deep_agent(model=model, system_prompt=prompt, backend=backend, subagents=subagents)
    with get_openai_callback() as usage:
        response = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": f"Review the documents provided:\n{manifest}",
                    },
                ]
            }
        )

    logging.info("response: %s", json.dumps(response, indent=2, default=repr))
    logging.info("cost: $%.6f", usage.total_cost)

    return response["messages"][-1].content


def main():
    """Main entry point for the DeepAgent document review orchestrator."""
    parser = ArgumentParser(description="DeepAgent document review orchestrator", argument_default=SUPPRESS)
    parser.add_argument("-l", "--logging", type=str, default="info", help="Logging level.")
    parser.add_argument("-d", "--deployment", type=str, help="Azure deployment name.")
    parser.add_argument("decision", type=Path, help="Path to the decision file to review.")
    keywords = vars(parser.parse_args())

    logging.basicConfig(
        level=getattr(logging, keywords.pop("logging").upper()),
        format="%(asctime)s:%(levelname)s: %(message)s",
    )

    try:
        with TemporaryDirectory(prefix="ada_scratch_") as directory:
            return orchestrate(directory, keywords.pop("decision"), **keywords)
    except ValueError as exception:
        logging.error("%s", exception)
        return 1


if __name__ == "__main__":
    sys.exit(main())
