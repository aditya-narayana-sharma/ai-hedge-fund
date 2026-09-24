# Plans

In-repo requirement and remediation tracking.

## What belongs here

One Markdown document per body of work large enough that its scope, its
rationale and its finished state are worth writing down before the code is
written. A plan should say what the problem is, what "done" looks like, and
what is deliberately out of scope. It should not restate the diff.

Plans are living documents: update the status as work lands, and keep the
evidence (file, line, command output) that justified the work in the first
place, so a later reader can tell whether a claim still holds.

## Naming

`kebab-case-topic.md`. Group related plans into a subdirectory once there are
several of them on one topic.

## Current plans

| Plan | Scope |
|---|---|
| [`remediation-2025.md`](remediation-2025.md) | The twelve remediation packages derived from the audit and root-cause analysis: build gates, portfolio accounting, cache coverage, run scoping, catalog serving, the web contract, backtesting over HTTP, headless rendering, containers and conventions. |
