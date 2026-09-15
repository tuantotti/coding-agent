---
name: requirement-analysis
description: Analyze a software change request against repository context and produce explicit, testable requirements before implementation.
---

# Requirement Analysis

Convert a software change request into an evidence-based specification that
can be handed to implementation and testing agents.

## Core Principle

Do not implement assumptions.

A requirement specification must distinguish what the user requested from
what the analyst inferred.

## Workflow

### 1. Understand the Requested Outcome

Identify:

- the requested change;
- the user-visible outcome;
- explicitly stated constraints;
- explicitly excluded behavior.

Do not interpret implementation details as requirements unless the user
specifically requires them.

### 2. Investigate Existing Behavior

Inspect repository evidence relevant to the request.

Prefer:

- existing implementations;
- interfaces;
- configuration;
- tests;
- related modules;
- documentation.

Use the repository-investigation skill when necessary.

State only behavior supported by repository evidence.

### 3. Identify Requirement Gaps

Determine whether any ambiguity materially affects:

- externally observable behavior;
- API contracts;
- data representation;
- compatibility;
- security;
- error handling;
- acceptance criteria.

Separate:

- Known
- Inferred
- Unknown

### 4. Define Scope

Explicitly state:

#### In Scope

Behavior necessary to satisfy the request.

#### Out of Scope

Behavior explicitly excluded or clearly unrelated.

#### Unknown

Behavior that cannot be determined from the request or repository.

### 5. Functional Requirements

Use stable IDs:

- FR-1
- FR-2
- FR-3

Each requirement should describe observable system behavior.

Example:

FR-1:
When the user searches menu items by title, the system shall perform a
case-insensitive search across both parent and child menu items.

### 6. Non-Functional Requirements

Only add non-functional requirements when supported by:

- the user request;
- existing system constraints;
- repository conventions;
- external specification.

Use:

- NFR-1
- NFR-2

Do not add generic engineering preferences.

### 7. Edge Cases

Identify meaningful boundary or failure cases.

Examples include:

- empty input;
- missing data;
- duplicated values;
- nested data;
- invalid state;
- incompatible existing behavior.

Only include cases relevant to the requested change.

### 8. Acceptance Criteria

Acceptance criteria must be:

- observable;
- testable;
- traceable to a requirement;
- independent of implementation details where possible.

Use:

- AC-1
- AC-2

Prefer Given / When / Then when appropriate.

### 9. Open Questions

Only ask questions whose answers materially change the implementation or
observable behavior.

Do not block implementation for minor details that can be safely derived from
existing repository conventions.

## Output Format

### Goal

### Current Behavior

### Desired Behavior

### Functional Requirements

### Non-Functional Requirements

### Constraints

### Edge Cases

### Acceptance Criteria

### Open Questions

### Repository Evidence
