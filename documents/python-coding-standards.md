# Python Coding Standards
## TL;DR
* **Meaningful full-word identifiers** that are deterministic but concise; don't contract, remove, or use single letters
* **No global variables**; put constants in class or other scopes
* Use **object-functional** programming, preferring pure functions
* **Avoid shared state** if possible; pass it explicitly if necessary
* **Separate concerns** and use single responsibility
* Keep it **DRY**
* Use `ruff check --fix` and `ruff format` automatically with the project `pyproject.toml`

---

This document outlines the coding standards for Python development, ensuring code is **production quality** and adheres to best practices of **readability** and **maintainability**.
It is intended to be read in conjunction with the [general coding standards document](coding-standards.md).

---

## General Principles for Python

* **Python Version**: Use **Python >= 3.13**.
* **Style Guide**: Adhere to **PEP 8**, with clarifications and exceptions detailed in this document.
* **Linting**: Use **`ruff check`**, and all modules must pass **100% cleanly** using the appropriate `pyproject.toml` file.

---
## Identifier Naming

Identifiers must follow the semantic rules (Full English words, no abbreviations) outlined in the [General Coding Standards](coding-standards.md).

* **Style Guide**: Follow **PEP 8** casing conventions (e.g., `snake_case` for variables/functions, `PascalCase` for classes).
* **Initialisms**: As per the general standards, treat initialisms strictly. If a class name contains an initialism, capitalize all its letters. Note that we intentionally diverge from PEP 8 for initialisms.

### Python Examples


| Do | Don't |
| :--- | :--- |
| `except TypeError as exception:` | `except TypeError as e:` |
| `for item in items:` | `for i in items:` |
| `class HTTPServer:` | `class HttpServer:` |

---

## Variables, State, and Functional Paradigms

Adhere to the state management and functional principles (Prohibition of Global Variables, Pure Functions) outlined in the [General Coding Standards](coding-standards.md).

### Python Implementation Details

* **Immutability**: To enforce the general rule of immutability, use the following constructs instead of standard mutable objects as appropriate:
    * **`@dataclass(frozen=True)`**: Preferred for complex data structures.
    * **`NamedTuple`**: Acceptable for simple, tuple-like records.
* **Module-Level Exceptions**:
    * While global state is prohibited, module-level names are permitted if they bind to functions/classes that are **dynamically generated** (e.g., using `functools.partial` to create a curried version of a function).
* **Closures**:
    * Closures accessing the state of their enclosing scope are encouraged.
    * *Note*: Python closures capture variables by reference, not value. Be mindful of this "late binding" behavior when defining closures and lambdas inside loops.

---

## Files and Structure

* **Encoding**: Files must be encoded in **UTF-8** format and should not have an encoding declaration (which is deprecated in Python 3).
* **Executable Files**: Files intended for execution must:
    * Have the shebang: `#!/usr/bin/env python3`.
    * Have the **execute bit set** (`chmod +x`).
    * Contain an `if __name__ == "__main__"` main block and a `main` function (or similar).
    * Have all statements to be executed as part of running the program **inside functions**, not at the module level. This allows the module to be imported for testing and other purposes.

---

## Imports

* **Absolute Imports** are used in all cases, even when importing symbols from adjacent modules in the same package.
    * **Relative imports are prohibited**.
* Wildcard Imports are prohibited, except to import the entire contents of related sub-modules into a single presentation layer (e.g., in an `__init__.py` file).
* **Form**: The `from module import symbol` form is preferred in all cases, unless:
    * Names would be **ambiguous or confusing** (e.g., `import json`).
    * A **substantial number of items** will be imported, making it more readable to import just the module.

### Import Formatting
Imports are formatted and sorted according to black and isort styles (we use ruff to implement this):
* Imports are grouped in **standard, third-party, and local import order**, as per PEP 8.
    * Sections are separated by a blank line (but not annotated with a comment).
    * Within each section, **whole package imports** are grouped before **`from` imports**.
    * Import order is sorted alphabetically.

---
## Generators, Laziness, and Comprehensions

