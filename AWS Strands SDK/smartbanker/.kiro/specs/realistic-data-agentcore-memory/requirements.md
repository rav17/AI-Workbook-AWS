# Requirements Document

## Introduction

The SmartBanker AI agent currently suffers from two problems: (1) local tool stubs return minimal hardcoded data, causing the LLM to fabricate financial details (credit card offers, interest rates, transaction histories) when it lacks sufficient context, and (2) the memory layer uses a raw DynamoDB table and a custom vector memory implementation instead of the managed AgentCore Memory provided by the Strands Agents SDK. This feature introduces a realistic JSON-based seed data layer that all local tools read from, and migrates the memory subsystem from custom DynamoDB/vector implementations to AgentCore Memory's managed STM and LTM APIs.

## Glossary

- **Seed_Database**: A collection of JSON files under `data/` that represent a realistic bank database containing customer profiles, accounts, transactions, products, and portfolios
- **Tool_Stub**: The local fallback implementation inside each `@tool` function (the `_local` lambda), executed when `USE_LAMBDA=false`
- **Seed_Data_Loader**: A module (`data/loader.py`) that reads and indexes the Seed_Database JSON files and exposes query functions for Tool_Stubs
- **AgentCore_Memory**: The managed memory service provided by Bedrock AgentCore Runtime, accessed via the Strands Agents SDK, supporting both short-term memory (STM) and long-term memory (LTM) with semantic search
- **STM**: Short-term memory — stores recent interaction records (currently in DynamoDB table `smartbanker_stm`, to be replaced by AgentCore_Memory managed STM)
- **LTM**: Long-term memory — stores financial behaviour patterns as vector embeddings for semantic search (currently a custom in-memory store with Bedrock Titan embeddings, to be replaced by AgentCore_Memory managed LTM)
- **Coordinator**: The `CoordinatorAgent` class in `agents/coordinator.py` that orchestrates the self-healing loop and is the primary consumer of STM and LTM
- **Financial_Tools**: The 12 `@tool`-decorated functions in `tools/financial_tools.py` that serve as the agent's data access layer
- **Data_Grounding_Directive**: An instruction in the system prompt that prohibits the LLM from inventing financial data not provided by tools

## Requirements

### Requirement 1: Seed Database Structure

**User Story:** As a developer, I want a comprehensive JSON-based seed database with realistic banking data, so that local tool stubs return grounded, believable responses instead of minimal hardcoded values.

#### Acceptance Criteria

1. THE Seed_Database SHALL contain at least one customer profile with fields for user ID, name, tier, contact information, KYC status, and account opening date
2. THE Seed_Database SHALL contain at least three account records per customer (checking, savings, investment) with realistic balances, account numbers, and status fields
3. THE Seed_Database SHALL contain at least 60 transaction records per customer spanning a minimum of 90 days, with realistic merchant names, categories, amounts, and dates
4. THE Seed_Database SHALL contain a product catalog with at least four credit card products, four loan products, and four investment products, each with specific rates, terms, fees, and eligibility criteria
5. THE Seed_Database SHALL contain at least two credit card records per customer with card number (masked), credit limit, current balance, reward points, and associated offers
6. THE Seed_Database SHALL contain at least two loan records per customer with loan type, principal, interest rate, EMI, tenure, and outstanding balance
7. THE Seed_Database SHALL contain an investment portfolio per customer with at least four holdings including asset name, quantity, purchase price, current value, and asset class
8. THE Seed_Database SHALL store all data as JSON files under a `data/` directory at the project root

### Requirement 2: Seed Data Loader

**User Story:** As a developer, I want a single data loader module that reads and indexes the seed database, so that all tool stubs access data through one consistent interface.

#### Acceptance Criteria

1. THE Seed_Data_Loader SHALL load all JSON files from the `data/` directory at module import time and cache the parsed data in memory
2. THE Seed_Data_Loader SHALL provide a `get_customer(user_id)` function that returns the full customer profile or raises a `KeyError` when the user ID is not found
3. THE Seed_Data_Loader SHALL provide a `get_transactions(user_id, days)` function that returns transactions filtered to the specified number of days from the most recent transaction date
4. THE Seed_Data_Loader SHALL provide a `get_accounts(user_id)` function that returns all account records for the given customer
5. THE Seed_Data_Loader SHALL provide a `get_products(product_type)` function that returns catalog entries filtered by product type (credit_card, loan, investment, insurance)
6. THE Seed_Data_Loader SHALL provide a `get_credit_cards(user_id)` function that returns credit card records including associated offers for the given customer
7. THE Seed_Data_Loader SHALL provide a `get_loans(user_id)` function that returns active loan records for the given customer
8. THE Seed_Data_Loader SHALL provide a `get_investments(user_id)` function that returns the investment portfolio for the given customer
9. WHEN a query function receives a user_id that does not exist in the Seed_Database, THE Seed_Data_Loader SHALL raise a `KeyError` with a descriptive message including the unknown user_id

### Requirement 3: Tool Stub Migration to Seed Data

**User Story:** As a developer, I want all local tool stubs to read from the seed database instead of returning inline hardcoded values, so that the LLM receives consistent, realistic data across all tools.

#### Acceptance Criteria

