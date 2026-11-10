# Data Model: Questions File

`<feature>/questions.md`:

```
# Clarifying Questions

## Q1 [role: product]
Which users?

**Answer:** Branch staff
```

- **Question:** `id` (`Q<n>`, unique), `role` (roster agent id), `text` (one line, at most 500 chars), `answer` (empty means open).
- **Audit events:** `question_asked` (`Q1 role=product`), `question_answered`.
- **Sensor:** builtin `questions`; fails while any question is open.