Modern Python is fundamentally designed around **lazy evaluation**. We prioritize processing data streams one item at a time rather than loading entire datasets into memory.

### Generators and Lazy Evaluation

Generators are the standard mechanism for implementing lazy evaluation. They allow functions to pause execution and yield a value, maintaining state for when they are resumed.

* **Memory Efficiency**: Unlike lists, generators do not store all values in memory. They generate values on the fly, making them essential for processing large files, infinite sequences, or database streams.
* **Pipelining**: Generators allow for the creation of processing pipelines (similar to Unix pipes) where data flows through a series of transformations without creating expensive intermediate collections.
* **`yield`**: Use the `yield` keyword to produce a value and suspend the function's execution.
* **`yield from`**: Use `yield from` to delegate iteration to another iterator or generator. This promotes composition, allowing you to refactor complex generators into smaller, readable sub-generators.

**Python 3 Alignment**: Most standard library functions (e.g., `range`, `map`, `filter`, `zip`) return generators, not lists. Your code should mirror this behavior: return a generator, and let the consumer decide if they need to materialize it into a list.

### Comprehensions over Iterative Construction

When building data structures, **comprehensions** are strictly preferred over instantiating an empty container and extending it via a loop.

| Rule | Rationale |
| :--- | :--- |
| **Use Comprehensions** | List, Dictionary, and Set comprehensions are declarative, more readable, and significantly faster than explicit `for` loops with `.append()` calls (as the loop overhead is handled in C). |
| **Generator Expressions** | Use generator expressions `(item.value for item in items)` instead of list comprehensions `[item.value for item in items]` if the result is large and will only be iterated over once. |

**Example:**

```python
# Do:
lookup = {user.id: user for user in users}
names = [user.name for user in users if user.active]
better = (user.name for user in users if user.active)  # Generator expression

# Don't:
names = []
for user in users:
    if user.active:
        names.append(user.name)
```
### Exception: DataFrames and Vectorization

While generators and comprehensions are preferred for general Python logic, **Pandas DataFrames** (or PyArrow or NumPy arrays) are the preferred when:
* Vectorized operations provided by these libraries offer significant performance benefits over Python-level iteration.
* The problem domain requires columnar analysis, matrix operations, or complex statistical transformations.
* Downstream systems or libraries specifically consume these.
---
## String Formatting

* **F-Strings**: For simple formatting and interpolation, **f-strings** (formatted string literals) are the preferred method.
    * **Rationale**: F-strings are significantly more readable, concise, and performant than the legacy `%` operator or the `.format()` method.
    * **Exception**: For logging, do not use f-strings; use the logging module’s lazy formatting.

**Example:**

```python
# Do:
message = f"Hello, {user.name}. Your score is {score}."

# Don't:
message = "Hello, %s. Your score is %s." % (user.name, score)
message = "Hello, {}. Your score is {}.".format(user.name, score)
```
---
## Logging and Printing

* **Standard Logging**: The standard Python **`logging`** module must be used for all diagnostic and informational messages.
* **Lazy Formatting**: Log messages must be constructed using the logger's **lazy formatting** (i.e., with parameters passed and left for the logger to format).

* **Configuration**: The logger should be configured **only by the client program’s main**.
    * Log messages must **not** be sent at module import time.
* **`print`**: The `print` function is **prohibited** for outputting diagnostic or informational messages (including for testing and debugging); use the logger instead.
    * `print` should only be used for the **actual intended machine output** from a process (e.g., JSON messages streamed out to another process or a file). In such cases, printing should be handled by the program’s `main` or a similarly top-level/controller function.

```python
# Do:
logger.debug("Processing request for %s with ID %d", username, user_id)

# Don't:
logger.debug(f"Processing request for {username} with ID {user_id}")
logger.debug("Processing request for %s with ID %d" % (username, user_id))
logger.debug("Processing request for " + username + " with ID " + str(user_id))
print(f"Processing request for {username} with ID {user_id}")

```
---
## Exception Handling

