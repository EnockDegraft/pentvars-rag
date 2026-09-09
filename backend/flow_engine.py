import os
import re
import json
import time
import uuid
import random

from flow import NODES, START_NODE, ISSUES, PHRASES
from rag_pipeline import answer_question

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SESSION_LOG_PATH = os.path.join(ROOT, "data", "sessions.log.jsonl")

_SESSIONS = {}
_MAX_SESSIONS = 1000
_TTL_SECONDS = 6 * 3600


# --- session store --------------------------------------------------------

def _sweep():
    now = time.time()
    stale = [sid for sid, s in _SESSIONS.items() if now - s["last_seen"] > _TTL_SECONDS]
    for sid in stale:
        _SESSIONS.pop(sid, None)
    if len(_SESSIONS) > _MAX_SESSIONS:
        for sid, _ in sorted(_SESSIONS.items(), key=lambda kv: kv[1]["last_seen"])[
            : len(_SESSIONS) - _MAX_SESSIONS
        ]:
            _SESSIONS.pop(sid, None)


def _get(session_id):
    s = _SESSIONS.get(session_id)
    if s is None:
        raise KeyError("unknown or expired session")
    s["last_seen"] = time.time()
    return s


def get_profile(session_id):
    s = _SESSIONS.get(session_id)
    if not s:
        return None
    return {"name": s["name"], "index_number": s["index_number"]}


def _log_login(session):
    try:
        os.makedirs(os.path.dirname(SESSION_LOG_PATH), exist_ok=True)
        with open(SESSION_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "session_id": session["id"],
                "name": session["name"],
                "index_number": session["index_number"],
            }) + "\n")
    except Exception:
        pass  # logging is best-effort; never break a session over it


# --- conversational helpers ------------------------------------------

def _greeting():
    """Time-of-day greeting (server local time — fine for a single-site demo)."""
    hour = time.localtime().tm_hour
    if hour < 12:
        return "Good morning"
    if hour < 17:
        return "Good afternoon"
    return "Good evening"


def _pick(session, pool_name):
    """Pick a line from a PHRASES pool, avoiding the one used last for this
    pool in this session so the assistant doesn't repeat itself."""
    pool = PHRASES.get(pool_name) or [""]
    last = session.setdefault("_last_phrase", {})
    choices = [p for p in pool if p != last.get(pool_name)] or pool
    line = random.choice(choices)
    last[pool_name] = line
    return line


# --- validation ---------------------------------------------------------

def _validate(kind, raw):
    """Return (ok: bool, cleaned: str, message: str)."""
    text = (raw or "").strip()
    if kind == "name":
        if len(text) < 2 or not re.search(r"[A-Za-z]", text):
            return False, text, "I didn't quite catch that — what's your name?"
        if len(text) > 80:
            return False, text, "That's a long one! Could you give me a shorter version of your name?"
        return True, re.sub(r"\s+", " ", text).title(), ""
    if kind == "index_number":
        cleaned = re.sub(r"\s+", "", text).upper()
        if not re.fullmatch(r"[A-Z0-9/\-]{5,15}", cleaned) or not re.search(r"\d", cleaned):
            return False, cleaned, (
                "Hmm, that doesn't look like an index number — it's usually something "
                "like UEB3402721. Mind trying again?"
            )
        return True, cleaned, ""
    return True, text, ""


# --- node resolution --------------------------------------------------

def _split_synthetic(node_id):
    """"issuelist:it" -> ("issuelist", "it"); "issue:it:portal_login" -> ..."""
    parts = node_id.split(":")
    return parts[0], parts[1:]


def _issuelist_node(cat):
    cat_data = ISSUES[cat]
    options = [
        {"label": item["label"], "next": f"issue:{cat}:{item_id}"}
        for item_id, item in cat_data["items"].items()
    ]
    options.append({"label": "Back to issue categories", "next": "issue_category"})
    options.append({"label": "Back to main menu", "next": "main_menu"})
    return {
        "prompt": f"Okay, {cat_data['title'].lower()}. Which of these is closest?",
        "expect": "choice",
        "options": options,
    }


def _issue_node(cat, item_id):
    item = ISSUES[cat]["items"][item_id]
    return {
        "_issue": (cat, item_id, item),
        "prompt": "Did that help?",
        "expect": "choice",
        "options": [
            {"label": "Another issue in this category", "next": f"issuelist:{cat}"},
            {"label": "A different kind of issue", "next": "issue_category"},
            {"label": "Back to main menu", "next": "main_menu"},
            {"label": "I'm done", "next": "goodbye"},
        ],
    }


def _resolve_node(node_id):
    if node_id in NODES:
        return dict(NODES[node_id])
    head, rest = _split_synthetic(node_id)
    if head == "issuelist" and rest and rest[0] in ISSUES:
        return _issuelist_node(rest[0])
    if head == "issue" and len(rest) == 2 and rest[0] in ISSUES \
            and rest[1] in ISSUES[rest[0]]["items"]:
        return _issue_node(rest[0], rest[1])
    raise KeyError(f"unknown node {node_id!r}")


# --- rendering --------------------------------------------------------

def _fmt(text, session, **extra):
    ctx = {
        "name": session.get("name") or "there",
        "first_name": session.get("first_name") or "there",
        "index_number": session.get("index_number") or "",
        "greeting": _greeting(),
        "topic": "",
    }
    ctx.update(extra)
    try:
        return text.format(**ctx)
    except Exception:
        return text


