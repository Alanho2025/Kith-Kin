# Clean Code Rules for Python FastAPI + React TypeScript Project

Version: 2.0.0
Status: mandatory rule set for future code changes
Scope: Python backend, FastAPI API layer, React frontend, TypeScript frontend logic, AI-agent assisted development

## Purpose

This file defines the clean code rules for this project.

The goal is not clever code.

The goal is low change cost.

A good change should make the system easier to read, easier to test, easier to extend, and safer to modify later.

This project uses:

- Python for backend logic
- FastAPI for API endpoints
- Pydantic for request and response schemas
- React for frontend UI
- TypeScript for frontend safety
- API contracts between backend and frontend
- Tests to protect important behavior
- AI coding tools when useful

The rule is simple:

If a change solves today's task but makes tomorrow's task harder, it is not clean code yet.

---

## 1. Core Standard

[Clean Code]

A change is acceptable only when it keeps the code:

- easy to read
- easy to extend
- easy to test
- easy to review
- low-risk to modify later

Prefer clear code over smart code.

Avoid changes that solve the current task but make the next task harder.

Readable code is not slow code. It is code that the next developer can change without needing a crime board and red string.

---

## 2. Responsibility Rule

[Clean Code]

One unit should own one clear job.

This applies to:

- function
- class
- module
- API endpoint
- React component
- custom hook
- service
- repository
- mapper
- formatter
- test file

### Function level

One function should do one job.

Split a function when it does more than one of these jobs:

- fetch data
- validate input
- transform data
- format display text
- update state
- persist data
- call an external service
- send a response
- handle security or permissions
- build a view model

If a function name needs `and`, it is usually too broad.

Good examples:

```python
build_interview_question_plan()
map_session_history_item()
format_report_score_band()
persist_session_transcript()
validate_upload_file()
```

Bad examples:

```python
handle_data()
process_thing()
do_report()
fix_info()
validate_and_save_and_send()
```

### Module level

One file should own one clear responsibility group.

Do not mix:

- persistence and display formatting
- business rules and HTTP response control
- database query logic and LLM prompt logic
- page layout and large display transformation logic
- React rendering and browser runtime control
- API calls and view model formatting
- Pydantic schema and database model logic
- test helpers and production logic

If a file needs many comments to explain why unrelated code lives together, the file is probably doing too much.

---

## 3. Architecture Boundary Rule

[Clean Architecture]

The system should have clear boundaries.

Backend and frontend should not leak their internal details into each other.

Backend owns:

- data validation
- business rules
- persistence
- authentication and authorization
- API response shape
- external service integration
- server-side error handling

Frontend owns:

- user interaction
- UI state
- rendering
- view model display
- browser APIs
- client-side error display
- user-facing recovery actions

Shared responsibility:

- API contract
- naming consistency
- error code consistency
- test coverage for important flows

Avoid:

- frontend depending on raw database names
- backend returning unstable internal objects
- components reading deeply nested backend response fields
- backend services formatting frontend text
- frontend duplicating backend business rules
- hidden assumptions that only exist in one layer

The API contract is the handshake. Do not make it a secret handshake.

---

## 4. FastAPI Backend Layer Rule

[FastAPI] [Clean Architecture]

Backend files must keep clear boundaries.

Use these roles:

- `router`: APIRouter registration and route grouping only
- `endpoint handler`: request orchestration, dependency injection, response mapping only
- `dependency`: database session, auth, settings, external client, request context only
- `schema`: request and response shape only
- `service`: business logic and workflow only
- `repository`: database query and persistence only
- `domain`: core business rules, domain objects, domain errors
- `infrastructure`: external APIs, file storage, email, LLM, vector DB, speech service
- `utility`: pure reusable helper logic only
- `middleware`: request pre-processing, security, logging, tracing, rate limiting

### Rules

A router should not contain business logic.

An endpoint handler should not contain heavy domain logic.

A service should not import or depend on:

- `Request`
- `Response`
- `Depends`
- `HTTPException`
- FastAPI status codes
- FastAPI routing objects

A repository should not format data for the frontend.

A schema should not call the database.

A dependency should not hide a business workflow.

A utility should not silently depend on database state, request state, or environment state.

### Good backend flow

```text
router
  -> endpoint handler
    -> dependency provides database or user context
    -> service runs business workflow
      -> repository reads or writes data
      -> infrastructure calls external systems
    -> endpoint maps result to response schema
```

### Bad backend flow

```text
endpoint
  -> validates input manually
  -> queries database directly
  -> calls LLM directly
  -> formats frontend text
  -> catches all errors
  -> returns inconsistent response shape
```

That is not an endpoint. That is a tiny haunted house.

---

## 5. FastAPI Endpoint Rule

[FastAPI] [Clean Code]

