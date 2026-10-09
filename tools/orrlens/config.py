"""Constants shared by the generator and the checks."""

import re

SCHEMA_VERSION = "2021-11-01"

# Limits (see docs/scoring.md and the AWS WA Tool lens format specification and API reference)
MAX_PILLARS = 10
MAX_QUESTIONS_PER_PILLAR = 20
MAX_CHOICES_PER_QUESTION = 15
MAX_STATEMENTS = 4             # lens policy: at most 4 non-None statements per question
MAX_RULES = 3
MAX_LENS_NAME = 128
MAX_LENS_DESCRIPTION = 1024    # Lens/LensSummary Description in the API
MAX_TITLE = 128                # question and choice titles
MAX_DESCRIPTION = 1024         # Answer.QuestionDescription in the API (spec allows 2,048)
MAX_QUESTION_HELPFUL = 64      # Answer.HelpfulResourceDisplayText in the API (spec allows 2,048)
MAX_CHOICE_TEXT = 1024         # ChoiceContent display text and URL in the API (spec allows 2,048)
MAX_ADDITIONAL_PER_TYPE = 5
MAX_ID = 64                    # lens policy (UpdateAnswer caps choice ids at 64)
MIN_ID = 3
LENS_SIZE_BUDGET = 400 * 1024  # hard limit is 500 KB
VERSION_NAME_MAX = 32

# ImportLens restricts the characters of these fields (sandbox gate G4, 2026-10-06; see docs/gates.md): lens name,
# lens description, pillar name, question title, question description and choice title. The API error lists
# letters, digits and - _ . , : / ( ) @ ! & # + ' and U+2019; space, newline and ? were also accepted. It rejects,
# among others, ; % < > = * " [ ] $ | ~ { }. Helpful, improvement and additional-resource display texts are not
# restricted. The lens is ASCII only, so U+2019 is never used.
RESTRICTED_FIELD_CHARS = r"[A-Za-z0-9 \n\-_.,:/()@!&#+'?]"

NONE_ID = "none_no"
NONE_TITLE = "None of these"

CATEGORIES = [
    "Deployment safety",
    "Defense against overload",   # the whitepaper's "Defense against customers" (renamed in core 2.0.1, event 1.0.1 and genai 1.0.1)
    "Defense against dependencies",
    "Data recovery",
    "Operator safety",
    "Blast radius containment",
    "Event detection",
    "Service restart",
    "Forensics",
    "Escalation",
    "Readiness governance",   # addition to the whitepaper's ten
    "Security readiness",     # addition to the whitepaper's ten
]

RISK_TEXT = {
    "HIGH": "Maximum risk: High (launch-blocking unless remediated or formally accepted).",
    "MEDIUM": "Maximum risk: Medium (not launch-blocking, remediate on a plan).",
}

RISK_WORD = {"HIGH": "High", "MEDIUM": "Medium"}

ALLOWED_URL_HOSTS = (
    "docs.aws.amazon.com",
    "aws.amazon.com",
    "builder.aws.com",
    "opentelemetry.io",
    "owasp.org",
    "genai.owasp.org",
)
# github.com URLs are allowed only under these AWS organizations (the first path segment, matched exactly).
ALLOWED_GITHUB_ORGS = frozenset({
    "aws", "awslabs", "aws-samples", "aws-solutions", "aws-solutions-library-samples", "awsdocs",
    "aws-observability", "aws-ia", "aws-cloudformation", "aws-powertools", "aws-actions",
})

RESERVED_PREFIX = "x_"

# ---------------------------------------------------------------------------
# Well-Architected best-practice ids
# ---------------------------------------------------------------------------

# Sources of the best-practice ids that `wa_bp` and `severity_basis: "wa:<BP-ID> (High)"` may name, keyed by the
# `lens` field of data/wa-best-practices.yaml (an entry without `lens` is a Framework practice). `pattern` is the
# id format and `url_dirs` the documentation folders an entry's url may use. Formats were read from each lens's
# live table of contents on 2026-10-07: the Generative AI Lens uses GEN<pillar>, the Agentic AI Lens
# AGENT<pillar> and the Responsible AI Lens RAI<focus area> (UC, BR, DP, ER, GT, MON, RC, SP).
WA_FRAMEWORK = "framework"
WA_BP_SOURCES = {
    "framework": {
        "name": "AWS Well-Architected Framework",
        "pattern": r"(?:OPS|SEC|REL|PERF|COST|SUS)\d{2}-BP\d{2}",
        "url_dirs": ("framework", "operational-excellence-pillar", "security-pillar", "reliability-pillar",
                     "performance-efficiency-pillar", "cost-optimization-pillar", "sustainability-pillar"),
    },
    "generative-ai": {
        "name": "Generative AI Lens",
        "pattern": r"GEN(?:OPS|SEC|REL|PERF|COST|SUS)\d{2}-BP\d{2}",
        "url_dirs": ("generative-ai-lens",),
    },
    "agentic-ai": {
        "name": "Agentic AI Lens",
        "pattern": r"AGENT(?:OPS|SEC|REL|PERF|COST|SUS)\d{2}-BP\d{2}",
        "url_dirs": ("agentic-ai-lens",),
    },
    "responsible-ai": {
        "name": "Responsible AI Lens",
        "pattern": r"RAI(?:UC|BR|DP|ER|GT|MON|RC|SP)\d{2}-BP\d{2}",
        "url_dirs": ("responsible-ai-lens",),
    },
}
# Any best-practice id of any source above (no anchors; callers add them).
WA_BP_ID = "(?:" + "|".join(v["pattern"] for v in WA_BP_SOURCES.values()) + ")"