1. WHEN `USE_LAMBDA` is false, THE `transaction_fetcher` Tool_Stub SHALL return transactions from the Seed_Database filtered by user_id and days parameter
2. WHEN `USE_LAMBDA` is false, THE `balance_checker` Tool_Stub SHALL return account balances from the Seed_Database for the given user_id
3. WHEN `USE_LAMBDA` is false, THE `investment_data_api` Tool_Stub SHALL return investment products from the Seed_Database product catalog filtered by risk_tolerance
4. WHEN `USE_LAMBDA` is false, THE `budgeting_calculator` Tool_Stub SHALL compute budget allocations using the customer's actual account balances and transaction totals from the Seed_Database
5. WHEN `USE_LAMBDA` is false, THE `loan_product_catalog` Tool_Stub SHALL return loan products from the Seed_Database product catalog filtered by loan_type and user_tier
6. WHEN `USE_LAMBDA` is false, THE `activity_analyzer` Tool_Stub SHALL compute activity metrics from the Seed_Database transaction history and account data for the given user_id
7. WHEN `USE_LAMBDA` is false, THE `tier_benefit_mapper` Tool_Stub SHALL return tier benefits from the Seed_Database product catalog for the given user_tier
8. WHEN a Tool_Stub receives a user_id not present in the Seed_Database, THE Tool_Stub SHALL return a JSON error response with status "error" and a message indicating the user was not found
9. THE Financial_Tools module SHALL contain zero inline hardcoded financial data values in any Tool_Stub — all financial data SHALL originate from the Seed_Database

### Requirement 4: LLM Data Grounding Directive

**User Story:** As a product owner, I want the LLM to only use data provided by tools and never fabricate financial information, so that users receive accurate, verifiable responses.

#### Acceptance Criteria

1. THE Coordinator system prompt SHALL include a Data_Grounding_Directive instructing the LLM to only present financial data returned by tool calls
2. THE Data_Grounding_Directive SHALL explicitly prohibit the LLM from inventing credit card offers, interest rates, account balances, transaction details, or any other financial data
3. THE Data_Grounding_Directive SHALL instruct the LLM to state "I don't have that information" when a tool does not return the requested data
4. WHEN a worker agent system prompt references financial data, THE system prompt SHALL include the Data_Grounding_Directive

### Requirement 5: AgentCore Memory STM Migration

**User Story:** As a developer, I want to replace the raw DynamoDB short-term memory with AgentCore Memory's managed STM, so that the system uses the platform's built-in memory management instead of maintaining a custom DynamoDB table.

#### Acceptance Criteria

1. THE Coordinator SHALL use the Strands SDK AgentCore_Memory API for storing interaction records to STM instead of the `DynamoDBShortTermMemory` class
2. THE Coordinator SHALL use the Strands SDK AgentCore_Memory API for retrieving recent interactions from STM instead of querying DynamoDB directly
3. THE Coordinator SHALL use the Strands SDK AgentCore_Memory API for retrieving failed interactions from STM
4. THE STM migration SHALL preserve the existing `InteractionRecord` data model fields (user_id, timestamp, input, output, status, confidence, intent, worker_domain, strategy_used, correlation_id)
5. THE STM migration SHALL preserve the existing pruning behaviour where the system retains a maximum of 20 interactions per user, with failures retained longer than successes
6. WHEN AgentCore_Memory STM is unavailable, THE Coordinator SHALL log a warning and continue operation with an empty memory context

### Requirement 6: AgentCore Memory LTM Migration

**User Story:** As a developer, I want to replace the custom vector memory with AgentCore Memory's managed LTM with semantic search, so that the system uses the platform's built-in embedding and search capabilities.

#### Acceptance Criteria

1. THE Coordinator SHALL use the Strands SDK AgentCore_Memory API for storing financial patterns to LTM instead of the `VectorMemoryManager` class
2. THE Coordinator SHALL use the Strands SDK AgentCore_Memory API for semantic similarity search over stored patterns instead of the custom cosine similarity implementation
3. THE LTM migration SHALL preserve the existing `FinancialPattern` data model fields (pattern_id, user_id, pattern_type, content, metadata)
4. THE LTM migration SHALL preserve the existing search behaviour of returning top-K results filtered by user_id
5. WHEN AgentCore_Memory LTM is unavailable, THE Coordinator SHALL log a warning and continue operation with an empty pattern list

### Requirement 7: Remove Standalone DynamoDB Resources

**User Story:** As a developer, I want to remove the standalone DynamoDB table and associated IAM policies from the deployment stack, so that the infrastructure reflects the migration to AgentCore Memory.

#### Acceptance Criteria

1. THE CloudFormation template (`deployment/cfn_template.json`) SHALL NOT contain a DynamoDB table resource for `smartbanker_stm`
2. THE IAM role policy in the CloudFormation template SHALL NOT contain DynamoDB access permissions for the `smartbanker_stm` table
3. THE deployment configuration (`deployment/aws_config.json`) SHALL update the Memory architecture description to reference AgentCore_Memory instead of DynamoDB and OpenSearch
4. THE deployment configuration SHALL remove the DynamoDB section describing the `smartbanker_stm` table

### Requirement 8: Backward Compatibility and Graceful Degradation

**User Story:** As a developer, I want the memory migration to be backward-compatible with existing tests and the degradation control module, so that the 160 existing tests continue to pass.

#### Acceptance Criteria

1. THE `MemoryDegradationControl` class SHALL continue to function with the same `prepare_context` interface, receiving `InteractionRecord` and `SimilarPattern` lists regardless of the underlying memory backend
2. THE `MemoryConfig` class SHALL retain the `agent_id` field and add any new fields required by AgentCore_Memory configuration
3. WHEN the system runs in local mode (`USE_LAMBDA=false`), THE memory layer SHALL operate without requiring an active AgentCore Runtime connection by using an in-memory fallback
4. THE `InteractionRecord` and `FinancialPattern` Pydantic models SHALL remain unchanged to preserve compatibility with all existing consumers