Endpoint handlers should be thin.

An endpoint may:

- accept request schema
- receive dependencies
- call one service method
- map service result to response schema
- raise or map expected API errors
- return the response

An endpoint should not:

- contain SQL queries
- contain long business rules
- build complex prompts
- call external APIs directly
- handle many unrelated branches
- format large user-facing messages
- mutate data in multiple places
- contain logic that is hard to unit test

Good example:

```python
@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    request: CreateSessionRequest,
    service: SessionService = Depends(get_session_service),
) -> SessionResponse:
    result = await service.create_session(request.to_command())
    return SessionResponse.from_domain(result)
```

Bad example:

```python
@router.post("/sessions")
async def create_session(request: Request):
    body = await request.json()
    # validate fields
    # query user
    # build prompt
    # call LLM
    # save result
    # format UI text
    # handle every exception
    return {"data": "..."}
```

Thin endpoints make tests easier and bugs less dramatic.

---

## 6. Pydantic Schema Rule

[Pydantic] [API Contract]

Pydantic models should define clear API boundaries.

Do not use one model for every layer.

Use separate models when responsibilities differ:

- request schema: input validation
- response schema: public API output
- domain object: business meaning
- ORM model: database persistence
- internal DTO: service-to-service data transfer
- command object: service input
- result object: service output

### Naming

Use clear names:

```python
CreateSessionRequest
SessionResponse
SessionDomain
SessionRecord
CreateSessionCommand
CreateSessionResult
```

Avoid vague names:

```python
SessionData
SessionModel
SessionInfo
ThingSchema
ResponseData
```

### Rules

Request schemas should validate external input.

Response schemas should expose only safe public fields.

Domain objects should express business meaning.

ORM models should reflect persistence needs.

Internal DTOs should support service boundaries.

Do not return ORM objects directly from API endpoints.

Do not expose internal database fields unless they belong in the public API.

Do not put business workflow inside Pydantic validators.

Validators should validate shape and simple field rules. Services should handle business decisions.

### Smells

[Code Smell]

Review the code when:

- one Pydantic model is used for request, response, database, and domain
- response schema exposes fields that frontend does not need
- schema names are vague
- validators call database or external APIs
- schema contains too many optional fields because no one knows the real shape
- frontend depends on backend private field names

---

## 7. Python Safety Rule

[Python] [Clean Code]

Python code should be explicit and predictable.

Prefer:

- clear function names
- type hints for public functions
- small pure functions
- dataclasses or Pydantic models for structured data
- early returns for invalid inputs
- explicit error handling
- dependency injection over hidden globals
- immutable data where practical
- readable control flow over clever one-liners

Avoid:

- hidden mutation
- mutable default arguments
- broad `except Exception` without a clear reason
- magic strings repeated across files
- unclear dictionaries with unknown shape
- large functions with mixed abstraction levels
- global mutable runtime state
- import-time side effects
- silent fallback values that hide broken data

### Good example

```python
def calculate_score_band(score: float) -> ScoreBand:
    if score < 0 or score > 1:
        raise ValueError("score must be between 0 and 1")

    if score >= 0.8:
        return ScoreBand.HIGH

    if score >= 0.5:
        return ScoreBand.MEDIUM

    return ScoreBand.LOW
```

### Bad example

```python
def calc(x):
    try:
        return "high" if x > .8 else "med" if x > .5 else "low"
    except:
        return "low"
```

Do not hide bugs under friendly defaults. Bugs love blankets.

---

## 8. TypeScript Safety Rule

[TypeScript] [Clean Code]

TypeScript should reduce uncertainty, not decorate JavaScript.

Avoid unsafe escape hatches:

- `any`
- `unknown` without narrowing
- type assertion used to silence real uncertainty
- non-null assertion unless the invariant is obvious
- duplicated API response types
- broad object types like `Record<string, any>`
- optional fields used because the real state is unclear

Prefer:

- strict TypeScript settings
- explicit API DTO types
- discriminated unions for state
- type guards for unknown data
- shared constants for statuses and event names
- typed component props
- typed hook return values
- typed API client methods

### Good state model

```ts
type LoadState<T> =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; data: T }
  | { status: "error"; message: string };
```

### Bad state model

```ts
const [loading, setLoading] = useState(false);
const [error, setError] = useState("");
const [data, setData] = useState(null);
```

The bad version can create impossible states, such as loading and error at the same time.

### Smells

[Code Smell]

Review the code when:

- `any` appears in feature code
- API response is cast instead of parsed or normalized
- non-null assertion is used to force the compiler to be quiet
- component props are too broad
- one type has many optional fields because state is unclear
- frontend status strings are repeated in many files

The compiler is not your enemy. It is the friend who tells you your zipper is open.

