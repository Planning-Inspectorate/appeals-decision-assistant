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
from spire.pdf import *
from spire.pdf.common import *
from spire.pdf.annotations.PdfTextMarkupAnnotation import PdfTextMarkupAnnotation
from spire.pdf import PdfTextExtractor, PdfTextExtractOptions
import re

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


def extract_line_numbers(text: str) -> list[int]:
    """Extract line numbers from comment text like 'Lines 9-11' or 'line 53'."""
    line_numbers = []
    # Match patterns like "Lines 9-11", "line 53", "Lines 106-108"
    patterns = [
        r'[Ll]ines?\s+(\d+)-(\d+)',  # Lines 9-11
        r'[Ll]ines?\s+(\d+)',          # line 53
    ]

    for pattern in patterns:
        matches = re.finditer(pattern, text)
        for match in matches:
            if len(match.groups()) == 2:
                start, end = int(match.group(1)), int(match.group(2))
                line_numbers.extend(range(start, end + 1))
            else:
                line_numbers.append(int(match.group(1)))

    return sorted(set(line_numbers))


def add_comments_to_pdf(pdf_path: Path, comments_text: str, output_path: Path) -> None:
    """Add LLM improvement suggestions as highlight annotations on the PDF."""
    doc = PdfDocument()
    doc.LoadFromFile(str(pdf_path))

    all_text = ""
    for page_idx in range(doc.Pages.Count):
        page = doc.Pages[page_idx]
        extractor = PdfTextExtractor(page)
        options = PdfTextExtractOptions()
        all_text += extractor.ExtractText(options) + "\n"

    text_lines = all_text.split("\n")

    comment_sections = []
    current_section = []

    for line in comments_text.split("\n"):
        line = line.strip()
        if line and (line[0].isdigit() or line.startswith("Location:")):
            if current_section:
                comment_sections.append("\n".join(current_section))
            current_section = [line]
        elif current_section:
            current_section.append(line)

    if current_section:
        comment_sections.append("\n".join(current_section))

    annotations_added = 0
    for comment in comment_sections[:50]:
        line_numbers = extract_line_numbers(comment)

        if not line_numbers:
            continue

        target_lines = []
        for line_num in line_numbers:
            if 1 <= line_num <= len(text_lines):
                target_lines.append(text_lines[line_num - 1])

        if not target_lines:
            continue

        search_text = target_lines[0].strip()
        if not search_text or len(search_text) < 3:
            continue

        for page_idx in range(doc.Pages.Count):
            page = doc.Pages[page_idx]

            finder = PdfTextFinder(page)
            finder.Options.Parameter = TextFindParameter.IgnoreCase

            fragments = finder.Find(search_text)

            if fragments and len(fragments) > 0:
                text_fragment = fragments[0]

                for i in range(len(text_fragment.Bounds)):
                    rect = text_fragment.Bounds[i]

                    annotation = PdfTextMarkupAnnotation("ADA", comment[:500] if len(comment) > 500 else comment, rect)
                    annotation.TextMarkupAnnotationType = PdfTextMarkupAnnotationType.Highlight
                    annotation.TextMarkupColor = PdfRGBColor(Color.get_Yellow())

                    page.AnnotationsWidget.Add(annotation)

                annotations_added += 1
                break

    doc.SaveToFile(str(output_path))
    doc.Close()

    logging.info(f"Added {annotations_added} highlight annotations to PDF")


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
        decision_path = keywords.pop("decision")
        with TemporaryDirectory(prefix="ada_scratch_") as directory:
            improvements = orchestrate(directory, decision_path, **keywords)
            print(improvements)

            output_path = decision_path.parent / f"{decision_path.stem}_reviewed{decision_path.suffix}"
            add_comments_to_pdf(decision_path, improvements, output_path)
            logging.info("Annotated PDF saved to: %s", output_path)

        return 0
    except ValueError as exception:
        logging.error("%s", exception)
        return 1


if __name__ == "__main__":
    sys.exit(main())
