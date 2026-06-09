import json
import os
import tempfile
import unittest
from pathlib import Path

from tokenlens_core import (
    DEFAULT_CONFIG,
    collect_all_usage,
    compact_summary,
    compact_summary_payload,
    deep_merge,
    detect_current_agent,
    finalize_session,
    install_antigravity_mcp,
    install_json_mcp,
    install_workspace_rules,
    make_generation,
    make_session,
    mcp_json_snippet,
    mcp_toml_snippet,
    summarize_usage,
)


class EnvPatch:
    def __init__(self, **values):
        self.values = values
        self.old = {}

    def __enter__(self):
        for key, value in self.values.items():
            self.old[key] = os.environ.get(key)
            os.environ[key] = value

    def __exit__(self, exc_type, exc, tb):
        for key, value in self.old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


class CollectorTests(unittest.TestCase):
    def test_collects_claude_codex_and_cline_without_estimating_missing_usage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            appdata = root / "AppData" / "Roaming"

            claude_file = root / ".claude" / "projects" / "proj-a" / "session-a.jsonl"
            write_jsonl(
                claude_file,
                [
                    {
                        "type": "user",
                        "sessionId": "session-a",
                        "timestamp": "2026-06-07T10:00:00Z",
                        "cwd": str(root / "ProjectA"),
                        "message": {"role": "user", "content": "Build a thing"},
                    },
                    {
                        "type": "assistant",
                        "sessionId": "session-a",
                        "timestamp": "2026-06-07T10:01:00Z",
                        "requestId": "req-1",
                        "message": {
                            "role": "assistant",
                            "model": "claude-test",
                            "usage": {
                                "input_tokens": 10,
                                "cache_read_input_tokens": 20,
                                "cache_creation_input_tokens": 30,
                                "output_tokens": 40,
                            },
                        },
                    },
                ],
            )

            codex_file = root / ".codex" / "sessions" / "2026" / "06" / "07" / "rollout.jsonl"
            write_jsonl(
                codex_file,
                [
                    {
                        "type": "session_meta",
                        "timestamp": "2026-06-07T11:00:00Z",
                        "payload": {"type": "session_meta", "id": "codex-a", "cwd": str(root / "ProjectB")},
                    },
                    {
                        "type": "event_msg",
                        "timestamp": "2026-06-07T11:01:00Z",
                        "payload": {
                            "type": "token_count",
                            "info": {
                                "total_token_usage": {
                                    "input_tokens": 100,
                                    "cached_input_tokens": 40,
                                    "output_tokens": 20,
                                    "reasoning_output_tokens": 0,
                                    "total_tokens": 120,
                                },
                                "last_token_usage": {
                                    "input_tokens": 100,
                                    "cached_input_tokens": 40,
                                    "output_tokens": 20,
                                    "reasoning_output_tokens": 0,
                                    "total_tokens": 120,
                                },
                            },
                        },
                    },
                    {
                        "type": "event_msg",
                        "timestamp": "2026-06-07T11:01:05Z",
                        "payload": {
                            "type": "token_count",
                            "info": {
                                "total_token_usage": {
                                    "input_tokens": 100,
                                    "cached_input_tokens": 40,
                                    "output_tokens": 20,
                                    "reasoning_output_tokens": 0,
                                    "total_tokens": 120,
                                }
                            },
                        },
                    },
                    {
                        "type": "event_msg",
                        "timestamp": "2026-06-07T11:02:00Z",
                        "payload": {
                            "type": "token_count",
                            "info": {
                                "total_token_usage": {
                                    "input_tokens": 160,
                                    "cached_input_tokens": 50,
                                    "output_tokens": 30,
                                    "reasoning_output_tokens": 5,
                                    "total_tokens": 190,
                                }
                            },
                        },
                    },
                ],
            )

            cline_task = appdata / "Code" / "User" / "globalStorage" / "saoudrizwan.claude-dev" / "tasks" / "task-a"
            cline_task.mkdir(parents=True)
            (cline_task / "task_metadata.json").write_text(json.dumps({"model_usage": []}), encoding="utf-8")
            (cline_task / "ui_messages.json").write_text(
                json.dumps(
                    [
                        {"type": "say", "say": "task", "text": "Cline title", "ts": 1778616791744},
                        {
                            "type": "say",
                            "say": "api_req_started",
                            "ts": 1778616792744,
                            "modelInfo": {"modelId": "cline-model"},
                            "text": json.dumps({"tokensIn": 7, "tokensOut": 8, "cacheReads": 9, "cacheWrites": 10}),
                        },
                    ]
                ),
                encoding="utf-8",
            )

            config = deep_merge(DEFAULT_CONFIG, {"antigravity_dir": ""})
            with EnvPatch(HOME=str(root), USERPROFILE=str(root), APPDATA=str(appdata), CODEX_HOME=str(root / ".codex")):
                data = collect_all_usage(config)

            agents = {a["agent"]: a for a in data["agents"]}
            self.assertEqual(agents["claude_code"]["total_tokens"], 100)
            self.assertEqual(agents["claude_code"]["active_tokens"], 80)
            self.assertEqual(agents["codex"]["total_tokens"], 190)
            self.assertEqual(agents["codex"]["active_tokens"], 140)
            self.assertEqual(agents["codex"]["chats"], 2)
            self.assertEqual(agents["cline"]["total_tokens"], 34)
            self.assertEqual(agents["cline"]["active_tokens"], 25)
            self.assertEqual(data["summary"]["total_tokens"], 324)
            self.assertEqual(data["summary"]["active_tokens"], 245)
            self.assertIn("current_session", data["summary"])
            self.assertIn("windows_by_agent", data["summary"])
            self.assertIn("rolling_usage_by_agent", data["summary"])
            summary_line = compact_summary(data)
            self.assertIn("TokenLens |", summary_line)
            self.assertIn("| active |", summary_line)
            self.assertIn("session ", summary_line)
            self.assertIn("last ", summary_line)
            self.assertIn("5h ", summary_line)
            self.assertIn("24h ", summary_line)
            self.assertTrue(summary_line.endswith("estimated"))
            self.assertNotIn("\n", summary_line)
            payload = compact_summary_payload(data)
            self.assertEqual(payload["line"], summary_line)
            self.assertEqual(payload["agent_id"], "codex")
            self.assertIn("rolling_5h_active_tokens", payload)

            with EnvPatch(HOME=str(root), USERPROFILE=str(root), APPDATA=str(appdata), CODEX_HOME=str(root / ".codex")):
                codex_only = collect_all_usage(config, only_agents="codex")
            self.assertEqual(codex_only["summary"]["active_tokens"], 140)
            self.assertEqual(codex_only["summary"]["sessions"], 1)
            self.assertEqual(codex_only["summary"]["current_session"]["agent"], "codex")

            with EnvPatch(HOME=str(root), USERPROFILE=str(root), APPDATA=str(appdata), CODEX_HOME=str(root / ".codex"), CODEX_THREAD_ID="thread-a"):
                current_only = collect_all_usage(config, only_agents="current")
            self.assertEqual(current_only["summary"]["current_session"]["agent"], "codex")

    def test_install_workspace_rules_creates_common_agent_rule_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            touched = install_workspace_rules(workspace_dir=root, cli_path=root / "TokenLens" / "cli.py")
            touched_names = {Path(path).name for path in touched}

            for filename in [".airules", ".cursorrules", ".clinerules", "AGENTS.md", "CLAUDE.md", "GEMINI.md"]:
                self.assertIn(filename, touched_names)
                content = (root / filename).read_text(encoding="utf-8")
                self.assertIn("--compact", content)
                self.assertIn("get_token_summary", content)
                self.assertIn("never use dashboard output for routine turn summaries", content)
                self.assertIn("Never run plain `python cli.py`", content)

    def test_install_antigravity_mcp_writes_config_and_tool_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "mcp_config.json"
            result = install_antigravity_mcp(config_path=config_path)

            self.assertTrue(result["changed"])
            data = json.loads(config_path.read_text(encoding="utf-8"))
            entry = data["mcpServers"]["tokenlens"]
            self.assertTrue(entry["args"][0].endswith("mcp_server.py"))
            self.assertEqual(entry["args"][1:], ["--agent", "antigravity"])
            self.assertTrue(Path(result["metadata_dir"], "get_token_summary.json").exists())
            instructions = Path(result["metadata_dir"], "instructions.md").read_text(encoding="utf-8")
            self.assertIn("do not run shell commands", instructions)

    def test_generic_mcp_install_and_snippets_support_current_agent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "mcp_config.json"
            result = install_json_mcp(config_path=config_path, default_agent="current")

            self.assertTrue(result["changed"])
            data = json.loads(config_path.read_text(encoding="utf-8"))
            entry = data["mcpServers"]["tokenlens"]
            self.assertEqual(entry["args"][-2:], ["--agent", "current"])
            self.assertIn('"mcpServers"', mcp_json_snippet(default_agent="codex"))
            self.assertIn("[mcp_servers.tokenlens]", mcp_toml_snippet(default_agent="codex"))
            self.assertEqual(detect_current_agent({"CODEX_THREAD_ID": "thread-a"}), "codex")

    def test_active_tokens_exclude_cached_reads_for_any_agent(self):
        session = make_session("antigravity", "ag-a", "Project", "Title")
        session["generations"] = [
            make_generation(
                "antigravity",
                "ag-a",
                "1",
                timestamp="2026-06-07T12:00:00Z",
                input_tokens=100,
                cached_tokens=900,
                cache_write_tokens=20,
                output_tokens=30,
                reasoning_tokens=5,
            )
        ]
        session = finalize_session(session)

        self.assertEqual(session["totals"]["total_tokens"], 1055)
        self.assertEqual(session["totals"]["active_tokens"], 155)

        summary = summarize_usage([session], DEFAULT_CONFIG)
        self.assertEqual(summary["total_tokens"], 1055)
        self.assertEqual(summary["active_tokens"], 155)


if __name__ == "__main__":
    unittest.main()