---

## 9. Dependency Injection Rule

[FastAPI] [Design Pattern]

FastAPI dependencies should inject resources, not hide business logic.

Good dependency usage:

- database session
- current user
- permission context
- settings
- external API client
- request-scoped correlation id
- service instance
- repository instance

Bad dependency usage:

- running full business workflows
- mutating database state
- formatting response text
- calling LLM directly
- triggering email or external side effects
- hiding permission decisions that should be visible in service logic

### Rule

Dependencies should make requirements explicit.

If a dependency changes data, calls external systems, or decides a business outcome, review it.

### Good example

```python
def get_session_service(
    repository: SessionRepository = Depends(get_session_repository),
    llm_client: LlmClient = Depends(get_llm_client),
) -> SessionService:
    return SessionService(repository=repository, llm_client=llm_client)
```

### Bad example

```python
def get_ready_session():
    # reads request
    # creates session
    # calls LLM
    # saves result
    # returns final response
```

Dependency injection is for wiring. It is not a magic tunnel for hidden behavior.

---

## 10. Async and Blocking I/O Rule

[FastAPI] [Performance] [Clean Code]

Use async only when the called library supports await.

Do:

- use `async def` when calling async database, HTTP, file, queue, or client code
- use `await` for real async operations
- keep async flow clear
- isolate long-running work into a task or background layer
- use normal `def` when calling blocking sync libraries

Avoid:

- fake async with blocking I/O
- calling sync database or file code inside async endpoint without planning
- mixing async and sync control flow in one service without a clear reason
- creating fire-and-forget tasks without logging, ownership, or failure handling
- hiding slow external calls inside mappers or formatters

### Rule

If a function is async, its reason should be obvious.

If a function blocks, its blocking behavior should be obvious.

### Smells

[Code Smell]

Review the code when:

- `async def` contains blocking file or network code
- a service has both async and sync versions of the same method
- background work has no error handling
- endpoint waits on slow work that could be queued
- a helper secretly calls external services

Async is powerful. Fake async is just sync wearing sunglasses.

---

## 11. Lifespan and Resource Rule

[FastAPI] [Infrastructure]

Shared resources should be created and cleaned through application lifespan or explicit dependency providers.

Use lifespan or dependency providers for:

- database engine or pool
- external API client
- LLM client
- vector database client
- cache client
- speech service client
- loaded model
- file storage client

Avoid:

- loading heavy clients at import time
- creating database engines inside endpoint functions
- creating LLM or vector clients repeatedly per request
- global mutable runtime state without lifecycle control
- resource cleanup hidden in random functions

### Rule

Heavy resources need clear ownership.

If a resource is expensive, shared, or needs cleanup, define where it starts and where it stops.

---

## 12. Database and Repository Rule

[Repository Pattern] [Persistence]

Repositories own persistence.

A repository may:

- build database queries
- create records
- update records
- delete records
- map database rows to repository records
- handle transaction-level persistence details when required

A repository should not:

- decide business strategy
- format frontend text
- call LLMs
- build API responses
- read from React-specific concepts
- hide permission checks unless it is a data access rule
- return raw database rows to frontend-facing code

### Service and repository boundary

Service asks:

```text
What business action should happen?
```

Repository asks:

```text
How do we read or write the data?
```

### Good examples

```python
session = await session_repository.get_by_id(session_id)
await session_repository.save_transcript(session_id, transcript)
```

### Bad examples

```python
await session_repository.generate_interview_feedback_and_save(...)
await session_repository.get_pretty_report_for_frontend(...)
```

### Transaction rule

Transaction ownership should be clear.

For simple use cases, repository may commit if the project standard allows it.

For multi-step business workflows, service or unit-of-work layer should own transaction control.

Do not mix commit patterns randomly.

---

## 13. API Contract Rule

[API Contract] [Backend Frontend Boundary]

API contracts must be stable, explicit, and normalized.

Backend should return documented response schemas.

Frontend API modules should normalize backend responses before exposing them to components.

Components should not know raw backend response shapes unless the shape is stable and documented.

### Prefer

```text
fetchSession() returns SessionViewData
parseCv() returns { parsedCv, warnings }
parseJd() returns { parsedJd, warnings }
matchCvToJd() returns { matchResult, evidence, warnings }
generateReport() returns { report, warnings }
```

### Avoid

- reading deeply nested response fields inside page components
- repeating fallback logic across components
- mixing fetch logic with display formatting
- returning different shapes for the same API state
- returning raw exception strings to frontend
- leaking database field names into UI logic

### Error shape

Expected API failures should use a consistent error shape.

Example:

```json
{
  "error": {
    "code": "SESSION_NOT_FOUND",
    "message": "Session was not found.",
    "requestId": "req_123"
  }
}
```

