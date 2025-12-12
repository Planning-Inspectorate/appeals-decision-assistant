"""Dataset management for LangSmith evaluations."""

import logging
import sys
from pathlib import Path

import yaml
from langsmith import Client


def load_dataset_config() -> dict:
    """Load dataset configuration from YAML file."""
    dataset_yml_path = Path(__file__).parent / "dataset.yml"
    logging.info("Loading dataset configuration from %s", dataset_yml_path)
    return yaml.safe_load(dataset_yml_path.read_text())


def get_dataset_name() -> str:
    """Get the dataset name from the configuration."""
    config = load_dataset_config()
    return config.get("name", "test-dataset")


def get_or_create_dataset(client: Client, dataset_name: str, description: str):
    """Get existing dataset or create a new one."""
    logging.info("Attempting to list existing datasets from LangSmith client")
    datasets = list(client.list_datasets())
    logging.info("Listed %d datasets", len(datasets))

    for ds in datasets:
        if ds.name == dataset_name:
            logging.info("Found existing dataset '%s' (%s).", dataset_name, getattr(ds, "name", None))
            return ds

    logging.info("Creating dataset '%s' in LangSmith", dataset_name)
    dataset = client.create_dataset(dataset_name=dataset_name, description=description)
    logging.info("Created dataset '%s' (%s).", dataset_name, getattr(dataset, "name", None))
    return dataset


def load_examples_from_yaml() -> list:
    """Load examples from the dataset YAML configuration file."""
    config = load_dataset_config()
    examples = config.get("examples", [])
    logging.info("Loaded %d example(s) from YAML file", len(examples))
    return examples


def create_missing_examples(client: Client, dataset_name: str, examples: list, existing_examples: list) -> int:
    """Create examples that don't already exist in the dataset, and update outputs if they differ."""
    examples_to_create = []
    examples_to_update = []

    for example in examples:
        # Find matching example by inputs
        matching_example = None
        for ex in existing_examples:
            if ex.inputs == example["inputs"]:
                matching_example = ex
                break

        if matching_example is None:
            # Example doesn't exist, add to create list
            examples_to_create.append(example)
        elif matching_example.outputs != example.get("outputs"):
            # Example exists, check if outputs match
            examples_to_update.append((matching_example, example))
            logging.info("Example with inputs %s has differing outputs, will update", example["inputs"])

    if examples_to_create:
        client.create_examples(dataset_name=dataset_name, examples=examples_to_create)
        logging.info("Successfully created %d example(s) in dataset %s", len(examples_to_create), dataset_name)
    else:
        logging.info("All examples already exist in dataset %s", dataset_name)

    if examples_to_update:
        for existing_ex, example in examples_to_update:
            client.update_example(
                example_id=getattr(existing_ex, "id", None),
                outputs=example.get("outputs")
            )
        logging.info("Successfully updated %d example(s) in dataset %s", len(examples_to_update), dataset_name)

    return len(examples_to_create)


def handle_extra_examples(client: Client, existing_examples: list, examples: list) -> int:
    """Handle examples in dataset that are not in the examples list."""
    examples_to_delete = []
    for ex in existing_examples:
        example_in_list = any(
            ex.inputs == example["inputs"] for example in examples
        )
        if not example_in_list:
            examples_to_delete.append(ex)

    if not examples_to_delete:
        return 0

    logging.warning("Found %d example(s) in dataset not in the examples list", len(examples_to_delete))
    for ex in examples_to_delete:
        logging.warning("  - Example id=%s with inputs=%s", getattr(ex, "id", None), ex.inputs)

    user_response = input(f"Delete {len(examples_to_delete)} example(s) not in the examples list? (yes/no): ").strip().lower()
    if user_response == "yes":
        for ex in examples_to_delete:
            client.delete_example(example_id=getattr(ex, "id", None))
        logging.info("Deleted %d example(s) from dataset", len(examples_to_delete))
        return len(examples_to_delete)
    logging.info("User chose not to delete extra examples")
    return 0


def create_sample_dataset(client: Client):
    """Create a sample dataset in LangSmith for spelling correction."""
    # Ensure logging outputs to console for this operation
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout)

    # Load configuration from YAML
    config = load_dataset_config()
    dataset_name = config.get("name", "test-dataset")
    description = config.get("description", "Dataset for Ada orchestrator evaluations.")

    logging.info("create_sample_dataset: starting (dataset_name=%s)", dataset_name)

    # Get or create dataset
    dataset = get_or_create_dataset(client, dataset_name, description)

    # Load examples from YAML
    examples = load_examples_from_yaml()

    logging.info("Processing %d example(s) in dataset %s", len(examples), getattr(dataset, "name", None))
    try:
        # Get existing examples in the dataset
        existing_examples = list(client.list_examples(dataset_name=dataset.name))
        logging.info("Found %d existing example(s) in dataset", len(existing_examples))

        # Create missing examples
        create_missing_examples(client, dataset.name, examples, existing_examples)

        # Handle extra examples
        handle_extra_examples(client, existing_examples, examples)

    except (ValueError, KeyError, TypeError) as e:
        logging.error("Failed to process examples - invalid data format: %s", e)
    except OSError as e:
        logging.error("Failed to access LangSmith API: %s", e)
    except RuntimeError as e:
        logging.error("Failed to process examples in dataset %s: %s", getattr(dataset, "name", None), e)

