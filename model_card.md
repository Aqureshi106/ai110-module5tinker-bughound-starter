# BugHound Mini Model Card (Reflection)

Fill this out after you run BugHound in **both** modes (Heuristic and Gemini).

---

## 1) What is this system?

**Name:** BugHound  
**Purpose:** Analyze a Python snippet, propose a fix, and run reliability checks before suggesting whether the fix should be auto-applied.

**Intended users:** Students learning agentic workflows, lightweight code review, and AI reliability concepts.

---

## 2) How does it work?

BugHound runs a short agentic loop: it plans a quick scan, analyzes the code for issues, acts by proposing a fix, tests the result with a risk assessor, and then reflects on whether the fix is safe enough to auto-apply.

In heuristic mode, analysis and fixing are handled by local pattern matching. The analyzer looks for print statements, bare except blocks, and TODO comments. The fixer makes simple text substitutions, such as replacing print with logging and rewriting bare except blocks. This mode runs offline and does not use the API.

In Gemini mode, the agent sends prompts to Gemini for both analysis and fixing. The code expects the analyzer to return JSON and the fixer to return raw Python code only. If the response is missing, empty, or not parseable in the expected shape, the agent falls back to heuristics. The risk assessor then scores the proposed fix and decides whether auto-fix is allowed.

---

## 3) Inputs and outputs

**Inputs:**

I tested short Python snippets and small files from `sample_code/`:

- `sample_code/cleanish.py` for a mostly clean function
- `sample_code/print_spam.py` for repeated print statements
- `sample_code/flaky_try_except.py` for a bare `except:` block
- `sample_code/mixed_issues.py` for a file with multiple issues at once
- A comments-only snippet containing a TODO comment
- A malformed synthetic fix input that intentionally produced invalid Python

The inputs were mostly one-function examples, simple scripts, or very small files with obvious patterns.

**Outputs:**

The agent detected code quality issues, reliability issues, and maintainability issues. In practice, that meant print statements, bare except blocks, and TODO comments.

The risk report showed score, level, reasons, and should_autofix. Clean code usually scored low risk with no strong reasons. Multiple issues pushed the score down into medium or high risk. When a fix was malformed or changed the structure too much, the report became more cautious and refused auto-fix.

---

## 4) Reliability and safety rules

Two important rules in `reliability/risk_assessor.py` are:

1. Syntax validation with `ast.parse(fixed_code)`.
	- What it checks: whether the proposed fix is valid Python.
	- Why it matters: a fix that does not parse cannot be executed safely.
	- False positive: a code fragment or partial snippet that is intentionally incomplete could be flagged even if the surrounding context would make it valid.
	- False negative: syntactically valid code can still be logically wrong.

2. Function signature change detection.
	- What it checks: whether the top-level `def` line changed between the original and fixed code.
	- Why it matters: signature changes can break callers or subtly alter behavior.
	- False positive: a legitimate refactor may need a signature change, so the rule may be too cautious.
	- False negative: changes deeper in the body can still alter behavior even if the signature stays the same.

The older rules for short rewrites, removed return statements, and bare except rewrites are also useful because they catch risky structural changes. They can be conservative, but that is usually better than auto-applying a dangerous edit.

---

## 5) Observed failure modes

I observed these failure modes:

1. Gemini format failure: on `sample_code/print_spam.py` and `sample_code/flaky_try_except.py`, Gemini mode often returned output that was not parseable JSON for analysis or empty output for fixing. The agent fell back to heuristics instead of using the model result directly.
2. Over-editing: the heuristic fixer could make a fix feel bigger than the original problem. For example, the print-focused path introduced extra logging-related changes and even widened the function interface in one mock run, which felt more invasive than the original issue.
3. Unsafe confidence: before the syntax guardrail was added, a malformed synthetic fix still scored low risk and was treated as auto-fixable. That was a clear example of the risk layer being too permissive.

---

## 6) Heuristic vs Gemini comparison

Heuristics were consistent at spotting the obvious patterns: print statements, bare except blocks, and TODO comments. They also produced predictable fallback behavior when no API was needed.

Gemini mode did not consistently outperform heuristics in my runs because the model often returned output in the wrong shape. When that happened, the agent rejected the response and fell back to heuristics. In the successful wrapped-JSON test, the analyzer output was accepted, which showed that the parser can handle slightly more structured responses.

The biggest difference was reliability, not creativity. Heuristic fixes were simple and predictable, while Gemini responses were more variable and occasionally unusable. The risk scorer generally agreed with caution for multi-issue files and malformed fixes, but before the syntax check it could be too optimistic about broken code.

---

## 7) Human-in-the-loop decision

BugHound should refuse to auto-fix when the proposed fix does not parse as valid Python or when it changes the function signature unexpectedly. That kind of edit can break callers or create runtime errors, so it should go to human review.

I would keep this in the risk_assessor layer because that is the decision gate for should_autofix. The tool should show a message like: “Human review recommended: the proposed fix changes code structure or contains syntax errors.”

---

## 8) Improvement idea

A low-complexity improvement would be to tighten the fixer prompt so it explicitly says not to add parameters, change return values, or alter control flow unless the issue requires it. That would reduce over-editing without changing the overall architecture.
