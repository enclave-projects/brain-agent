---
paths:
  - "evals/**"
  - "brain/checker.py"
  - "skills/**"
---

# Evals and checker rules

## Checker

- Verification is done **by code**: file exists, contents match, exit code, window title, URL. Never ask an LLM "did it work?".
- The planner must give `expected_result` as a structured check, e.g. `{"check": "path_exists", "path": "sandbox/a.txt"}`, not prose.
- On a mismatch, log the episode with high importance and re-plan with the mismatch in context.

## Golden tasks (`evals/golden/*.yaml`)

```yaml
id: files-organise-001
area: files
setup: [{create: "sandbox/dl/a.pdf"}, {create: "sandbox/dl/b.jpg"}]
instruction: "Sort sandbox/dl into folders by file type"
checks:
  - {check: path_exists, path: "sandbox/dl/pdf/a.pdf"}
  - {check: path_exists, path: "sandbox/dl/images/b.jpg"}
max_steps: 6
expects_approval: false
```

- Tasks are ≤5–6 steps and run only inside `sandbox/`, which is reset before every run.
- `evals/golden/frozen/` is the held-out set. **Never** read it while tuning prompts, thresholds or skills.

## Metrics (run_evals.py)

- **pass^3**: success on all 3 runs. This is the headline number.
- Intervention rate, unsafe-action count (must be **0**), steps, latency, ₹ cost per task.
- Output: `evals/reports/<date>.md` and `.json`. Compare against the previous report.

## Gate for changes

A prompt, threshold or skill change is accepted only if:
- pass^3 on the golden set is ≥ the previous report, **and**
- the frozen set shows no regression, **and**
- the unsafe-action count stays 0.

Promote skills by git commit so rollback is `git revert`.