* **Specificity**: Always catch the most specific exception possible.
    * **Prohibited**: `except:` (bare except) and `except Exception:` are prohibited. Bare except catches system-exiting events (like `SystemExit`) and mask syntax errors.
    * **Allowed**: Catching `Exception` is only acceptable in top level contexts, such as `main` (or equivalent thread/process entry point) to log a crash before exiting.
* **Naming**: While using `exception` as the variable name is encouraged (e.g., `except ValueError as exception`)
* **Chaining**: When raising a new exception from an `except` block, always use `from` to preserve the stack trace (e.g., `raise NewError from exception`).
* **Flow Control**: Do not use exceptions for normal flow control (e.g., do not use `try/except` to check if a key exists in a dictionary; use `.get()` or `in` instead).
* **Logging with Stack Trace**: If stack trace is desired, prefer `logging.exception` to log at `error` level with the stack trace automatically included.

```python
# Do:
try:
    data = fetch_data()
except ConnectionError as exception:
    logger.error("Connection failed: %s", exception)
    raise DataFetchError("Could not retrieve data") from exception

# Don't:
try:
    process()
except:
    pass
```
---
## Resource Management

* **Context Managers**: Use the `with` statement for any object that manages resources (files, sockets, database connections, locks). This ensures cleanup happens even if exceptions occur.
* **`contextlib`**: Use `contextlib.closing` for objects that provide a `close()` method but do not support the context manager protocol natively.

```python
# Do:
with open("file.txt") as stream:
    data = stream.read()

# Don't:
stream = open("file.txt")
data = stream.read()
stream.close() # Might not execute if read() fails
```

---

## Boolean Evaluations

* **Implicit False**: Use implicit false for empty sequences (lists, dicts, strings).
    * **Do**: `if not users:`
    * **Don't**: `if len(users) == 0:` or `if users == []:`
* **Boolean Values**: Do not compare boolean values to True/False.
    * **Do**: `if is_valid:`
    * **Don't**: `if is_valid == True:`
* **None Checks**: Comparisons with `None` must always use `is None` or `is not None`, never `== None`.
    * **Rationale**: `None` is a singleton, and checking identity is idiomatic and faster.

---

## Modern Library Preferences

* **Path Handling**: Use **`pathlib`** for all file path manipulations.
    * **Prohibited**: `os.path.join`, `os.path.exists`, etc.
    * **Rationale**: `pathlib` provides an object-oriented interface that handles cross-platform separators automatically.
* **Timezones**: All naive datetime objects are prohibited. Use `datetime.timezone.utc` for all internal time representations. Convert to local time only at the user interface boundary.
* **Subprocesses**: Use the `subprocess` module (specifically `run`) instead of `os.system`.

```python
# Do:
from pathlib import Path
path = Path("data") / "raw" / "file.csv"

# Don't:
path = os.path.join("data", "raw", "file.csv")
```
---

## Formatting (PEP 8 Clarifications)

PEP 8 formatting is followed, with the following mandatory choices and exception:

* **Indentation**: Use **4 spaces** per indentation level. **Tabs are prohibited**.
* **Trailing Comma**: A **trailing comma** is always used on the last line of any multi-line list, dict, set, tuple, or similar construct.
* **Closing Delimiter Alignment**: The closing brace/bracket/parenthesis on multi-line constructs must be lined up **under the first character of the line that starts the multi-line construct**.
* **Argument/Item Consistency**: If one list or argument item is made multi-line, **all items must be made multi-line** (each on a separate line).
* **Quotes**: double quotes (" and """) are preferred over single quotes (' and ''').
* **Line Length**: Aim for 120 characters per line but break lines for overall readability. Black will break lines at 120 characters, but it is acceptable to exceed this for the sake of readability and override Black.

### Black and Ruff
* The above rules match the Black style (when set to 120 characters per line, but without allowing for longer lines).
* We follow the Black code style and isort import ordering, implemented via Ruff (`ruff check` and `ruff format`) automatically in either our IDE on-write or as a pre-commit hook (or both) on all code before it is committed.
* The formatter will often single-line blocks that are better formatted for readability as multiple lines (such as complex list comprehensions). For this reason it is recommend to use `# fmt: off` and `# fmt: on` to disable formatting for such blocks.
* It is acceptable to add a `# fmt: off` comment to the top of a file (or any scope) containing many such blocks, if you prefer to accept responsibility for formatting according to the above rules manually.

