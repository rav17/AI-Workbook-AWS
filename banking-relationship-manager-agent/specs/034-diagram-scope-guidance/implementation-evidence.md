# Implementation Evidence: Two-Level Diagram Scope Guidance

**Feature**: `specs/034-diagram-scope-guidance`
**Purpose**: record implementation reviews and truthful provenance for T001/T012. This file is evidence, not an independent review verdict, architecture approval, or lifecycle-gate approval.

## Preservation provenance and result

The historical baseline is not reconstructed from HEAD or inferred from the current worktree. Original local event records retained outside the repository report:

- Lead pre-edit capture: event lines 9772 (command) / 9799 (output), `2026-11-13T19:13:19.459Z`, count 14.
- Documentation-worker pre-edit capture: lines 10336 / 10361, `2026-11-13T19:16:47.289Z`, count 14. The first edit attempt is recorded at line 10371 (`19:17:11.348Z`); the successful edit command/result are lines 10397 / 10406, after both pre-edit captures.
- Documentation-worker post-edit capture and diagram status: lines 10572 / 10579, `2026-11-13T19:20:04.285Z`, count 14, empty `git status --short -- docs/architecture`.
- Lead post-edit exact comparison and diagram status: lines 10990 / 10997, `2026-11-13T19:26:10.590Z`, count 14, matching paths/hashes, empty diagram status.
- Recovery-time fresh current capture: `2026-11-13T19:38:02.568007Z` through `19:38:03.236852Z`, Python SHA-256 over current file bytes, count 14, empty diagram status. This capture is current-at-recovery, **not pre-edit**.
- Machine comparison JSON timestamp: `2026-11-13T19:40:43.412038+00:00`. A fresh check in this implement session independently recomputed current file hashes and compared all rows in that JSON: 14 current paths; 0 mismatches for each of five named capture/report records. The report-table entry is a reported claim, not an independent capture.

The retained external source files are:

- `C:\Users\RavindraYadav\.copilot\session-state\1bd4aa33-411a-4f0d-ad32-28a589752ef5\files\agent-quality-feature034-hash-recovery-20261113T193801Z\RECOVERY-REPORT.md`
- `C:\Users\RavindraYadav\.copilot\session-state\1bd4aa33-411a-4f0d-ad32-28a589752ef5\files\agent-quality-feature034-hash-recovery-20261113T193801Z\current-diagrams-sha256-and-status.txt`
- `C:\Users\RavindraYadav\.copilot\session-state\1bd4aa33-411a-4f0d-ad32-28a589752ef5\files\agent-quality-feature034-hash-recovery-20261113T193801Z\historical-vs-current-comparisons.json`

Both historical before/after pairs match exactly (14/14 paths and SHA-256 values). Each retained capture/report row also matches the fresh current recomputation. Exact hashes from that machine recomputation:

| Current `docs/architecture/*.drawio` path | SHA-256 |
|---|---|
| `docs/architecture/01_Key_NFRs.drawio` | `5e3d6c5d07c176d8226b9106d1d63f7df05144855c3097d2b413b1f2350af7e3` |
| `docs/architecture/01_System_Context_Diagram.drawio` | `ad599a0b8e97cdc44894e2422f201b9e2793e2eac3736a758733067ce5786d8f` |
| `docs/architecture/01_Use_Case_Diagram.drawio` | `4c93a9fdefc4decd1c13d64deb52be8d33c5232c6b1da787ae8f0a87f858b686` |
| `docs/architecture/02_Architecture_Overview.drawio` | `0a3ea41aa098da46e2b1f34862ab2a29cc3e028793dcb03e018ad828a8f71abe` |
| `docs/architecture/03_Component_Model.drawio` | `06bcd8a82de54d134fe78a0ebe8ad930c5cbeb519b5417afa26906e7b7805f80` |
| `docs/architecture/03_Sequence_Chat_Message.drawio` | `406ee3113383b0643cadee61338ca26a71ee2600a9feb31bd6bbfa6220b58c72` |
| `docs/architecture/03_Sequence_Proactive_Event.drawio` | `a21e816e4109bb8f8f2d4ce0b7475e8ee109223215e6b864ce52c3352c1d1ea9` |
| `docs/architecture/04_Deployment_Unit_Model.drawio` | `3344023311921c5fcbd90d8def16730b969a6f8b91489b14688e9bef2aea7fea` |
| `docs/architecture/04_Location_Model.drawio` | `5f954fee822a59d93c2f16ee1a13166dfbe90a6774e810ea16a6ca7fa9c8de55` |
| `docs/architecture/05_LOM.drawio` | `05d0064292bacaf0fb50479f64a4354eb0d2d777ab2219367224e0769ddd2300` |
| `docs/architecture/05_POM.drawio` | `6145104ef6c037bf2b71c39fee6d9195e348b4b38070e22c32c331ba4233aef6` |
| `docs/architecture/07_Architecture_On_A_Page.drawio` | `30a266431e074eec5d1fb22b7f800eebdd5764cea4977a47a2cc35301ea34fab` |
| `docs/architecture/07_Security_Viewpoint.drawio` | `088a07957df7f435fa16dd12c800a1a83d5f94a09edc06334dae396916adb497` |
| `docs/architecture/08_Aria_End_State_Architecture.drawio` | `1609522222ed533a092bc17f48264147276e48953a5b826cbb4e10c3d2a4ad46` |

