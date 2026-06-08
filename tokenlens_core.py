import argparse
import datetime as _dt
import glob
import json
import os
import sqlite3
from pathlib import Path
from urllib.parse import quote


AGENT_NAMES = {
    "antigravity": "Antigravity",
    "claude_code": "Claude Code",
    "codex": "Codex",
    "cline": "Cline",
}


DEFAULT_CONFIG = {
    "antigravity_dir": "",
    "pricing": {
        "mode": "known_only",
        "default_input_per_1m": None,
        "default_output_per_1m": None,
    },
    "billing": {
        "agents": {
            "antigravity": "subscription",
            "claude_code": "subscription",
            "codex": "subscription",
            "cline": "recorded_or_metered",
        },
        "model_prices": {},
    },
    "display": {
        "show_last_turn": True,
        "show_cached_percentage": True,
    },
    "dashboard": {
        "live_pricing": False,
    },
    "agents": {
        "antigravity": True,
        "claude_code": True,
        "codex": True,
        "cline": True,
    },
    "agent_dirs": {
        "antigravity": [],
        "claude_code": [],
        "codex": [],
        "cline": [],
    },
}


def deep_merge(base, override):
    result = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(config_path=None):
    path = Path(config_path or Path(__file__).with_name("config.json"))
    if not path.exists():
        return json.loads(json.dumps(DEFAULT_CONFIG))
    try:
        user_config = json.loads(path.read_text(encoding="utf-8"))
        return deep_merge(DEFAULT_CONFIG, user_config)
    except Exception:
        return json.loads(json.dumps(DEFAULT_CONFIG))


def expand_path(path):
    if not path:
        return ""
    return os.path.abspath(os.path.expandvars(os.path.expanduser(path)))


def unique_existing_dirs(paths):
    seen = set()
    result = []
    for path in paths:
        expanded = expand_path(path)
        if not expanded or not os.path.isdir(expanded):
            continue
        key = os.path.normcase(os.path.abspath(expanded))
        if key not in seen:
            seen.add(key)
            result.append(expanded)
    return result


def fmt_tokens(n):
    n = int(n or 0)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def parse_time(value):
    if not value:
        return None
    if isinstance(value, (int, float)):
        try:
            if value > 10_000_000_000:
                value = value / 1000
            return _dt.datetime.fromtimestamp(value)
        except Exception:
            return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = _dt.datetime.fromisoformat(text)
            if parsed.tzinfo:
                parsed = parsed.astimezone().replace(tzinfo=None)
            return parsed
        except Exception:
            return None
    return None


def to_iso(value):
    parsed = parse_time(value)
    return parsed.isoformat() if parsed else ""


def safe_title(text, fallback="Untitled", limit=80):
    if not text:
        return fallback
    text = " ".join(str(text).split())
    if not text:
        return fallback
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text


def project_name_from_path(path, fallback="Unknown Project"):
    if not path:
        return fallback
    cleaned = str(path).replace("\\", "/").rstrip("/")
    if cleaned.startswith("file:///"):
        cleaned = cleaned[8:]
    name = os.path.basename(cleaned)
    return name or fallback