def wa_bp_source(bp_id: str):
    """The WA_BP_SOURCES key whose id format bp_id matches exactly, or None."""
    for key, v in WA_BP_SOURCES.items():
        if re.fullmatch(v["pattern"], bp_id or ""):
            return key
    return None


# ---------------------------------------------------------------------------
# Repository layout
# ---------------------------------------------------------------------------

LENS_ORDER = ["core", "event", "genai"]   # lens-src/<key>/lens.yaml; other keys sort after these
MAX_FAMILY_LENSES = 4                     # family policy: the core lens plus at most three companion modules
V1_DIR = "wafr-operational-readiness-lens"
V1_GLOB = "orr-v1.3.*-PUBLISHED.json"
V1_CURRENT = "1.3.6"                            # the last published v1 version
ADDON_SOURCE = "lens-src/templates/org-addon.yaml"
ADDON_OUTPUT = "templates/org-addon-lens.json"
IDS_FILE = "ids.yaml"
DENYLIST_FILE = "private/denylist.txt"
DATA_WA_BPS = "data/wa-best-practices.yaml"
DATA_PARTITIONS = "data/partition-availability.yaml"
DATA_LIFECYCLE = "data/lifecycle-denylist.yaml"
DATA_BUILDER = "data/builder-allowlist.yaml"
RELEASE_STAGING = "build/release"

# Question ids retired permanently in 2.0.0: the four typo'd ids, and the kept ids whose applicability broadened
# (gate G2 showed that v1 "does not apply" flags carry over to kept ids, decision D-2). They can never become
# active again, even before 2.0.0 is released.
PERMANENT_RETIREMENTS = {
    "architecture_plane_redundency": "2.0.0",
    "architecture_gradeful_recovery": "2.0.0",
    "architecture_mulitaccount_stragy": "2.0.0",
    "architecture_mutliaccount_credentials": "2.0.0",
    "releases_onebox_deployments": "2.0.0",
    "architecture_health_checks": "2.0.0",
}

# ---------------------------------------------------------------------------
# Language and text checks
# ---------------------------------------------------------------------------

# Forward-looking availability wording. "planned" and "soon" are matched in availability contexts only, because
# the lenses legitimately say "planned peak", "planned lifecycle events", "a planned rollback", "as soon as" and
# "soon enough"; "not yet", "not run yet", "under development", "no release date", "roadmap" and
# "upcoming <feature|launch|...>" are matched everywhere.
FORWARD_LOOKING = [
    r"\bbeing\s+planned\b",
    r"\bplanned\s+for\b",
    r"\b(?:is|are|was|were|be|been|remains?)\s+(?:currently\s+|also\s+)?planned\b",
    r"\bplanned\s+(?:to\s+(?:launch|ship|release|support|arrive|be\s+available)|support|availability|launch|release)\b",
    r"\bcoming\s+soon\b",
    r"(?<!\bas\s)(?<!\bor\s)\bsoon\b(?!\s+(?:as|enough|after)\b)",
    r"\bnot\s+yet\b",
    r"\bnot\s+run\s+yet\b",
    r"\bunder\s+development\b",
    r"\bno\s+release\s+date\b",
    r"\bwill\s+(?:soon\s+)?(?:be\s+)?(?:generally\s+)?(?:available|supported|launch\w*|released?|added|offered)\b",
    r"\bexpected\s+to\s+(?:launch|ship|be\s+(?:available|supported|released))\b",
    r"\bupcoming\s+(?:features?|launch(?:es)?|releases?|support|availability|services?|capabilit(?:y|ies))\b",
    r"\broadmap\b",
    r"\blater\s+this\s+(?:year|quarter|month)\b",
    r"\bin\s+the\s+coming\s+(?:weeks|months|quarters?|year)\b",
    r"\b20\d\d\s?Q[1-4]\b",
    r"\bQ[1-4]\s?20\d\d\b",
]
INCLUSIVE_DENYLIST = [r"\bwhite-?lists?(?:ed|ing)?\b", r"\bblack-?lists?(?:ed|ing)?\b", r"\bmasters?\b", r"\bslaves?\b"]
DASHES = {"\u2014": "em dash", "\u2013": "en dash"}

