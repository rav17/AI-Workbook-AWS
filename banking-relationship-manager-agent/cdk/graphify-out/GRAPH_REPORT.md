# Graph Report - cdk  (2026-09-18)

## Corpus Check
- 9 files · ~1,853 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 1 file(s) not represented in the graph (top: .out 1)

## Summary
- 61 nodes · 70 edges · 8 communities (7 shown, 1 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 2 edges (avg confidence: 0.9)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `2bf4a2bc`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- metadata
- App
- properties
- AriaStatefulStack
- Tree
- lookupRole
- .__init__
- tags

## God Nodes (most connected - your core abstractions)
1. `metadata` - 13 edges
2. `AriaStatefulStack` - 7 edges
3. `StatefulStack` - 6 edges
4. `artifacts` - 4 edges
5. `lookupRole` - 4 edges
6. `AriaStatefulStack.assets` - 3 edges
7. `tags` - 3 edges
8. `Tree` - 3 edges
9. `test_stateful_stack_synthesizes_without_unsupported_security_configuration()` - 3 edges
10. `build_app()` - 2 edges

## Surprising Connections (you probably didn't know these)
- `build_app()` --calls--> `StatefulStack`  [EXTRACTED]
  app.py → stacks/stateful_stack.py
- `test_stateful_stack_synthesizes_without_unsupported_security_configuration()` --uses--> `StatefulStack`  [INFERRED]
  tests/test_security.py → stacks/stateful_stack.py

## Import Cycles
- None detected.

## Communities (8 total, 1 thin omitted)

### Community 0 - "metadata"
Cohesion: 0.15
Nodes (13): metadata, /AriaStatefulStack, /AriaStatefulStack/BootstrapVersion, /AriaStatefulStack/CDKMetadata/Default, /AriaStatefulStack/CheckBootstrapVersion, /AriaStatefulStack/ProviderSecret/Resource, /AriaStatefulStack/SessionStateKey/Alias/Resource, /AriaStatefulStack/SessionStateKey/Resource (+5 more)

### Community 1 - "App"
Cohesion: 0.27
Nodes (10): App, build_app(), aws_cdk, cdk_stacks_stateful_stack, constructs, os, Stack, StatefulStack (+2 more)

### Community 2 - "properties"
Cohesion: 0.18
Nodes (12): properties, properties, additionalDependencies, assumeRoleArn, bootstrapStackVersionSsmParameter, cloudFormationExecutionRoleArn, notificationArns, requiresBootstrapStackVersion (+4 more)

### Community 3 - "AriaStatefulStack"
Cohesion: 0.20
Nodes (9): type, dependencies, displayName, environment, type, artifacts, AriaStatefulStack, AriaStatefulStack.assets (+1 more)

### Community 4 - "Tree"
Cohesion: 0.50
Nodes (4): Tree, file, properties, type

### Community 5 - "lookupRole"
Cohesion: 0.50
Nodes (4): arn, bootstrapStackVersionSsmParameter, requiresBootstrapStackVersion, lookupRole

### Community 7 - "tags"
Cohesion: 0.67
Nodes (3): tags, environment, project

## Knowledge Gaps
- **32 isolated node(s):** `version`, `type`, `type`, `environment`, `templateFile` (+27 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 37 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `AriaStatefulStack` connect `AriaStatefulStack` to `metadata`, `properties`?**
  _High betweenness centrality (0.358) - this node is a cross-community bridge._
- **Why does `properties` connect `properties` to `AriaStatefulStack`, `lookupRole`, `tags`?**
  _High betweenness centrality (0.343) - this node is a cross-community bridge._
- **Why does `metadata` connect `metadata` to `AriaStatefulStack`?**
  _High betweenness centrality (0.261) - this node is a cross-community bridge._
- **What connects `version`, `type`, `type` to the rest of the system?**
  _32 weakly-connected nodes found - possible documentation gaps or missing edges._