def read_json_file(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            return json.load(handle)
    except Exception:
        return None


def iter_jsonl(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            for line_no, line in enumerate(handle, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    yield line_no, json.loads(line)
                except Exception:
                    continue
    except Exception:
        return


def usage_total(usage):
    return int(
        (usage.get("input_tokens") or 0)
        + (usage.get("cached_tokens") or 0)
        + (usage.get("cache_write_tokens") or 0)
        + (usage.get("output_tokens") or 0)
        + (usage.get("reasoning_tokens") or 0)
    )


def make_generation(
    agent,
    session_id,
    chat_id,
    timestamp="",
    model="Unknown Model",
    input_tokens=0,
    cached_tokens=0,
    cache_write_tokens=0,
    output_tokens=0,
    reasoning_tokens=0,
    total_tokens=None,
    cost=None,
    source_path="",
    confidence="exact",
):
    input_tokens = int(input_tokens or 0)
    cached_tokens = int(cached_tokens or 0)
    cache_write_tokens = int(cache_write_tokens or 0)
    output_tokens = int(output_tokens or 0)
    reasoning_tokens = int(reasoning_tokens or 0)
    calculated = input_tokens + cached_tokens + cache_write_tokens + output_tokens + reasoning_tokens
    return {
        "agent": agent,
        "agent_name": AGENT_NAMES.get(agent, agent),
        "session_id": session_id or "",
        "chat_id": str(chat_id or ""),
        "timestamp": to_iso(timestamp) if timestamp else "",
        "model": model or "Unknown Model",
        "input_tokens": input_tokens,
        "cached_tokens": cached_tokens,
        "cache_write_tokens": cache_write_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
        "total_tokens": int(total_tokens if total_tokens is not None else calculated),
        "cost": cost,
        "source_path": source_path,
        "confidence": confidence,
    }


def make_session(agent, session_id, project, title, source_path="", project_path=""):
    return {
        "agent": agent,
        "agent_name": AGENT_NAMES.get(agent, agent),
        "conversation_id": session_id or "",
        "session_id": session_id or "",
        "title": safe_title(title, fallback=f"{AGENT_NAMES.get(agent, agent)} session"),
        "project": project or "Unknown Project",
        "project_path": project_path or "",
        "generations": [],
        "start_time": None,
        "end_time": None,
        "source_path": source_path,
    }


def finalize_session(session):
    timestamps = [parse_time(g.get("timestamp")) for g in session.get("generations", []) if g.get("timestamp")]
    timestamps = [t for t in timestamps if t]
    if timestamps:
        session["start_time"] = min(timestamps).isoformat()
        session["end_time"] = max(timestamps).isoformat()
    total = {
        "input_tokens": 0,
        "cached_tokens": 0,
        "cache_write_tokens": 0,
        "output_tokens": 0,
        "reasoning_tokens": 0,
        "total_tokens": 0,
        "cost": 0.0,
    }
    cost_seen = False
    for gen in session.get("generations", []):
        for key in ("input_tokens", "cached_tokens", "cache_write_tokens", "output_tokens", "reasoning_tokens"):
            total[key] += int(gen.get(key) or 0)
        total["total_tokens"] += int(gen.get("total_tokens") or usage_total(gen))
        if gen.get("cost") is not None:
            cost_seen = True
            try:
                total["cost"] += float(gen.get("cost") or 0)
            except Exception:
                pass
    if not cost_seen:
        total["cost"] = None
    session["totals"] = total
    session["chat_count"] = len(session.get("generations", []))
    return session


def sqlite_connect_ro(db_path):
    resolved = Path(db_path).resolve()
    as_posix = resolved.as_posix()
    uri = "file:" + quote(as_posix, safe="/:") + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=1.0)
    conn.execute("PRAGMA query_only=ON")
    conn.execute("PRAGMA busy_timeout=1000")
    return conn


def parse_varint(data, offset):
    result = 0
    shift = 0
    while offset < len(data) and shift <= 70:
        b = data[offset]
        result |= (b & 0x7F) << shift
        offset += 1
        if not (b & 0x80):
            return result, offset
        shift += 7
    return result, offset


def parse_proto(data):
    fields = {}
    offset = 0
    while offset < len(data):
        tag_type, offset = parse_varint(data, offset)
        if tag_type == 0:
            break
        tag = tag_type >> 3
        wire_type = tag_type & 0x07

        if wire_type == 0:
            val, offset = parse_varint(data, offset)
        elif wire_type == 1:
            if offset + 8 > len(data):
                break
            val = data[offset : offset + 8]
            offset += 8
        elif wire_type == 2:
            length, offset = parse_varint(data, offset)
            if length < 0 or offset + length > len(data):
                break
            val = data[offset : offset + length]
            offset += length
        elif wire_type == 5:
            if offset + 4 > len(data):
                break
            val = data[offset : offset + 4]
            offset += 4
        else:
            break

        fields.setdefault(tag, []).append((wire_type, val))
    return fields


def get_submsg(fields, tag):
    if tag in fields:
        wire_type, val = fields[tag][0]
        if wire_type == 2:
            return parse_proto(val)
    return None


def get_int(fields, tag):
    if tag in fields:
        wire_type, val = fields[tag][0]
        if wire_type == 0:
            return int(val or 0)
    return 0


def get_string(fields, tag):
    if tag in fields:
        wire_type, val = fields[tag][0]
        if wire_type == 2:
            return val.decode("utf-8", errors="ignore")
    return None


def get_field_values(fields, tag):
    return fields.get(tag, []) if isinstance(fields, dict) else []


def antigravity_roots(config, custom_path=None):
    paths = []
    if custom_path:
        paths.append(custom_path)
    cfg_path = config.get("antigravity_dir")
    if cfg_path:
        paths.append(cfg_path)
    paths.extend(config.get("agent_dirs", {}).get("antigravity") or [])
    home = os.path.expanduser("~")
    paths.append(os.path.join(home, ".gemini", "antigravity"))
    paths.append(os.path.join(home, ".gemini", "antigravity-ide"))
    return unique_existing_dirs(paths)


def load_antigravity_metadata(base_dir):
    pb_path = os.path.join(base_dir, "agyhub_summaries_proto.pb")
    conv_metadata = {}
    if not os.path.exists(pb_path):
        return conv_metadata
    try:
        with open(pb_path, "rb") as handle:
            pb_fields = parse_proto(handle.read())
        for t, conv_msg in pb_fields.get(1, []):
            if t != 2:
                continue
            c_msg = parse_proto(conv_msg)
            c_id = get_string(c_msg, 1)
            detail = get_submsg(c_msg, 2)
            project = ""
            title = ""
            if detail:
                title = get_string(detail, 1) or ""
                p_msg = get_submsg(detail, 9)
                if p_msg:
                    p_det = get_submsg(p_msg, 3)
                    if p_det:
                        project = get_string(p_det, 1) or ""
            if c_id:
                conv_metadata[c_id] = {"title": title, "project": project}
    except Exception:
        pass
    return conv_metadata


def antigravity_title_from_transcript(base_dir, conv_id, fallback):
    transcript_path = os.path.join(base_dir, "brain", conv_id, ".system_generated", "logs", "transcript.jsonl")
    if not os.path.exists(transcript_path):
        return fallback
    for _, obj in iter_jsonl(transcript_path):
        if obj.get("type") != "USER_INPUT":
            continue
        content = obj.get("content", "")
        if "<USER_REQUEST>" in content:
            content = content.split("<USER_REQUEST>", 1)[1].split("</USER_REQUEST>", 1)[0]
        return safe_title(content, fallback=fallback, limit=80)
    return fallback


def collect_antigravity(config, custom_path=None):
    sessions = []
    sources = []
    for base_dir in antigravity_roots(config, custom_path):
        conv_dir = os.path.join(base_dir, "conversations")
        if not os.path.isdir(conv_dir):
            sources.append({"agent": "antigravity", "path": base_dir, "status": "missing_conversations", "sessions": 0, "chats": 0})
            continue

        metadata = load_antigravity_metadata(base_dir)
        db_files = glob.glob(os.path.join(conv_dir, "*.db"))
        root_sessions = 0
        root_chats = 0

        for db_path in db_files:
            conv_id = os.path.splitext(os.path.basename(db_path))[0]
            meta = metadata.get(conv_id, {})
            project = meta.get("project") or "Unknown Project"
            workspace_uri = ""
            title = meta.get("title") or "Untitled"
            generations = []

            try:
                with sqlite_connect_ro(db_path) as conn:
                    cursor = conn.cursor()
                    try:
                        cursor.execute("SELECT data FROM trajectory_metadata_blob LIMIT 1;")
                        row = cursor.fetchone()
                        if row and row[0]:
                            traj_fields = parse_proto(row[0])
                            p_msg = get_submsg(traj_fields, 3)
                            if p_msg:
                                project = get_string(p_msg, 1) or project
                            workspace_uri = get_string(traj_fields, 1) or ""
                    except Exception:
                        pass

                    try:
                        cursor.execute("SELECT idx, data FROM gen_metadata ORDER BY idx ASC;")
                        rows = cursor.fetchall()
                    except Exception:
                        rows = []

                    for idx, blob in rows:
                        if not blob:
                            continue
                        fields = parse_proto(blob)
                        model_fields = get_submsg(fields, 1)
                        if not model_fields:
                            continue
                        model_name = get_string(model_fields, 19) or "Unknown Model"
                        out_tokens = get_int(model_fields, 3) or 0
                        usage_metadata = get_submsg(model_fields, 9)
                        in_tokens = 0
                        cached_tokens = 0
                        timestamp_sec = None

                        if usage_metadata:
                            f10_msg = get_submsg(usage_metadata, 10)
                            if f10_msg:
                                in_tokens = get_int(f10_msg, 1) or 0
                                for t3, val3 in get_field_values(f10_msg, 3):
                                    if t3 == 2:
                                        f3_msg = parse_proto(val3)
                                        for t1, val1 in get_field_values(f3_msg, 1):
                                            if t1 == 2:
                                                block = parse_proto(val1)
                                                tok = get_int(block, 4) or 0
                                                is_cached = get_int(block, 3) == 1
                                                if is_cached:
                                                    cached_tokens += tok
                                in_tokens = max(0, in_tokens - cached_tokens)

                            f4_msg = get_submsg(usage_metadata, 4)
                            if f4_msg:
                                timestamp_sec = get_int(f4_msg, 1)

                        generations.append(
                            make_generation(
                                "antigravity",
                                conv_id,
                                idx,
                                timestamp=timestamp_sec,
                                model=model_name,
                                input_tokens=in_tokens,
                                cached_tokens=cached_tokens,
                                output_tokens=out_tokens,
                                source_path=db_path,
                            )
                        )
            except Exception:
                continue

            if not generations:
                continue
            if not project and workspace_uri:
                project = project_name_from_path(workspace_uri)
            title = antigravity_title_from_transcript(base_dir, conv_id, title)
            session = make_session("antigravity", conv_id, project, title, source_path=db_path, project_path=workspace_uri)
            session["generations"] = generations
            sessions.append(finalize_session(session))
            root_sessions += 1
            root_chats += len(generations)

        sources.append({"agent": "antigravity", "path": base_dir, "status": "ok", "sessions": root_sessions, "chats": root_chats})
    return sessions, sources


def extract_message_text(message):
    if isinstance(message, str):
        return message
    if not isinstance(message, dict):
        return ""
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return " ".join(parts)
    return ""


def claude_roots(config):
    paths = list(config.get("agent_dirs", {}).get("claude_code") or [])
    paths.append(os.path.join(os.path.expanduser("~"), ".claude", "projects"))
    return unique_existing_dirs(paths)


def collect_claude_code(config):
    sessions = []
    sources = []
    for root in claude_roots(config):
        files = glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True)
        root_sessions = 0
        root_chats = 0
        for path in files:
            session_id = Path(path).stem
            project_path = ""
            project = project_name_from_path(Path(path).parent.name)
            title = "Claude Code session"
            usage_by_request = {}
            order = []

            for line_no, obj in iter_jsonl(path):
                if not isinstance(obj, dict):
                    continue
                if obj.get("cwd") and not project_path:
                    project_path = obj.get("cwd")
                    project = project_name_from_path(project_path, fallback=project)
                if obj.get("sessionId"):
                    session_id = str(obj.get("sessionId"))
                if obj.get("type") == "user" and title == "Claude Code session":
                    title = safe_title(extract_message_text(obj.get("message")), fallback=title)
                if obj.get("type") != "assistant":
                    continue
                message = obj.get("message") or {}
                usage = message.get("usage") or {}
                if not isinstance(usage, dict):
                    continue
                request_id = obj.get("requestId") or obj.get("uuid") or f"{Path(path).name}:{line_no}"
                input_tokens = int(usage.get("input_tokens") or 0)
                cached_tokens = int(usage.get("cache_read_input_tokens") or 0)
                cache_write_tokens = int(usage.get("cache_creation_input_tokens") or 0)
                output_tokens = int(usage.get("output_tokens") or 0)
                total_tokens = input_tokens + cached_tokens + cache_write_tokens + output_tokens
                generation = make_generation(
                    "claude_code",
                    session_id,
                    request_id,
                    timestamp=obj.get("timestamp"),
                    model=message.get("model") or "Unknown Model",
                    input_tokens=input_tokens,
                    cached_tokens=cached_tokens,
                    cache_write_tokens=cache_write_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    source_path=path,
                )
                old = usage_by_request.get(request_id)
                if not old:
                    order.append(request_id)
                    usage_by_request[request_id] = generation
                elif generation["total_tokens"] >= old["total_tokens"]:
                    usage_by_request[request_id] = generation

            generations = [usage_by_request[key] for key in order if usage_by_request.get(key)]
            if not generations:
                continue
            session = make_session("claude_code", session_id, project, title, source_path=path, project_path=project_path)
            session["generations"] = generations
            sessions.append(finalize_session(session))
            root_sessions += 1
            root_chats += len(generations)
        sources.append({"agent": "claude_code", "path": root, "status": "ok", "sessions": root_sessions, "chats": root_chats})
    return sessions, sources


def codex_roots(config):
    paths = list(config.get("agent_dirs", {}).get("codex") or [])
    paths.append(os.environ.get("CODEX_HOME", ""))
    paths.append(os.path.join(os.path.expanduser("~"), ".codex"))
    return unique_existing_dirs(paths)


def codex_usage_from_raw(raw):
    if not isinstance(raw, dict):
        return None
    raw_input = int(raw.get("input_tokens") or 0)
    cached = int(raw.get("cached_input_tokens") or raw.get("cache_read_input_tokens") or 0)
    raw_output = int(raw.get("output_tokens") or 0)
    reasoning = int(raw.get("reasoning_output_tokens") or 0)
    total = raw.get("total_tokens")
    if total is not None and reasoning and int(total or 0) == raw_input + raw_output:
        output = max(0, raw_output - reasoning)
    else:
        output = raw_output
    if total is None:
        total = max(0, raw_input) + max(0, output) + max(0, reasoning)
    return {
        "input_tokens": max(0, raw_input - cached),
        "cached_tokens": cached,
        "cache_write_tokens": 0,
        "output_tokens": output,
        "reasoning_tokens": reasoning,
        "total_tokens": int(total or 0),
    }


def usage_delta(current, previous):
    if not current:
        return None
    if not previous:
        return current
    delta = {}
    for key in ("input_tokens", "cached_tokens", "cache_write_tokens", "output_tokens", "reasoning_tokens", "total_tokens"):
        delta[key] = int(current.get(key) or 0) - int(previous.get(key) or 0)
    if delta["total_tokens"] <= 0 and all(v <= 0 for v in delta.values()):
        return None
    for key, value in list(delta.items()):
        delta[key] = max(0, value)
    return delta


def collect_codex(config):
    sessions = []
    sources = []
    for root in codex_roots(config):
        files = glob.glob(os.path.join(root, "sessions", "**", "*.jsonl"), recursive=True)
        root_sessions = 0
        root_chats = 0
        for path in files:
            if f"{os.sep}.tmp{os.sep}" in path:
                continue
            session_id = Path(path).stem
            project_path = ""
            project = "Unknown Project"
            title = "Codex session"
            model = "Unknown Model"
            generations = []
            previous_total = None
            seen_last = set()

            for line_no, obj in iter_jsonl(path):
                if not isinstance(obj, dict):
                    continue
                payload = obj.get("payload") if isinstance(obj.get("payload"), dict) else {}
                ptype = payload.get("type")
                if obj.get("type") == "session_meta":
                    session_id = str(payload.get("id") or session_id)
                    project_path = payload.get("cwd") or project_path
                    project = project_name_from_path(project_path, fallback=project)
                    model = payload.get("model") or model
                elif obj.get("type") == "turn_context":
                    project_path = payload.get("cwd") or project_path
                    project = project_name_from_path(project_path, fallback=project)
                    model = payload.get("model") or model
                elif obj.get("type") == "response_item" and payload.get("role") == "user" and title == "Codex session":
                    title = safe_title(extract_codex_content(payload.get("content")), fallback=title)

                if ptype != "token_count":
                    continue
                info = payload.get("info") if isinstance(payload.get("info"), dict) else {}
                total_usage = codex_usage_from_raw(info.get("total_token_usage"))
                last_usage = codex_usage_from_raw(info.get("last_token_usage"))
                delta = None
                if total_usage:
                    delta = usage_delta(total_usage, previous_total)
                    if delta:
                        previous_total = total_usage
                    elif previous_total is None:
                        previous_total = total_usage
                elif last_usage:
                    fingerprint = tuple(last_usage.get(k, 0) for k in sorted(last_usage))
                    if fingerprint not in seen_last:
                        seen_last.add(fingerprint)
                        delta = last_usage
                if not delta or int(delta.get("total_tokens") or 0) <= 0:
                    continue
                generations.append(
                    make_generation(
                        "codex",
                        session_id,
                        f"{Path(path).name}:{line_no}",
                        timestamp=obj.get("timestamp"),
                        model=model,
                        source_path=path,
                        **delta,
                    )
                )

            if not generations:
                continue
            session = make_session("codex", session_id, project, title, source_path=path, project_path=project_path)
            session["generations"] = generations
            sessions.append(finalize_session(session))
            root_sessions += 1
            root_chats += len(generations)
        sources.append({"agent": "codex", "path": root, "status": "ok", "sessions": root_sessions, "chats": root_chats})
    return sessions, sources


def extract_codex_content(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if isinstance(item.get("text"), str):
                    parts.append(item["text"])
                elif isinstance(item.get("content"), str):
                    parts.append(item["content"])
        return " ".join(parts)
    return ""


def cline_roots(config):
    paths = list(config.get("agent_dirs", {}).get("cline") or [])
    home = os.path.expanduser("~")
    appdata = os.environ.get("APPDATA", "")
    paths.append(os.path.join(home, ".cline", "data", "tasks"))
    for app_name in ("Code", "Cursor", "VSCodium"):
        if appdata:
            base = os.path.join(appdata, app_name, "User", "globalStorage")
            paths.append(os.path.join(base, "saoudrizwan.claude-dev", "tasks"))
            paths.append(os.path.join(base, "cline.cline", "tasks"))
            paths.append(os.path.join(base, "kilocode.kilo-code", "tasks"))
            paths.append(os.path.join(base, "rooveterinaryinc.roo-cline", "tasks"))
    return unique_existing_dirs(paths)


def collect_cline(config):
    sessions = []
    sources = []
    for root in cline_roots(config):
        task_dirs = [p for p in glob.glob(os.path.join(root, "*")) if os.path.isdir(p)]
        root_sessions = 0
        root_chats = 0
        unmetered = 0
        for task_dir in task_dirs:
            task_id = os.path.basename(task_dir)
            ui_path = os.path.join(task_dir, "ui_messages.json")
            metadata_path = os.path.join(task_dir, "task_metadata.json")
            if not os.path.exists(ui_path):
                continue
            ui_messages = read_json_file(ui_path)
            if not isinstance(ui_messages, list):
                continue
            metadata = read_json_file(metadata_path) or {}
            project = project_name_from_cline_metadata(metadata, task_dir)
            title = "Cline task"
            generations = []
            last_model = "Unknown Model"

            for index, item in enumerate(ui_messages):
                if not isinstance(item, dict):
                    continue
                model_info = item.get("modelInfo") if isinstance(item.get("modelInfo"), dict) else {}
                last_model = model_info.get("modelId") or last_model
                if item.get("say") == "task" and title == "Cline task":
                    title = safe_title(item.get("text"), fallback=title)
                if item.get("say") != "api_req_started" or not item.get("text"):
                    continue
                try:
                    req = json.loads(item.get("text") or "{}")
                except Exception:
                    continue
                if not any(k in req for k in ("tokensIn", "tokensOut", "cacheReads", "cacheWrites", "cost")):
                    continue
                input_tokens = int(req.get("tokensIn") or 0)
                cached_tokens = int(req.get("cacheReads") or 0)
                cache_write_tokens = int(req.get("cacheWrites") or 0)
                output_tokens = int(req.get("tokensOut") or 0)
                total_tokens = input_tokens + cached_tokens + cache_write_tokens + output_tokens
                cost = req.get("cost")
                try:
                    cost = float(cost) if cost is not None else None
                except Exception:
                    cost = None
                generations.append(
                    make_generation(
                        "cline",
                        task_id,
                        index,
                        timestamp=item.get("ts"),
                        model=last_model,
                        input_tokens=input_tokens,
                        cached_tokens=cached_tokens,
                        cache_write_tokens=cache_write_tokens,
                        output_tokens=output_tokens,
                        total_tokens=total_tokens,
                        cost=cost,
                        source_path=ui_path,
                    )
                )

            if not generations:
                unmetered += 1
                continue
            session = make_session("cline", task_id, project, title, source_path=ui_path)
            session["generations"] = generations
            sessions.append(finalize_session(session))
            root_sessions += 1
            root_chats += len(generations)
        sources.append(
            {
                "agent": "cline",
                "path": root,
                "status": "ok",
                "sessions": root_sessions,
                "chats": root_chats,
                "unmetered_sessions": unmetered,
            }
        )
    return sessions, sources


def project_name_from_cline_metadata(metadata, task_dir):
    env = metadata.get("environment_history") if isinstance(metadata, dict) else None
    if isinstance(env, list):
        for item in reversed(env):
            if isinstance(item, dict):
                cwd = item.get("cwd") or item.get("workspacePath") or item.get("workspace_path")
                if cwd:
                    return project_name_from_path(cwd)
    return project_name_from_path(os.path.dirname(os.path.dirname(task_dir)), fallback="Cline")


def is_agent_enabled(config, agent):
    agents = config.get("agents", {})
    return bool(agents.get(agent, True))


def collect_all_usage(config=None, custom_antigravity_dir=None):
    config = config or load_config()
    sessions = []
    sources = []
    collectors = [
        ("antigravity", collect_antigravity, {"custom_path": custom_antigravity_dir}),
        ("claude_code", collect_claude_code, {}),
        ("codex", collect_codex, {}),
        ("cline", collect_cline, {}),
    ]
    for agent, collector, kwargs in collectors:
        if not is_agent_enabled(config, agent):
            sources.append({"agent": agent, "path": "", "status": "disabled", "sessions": 0, "chats": 0})
            continue
        try:
            if kwargs:
                found_sessions, found_sources = collector(config, **kwargs)
            else:
                found_sessions, found_sources = collector(config)
            sessions.extend(found_sessions)
            sources.extend(found_sources)
        except Exception as exc:
            sources.append({"agent": agent, "path": "", "status": f"error:{type(exc).__name__}", "sessions": 0, "chats": 0})

    sessions.sort(key=lambda s: parse_time(s.get("end_time") or s.get("start_time")) or _dt.datetime.min, reverse=True)
    return {
        "sessions": sessions,
        "sources": sources,
        "agents": summarize_agents(sessions, sources),
        "summary": summarize_usage(sessions, config),
        "config": config,
    }


def summarize_agents(sessions, sources):
    result = {}
    for agent in AGENT_NAMES:
        result[agent] = {
            "agent": agent,
            "agent_name": AGENT_NAMES[agent],
            "sessions": 0,
            "chats": 0,
            "total_tokens": 0,
            "input_tokens": 0,
            "cached_tokens": 0,
            "cache_write_tokens": 0,
            "output_tokens": 0,
            "reasoning_tokens": 0,
            "sources": [],
        }
    for source in sources:
        agent = source.get("agent")
        if agent not in result:
            result[agent] = {"agent": agent, "agent_name": AGENT_NAMES.get(agent, agent), "sources": []}
        result[agent].setdefault("sources", []).append(source)
    for session in sessions:
        agent = session.get("agent", "unknown")
        bucket = result.setdefault(agent, {"agent": agent, "agent_name": AGENT_NAMES.get(agent, agent), "sources": []})
        bucket["sessions"] = bucket.get("sessions", 0) + 1
        bucket["chats"] = bucket.get("chats", 0) + len(session.get("generations", []))
        totals = session.get("totals", {})
        for key in ("input_tokens", "cached_tokens", "cache_write_tokens", "output_tokens", "reasoning_tokens", "total_tokens"):
            bucket[key] = bucket.get(key, 0) + int(totals.get(key) or 0)
    return list(result.values())


def summarize_usage(sessions, config):
    now = _dt.datetime.now()
    windows = {
        "five_hour": now - _dt.timedelta(hours=5),
        "twenty_four_hour": now - _dt.timedelta(hours=24),
        "weekly": now - _dt.timedelta(days=7),
        "monthly": now - _dt.timedelta(days=30),
    }
    summary = {
        "input_tokens": 0,
        "cached_tokens": 0,
        "cache_write_tokens": 0,
        "output_tokens": 0,
        "reasoning_tokens": 0,
        "total_tokens": 0,
        "sessions": len(sessions),
        "chats": 0,
        "windows": {key: 0 for key in windows},
        "windows_by_agent": {},
        "last_chat": None,
        "current_session": None,
    }
    last_time = None
    for session in sessions:
        summary["chats"] += len(session.get("generations", []))
        for gen in session.get("generations", []):
            total = int(gen.get("total_tokens") or usage_total(gen))
            for key in ("input_tokens", "cached_tokens", "cache_write_tokens", "output_tokens", "reasoning_tokens"):
                summary[key] += int(gen.get(key) or 0)
            summary["total_tokens"] += total
            ts = parse_time(gen.get("timestamp"))
            if ts:
                agent = session.get("agent", "unknown")
                agent_windows = summary["windows_by_agent"].setdefault(agent, {key: 0 for key in windows})
                for key, start in windows.items():
                    if start <= ts <= now:
                        summary["windows"][key] += total
                        agent_windows[key] += total
                if last_time is None or ts > last_time:
                    last_time = ts
                    summary["last_chat"] = dict(gen)
                    summary["last_chat"]["project"] = session.get("project")
                    summary["last_chat"]["title"] = session.get("title")
                    summary["current_session"] = {
                        "agent": session.get("agent"),
                        "agent_name": session.get("agent_name"),
                        "session_id": session.get("session_id"),
                        "project": session.get("project"),
                        "title": session.get("title"),
                        "total_tokens": int((session.get("totals") or {}).get("total_tokens") or 0),
                        "chats": len(session.get("generations", [])),
                    }
    summary["rolling_usage"] = {
        "five_hour": rolling_usage_summary(summary["windows"]["five_hour"]),
        "twenty_four_hour": rolling_usage_summary(summary["windows"]["twenty_four_hour"]),
        "weekly": rolling_usage_summary(summary["windows"]["weekly"]),
        "monthly": rolling_usage_summary(summary["windows"]["monthly"]),
    }
    summary["rolling_usage_by_agent"] = {
        agent: {
            "five_hour": rolling_usage_summary(agent_windows.get("five_hour", 0)),
            "twenty_four_hour": rolling_usage_summary(agent_windows.get("twenty_four_hour", 0)),
            "weekly": rolling_usage_summary(agent_windows.get("weekly", 0)),
            "monthly": rolling_usage_summary(agent_windows.get("monthly", 0)),
        }
        for agent, agent_windows in summary["windows_by_agent"].items()
    }
    return summary


def rolling_usage_summary(used):
    return {"used": int(used or 0)}


def compact_summary(data):
    summary = data.get("summary", {})
    rolling_usage = summary.get("rolling_usage", {})
    last = summary.get("last_chat") or {}
    session = summary.get("current_session") or {}
    last_total = last.get("total_tokens", 0)
    session_total = session.get("total_tokens", 0)
    agent_id = session.get("agent") or last.get("agent")
    agent = session.get("agent_name") or last.get("agent_name") or AGENT_NAMES.get(last.get("agent"), "")
    agent_usage = summary.get("rolling_usage_by_agent", {}).get(agent_id, {}) if agent_id else {}
    five_hour = agent_usage.get("five_hour") or rolling_usage.get("five_hour", {})
    twenty_four_hour = agent_usage.get("twenty_four_hour") or rolling_usage.get("twenty_four_hour", {})
    five_hour_used = five_hour.get("used", 0)
    twenty_four_hour_used = twenty_four_hour.get("used", 0)
    window_text = f"5h {fmt_tokens(five_hour_used)} | 24h {fmt_tokens(twenty_four_hour_used)}"
    agent_label = agent or "Agent"
    return (
        f"TokenLens | {agent_label} | "
        f"session {fmt_tokens(session_total)} | "
        f"last {fmt_tokens(last_total)} | "
        f"{window_text} | estimated"
    )


def human_summary(data, compact=False):
    if compact:
        return compact_summary(data)
    summary = data.get("summary", {})
    lines = ["TokenLens Summary"]
    last = summary.get("last_chat")
    if last:
        current = summary.get("current_session") or {}
        if current:
            lines.append(
                "Current: "
                f"{fmt_tokens(current.get('total_tokens', 0))} "
                f"({current.get('agent_name') or AGENT_NAMES.get(current.get('agent'), 'Agent')}, "
                f"{current.get('chats', 0)} chats)"
            )
        lines.append(
            "Last: "
            f"{fmt_tokens(last.get('total_tokens', 0))} "
            f"({last.get('agent_name') or AGENT_NAMES.get(last.get('agent'), 'Agent')}, "
            f"{fmt_tokens(last.get('input_tokens', 0))} in, "
            f"{fmt_tokens(last.get('cached_tokens', 0))} cache, "
            f"{fmt_tokens(last.get('output_tokens', 0))} out)"
        )
    lines.append(
        "All: "
        f"{fmt_tokens(summary.get('total_tokens', 0))} tokens "
        f"across {summary.get('sessions', 0)} sessions/{summary.get('chats', 0)} chats"
    )
    lines.append(
        "Cache: "
        f"{fmt_tokens(summary.get('cached_tokens', 0))} read, "
        f"{fmt_tokens(summary.get('cache_write_tokens', 0))} write"
    )
    rolling_usage = summary.get("rolling_usage", {})
    lines.append(
        "Rolling: "
        f"5h {fmt_tokens(rolling_usage.get('five_hour', {}).get('used', 0))}, "
        f"24h {fmt_tokens(rolling_usage.get('twenty_four_hour', {}).get('used', 0))}, "
        f"wk {fmt_tokens(rolling_usage.get('weekly', {}).get('used', 0))}, "
        f"mo {fmt_tokens(rolling_usage.get('monthly', {}).get('used', 0))}"
    )
    agent_bits = []
    for agent in data.get("agents", []):
        if agent.get("total_tokens", 0):
            agent_bits.append(f"{agent.get('agent_name')}: {fmt_tokens(agent.get('total_tokens', 0))}")
    if agent_bits:
        lines.append("Agents: " + "; ".join(agent_bits))
    return "\n".join(lines)


def tokenlens_rule_section(cli):
    return (
        "\n\n# TokenLens\n"
        "At the end of every assistant turn, run exactly once:\n"
        f"python \"{cli}\" --compact\n"
        "Append only the returned one-line TokenLens summary. It reports current/latest session tokens (`session`), "
        "last chat tokens (`last`), and estimated current-agent rolling 5-hour and 24-hour usage. "
        "Do not expand it unless asked. The dashboard may be opened for setup or human inspection, "
        "but never use dashboard output for routine turn summaries.\n"
    )


def replace_tokenlens_rule(content, rule_section):
    marker = "# TokenLens\n"
    start = content.find(marker)
    if start == -1:
        return content.rstrip() + rule_section
    if start > 0 and content[start - 1] != "\n":
        return content.rstrip() + rule_section

    block_start = start - 1 if start > 0 else start
    next_heading = content.find("\n# ", start + len(marker))
    if next_heading == -1:
        return content[:block_start].rstrip() + rule_section
    return content[:block_start].rstrip() + rule_section + content[next_heading:]


def install_workspace_rules(workspace_dir=None, cli_path=None):
    workspace = Path(workspace_dir or os.getcwd()).resolve()
    repo_dir = Path(__file__).resolve().parent
    if workspace == repo_dir:
        return []
    cli = Path(cli_path or Path(__file__).with_name("cli.py")).resolve()
    rule_section = tokenlens_rule_section(cli)
    touched = []
    for filename in [".airules", ".cursorrules", ".clinerules"]:
        path = workspace / filename
        try:
            if path.exists():
                content = path.read_text(encoding="utf-8", errors="ignore")
                new_content = replace_tokenlens_rule(content, rule_section)
                if new_content != content:
                    path.write_text(new_content, encoding="utf-8")
                    touched.append(str(path))
            else:
                path.write_text("# Agent Rules" + rule_section, encoding="utf-8")
                touched.append(str(path))
        except Exception:
            pass
    for filename in ["AGENTS.md", "CLAUDE.md", "GEMINI.md"]:
        path = workspace / filename
        try:
            if path.exists():
                content = path.read_text(encoding="utf-8", errors="ignore")
                new_content = replace_tokenlens_rule(content, rule_section)
                if new_content != content:
                    path.write_text(new_content, encoding="utf-8")
                    touched.append(str(path))
            else:
                path.write_text("# Agent Rules" + rule_section, encoding="utf-8")
                touched.append(str(path))
        except Exception:
            pass
    return touched


def cli_arg_parser():
    parser = argparse.ArgumentParser(description="Summarize local AI agent token usage.")
    parser.add_argument("path", nargs="?", help="Optional Antigravity data directory.")
    parser.add_argument("--compact", action="store_true", help="Print a one-line agent-safe summary.")
    parser.add_argument("--json", action="store_true", help="Print normalized usage JSON.")
    parser.add_argument("--install-rules", action="store_true", help="Install token status guidance into workspace rules.")
    parser.add_argument("--workspace", help="Workspace directory for --install-rules. Defaults to the current directory.")
    parser.add_argument("--config", help="Path to config.json.")
    return parser