# Repository files (besides the rendered lens text) that the language check scans.
LANGUAGE_FILE_GLOBS = [
    "README.md", "MIGRATION.md", "CHANGELOG.md", "CONTRIBUTING.md", "SECURITY.md", "CODEOWNERS",
    "docs/**/*.md", "docs/**/*.csv", "crosswalk/**/*.csv", "lens-src/**/*.yaml", "lens-src/**/*.md",
    "data/**/*.yaml", "templates/**/*.json", "wafr-operational-readiness-lens/README.md",
]

# Files and folders scanned for links (links command and the online part of check).
LINK_SOURCE_GLOBS = ["lens-src/**/*.yaml", "data/**/*.yaml", "docs/**/*.md", "docs/**/*.csv", "README.md"]

# URLs of this repository: host-checked only, because release assets and files on main exist only after the
# public squash commit and release. /blob/main/<path> and /tree/main/<path> must exist locally.
SELF_REPO_URL = "https://github.com/awslabs/operational-readiness-review-custom-war-lens"
SELF_REPO_SLUG = "awslabs/operational-readiness-review-custom-war-lens"

# Phrases that the partition matcher finds after "AWS" or "Amazon" but that are not services. Matching is exact
# on the whole capitalized run (so "AWS Cloud" does not hide "AWS Cloud Map" or "AWS Cloud WAN", and "AWS Account"
# does not hide "AWS Account Management"), except for entries that end with " *", which match by word prefix:
# "AWS Well-Architected *" covers "AWS Well-Architected" and "AWS Well-Architected Framework". Add more in
# data/partition-availability.yaml under not_services (the same syntax).
NOT_SERVICES = [
    "Amazon Web Services",
    "AWS Region", "AWS Regions",
    "AWS GovCloud *",
    "AWS Well-Architected *",
    "AWS Post-Event Summary", "AWS Post-Event Summaries",
    "AWS Operational Readiness *",
    "AWS Builders *", "Amazon Builders *", "AWS Builder Center",
    "AWS ORR",
    "AWS Capabilities",
    "AWS What",
    "AWS Management Console",
    "AWS CLI", "AWS SDK", "AWS SDKs",
    "AWS Partner", "AWS Partners", "AWS Partner Network",
    "AWS Prescriptive Guidance",
    "AWS Architecture Blog", "AWS Public Sector Blog",
    "AWS Account", "AWS Accounts",
    "AWS Cloud",
    "AWS API", "AWS APIs", "AWS Services", "AWS Solution", "AWS Solutions",
]

# Leftover placeholders that must be replaced before a release: (kind, regex, flags). Every exportable text file
# except Python sources is scanned (see checks.check_placeholders). Format tokens that documentation uses on
# purpose, such as <register-id>, <yyyy-mm> or YYYY-MM-DD, are not placeholders. GitHub Actions expressions
# (${{ ... }}) are excluded.
PLACEHOLDER_PATTERNS = [
    ("template placeholder", r"(?<![$\w{])\{\{[^{}\n]{0,80}\}\}(?!\})", 0),
    ("placeholder", r"<\s*(?:(?:release|publication|publish|launch|target|due|ship|go-live|blog[ _-]post)[ _-]?"
                    r"(?:date|day|url|link|version)|date|tbd|todo|fixme|placeholder|insert\b[^<>\n]{0,60}|"
                    r"fill[ _-]in\b[^<>\n]{0,60}|replace[ _-](?:me|with\b[^<>\n]{0,60}))\s*>", re.I),
    ("placeholder", r"\[\s*(?:tbd|todo|placeholder|date|release[ _-]date|insert\b[^\]\n]{0,60})\s*\]", re.I),
    ("unfinished marker", r"\b(?:TBD|TODO|FIXME|TKTK)\b", 0),
]

# Repository prose (besides the rendered lens text) in which the partition check also verifies "available" and
# "not available" statements about AWS GovCloud (US) against data/partition-availability.yaml. docs/questions.md
# is generated from the lens text, which is checked directly.
PARTITION_CLAIM_FILE_GLOBS = ["README.md", "MIGRATION.md", "CHANGELOG.md", "CONTRIBUTING.md", "docs/**/*.md",
                              "wafr-operational-readiness-lens/README.md"]
PARTITION_CLAIM_SKIP = ("docs/questions.md",)

# Exported files that may be binary (not UTF-8 text). Any other exported file must decode as text, or the
# internal-wording check fails instead of skipping it.
BINARY_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip")

# Built-in sensitive-data patterns for the internal-wording check; they run even without private/denylist.txt.
# 123456789012 is the documentation placeholder account id and is allowed.
SENSITIVE_PATTERNS = [
    ("AWS account id", r"(?<![0-9A-Za-z])(?!123456789012(?![0-9]))\d{12}(?![0-9A-Za-z])"),
    ("ARN with an account id", r"arn:aws[a-z-]*:[^\s:]*:[^\s:]*:(?!123456789012\b)\d{12}\b"),
]

USER_AGENT = ("orrlens-linkcheck/2.0 (+https://github.com/awslabs/operational-readiness-review-custom-war-lens; "
              "weekly documentation link check)")