**Limits**: These are local event records and hash snapshots, not signed independent attestations. Matching endpoint snapshots support byte equality at the captured points; they do not prove continuous absence of transient edits, architectural correctness/freshness, or owner approval. No current/recovery capture is represented as a pre-edit baseline.

## Documentation review/check outcomes

- **T004 (US1)**: inspected the complete skill and register template. The skill distinguishes shared baseline from useful full-lifecycle feature-local views, does not copy the baseline, makes ideation sketches optional/conceptual and unapproved, and does not impose a view set on the `refactor` route. The template permits `none` and applicability/deferred rationale; no mandatory candidate view or baseline copy is implied.
- **T007 (US2)**: inspected relevant, irrelevant, missing, stale, conflicting, unknown-source-version/status, and unknown-review-point cases. Relevant baselines get a navigable link plus relevance/scope; no-relevant needs no link; a missing baseline remains pending with no asserted relevance/link until owner disposition; stale means a relevant source changed/superseded since review; gaps/conflicts and unknowns request designated-owner revalidation. The template has each FR-006 field, including timezone-aware time, reviewer/role/owner status, source IDs/versions, uncertainty, gap/conflict request, and missing-baseline disposition/follow-up/rationale.
- **T010 (US3)**: inspected the complete proposal template and skill procedure. Pending, rejected, and conditional block application; condition satisfaction alone does not approve; explicit owner approval must follow evidence of all conditions and precede application. The explicitly approved state is recorded, not inferred. Structural validation is not authorization.
- **T011 (FR-001-FR-010 / SC-001-SC-005)**: inspected all three full guidance files. Scope, evidence fields, owner approval sequence, synthetic-only examples, validator limits, and preservation boundary are represented. This review does not prove universal future compliance.
- Exact existence/trailing-whitespace checks passed for all three guidance files. `git diff --check` exited 0; however, `.github/skills/speckit-diagrams/` is untracked in this worktree, so that command does not substantively inspect those untracked contents. The explicit file/whitespace scan did inspect them.

## Other verification and route applicability

- The feature plan is documentation-only; no application code or feature-specific test was required by the plan. A support-reported supplemental command `PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider` exited 0 with 776 passed and 7 skipped in 243.39 seconds; skips were attributed to symlink/module availability. This broad project run is not feature-specific acceptance and was not rerun during this bounded correction.
- No diagram validator was run: no diagrams changed, no feature diagram was created, and the route is `refactor`.
- No feature 033, spec/checklist, app source, pointer, or lifecycle state was changed. The spec remains Draft; no approval or gate is inferred.


## Authorized lint-fix exception (bounded implement resume)

Recorded at: 2026-11-13T20:30:31.175874+00:00. Lead: developer / speckit-developer (agent:developer).