Unexpected API failures should keep enough debug context in logs but show users a clear action-based message.

### Frontend rule

Frontend should map API error codes to user-facing messages in one place.

Do not repeat API error handling across many components.

---

## 14. Error Handling Rule

[Clean Code] [Reliability]

Error handling must be consistent.

### Backend

Expected errors should use shared domain errors or a shared error pattern.

Unexpected errors should bubble to the global handler.

Do not mix these patterns for the same kind of failure without a reason:

- `raise`
- `return None`
- `return { "ok": false }`
- direct HTTP response
- broad catch and fallback

Services should raise domain errors or return explicit result objects.

Endpoint handlers or exception handlers should map errors to HTTP responses.

Backend errors should preserve enough context for debugging without exposing:

- secrets
- tokens
- passwords
- private user data
- sensitive health or identity information
- raw external provider response when unsafe

### Frontend

Separate frontend errors into:

- user-facing errors
- recoverable runtime errors
- developer/debug errors

Rules:

- loading state pattern should be consistent
- empty state pattern should be consistent
- error state pattern should be consistent
- user-facing errors should be clear and action-based
- recoverable runtime errors should expose recovery state when possible
- developer errors should be logged with context but not shown directly to users

Important flows should not fail silently.

Examples:

- upload
- parsing
- matching
- report generation
- voice session
- WebSocket session
- payment or external submission if added later

### Smells

[Code Smell]

Review the code when:

- `except Exception` returns a success response
- service raises `HTTPException`
- frontend shows raw backend error details
- expected errors return different shapes
- logs contain sensitive data
- a failed operation has no visible recovery path
- retry logic exists in three different places

---

## 15. React Component Rule

[React] [Clean Code]

Components should primarily render UI.

A component may contain:

- simple event handlers
- simple conditional rendering
- simple local UI state
- simple mapping over already-prepared display data

A component should not contain:

- large data transformation logic
- business rules
- network request implementation
- WebSocket lifecycle logic
- audio stream lifecycle logic
- repeated response normalization logic
- complex scoring, matching, or report-generation logic
- API error mapping
- large permission logic

When a component starts managing feature flow, extract a custom hook.

When a component starts transforming data heavily, extract a mapper or builder.

When a component repeats UI with stable behavior and a clear name, extract a reusable component.

Do not extract repeated JSX only because it looks similar.

Small JSX duplication is acceptable when extraction would create unclear props or reduce readability.

### Good component role

```text
receive prepared props
render UI
call handler props or hook actions
show loading, empty, error, and success states
```

### Bad component role

```text
fetch data
parse response
calculate score
build prompt
manage WebSocket
format report
render UI
```

That is not a component. That is a startup in a trench coat.

---

## 16. React Hook Rule

[React] [Clean Code]

Custom hooks should own one feature-level behavior.

Good examples:

```ts
useVoiceInterviewSession()
useCvUpload()
useMatchAnalysis()
useSessionReport()
useWebSocketConnection()
useAudioRecorder()
```

A hook should not mix unrelated responsibilities.

Avoid hooks that manage all of these in one file:

- UI state
- API calls
- large response transformation
- browser APIs
- timers
- WebSocket lifecycle
- display text formatting
- business rules
- report generation logic

If a hook grows too broad, split it into:

- runtime hook
- state hook
- API helper
- pure mapper
- UI formatter
- service-like frontend module

A hook should expose a small and clear interface to components.

Avoid returning large bags of unrelated state and handlers.

### Smells

[Code Smell]

Review the code when:

- hook return object has more than 8 to 10 fields
- hook imports many unrelated modules
- hook owns several lifecycle flows
- hook knows too much about backend response shape
- hook contains business rules that should be backend-side
- hook cannot be tested without rendering a full page

---

## 17. React Effect Rule

[React] [Side Effects]

Use `useEffect` only for real side effects.

Good uses include:

- network synchronization
- browser API subscription
- WebSocket lifecycle
- audio or media stream lifecycle
- timer setup and cleanup
- external storage synchronization
- event listener setup and cleanup

Do not use `useEffect` for:

- deriving display values
- copying props into state without a clear reason
- formatting data
- running business rules that can be pure functions
- hiding control flow that should be handled by an event handler
- fixing state design problems with more state

Every effect must have:

- one clear purpose
- a correct dependency list
- cleanup when it subscribes, listens, streams, or starts timers

If an effect becomes hard to explain, split it.

If an effect causes repeated re-renders, fix the state flow instead of adding guards everywhere.

### Smells

[Code Smell]

Review the code when:

- effect sets state that could be derived during render
- effect has a very large dependency list
- effect ignores dependency warnings without explanation
- effect starts a timer or subscription without cleanup
- effect controls too many unrelated flows
- effect exists only to patch a previous state update

