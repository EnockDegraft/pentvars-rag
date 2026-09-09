#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
smalltalk.py — Handles social pleasantries (greetings, "how are you?",
"thanks", "who are you?", "bye") so they get a friendly reply instead of
"I couldn't find anything in the knowledge base."

rag_pipeline.answer_question() calls respond() before it does any
retrieval. respond(text) returns a reply string, or None if the text is a
real question that should go to the RAG pipeline.

Matching is deliberately conservative: the whole message must be short and
match an anchored pattern, so "hi, what programmes do you offer?" and
"how are entry requirements decided?" fall through to retrieval untouched.
Edit the RESPONSES lists below to change the wording.
"""
import re
import random

RESPONSES = {
    "greeting": [
        "Hello! \U0001F44B I'm the Pentecost University assistant. Ask me anything "
        "about admissions, programmes, fees, scholarships, the library or "
        "student life.",
        "Hi there! \U0001F44B I can help with Pentecost University questions — try "
        "admissions, tuition and scholarships, programmes, or how to reach an "
        "office.",
        "Hey! \U0001F44B What would you like to know about Pentecost University?",
    ],
    "how_are_you": [
        "I'm doing well, thanks for asking! What would you like to know about "
        "Pentecost University?",
        "All good on my end. \U0001F60A Ask me anything about Pentecost University.",
        "I'm great, thank you. How can I help with Pentecost University today?",
    ],
    "thanks": [
        "You're welcome! Anything else about Pentecost University I can help "
        "with?",
        "Happy to help. \U0001F60A Ask me another question any time.",
        "Anytime! Let me know if there's anything else you need.",
    ],
    "who_are_you": [
        "I'm the Pentecost University Institutional Knowledge Assistant — an AI "
        "chatbot that answers questions about the university from its official "
        "information. Try asking about entry requirements, tuition and "
        "scholarships, programmes, the library, or how to contact an office.",
    ],
    "capabilities": [
        "I can answer questions about Pentecost University — admissions and "
        "entry requirements, undergraduate and postgraduate programmes, "
        "tuition and scholarships, the academic calendar, the library, student "
        "support, accommodation, international students, and contact details. "
        "What would you like to know?",
    ],
    "bot_check": [
        "I'm an AI assistant for Pentecost University — not a human — but I can "
        "answer factual questions about the university.",
    ],
    "goodbye": [
        "Goodbye! \U0001F44B Come back any time you have a question about "
        "Pentecost University.",
        "See you! \U0001F44B I'm here whenever you need information about the "
        "university.",
        "Take care! \U0001F44B",
    ],
    "ack": [
        "\U0001F44D What would you like to know about Pentecost University?",
        "Sure — ask me anything about Pentecost University whenever you're "
        "ready.",
    ],
}

# (category, pattern) pairs, tried in order. The message is lower-cased and
# whitespace-collapsed first. Anchored ^...$ so only a whole short message
# matches. Order puts the more specific intents before plain "greeting"/"ack".
_PATTERNS = [
    ("how_are_you", re.compile(
        r"^(hi+|hello+|hey+|yo+|good\s*(morning|afternoon|evening|day))?[\s,!.]*"
        r"(how\s*(are|r|is|'?s)\s*(you|u|ya|things|it\s*going|everything)"
        r"(\s*(doing|today|now|going|these\s*days))?|"
        r"how\s*(do\s*you\s*do|are\s*ya|far|is\s*it\s*going)|"
        r"hope\s*you\s*(are|'?re)\s*(well|good|doing\s*well)|"
        r"you\s*(doing\s*)?(ok(ay)?|good|well|fine|alright)\??|"
        r"what'?s\s*up|wa?ssup|sup)[\s,!.?]*$")),
    ("thanks", re.compile(
        r"^(ok(ay)?[\s,!.]*)?"
        r"(thank(s|\s*you|\s*u)?(\s*(so\s*much|a\s*lot|very\s*much))?|thx|ty|"
        r"much\s*appreciated|i\s*(really\s*)?appreciate\s*(it|that|this)|"
        r"medaase|me\s*da\s*ase|"
        r"that('?s|\s*is|\s*was)\s*(great|helpful|perfect|useful|nice)|"
        r"(this\s*)?(helps|helped|was\s*helpful)(\s*a\s*lot)?)[\s,!.]*$")),
    ("bot_check", re.compile(
        r"^(are\s*you|r\s*u|is\s*this)\s*(a\s*)?"
        r"(real|human|robot|bot|an?\s*ai|a\s*person|alive|chat\s*gpt|gpt|machine)"
        r"[\s,!.?]*$")),
    ("who_are_you", re.compile(
        r"^(who|what)\s*(are|'?re|r)\s*(you|u|this)[\s,!.?]*$"
        r"|^who\s*(are\s*you|is\s*this)[\s,!.?]*$"
        r"|^what('?s|\s*is)\s*(this|your\s*name)[\s,!.?]*$"
        r"|^(your\s*name)[\s,!.?]*$"
        r"|^introduce\s*yourself[\s,!.?]*$")),
    ("capabilities", re.compile(
        r"^(what\s*can\s*(you|u)\s*do( for me)?|what\s*do\s*(you|u)\s*do|"
        r"how\s*(can|do)\s*(you|u)\s*help( me)?|"
        r"how\s*does\s*this\s*(work|thing\s*work)|"
        r"what\s*(is|'?s)\s*this\s*(for|about)?|what\s*are\s*you\s*for|"
        r"help)[\s,!.?]*$")),
    ("goodbye", re.compile(
        r"^(ok(ay)?[\s,!.]*)?"
        r"(bye+|goodbye|good\s*bye|see\s*(you|ya|u)(\s*(later|soon))?|cya|"
        r"later|gtg|got\s*to\s*go|that('?s|\s*is)\s*all|i'?m\s*done|"
        r"no\s*(thanks|thank\s*you)|nothing\s*(else|more)|we'?re\s*good|"
        r"that\s*(will|'?ll)\s*be\s*all)[\s,!.]*$")),
    ("greeting", re.compile(
        r"^(hi+|he+y+|hello+|hiya|holla|hola|yo+|howdy|greetings|"
        r"good\s*(morning|afternoon|evening|day)|gm|"
        r"hey\s*there|hi\s*there|hello\s*there|good\s*day|"
        r"morning|afternoon|evening)"
        r"[\s,!.]*(assistant|bot|there|pentvars|pu|team)?[\s,!.]*$")),
    ("ack", re.compile(
        r"^(ok(ay)?|k|kk|alright|all\s*right|cool|nice|great|good|fine|"
        r"got\s*it|understood|sure|noted|yeah|yep|yes|nope|no)[\s,!.]*$")),
]


def respond(text):
    """Return a friendly reply for social small talk, or None to let the
    question go through to retrieval."""
    t = re.sub(r"\s+", " ", (text or "").strip().lower())
    if not t or len(t) > 60 or len(t.split()) > 8:
        return None
    for category, pattern in _PATTERNS:
        if pattern.search(t):
            return random.choice(RESPONSES[category])
    return None
