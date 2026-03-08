# Open WebUI + Snowflake MCP Integration Demo

A complete demonstration of using [Open WebUI](https://openwebui.com/) as a unified AI frontend that securely connects to Snowflake via the **Model Context Protocol (MCP)**. This demo showcases enterprise-grade security patterns including **Row-Level Security (RLS)** and **Data Masking** enforced automatically by Snowflake.

## What This Demo Proves

1. **Unified AI Interface**: A single chat UI routes users to different AI backends (RAG chatbot, Snowflake Cortex Analyst)
2. **Per-User RBAC**: Different users see different data based on their Snowflake role
3. **Security Pass-Through**: Snowflake's RLS and masking policies are enforced automatically
4. **MCP Protocol**: Industry-standard protocol for AI-to-data connectivity

### The Demo Scenario

| User | Snowflake Role | What They See |
|------|---------------|---------------|
| **west_user** | WEST_MANAGER | 4 WEST region drivers, phone numbers MASKED |
| **east_user** | EAST_MANAGER | 4 EAST region drivers, phone numbers MASKED |
| **admin** | ACCOUNTADMIN | All 8 drivers, phone numbers VISIBLE |
| **web_user** | (none) | RAG documents only, no database access |

---

## Prerequisites

- **Snowflake Account** (Enterprise edition or trial)
- **Docker Desktop** installed and running
- **30-45 minutes** for setup

---

## Quick Start

### Step 1: Clone This Repository

```bash
git clone https://github.com/azbarbarian2020/openwebui-snowflake-mcp-demo.git
cd openwebui-snowflake-mcp-demo
```

---

### Step 2: Run Snowflake Setup (5 min)

1. Log into [Snowsight](https://app.snowflake.com) as ACCOUNTADMIN
2. Open a new SQL Worksheet
3. Copy the entire contents of `snowflake_setup.sql` from this repository
4. Paste and run (click "Run All" or Ctrl+Shift+Enter)

**Expected Result**: All verification queries at the end should show:
- ACCOUNTADMIN: 8 drivers, real phone number
- WEST_MANAGER: 4 drivers, "MASKED" phone
- EAST_MANAGER: 4 drivers, "MASKED" phone

---

### Step 3: Generate Personal Access Tokens (10 min)

You need PATs for three users: **WEST_USER**, **EAST_USER**, and your **admin user**.

#### For WEST_USER and EAST_USER:

1. In Snowsight, click your user menu (bottom left) → **Switch Role** → **ACCOUNTADMIN**
2. Go to **Admin** → **Users & Roles** → **Users**
3. Click on **WEST_USER** → **Authentication** tab
4. Under "Programmatic access tokens", click **+ Generate new token**
5. Name: `openwebui-demo`, Expiration: 30 days
6. Click **Generate** and **copy the token immediately** (you won't see it again)
7. Repeat for **EAST_USER**

#### For your Admin user:

1. Click your user menu → **My Profile**
2. Go to **Authentication** tab
3. Generate a PAT the same way

**Save all three PATs** - you'll need them in Step 5.

---

### Step 4: Get Your Account Identifier

Your Snowflake account identifier is in your URL:

- **Trial accounts**: `https://abc12345.snowflakecomputing.com` → identifier is `abc12345`
- **Enterprise accounts**: `https://orgname-accountname.snowflakecomputing.com` → identifier is `orgname-accountname`

---

### Step 5: Configure Credentials (5 min)

1. Copy the template:
   ```bash
   cp config/user_credentials.template.json config/user_credentials.json
   ```

2. Edit `config/user_credentials.json`:
   ```json
   {
     "snowflake_account": "YOUR_ACCOUNT_IDENTIFIER",
     "semantic_view": "SECURITY_WORKSHOP.TRUCKING.TRUCKING_SEMANTIC_VIEW",
     "users": {
       "web_user": {
         "snowflake_user": null,
         "pat": null,
         "has_analyst_access": false,
         "has_rag_access": true
       },
       "west_user": {
         "snowflake_user": "WEST_USER",
         "pat": "PASTE_WEST_USER_PAT_HERE",
         "has_analyst_access": true,
         "has_rag_access": false
       },
       "east_user": {
         "snowflake_user": "EAST_USER",
         "pat": "PASTE_EAST_USER_PAT_HERE",
         "has_analyst_access": true,
         "has_rag_access": false
       },
       "admin": {
         "snowflake_user": "YOUR_ADMIN_USERNAME",
         "pat": "PASTE_ADMIN_PAT_HERE",
         "has_analyst_access": true,
         "has_rag_access": true
       }
     }
   }
   ```

---

### Step 6: Start Open WebUI (2 min)

From the repository directory, start the Docker container:

```bash
docker-compose up -d
```

This downloads and starts Open WebUI. Wait ~30 seconds for startup, then open: **http://localhost:3002**

#### First-Time Setup:

1. Click **Get Started**
2. You'll be prompted to create an **Admin Account**
3. Use `admin@demo.local` as the email (the `admin` part must match the key in `user_credentials.json`)
4. Enter any name and password (e.g., `Admin User` / `admin123`)
5. Click **Create Admin Account**

**Important**: The username (part before `@`) determines which Snowflake credentials are used. Using `admin@demo.local` maps to the `admin` entry in `user_credentials.json`, giving full Snowflake access + RAG access.

You should now see the Open WebUI chat interface.

To stop later: `docker-compose down`

---

### Step 7: Install the Filter Function (5 min)

1. In Open WebUI, click **your avatar** (top right) → **Admin Panel**
2. Go to **Functions** tab
3. Click **+ Create a Function**
4. Copy the entire contents of [`functions/mcp_analyst_router.py`](./functions/mcp_analyst_router.py)
5. Paste into the code editor
6. Click **Save**
7. **IMPORTANT**: Click the **Global** toggle to enable it for all users
8. The function status should show as enabled (green)

---

### Step 8: Create Knowledge Base for RAG (5 min)

1. Go to **Workspace** → **Knowledge**
2. Click **+ Create Knowledge Base**
3. Name: `Technician Reviews`
4. Click **Create**
5. Click **+ Add Content** → **Upload Files**
6. Upload [`docs/Technician_Reviews_2025.pdf`](./docs/Technician_Reviews_2025.pdf)
7. Wait for processing to complete
8. **Copy the Knowledge Base ID** from the URL: `http://localhost:3000/workspace/knowledge/{THIS-ID}`

#### Update Filter Function with Knowledge Base ID:

1. Go back to **Admin Panel** → **Functions**
2. Click on your **MCP Analyst Router** function
3. Find the `knowledge_id` valve and paste your Knowledge Base ID
4. Save

---

### Step 9: Create Test Users (5 min)

1. Go to **Admin Panel** → **Users**
2. Create these users (passwords can be anything for demo):

| Email | Name | Role |
|-------|------|------|
| `west_user@demo.local` | west_user | User |
| `east_user@demo.local` | east_user | User |
| `web_user@demo.local` | web_user | User |

**Important**: The username (before @) must match the keys in `user_credentials.json`

---

### Step 10: Test the Demo (5 min)

#### Test 1: Row-Level Security

Log in as each user and ask: **"Show me all drivers with their region and phone numbers"**

| User | Expected Result |
|------|-----------------|
| west_user | 4 WEST drivers, phones show "MASKED" |
| east_user | 4 EAST drivers, phones show "MASKED" |
| admin | 8 drivers (all), phones show real numbers |

#### Test 2: RAG Access

Ask: **"Tell me about Sarah Chen's performance review"**

| User | Expected Result |
|------|-----------------|
| web_user | Full review from knowledge base |
| west_user | "You don't have access to the knowledge base" |
| admin | Full review (has both RAG and Analyst access) |

---

## Troubleshooting

### "I can't do that" response
- Check that the **Global** toggle is enabled on the filter function
- Verify the function is showing as active (not errored)

### No data returned from Snowflake
- Verify PATs are valid (not expired)
- Check account identifier is correct in `user_credentials.json`
- Ensure MCP Server was created: `SHOW MCP SERVERS IN SECURITY_WORKSHOP.TRUCKING;`

### 401 Unauthorized errors (API access blocked)
- **Trial accounts**: Network policy is required. Run Step 15 in `snowflake_setup.sql`
- **Internal Snowflake accounts**: Check existing network policies with `SHOW NETWORK POLICIES;`
- Run `SHOW PARAMETERS LIKE 'NETWORK_POLICY' IN ACCOUNT;` to see current policy

### RAG not working
- Verify Knowledge Base ID is correct in function valves
- Ensure PDF was uploaded and processed (shows green checkmark)

### Docker issues
```bash
docker-compose down
docker-compose up -d
docker logs open-webui
```

---

## Architecture

See [ARCHITECTURE.md](./ARCHITECTURE.md) for detailed technical documentation including:
- MCP protocol details (JSON-RPC 2.0)
- Security model ("Query First, Enforce on Results")
- Demo vs Production differences
- OAuth SSO upgrade path

---

## Files in This Repository

| File | Description |
|------|-------------|
| `snowflake_setup.sql` | Complete SQL worksheet for Snowflake setup |
| `docker-compose.yml` | Open WebUI container configuration |
| `config/user_credentials.template.json` | Template for PAT configuration |
| `functions/mcp_analyst_router.py` | Filter function for MCP routing |
| `docs/Technician_Reviews_2025.pdf` | Sample document for RAG |
| `scripts/verify_setup.py` | Validation script |
| `ARCHITECTURE.md` | Technical deep-dive |
| `blog.md` | Blog article about the architecture |

---

## Security Notes

- **PATs are sensitive** - Don't commit real PATs to version control
- **Demo passwords** - Change default passwords for any non-demo use
- **Production**: Replace PATs with OAuth SSO (see ARCHITECTURE.md)

---

## License

MIT License - See [LICENSE](./LICENSE)

---

## Credits

Built with:
- [Open WebUI](https://openwebui.com/) - Open-source AI chat interface
- [Snowflake Cortex](https://www.snowflake.com/en/data-cloud/cortex/) - AI/ML platform
- [Model Context Protocol](https://modelcontextprotocol.io/) - Anthropic's open standard

