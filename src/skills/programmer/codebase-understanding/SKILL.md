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

## How to Read Code Quickly

When provided with existing code for reference:

1. **Read the public interface first**: function signatures, class APIs, exports — understand what the code does before understanding how it does it
2. **Find repeating patterns**: How the project handles a CRUD endpoint, a service, a test — then follow that pattern
3. **Pay attention to comments and TODOs**: They carry context that code alone doesn't express