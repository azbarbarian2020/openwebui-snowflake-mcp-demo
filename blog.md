# Building Enterprise AI Interfaces with Snowflake: From Custom Front-Ends to Snowflake Intelligence

## Introduction

As enterprises adopt AI-powered data interfaces, architects face critical decisions about where to place orchestration logic, how to handle multi-modal data access (structured + unstructured), and—most importantly—how to maintain governance and security throughout.

This article explores the architectural spectrum, from custom front-ends like Open WebUI to Snowflake Intelligence, examining the trade-offs, security implications, and realistic implementation patterns.

**Key Premise**: While Snowflake Intelligence provides the most seamless experience for organizations whose data primarily resides in Snowflake, many enterprises have existing AI initiatives with established front-ends. Understanding how to integrate these with Snowflake's AI capabilities—while maintaining governance—is essential.

**The Core Insight**: Snowflake's security enforcement happens at query execution time, not at the application layer. By passing user-specific credentials through the MCP protocol, we get enterprise security "for free"—the AI frontend doesn't need complex access control logic because Snowflake already enforces it.

---

## Part 1: The Architectural Spectrum

### Option A: Snowflake Intelligence (Recommended for Snowflake-Centric Organizations)

**What It Is**: Snowflake Intelligence is Snowflake's native conversational interface that orchestrates multiple Cortex Agents, each capable of combining Cortex Analyst (structured data) and Cortex Search (unstructured data) tools.

**Architecture**:
```
┌─────────────────────────────────────────────────────────────────┐
│                    SNOWFLAKE INTELLIGENCE                        │
│                   (Native Snowflake Interface)                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   User → Snowflake Intelligence → Agent Orchestrator             │
│                                        │                         │
│              ┌─────────────────────────┼─────────────────┐       │
│              │                         │                 │       │
│              ▼                         ▼                 ▼       │
│     ┌─────────────┐          ┌─────────────┐     ┌─────────────┐ │
│     │   Agent A   │          │   Agent B   │     │ External    │ │
│     │ (Sales)     │          │ (HR)        │     │ Agent (MCP) │ │
│     └─────────────┘          └─────────────┘     └─────────────┘ │
│           │                        │                    │        │
│     ┌─────┴─────┐            ┌─────┴─────┐             │        │
│     │           │            │           │             │        │
│     ▼           ▼            ▼           ▼             ▼        │
│ ┌───────┐  ┌────────┐   ┌───────┐  ┌────────┐    ┌──────────┐  │
│ │Analyst│  │ Search │   │Analyst│  │ Search │    │ External │  │
│ │(Sales)│  │(Docs)  │   │(HR DB)│  │(Policies)│  │  Tools   │  │
│ └───────┘  └────────┘   └───────┘  └────────┘    └──────────┘  │
│                                                                  │
│              ALL GOVERNED BY SNOWFLAKE RBAC                      │
└─────────────────────────────────────────────────────────────────┘
```

**Advantages**:
- **Native SSO Integration**: User identity flows through seamlessly
- **Full RBAC Enforcement**: Row-level security, masking policies, and object grants enforced automatically
- **Multi-Agent Orchestration**: Built-in capability to route questions to appropriate agents
- **MCP for External Tools**: Can call external agents/tools via MCP protocol
- **Zero Infrastructure**: No additional services to deploy or maintain

**When to Choose This**:
- Majority of your data is in Snowflake
- You want the simplest path to production
- Governance is non-negotiable
- You don't have an existing AI front-end investment

---

### Option B: Custom Front-End with Snowflake MCP Integration

**What It Is**: Using an existing AI interface (Open WebUI, custom app, etc.) that calls Snowflake via the MCP (Model Context Protocol) standard.

