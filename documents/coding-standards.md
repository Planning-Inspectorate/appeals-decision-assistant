# General Coding Standards

This document outlines general language-agnostic coding standards for development, ensuring code is **production quality** and adheres to best practices of **readability** and **maintainability**.
It is intended to be read in conjunction with a language-specific coding standards document.

---

## General Principles

* All code must be of production quality.
* **Linting**: Use the linting tool specific to your language and all modules must pass **100% cleanly** using appropriate project configuration files.
* **Static Analysis**: Use **SonarQube**, and all software should pass with **0 unresolved issues**.

---

## Identifier Naming

All identifier names must be clear and descriptive. Use only **whole English dictionary words** without contraction or removing letters.

### Rationale: The Case for Full-Word Identifiers

Code is read orders of magnitude more often than it is written. Therefore, we optimize for readability, predictability, and cognitive ease, not for write-time speed or brevity.

#### 1. Code as Documentation
The code itself is the primary source of truth. Comments rot; they drift out of sync with the logic they describe. Explicit, full-word identifiers make the code self-documenting.

* Ambiguity is a Bug: An identifier like `res` is ambiguous: it could mean "response", "result", "resource", or "resolution". `response` is unambiguous. `mod` could be "modulo", "module", "model", "modifier", or "mode"; `module` is absolute.

* Zero-Latency Comprehension: When a developer reads `connection_parameters`, their brain processes the concept immediately. When they read `conn_params`, the brain performs a micro-context switch to "decrypt" the abbreviation. Over thousands of lines of code, this cognitive load accumulates, leading to fatigue and oversight.

#### 2. Determinism and Predictability over Memory
Abbreviating words requires arbitrary decisions about which letters to remove. This forces developers to memorize the "local dialect" of the codebase rather than just knowing English.

* The Guessing Game: An identifier like `cfg` is easy enough to read, but impossible to predict. When writing code, a developer must pause and ask: "Did we agree on `cfg`, `conf`, `cnfg`, or `config`?" The word `configuration` requires no memorization and no searching the codebase. It is the only correct spelling in the dictionary. We type it once, correctly, and let auto-completion handle the rest.

* Searchability: Full words make "grepping" the codebase effective. Searching for `user` yields relevant results. Searching for `u` yields noise.

#### 3. The "Keystroke" Fallacy
The historical argument for abbreviation - saving keystrokes and screen real estate - is obsolete.

Intelligent Tooling: Modern IDEs and text editors provide robust tab completion and IntelliSense. Typing con and hitting <Tab> instantly expands to connection_parameters. There is no "write-time" penalty for long names.

Screen Real Estate: We work on high-resolution monitors, not 80-column terminals. Breaking lines for readability is free; misunderstanding a contracted variable name is expensive.

#### Conclusion
We do not encrypt our code; we use English. We prefer company_description over compny_desc. We prefer predictable clarity over brevity.

| Rule | Principle/Rationale | Example |
| :--- | :--- | :--- |
| **Full Words** | Names must be composed of only **whole English dictionary words** or well-known initialisms (e.g., `api`, `jwt`, `tcp`). **Do not use abbreviations** by contraction or removing letters. | `connection_parameters` over `conn_params`; `socket` over `sock` |
| **Single Letters** | Do not use single-letter variables. | `text` over `s`; `value` over `x`; `index` over `i` |
| **Standard Exceptions** | Standard single-letter conventions are acceptable only in specific, well-established contexts. | Geometric coordinates (`x`, `y`, `z`); `_` throwaway value; Matrix enumeration (`i`, `j`, `k`) or numeric indices clearly maths-like contexts |
| **Brevity Preference** | Single-word names are preferred over multi-word names, provided the single word is sufficiently descriptive and unambiguous in the context. | `user` over `user_profile`; `address` over `ip_address`. |
| **Initialisms** | When using `CamelCase` names, capitalize **all** or **none** of the letters of an initialism. | `HTTPServer`, `tcpReceiver`. |
| **Lazy Initialization and Scope Limitation** | Variables are initialized (if necessary) as late as possible and in the narrowest scope possible. | |

---

## Variables, State, and Functional Paradigms

