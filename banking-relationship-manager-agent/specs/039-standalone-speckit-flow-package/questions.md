# Clarifying Questions

## Q1 [role: architect]
For FR-002 snapshot consent, which approval contract is authorized: (A) require assemble to consume and compare the exact human-reviewed inventory/digest, defining how generated metadata remains bound, or (B) revise the spec, CLI contract, and quickstart so assembly-time approval explicitly authorizes the exact capture performed? Decide the intended evidence path before any source inventory is approved or external assembly occurs.

**Answer:** A — assembly MUST consume the exact human-reviewed inventory file and compare its bytes to the supplied approved SHA-256 digest. It MUST compare the current capture against that inventory, take generated snapshot metadata from it, and embed those same inventory bytes in the package.

## Q2 [role: product]
For T032, the manifest and bootstrap tests had tracked changes before this stage and no trustworthy pre-change baseline exists; the installer has no tracked diff. Which evidence/requirement resolution do you authorize: provide independent historical evidence for the unchanged criterion, or revise T032 to compare against a new baseline and limit its claim to changes after that point? Keep T032 unchecked and preserve current bytes until resolved.

**Answer:** Revise T032 to use the new human-created baseline and limit the claim to preservation from that baseline onward; this is not historical proof of prior state.