def _steps_block(item):
    lines = [f"**{item['label']}**", "", "Here's what to try:"]
    lines += [f"{i}. {s}" for i, s in enumerate(item["steps"], 1)]
    return "\n".join(lines)


def _render(session, extra_messages=None):
    node_id = session["node"]
    node = _resolve_node(node_id)
    messages = list(extra_messages or [])

    # An issue node front-loads: a sympathetic opener, the steps, a grounded
    # excerpt, then who to contact.
    if "_issue" in node:
        cat, _, item = node["_issue"]
        messages.append({"kind": "text", "text": _fmt(_pick(session, "issue_openers"), session)})
        messages.append({"kind": "text", "text": _steps_block(item)})
        rag = answer_question(item["rag_query"], source=ISSUES[cat].get("doc"))
        messages.append({
            "kind": "answer",
            "answer": rag["answer"],
            "sources": rag["sources"],
            "mode": rag["mode"],
        })
        messages.append({"kind": "text", "text": f"{_fmt(_pick(session, 'contact_leads'), session)} {item['contact']}"})

    # Opening lines: a rotating pool line (say_pool), then any fixed say lines.
    # The main menu greets you fully the first time, then just checks back in.
    if node.get("say_pool"):
        messages.append({"kind": "text", "text": _fmt(_pick(session, node["say_pool"]), session)})
    if node_id == "main_menu" and session.get("_seen_menu"):
        messages.append({"kind": "text", "text": _fmt(_pick(session, "menu_returns"), session)})
    else:
        if node_id == "main_menu":
            session["_seen_menu"] = True
        for line in _as_list(node.get("say")):
            messages.append({"kind": "text", "text": _fmt(line, session)})

    render = {
        "session_id": session["id"],
        "node": node_id,
        "done": node["expect"] == "end",
        "messages": messages,
        "expect": node["expect"],
        "prompt": _fmt(node.get("prompt", ""), session),
        "hint": node.get("hint"),
        "profile": {"name": session["name"], "index_number": session["index_number"]},
    }
    if node["expect"] == "choice":
        render["options"] = [
            {"id": str(i), "label": opt["label"]}
            for i, opt in enumerate(node["options"])
        ]
    return render


def _as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


# --- public entry points -------------------------------------------------

def start_session():
    _sweep()
    session_id = uuid.uuid4().hex
    session = {
        "id": session_id,
        "name": None,
        "index_number": None,
        "node": START_NODE,
        "created_at": time.time(),
        "last_seen": time.time(),
    }
    _SESSIONS[session_id] = session
    return session_id, _render(session)


def advance(session_id, user_text):
    session = _get(session_id)
    _sweep()
    node_id = session["node"]
    node = _resolve_node(node_id)
    user_text = (user_text or "").strip()

    # ---- end state: only "start over" (handled by /start) makes sense ----
    if node["expect"] == "end":
        return _render(session)

    # ---- text nodes: validate, store, maybe run RAG, then advance -------
    if node["expect"] == "text":
        if node.get("validate"):
            ok, cleaned, msg = _validate(node["validate"], user_text)
            if not ok:
                out = _render(session)
                out["messages"].insert(0, {"kind": "text", "text": msg})
                return out
            user_text = cleaned
        if node.get("store"):
            session[node["store"]] = user_text
            if node["store"] == "name":
                session["first_name"] = user_text.split()[0]
            if node["store"] == "index_number" and session.get("name"):
                _log_login(session)

        extra = []
        if node.get("action") == "rag":
            if not user_text:
                out = _render(session)
                out["messages"].insert(0, {"kind": "text", "text": "Go ahead — type a question and I'll look it up."})
                return out
            rag = answer_question(user_text)
            if rag["mode"] != "smalltalk":
                extra.append({"kind": "text", "text": _fmt(_pick(session, "found_leads"), session)})
            extra.append({
                "kind": "answer",
                "answer": rag["answer"],
                "sources": rag["sources"],
                "mode": rag["mode"],
            })
        session["node"] = node["next"]
        return _render(session, extra_messages=extra)

    # ---- choice nodes -------------------------------------------------
    options = node["options"]
    if user_text.isdigit() and 0 <= int(user_text) < len(options):
        chosen = options[int(user_text)]
        extra = []
        if chosen.get("rag_query"):
            topic = re.sub(r"\s*\(.*?\)\s*$", "", chosen["label"]).strip().lower()
            extra.append({"kind": "text", "text": _fmt(_pick(session, "acks"), session, topic=topic)})
            rag = answer_question(chosen["rag_query"], source=chosen.get("source"))
            extra.append({
                "kind": "answer",
                "answer": rag["answer"],
                "sources": rag["sources"],
                "mode": rag["mode"],
            })
        session["node"] = chosen["next"]
        return _render(session, extra_messages=extra)

    # free text typed at a menu -> treat it as a question (or small talk),
    # stay on this node
    if user_text:
        rag = answer_question(user_text)
        out = _render(session)
        out["messages"].insert(0, {
            "kind": "answer",
            "answer": rag["answer"],
            "sources": rag["sources"],
            "mode": rag["mode"],
        })
        if rag["mode"] != "smalltalk":
            out["messages"].insert(0, {"kind": "text", "text": _fmt(_pick(session, "found_leads"), session)})
        return out

    return _render(session)
