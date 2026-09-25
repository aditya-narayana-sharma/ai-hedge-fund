# Plans

Requirement documents for work that is planned but not yet built.

Each plan is a Markdown file named after the change it describes
(`kebab-case.md`) and should state, in this order:

1. **Problem** — what is wrong or missing today, with file and line evidence.
2. **Proposal** — what to build, concretely enough to review before any code exists.
3. **Scope** — which modules change, and explicitly what does not.
4. **Verification** — the check that proves it works, ideally a test name.

Plans are deleted once the work lands; the commit message and
[`ARCHITECTURE.md`](../ARCHITECTURE.md) become the record.

## Current plans

See [`open/`](open/). Nothing here blocks a release — the two ship blockers and
all twelve fix packages from the status audit have landed.
