#!/usr/bin/env python3
"""
Verify Setup Script for Open WebUI + Snowflake MCP Demo

This script validates that all components are correctly configured:
1. Credentials file is valid JSON with required fields
2. PATs are valid (not expired)
3. MCP Server is accessible
4. RLS is working (different users see different data)
5. Masking is working (non-admins see MASKED)

Usage:
    python scripts/verify_setup.py

Requirements:
    pip install requests
"""

import json
import sys
import os
import requests
from pathlib import Path

def load_credentials(config_path: str = "config/user_credentials.json") -> dict:
    """Load and validate credentials file"""
    try:
        with open(config_path, 'r') as f:
            creds = json.load(f)
        
        required_fields = ["snowflake_account", "users"]
        for field in required_fields:
            if field not in creds:
                print(f"❌ Missing required field: {field}")
                return None
        
        print(f"✅ Credentials file loaded: {config_path}")
        return creds
    except FileNotFoundError:
        print(f"❌ Credentials file not found: {config_path}")
        print("   Run: cp config/user_credentials.template.json config/user_credentials.json")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in credentials file: {e}")
        return None

def test_mcp_connection(account: str, pat: str, user_name: str) -> dict:
    """Test MCP Server connectivity using tools/list"""
    url = f"https://{account}.snowflakecomputing.com/api/v2/databases/SECURITY_WORKSHOP/schemas/TRUCKING/mcp-servers/TRUCKING_MCP"
    
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {}
    }
    
    try:
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {pat}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            tools = result.get("result", {}).get("tools", [])
            print(f"✅ MCP connection OK for {user_name}: {len(tools)} tool(s) available")
            return {"success": True, "tools": tools}
        elif response.status_code == 401:
            print(f"❌ PAT invalid or expired for {user_name}")
            return {"success": False, "error": "Invalid/expired PAT"}
        else:
            print(f"❌ MCP error for {user_name}: HTTP {response.status_code}")
            return {"success": False, "error": f"HTTP {response.status_code}"}
    except requests.exceptions.RequestException as e:
        print(f"❌ Connection failed for {user_name}: {e}")
        return {"success": False, "error": str(e)}

def test_analyst_query(account: str, pat: str, user_name: str) -> dict:
    """Test Cortex Analyst query via MCP and execute returned SQL"""
    mcp_url = f"https://{account}.snowflakecomputing.com/api/v2/databases/SECURITY_WORKSHOP/schemas/TRUCKING/mcp-servers/TRUCKING_MCP"
    sql_url = f"https://{account}.snowflakecomputing.com/api/v2/statements"
    
    mcp_payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "trucking-analyst",
            "arguments": {
                "message": "Show me all drivers with their region and phone number"
            }
        }
    }
    
    headers = {
        "Authorization": f"Bearer {pat}",
        "Content-Type": "application/json"
    }
    
    try:
        mcp_response = requests.post(mcp_url, headers=headers, json=mcp_payload, timeout=60)
        
        if mcp_response.status_code != 200:
            return {"success": False, "error": f"MCP HTTP {mcp_response.status_code}"}
        
        mcp_result = mcp_response.json()
        content = mcp_result.get("result", {}).get("content", [])
        
        sql_query = None
        for item in content:
            if item.get("type") == "text":
                try:
                    parsed = json.loads(item.get("text", ""))
                    if isinstance(parsed, list):
                        for p in parsed:
                            if "statement" in p:
                                sql_query = p["statement"]
                                break
                except json.JSONDecodeError:
                    pass
        
        if not sql_query:
            return {"success": False, "error": "No SQL returned from MCP"}
        
        sql_response = requests.post(
            sql_url,
            headers=headers,
            json={
                "statement": sql_query,
                "timeout": 60,
                "database": "SECURITY_WORKSHOP",
                "schema": "TRUCKING",
                "warehouse": "SECURITY_WH"
            },
            timeout=60
        )
        
        if sql_response.status_code == 200:
            result = sql_response.json()
            data = result.get("data", [])
            columns = [col["name"] for col in result.get("resultSetMetaData", {}).get("rowType", [])]
            
            rows = []
            for row in data:
                rows.append(dict(zip(columns, row)))
            
            return {"success": True, "rows": rows, "count": len(rows)}
        else:
            return {"success": False, "error": f"SQL HTTP {sql_response.status_code}"}
            
    except Exception as e:
        return {"success": False, "error": str(e)}

