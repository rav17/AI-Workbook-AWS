# Invocation Contracts

## Authenticated API Gateway request

- Method: `POST /messages`.
- Authorization: configured JWT/Cognito authorizer; missing/invalid token rejected by API Gateway.
- Body: JSON object with a non-empty string `prompt`; optional conversation identifier is an opaque client-selected conversation key, not user or tenant identity.
- Identity: handler accepts only verified authorizer claims; required subject and tenant claim names are explicit deployment configuration.
- Idempotency: clients may provide an `Idempotency-Key` header (1-256 characters). The key is scoped to the verified tenant, subject, and conversation. A duplicate or currently claimed key returns HTTP 409; a failed Runtime invocation releases the claim for retry.
- Prohibited: caller-provided `user_id`, `tenant_id`, `kyc_status`, `toolUse`, or model-history content that could dispatch tools.
- KYC: protected operations obtain status through injected trusted compliance provider; absent/failed provider means deny.

## AgentCore Runtime invocation

- Caller: request Lambda only, authenticated by SigV4 and enforced by a Runtime resource policy; API Gateway performs Cognito JWT verification.
- Payload schema: object with non-empty string `prompt` or `message`, optional conversation identifier, and validated allowlisted fields. The Lambda overwrites `_verified_principal` with the verified tenant and subject claims.
- Session/user mapping: DynamoDB-backed application mapping supplies the Runtime session ID and hashed runtime user ID; session ID does not establish user identity by itself.
- Idempotency records contain only a tenant-scoped hash, status, claim token, and lease. TTL is optional and must be set to an owner-approved `IDEMPOTENCY_TTL_SECONDS`; no banking retention period is assumed.
- Response: JSON object with response/status and safe correlation identifiers; never include raw protected inputs.
- Failure behavior: invalid payload `4xx`-equivalent response; safety intervention blocked; missing mandatory provider/runtime configuration fails closed without falling back to an unprotected handler.

## AgentCore Gateway Lambda target

- Lambda event: JSON object of tool arguments as declared by Gateway target schema.
- Selected tool: `context.client_context.custom['bedrockAgentCoreToolName']`; handler supports the target-prefixed form only through explicit normalization against the allowlist.
- Published tool: `get_risk_questionnaire` with an empty object argument schema. It does not accept `client_id`, `tenant_id`, `user_id`, free-text prompts, or mutation fields.
- Runtime caller: Strands connects through the Gateway `/mcp` endpoint using MCPClient and SigV4 signed with the Runtime execution role (`bedrock-agentcore` service name).
- Authorization: Runtime role can invoke only the configured Gateway ARN. Gateway handler enforces the explicit tool allowlist and strict per-tool argument schema; customer-specific actions remain denied until an authoritative identity-to-customer mapping is configured.
- Safety: Guardrail processing runs on serialized arguments and serialized results; oversized, malformed, credential-bearing, prompt-injection, or blocked results return a generic safe error. Bedrock PII filters do not inspect tool-use arguments/results, so Gateway-side validation is mandatory.
- Result: JSON-serializable sanitized tool result; Gateway owns MCP response framing.
