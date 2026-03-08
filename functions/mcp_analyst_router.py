"""
title: MCP Analyst Router
author: Cortex Code
version: 2.0.0
description: Routes queries via Snowflake Managed MCP Server. Demonstrates production-ready architecture with MCP protocol, per-user RBAC via PAT (OAuth in production).
"""

import json
import requests
import time
from typing import Optional
from pydantic import BaseModel, Field


class Filter:
    class Valves(BaseModel):
        credentials_file: str = Field(
            default="/app/backend/data/user_credentials.json",
            description="Path to user credentials JSON file"
        )
        knowledge_id: str = Field(
            default="REPLACE_WITH_YOUR_KNOWLEDGE_BASE_ID",
            description="Knowledge base collection ID for RAG queries (get from URL after creating knowledge base)"
        )
        vector_db_path: str = Field(
            default="/app/backend/data/vector_db",
            description="Path to ChromaDB vector database"
        )
        rag_top_k: int = Field(
            default=5,
            description="Number of RAG results to retrieve"
        )
        mcp_server_name: str = Field(
            default="TRUCKING_MCP",
            description="Name of the Snowflake MCP Server"
        )
        mcp_database: str = Field(
            default="SECURITY_WORKSHOP",
            description="Database containing the MCP Server"
        )
        mcp_schema: str = Field(
            default="TRUCKING",
            description="Schema containing the MCP Server"
        )
        show_mcp_debug: bool = Field(
            default=True,
            description="Show MCP protocol details in responses for demo purposes"
        )

    def __init__(self):
        self.valves = self.Valves()
        self._credentials_cache = None
        self._chroma_client = None
        self._mcp_call_log = []

    def _load_credentials(self) -> dict:
        if self._credentials_cache is None:
            try:
                with open(self.valves.credentials_file, 'r') as f:
                    self._credentials_cache = json.load(f)
            except Exception as e:
                print(f"[MCP Router] Failed to load credentials: {e}")
                self._credentials_cache = {"users": {}}
        return self._credentials_cache

    def _get_user_config(self, username: str) -> dict:
        creds = self._load_credentials()
        username_lower = username.lower() if username else ""
        return creds.get("users", {}).get(username_lower, {
            "snowflake_user": None,
            "pat": None,
            "has_analyst_access": False,
            "has_rag_access": True
        })

    def _get_chroma_client(self):
        """Get ChromaDB client - uses Open WebUI's singleton"""
        if self._chroma_client is None:
            try:
                from open_webui.retrieval.vector.factory import VECTOR_DB_CLIENT
                if hasattr(VECTOR_DB_CLIENT, 'client'):
                    self._chroma_client = VECTOR_DB_CLIENT.client
                else:
                    self._chroma_client = VECTOR_DB_CLIENT
            except ImportError as e:
                print(f"[MCP Router] Could not import Open WebUI client: {e}")
                return None
        return self._chroma_client

    def _query_rag(self, query: str) -> Optional[list]:
        """Query RAG knowledge base directly via ChromaDB"""
        try:
            client = self._get_chroma_client()
            if not client:
                return None
            
            collection_name = self.valves.knowledge_id
            
            try:
                collection = client.get_collection(name=collection_name)
            except Exception as e:
                print(f"[MCP Router] Collection not found: {e}")
                return None
            
            results = collection.query(
                query_texts=[query],
                n_results=self.valves.rag_top_k
            )
            
            documents = results.get("documents", [[]])[0] if results.get("documents") else []
            metadatas = results.get("metadatas", [[]])[0] if results.get("metadatas") else []
            
            rag_results = []
            for i, doc in enumerate(documents):
                metadata = metadatas[i] if i < len(metadatas) else {}
                rag_results.append({
                    "content": doc,
                    "source": metadata.get("name", metadata.get("source", "Technician_Reviews_2025.pdf")),
                    "metadata": metadata
                })
            return rag_results
            
        except Exception as e:
            print(f"[MCP Router] RAG query error: {e}")
            return None

    def _format_rag_results(self, results: list) -> str:
        """Format RAG results for injection into context"""
        if not results:
            return ""
        
        formatted = "\n[RETRIEVED DOCUMENTS FROM KNOWLEDGE BASE]\n\n"
        
        sources = set()
        for i, result in enumerate(results, 1):
            source = result.get("source", "Unknown")
            sources.add(source)
            content = result.get("content", "")
            formatted += f"--- Document {i} (Source: {source}) ---\n{content}\n\n"
        
        formatted += f"[END RETRIEVED DOCUMENTS - Sources: {', '.join(sources)}]\n"
        return formatted

    def _mcp_tools_list(self, pat: str, account: str) -> dict:
        """MCP Protocol: tools/list - Discover available tools"""
        url = f"https://{account}.snowflakecomputing.com/api/v2/databases/{self.valves.mcp_database}/schemas/{self.valves.mcp_schema}/mcp-servers/{self.valves.mcp_server_name}"
        
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        }
        
        try:
            start_time = time.time()
            response = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {pat}",
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                json=payload,
                timeout=30
            )
            elapsed = time.time() - start_time
            
            result = {
                "method": "tools/list",
                "url": url,
                "status_code": response.status_code,
                "elapsed_ms": int(elapsed * 1000),
                "response": response.json() if response.status_code == 200 else {"error": response.text[:200]}
            }
            
            self._mcp_call_log.append(result)
            print(f"[MCP Router] tools/list completed in {result['elapsed_ms']}ms")
            
            return result
            
        except Exception as e:
            print(f"[MCP Router] tools/list failed: {e}")
            return {"error": str(e)}

    def _mcp_tools_call(self, tool_name: str, query: str, pat: str, account: str) -> dict:
        """MCP Protocol: tools/call - Invoke a tool"""
        url = f"https://{account}.snowflakecomputing.com/api/v2/databases/{self.valves.mcp_database}/schemas/{self.valves.mcp_schema}/mcp-servers/{self.valves.mcp_server_name}"
        
        payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": {
                    "message": query
                }
            }
        }
        
        try:
            start_time = time.time()
            response = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {pat}",
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                json=payload,
                timeout=60
            )
            elapsed = time.time() - start_time
            
            result = {
                "method": "tools/call",
                "tool": tool_name,
                "url": url,
                "status_code": response.status_code,
                "elapsed_ms": int(elapsed * 1000),
                "request": payload,
                "response": response.json() if response.status_code == 200 else {"error": response.text[:500]}
            }
            
            self._mcp_call_log.append(result)
            print(f"[MCP Router] tools/call '{tool_name}' completed in {result['elapsed_ms']}ms, status={response.status_code}")
            
            return result
            
        except Exception as e:
            print(f"[MCP Router] tools/call failed: {e}")
            return {"error": str(e)}

    def _execute_sql(self, sql: str, pat: str, account: str) -> list:
        """Execute SQL via Snowflake SQL API"""
        url = f"https://{account}.snowflakecomputing.com/api/v2/statements"
        
        try:
            response = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {pat}",
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                json={
                    "statement": sql,
                    "timeout": 60,
                    "database": self.valves.mcp_database,
                    "schema": self.valves.mcp_schema,
                    "warehouse": "SECURITY_WH"
                },
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                data = result.get("data", [])
                columns = [col["name"] for col in result.get("resultSetMetaData", {}).get("rowType", [])]
                
                results = []
                for row in data:
                    results.append(dict(zip(columns, row)))
                return results
            else:
                print(f"[MCP Router] SQL execution returned {response.status_code}")
                return []
                
        except Exception as e:
            print(f"[MCP Router] SQL execution failed: {e}")
            return []

    def _parse_mcp_analyst_response(self, mcp_response: dict) -> Optional[dict]:
        """Parse MCP tools/call response for Cortex Analyst"""
        try:
            if "error" in mcp_response:
                return None
            
            response_data = mcp_response.get("response", {})
            result = response_data.get("result", {})
            content = result.get("content", [])
            
            text_response = ""
            sql_query = ""
            
            for item in content:
                item_type = item.get("type", "")
                if item_type == "text":
                    text_content = item.get("text", "")
                    try:
                        parsed_text = json.loads(text_content)
                        # MCP returns a list of items, not a dict
                        if isinstance(parsed_text, list):
                            for p in parsed_text:
                                if "text" in p:
                                    text_response = p["text"]
                                if "statement" in p:
                                    sql_query = p["statement"]
                        elif isinstance(parsed_text, dict):
                            # Fallback for different response format
                            msg = parsed_text.get("message", {})
                            msg_content = msg.get("content", [])
                            for c in msg_content:
                                if c.get("type") == "text":
                                    text_response = c.get("text", "")
                                elif c.get("type") == "sql":
                                    sql_query = c.get("statement", "")
                    except json.JSONDecodeError:
                        text_response = text_content
            
            if sql_query or text_response:
                return {
                    "text": text_response,
                    "sql": sql_query,
                    "results": []
                }
            return None
            
        except Exception as e:
            print(f"[MCP Router] Failed to parse MCP response: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _format_analyst_results(self, data: dict, mcp_debug: str = "") -> str:
        """Format Analyst results for injection into context"""
        if not data:
            return ""
        
        interpretation = data.get("text", "")
        results = data.get("results", [])
        
        if not results and not interpretation:
            return ""
        
        row_count = len(results) if results else 0
        formatted = f"\n[DATA FROM SNOWFLAKE VIA MCP SERVER"
        if row_count > 0:
            formatted += f" - {row_count} ROWS"
        formatted += "]\n"
        
        if mcp_debug:
            formatted += f"\n{mcp_debug}\n"
        
        if interpretation:
            formatted += f"Interpretation: {interpretation}\n\n"
        
        if results:
            headers = list(results[0].keys())
            formatted += "| " + " | ".join(str(h) for h in headers) + " |\n"
            formatted += "|" + "|".join(["---" for _ in headers]) + "|\n"
            for row in results[:100]:
                formatted += "| " + " | ".join(str(row.get(h, "")) for h in headers) + " |\n"
        
        formatted += f"\n[END MCP DATA]\n"
        return formatted

    def _format_mcp_debug(self, user_config: dict) -> str:
        """Format MCP call details for demo showcase"""
        if not self.valves.show_mcp_debug or not self._mcp_call_log:
            return ""
        
        snowflake_user = user_config.get("snowflake_user", "unknown")
        
        debug = "--- MCP Protocol Details (Demo Showcase) ---\n"
        debug += f"Snowflake User: {snowflake_user}\n"
        debug += f"MCP Server: {self.valves.mcp_database}.{self.valves.mcp_schema}.{self.valves.mcp_server_name}\n"
        debug += f"Auth: PAT (simulates OAuth token in production)\n\n"
        
        for call in self._mcp_call_log:
            method = call.get("method", "unknown")
            elapsed = call.get("elapsed_ms", 0)
            status = call.get("status_code", "?")
            
            if method == "tools/list":
                tools = call.get("response", {}).get("result", {}).get("tools", [])
                debug += f"1. tools/list ({elapsed}ms, status={status})\n"
                debug += f"   Discovered {len(tools)} tool(s): "
                debug += ", ".join([t.get("name", "?") for t in tools]) + "\n\n"
                
            elif method == "tools/call":
                tool = call.get("tool", "?")
                debug += f"2. tools/call '{tool}' ({elapsed}ms, status={status})\n"
                debug += f"   Request: {json.dumps(call.get('request', {}).get('params', {}), indent=2)[:200]}\n\n"
        
        debug += "--- End MCP Details ---\n"
        return debug

    def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        print(f"[MCP Router] ===== INLET CALLED (MCP VERSION) =====")
        
        self._mcp_call_log = []
        
        messages = body.get("messages", [])
        if not messages:
            return body
        
        last_message = messages[-1]
        if last_message.get("role") != "user":
            return body
        
        user_content = last_message.get("content", "")
        
        username = ""
        if __user__:
            username = __user__.get("name", "") or __user__.get("email", "").split("@")[0]
        
        print(f"[MCP Router] User: '{username}'")
        
        user_config = self._get_user_config(username)
        has_analyst = user_config.get("has_analyst_access", False)
        has_rag = user_config.get("has_rag_access", False)
        pat = user_config.get("pat")
        
        print(f"[MCP Router] Access - Analyst: {has_analyst}, RAG: {has_rag}")
        
        creds = self._load_credentials()
        account = creds.get("snowflake_account", "")
        
        rag_keywords = ["review", "performance review", "employee review", "annual review", 
                       "evaluation", "technician", "rating", "strengths", "growth"]
        query_lower = user_content.lower()
        is_rag_query = any(kw in query_lower for kw in rag_keywords)
        
        analyst_data = None
        rag_results = None
        mcp_debug = ""
        
        if is_rag_query:
            print(f"[MCP Router] Querying RAG knowledge base...")
            rag_results = self._query_rag(user_content)
            if rag_results:
                print(f"[MCP Router] RAG found {len(rag_results)} results")
        else:
            if has_analyst and pat:
                print(f"[MCP Router] === Calling Snowflake MCP Server ===")
                
                tools_list = self._mcp_tools_list(pat, account)
                print(f"[MCP Router] tools/list response: {json.dumps(tools_list.get('response', {}), indent=2)[:300]}")
                
                mcp_response = self._mcp_tools_call("trucking-analyst", user_content, pat, account)
                
                if mcp_response.get("status_code") == 200:
                    parsed = self._parse_mcp_analyst_response(mcp_response)
                    
                    if parsed and parsed.get("sql"):
                        print(f"[MCP Router] Executing SQL from MCP response...")
                        results = self._execute_sql(parsed["sql"], pat, account)
                        parsed["results"] = results
                        print(f"[MCP Router] SQL returned {len(results)} rows")
                    
                    analyst_data = parsed
                    mcp_debug = self._format_mcp_debug(user_config)
                else:
                    print(f"[MCP Router] MCP call failed: {mcp_response}")
        
        if rag_results:
            if has_rag:
                rag_data = self._format_rag_results(rag_results)
                system_content = f"""You are answering questions using documents from a knowledge base.
The following documents were retrieved based on the user's question.
Use ONLY the information in these documents to answer. If the answer is not in the documents, say so.

{rag_data}"""
                system_injection = {"role": "system", "content": system_content}
                
                if messages and messages[0].get("role") == "system":
                    messages[0]["content"] += f"\n\n{rag_data}"
                else:
                    messages.insert(0, system_injection)
                
                body["messages"] = messages
                print(f"[MCP Router] SUCCESS - Injected RAG context")
            else:
                deny_msg = {
                    "role": "system", 
                    "content": """The user asked about employee reviews or documents, but they do not have access to the knowledge base.

You must respond with:
"I found relevant documents, but you don't have permission to access the knowledge base. Please contact your administrator for access."

Do NOT answer the question. Do NOT use your training data to answer."""
                }
                messages.insert(0, deny_msg)
                body["messages"] = messages
                print(f"[MCP Router] ACCESS DENIED - RAG results found but user not authorized")
            
        elif analyst_data and (analyst_data.get("results") or analyst_data.get("text")):
            formatted_data = self._format_analyst_results(analyst_data, mcp_debug)
            result_count = len(analyst_data.get('results', []))
            
            system_content = f"""You are answering questions using data from Snowflake via the MCP Server.
The data below was retrieved through the MCP protocol from Cortex Analyst.
Present this data clearly and completely. Include the MCP debug info if shown.

{formatted_data}"""
            
            system_injection = {"role": "system", "content": system_content}
            
            if messages and messages[0].get("role") == "system":
                messages[0]["content"] += f"\n\n{formatted_data}"
            else:
                messages.insert(0, system_injection)
            
            body["messages"] = messages
            print(f"[MCP Router] SUCCESS - Injected {result_count} results via MCP")
            
        elif not has_analyst and not has_rag:
            error_msg = {"role": "system", "content": "This user does not have access to query any data sources. Please contact your administrator."}
            messages.insert(0, error_msg)
            body["messages"] = messages
            
        elif is_rag_query and not rag_results:
            no_docs_msg = {
                "role": "system", 
                "content": """The user asked about documents/reviews but no relevant documents were found in the knowledge base.

Respond with: "I searched the knowledge base but didn't find any documents matching your question. Try rephrasing or ask about a specific technician's review."

Do NOT make up information."""
            }
            messages.insert(0, no_docs_msg)
            body["messages"] = messages
            
        elif has_analyst and not analyst_data:
            no_data_msg = {
                "role": "system", 
                "content": """You are a data assistant. The user's question could not be answered from the database via MCP.

Respond with: "I couldn't retrieve data via the MCP Server. I can help with questions about drivers, routes, trucks, and shipments."

Do NOT answer general knowledge questions."""
            }
            messages.insert(0, no_data_msg)
            body["messages"] = messages
        
        return body

    def outlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        return body
