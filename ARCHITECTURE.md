# Open WebUI + Snowflake Cortex Integration Demo

## Comprehensive Architecture & Security Documentation

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [What We're Demonstrating](#what-were-demonstrating)
3. [Architecture Overview](#architecture-overview)
4. [Security Model](#security-model)
5. [Design Decisions & Rationale](#design-decisions--rationale)
6. [MCP Architecture: How It Works](#mcp-architecture-how-it-works)
7. [Demo vs Production: What's Different](#demo-vs-production-whats-different)
8. [Why MCP + Per-User Identity Matters](#why-mcp--per-user-identity-matters)
9. [Test Results](#test-results)
10. [Key Takeaways](#key-takeaways)

---

## Executive Summary

This demo proves that **Open WebUI can serve as a unified AI frontend** that securely routes different users to different AI backends (RAG chatbot, Snowflake Cortex Analyst via MCP) while **preserving Snowflake's native security policies** including Row-Level Security (RLS) and data masking.

The key insight: **Snowflake's security enforcement happens at query execution time**, not at the application layer. By passing user-specific credentials (Bearer tokens) through the MCP protocol to Snowflake, we get enterprise security "for free" - the AI frontend doesn't need to implement complex access control logic because Snowflake already does it.

---

## What We're Demonstrating

### Primary Objectives

1. **Unified AI Interface**: A single chat interface (Open WebUI) that routes users to the appropriate AI service based on their access rights

2. **Security Pass-Through**: Snowflake's Row-Level Security and data masking policies are enforced automatically when users query data through an external AI frontend

3. **Per-User Authorization**: Different users see different data based on their Snowflake role, even though they're all using the same Open WebUI interface

4. **Feasibility Proof**: Organizations can adopt Open WebUI (or similar tools) as their AI frontend while maintaining Snowflake as their secure data backend

### The Four User Types

| User | Open WebUI Access | Snowflake Access | What They See |
|------|------------------|------------------|---------------|
| **web_user** | RAG Only | None | Technician reviews from PDF |
| **west_user** | Analyst Only | WEST_MANAGER role | WEST region data, PII masked |
| **east_user** | Analyst Only | EAST_MANAGER role | EAST region data, PII masked |
| **admin** | RAG + Analyst | ACCOUNTADMIN role | All data, nothing masked |

### Test Questions

Two questions test the complete access matrix:

1. **"Show me the details of Sarah Chen's performance review"** - Tests RAG access (knowledge base)
2. **"Show me drivers, their region and phone numbers"** - Tests Analyst access with RLS and masking

---

## Architecture Overview

### High-Level Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER BROWSER                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              OPEN WEBUI                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     MCP Analyst Router                               │    │
│  │                      (Filter Function)                               │    │
│  │                                                                      │    │
│  │   1. Identify user from session                                      │    │
│  │   2. Load user config (PAT, access flags)                           │    │
│  │   3. Determine query type (RAG vs Analyst)                          │    │
│  │   4. Check user authorization                                        │    │
│  │   5. Call Snowflake MCP Server with user's Bearer token             │    │
│  │   6. Execute returned SQL, return results (or access denied)        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                    │                              │                          │
│                    ▼                              ▼                          │
│  ┌──────────────────────────┐    ┌──────────────────────────────────────┐   │
│  │       ChromaDB           │    │     Snowflake MCP Server              │   │
│  │    (Vector Database)     │    │                                       │   │
│  │                          │    │   Authorization: Bearer <user's PAT>  │   │
│  │  Technician_Reviews.pdf  │    │   Method: tools/call                  │   │
│  │  embedded as vectors     │    │   Tool: trucking-analyst              │   │
│  └──────────────────────────┘    └──────────────────────────────────────┘   │
│                                                   │                          │
│                                                   ▼                          │
│                                  ┌──────────────────────────────────────┐   │
│                                  │   Snowflake Cortex Analyst            │   │
│                                  │   (via MCP Server)                    │   │
│                                  │                                       │   │
│                                  │   Token → User → Role → RLS/Masking   │   │
│                                  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component Details

#### 1. Open WebUI
- **Role**: User interface and session management
- **Authentication**: Local email/password accounts (demo) or OAuth SSO (production)
- **Extensibility**: Filter functions for custom routing, or native MCP support (v0.6.31+)

#### 2. MCP Analyst Router (Filter Function)
- **Location**: `/app/backend/data/functions/mcp_analyst_router.py`
- **Purpose**: Intercepts messages, routes to MCP Server or RAG, enforces access
- **MCP Endpoint**: `https://<account>.snowflakecomputing.com/api/v2/databases/SECURITY_WORKSHOP/schemas/TRUCKING/mcp-servers/TRUCKING_MCP`

#### 3. ChromaDB (RAG Backend)
- **Role**: Vector database for document retrieval
- **Data**: Technician_Reviews_2025.pdf embedded as vectors
- **Access**: Controlled by router function (not by ChromaDB itself)

#### 4. Snowflake MCP Server
- **Role**: Exposes Cortex Analyst as an MCP tool
- **Protocol**: JSON-RPC 2.0 (`tools/list`, `tools/call`)
- **Authentication**: Bearer token (PAT or OAuth) in Authorization header
- **Tool Name**: `trucking-analyst`
- **Semantic Model**: `SECURITY_WORKSHOP.TRUCKING.TRUCKING_SEMANTIC_VIEW`

#### 5. Snowflake RBAC
- **Role**: Enforces Row-Level Security and Data Masking
- **Trigger**: Bearer token maps to Snowflake user → user's role → policies applied
- **Key Point**: Security enforced by Snowflake, not the application

---

## Security Model

### The "Query First, Enforce on Results" Pattern

This is the critical architectural pattern that makes the demo work:

```
Traditional Approach (Application-Level Security):
┌─────────────────────────────────────────────────────────────┐
│  Application checks: "Can user X see region WEST?"          │
│  Application filters: "Add WHERE region = 'WEST' to query"  │
│  Application masks: "Replace phone with 'MASKED'"           │
│  ❌ Complex, error-prone, must duplicate Snowflake logic    │
└─────────────────────────────────────────────────────────────┘

Our Approach (Database-Level Security via MCP):
┌─────────────────────────────────────────────────────────────┐
│  Application sends: User's Bearer token + MCP tools/call    │
│  Snowflake MCP: Generates SQL via Cortex Analyst            │
│  Snowflake enforces: RLS automatically filters rows         │
│  Snowflake enforces: Masking policy hides PII               │
│  ✅ Simple, secure, single source of truth                  │
└─────────────────────────────────────────────────────────────┘
```

### How Snowflake Security Works in This Demo

#### Row-Level Security (RLS)

```sql
-- Snowflake Row Access Policy (simplified)
CREATE ROW ACCESS POLICY region_filter AS (region VARCHAR)
RETURNS BOOLEAN ->
  CASE
    WHEN IS_ROLE_IN_SESSION('ACCOUNTADMIN') THEN TRUE
    WHEN IS_ROLE_IN_SESSION('WEST_MANAGER') AND region = 'WEST' THEN TRUE
    WHEN IS_ROLE_IN_SESSION('EAST_MANAGER') AND region = 'EAST' THEN TRUE
    ELSE FALSE
  END;
```

**Result**: When `west_user` queries drivers, they only see WEST region rows - not because our code filtered them, but because Snowflake's RLS policy filtered them.

#### Data Masking

```sql
-- Snowflake Masking Policy (simplified)
CREATE MASKING POLICY phone_mask AS (val VARCHAR)
RETURNS VARCHAR ->
  CASE
    WHEN IS_ROLE_IN_SESSION('ACCOUNTADMIN') THEN val
    ELSE 'MASKED'
  END;
```

**Result**: When `west_user` sees driver phone numbers, they appear as "MASKED" - not because our code masked them, but because Snowflake's masking policy did.

### Security Mapping: Snowflake ↔ Open WebUI

| Layer | Snowflake | Open WebUI | How They Connect |
|-------|-----------|------------|------------------|
| **Identity** | Snowflake User | Open WebUI User | Mapped via `user_credentials.json` |
| **Authentication** | PAT (Personal Access Token) | Email/Password | PAT stored in config, used for API calls |
| **Authorization** | Roles (WEST_MANAGER, etc.) | Access flags | Role inherited from PAT, flags control routing |
| **Row Security** | Row Access Policies | N/A (pass-through) | Enforced by Snowflake when SQL executes |
| **Data Masking** | Masking Policies | N/A (pass-through) | Enforced by Snowflake when data returned |

### What's REAL Security vs Demo Simplification

| Security Layer | Real-World | Demo | Why Different |
|---------------|------------|------|---------------|
| **RLS filtering** | ✅ 100% Real | ✅ 100% Real | Snowflake enforces this regardless of caller |
| **Data masking** | ✅ 100% Real | ✅ 100% Real | Snowflake enforces this regardless of caller |
| **User authentication** | SSO/SAML/OAuth | Local accounts | Simplified for demo portability |
| **Credential management** | Vault/Secrets Manager | JSON config file | Simplified for demo setup |
| **User-PAT mapping** | IAM/Directory Service | Hardcoded JSON | Simplified for demo clarity |

---

## Design Decisions & Rationale

### Decision 1: Filter Function vs. LLM-Based Routing

#### What We Chose: Deterministic Filter Function

```python
def _is_analyst_query(self, query: str) -> bool:
    """Simple keyword-based detection for demo"""
    analyst_keywords = [
        'driver', 'truck', 'route', 'delivery', 'fleet',
        'shipment', 'cargo', 'mileage', 'fuel', 'maintenance'
    ]
    query_lower = query.lower()
    return any(keyword in query_lower for keyword in analyst_keywords)
```

#### Alternative: LLM-Based Routing

```python
def _is_analyst_query_llm(self, query: str) -> bool:
    """LLM-based intent classification (not used in demo)"""
    prompt = f"""Classify this query:
    - "analyst" if about trucking operations, drivers, routes, deliveries
    - "rag" if about employee reviews, performance, HR topics
    - "general" if neither
    
    Query: {query}
    Classification:"""
    
    response = llm.complete(prompt)
    return response.strip().lower() == "analyst"
```

#### Why We Chose Keyword Matching

| Factor | Keyword Matching | LLM Routing |
|--------|-----------------|-------------|
| **Latency** | ~0ms | 500-2000ms per query |
| **Cost** | $0 | $0.01-0.10 per query |
| **Predictability** | 100% deterministic | Probabilistic |
| **Demo Clarity** | Easy to explain | "Magic" black box |
| **Failure Modes** | Obvious misses | Subtle misclassifications |

**Key Insight**: For a demo, we want the audience to understand *exactly* why a query was routed to Analyst vs RAG. With keyword matching, we can say "it saw 'driver' so it went to Analyst." With LLM routing, the reasoning is opaque.

#### Production Recommendation

In production, consider a **hybrid approach**:

```python
def _route_query(self, query: str) -> str:
    # Fast path: Check for obvious keywords first
    if self._has_obvious_analyst_keywords(query):
        return "analyst"
    if self._has_obvious_rag_keywords(query):
        return "rag"
    
    # Slow path: Use LLM only for ambiguous queries
    return self._llm_classify(query)
```

This gives you:
- Fast routing for 80% of queries (obvious cases)
- Intelligent routing for 20% (ambiguous cases)
- Lower cost than routing everything through an LLM

### Decision 2: Using Open WebUI's Internal ChromaDB

#### The Problem

Open WebUI already runs a ChromaDB instance for its knowledge base feature. Creating a second ChromaDB client causes conflicts:

```
Error: "An instance of Chroma already exists for /app/backend/data/vector_db 
with different settings"
```

#### Our Solution

Import and use Open WebUI's existing singleton:

```python
from open_webui.retrieval.vector.factory import VECTOR_DB_CLIENT

def _get_chroma_client(self):
    if hasattr(VECTOR_DB_CLIENT, 'client'):
        return VECTOR_DB_CLIENT.client
    return VECTOR_DB_CLIENT
```

#### Why This Matters

1. **No conflicts**: We share the same ChromaDB instance
2. **Access to knowledge base**: Documents uploaded via Open WebUI's UI are accessible
3. **Consistent state**: No synchronization issues between separate databases

### Decision 3: Per-User PATs vs. Service Account

#### What We Chose: Per-User PATs

Each user has their own Snowflake PAT:
- `west_user` → PAT authenticates as `WEST_USER` with `WEST_MANAGER` role
- `east_user` → PAT authenticates as `EAST_USER` with `EAST_MANAGER` role
- `admin` → PAT authenticates as `admin` with `ACCOUNTADMIN` role

#### Alternative: Single Service Account

One PAT for all users, with application-level filtering:

```python
# NOT what we did - this would bypass Snowflake security
def query_analyst(user, query):
    # Use single service account PAT
    sql = analyst.generate_sql(query)
    
    # Application must add security filters
    if user.role == "WEST_MANAGER":
        sql += " WHERE region = 'WEST'"
    
    # Application must mask data
    results = execute(sql)
    if user.role != "ACCOUNTADMIN":
        results = mask_pii(results)
    
    return results
```

#### Why Per-User PATs Win

| Factor | Per-User PATs | Service Account |
|--------|--------------|-----------------|
| **Security Enforcement** | Snowflake (trustworthy) | Application (error-prone) |
| **Audit Trail** | User-level in Snowflake | Generic "service" user |
| **Policy Changes** | Update Snowflake, done | Update app code, redeploy |
| **Credential Scope** | Minimal (user's access only) | Maximal (service sees all) |

**The Core Principle**: Never implement in the application what the database can enforce. Snowflake's RLS and masking are battle-tested, audited, and centrally managed. Application-level security is a liability.

---

## MCP Architecture: How It Works

### What is MCP?

**Model Context Protocol (MCP)** is Anthropic's open standard for connecting AI assistants to external tools and data sources. Snowflake's managed MCP Server exposes Cortex Analyst as an MCP tool, enabling natural language to SQL via the standard MCP protocol.

### This Demo Uses MCP with Per-User Identity

**Key Insight**: MCP supports per-user authentication via Bearer tokens. Each user's token (PAT in demo, OAuth in production) is passed in the `Authorization` header, and Snowflake enforces RBAC based on that identity.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     MCP PROTOCOL FLOW (IDENTICAL IN DEMO & PRODUCTION)       │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌─────────────┐        ┌─────────────────┐        ┌─────────────────────┐
    │   User      │        │   Open WebUI    │        │  Snowflake MCP      │
    │  Browser    │        │                 │        │  Server             │
    └──────┬──────┘        └────────┬────────┘        └──────────┬──────────┘
           │                        │                            │
           │  "Show me drivers"     │                            │
           │───────────────────────>│                            │
           │                        │                            │
           │                        │  MCP tools/call            │
           │                        │  Authorization: Bearer     │
           │                        │  <user's token>            │
           │                        │───────────────────────────>│
           │                        │                            │
           │                        │                            │  Token → User Identity
           │                        │                            │  User → Role (WEST_MANAGER)
           │                        │                            │  Role → RLS + Masking
           │                        │                            │
           │                        │  SQL + Results             │
           │                        │  (filtered by RLS)         │
           │                        │<───────────────────────────│
           │                        │                            │
           │  Only WEST drivers     │                            │
           │  (phones masked)       │                            │
           │<───────────────────────│                            │
           │                        │                            │
```

### MCP Protocol Details

The MCP calls use standard JSON-RPC 2.0:

```json
// Request: tools/call
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "trucking-analyst",
    "arguments": {
      "message": "Show me drivers and their phone numbers"
    }
  }
}

// Response contains generated SQL and natural language explanation
{
  "result": {
    "content": [{
      "type": "text",
      "text": "[{\"text\":\"Here are the drivers...\",\"statement\":\"SELECT...\"}]"
    }]
  }
}
```

**The critical piece**: The `Authorization: Bearer <token>` header determines which Snowflake user identity executes the query. This is identical whether the token is a PAT (demo) or OAuth access token (production).

---

## Demo vs Production: What's Different

### The MCP Protocol Is Identical

| Component | Demo | Production | Difference |
|-----------|------|------------|------------|
| **MCP Endpoint** | Snowflake MCP Server | Snowflake MCP Server | None |
| **MCP Method** | `tools/call` | `tools/call` | None |
| **Authorization Header** | `Bearer <PAT>` | `Bearer <OAuth token>` | Token source only |
| **RBAC Enforcement** | Snowflake RLS/Masking | Snowflake RLS/Masking | None |
| **Audit Trail** | User-level | User-level | None |

### Only the Token Source Changes

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DEMO ARCHITECTURE                               │
│                          (PAT-based, for simplicity)                         │
└─────────────────────────────────────────────────────────────────────────────┘

    User logs into Open WebUI          Token lookup from config
    (local account)                    (user_credentials.json)
           │                                    │
           ▼                                    ▼
    ┌─────────────┐                    ┌─────────────────┐
    │ west_user   │ ──────────────────>│ PAT for         │
    │ @demo.local │                    │ WEST_USER       │
    └─────────────┘                    └────────┬────────┘
                                                │
                                                ▼
                                       Authorization: Bearer <PAT>
                                                │
                                                ▼
                                       ┌─────────────────────┐
                                       │  Snowflake MCP      │
                                       │  WEST_USER identity │
                                       │  RLS enforced       │
                                       └─────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                           PRODUCTION ARCHITECTURE                            │
│                      (OAuth SSO, for enterprise deployment)                  │
└─────────────────────────────────────────────────────────────────────────────┘

    User clicks "Login with Snowflake"     OAuth flow returns token
    (SSO via OIDC)                         (stored in session)
           │                                    │
           ▼                                    ▼
    ┌─────────────┐                    ┌─────────────────┐
    │ jsmith      │ ──────────────────>│ OAuth token for │
    │ @corp.com   │  Snowflake OAuth   │ JSMITH          │
    └─────────────┘                    └────────┬────────┘
                                                │
                                                ▼
                                       Authorization: Bearer <OAuth>
                                                │
                                                ▼
                                       ┌─────────────────────┐
                                       │  Snowflake MCP      │
                                       │  JSMITH identity    │
                                       │  RLS enforced       │
                                       └─────────────────────┘
```

### Why We Use PATs in the Demo

| Factor | PAT (Demo) | OAuth (Production) |
|--------|-----------|--------------------|
| **Setup Complexity** | Simple - generate PAT in Snowsight | Complex - OAuth Security Integration, OIDC config |
| **Portability** | Works anywhere with valid PATs | Requires OAuth provider configuration per environment |
| **Token Lifetime** | Long-lived (configurable) | Short-lived with refresh tokens |
| **Visibility** | Can explicitly show token being passed | Token handling is "invisible" (automatic) |
| **Demo Clarity** | Easy to explain to audience | More abstraction layers to explain |

**For an AI Architect**: The demo proves the architecture works. The only production change is replacing the PAT lookup with OAuth token retrieval - the MCP protocol, RBAC enforcement, and security model are identical.

### Production Upgrade Path

To move from demo to production:

1. **Create Snowflake OAuth Security Integration**:
```sql
CREATE SECURITY INTEGRATION openwebui_oauth
  TYPE = OAUTH
  OAUTH_CLIENT = CUSTOM
  ENABLED = TRUE
  OAUTH_REDIRECT_URI = 'https://your-openwebui.com/oauth/oidc/callback';
```

2. **Configure Open WebUI OIDC**:
```bash
OAUTH_CLIENT_ID=<from Snowflake>
OAUTH_CLIENT_SECRET=<from Snowflake>
OPENID_PROVIDER_URL=https://<account>.snowflakecomputing.com/.well-known/openid-configuration
OAUTH_SCOPES=openid email profile session:role:any
```

3. **Use Open WebUI's Native MCP Support** (v0.6.31+):
   - Admin Settings → External Tools → Add MCP Server
   - Auth Type: OAuth 2.1
   - Open WebUI automatically passes user's OAuth token to MCP

4. **Remove custom filter function** - native MCP handles everything

### What Stays the Same

- Snowflake MCP Server configuration
- Semantic View definition
- Row Access Policies
- Masking Policies
- Role hierarchy (WEST_MANAGER, EAST_MANAGER, etc.)
- All RBAC logic in Snowflake

---

## Why MCP + Per-User Identity Matters

### The Alternative: Service Account Anti-Pattern

Some implementations use a single service account for all MCP calls:

```
❌ ANTI-PATTERN: Service Account MCP
┌─────────────────────────────────────────────────────┐
│  All users → Single service account token           │
│  Snowflake sees: SERVICE_ACCOUNT (one identity)     │
│  Application must implement RLS logic               │
│  Application must implement masking logic           │
│  Audit trail shows: "SERVICE_ACCOUNT ran query"     │
└─────────────────────────────────────────────────────┘
```

This requires duplicating Snowflake's security in the application - error-prone and unauditable.

### Our Approach: Per-User Token Pass-Through

```
✅ CORRECT: Per-User MCP Authentication
┌─────────────────────────────────────────────────────┐
│  Each user → Their own token (PAT or OAuth)         │
│  Snowflake sees: The actual human user              │
│  RLS enforced automatically by Snowflake            │
│  Masking enforced automatically by Snowflake        │
│  Audit trail shows: "WEST_USER ran query"           │
└─────────────────────────────────────────────────────┘
```

### Proven in This Demo

The `demo_mcp_rbac.py` script proves MCP + per-user identity works:

```
=== WEST_USER Results ===
Drivers returned: 4 (WEST only)
Phone numbers: MASKED

=== EAST_USER Results ===  
Drivers returned: 4 (EAST only)
Phone numbers: MASKED

=== ADMIN Results ===
Drivers returned: 8 (all regions)
Phone numbers: VISIBLE
```

Same MCP endpoint, same query, different results based on user identity. This is exactly how production would behave with OAuth tokens.

---

## Test Results

### Complete Test Matrix

| User | Q1: Sarah Chen's Review | Q2: Drivers + Phone | Status |
|------|------------------------|---------------------|--------|
| **web_user** | ✅ Full review from RAG | ✅ Denied (no Analyst) | PASS |
| **west_user** | ✅ Denied (no RAG) | ✅ 4 WEST drivers, MASKED | PASS |
| **east_user** | ✅ Denied (no RAG) | ✅ 4 EAST drivers, MASKED | PASS |
| **admin** | ✅ Full review from RAG | ✅ 8 drivers, UNMASKED | PASS |

### Evidence of RLS Working

**west_user query**: "Show me drivers, their region and phone numbers"

```
DRIVER_ID | REGION | PHONE_NUMBER
----------|--------|-------------
DRV001    | WEST   | MASKED
DRV002    | WEST   | MASKED
DRV005    | WEST   | MASKED
DRV007    | WEST   | MASKED
```

- Only 4 rows returned (WEST region only)
- No EAST drivers visible
- Phone numbers masked

**admin query**: Same question

```
DRIVER_ID | REGION | PHONE_NUMBER
----------|--------|-------------
DRV001    | WEST   | 555-123-4567
DRV002    | WEST   | 555-234-5678
DRV003    | EAST   | 555-345-6789
DRV004    | EAST   | 555-456-7890
DRV005    | WEST   | 555-567-8901
DRV006    | EAST   | 555-678-9012
DRV007    | WEST   | 555-789-0123
DRV008    | EAST   | 555-890-1234
```

- All 8 rows returned (both regions)
- Phone numbers visible

**This proves**: The same MCP endpoint, same query, different results based solely on Snowflake's security policies tied to the user's Bearer token.

---

## Key Takeaways

### 1. MCP + Per-User Identity = Enterprise-Ready AI

This demo proves that Snowflake's managed MCP Server supports per-user authentication. The MCP protocol is identical between demo and production - only the token source changes (PAT vs OAuth).

### 2. Snowflake Security Is the Source of Truth

Don't rebuild security in your AI frontend. Use Snowflake's:
- Row Access Policies for row-level filtering
- Masking Policies for sensitive data protection
- Role-Based Access Control for authorization

### 3. Per-User Identity Enables Database-Level Security

By passing user-specific tokens (PATs or OAuth) to Snowflake MCP, you get:
- Automatic RLS enforcement
- Automatic data masking
- User-level audit trails
- Zero application-layer security code

### 4. Open WebUI Is a Viable Enterprise AI Frontend

Open WebUI supports:
- Native MCP integration (v0.6.31+) with OAuth 2.1
- OIDC SSO with Snowflake as identity provider
- Server-side OAuth session management with auto-refresh
- Custom filter functions for advanced routing logic

### 5. Demo Simplifications Don't Undermine the Architecture

We simplified:
- **Token source**: PATs (demo) vs OAuth (production)
- **User mapping**: JSON config vs LDAP/IdP
- **Routing logic**: Keywords vs LLM-based classification

But **these are identical** between demo and production:
- MCP protocol (`tools/call` with Bearer token)
- RBAC enforcement (Snowflake RLS + Masking)
- User identity flow (token → user → role → policies)
- Audit trail (user-level in Snowflake)

---

## Appendix: Configuration Files

### User Credentials (`/app/backend/data/user_credentials.json`)

```json
{
  "admin": {
    "snowflake_user": "admin",
    "pat": "ver:1:...",
    "has_analyst_access": true,
    "has_rag_access": true
  },
  "west_user": {
    "snowflake_user": "WEST_USER",
    "pat": "ver:1:...",
    "has_analyst_access": true,
    "has_rag_access": false
  },
  "east_user": {
    "snowflake_user": "EAST_USER",
    "pat": "ver:1:...",
    "has_analyst_access": true,
    "has_rag_access": false
  },
  "web_user": {
    "snowflake_user": null,
    "pat": null,
    "has_analyst_access": false,
    "has_rag_access": true
  }
}
```

### Filter Function Settings (Valves)

```python
class Valves(BaseModel):
    snowflake_account: str = "SFSENORTHAMERICA-JDREW"
    mcp_server_path: str = "SECURITY_WORKSHOP.TRUCKING.TRUCKING_MCP"
    warehouse: str = "SECURITY_WH"
    credentials_file: str = "/app/backend/data/user_credentials.json"
    knowledge_base_id: str = "6e2a5a65-ac3b-4c71-9cf4-84c2ac415885"
```

### MCP Server Configuration

```
MCP Server Name: TRUCKING_MCP
Database: SECURITY_WORKSHOP
Schema: TRUCKING
Semantic View: TRUCKING_SEMANTIC_VIEW
Tool Name: trucking-analyst

MCP Endpoint URL:
https://SFSENORTHAMERICA-JDREW.snowflakecomputing.com/api/v2/databases/SECURITY_WORKSHOP/schemas/TRUCKING/mcp-servers/TRUCKING_MCP
```

---

## Document Information

- **Version**: 2.0
- **Date**: March 3, 2026
- **Author**: Cortex Code (with human oversight)
- **Demo Environment**: Open WebUI v0.8.6, Docker, macOS
- **Snowflake Account**: SFSENORTHAMERICA-JDREW
- **MCP Server**: SECURITY_WORKSHOP.TRUCKING.TRUCKING_MCP

### Version History
| Version | Date | Changes |
|---------|------|---------|
| 1.0 | March 1, 2026 | Initial documentation |
| 2.0 | March 3, 2026 | Updated to reflect working MCP integration; added Demo vs Production comparison; removed outdated "Why Not MCP?" section |

---

*This documentation accompanies the Open WebUI + Snowflake Cortex Integration Demo. For questions or issues, refer to the demo's DEMO_ARCHITECTURE.md and DEMO_REALITY_CHECK.md files.*
