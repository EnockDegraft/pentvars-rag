#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
flow.py — Declarative definition of the guided assistant conversation.

This is pure data (no logic). flow_engine.py walks it, keeping one small
in-memory session per student. The shape:

NODES: dict[node_id -> node]. A node is:
    {
      "say":      str | [str]     # optional bot lines shown when the node opens
      "say_pool": str              # optional PHRASES pool to open with a rotating line
      "prompt":  str               # the question / call-to-action (supports tokens)
      "expect":  "text" | "choice" | "end"
      "store":   "name" | "index_number"      # (text nodes) where to save the reply
      "validate":"name" | "index_number"      # (text nodes) how to check the reply
      "hint":    str               # (text nodes) input placeholder
      "action":  "rag"             # (text nodes) run retrieval on the free text
      "next":    node_id           # (text nodes) node to go to after storing
      "options": [ {"label": str, "next": node_id, "rag_query": str} ]
    }

Issue nodes are generated on the fly by flow_engine from ISSUES, using
synthetic ids "issuelist:<cat>" and "issue:<cat>:<item_id>", so new issues
are added just by editing the ISSUES dict below.
"""

# --- Conversational phrasing ----------------------------------------------
# Small pools the engine rotates through (it skips the line it used last for
# a pool) so the assistant varies its wording instead of sounding like a
# form. Tokens available in any of these: {greeting} (time of day),
# {first_name}, {name}, {index_number}, {topic}.
PHRASES = {
    "greetings": [
        "{greeting}! \U0001F44B I'm the Pentecost University Institutional Knowledge Assistant.",
        "{greeting}! \U0001F44B Welcome — I'm the Pentecost University assistant.",
        "{greeting}! \U0001F44B I'm here to help you get things sorted at Pentecost University.",
    ],
    "menu_returns": [
        "What else can I help with, {first_name}?",
        "Anything else, {first_name}?",
        "Back to the menu — what would you like to look at now?",
        "Sure thing. What next, {first_name}?",
    ],
    "acks": [
        "Sure thing — here's what I have on {topic}:",
        "Of course. Here's the detail on {topic}:",
        "Happy to help. On {topic}:",
        "Good one — here's what I found on {topic}:",
    ],
    "issue_openers": [
        "Sorry you're running into that — let's sort it out. \U0001F527",
        "Ah, that's a common one. Here's how to fix it:",
        "No worries — this is usually quick to resolve.",
        "Let's get that sorted for you, {first_name}.",
    ],
    "contact_leads": [
        "Still stuck? Reach out to",
        "If that doesn't do it, contact",
        "Need a hand from a person? Contact",
    ],
    "found_leads": [
        "Here's what I found:",
        "This looks relevant:",
        "Here's the closest match I have:",
    ],
    "goodbyes": [
        "Take care, {first_name}! \U0001F44B Start a new session any time with \"Start over\".",
        "All the best with your studies, {first_name}! \U0001F44B Hit \"Start over\" whenever you need me.",
        "Bye for now, {first_name}! \U0001F44B Press \"Start over\" to begin again.",
    ],
}


# --- The scripted part of the conversation ----------------------------------

NODES = {
    "welcome": {
        "say_pool": "greetings",
        "say": "Let's get you signed in so I can keep track of your session.",
        "prompt": "First up — what's your name?",
        "expect": "text",
        "store": "name",
        "validate": "name",
        "hint": "e.g. Ama Serwaa Boateng",
        "next": "ask_index",
    },
    "ask_index": {
        "prompt": "Thanks, {first_name}! And your student index number?",
        "expect": "text",
        "store": "index_number",
        "validate": "index_number",
        "hint": "e.g. UEB3402721",
        "next": "main_menu",
    },
    "main_menu": {
        "say": "You're all set, {first_name} — signed in as {index_number}.",
        "prompt": "What would you like help with today?",
        "expect": "choice",
        "options": [
            {"label": "Scholarships & financial support", "next": "scholarship_menu"},
            {"label": "Report an issue", "next": "issue_category"},
            {"label": "Ask a free-text question", "next": "freeform"},
            {"label": "I'm done for now", "next": "goodbye"},
        ],
    },

    # --- Scholarship branch ------------------------------------------------
    "scholarship_menu": {
        "prompt": "Which one would you like to know about, {first_name}?",
        "expect": "choice",
        "options": [
            {
                "label": "Full Scholarship (100% of tuition)",
                "rag_query": "Full Scholarship covering 100% of tuition fees — "
                             "eligibility, required documents, and how to apply.",
                "source": "scholarship_full.md",
                "next": "scholarship_followup",
            },
            {
                "label": "Half Scholarship (50% of tuition)",
                "rag_query": "Half Scholarship covering 50% of tuition fees — "
                             "eligibility, required documents, and how to apply.",
                "source": "scholarship_half.md",
                "next": "scholarship_followup",
            },
            {
                "label": "Student Bursary (one-off award)",
                "rag_query": "Student Bursary one-off award — who qualifies, the "
                             "required documents, and how it is applied for.",
                "source": "scholarship_bursary.md",
                "next": "scholarship_followup",
            },
            {
                "label": "Church Member Discount (10% of tuition)",
                "rag_query": "Church Member Discount of 10% on tuition for members of "
                             "The Church of Pentecost — proof of membership and how to "
                             "claim it.",
                "source": "scholarship_church_discount.md",
                "next": "scholarship_followup",
            },
            {
                "label": "Application process, deadlines & documents",
                "rag_query": "Scholarship application process, timeline and deadlines, "
                             "and the documents required.",
                "source": "scholarship_application_process.md",
                "next": "scholarship_followup",
            },
            {
                "label": "Renewing a scholarship",
                "rag_query": "Renewing a scholarship — the GPA conditions and how to "
                             "reapply each year.",
                "source": "scholarship_application_process.md",
                "next": "scholarship_followup",
            },
            {"label": "Back to main menu", "next": "main_menu"},
        ],
    },
    "scholarship_followup": {
        "prompt": "Anything else on scholarships, {first_name}?",
        "expect": "choice",
        "options": [
            {"label": "Yes, another scholarship option", "next": "scholarship_menu"},
            {"label": "Back to main menu", "next": "main_menu"},
            {"label": "I'm done", "next": "goodbye"},
        ],
    },

    # --- Issue branch: category picker (issue lists are generated) --------
    "issue_category": {
        "prompt": "What's giving you trouble, {first_name}?",
        "expect": "choice",
        "options": [
            {"label": "Portal, IT, email & wifi", "next": "issuelist:it"},
            {"label": "Fees & payments", "next": "issuelist:fees"},
            {"label": "Results & transcripts", "next": "issuelist:results"},
            {"label": "Registration & ID card", "next": "issuelist:registration"},
            {"label": "Accommodation & library", "next": "issuelist:campus"},
            {"label": "Back to main menu", "next": "main_menu"},
        ],
    },

    # --- Free-text branch ------------------------------------------------
    "freeform": {
        "say": "Ask me anything about Pentecost University — admissions, programmes, "
               "fees, scholarships, student life or contacts.",
        "prompt": "Go ahead, {first_name} — what's your question?",
        "expect": "text",
        "hint": "e.g. What programmes does the Faculty of IT offer?",
        "action": "rag",
        "next": "freeform_followup",
    },
    "freeform_followup": {
        "prompt": "Ask another question, or head back?",
        "expect": "choice",
        "options": [
            {"label": "Ask another question", "next": "freeform"},
            {"label": "Back to main menu", "next": "main_menu"},
            {"label": "I'm done", "next": "goodbye"},
        ],
    },

    "goodbye": {
        "say_pool": "goodbyes",
        "prompt": "Session ended.",
        "expect": "end",
    },
}

START_NODE = "welcome"


# --- The issue catalogue --------------------------------------------------
# Each item: label, steps (shown verbatim), rag_query (grounded elaboration
# pulled from the knowledge base), contact (who to escalate to).

ISSUES = {
    "it": {
        "title": "Portal, IT, email & wifi",
        "doc": "portal_and_it_support.md",
        "items": {
            "portal_login": {
                "label": "I can't log into the student e-portal",
                "steps": [
                    "Go to https://eportal.pentvars.edu.gh and check the address is exact.",
                    "Your username is your index number — no spaces, correct prefix.",
                    "Your first password is the one issued with your admission letter.",
                    "Use \"Forgot Password\" to send a reset link to your student email "
                    "(check the spam folder).",
                    "After 5 failed tries the account locks for 30 minutes — wait, then retry.",
                ],
                "rag_query": "How do I fix student e-portal login problems at Pentecost "
                             "University?",
                "contact": "ICT Directorate — ict@pentvars.edu.gh, +233 30 241 7057 / 7058. "
                           "Bring your student ID if you go in person.",
            },
            "password_reset": {
                "label": "I need to reset my e-portal or email password",
                "steps": [
                    "Use the \"Forgot Password\" link on the e-portal login page.",
                    "The reset link goes to your official student email address.",
                    "If that email is an old address you can't reach, email "
                    "ict@pentvars.edu.gh from any address and ask them to update your "
                    "recovery email — they will verify your identity first.",
                ],
                "rag_query": "How do I reset my student e-portal or email password at "
                             "Pentecost University?",
                "contact": "ICT Directorate — ict@pentvars.edu.gh, +233 30 241 7057 / 7058.",
            },
            "email_access": {
                "label": "I can't access my student email",
                "steps": [
                    "Use the credentials ICT issued during orientation for the first sign-in.",
                    "The student email uses the same account as the e-portal and LMS.",
                    "Scholarship and results notices only go here — check it and its spam folder.",
                ],
                "rag_query": "How do students access their official student email at "
                             "Pentecost University?",
                "contact": "ICT Directorate — ict@pentvars.edu.gh.",
            },
            "wifi": {
                "label": "Campus wifi won't connect",
                "steps": [
                    "Connect to the campus network and sign in with your e-portal username "
                    "and password.",
                    "If it rejects you, confirm your e-portal login itself works — wifi uses "
                    "the same account.",
                    "For a weak signal, note the building and room so ICT can log it.",
                ],
                "rag_query": "How do students connect to campus wifi at Pentecost University?",
                "contact": "ICT Directorate — ict@pentvars.edu.gh, +233 30 241 7057 / 7058.",
            },
            "lms_course_missing": {
                "label": "A course I registered for isn't showing in the LMS",
                "steps": [
                    "Wait 24–48 hours after registering — courses take time to sync to the LMS.",
                    "On the e-portal, open your registration slip and confirm the course is on it.",
                    "If the slip shows it but the LMS still doesn't after 48 hours, send ICT a "
                    "screenshot.",
                ],
                "rag_query": "Why is a registered course not showing in the LMS at Pentecost "
                             "University and how is it fixed?",
                "contact": "ICT Directorate — ict@pentvars.edu.gh. If the course is missing "
                           "from registration itself, contact your department.",
            },
            "payment_portal": {
                "label": "The payment portal won't load",
                "steps": [
                    "The payment portal is https://interpayafrica.com/puc/student.",
                    "Try a different browser or network before assuming it's your account.",
                    "A payment that left your bank but doesn't show on the e-portal is a "
                    "Finance Office matter, not ICT.",
                ],
                "rag_query": "What should a student do when the Pentecost University payment "
                             "portal will not load?",
                "contact": "ICT for the portal itself (ict@pentvars.edu.gh); Finance Office "
                           "for a missing payment (finance@pentvars.edu.gh).",
            },
        },
    },

    "fees": {
        "title": "Fees & payments",
        "doc": "fees_payment_issues.md",
        "items": {
            "payment_not_reflecting": {
                "label": "I paid but my payment isn't showing on the portal",
                "steps": [
                    "Wait a few hours — the portal reconciles on a delay, and bank payments "
                    "post the next working day.",
                    "If it still doesn't show the next working day, take proof of payment "
                    "(bank slip or transaction reference, amount, date, account paid into) to "
                    "the Cash Office.",
                    "They post it to your account manually and reissue your registration invoice.",
                    "Keep every receipt until the balance on the e-portal is correct.",
                ],
                "rag_query": "What should a student do when a fee payment is not reflecting on "
                             "the Pentecost University e-portal?",
                "contact": "Finance Office / Cash Office — finance@pentvars.edu.gh, "
                           "+233 30 241 7057 / 7058. Go in person for a payment trace.",
            },
            "cannot_register_balance": {
                "label": "I can't register because of an outstanding balance",
                "steps": [
                    "Online registration needs at least 70% of tuition plus all other "
                    "required fees.",
                    "If you've paid enough but are still blocked, it's usually an unreconciled "
                    "payment — take proof to the Cash Office.",
                    "If you genuinely can't raise 70% by the deadline, ask the Finance Office "
                    "about a payment arrangement *before* the deadline.",
                ],
                "rag_query": "Why can't a student register when they have an outstanding fee "
                             "balance at Pentecost University, and what are the options?",
                "contact": "Finance Office — finance@pentvars.edu.gh.",
            },
            "installment": {
                "label": "I need a payment or instalment arrangement",
                "steps": [
                    "The standard schedule is already split: 70% before registration, the "
                    "balance before revision week.",
                    "For anything beyond that, request a written instalment arrangement from "
                    "the Finance Office and bring evidence of your situation.",
                    "An approved arrangement lets you register; missing an agreed instalment "
                    "can void it and stop you sitting exams.",
                ],
                "rag_query": "How does a student request a fee payment or instalment "
                             "arrangement at Pentecost University?",
                "contact": "Finance Office — finance@pentvars.edu.gh, +233 30 241 7057 / 7058.",
            },
            "receipt": {
                "label": "I need an official receipt or fee statement",
                "steps": [
                    "An official receipt is on the e-portal after each posted payment.",
                    "For a stamped hard-copy receipt or a full statement of your fee account, "
                    "ask at the Cash Office.",
                ],
                "rag_query": "How does a student get an official fee receipt or statement at "
                             "Pentecost University?",
                "contact": "Cash Office — finance@pentvars.edu.gh.",
            },
            "refund": {
                "label": "I need a refund or I overpaid my fees",
                "steps": [
                    "Overpayments are normally held as a credit against next semester's fees.",
                    "A cash refund (e.g. after withdrawing) is requested in writing to the "
                    "Finance Office and is subject to any non-refundable charges in your "
                    "admission terms.",
                    "Refunds go to a bank account, not cash, and take a few weeks.",
                ],
                "rag_query": "How do fee refunds and overpayments work at Pentecost University?",
                "contact": "Finance Office — finance@pentvars.edu.gh.",
            },
            "late_fee": {
                "label": "I've been charged a late registration fee unfairly",
                "steps": [
                    "Late registration attracts a late fee by default.",
                    "If the delay was a university-side error (e.g. an unreconciled payment you "
                    "had already reported), write to the Finance Office asking for the charge "
                    "to be waived and attach your evidence.",
                ],
                "rag_query": "Can a late registration fee be waived at Pentecost University and "
                             "how?",
                "contact": "Finance Office — finance@pentvars.edu.gh.",
            },
        },
    },

    "results": {
        "title": "Results & transcripts",
        "doc": "results_and_transcripts.md",
        "items": {
            "results_not_showing": {
                "label": "My semester results aren't showing or are withheld",
                "steps": [
                    "Results appear on the e-portal under \"Results\" / \"Academic Record\" "
                    "after the Academic Board approves them.",
                    "Common holds: outstanding fees, an incomplete assessment (\"IC\"), an "
                    "exam irregularity under review, or a registration mismatch.",
                    "Clear any fee balance, then contact Student Records to release the record; "
                    "for an \"IC\", contact the course lecturer and department.",
                ],
                "rag_query": "Why are a student's results withheld or not showing at Pentecost "
                             "University and how is it resolved?",
                "contact": "Student Records / Examinations Office — records@pentvars.edu.gh, "
                           "+233 30 241 7057 / 7058.",
            },
            "transcript": {
                "label": "I need an official transcript",
                "steps": [
                    "An unofficial statement of results downloads from the e-portal.",
                    "For an official (sealed, stamped) transcript, apply via the e-portal "
                    "\"Transcript Request\" section or at Student Records, and pay the fee per "
                    "copy.",
                    "State the delivery method (collect, post, or direct to an institution).",
                    "Processing is about 5–10 working days; longer for postal delivery abroad.",
                    "Transcripts aren't released with an outstanding fee balance or an "
                    "unreturned library book.",
                ],
                "rag_query": "How does a student request an official transcript at Pentecost "
                             "University?",
                "contact": "Student Records — records@pentvars.edu.gh.",
            },
            "remark": {
                "label": "I want a grade reviewed or remarked",
                "steps": [
                    "First ask the course lecturer for a review — often it's an unrecorded "
                    "coursework mark or an addition error.",
                    "If unresolved, submit a formal remarking request to the Head of "
                    "Department within the deadline given when results were released, and pay "
                    "the remarking fee.",
                    "Another examiner remarks the script; the revised mark stands whether "
                    "higher, the same, or lower.",
                    "A further appeal on process grounds goes to the Faculty Board, then the "
                    "Academic Board (final).",
                ],
                "rag_query": "What is the grade appeal and remarking process at Pentecost "
                             "University?",
                "contact": "Head of Department, then Student Records — records@pentvars.edu.gh.",
            },
            "certificate": {
                "label": "I need to collect or replace my certificate",
                "steps": [
                    "Graduands collect certificates from the Registry after congregation, "
                    "with a valid ID and a clearance slip (no fee or library debts).",
                    "A replacement for a lost certificate needs a sworn affidavit, a police "
                    "report, a newspaper publication of the loss, and a replacement fee.",
                ],
                "rag_query": "How does a student collect or replace a certificate at Pentecost "
                             "University?",
                "contact": "Registry — registry@pentvars.edu.gh.",
            },
        },
    },

    "registration": {
        "title": "Registration & ID card",
        "doc": "registration_and_id.md",
        "items": {
            "registration_blocked": {
                "label": "Course registration is closed or blocked for me",
                "steps": [
                    "Check your fee balance first — a balance or an unreconciled payment "
                    "blocks registration.",
                    "If fees are clear, ask the Finance Office to confirm reconciliation, then "
                    "Student Records to reopen your registration window.",
                    "If the window has simply ended, ask about late registration (a short "
                    "period, with a late fee).",
                ],
                "rag_query": "Why is course registration blocked or closed for a student at "
                             "Pentecost University and how is it reopened?",
                "contact": "Finance Office (balances) then Student Records "
                           "(records@pentvars.edu.gh).",
            },
            "wrong_course": {
                "label": "I registered for the wrong course / need add-drop",
                "steps": [
                    "Use add-and-drop on the e-portal (\"Course Registration\" → \"Add/Drop\") "
                    "during the published add-drop period — usually the first two weeks.",
                    "After that period, changes need written departmental approval and may not "
                    "be possible.",
                    "Dropping a course after the deadline can be recorded as a fail — get "
                    "approval first.",
                ],
                "rag_query": "How does add and drop work for course registration at Pentecost "
                             "University?",
                "contact": "Your department, then Student Records — records@pentvars.edu.gh.",
            },
            "course_missing": {
                "label": "A required course isn't in my registration list",
                "steps": [
                    "This is usually a curriculum-mapping issue for your programme and level.",
                    "Report it to your department with your programme name and level.",
                    "If your level or programme is showing wrong, take your admission letter "
                    "or last results to Student Records.",
                ],
                "rag_query": "What should a student do if a required course is missing from "
                             "their registration list at Pentecost University?",
                "contact": "Department, then Student Records — records@pentvars.edu.gh.",
            },
            "id_card": {
                "label": "I've lost my student ID card / need a replacement",
                "steps": [
                    "Report the loss; get a police report if it was stolen.",
                    "Apply for a replacement at the Student Records / ID Office and pay the "
                    "replacement fee.",
                    "A new card is normally ready within a few working days.",
                    "A reissue for a university error (wrong details, damaged card) is free — "
                    "return the old card.",
                ],
                "rag_query": "How does a student replace a lost or damaged student ID card at "
                             "Pentecost University?",
                "contact": "Student Records / ID Office — records@pentvars.edu.gh.",
            },
            "deferment": {
                "label": "I need to defer or withdraw from the semester",
                "steps": [
                    "Apply in writing to the Registrar before the semester deadline, stating "
                    "the reason (medical, financial, personal) with evidence.",
                    "An approved deferment protects your place.",
                    "Leaving without approval is recorded as a withdrawal and can affect any "
                    "refund.",
                ],
                "rag_query": "How does a student defer or withdraw from a semester at Pentecost "
                             "University?",
                "contact": "Registrar's Office — registry@pentvars.edu.gh.",
            },
        },
    },

    "campus": {
        "title": "Accommodation & library",
        "doc": "campus_life_services.md",
        "items": {
            "accommodation_apply": {
                "label": "How do I apply for accommodation or a hostel?",
                "steps": [
                    "Open the \"Accommodation\" section of the e-portal when it opens for the "
                    "semester, choose a hall or room type, and pay the accommodation fee to "
                    "confirm the place.",
                    "Accommodation fees are separate from tuition and aren't covered by the "
                    "Full or Half Scholarship.",
                    "Rooms are allocated in order of application and payment; first-years and "
                    "students with a medical need get priority.",
                ],
                "rag_query": "How does a student apply for accommodation at Pentecost "
                             "University?",
                "contact": "Hall / Accommodation Office — students@pentvars.edu.gh.",
            },
            "no_room": {
                "label": "There's no room available for me",
                "steps": [
                    "Ask the Hall/Accommodation Office for the list of approved off-campus "
                    "hostels.",
                    "Only use approved hostels — the university won't intervene in disputes "
                    "with unapproved landlords.",
                ],
                "rag_query": "What are a student's options when no on-campus room is available "
                             "at Pentecost University?",
                "contact": "Hall / Accommodation Office — students@pentvars.edu.gh.",
            },
            "hall_issue": {
                "label": "There's a maintenance or roommate problem in my hall",
                "steps": [
                    "Report plumbing, electricity, safety or roommate-conflict issues to the "
                    "Hall Warden or Senior Resident first.",
                    "Anything unresolved goes to the Dean of Students.",
                ],
                "rag_query": "How does a student report a maintenance or welfare problem in "
                             "hall at Pentecost University?",
                "contact": "Hall Warden, then Dean of Students — students@pentvars.edu.gh.",
            },
            "library_fine": {
                "label": "I have a library fine or overdue book blocking my results",
                "steps": [
                    "Return the book(s) and pay any outstanding fine at the library.",
                    "Results and transcripts are withheld while books are out or fines unpaid.",
                    "For a lost book, pay the replacement cost plus the processing charge.",
                ],
                "rag_query": "How do library fines and overdue books affect a student's "
                             "results at Pentecost University, and how are they cleared?",
                "contact": "Library — library@pentvars.edu.gh.",
            },
            "calendar": {
                "label": "What are the key dates this semester?",
                "steps": [
                    "The year runs in two semesters, each with a teaching period, revision "
                    "week, and exams, then a break.",
                    "Key dates each semester: registration opens, registration deadline, "
                    "add/drop deadline, revision week, exams start, semester ends.",
                    "Exact dates are published each year on the e-portal and noticeboards — "
                    "check the current calendar, not last year's.",
                ],
                "rag_query": "What does the Pentecost University academic calendar contain and "
                             "where are the exact dates published?",
                "contact": "Student Records — records@pentvars.edu.gh.",
            },
        },
    },
}
