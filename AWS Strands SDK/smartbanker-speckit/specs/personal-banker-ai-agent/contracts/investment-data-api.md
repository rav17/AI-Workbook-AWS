# Contract: Investment Data API

## Overview
The Investment Data API provides access to market data, investment products, and portfolio information for risk-aware investment guidance.

## Endpoint
- **URL**: `https://api.investment.com/data`
- **Method**: POST
- **Authentication**: AWS IAM + API Key

## Request Contract
```json
{
  "query_type": "market_data|portfolio|products",
  "customer_id": "string",
  "parameters": {
    "symbols": ["AAPL", "GOOGL"],
    "risk_level": "low|medium|high",
    "amount": 10000
  }
}
```

**Field Definitions:**
- `query_type`: Type of data requested.
- `customer_id`: Customer identifier.
- `parameters`: Query-specific parameters.

## Response Contract
```json
{
  "data": [
    {
      "symbol": "AAPL",
      "price": 150.00,
      "change_percent": 2.5,
      "risk_rating": "medium"
    }
  ],
  "recommendations": [
    {
      "product_id": "string",
      "name": "Balanced Fund",
      "suitability_score": 0.8,
      "expected_return": 7.5
    }
  ]
}
```

**Field Definitions:**
- `data`: Market or portfolio data.
- `recommendations`: Suggested investment products.

## Error Handling
- **400 Bad Request**: Invalid parameters.
- **401 Unauthorized**: Authentication failure.
- **404 Not Found**: Data not available.
- **500 Internal Server Error**: Service error.

## Lambda Gateway Wrapper
Proxied through AWS Lambda with validation and compliance checks.