```python
# Examples
things = [
    1,
    2,
    3,
]

dictionary = {
    "this": "that",
    "these": "those",
}

result = some_function_that_takes_arguments(
    some_quite_long_identifier,
    something,
    shorter,
)

def method_with_many_arguments(
    self,
    name,
    some_very_long_argument_name,
    another_very_long_argument_name,
    *arguments,
    **keywords,
):
    pass
```
---

## Type Hints and Docstrings

### Documentation, Comments, and Type Hints

* **Docstring Format**: All docstrings should use the **reStructuredText** format (or Google format if complex argument descriptions are needed) to maintain consistency.
* **Comments**:
  * "Why", not "How": Comments should explain **why** a piece of code exists or the business logic behind a decision. The code itself should explain **how** it works via descriptive function and variable names.
  * Necessary: Comments should only be added when necessary. Do not add comments to explain what is entirely obvious from reading the code.
  * Maintenance: Comments must be kept up-to-date. An incorrect comment is significantly worse than no comment.
  * Sections: Comments delineating related sections of a function are acceptable; but, if this is necessary, thought should be given to whether the function is too long.
* **TODOs**: Use `TODO(username):` format for temporary notes. These must be resolved before merging to main branch(es).

### Type Hints

* **Not Compulsory**: Type hints are **not compulsory**.
* **Consistency**: If any argument of a function has a type hint, **all other arguments and the return type must also have a type hint**.
* **Standards**: Where included, type hints must comply with **`mypy`** standards.
* **Docstring Integration**: If a docstring is necessary to explain functionality, type hints should be included, and the docstring should **not** list arguments and return types.
    * For complicated cases needing in-depth written descriptions of arguments, follow the basic structure detailed in the **Google Python Style Guide**.
* **Type Aliases**: It is preferable **not to use `TypeAlias`** if another viable solution exists.
    * If types are complicated enough to require an alias, first consider refactoring to use a more suitable data structure, such as a **`dataclass`**.

### Doctests

* **Usage**: When a function requires an **illustrative example** in a docstring, a **doctest** should be used. This helps flag when documentation is outdated.
    * *Note: For simple functions, descriptive naming should make an example unnecessary*.
* **Simplicity**: Doctests must be kept as **short and simple as possible** to be easy to read.
* **Purpose**: Doctests serve as **documentation**; they must not attempt to capture edge cases or replace unit tests.

---

## Testing Structure

* **Framework**: **`pytest`** is the standard testing framework.
* **Location**: Tests should be located in a `tests/` directory at the root of the project, mirroring the source code structure.
* **Fixtures**: Use `pytest` fixtures for setup/teardown rather than `setUp`/`tearDown` methods.
* **Coverage**: While 100% statement coverage is the target, valid assertions on edge cases are more important than raw percentage metrics.

---

## Package and Dependency Management

We prioritize **reproducibility**, **isolation**, and **speed** in dependency management.

* **Standard Tool**: **`uv`** is the mandated tool for project management, package resolution, and virtual environment handling.
* **Configuration**: All dependencies must be declared in the standard **`pyproject.toml`** file.
    * *Legacy formats like `requirements.txt` are deprecated.*
* **Lock Files**:
    * A **`uv.lock`** file must be committed to source control.
    * This ensures all developers and CI/CD pipelines run the exact same dependency graph (including hashes).
    * **Do not** manually edit the lock file; update it via `uv lock` or `uv add`.

### Dependency Grouping

Dependencies must be segregated by purpose to keep production images lightweight.

* **Project Dependencies**: Core libraries required for the application to run (e.g., `fastapi`, `pydantic`). Added via `uv add <package>`.
* **Development Dependencies**: Tools required for linting, formatting, and local development (e.g., `ruff`). Added via `uv add --dev <package>`.
* **Test Dependencies**: Libraries required strictly for testing (e.g., `pytest`). Added to a specific group: `uv add --group test <package>`.
