"""Deterministic offline LLM used for tests and demos. Content is clearly fake."""

import json
import re
import unicodedata

from app.modules.generation.normalize import normalize_benefit, normalize_goal

SECTION_PATH_RE = re.compile(r"SECTION PATH:\s*(.+)")
SECTION_NUMBER_RE = re.compile(r"SECTION NUMBER:\s*(.*)")
SECTION_TITLE_RE = re.compile(r"SECTION TITLE:\s*(.+)")
SECTION_TEXT_RE = re.compile(r"SECTION TEXT:\s*(.*)", re.DOTALL)
BACKLOG_INPUT = "BACKLOG INPUT:"


def _match(pattern: re.Pattern, text: str, default: str = "") -> str:
    match = pattern.search(text)
    return match.group(1).strip() if match else default


def _section_info(user: str) -> tuple[str, str, str]:
    path = [part.strip() for part in _match(SECTION_PATH_RE, user).split(">") if part.strip()]
    number = _match(SECTION_NUMBER_RE, user)
    title = _match(SECTION_TITLE_RE, user)
    if not title and path:
        title = re.sub(r"^\d+(?:\.\d+)*\s*", "", path[-1]).strip()
    if not number and path:
        match = re.match(r"^(\d+(?:\.\d+)*)", path[-1])
        number = match.group(1) if match else ""
    return title or "this requirement", number or "the section", _match(SECTION_TEXT_RE, user)


def _normalize(text: str) -> str:
    lowered = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", lowered.lower()).strip()


def _objective(text: str) -> str:
    for line in (text or "").splitlines():
        cleaned = line.strip()
        if cleaned.lower().startswith("objet"):
            return re.sub(r"^objet\s*:\s*", "", cleaned, flags=re.IGNORECASE).strip()
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    return lines[0] if lines else ""


def _topics(text: str) -> list[str]:
    body = re.sub(r"contenu possible\s*:", "\n", text or "", flags=re.IGNORECASE)
    out: list[str] = []
    for line in body.splitlines():
        line = line.strip()
        if not line or line.lower().startswith("objet"):
            continue
        parts = re.split(r"\s+-\s+|^-\s*", line)
        for part in parts:
            cleaned = part.strip(" -.\t")
            if cleaned and cleaned.lower() not in {item.lower() for item in out}:
                out.append(cleaned)
    return out[:8]