**Architecture** (What We Built):
```
┌─────────────────────────────────────────────────────────────────┐
│                      OPEN WEBUI INTERFACE                        │
│                    (Custom AI Front-End)                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   User ──────► Open WebUI ──────► Filter Function                │
│   (SSO)         (LLM)             (Tool Router)                  │
│                                        │                         │
│              ┌─────────────────────────┼─────────────────┐       │
│              │                         │                 │       │
│              ▼                         ▼                 ▼       │
│     ┌─────────────┐          ┌─────────────────────────────────┐ │
│     │  Local RAG  │          │      SNOWFLAKE MCP SERVER       │ │
│     │ (ChromaDB)  │          │  ┌──────────────────────────┐   │ │
│     │             │          │  │ MCP Protocol (JSON-RPC)  │   │ │
│     │ Technician  │          │  │  - tools/list            │   │ │
│     │ Reviews PDF │          │  │  - tools/call            │   │ │
│     └─────────────┘          │  └──────────────────────────┘   │ │
│                              │              │                   │ │
│                              │              ▼                   │ │
│                              │     ┌─────────────────┐          │ │
│                              │     │ Cortex Analyst  │          │ │
│                              │     │ (Semantic View) │          │ │
│                              │     └─────────────────┘          │ │
│                              │              │                   │ │
│                              │              ▼                   │ │
│                              │     ┌─────────────────┐          │ │
│                              │     │   RLS + Masking │          │ │
│                              │     │   Enforcement   │          │ │
│                              │     └─────────────────┘          │ │
│                              └─────────────────────────────────┘ │
│                                                                  │
│    Auth: Bearer <user_token> passed to MCP → Snowflake RBAC      │
└─────────────────────────────────────────────────────────────────┘
```

**Key Implementation Detail - MCP Protocol**:
```python
# MCP uses JSON-RPC 2.0 protocol
# Step 1: Discover available tools
tools_list_request = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list",
    "params": {}
}

# Step 2: Call the tool with user's question
tools_call_request = {
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
        "name": "trucking-analyst",
        "arguments": {"message": "Show me all drivers and phone numbers"}
    }
}

# Both calls use: Authorization: Bearer <user_token>
```

**When to Choose This**:
- Existing AI front-end investment you want to preserve
- Need to combine Snowflake data with non-Snowflake data sources
- Want fine-grained control over orchestration logic
- Regulatory requirements mandate specific UI/UX

---

### Option C: Custom Front-End with Direct API (Non-MCP)

**What It Is**: Calling Snowflake Cortex Analyst directly via REST API instead of MCP.

**Key Difference from MCP**:
| Aspect | Direct REST API | MCP Server |
|--------|-----------------|------------|
| **URL** | `/api/v2/cortex/analyst/message` | `/api/v2/.../mcp-servers/{name}` |
| **Protocol** | REST (JSON body) | JSON-RPC 2.0 |
| **Tool Discovery** | None | `tools/list` returns available tools |
| **Standard** | Snowflake-specific | Industry standard (MCP) |
| **Multi-tool** | One semantic view per call | Server can expose multiple tools |

**When to Choose This**:
- Simple, single-purpose integration
- MCP not yet supported by your client
- Prototyping before MCP migration

---

## Part 2: Security Architecture Patterns

### The "Query First, Enforce on Results" Pattern

This is the critical architectural insight that makes per-user token pass-through work:

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

### Pattern 1: Per-User Token Pass-Through (Recommended)

Each user's identity token (OAuth or PAT) is passed to Snowflake, enabling full RBAC enforcement.

```
┌─────────────────────────────────────────────────────────────────┐
│                    PER-USER TOKEN PATTERN                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   west_user ───► Open WebUI ───► MCP Server ───► Snowflake       │
│   (OAuth)        stores          passes          enforces        │
│                  token           Bearer token    RBAC as         │
│                                                  WEST_USER       │
│                                                       │          │
│                                                       ▼          │
│                                           ┌─────────────────┐    │
│                                           │ Row-Level       │    │
│                                           │ Security:       │    │
│                                           │ WHERE region =  │    │
│                                           │ 'WEST'          │    │
│                                           ├─────────────────┤    │
│                                           │ Masking Policy: │    │
│                                           │ phone_number =  │    │
│                                           │ '***MASKED***'  │    │
│                                           └─────────────────┘    │
│                                                                  │
│   RESULT: west_user sees only WEST region, phones masked         │
│                                                                  │
│   admin ─────► Open WebUI ───► MCP Server ───► Snowflake         │
│   (OAuth)                                      enforces          │
│                                                RBAC as           │
│                                                ADMIN             │
│                                                       │          │
│                                                       ▼          │
│                                           ┌─────────────────┐    │
│                                           │ RLS: ALL rows   │    │
│                                           │ Masking: NONE   │    │
│                                           │ (admin exempt)  │    │
│                                           └─────────────────┘    │
│                                                                  │
│   RESULT: admin sees ALL regions, real phone numbers             │
└─────────────────────────────────────────────────────────────────┘
```

