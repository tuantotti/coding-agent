---
name: codebase-understanding
description: >
  Skill for the Programmer agent to read and understand the existing codebase
  before writing code. Triggers when Programmer receives project context,
  existing code, or needs to write code that fits into an existing codebase.
  Guides how to analyze project structure, conventions, and dependencies.
---

# Codebase Understanding
Before writing any code, understand the codebase it will live in. Good code that doesn't fit the project will still get rejected.

## Pre-coding Checklist

When you receive codebase context from Orchestrator or Information Retriever, check:

### 1. Project structure
- What language and framework is the project using?
- What folder structure convention is followed? (MVC, feature-based, layer-based...)
- Where should new files be placed?

### 2. Coding conventions
- Naming style: camelCase, snake_case, PascalCase?
- Indentation: tabs or spaces? How many spaces?
- Import style: absolute or relative?
- Is there a linting config (ESLint, Pylint, Rubocop...)? → Follow it

### 3. Patterns in use
- Error handling: throw exceptions, return error codes, or Result types?
- Async: callbacks, Promises, async/await?
- State management (if frontend): Redux, Zustand, Context...?
- Is dependency injection used?

### 4. Dependencies
- Don't add a new dependency if the codebase already has a library that does the same thing
- Example: project uses `lodash` → don't add `underscore` for the same purpose
- Example: project uses `axios` → don't use `fetch` unless there's a specific reason


## How to Read Code Quickly

When provided with existing code for reference:

1. **Read the public interface first**: function signatures, class APIs, exports — understand what the code does before understanding how it does it
2. **Find repeating patterns**: How the project handles a CRUD endpoint, a service, a test — then follow that pattern
3. **Pay attention to comments and TODOs**: They carry context that code alone doesn't express

## Applying to New Code

When writing new code inside an existing codebase:

- **Copy the style, not the code**: Learn how the project writes things, then write that way. Don't copy-paste and modify.
- **Consistent > "better"**: If the project uses callbacks everywhere, don't switch to async/await for your part. Consistency matters more than personal preference.
- **When you want to do it differently**: If the codebase has a clearly bad pattern, raise the concern to Orchestrator instead of going your own way. One part being different only adds inconsistency.