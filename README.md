# RAG Recommendation API

A catalog-grounded recommendation service built with FastAPI, LangChain,
LangGraph, OpenAI, and Chroma.

## Architecture

`POST /v1/index/products` is the indexing phase: it converts products into
LangChain documents and upserts their OpenAI embeddings into a persistent
Chroma collection.

`POST /v1/recommendations` is the retrieval phase: a LangGraph pipeline
retrieves relevant products, then `ChatOpenAI` produces structured,
catalog-grounded recommendations.

## Setup

```bash
uv sync --all-groups
cp .env.example .env
# Edit .env and set OPENAI_API_KEY
uv run uvicorn main:app --app-dir src --reload
```

## Index a catalog

```bash
curl -X POST http://127.0.0.1:8000/v1/index/products \
  -H 'content-type: application/json' \
  -d '{"products":[{"id":"shoe-1","name":"Trail Runner","description":"Water-resistant shoe for technical trails.","category":"footwear","price":120,"attributes":{"terrain":"trail"}}]}'
```

## Request recommendations

```bash
curl -X POST http://127.0.0.1:8000/v1/recommendations \
  -H 'content-type: application/json' \
  -d '{"query":"I need a durable shoe for wet hiking trails","category":"footwear"}'
```

## Development

```bash
uv run ruff check .
uv run pytest
```

Vector data is persisted beneath `.data/chroma` and excluded from Git.