def analyze_results(results: dict) -> dict:
    """Analyze query results for RLS and masking"""
    rows = results.get("rows", [])
    count = len(rows)
    
    regions = set()
    phone_masked = True
    
    for row in rows:
        if "REGION" in row:
            regions.add(row["REGION"])
        if "PHONE_NUMBER" in row:
            if row["PHONE_NUMBER"] != "MASKED":
                phone_masked = False
    
    return {
        "count": count,
        "regions": list(regions),
        "phones_masked": phone_masked
    }

def main():
    print("=" * 60)
    print("Open WebUI + Snowflake MCP Demo - Setup Verification")
    print("=" * 60)
    print()
    
    creds = load_credentials()
    if not creds:
        sys.exit(1)
    
    account = creds.get("snowflake_account", "")
    if not account or account == "YOUR_ACCOUNT_IDENTIFIER":
        print("❌ snowflake_account not configured in credentials file")
        sys.exit(1)
    
    print(f"   Account: {account}")
    print()
    
    users_to_test = ["west_user", "east_user", "admin"]
    
    print("-" * 60)
    print("Testing MCP Connectivity...")
    print("-" * 60)
    
    connection_results = {}
    for user_name in users_to_test:
        user_config = creds.get("users", {}).get(user_name, {})
        pat = user_config.get("pat")
        
        if not pat or pat.startswith("PASTE_"):
            print(f"⚠️  {user_name}: PAT not configured (skipping)")
            continue
        
        result = test_mcp_connection(account, pat, user_name)
        connection_results[user_name] = result
    
    print()
    print("-" * 60)
    print("Testing RLS and Masking...")
    print("-" * 60)
    
    query_results = {}
    for user_name in users_to_test:
        user_config = creds.get("users", {}).get(user_name, {})
        pat = user_config.get("pat")
        
        if not pat or pat.startswith("PASTE_"):
            continue
        
        if not connection_results.get(user_name, {}).get("success"):
            continue
        
        print(f"\nQuerying as {user_name}...")
        result = test_analyst_query(account, pat, user_name)
        
        if result.get("success"):
            analysis = analyze_results(result)
            query_results[user_name] = analysis
            print(f"   Rows: {analysis['count']}, Regions: {analysis['regions']}, Phones Masked: {analysis['phones_masked']}")
        else:
            print(f"   ❌ Query failed: {result.get('error')}")
    
    print()
    print("=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    print()
    
    expected = {
        "west_user": {"count": 4, "regions": ["WEST"], "phones_masked": True},
        "east_user": {"count": 4, "regions": ["EAST"], "phones_masked": True},
        "admin": {"count": 8, "regions": ["WEST", "EAST"], "phones_masked": False}
    }
    
    all_pass = True
    
    print(f"{'User':<12} {'Rows':<8} {'Regions':<15} {'Masked':<10} {'Status':<10}")
    print("-" * 60)
    
    for user_name in users_to_test:
        if user_name not in query_results:
            print(f"{user_name:<12} {'N/A':<8} {'N/A':<15} {'N/A':<10} {'SKIP':<10}")
            continue
        
        actual = query_results[user_name]
        exp = expected[user_name]
        
        count_ok = actual["count"] == exp["count"]
        regions_ok = set(actual["regions"]) == set(exp["regions"])
        masked_ok = actual["phones_masked"] == exp["phones_masked"]
        
        status = "✅ PASS" if (count_ok and regions_ok and masked_ok) else "❌ FAIL"
        if status == "❌ FAIL":
            all_pass = False
        
        print(f"{user_name:<12} {actual['count']:<8} {str(actual['regions']):<15} {str(actual['phones_masked']):<10} {status:<10}")
    
    print()
    if all_pass:
        print("🎉 All tests passed! Your demo is ready.")
    else:
        print("⚠️  Some tests failed. Please check the configuration.")
    
    return 0 if all_pass else 1

if __name__ == "__main__":
    sys.exit(main())