**Advantages**:
- Full Snowflake governance enforced
- Audit trail shows actual user who accessed data
- No application-layer security logic needed for Snowflake data

**Implementation Requirements**:
- OAuth integration between front-end and Snowflake
- Token storage and refresh in front-end application
- MCP or REST calls with `Authorization: Bearer <user_token>`

---

### Pattern 2: Service Account with Application-Layer Filtering

A single service account accesses Snowflake; the application layer enforces access control.

```
┌─────────────────────────────────────────────────────────────────┐
│               SERVICE ACCOUNT PATTERN                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   west_user ───► Open WebUI ───► Application Logic               │
│   east_user ───►     │                  │                        │
│   admin     ───►     │                  │                        │
│                      ▼                  ▼                        │
│              ┌─────────────┐    ┌─────────────────┐              │
│              │ User Access │    │ Query Modifier  │              │
│              │ Control     │    │ (App Layer)     │              │
│              │ Table       │    │                 │              │
│              │             │    │ IF user.role =  │              │
│              │ west_user:  │    │   'WEST':       │              │
│              │  region=    │───►│   ADD filter:   │              │
│              │  'WEST'     │    │   region='WEST' │              │
│              └─────────────┘    └─────────────────┘              │
│                                         │                        │
│                                         ▼                        │
│                          ┌─────────────────────────┐             │
│                          │    Snowflake MCP        │             │
│                          │    (Service Account)    │             │
│                          │                         │             │
│                          │  Auth: Bearer           │             │
│                          │  <SERVICE_ACCOUNT_PAT>  │             │
│                          └─────────────────────────┘             │
│                                         │                        │
│                                         ▼                        │
│                          ┌─────────────────────────┐             │
│                          │  Snowflake sees only    │             │
│                          │  SERVICE_ACCOUNT user   │             │
│                          │                         │             │
│                          │  No RLS enforcement     │             │
│                          │  (service account has   │             │
│                          │   full access)          │             │
│                          └─────────────────────────┘             │
│                                                                  │
│   ⚠️  SECURITY RELIES ON APPLICATION LAYER                       │
│   ⚠️  Audit trail shows SERVICE_ACCOUNT, not actual user         │
└─────────────────────────────────────────────────────────────────┘
```

**When This Pattern is Used**:
- Legacy systems that can't do per-user OAuth
- Simplified token management (one credential to rotate)
- Application already has robust access control logic

**Critical Risks**:
- **Audit Gap**: Snowflake logs show service account, not actual user
- **Application Trust**: Security depends entirely on application logic
- **Bypass Risk**: Any bug in application filtering exposes all data
- **Compliance Issues**: May not satisfy regulatory requirements for audit trails

**Mitigation Strategies** (if you must use this pattern):
```python
# Option 1: Add user context to queries via session parameters
cursor.execute(f"ALTER SESSION SET QUERY_TAG = 'user={actual_user}'")

# Option 2: Use a view with application-injected filter
# Pass user context and let Snowflake view filter
cursor.execute("""
    SELECT * FROM data_view 
    WHERE region = %(user_region)s  -- App injects filter
""", {"user_region": user_config["region"]})

# Option 3: Log access in application before query
audit_log.info(f"User {actual_user} querying: {query}")
```

---

### Pattern 3: Hybrid (Mixed Security Boundaries)

Different data sources have different security models.

