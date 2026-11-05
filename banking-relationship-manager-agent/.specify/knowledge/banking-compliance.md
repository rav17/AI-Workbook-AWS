title: Banking compliance basics
stages: specify, plan, implement, analyze

# Banking compliance basics

- Customer data (names, account numbers, balances) must never appear in logs, audit details, specs or tests; use synthetic data.
- Any action that moves money or changes customer records needs an explicit human approval step.
- Every decision that affects a customer must be traceable in the audit trail.
- Keep secrets out of source control; read them from the environment or a secrets manager.