---

## 18. React State Ownership Rule

[React] [State Management]

Each piece of state must have one owner.

Prefer:

- local component state for temporary UI state
- custom hook state for one feature flow
- context only for cross-page or cross-feature state
- backend as the source of truth for persisted session, user, report, and uploaded document data
- URL params for shareable navigation state
- query/cache layer only when the project clearly needs it

Avoid:

- duplicating backend data into multiple local states
- storing derived values as state
- passing state through many layers when a feature hook or context is clearer
- using `localStorage` as the source of truth for important application data
- updating the same state from multiple unrelated places
- storing API raw response and view model separately without a clear reason

Derived values should usually be calculated with pure functions or memoized values.

Persisted data should be reloaded or invalidated in a predictable way.

### Good question

```text
Who owns this state?
```

If the answer is unclear, fix that before adding more code.

---

## 19. Frontend API Boundary Rule

[Frontend] [API Contract]

Frontend API modules own network communication.

API module owns:

- fetch implementation
- request construction
- response parsing
- response normalization
- error mapping
- DTO type
- retry behavior if needed
- auth header attachment if needed

Components should not:

- call `fetch` directly
- know raw backend error shape
- parse backend response deeply
- repeat loading and error mapping logic
- build API URLs manually in many places

Hooks may call API modules.

Components may call hook actions.

This keeps network details out of UI.

### Good flow

```text
component
  -> custom hook
    -> API module
      -> backend
```

### Bad flow

```text
component
  -> fetch
  -> parse JSON
  -> handle error codes
  -> normalize response
  -> render UI
```

---

## 20. Predictable Data Flow Rule

[Clean Code]

Input shape should be clear.

Output shape should be clear.

Side effects should be obvious.

Avoid:

- hidden mutation
- silent fallback values that hide real bugs
- functions that depend on unrelated external state
- deep nested property access in UI files
- broad object passing without clear shape
- mixing command and query behavior in the same function
- data transformation spread across many layers

Prefer:

- mapper for shape conversion
- formatter for text or display conversion
- builder for higher-level view model assembly
- factory for domain object creation
- normalized API output before data reaches components
- clear command objects for service inputs
- clear result objects for service outputs

### Rule

A reader should know:

- what goes in
- what comes out
- what changes
- what can fail

If those four things are unclear, the function needs redesign.

---

## 21. Design Pattern Usage Rule

[Design Pattern]

Use design patterns to reduce change cost, not to look professional.

Allowed common patterns:

- Repository: persistence boundary
- Service: business workflow
- Mapper: shape conversion
- Formatter: user-facing text conversion
- Builder: assembling view models or domain objects
- Factory: creating domain objects with defaults or invariants
- Adapter: external API, LLM, file storage, speech service, vector DB
- Strategy: interchangeable scoring, ranking, parsing, prompting logic
- Dependency Injection: explicit resource wiring
- Unit of Work: transaction boundary for multi-step persistence
- Facade: simple interface over complex subsystem, when needed

### When to introduce a pattern

Introduce a pattern only when:

- the responsibility is stable
- the name is clear
- it reduces future change cost
- it improves testing or replacement
- it prevents repeated logic
- the abstraction does not hide important behavior

### When not to introduce a pattern

Do not introduce a pattern when:

- there is only one simple use case
- the abstraction name is vague
- the pattern adds files but not clarity
- the team cannot explain why it exists
- it makes debugging harder
- it is only added because the code looks more serious

Patterns are tools. Do not use a chainsaw to cut tofu.

---

## 22. Code Smell Checklist

[Code Smell]

Review the code when you see any of these.

### General smells

- function name contains `and`
- vague names such as `data`, `info`, `thing`, `manager`, `helper`
- file has more than one responsibility
- large function with several abstraction levels
- same logic copied for the third time
- silent fallback hides broken data
- magic string repeated across files
- important behavior exists only in comments
- code needs too much context to review
- small change requires editing many unrelated files

### Backend smells

- endpoint contains database query and business rule together
- service imports FastAPI `Request`, `Response`, `Depends`, or `HTTPException`
- repository formats frontend response
- Pydantic schema is reused for request, response, database, and domain
- dependency runs business workflow
- async endpoint calls blocking sync I/O
- transaction ownership is unclear
- external API call is hidden inside mapper or formatter
- broad `except Exception` hides failure
- logs expose sensitive data

### Frontend smells

- React component calls API directly
- component contains scoring, matching, or report logic
- hook returns a large bag of unrelated state
- `useEffect` derives display data
- frontend stores derived values as state
- TypeScript uses `any` to bypass uncertainty
- non-null assertion hides missing data
- raw backend response reaches UI components
- same loading or error pattern is reimplemented many times
- component props become unclear or too broad