```
┌─────────────────────────────────────────────────────────────────┐
│                    HYBRID PATTERN                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   User ───► Open WebUI ───► Tool Router                          │
│                                  │                               │
│              ┌───────────────────┼───────────────────┐           │
│              │                   │                   │           │
│              ▼                   ▼                   ▼           │
│     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     │
│     │  Local RAG  │     │  Snowflake  │     │  External   │     │
│     │  (ChromaDB) │     │  MCP Server │     │  API        │     │
│     └─────────────┘     └─────────────┘     └─────────────┘     │
│            │                   │                   │             │
│            ▼                   ▼                   ▼             │
│     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     │
│     │ App-Layer   │     │ Per-User    │     │ API Key     │     │
│     │ Access      │     │ Token       │     │ Auth        │     │
│     │ Control     │     │ (Full RBAC) │     │             │     │
│     └─────────────┘     └─────────────┘     └─────────────┘     │
│                                                                  │
│   WHAT WE BUILT:                                                 │
│   - RAG: Application controls who can query knowledge base       │
│   - Snowflake: User's PAT enforces RLS + Masking                │
│   - Result: Best security model for each data source             │
└─────────────────────────────────────────────────────────────────┘
```

**Our Demo Implementation**:
```python
# From mcp_analyst_router.py - the filter function

def inlet(self, body: dict, __user__: dict) -> dict:
    user_config = self._get_user_config(username)
    
    # RAG queries: Application-layer access control
    if is_rag_query:
        if user_config.get("has_rag_access"):
            results = self._query_rag(query)  # Local ChromaDB
            # ... inject into context
        else:
            # Deny access at application layer
    
    # Snowflake queries: Per-user token, Snowflake RBAC
    elif user_config.get("has_analyst_access"):
        pat = user_config.get("pat")  # User's own token
        # MCP call with user's token - Snowflake enforces RBAC
        response = self._mcp_tools_call(
            "trucking-analyst", 
            query, 
            pat,  # User's identity
            account
        )
```

### Design Decision: Keyword Routing vs LLM-Based Routing

We chose **deterministic keyword matching** for query routing:

```python
def _is_analyst_query(self, query: str) -> bool:
    analyst_keywords = ['driver', 'truck', 'route', 'delivery', 'fleet', 'shipment']
    return any(keyword in query.lower() for keyword in analyst_keywords)
```

| Factor | Keyword Matching | LLM Routing |
|--------|-----------------|-------------|
| **Latency** | ~0ms | 500-2000ms |
| **Cost** | $0 | $0.01-0.10 per query |
| **Predictability** | 100% deterministic | Probabilistic |
| **Demo Clarity** | Easy to explain | "Magic" black box |

**Production Recommendation**: Use a **hybrid approach**—fast keyword matching for obvious cases (80%), LLM classification for ambiguous queries (20%).

---

## Part 3: Our Demo Implementation

### What We Built

A working demonstration of **Pattern 3 (Hybrid)** using:
- **Front-End**: Open WebUI (open-source AI chat interface)
- **Structured Data**: Snowflake Cortex Analyst via MCP Server
- **Unstructured Data**: Local RAG (ChromaDB) with technician reviews PDF
- **Security**: Per-user PATs for Snowflake, application-layer for RAG

### The Four User Types

| User | Open WebUI Access | Snowflake Access | What They See |
|------|------------------|------------------|---------------|
| **web_user** | RAG Only | None | Technician reviews from PDF |
| **west_user** | Analyst Only | WEST_MANAGER role | WEST region data, PII masked |
| **east_user** | Analyst Only | EAST_MANAGER role | EAST region data, PII masked |
| **admin** | RAG + Analyst | ACCOUNTADMIN role | All data, nothing masked |

### Test Questions That Prove the Architecture

1. **"Show me Sarah Chen's performance review"** → Tests RAG access (knowledge base)
2. **"Show me drivers, their region and phone numbers"** → Tests Analyst + RLS + Masking

### Creating the Snowflake MCP Server