The management of state is the single most critical factor in ensuring code is predictable, testable, and maintainable. **Global variables are prohibited**, and a shift toward **Object-Functional Programming** is strongly encouraged.

### Global Variables

Global variables (including "module-only" variables) make program state unpredictable, create hidden couplings, and are the primary cause of concurrency pitfalls.

| Rule | Rationale |
| :--- | :--- |
| **Strictly Avoid Global Variables** | Global state creates hidden dependencies that make refactoring much harder and debugging painful. It breaks the isolation required for reliable unit testing. |
| **Prefer Scoping Constants** | Even "constants" are best placed within a suitable class scope or configuration object to prevent namespace pollution and allow for easier mocking during tests. |
| **Pass State Explicitly** | State must always be passed explicitly between functions and classes as arguments. Functions should rely only on their inputs, not on the environment. |

**Clarifications on State:**

* Methods can, of course, access the state of their object instance but the developer should be conscious of what this means in terms of mutability and object-orientation vs functional programming.
* Closures accessing the state of their enclosing scope are allowed and encouraged as an essential aspect of functional programming.

**Exceptions to the Global Rule:**
* Names at the module level that exist **only to alias** another function or class.
* Names binding to functions or classes that are **dynamically generated** (e.g., using currying to create a partial application of another function).
* Names at the global level that are unavoidable when using particular frameworks or libraries (e.g. creating the `app` for the decorator in a Flask or FastAPI application).

### Functional Principles and Pure Algorithms

Wherever possible, write algorithms as **pure functions**. A pure function has two key properties:
* **Deterministic:** Given the same input, it always returns the same output.
* **No Side Effects:** It does not modify its arguments, global variables, or external systems (I/O, Database).

**Benefits of Pure Functions:**
* **Testability:** Unit tests become trivial; you only need to assert `function(input) == expected` without setting up complex mocks or tear-down procedures.
* **Debuggability:** Errors are localized to the function logic, not the state of the system at a specific point in time.
* **Concurrency:** Pure functions are inherently thread-safe and process-safe because they do not share mutable state.

* **Isolate Side Effects**: Push "impure" code (database writes, API calls) to the **boundaries** of your application (e.g., the Controller or `main` execution block). Keep the core logic pure.

| Concept | Guideline |
| :--- | :--- |
| **Immutability** | Treat data objects as immutable where practical. Instead of modifying an object in place (`thing.value = 5`), return a new instance with the updated value. Use the appropriate language-specific immutable constructs (e.g., frozen data classes, readonly interfaces or records/tuples). |
| **Composition** | Build complex logic by composing small, reusable pure functions rather than writing large, monolithic class methods that rely on instance state. |
| **Stateless Logic** | Methods inside a class should ideally operate on their arguments and the instance properties without *mutating* the instance itself. |

### Exceptions: Acceptable Mutability
Most classes should be immutable by default, but some are *naturally stateful*. Mutability is appropriate when it reflects meaningful, real-world state changes and is isolated and explicit:
* Real Stateful Objects: Classes that model evolving state may mutate:
    * caches
    * sessions
    * workflows / state machines
    * request / response builders
* Resource Wrappers: Objects that manage external resources that must reflect real state:
    * database connections
    * sockets
    * file handles
* Performance-Critical Code: Mutation is acceptable when copying would be unreasonably expensive.
* Accumulators and Builders: Objects explicitly designed to gather or assemble data over time may mutate internal collections.

---

## Git and Version Control
* **Source Control**: **Git** is used to track all source code.
* Commits are regularly made and pushed to the appropriate repository.
* If reformatting or reordering of code is required, commit these changes separately before making logic changes.
* Similarly, if refactoring is required, commit these changes separately from reformatting or logic changes.
* Always commit with a clear, concise, and descriptive message.
* Commit granularly, keeping each commit focused on a single feature or bug fix.
* Similarly, PRs should be granular and contain commits for review on a focused set of related changes. Break work in multiple PRs if necessary to avoid super PRs, which are hard to review and merge effectively.

---

## Engineering Principles

While beyond the scope of a coding standards guide, the following principles should be adhered to:

* **DRY**: All code must follow **Don't Repeat Yourself (DRY) principles**.
* **SOLID**: Object-oriented code follows **SOLID principles**.