PROFILES = [
    (
        ("parties prenantes", "stakeholder"),
        {
            "title": "Clarify stakeholder roles and decision rights",
            "persona": "Business Analyst",
            "goal": "see who is accountable, consulted and informed for each project decision",
            "benefit": "avoid ownership gaps before delivery starts",
            "feature": "Stakeholder alignment",
            "priority": "must",
            "reason": "Clear ownership is required before requirements can be validated.",
            "rules": [
                "Each stakeholder group has one named owner and one decision right.",
                "A stakeholder change is recorded with its author and date.",
            ],
            "deps": ["The client confirms the stakeholder groups before the first review."],
            "description": (
                "The project needs one shared view of the people involved and the decisions they own. "
                "The stakeholder map separates the business client, Business Analyst, Product Owner, "
                "quality lead and functional administrator. It gives every review a clear owner and "
                "keeps approval paths visible from the first workshop."
            ),
            "ac": [
                "Given the stakeholder list in section 1.3 contains 5 groups, when the Business Analyst opens the requirement, then each group shows its role and decision right.",
                "Given a decision owned by the Product Owner, when the client asks for a scope change, then the request is routed to that owner and stays pending until approval.",
                "Given a stakeholder who leaves the project, when the Business Analyst updates the group, then the change is timestamped and existing stories keep their original source evidence.",
                "Given a new stakeholder group with no named owner, when the backlog is reviewed, then a Blocking question is raised before generation.",
            ],
        },
    ),
    (
        ("inclus", "included"),
        {
            "title": "Confirm the capabilities included in the release",
            "persona": "Product Owner",
            "goal": "confirm the capabilities that are included in the proposed release",
            "benefit": "keep the release scope explicit and defendable",
            "feature": "Release scope",
            "priority": "must",
            "reason": "The release cannot be planned without an agreed included scope.",
            "rules": [
                "Every included capability has a named source section.",
                "A capability is excluded from the release only after a recorded decision.",
            ],
            "deps": ["The client validates the release boundary before backlog approval."],
            "description": (
                "The release scope lists the capabilities the client expects in this version, from "
                "document import through export. The Product Owner uses this list to confirm what the "
                "team will deliver and what depends on later releases. It becomes the baseline for "
                "acceptance and planning."
            ),
            "ac": [
                "Given the included scope in section 1.4.1 lists 4 capabilities, when the Product Owner opens the scope view, then all 4 are shown with their source section.",
                "Given an included capability with no acceptance criterion, when the backlog is generated, then the capability is marked incomplete and cannot be approved.",
                "Given a capability excluded from the release, when the Product Owner reviews the included list, then the excluded item does not appear as committed scope.",
                "Given the client adds a capability to the release, when the scope is reviewed, then the change is recorded with its author and date.",
            ],
        },
    ),
    (
        ("exclu", "excluded", "hors perimetre"),
        {
            "title": "Make out-of-scope items explicit",
            "persona": "Product Owner",
            "goal": "see clearly which expected capabilities are outside the release",
            "benefit": "prevent commitments that the solution will not meet",
            "feature": "Release scope",
            "priority": "should",
            "reason": "Explicit exclusions protect delivery from false expectations.",
            "rules": [
                "Excluded items stay visible with the reason for exclusion.",
                "A later request to include an excluded item triggers a change review.",
            ],
            "deps": ["Business stakeholders agree on the exclusion list before planning."],
            "description": (
                "The exclusion list captures the expectations that are deliberately not part of this "
                "release. It names automatic validation, automated priority decisions and test execution "
                "on the target application as out of scope. The list protects the team from silent scope "
                "growth and gives the client a clear decision record."
            ),
        },
    ),
    (
        ("hypotheses", "dependances"),
        {
            "title": "Track assumptions and external dependencies",
            "persona": "Business Analyst",
            "goal": "track the assumptions and external dependencies that the analysis relies on",
            "benefit": "surface blockers before they affect delivery",
            "feature": "Dependency management",
            "priority": "must",
            "reason": "Unmanaged assumptions invalidate estimates and review dates.",
            "rules": [
                "Each dependency has an owner, a due date and a status.",
                "An open dependency is visible on the project before generation starts.",
            ],
            "deps": ["Stakeholders confirm availability for review sessions."],
            "description": (
                "The analysis depends on readable documents, available business users and access to "
                "the export tools. The story records these conditions as managed dependencies rather "
                "than hidden assumptions. The Business Analyst can then plan reviews and escalate "
                "blockers early."
            ),
        },
    ),
    (
        ("vue d'ensemble", "vue densemble", "overview"),
        {
            "title": "Walk the end-to-end backlog workflow",
            "persona": "Business Analyst",
            "goal": "follow the complete workflow from import to export",
            "benefit": "give the team one shared view of the delivery path",
            "feature": "End-to-end workflow",
            "priority": "must",
            "reason": "The main journey defines the minimum usable product.",
            "rules": [
                "The workflow keeps the same order from import to export.",
                "Each step exposes its status and the next human action.",
            ],
            "deps": ["Project roles are confirmed before the workflow is tested end to end."],
            "description": (
                "The overview follows the work from document import through analysis, generation, "
                "review, validation and export. It gives the team a simple mental model of the product "
                "and highlights where humans approve the output. The workflow becomes the backbone for "
                "navigation, tests and training."
            ),
        },
    ),
    (
        ("personas", "utilisateurs"),
        {
            "title": "Define personas and their main needs",
            "persona": "Business Analyst",
            "goal": "capture each persona's objective, allowed actions and current pain points",
            "benefit": "write stories that speak to real users rather than generic roles",
            "feature": "Persona definition",
            "priority": "should",
            "reason": "Consistent personas improve story quality and review speed.",
            "rules": [
                "Each persona has one main objective and a named set of allowed actions.",
                "A story names exactly one persona from the approved list.",
            ],
            "deps": ["Business stakeholders validate the persona list."],
            "description": (
                "The personas describe the profiles that use the solution and the outcomes they care "
                "about. They include the role, main objective, allowed actions and current difficulties. "
                "The backlog uses these personas consistently so that every story has a real user behind "
                "it."
            ),
        },
    ),
    (
        ("parcours", "user journey", "journeys"),
        {
            "title": "Map the key user journeys",
            "persona": "Business Analyst",
            "goal": "map the actions that users perform from project setup to export",
            "benefit": "connect requirements to real sequences of work",
            "feature": "User journeys",
            "priority": "should",
            "reason": "Journey coverage exposes gaps that a list of requirements misses.",
            "rules": [
                "Every journey starts with a user goal and ends with a visible outcome.",
                "A journey step that needs approval is marked as a human checkpoint.",
            ],
            "deps": ["Personas are agreed before journeys are finalised."],
            "description": (
                "The key journeys cover project creation, document upload, result review, correction, "
                "validation and export. They show where users need context and where the solution must "
                "hand control back to a person. The journeys link each screen to a concrete business "
                "outcome."
            ),
        },
    ),
    (
        ("exigences fonctionnelles", "functional requirements"),
        {
            "title": "Capture functional requirements with business rules",
            "persona": "Business Analyst",
            "goal": "capture each functional requirement with its user, rule and expected result",
            "benefit": "give delivery a complete and testable definition of the need",
            "feature": "Functional requirements",
            "priority": "must",
            "reason": "Functional requirements are the core input to backlog generation.",
            "rules": [
                "Each requirement names one user, one rule and one expected result.",
                "An important error case is documented with the requirement.",
            ],
            "deps": ["Business rules are confirmed by the business owner."],
            "description": (
                "The functional requirements describe what the solution must let users do, for whom, "
                "with which rule and with which expected result. They also capture important error cases. "
                "Each requirement is written so that the backlog can turn it into a story with concrete "
                "acceptance criteria."
            ),
        },
    ),
    (
        ("cas d'usage ia", "cas dusage ia", "ai use"),
        {
            "title": "Detect requirements and gaps with AI",
            "persona": "Business Analyst",
            "goal": "use AI to understand the document and identify requirements and missing information",
            "benefit": "start from a reliable draft instead of a blank page",
            "feature": "AI-assisted analysis",
            "priority": "must",
            "reason": "AI-assisted analysis is the core value of the product.",
            "rules": [
                "Every AI output keeps a reference to its source section.",
                "A detected ambiguity is raised as a question instead of guessed.",
            ],
            "deps": ["A readable source document is available before analysis starts."],
            "description": (
                "The AI use cases cover document understanding, requirement detection, backlog and test "
                "generation and the detection of missing information. The Business Analyst gets a first "
                "draft that is already linked to the source. The value comes from speed with evidence, "
                "not from hidden automation."
            ),
        },
    ),
    (
        ("organisation des traitements", "traitements ia"),
        {
            "title": "Run the AI workflow in controlled stages",
            "persona": "Business Analyst",
            "goal": "follow the AI work through analysis, generation, consistency checks and review",
            "benefit": "understand what the system is doing and where to intervene",
            "feature": "AI workflow",
            "priority": "must",
            "reason": "Controlled stages make AI output reviewable and explainable.",
            "rules": [
                "Each stage exposes a start, an end and a failure reason.",
                "Generation waits for human context approval.",
            ],
            "deps": ["Provider access and a readable document are available."],
            "description": (
                "The AI work is split into visible stages: document analysis, result creation, "
                "consistency control and presentation for validation. Each stage reports progress and "
                "can be reviewed on its own. The analyst knows when to wait and when to act."
            ),
        },
    ),
    (
        ("qualite et controle", "quality", "controle"),
        {
            "title": "Validate AI output with traceable checks",
            "persona": "Quality lead",
            "goal": "check that each AI result is traceable, editable and supported by evidence",
            "benefit": "trust the backlog without blind acceptance",
            "feature": "Quality control",
            "priority": "must",
            "reason": "Quality control is required before any result leaves the platform.",
            "rules": [
                "Every item keeps a link to its source section.",
                "Uncertainty is visible and can be rejected or corrected.",
                "Each validation decision is recorded in the history.",
            ],
            "deps": ["The source section remains available during review."],
            "description": (
                "Quality control gives the analyst the evidence needed to accept or reject AI output. "
                "Each result keeps its source reference, can be edited and exposes uncertainty. The "
                "validation history records who made each decision and when. This keeps the backlog "
                "defendable in front of the client."
            ),
        },
    ),
    (
        ("usage responsable", "responsable"),
        {
            "title": "Protect data and govern AI usage",
            "persona": "Security officer",
            "goal": "keep project data confidential and limit AI activity to authorised users",
            "benefit": "use AI without weakening client trust or compliance",
            "feature": "Responsible AI",
            "priority": "must",
            "reason": "Confidentiality and traceability are non-negotiable client expectations.",
            "rules": [
                "Only authorised users can access a project and its documents.",
                "No item is exported before validation.",
                "Every decision is traceable to a named user and time.",
            ],
            "deps": ["The client confirms applicable security policies."],
            "description": (
                "The responsible AI story defines the guarantees around confidentiality, access and "
                "decision history. It limits access to authorised people and blocks export before "
                "validation. The analyst can show exactly who approved each item and when, which keeps "
                "the engagement auditable."
            ),
        },
    ),
    (
        ("non fonctionnelles", "nonfunctional", "qualites generales"),
        {
            "title": "Meet quality, performance and reliability expectations",
            "persona": "Product Owner",
            "goal": "confirm the usability, performance, security and availability expectations",
            "benefit": "avoid a backlog that is functionally right but operationally weak",
            "feature": "Non-functional requirements",
            "priority": "should",
            "reason": "Non-functional gaps create rework late in delivery.",
            "rules": [
                "Each non-functional requirement has a measurable target.",
                "Supported input and output formats are listed explicitly.",
            ],
            "deps": ["The client provides expected volumes and availability targets."],
            "description": (
                "The non-functional requirements describe ease of use, response time, data protection, "
                "availability and compatibility with agreed formats. They turn general quality "
                "expectations into measurable delivery targets. The team can then test the solution "
                "against the same expectations the client will use."
            ),
        },
    ),
    (
        ("entrees", "inputs"),
        {
            "title": "Collect the client inputs needed for analysis",
            "persona": "Business Analyst",
            "goal": "collect the document, project information, output language and business rules",
            "benefit": "start the analysis with complete and usable inputs",
            "feature": "Input readiness",
            "priority": "must",
            "reason": "Missing inputs are the most common cause of poor generation.",
            "rules": [
                "The source document is PDF or Word and readable.",
                "The expected output language and format are recorded before generation.",
            ],
            "deps": ["The client supplies the functional document and project metadata."],
            "description": (
                "The input story makes the required client inputs explicit before analysis starts. It "
                "covers the functional document, project information, output language, output format "
                "and any business rules or templates. A clear input checklist removes avoidable "
                "back-and-forth during review."
            ),
        },
    ),
    (
        ("integrations", "integration"),
        {
            "title": "Hand off approved backlog to delivery tools",
            "persona": "Business Analyst",
            "goal": "send the approved backlog to the backlog and test management tools",
            "benefit": "keep one source of truth from analysis to delivery",
            "feature": "Integration handoff",
            "priority": "should",
            "reason": "Manual re-entry slows delivery and introduces errors.",
            "rules": [
                "Only approved items are transferred.",
                "Accepted file formats and validation rules are shown before transfer.",
            ],
            "deps": ["Tool access and credentials are available when transfer is requested."],
            "description": (
                "The integration story covers the export of approved items to backlog and test "
                "management tools. It defines accepted formats, validation conditions and the moment "
                "when transfer becomes possible. The team avoids retyping content and keeps traceability "
                "outside the application."
            ),
        },
    ),
    (
        ("donnees", "data"),
        {
            "title": "Manage project, backlog and validation data",
            "persona": "Business Analyst",
            "goal": "keep projects, requirements, backlog items, criteria, tests and decisions consistent",
            "benefit": "maintain a reliable record across the whole engagement",
            "feature": "Data management",
            "priority": "must",
            "reason": "Traceability depends on consistent, durable data.",
            "rules": [
                "A project groups its documents, sections, items, questions and decisions.",
                "A deleted project removes its derived content and stored files.",
            ],
            "deps": ["Storage and backup policies are agreed with the client."],
            "description": (
                "The data story defines the main information the solution manages: projects, "
                "documents, requirements, backlog items, acceptance criteria, tests, comments, "
                "validations and exports. It keeps these objects linked so that a change can be traced "
                "from source to decision. The analyst can rely on the project record throughout the "
                "engagement."
            ),
        },
    ),
    (
        ("principes", "principles"),
        {
            "title": "Keep the experience simple and transparent",
            "persona": "Business Analyst",
            "goal": "work in a simple interface that is honest about AI results",
            "benefit": "stay in control without fighting the tool",
            "feature": "Experience principles",
            "priority": "should",
            "reason": "Trust and adoption depend on simple, transparent behaviour.",
            "rules": [
                "AI results are labelled and never presented as human decisions.",
                "Important actions require confirmation before they run.",
            ],
            "deps": ["The product team reviews key screens with real users."],
            "description": (
                "The experience principles set the tone for the whole product: simplicity, readability, "
                "transparency about AI and confirmation before important actions. They guide layout and "
                "interaction choices as much as wording. The analyst always knows what the system did and "
                "what remains under human control."
            ),
        },
    ),
    (
        ("ecrans", "screens"),
        {
            "title": "Provide the screens needed for the workflow",
            "persona": "Business Analyst",
            "goal": "move through the project list, document review, backlog, validation and export screens",
            "benefit": "complete the work without leaving the application",
            "feature": "Workspace screens",
            "priority": "should",
            "reason": "Screen coverage is needed to run an end-to-end review.",
            "rules": [
                "Each main step has a dedicated screen or view.",
                "The current project and step are always visible.",
            ],
            "deps": ["The workflow and personas are agreed before screen design."],
            "description": (
                "The screen story lists the main views: project list, document and requirement review, "
                "backlog and test cases, validation and export. It ensures that each step of the "
                "workflow has a clear home. The analyst can complete the full review without switching "
                "to another tool."
            ),
        },
    ),
    (
        ("securite et conformite", "conformite", "compliance"),
        {
            "title": "Enforce access control and auditability",
            "persona": "Security officer",
            "goal": "apply role-based access and keep a history of sensitive actions",
            "benefit": "meet client compliance rules and protect project data",
            "feature": "Compliance",
            "priority": "must",
            "reason": "Compliance requirements can block client acceptance.",
            "rules": [
                "Access is granted according to role.",
                "Documents remain confidential and deletion is controlled.",
                "Sensitive actions are kept in the audit history.",
            ],
            "deps": ["The client provides its access and retention policies."],
            "description": (
                "The compliance story covers role-based access, document confidentiality, action history, "
                "data deletion and applicable client rules. It turns security expectations into "
                "verifiable controls. The project can then be audited without reconstructing decisions "
                "after the fact."
            ),
        },
    ),
    (
        ("strategie de tests", "test strategy", "tests"),
        {
            "title": "Define a risk-based test strategy",
            "persona": "Quality lead",
            "goal": "cover the main journey, error cases, user rights and generated output quality",
            "benefit": "focus test effort on the risks that matter",
            "feature": "Test strategy",
            "priority": "should",
            "reason": "A clear test strategy makes acceptance evidence repeatable.",
            "rules": [
                "Each story has at least one positive test and one error or permission test where relevant.",
                "Test data is explicit and reusable.",
            ],
            "deps": ["Acceptance criteria are approved before test execution starts."],
            "description": (
                "The test strategy covers the main journey, error cases, user rights, generated output "
                "quality and import or export. It sets the level of evidence expected for each story. "
                "The quality lead can plan execution and show coverage without inventing scenarios "
                "during the review."
            ),
        },
    ),
]