```sql
-- Step 1: Create a Semantic View over your data
CREATE OR REPLACE SEMANTIC VIEW SECURITY_WORKSHOP.TRUCKING.TRUCKING_SEMANTIC_VIEW
  AS SELECT * FROM TRUCKING.DRIVERS  -- Your base tables
  WITH
    COMMENT = 'Trucking operations data'
    -- Define dimensions, measures, relationships...
;

-- Step 2: Create the MCP Server pointing to the Semantic View
CREATE OR REPLACE CORTEX MCP SERVER SECURITY_WORKSHOP.TRUCKING.TRUCKING_MCP
  FROM SEMANTIC VIEW SECURITY_WORKSHOP.TRUCKING.TRUCKING_SEMANTIC_VIEW
  COMMENT = 'MCP Server for trucking data queries';

-- Step 3: Grant access to roles
GRANT USAGE ON CORTEX MCP SERVER TRUCKING_MCP TO ROLE WEST_MANAGER;
GRANT USAGE ON CORTEX MCP SERVER TRUCKING_MCP TO ROLE EAST_MANAGER;
```

### The Filter Function (Tool Router)

**Screenshot/Code Location**: `/functions/mcp_analyst_router.py`

Key sections:

**1. MCP Protocol Implementation**:
```python
def _mcp_tools_list(self, pat: str, account: str) -> dict:
    """MCP Protocol: tools/list - Discover available tools"""
    url = f"https://{account}.snowflakecomputing.com/api/v2/databases/{self.valves.mcp_database}/schemas/{self.valves.mcp_schema}/mcp-servers/{self.valves.mcp_server_name}"
    
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {}
    }
    
    response = requests.post(url,
        headers={"Authorization": f"Bearer {pat}", ...},
        json=payload
    )
    return response.json()

def _mcp_tools_call(self, tool_name: str, query: str, pat: str, account: str) -> dict:
    """MCP Protocol: tools/call - Invoke a tool"""
    payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": {"message": query}
        }
    }
    # Same URL, same auth header
```

**2. User Routing Logic**:
```python
def inlet(self, body: dict, __user__: dict) -> dict:
    # Get user-specific configuration
    user_config = self._get_user_config(username)
    
    # Route to appropriate tool based on query type and user access
    if is_rag_query and user_config.get("has_rag_access"):
        # Query local knowledge base
        results = self._query_rag(query)
    elif user_config.get("has_analyst_access"):
        # Call Snowflake MCP with user's token
        pat = user_config.get("pat")
        response = self._mcp_tools_call("trucking-analyst", query, pat, account)
```

### Demo vs Production

| Aspect | Demo (What We Built) | Production |
|--------|---------------------|------------|
| **User Auth** | PAT (Personal Access Token) | OAuth 2.0 / OIDC SSO |
| **Token Storage** | JSON config file | OAuth token store with refresh |
| **Token Lifetime** | Long-lived PAT | Short-lived OAuth + refresh tokens |
| **User Provisioning** | Manual JSON entries | SCIM / IdP sync |
| **Session Management** | None | OAuth session handling |
| **MCP Protocol** | Identical | Identical |
| **RBAC Enforcement** | Identical (Snowflake) | Identical (Snowflake) |

**Production Migration Path**:

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

**What Stays the Same**: Snowflake MCP Server, Semantic View, Row Access Policies, Masking Policies, Role hierarchy - all RBAC logic remains in Snowflake.

---

## Part 4: Complete Test Results

### Test Matrix

| User | Q1: Sarah Chen's Review | Q2: Drivers + Phone | Status |
|------|------------------------|---------------------|--------|
| **web_user** | ✅ Full review from RAG | ✅ Denied (no Analyst) | PASS |
| **west_user** | ✅ Denied (no RAG) | ✅ 4 WEST drivers, MASKED | PASS |
| **east_user** | ✅ Denied (no RAG) | ✅ 4 EAST drivers, MASKED | PASS |
| **admin** | ✅ Full review from RAG | ✅ 8 drivers, UNMASKED | PASS |

### RBAC Proof - Same Query, Different Results

The power of per-user authentication is that **Snowflake enforces governance automatically**.

**Query**: "Show me all drivers with their region and phone number"

**Results by User**:

| User | Snowflake Role | Rows Returned | Phone Numbers |
|------|---------------|---------------|---------------|
| west_user | WEST_MANAGER | 4 (WEST only) | `***MASKED***` |
| east_user | EAST_MANAGER | 4 (EAST only) | `***MASKED***` |
| admin | ACCOUNTADMIN | 8 (ALL) | Real numbers |

