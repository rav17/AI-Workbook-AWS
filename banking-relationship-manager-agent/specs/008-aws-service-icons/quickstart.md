# Quickstart: AWS Service Icons in Architecture Diagram

From the repository root, regenerate only the end-state architecture diagram:

```powershell
.\.venv\Scripts\python.exe -c "from docs.architecture.generate_diagrams import end_state_architecture; end_state_architecture()"
```

Parse the output as XML and verify:

- `docs/architecture/08_Aria_End_State_Architecture.drawio` opens as an editable Draw.io diagram.
- AWS-managed service cards display the mapped AWS4 resource icon.
- Non-AWS and custom components retain their generic styles.
- Every edge source and target refers to an existing cell.
- Every diagram vertex remains within the 2400 by 900 page.
