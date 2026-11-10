# Research: Questions File and Interaction Modes

- **Decision:** a plain Markdown file with `## Q<n> [role: <role>]` headings and an `**Answer:**` marker, so a human can edit it directly. **Alternative:** JSON (rejected; not pleasant to hand-edit).
- **Decision:** "answered" means a non-empty answer; hand edits therefore count, and the sensor reads the file rather than audit events.
- **Decision:** malformed `## ` headings are an error, so an unanswered question can never silently disappear from the gate checks.
- **Decision:** the CLI `answer` command is human-only; the guard hook also blocks agent shells from running it, because the CLI cannot authenticate an actor.
- **Not built:** a distinct "free discussion" mode; discussion happens in chat and the outcome is recorded with `questions answer`.