```
west_user results:
| DRIVER_ID | REGION | PHONE_NUMBER |
|-----------|--------|--------------|
| DRV001    | WEST   | ***MASKED*** |
| DRV002    | WEST   | ***MASKED*** |
| DRV005    | WEST   | ***MASKED*** |
| DRV007    | WEST   | ***MASKED*** |

admin results:
| DRIVER_ID | REGION | PHONE_NUMBER |
|-----------|--------|--------------|
| DRV001    | WEST   | 555-123-4567 |
| DRV002    | WEST   | 555-234-5678 |
| DRV003    | EAST   | 555-345-6789 |
| DRV004    | EAST   | 555-456-7890 |
| ...       | ...    | ...          |
```

**This happens because**:
1. User's token identifies them to Snowflake
2. Row-Level Security policy filters by region
3. Masking policy hides phone numbers for non-admin roles
4. **No application code required** - Snowflake handles it

---

## Part 5: Architecture Decision Guide

### Choose Snowflake Intelligence When:
- ✅ Most/all of your data is in Snowflake
- ✅ You want zero additional infrastructure
- ✅ Native SSO integration is sufficient
- ✅ You need multi-agent orchestration
- ✅ You want to call external tools via MCP

### Choose Custom Front-End with MCP When:
- ✅ You have an existing AI interface investment
- ✅ You need to combine Snowflake + non-Snowflake data
- ✅ You want custom orchestration logic
- ✅ Regulatory requirements mandate specific UI

### Choose Service Account Pattern When:
- ⚠️ Legacy systems can't support per-user OAuth
- ⚠️ You accept application-layer security responsibility
- ⚠️ Audit trail gaps are acceptable for your use case

---

## Part 6: Key Takeaways

1. **MCP is the Standard**: Whether using Snowflake Intelligence or custom front-ends, MCP provides a consistent protocol for tool integration.

2. **Per-User Tokens Enable Full RBAC**: The pattern of passing user identity through to Snowflake enables automatic enforcement of:
   - Row-Level Security (RLS)
   - Dynamic Data Masking
   - Object-level grants
   - Complete audit trails

3. **Hybrid Architectures Work**: You can mix security models—application-layer for local data, Snowflake RBAC for Snowflake data—as long as you're explicit about the boundaries.

4. **Demo to Production is Straightforward**: The core architecture (MCP protocol, tool routing, response handling) stays the same; only the authentication mechanism changes from PAT to OAuth.

5. **Snowflake Intelligence is the Simplest Path**: For organizations where Snowflake is the primary data platform, Snowflake Intelligence provides the most integrated experience with the least infrastructure.

---

## Appendix: Code & Configuration Files

### Files in This Demo

| File | Purpose |
|------|---------|
| `functions/mcp_analyst_router.py` | Open WebUI filter - routes queries to MCP or RAG |
| `config/user_credentials.json` | User access configuration (demo only) |
| `demo_mcp_rbac.py` | Standalone script proving RBAC via MCP |
| `prove_mcp.py` | Script showing raw MCP protocol exchange |
| `DEMO_DOCUMENTATION.md` | Full architecture documentation |

### MCP Protocol Reference

**Endpoint**: 
```
https://{account}.snowflakecomputing.com/api/v2/databases/{db}/schemas/{schema}/mcp-servers/{server_name}
```

**tools/list** - Discover available tools:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {}
}
```

**tools/call** - Invoke a tool:
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "tool-name",
    "arguments": {
      "message": "user's question"
    }
  }
}
```

---

## About This Demo

This demo was built to demonstrate enterprise integration patterns between custom AI interfaces and Snowflake's AI capabilities. It showcases:

- **MCP Protocol**: Industry-standard tool integration
- **Per-User RBAC**: Full Snowflake governance enforcement
- **Hybrid Architecture**: Combining structured and unstructured data sources
- **Production Pathways**: Clear upgrade path from demo (PAT) to production (OAuth)

For questions or to discuss your specific architecture needs, [contact information].