**Historical-scope qualification:** The documentation-only/no-application-source-change statements above and in the unchanged plan/tasks describe the original T001-T012 work, not the cumulative state after this resume. The user's explicit exception authorizes exactly `speckit_flow/reviews.py:57`: replace `(list, dict)` with `list | dict` inside `isinstance(raw_files, ...)`, plus this evidence update and the required backed-up local Graphify update. No other application file was edited. T001-T012 remain checked; no historical task/plan scope or valid historical evidence was rewritten. No new test file was authorized or created; existing focused tests and an in-memory equivalence matrix exercise the change. Python 3.11.9 was used; the project requires >=3.11.

### Commands and actual verification

Every CLI invocation began with `Set-Location 'C:\Users\RavindraYadav\Documents\AI-Workbook-AWS\banking-relationship-manager-agent'`. Python validation commands used `$env:PYTHONDONTWRITEBYTECODE='1'`. No feature workflow CLI, prerequisite rerun, integration/pointer switch, stage transition, sensor, or review-write command was run.

- `python -m ruff check --no-cache speckit_flow/reviews.py`: exit 0, all checks passed.
- `python -m pytest -p no:cacheprovider tests/unit/speckit_flow/test_flow_reviews.py tests/unit/speckit_flow/test_flow_gate_review.py`: exit 0, **22 passed in 5.06s**. pytest-asyncio warned that `asyncio_default_fixture_loop_scope` is unset. These are focused unit tests, not E2E or diagram-guidance acceptance.
- `python -m mypy --cache-dir=NUL speckit_flow/reviews.py`: exit 2, mypy 2.4.1 INTERNAL ERROR; no traceback was emitted. Retry: `python -m mypy --no-incremental --cache-dir 'C:\Users\RAVIND~1\AppData\Local\Temp\feature034-implement-7ox_mzml\mypy-cache' --show-traceback speckit_flow/reviews.py`: exit 0, success, no issues in 1 source file. The retry succeeded; the original internal error's cause is not established.
- `python -m ruff format --check --no-cache speckit_flow/reviews.py`: exit 0, 1 file already formatted.
- Inline Python assertions compared both `isinstance` forms and the complete rejection guard for 22 synthetic values, including list/dict subclasses, empty/nonempty containers, scalar/noncontainer values, and class objects: passed. This finite matrix is supplemental, not exhaustive or E2E proof.
- `git diff --check`: exit 0; Git emitted existing LF/CRLF conversion warnings on unrelated worktree files. `git --no-pager diff -- speckit_flow/reviews.py` shows only the authorized line.
- Complete guidance reads reconfirmed T004/T007/T010/T011 semantics: baseline/feature separation, optional conceptual sketches, useful full-lifecycle views only, relevant links with scope, all FR-006 fields and uncertainty/owner-revalidation handling, pending missing-baseline disposition with neither asserted relevance nor fabricated link, and pending/rejected/conditional blocking until subsequent explicit owner approval. All three guidance files passed explicit existence/trailing-whitespace assertions, including untracked files. They were not edited during this resume. Representative inspection is not proof of universal future compliance.
- No diagram validator: refactor route; zero draw.io changes or new feature diagrams. `.specify/extensions.yml` is absent, so no pre/post extension hooks apply.

### Implement-3 review-warning follow-up (open)

The independent `implement-3` review recorded two warnings; neither is represented as resolved by this bounded documentation correction:

- **Pointer interval**: `.specify/feature.json` was omitted from the initial inventory and has no pre-resume fingerprint. The recorded later fingerprint supports only the later interval; whole-resume pointer preservation remains unverified. No unauthorized pointer change was established, and none is inferred from the missing baseline.
- **Independent measurements**: the reviewer did not execute a fresh diff or rehash, and this implement follow-up did not perform or claim those independent measurements. The assigned reviewer is to inspect the final diff and independently measure the 14 diagrams. Conductor measurements are not a substitute for independent review.

The required lint and unit-tests sensor records available to this handoff are historical passes (`20:31:42Z` and `20:37:21Z`), not fresh runs in this session. The focused 22-pass pytest run and support-reported broad 776-pass/7-skip run recorded above do not establish the configured sensor command outputs. The conductor must run the actual required sensors; no sensor pass or implementation-stage completion is claimed here.

### Preservation evidence and limits

External checkpoint directory: `C:\Users\RAVIND~1\AppData\Local\Temp\feature034-implement-7ox_mzml`.

