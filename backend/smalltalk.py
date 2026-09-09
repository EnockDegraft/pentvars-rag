#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
smalltalk.py — Handles social pleasantries (greetings, "how are you?",
"thanks", compliments, apologies, "who are you?", "bye", and a few
off-topic asks) so they get a friendly reply instead of
"I couldn't find anything in the knowledge base."

rag_pipeline.answer_question() calls respond() before it does any
retrieval. respond(text) returns a reply string, or None if the text is a
real question that should go to the RAG pipeline.

Matching is deliberately conservative: the whole message must be short and
match an anchored pattern, so "hi, what programmes do you offer?" and
"how are entry requirements decided?" fall through to retrieval untouched.
Edit the RESPONSES lists below to change the wording; add a (category,
pattern) pair to _PATTERNS to add a new intent.
"""
import re
import random

_ASK = "What would you like to know about Pentecost University?"

RESPONSES = {
    "greeting": [
        "Hello! \U0001F44B I'm the Pentecost University assistant. Ask me about "
        "admissions, programmes, fees, scholarships, the library or student "
        "life.",
        "Hi there! \U0001F44B I can help with Pentecost University questions — try "
        "admissions, tuition and scholarships, programmes, or how to reach an "
        "office.",
        "Hey! \U0001F44B " + _ASK,
        "Hello! \U0001F44B Good to have you here. " + _ASK,
        "Hi! \U0001F44B I'm here to help you find your way around Pentecost "
        "University. What do you need?",
    ],
    "how_are_you": [
        "I'm doing well, thanks for asking! " + _ASK,
        "All good on my end. \U0001F60A Ask me anything about Pentecost "
        "University.",
        "I'm great, thank you. How can I help with Pentecost University today?",
        "Doing well and ready to help! What can I look up for you?",
    ],
    "thanks": [
        "You're welcome! Anything else about Pentecost University I can help "
        "with?",
        "Happy to help. \U0001F60A Ask me another question any time.",
        "Anytime! Let me know if there's anything else you need.",
        "My pleasure! \U0001F44D",
        "Glad that helped. Ask away if more comes up.",
    ],
    "compliment": [
        "Thank you, that's kind of you to say! \U0001F60A " + _ASK,
        "Appreciate it! I'll keep doing my best. " + _ASK,
        "Thanks! \U0001F64C Ask me anything else about Pentecost University.",
    ],
    "love": [
        "That's very sweet \U0001F60A — I'm just here to help with Pentecost "
        "University questions, though. What would you like to know?",
        "Aww, thanks! \U0001F49B Now, how can I help you with the university?",
    ],
    "apology": [
        "No need to apologise! " + _ASK,
        "That's completely fine. \U0001F642 What would you like to know?",
        "No worries at all. Ask me anything about Pentecost University.",
    ],
    "confused": [
        "No problem — I can answer questions about Pentecost University's "
        "admissions, programmes, fees and scholarships, the academic calendar, "
        "the library, student support, accommodation and contacts. What would "
        "you like to start with?",
        "Let's take it a step at a time. Try asking something specific, like "
        "\"what are the entry requirements?\" or \"how much is tuition?\"",
    ],
    "insult": [
        "Sorry I couldn't help there. Try asking about a specific topic — "
        "admissions, fees, programmes, the library or a contact — and I'll do "
        "better.",
        "Fair enough. Give me a specific question about Pentecost University "
        "and I'll try again.",
    ],
    "off_scope": [
        "I only know about Pentecost University, I'm afraid — not that. But "
        "ask me anything about the university and I'll help.",
        "That's outside what I cover. I can help with Pentecost University "
        "admissions, programmes, fees, scholarships, student life and "
        "contacts.",
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
        + _ASK,
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
        "Bye for now! \U0001F44B Press \"Start over\" whenever you want to begin "
        "again.",
    ],
    "ack": [
        "\U0001F44D " + _ASK,
        "Sure — ask me anything about Pentecost University whenever you're "
        "ready.",
        "Got it. What would you like to look at next?",
    ],
}

# (category, pattern) pairs, tried in order. The message is lower-cased and
# whitespace-collapsed first. Anchored ^...$ so only a whole short message
# matches. Order puts the more specific intents before plain
# "greeting"/"ack".
_PATTERNS = [
    ("how_are_you", re.compile(
        r"^(hi+|hello+|hey+|yo+|good\s*(morning|afternoon|evening|day))?[\s,!.]*"
        r"(how\s*(are|r|is|'?s)\s*(you|u|ya|things|it\s*going|everything)"
        r"(\s*(doing|today|now|going|these\s*days))?|"
        r"how\s*(do\s*you\s*do|are\s*ya|far|is\s*it\s*going|('?s|is)\s*your\s*day)|"
        r"hope\s*you\s*(are|'?re)\s*(well|good|doing\s*well)|"
        r"you\s*(doing\s*)?(ok(ay)?|good|well|fine|alright)\??|"
        r"what'?s\s*up|wa?ssup|sup|nice\s*to\s*meet\s*you)[\s,!.?]*$")),
    ("love", re.compile(
        r"^(i\s*)?(love\s*(you|u|this|it|this\s*(app|bot|assistant))|"
        r"you'?re\s*(the\s*best|amazing|awesome|the\s*goat)|marry\s*me|"
        r"love\s*ya)[\s,!.]*$")),
    ("thanks", re.compile(
        r"^(ok(ay)?[\s,!.]*)?"
        r"(thank(s|\s*you|\s*u)?(\s*(so\s*much|a\s*lot|very\s*much))?|thx|ty|"
        r"much\s*appreciated|i\s*(really\s*)?appreciate\s*(it|that|this)|"
        r"medaase|me\s*da\s*ase|cheers|"
        r"that('?s|\s*is|\s*was)\s*(great|helpful|perfect|useful|nice|brilliant)|"
        r"(this\s*)?(helps|helped|was\s*helpful)(\s*a\s*lot)?)[\s,!.]*$")),
    ("compliment", re.compile(
        r"^(you'?re|you\s*are|ur|u\s*r)\s*"
        r"(so\s*|really\s*|very\s*|pretty\s*)?"
        r"(great|good|helpful|smart|clever|brilliant|amazing|awesome|nice|"
        r"wonderful|useful|the\s*best|impressive|intelligent)"
        r"([\s,]*(bot|assistant))?[\s,!.]*$"
        r"|^(good|nice|great|smart|clever)\s*(bot|assistant|job|work)[\s,!.]*$"
        r"|^well\s*done[\s,!.]*$")),
    ("apology", re.compile(
        r"^(i'?m\s*)?(so\s*|really\s*|very\s*)?(sorry|apolog(y|ies|ise|ize)|"
        r"my\s*bad|my\s*mistake|oops|whoops|pardon(\s*me)?|excuse\s*me)"
        r"[\s,!.]*$")),
    ("confused", re.compile(
        r"^(i\s*(a?m|'?m)\s*)?(confused|lost|stuck|not\s*sure)[\s,!.]*$"
        r"|^i\s*(do\s*n'?t|don'?t|dont)\s*(understand|get\s*(it|this)|know)"
        r"[\s,!.]*$"
        r"|^(huh|what\s*do\s*you\s*mean|come\s*again|say\s*that\s*again|"
        r"i'?m\s*not\s*following)[\s,!.?]*$")),
    ("insult", re.compile(
        r"^(you'?re|you\s*are|ur|this\s*(app|bot|is)?|that'?s?)\s*"
        r"(so\s*|really\s*|absolutely\s*)?"
        r"(useless|dumb|stupid|rubbish|trash|garbage|terrible|awful|"
        r"the\s*worst|pointless|a\s*waste|not\s*helpful|unhelpful|bad)"
        r"[\s,!.]*$"
        r"|^(you\s*(suck|stink)|worst\s*bot|this\s*sucks|not\s*helpful)"
        r"[\s,!.]*$")),
    ("off_scope", re.compile(
        r"^(what('?s|\s*is)\s*the\s*(weather|time|date|news)"
        r"(\s*(today|now|like))?|"
        r"is\s*it\s*(raining|hot|cold|sunny)|how'?s\s*the\s*weather|"
        r"tell\s*me\s*a\s*joke|say\s*something\s*funny|make\s*me\s*laugh|"
        r"what\s*time\s*is\s*it|who\s*(are\s*you\s*voting|won\s*the\s*match)|"
        r"what\s*(is|'?s)\s*\d+\s*[-+x*/]\s*\d+|sing\s*(me\s*)?a\s*song)"
        r"[\s,!.?]*$")),
    ("bot_check", re.compile(
        r"^(are\s*you|r\s*u|is\s*this)\s*(a\s*)?"
        r"(real|human|robot|bot|an?\s*ai|a\s*person|alive|chat\s*gpt|gpt|"
        r"a\s*machine|a\s*computer|automated)[\s,!.?]*$")),
    ("who_are_you", re.compile(
        r"^(who|what)\s*(are|'?re|r)\s*(you|u|this)[\s,!.?]*$"
        r"|^who\s*(are\s*you|is\s*this)[\s,!.?]*$"
        r"|^what('?s|\s*is)\s*(this|your\s*name)[\s,!.?]*$"
        r"|^(your\s*name)[\s,!.?]*$"
        r"|^introduce\s*yourself[\s,!.?]*$"
        r"|^tell\s*me\s*about\s*yourself[\s,!.?]*$")),
    ("capabilities", re.compile(
        r"^(what\s*can\s*(you|u)\s*do( for me)?|what\s*do\s*(you|u)\s*do|"
        r"how\s*(can|do)\s*(you|u)\s*help( me)?|"
        r"how\s*does\s*this\s*(work|thing\s*work)|"
        r"what\s*(is|'?s)\s*this\s*(for|about)?|what\s*are\s*you\s*for|"
        r"what\s*(questions|can\s*i\s*ask)|can\s*you\s*help( me)?|help)"
        r"[\s,!.?]*$")),
    ("goodbye", re.compile(
        r"^(ok(ay)?[\s,!.]*)?"
        r"(bye+|goodbye|good\s*bye|see\s*(you|ya|u)(\s*(later|soon))?|cya|"
        r"later|gtg|got\s*to\s*go|that('?s|\s*is)\s*all|i'?m\s*done|"
        r"no\s*(thanks|thank\s*you)|nothing\s*(else|more)|we'?re\s*good|"
        r"that\s*(will|'?ll)\s*be\s*all|good\s*night|goodnight)[\s,!.]*$")),
    ("greeting", re.compile(
        r"^(hi+|he+y+|hello+|hiya|holla|hola|yo+|howdy|greetings|"
        r"good\s*(morning|afternoon|evening|day)|gm|"
        r"hey\s*there|hi\s*there|hello\s*there|good\s*day|"
        r"morning|afternoon|evening|hello\??|anyone\s*(there|home)|"
        r"you\s*there|are\s*you\s*there|can\s*you\s*hear\s*me)"
        r"[\s,!.]*(assistant|bot|there|pentvars|pu|team)?[\s,!.?]*$")),
    ("ack", re.compile(
        r"^(ok(ay)?|k|kk|alright|all\s*right|cool|nice|great|good|fine|"
        r"got\s*it|understood|sure|noted|yeah|yep|yes|nope|no|"
        r"perfect|awesome|please|thanks\s*anyway)[\s,!.]*$")),
]


def respond(text):
    """Return a friendly reply for social small talk, or None to let the
    question go through to retrieval."""
    t = re.sub(r"\s+", " ", (text or "").strip().lower())
    if not t or len(t) > 60 or len(t.split()) > 9:
        return None
    for category, pattern in _PATTERNS:
        if pattern.search(t):
            return random.choice(RESPONSES[category])
    return None