### Testing smells

- important business rule can only be tested through full end-to-end flow
- test depends on exact private implementation
- test setup is larger than the behavior being tested
- bug fix has no regression test
- tests mock the function under test instead of its boundary
- tests only check happy path for risky flows

Smells are not automatic failures. They are warning lights. Ignore enough of them and the engine becomes modern art.

---

## 23. Constants and Magic String Rule

[Clean Code]

Repeated domain strings must be centralized.

Examples:

- route names
- API paths
- error codes
- session statuses
- user roles
- permission names
- transcript statuses
- report score bands
- match result labels
- interview modes
- interview question types
- WebSocket event names
- localStorage keys
- feature flags
- external provider names

Avoid repeating string literals across components, hooks, services, repositories, tests, and schemas.

A shared string should have one owner.

If changing a label or status requires searching the whole project, it probably needs a constant.

### Backend example

```python
class SessionStatus(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
```

### Frontend example

```ts
export const SESSION_STATUS = {
  CREATED: "created",
  ACTIVE: "active",
  COMPLETED: "completed",
  FAILED: "failed",
} as const;
```

---

## 24. Duplication Rule

[Clean Code]

Repeated structure or repeated logic must not appear more than 3 times.

When a pattern appears for the third time, review it for extraction.

Extraction options include:

- helper
- mapper
- formatter
- builder
- factory
- shared component
- shared hook
- shared service
- shared constant
- shared test helper
- reusable API client method

Do not keep copy-paste variants with small text changes.

However, do not extract too early.

Small duplication is acceptable when extraction would create:

- unclear names
- unclear props
- weaker readability
- unnecessary indirection
- abstract code without stable meaning

Extract only when the repeated pattern has:

- the same responsibility
- similar behavior
- a stable name
- a clear owner

Duplication is cheaper than the wrong abstraction. But repeated copy-paste with tiny edits is how bugs learn mitosis.

---

## 25. Change-Friendly Design Rule

[Design]

When adding a feature, prefer adding a new focused module over modifying a large old module.

Target pattern:

```text
new feature
  -> new route if needed
  -> new service if business workflow is new
  -> new repository method if persistence query is new
  -> new schema if API shape is new
  -> new component or hook if UI flow is new
  -> new mapper or builder if shape conversion is new
```

Avoid:

```text
new feature
  -> keep stuffing logic into one existing big file
```

A good change should affect the fewest responsible files possible.

Do not avoid touching the right file just to reduce file count.

Good design allows future features to be added by extension, not by large invasive edits.

### Rule

Before editing a large file, ask:

```text
Am I adding to the right responsibility, or am I making this file more powerful than it should be?
```

Powerful files are suspicious. They usually become monarchs.

---

## 26. Naming Rule

[Clean Code]

Names should explain intent.

Prefer names that describe business meaning.

Good examples:

```python
create_interview_session()
build_question_plan()
calculate_match_score()
save_transcript_chunk()
get_active_session_for_user()
```

```ts
InterviewSessionPage
QuestionCard
useInterviewRecorder
mapSessionResponseToViewModel
formatScoreBandLabel
```

Avoid names that hide meaning:

```python
process()
handle()
run()
manage()
fix()
do_stuff()
```

```ts
DataBox
MainThing
useManager
handleClick2
formatData
```

### Rules

Use verbs for actions.

Use nouns for data structures.

Use domain words consistently.

Do not use abbreviations unless they are common in the project.

Do not use one name for two different concepts.

Do not use two names for the same concept.

If the team cannot explain the difference between two names, merge or rename them.

---

## 27. Security and Privacy Rule

[Security] [AI Safety]

Security and privacy must be part of clean code.

Do not expose:

- API keys
- tokens
- passwords
- secrets
- private user documents
- raw CV content unless needed
- sensitive personal data
- private logs
- provider debug output
- hidden system prompts
- internal security rules

### Backend rules

- validate input at API boundary
- validate file type and file size
- avoid trusting client-provided user IDs
- use authorization checks before data access
- mask sensitive fields in logs
- do not return internal stack traces to users
- keep secret config outside source code
- use safe error messages
- document high-risk actions

### Frontend rules

- do not store sensitive data in localStorage unless there is a clear reason
- do not show raw debug errors to users
- do not expose hidden prompts or internal scoring rules if unsafe
- do not trust frontend-only validation
- clear temporary sensitive state when no longer needed

### AI-specific rules

If the project uses LLMs:

- separate system prompt, developer prompt, and user input
- treat retrieved documents as untrusted input
- guard against prompt injection
- keep human confirmation for high-risk external actions
- do not send sensitive data to unapproved providers
- keep prompt and model behavior documented
- store enough trace data for debugging without leaking private data

