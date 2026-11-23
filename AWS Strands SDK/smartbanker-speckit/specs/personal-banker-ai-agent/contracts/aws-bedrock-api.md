# Contract: AWS Bedrock API

## Overview
AWS Bedrock provides foundation model access for text generation and embeddings used in planning, reasoning, and semantic memory.

## Text Generation Endpoint
- **Service**: bedrock-runtime
- **Method**: InvokeModel
- **Model**: Anthropic Claude 3.5 Sonnet (or configured model)

### Request Contract
```json
{
  "modelId": "anthropic.claude-3-5-sonnet-20240620-v1:0",
  "contentType": "application/json",
  "accept": "application/json",
  "body": {
    "anthropic_version": "bedrock-2023-05-31",
    "max_tokens": 1000,
    "messages": [
      {
        "role": "user",
        "content": "Analyze this spending data..."
      }
    ],
    "system": "You are a financial advisor..."
  }
}
```

### Response Contract
```json
{
  "content": [
    {
      "text": "Based on the data..."
    }
  ],
  "usage": {
    "input_tokens": 100,
    "output_tokens": 200
  }
}
```

## Embeddings Endpoint
- **Service**: bedrock-runtime
- **Method**: InvokeModel
- **Model**: Amazon Titan Text Embeddings V2

### Request Contract
```json
{
  "modelId": "amazon.titan-embed-text-v2:0",
  "contentType": "application/json",
  "accept": "application/json",
  "body": {
    "inputText": "Spending pattern: frequent dining out"
  }
}
```

### Response Contract
```json
{
  "embedding": [0.1, 0.2, ...],
  "inputTextTokenCount": 5
}
```

## Error Handling
- **ValidationException**: Invalid request.
- **ThrottlingException**: Rate limit exceeded.
- **InternalServerException**: Bedrock service error.

## Integration Notes
- All calls made through boto3 client.
- Model access must be enabled in Bedrock console.
- Costs monitored via AWS billing.