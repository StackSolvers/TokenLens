import sys
import argparse
import json
import os

from tokenlens_core import AGENT_FILTER_CHOICES, collect_all_usage, compact_summary, compact_summary_payload, load_config

DEFAULT_AGENT = "current"

def log(msg):
    if os.environ.get("TOKENLENS_MCP_DEBUG") != "1":
        return
    sys.stderr.write(f"[mcp] {msg}\n")
    sys.stderr.flush()

def handle_initialize(request_id, params):
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {}
            },
            "serverInfo": {
                "name": "tokenlens-mcp",
                "version": "1.0.0"
            }
        }
    }

def handle_list_tools(request_id):
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "tools": [
                {
                    "name": "get_token_summary",
                    "description": "Get one compact TokenLens line with current session, last chat, and rolling local usage.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "format": {
                                "type": "string",
                                "description": "Use text for the one-line footer, or json for a minimal structured payload.",
                                "default": "text"
                            },
                            "agent": {
                                "type": "string",
                                "description": "Optional agent filter. Use current for auto-detect, or a specific supported agent id.",
                                "enum": list(AGENT_FILTER_CHOICES),
                                "default": DEFAULT_AGENT
                            }
                        }
                    }
                }
            ]
        }
    }


def agent_filter(arguments):
    requested = DEFAULT_AGENT
    if isinstance(arguments, dict) and arguments.get("agent"):
        requested = str(arguments.get("agent"))
    if requested == "all":
        return None
    if requested in AGENT_FILTER_CHOICES:
        return requested
    return None


def handle_call_tool(request_id, name, arguments):
    if name == "get_token_summary":
        try:
            data = collect_all_usage(load_config(), only_agents=agent_filter(arguments))
            if isinstance(arguments, dict) and arguments.get("format") == "json":
                output = json.dumps(compact_summary_payload(data), ensure_ascii=False, separators=(",", ":"))
            else:
                output = compact_summary(data)
        except Exception as e:
            log(f"get_token_summary failed: {type(e).__name__}: {str(e)[:120]}")
            output = f"TokenLens error: {type(e).__name__}: {str(e)[:120]}"
            
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": output
                    }
                ]
            }
        }
    else:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {name}"
            }
        }

def main(argv=None):
    global DEFAULT_AGENT
    parser = argparse.ArgumentParser(description="TokenLens MCP server.")
    parser.add_argument("--agent", choices=AGENT_FILTER_CHOICES, default="current", help="Default agent filter for get_token_summary.")
    args = parser.parse_args(argv)
    DEFAULT_AGENT = args.agent

    log("TokenLens MCP server started.")
    # On Windows, stdin/stdout need to be binary to prevent encoding/newline issues
    if sys.platform == "win32":
        import msvcrt
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)

    # We read line by line
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            
            req = json.loads(line)
            req_id = req.get("id")
            method = req.get("method")
            params = req.get("params", {})
            
            if method == "initialize":
                resp = handle_initialize(req_id, params)
            elif method == "tools/list":
                resp = handle_list_tools(req_id)
            elif method == "tools/call":
                resp = handle_call_tool(req_id, params.get("name"), params.get("arguments", {}))
            elif method and method.startswith("notifications/"):
                continue
            else:
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }
            
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        except Exception as e:
            log(f"Error handling request: {type(e).__name__}: {str(e)[:120]}")

if __name__ == "__main__":
    main()