Clean code that leaks secrets is not clean. It is just well-formatted danger.

---

## 28. AI and External Service Adapter Rule

[Adapter Pattern] [AI Engineering]

External providers should be isolated behind adapter interfaces.

Examples:

- LLM provider
- speech-to-text provider
- text-to-speech provider
- email provider
- file storage provider
- vector database
- payment provider
- calendar provider
- third-party API

### Rules

Do not call external providers directly from:

- React components
- FastAPI endpoints
- repositories
- mappers
- formatters
- Pydantic validators

Use an adapter or infrastructure client.

The adapter should handle:

- provider request shape
- provider response shape
- timeout
- retry if safe
- provider error mapping
- logging context
- response normalization

The service should depend on the adapter interface, not provider details.

### Good example

```python
feedback = await feedback_generator.generate_feedback(transcript)
```

### Bad example

```python
response = await openai_client.chat.completions.create(...)
```

inside an endpoint or component-level equivalent.

This makes provider switching easier.

If DeepSeek, Gemini, OpenAI, Azure, or local models change, the whole app should not need a group therapy session.

---

## 29. Logging and Observability Rule

[Reliability]

Logs should help debugging without leaking sensitive data.

Backend logs should include:

- request id or correlation id
- operation name
- safe user or session reference when allowed
- error code
- failure location
- external provider name when relevant
- duration for slow operations

Do not log:

- passwords
- tokens
- full CV text
- full private documents
- raw user secrets
- full LLM prompts with sensitive data
- raw provider responses that may contain private data

### Rule

Every important failure should be traceable.

Every sensitive value should be protected.

### Smells

[Code Smell]

Review the code when:

- logs only say `something went wrong`
- logs expose raw request body
- slow operations have no timing
- external provider errors are swallowed
- frontend error cannot be connected to backend logs
- no request id exists for important flows

---

## 30. Testing Rule

[Testability]

Code should be structured so important logic can be tested in isolation.

Prefer extracting:

- pure functions
- builders
- formatters
- mappers
- narrow services
- repository methods
- API modules with normalized return shapes
- custom hooks with clear state transitions
- adapters with mocked external clients

Avoid burying core logic inside:

- giant endpoint handlers
- giant page components
- giant custom hooks
- controller-only flows
- mixed persistence and formatting functions
- UI event handlers that also contain business rules

### Backend testing boundary

Prefer testing:

- pure domain functions with unit tests
- services with mocked repositories and adapters
- repositories with test database when needed
- API endpoints with FastAPI TestClient or async client
- error mapping through focused API tests
- permission checks with dependency overrides

Avoid tests that:

- require real external API calls
- depend on production secrets
- test too many layers at once
- mock the function being tested
- only verify status code but not response shape
- ignore failure paths

### Frontend testing boundary

Prefer testing:

- pure mappers and builders with unit tests
- custom hooks for state transitions
- API modules with mocked network responses
- components by user-visible behavior
- voice or session runtime behavior through focused mocks

Avoid tests that depend on:

- private component state
- exact DOM structure unless required
- implementation-specific hook calls
- large end-to-end flows for logic that could be unit tested

### Regression rule

When fixing a bug, add a test that would have failed before the fix.

No regression test means the bug gets a return ticket.

---

## 31. Size Warning Rule

[Code Smell]

These are warning thresholds, not hard blockers.

Hitting a threshold means review is needed.

Line count is weaker than responsibility count.

A 90-line file with 4 responsibilities is worse than a 180-line file with one clear responsibility.

### Backend warning thresholds

Review when above:

- router file: 120 lines
- endpoint module: 160 lines
- service file: 220 lines
- repository file: 200 lines
- schema file: 180 lines
- dependency file: 120 lines
- utility file: 160 lines
- function: 40 lines
- class: 180 lines

### Frontend warning thresholds

Review when above:

- page file: 220 lines
- feature component file: 160 lines
- reusable UI component: 120 lines
- custom hook: 130 lines
- API module: 160 lines
- mapper or builder file: 160 lines
- formatter file: 120 lines
- runtime module: 180 lines
- function: 40 lines

If a file grows past the threshold, stop and check whether responsibility has started to blur.

Do not split files only to satisfy line count.

Split files when responsibilities are clearer after the split.

---

## 32. Review Rule

[Collaboration]

Every change should reduce these risks:

- merge conflict risk
- unclear ownership
- broad side effects
- hard-to-review diffs
- inconsistent patterns
- hidden API contract changes
- hidden security risks
- hidden test gaps

Prefer:

- smaller focused files
- stable calling patterns
- clean shared utilities
- clear constants
- predictable API contracts
- small pull requests when possible
- direct test coverage for important behavior
- clear migration notes when contracts change

Avoid:

- broad rewrites without a clear reason
- changing formatting and logic in the same commit
- editing unrelated files in one change
- introducing a second pattern when one already exists
- changing API shape without updating frontend types
- changing backend errors without updating frontend error mapping
- merging generated code without reading it

### AI-generated code review

If AI writes or modifies code, review for:

- boundary leaks
- fake abstractions
- missing tests
- unsafe fallback values
- inconsistent naming
- hidden behavior
- invented imports
- outdated library usage
- security and privacy risks
- broken API contract
- over-engineering

AI can write fast. That does not mean it read the room.

---

## 33. Required Workflow for Future Changes

[Workflow]

For every future feature or refactor:

1. Read this file first.
2. Read the relevant code area.
3. Identify duplication, boundary leaks, oversized modules, unclear state ownership, and unsafe external calls.
4. Check the API contract before changing backend or frontend data shape.
5. Choose the smallest clean design that supports the feature.
6. Make the largest safe batch of changes possible.
7. Add or update tests for important behavior.
8. Run relevant tests, lint checks, and type checks.
9. Keep the change focused and reviewable.
10. Document important new patterns when they become reusable.

### Before changing backend API

Check:

- request schema
- response schema
- error shape
- frontend API module
- frontend DTO type
- frontend mapper or builder
- tests on both sides

### Before changing frontend flow

Check:

- state owner
- API module boundary
- component responsibility
- hook responsibility
- effect usage
- loading, empty, error, and success states
- accessibility and user-facing clarity

### Before using AI-generated code

Check:

- does it follow this file
- does it fit existing patterns
- does it create a new pattern without reason
- does it pass tests
- does it hide errors
- does it leak data
- does it make the next change easier

---

## 34. Packaging and Versioning Rule

[Release]

Every formal delivered package must:

- use version naming
- exclude `.git`
- exclude `node_modules`
- exclude `.env`
- exclude Python virtual environment folders
- exclude build noise when possible
- exclude cache folders
- include the latest relevant documentation
- include migration notes if API contracts changed
- include test instructions when needed

Version examples:

```text
project-clean-code-v2.0.0.zip
project-clean-code-v2.1.0.zip
project-clean-code-v2.2.0.zip
```

Do not create zip packages for every small normal development change unless a handoff requires it.

For normal development, use:

- Git branches
- pull requests
- tagged releases where appropriate
- changelog notes for meaningful API or architecture changes

---

## 35. Definition of Done for Clean Code

[Definition of Done]

A code area is aligned with this standard when:

- duplication is controlled
- responsibilities are separated
- names are clear
- data flow is predictable
- state ownership is clear
- side effects are isolated
- API contracts are normalized
- errors are handled consistently
- file size is reasonable
- important logic is testable
- backend layers do not leak FastAPI concerns into services
- frontend components do not own business logic
- TypeScript types reduce real uncertainty
- Python code is explicit and safe
- Pydantic schemas match their layer responsibility
- external providers are isolated behind adapters
- security and privacy risks are checked
- future features can be added by extension, not by large invasive edits

If a change makes the code harder to reason about, it is not clean code yet.

If a reviewer needs too much context to understand a change, the code probably needs clearer structure.

If a test is painful to write, the design may be trying to tell you something.

---

## 36. Quick Review Checklist

Use this checklist before approving a change.

### Boundary

- Does the endpoint stay thin?
- Does the service avoid FastAPI objects?
- Does the repository only handle persistence?
- Does the component mostly render UI?
- Does the hook own one clear behavior?
- Does the API module own fetch and normalization?

### Data

- Are request and response schemas clear?
- Are frontend DTO types aligned with backend responses?
- Are raw backend shapes kept out of components?
- Are derived values not stored as state?
- Are fallback values intentional?

### Errors

- Are expected errors consistent?
- Are unexpected errors logged safely?
- Are user-facing errors clear?
- Are sensitive details hidden?
- Is there a recovery path where possible?

### Patterns

- Is the pattern useful or just fancy?
- Does the abstraction have a stable name?
- Does it reduce future change cost?
- Can it be tested easily?

### Tests

- Is important logic tested close to its source?
- Is there a regression test for bug fixes?
- Are external services mocked or adapted?
- Do tests avoid private implementation details?

### AI-generated code

- Was the generated code reviewed?
- Does it follow existing project patterns?
- Did it invent unnecessary abstractions?
- Did it skip tests?
- Did it introduce hidden security or privacy risks?

---

## Final Rule

Clean code is not about making code look perfect.

Clean code is about making future change safe.

Every file should answer three questions:

```text
What is my job?
What do I depend on?
What can safely change without breaking the world?
```

If the answers are clear, the code is probably healthy.

If the answers are not clear, refactor before the project starts charging interest.
