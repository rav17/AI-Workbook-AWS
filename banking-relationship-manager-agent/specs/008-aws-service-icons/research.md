# Research: AWS Service Icons in Architecture Diagram

## Decision: Use Draw.io Native AWS4 Resource Icons

The reference architecture uses editable `mxgraph.aws4.resourceIcon` shapes with `resIcon=mxgraph.aws4.<name>`. Reuse this convention rather than embedding bitmap assets so icons remain editable and match the requested reference.

Verified service stencil IDs from the reference file include `api_gateway`, `lambda`, `machine_learning`, `eventbridge`, `sqs`, `dynamodb`, `kms`, `secrets_manager`, `cloudwatch`, `sns`, and `general_saml_token`.

## Decision: Keep Service Cards and Connector Anchors

Place an AWS icon within each existing service card and leave the card cell as the edge endpoint. Keep the full service label in a separate text cell within that card. This preserves the current left-to-right layout and connector relationships.

## Decision: Use Specific or Broad Icons Conservatively

Use service-specific stencil IDs where verified. For AgentCore and Bedrock services without a confirmed dedicated stencil in the reference library, use the verified `machine_learning` category icon. Keep external vendors, human actors, custom application components, and services without a suitable icon as generic labeled cards.

## Alternatives Considered

- Embedded SVG/PNG assets: rejected because they are less editable and do not follow the reference diagram's native resource-icon pattern.
- Guessing unsupported stencil IDs: rejected because an unknown ID can render as a blank icon.
- Replacing cards with standalone icons: rejected because long labels and the current connection anchors would be harder to preserve.