- `preservation-before.json` captured SHA-256 for 694 tracked/nonignored project files before the code edit (including existing user changes); `preservation-after-code.json` compared the same inventory after code/tests/Graphify. Only `speckit_flow/reviews.py` differed outside Graphify at that point. All 12 files in the complete feature033 tree, 75 `aria/` files, and 25 other `speckit_flow/` files matched. Historical feature034 plan/tasks/spec/checklist and existing lifecycle/review artifacts in this inventory matched. Final comparison additionally allows only this evidence file.
- All 14 existing shared diagrams match both this resume's pre-edit fingerprints and the historical table above (14/14). All 15 inventoried `docs/architecture/` files were unchanged. This establishes endpoint byte equality, not approval/freshness or continuous absence of transient edits.
- **Capture gap:** `.specify/feature.json` is ignored and was omitted by the initial Git-based inventory. It was never intentionally edited or targeted by any write command, but there is no pre-code-edit pointer fingerprint from this resume, so no such comparison is claimed. Its later fingerprint (before this evidence edit) is `a09a2923ffde1dd3a2054b443c6efe3b387be569055e31f50ee2d7d7ff3854b7`; `late-forbidden-before-evidence.json` explicitly records late capture time and the complete feature033 inventory. Final comparison covers only the interval after that capture for the pointer.
- No reset/revert was used. No application source beyond the authorized line, feature033, shared diagram, pointer, integration, policy/rules, gate, state, audit or review file was intentionally changed. Initial preservation covers Git-visible/nonignored files, not all ignored runtime artifacts or other projects in the parent repository.

### Graphify backup, result and exact changed files

Before code modification/update, Python `shutil.copytree` copied all **1,158 files** from existing `graphify-out/` to `C:\Users\RAVIND~1\AppData\Local\Temp\feature034-implement-7ox_mzml\graphify-out`. `graphify-before.json` records their hashes. Existing user modifications were preserved in this external full copy; generated files were not reset to HEAD. A preceding local `graphify query "What is speckit_flow reviews validation and repository guidance for diagram scope?"` succeeded and returned a truncated local context response; the backup is pre-update, not pre-query.

After the code edit, `graphify update .` exited **0**: local AST re-extraction, 139 uncached files; rebuilt **4,808 nodes, 9,966 edges, 359 communities**. It skipped 28 unsupported files, including draw.io, and warned of changed community labels. No `graphify label`, semantic extraction, API command, or external transmission was invoked. Graphify itself also created a four-file curated backup under `graphify-out/2026-11-14/`; this is separate from the complete external preservation copy.

`graphify-changes.json` in the external checkpoint contains exact before/after hashes and added/modified status for **34 files** (no deletions), relative to the pre-update copy:

