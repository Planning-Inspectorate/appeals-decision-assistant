#!/usr/bin/env python3
"""DeepAgent orchestrator with document review subagents."""

import json
import logging
import sys
from argparse import SUPPRESS, ArgumentParser
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory

from deepagents import create_deep_agent  # type: ignore[import-untyped]
from deepagents.backends import FilesystemBackend  # type: ignore[import-untyped]
from langchain.chat_models import init_chat_model
from langchain_community.callbacks import get_openai_callback
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from tiktoken import encoding_for_model, get_encoding


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
    logging.info("input manifest:\n%s", manifest)

    model = init_chat_model(f"azure_openai:{deployment}")
    subagents = [
        # TODO: the agents will move to yml files and be interpolated
        {
            "name": "structure-reviewer",
            "description": "Reviews document content for structure of sentences and paragraphs.",
            "system_prompt": (
                "You are a content quality specialist. Review and highlight where sentences and paragraphs are too long\n\n"
                f"{manifest}"
            ),
            "model": model,
        },
        {
            "name": "spelling-reviewer",
            "description": "Reviews document content in terms of spelling, grammar and punctuation.",
            "system_prompt": (
                "You are a content quality specialist. Review and highlight any errors in spelling, grammar, or punctuation.\n"
                "Output only a list of errors to be corrected. Do not provide explanations or additional commentary.\n\n"
                f"{manifest}"
            ),
            "model": model,
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
        backend=backend,
        subagents=subagents,
    )

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
    """Main entry point for the DeepAgent PDF review example."""
    parser = ArgumentParser(description="DeepAgent PDF document review orchestrator", argument_default=SUPPRESS)
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
            print(orchestrate(directory, keywords.pop("decision"), **keywords))
    except ValueError as exception:
        logging.error("%s", exception)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