def _profile(title: str, text: str) -> dict:
    normalized_title = _normalize(title)
    for keywords, profile in PROFILES:
        if any(keyword in normalized_title for keyword in keywords):
            return profile
    cleaned = re.sub(r"^\d+(?:\.\d+)*\s*", "", title).strip()
    return {
        "title": f"Clarify the expected outcome for {cleaned or 'this requirement'}",
        "persona": "Business Analyst",
        "goal": f"apply the expectations described in {cleaned or 'this section'}",
        "benefit": "give the delivery team a clear and testable requirement",
        "feature": cleaned or "Requirement clarification",
        "priority": "should",
        "reason": "The requirement supports the core workflow but can follow the must-have scope.",
        "rules": ["Each rule in the source is represented by a testable acceptance criterion."],
        "deps": ["The source section is readable and confirmed by the business owner."],
        "description": (
            f"The requirement asks the solution to { _objective(text).rstrip('.').lower() or 'support the described business need' }. "
            "It keeps the original source evidence and turns the intent into a testable story. The "
            "delivery team can trace the outcome back to the specification."
        ),
    }


def _criterion_parts(criterion: str) -> tuple[str, str, str]:
    match = re.search(
        r"given\s+(.*?)(?:,\s*)?when\s+(.*?)(?:,\s*)?then\s+(.*)",
        criterion,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match:
        return (
            match.group(1).strip(" ,"),
            match.group(2).strip(" ,"),
            match.group(3).strip(" ,."),
        )
    lower = criterion.lower()
    marker = lower.find("then ")
    if marker >= 0:
        return "", "", criterion[marker + 5 :].strip(" ,.")
    return "", "", criterion.strip(" ,.")


def _tests_from_criteria(criteria: list[str], number: str) -> list[dict]:
    tests = []
    for index, criterion in enumerate(criteria, 1):
        given, when, then = _criterion_parts(criterion)
        title = then[:1].upper() + then[1:] if then else f"Verify criterion {index}"
        tests.append(
            {
                "title": title,
                "preconditions": [given] if given else [f"Source section {number} is available."],
                "steps": [when] if when else ["Run the described scenario."],
                "test_data": f"Section {number}, criterion {index}",
                "expected": then or criterion,
            }
        )
    return tests


def _story_from_section(user: str) -> dict:
    title, number, text = _section_info(user)
    profile = _profile(title, text)
    topics = _topics(text)
    objective = _objective(text).rstrip(".")
    count = max(3, len(topics))
    first = topics[0] if topics else profile["goal"]
    topic_list = ", ".join(topics[:4]) if topics else profile["goal"]
    excerpt = (objective or title)[:160]
    story_title = profile["title"]
    if _normalize(story_title) == _normalize(title):
        story_title = f"Clarify {title}"

    description = profile.get("description")
    if not description:
        description = (
            f"The section asks the solution to {objective.lower() or profile['goal']}. "
            f"It covers {topic_list}. The story keeps that intent traceable to section {number} "
            "and gives the team one testable outcome."
        )

    rules = list(profile.get("rules") or [])
    if not rules:
        rules = [
            f"The rules described in section {number} apply without exception.",
            "Any missing value is raised as a question before approval.",
        ]

    criteria = list(profile.get("ac") or []) or [
        (
            f"Given a project with {count} items listed in section {number}, when the analyst opens "
            f"the requirement, then all {count} items are visible with an owner and a status."
        ),
        (
            f"Given the source statement \"{excerpt}\", when the story is generated, then every "
            f"acceptance criterion remains traceable to section {number}."
        ),
        (
            f"Given the first review of \"{first}\", when the {profile['persona']} approves it, then "
            "the story moves to approved with no open Blocking question."
        ),
        (
            f"Given an incomplete item in section {number}, when the analyst reviews it, then a "
            "question with priority Important is raised before export."
        ),
    ]

    tests = _tests_from_criteria(criteria, number)

    estimate = "S" if len(text) < 500 else "L" if len(text) > 1400 else "M"
    evidence = [excerpt] if excerpt else []
    if topics:
        evidence.append(topics[0])

    goal = normalize_goal(profile["goal"])
    benefit = normalize_benefit(profile["benefit"])
    return {
        "title": story_title,
        "persona": profile["persona"],
        "goal": goal,
        "benefit": benefit,
        "as_a": profile["persona"],
        "i_want": goal,
        "so_that": benefit,
        "description": description,
        "business_rules": rules,
        "acceptance_criteria": criteria,
        "priority": profile["priority"],
        "priority_reason": profile["reason"],
        "estimate": estimate,
        "dependencies": list(profile.get("deps") or []),
        "tests": tests,
        "feature_hint": profile["feature"],
        "source_evidence": evidence[:3],
        "ambiguity_flag": False,
    }


def _consolidate(user: str) -> dict:
    if BACKLOG_INPUT not in user:
        return {"epics": [], "persona_aliases": [], "story_rewrites": []}
    try:
        payload = json.loads(user.split(BACKLOG_INPUT, 1)[1].strip())
    except json.JSONDecodeError:
        return {"epics": [], "persona_aliases": [], "story_rewrites": []}

    stories = payload.get("stories") or []
    if not stories:
        return {"epics": [], "persona_aliases": [], "story_rewrites": []}

    groups: dict[str, list[dict]] = {}
    for story in stories:
        hint = story.get("epic_hint") or "Project backlog"
        groups.setdefault(hint, []).append(story)

    if len(groups) > 9:
        ordered = list(groups.items())
        kept = ordered[:8]
        extra = [story for _, items in ordered[8:] for story in items]
        kept.append(("Additional scope", extra))
        groups = dict(kept)

    if len(groups) < 5 and len(stories) >= 5:
        refs = [story.get("ref") for story in stories]
        groups = {}
        for index in range(5):
            chunk = refs[index::5]
            if chunk:
                groups[f"Delivery theme {index + 1}"] = [
                    next(story for story in stories if story.get("ref") == ref) for ref in chunk
                ]

    epics = []
    for label, items in groups.items():
        title = re.sub(r"^\d+(?:\.\d+)*\s*", "", label).strip() or "Project scope"
        feature_groups: dict[str, list[str]] = {}
        for story in items:
            feature = story.get("feature_hint") or story.get("title") or "General"
            feature_groups.setdefault(feature, []).append(story.get("ref", ""))
        features = [
            {
                "title": feature,
                "summary": "",
                "story_refs": refs,
            }
            for feature, refs in feature_groups.items()
        ]
        story_titles = [story.get("title", "") for story in items[:2] if story.get("title")]
        first_goal = items[0].get("goal", "") if items else ""
        summary = (
            f"{title} groups the work needed to {first_goal or 'deliver the related business outcome'}. "
            f"It contains {len(features)} feature(s) and {len(items)} story(ies), including "
            f"{', '.join(story_titles) or 'the related stories'}. The stories share one business "
            "outcome and can be reviewed together."
        )
        epics.append({"title": title, "summary": summary, "features": features})

    return {"epics": epics, "persona_aliases": [], "story_rewrites": []}


class FakeLLM:
    name = "fake"

    def complete_json(self, system: str, user: str, schema: dict, on_event=None) -> dict:
        if "consolidat" in system.lower() or BACKLOG_INPUT in user:
            return _consolidate(user)
        return {
            "stories": [_story_from_section(user)],
            "questions": [],
        }