- `graphify-out/.graphify_labels.json` (modified)
- `graphify-out/.graphify_labels.json.sig` (modified)
- `graphify-out/2026-11-14/.graphify_labels.json` (added)
- `graphify-out/2026-11-14/GRAPH_REPORT.md` (added)
- `graphify-out/2026-11-14/graph.json` (added)
- `graphify-out/2026-11-14/manifest.json` (added)
- `graphify-out/GRAPH_REPORT.md` (modified)
- `graphify-out/cache/ast/v0.9.63-s3/0d1e78cea81dc6451356b833d192a605b9fe74ba80bebfe77ec04b0c4e4fbbc1.json` (added)
- `graphify-out/cache/ast/v0.9.63-s3/1c36070d2d2e99371a8964594a9258b744238a45046a72ba78399593367230c9.json` (added)
- `graphify-out/cache/ast/v0.9.63-s3/1d188fee5f39ce0886d72b89cd9f75aeb1ab1d75c2c78231df45fbef1483068a.json` (added)
- `graphify-out/cache/ast/v0.9.63-s3/2377902d3ffb809ab04c7bbfd15447183953e4b633f8b57fbc89ff758532c594.json` (added)
- `graphify-out/cache/ast/v0.9.63-s3/6b3e2098ac50c821e734f8e0ca1631f3f177acfb0ba4a9418a08561ef7615829.json` (added)
- `graphify-out/cache/ast/v0.9.63-s3/6ebac9eb0e8a2f822a2c0d37bfeac2c089f77e59ab2b072f35a22a2631094d53.json` (added)
- `graphify-out/cache/ast/v0.9.63-s3/7a79b226106e52676bfb4f6136b1f86d4486f16f7c835333a460f1ed4ed1713d.json` (added)
- `graphify-out/cache/ast/v0.9.63-s3/851edd8e7db5af6dcecaba0d342f3bb59c51ce7ead2408e45761907024fb2e10.json` (added)
- `graphify-out/cache/ast/v0.9.63-s3/90226cf445150373f9236a5220751977069f862e391a335021442a67854b3482.json` (added)
- `graphify-out/cache/ast/v0.9.63-s3/92c6719a3d00e200f0d057f21d251a933be7788e09e2ef3ccbc8c4e6d47756fc.json` (added)
- `graphify-out/cache/ast/v0.9.63-s3/9d7cd294c35e3b5fe832c45bf8989d9f9b5b3ff919e55c9eb49aefc78e11303a.json` (added)
- `graphify-out/cache/ast/v0.9.63-s3/a0c5c334f39eaeeab52efb860d814463366bda7be8c5e64f0d91ac373edfc94f.json` (added)
- `graphify-out/cache/ast/v0.9.63-s3/a7c268d6f8723bfed6d99ef227bb110d8db9cd41edf83117ebf02154c6a071ce.json` (added)
- `graphify-out/cache/ast/v0.9.63-s3/bbc7da1a773a7f38d4fc8dffec5d40af9e860517663ebb5de9128f614bc29146.json` (added)
- `graphify-out/cache/ast/v0.9.63-s3/c04a207005589a26b0976fa7e21be5d7b00e77301714b1208f41709780a46bd2.json` (added)
- `graphify-out/cache/ast/v0.9.63-s3/c65cf54987dbcbb89a71b9ec3478efaa17735124458f2cda994a6c45d71b675c.json` (added)
- `graphify-out/cache/ast/v0.9.63-s3/cf412c70f685f6d4e5759e049bdd5e38d4a25f4b29a8ffc22da3115262bc55bb.json` (added)
- `graphify-out/cache/ast/v0.9.63-s3/d614c4d0f7dccb83b30694e5e3420428ddaf14bed4a688943de3e64a18209aff.json` (added)
- `graphify-out/cache/ast/v0.9.63-s3/d7f893a58ca3baa46820cb11d4fac4c958bea097f91d107555164a8520277ecd.json` (added)
- `graphify-out/cache/ast/v0.9.63-s3/dbab2f5802ce73b22d55ff209c21563519a60155db03020a52942fe58ee58818.json` (added)
- `graphify-out/cache/ast/v0.9.63-s3/dd4846c24a360113d76dbbaa7e4997d7532921777d830e5d4dd595c6289e5518.json` (added)
- `graphify-out/cache/ast/v0.9.63-s3/e8d3494c865f2c1cbcdab218d53acd2fd7cd7524da66cd2a50acc5e968eba9ee.json` (added)
- `graphify-out/cache/ast/v0.9.63-s3/ea13d77d191a8ea693ec2ce59adfefcdb2aab804ac68ceb1042f1f4b4e7a526d.json` (added)
- `graphify-out/cache/stat-index.json` (modified)
- `graphify-out/graph.html` (modified)
- `graphify-out/graph.json` (modified)
- `graphify-out/manifest.json` (modified)

### Errors, remaining work and authority

Two initial read paths incorrectly used the parent directory and failed with file-not-found; corrected project-local reads succeeded. The first replacement attempt asserted against `value` instead of `raw_files`; its assertion failed before any source write. The corrected byte replacement changed exactly one occurrence. The initial mypy internal error and initial ignored-pointer capture gap remain disclosed above.

The conductor must run required stage sensors and arrange the post-edit independent review. This developer self-check is not that independent review. The earlier support observations supplied in the handoff were pre-edit and are not represented as a new independent post-edit verdict. No stage start/done, human/policy gate approval, architecture-owner approval, or specification approval is claimed. Stop after bounded implement work.

Final-check diagnostic: a raw-byte comparison to `git show HEAD` failed because the worktree source uses CRLF (HEAD uses LF); normalized comparison matched. The final source-preservation assertion instead reverses only the authorized replacement and compares its SHA-256 to the actual pre-edit worktree fingerprint, avoiding a reconstructed baseline.
