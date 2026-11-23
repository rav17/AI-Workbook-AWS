# Contract: Bank Transaction API

## Overview
The Bank Transaction API provides secure access to customer transaction data for spending analysis and financial insights. All data access is anonymized and aggregated to prevent sensitive information leakage.

## Endpoint
- **URL**: `https://api.bank.com/transactions`
- **Method**: POST
- **Authentication**: AWS IAM + API Key (managed by AgentCore gateway)

## Request Contract
```json
{
  "customer_id": "string",
  "date_range": {
    "start": "2023-01-01",
    "end": "2023-12-31"
  },
  "categories": ["string"],
  "limit": 100
}
```

**Field Definitions:**
- `customer_id`: Unique customer identifier.
- `date_range`: Date range for transactions (ISO 8601 format).
- `categories`: Optional filter by transaction categories.
- `limit`: Maximum number of transactions to return (default 100).

## Response Contract
```json
{
  "transactions": [
    {
      "id": "string",
      "date": "2023-01-01",
      "amount": 100.50,
      "category": "groceries",
      "description": "Supermarket purchase",
      "type": "debit"
    }
  ],
  "total_count": 50,
  "has_more": false
}
```

**Field Definitions:**
- `transactions`: Array of transaction objects.
  - `id`: Transaction identifier.
  - `date`: Transaction date.
  - `amount`: Transaction amount (positive for credit, negative for debit).
  - `category`: Categorized expense type.
  - `description`: Merchant or transaction description.
  - `type`: "credit" or "debit".
- `total_count`: Total transactions in the period.
- `has_more`: Boolean indicating if more data is available.

## Error Handling
- **400 Bad Request**: Invalid request parameters.
- **401 Unauthorized**: Authentication failure.
- **403 Forbidden**: Insufficient permissions.
- **500 Internal Server Error**: API service error.

## Lambda Gateway Wrapper
All calls to this API are proxied through an AWS Lambda function exposed via AgentCore gateway. The Lambda validates inputs, applies rate limiting, and logs access for compliance.