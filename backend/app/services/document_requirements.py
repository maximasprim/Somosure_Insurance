"""Single source of truth for "which documents does a customer need, and
what should they look like".

Used in three places so they can never drift apart:
  * GET /api/v1/quotes/document-requirements - tells the customer, right
    after quotes are generated, exactly which softcopies to have ready;
  * the upload validator (document_validation.py) - the keyword hints used
    to recognise a genuine document come from here;
  * the financing document checklist (document_reuse_service.py).

Nothing here touches the database, so it is cheap to import anywhere.
"""

from dataclasses import dataclass, field

ACCEPTED_FORMATS = "PDF, JPEG or PNG"
MAX_MB = 10


@dataclass(frozen=True)
class DocumentSpec:
    type: str
    label: str
    description: str
    tips: tuple[str, ...] = ()
    # Phrases (matched case-insensitively against text pulled from a PDF,
    # or from an image when OCR is available) that a genuine document of
    # this type normally contains. A document must contain at least
    # `min_hits` DISTINCT groups below to be recognised; each group is a
    # tuple of alternatives where any one counts. See document_validation.
    keyword_groups: tuple[tuple[str, ...], ...] = field(default=(), repr=False)
    min_hits: int = 1
    # Regexes that, if matched anywhere in the text, count as a hit on
    # their own (e.g. the shape of a KRA PIN).
    patterns: tuple[str, ...] = field(default=(), repr=False)


NATIONAL_ID = DocumentSpec(
    type="national_id",
    label="National ID",
    description="A clear copy of your Kenyan national ID - front and back.",
    tips=(
        "Photograph or scan both sides, flat, with all four corners visible.",
        "Digital ID / Maisha Card copies are fine.",
    ),
    keyword_groups=(
        ("republic of kenya", "jamhuri ya kenya"),
        ("identity card", "kitambulisho", "national id", "maisha", "huduma"),
        ("id number", "namba ya kitambulisho", "serial number"),
        ("date of birth", "tarehe ya kuzaliwa", "district of birth", "place of issue"),
    ),
    min_hits=2,
)

LOGBOOK = DocumentSpec(
    type="logbook",
    label="Vehicle logbook",
    description=(
        "The vehicle's registration document - either a scan/photo of the physical logbook, "
        "or the online copy downloaded from NTSA / eCitizen (TIMS)."
    ),
    tips=(
        "For the physical logbook, include the page showing chassis number, engine number and the registered owner.",
        "An online NTSA copy or search certificate saved as PDF works too.",
        "The registered owner should match the name on the application.",
    ),
    keyword_groups=(
        ("chassis",),
        ("engine no", "engine number", "engine"),
        ("registration no", "registration number", "registration certificate", "certificate of registration", "reg no"),
        ("log book", "logbook"),
        ("ntsa", "national transport and safety", "traffic act", "tims", "ecitizen"),
    ),
    min_hits=2,
)

KRA_PIN = DocumentSpec(
    type="kra_pin",
    label="KRA PIN certificate",
    description="Your KRA PIN certificate (PDF downloaded from iTax, or a clear photo of the printed copy).",
    tips=("Log in to iTax and use 'Reprint PIN Certificate' if you no longer have it.",),
    keyword_groups=(
        ("kenya revenue authority", "kra"),
        ("pin certificate", "personal identification number", "taxpayer", "tax payer", "itax"),
    ),
    min_hits=1,
    patterns=(r"\b[AP]\d{9}[A-Z]\b",),
)

CERTIFICATE_OF_INCORPORATION = DocumentSpec(
    type="certificate_of_incorporation",
    label="Certificate of incorporation",
    description="Your company's certificate of incorporation (replaces the national ID for company applicants).",
    tips=("A CR12 or business registration certificate is not a substitute - use the certificate of incorporation.",),
    keyword_groups=(
        ("certificate of incorporation", "certificate of registration"),
        ("companies act", "registrar of companies", "business registration service", "company no", "company number"),
        ("limited", "ltd", "private company"),
    ),
    min_hits=2,
)

PROPERTY_PROOF = DocumentSpec(
    type="property_proof",
    label="Proof of ownership or tenancy",
    description=(
        "Something that shows you own or rent the property you're insuring - a title deed or sale agreement, "
        "a lease, or a recent rates or utility bill in your name."
    ),
    tips=(
        "A photo or scan of the first page is enough if the document is long.",
        "For business premises, a lease or a trading licence showing the address works too.",
    ),
)

APPLICATION_FORM = DocumentSpec(
    type="application_form",
    label="Filled financing application form",
    description="The Bidii Credit financing application form, filled in and signed.",
    tips=("Fill it in clearly and sign it before scanning or photographing it.",),
)

PREMIUM_QUOTE = DocumentSpec(
    type="premium_quote",
    label="Insurance premium quote",
    description="The premium quote you selected. Somosure attaches this for you automatically - you don't upload it.",
)

SPECS: dict[str, DocumentSpec] = {
    s.type: s
    for s in (NATIONAL_ID, LOGBOOK, KRA_PIN, CERTIFICATE_OF_INCORPORATION, PROPERTY_PROOF, APPLICATION_FORM, PREMIUM_QUOTE)
}

# Document types the platform itself produces for the customer, so they are
# never asked to upload them.
SYSTEM_PROVIDED_TYPES = {"premium_quote"}

# Identity-style documents that stay valid across applications, so they
# can be reused for a returning, logged-in customer instead of re-asked.
REUSABLE_ACROSS_APPLICATIONS = {"national_id", "kra_pin", "certificate_of_incorporation"}


def insurance_documents(category: str) -> list[DocumentSpec]:
    """Documents needed for the insurance application itself.

    Motor needs the vehicle logbook; every other category only needs
    identity and tax documents (asking for a logbook on a medical or
    travel policy makes no sense)."""
    if category == "motor":
        return [NATIONAL_ID, LOGBOOK, KRA_PIN]
    if category == "property":
        return [NATIONAL_ID, PROPERTY_PROOF, KRA_PIN]
    return [NATIONAL_ID, KRA_PIN]


def financing_documents(is_corporate: bool) -> list[DocumentSpec]:
    """Documents Bidii Credit needs - same list the backend already
    enforces informationally (see REQUIRED_DOCUMENT_TYPES_* in
    financing_service.py)."""
    return [
        APPLICATION_FORM,
        LOGBOOK,
        CERTIFICATE_OF_INCORPORATION if is_corporate else NATIONAL_ID,
        KRA_PIN,
        PREMIUM_QUOTE,
    ]


def spec_to_dict(spec: DocumentSpec) -> dict:
    return {
        "type": spec.type,
        "label": spec.label,
        "description": spec.description,
        "tips": list(spec.tips),
        "system_provided": spec.type in SYSTEM_PROVIDED_TYPES,
    }


def requirements_payload(category: str, is_corporate: bool = False) -> dict:
    """The JSON the frontend shows on the 'have these ready' card."""
    return {
        "category": category,
        "accepted_formats": ACCEPTED_FORMATS,
        "max_mb": MAX_MB,
        "general_tips": [
            "Use your phone's scan feature or a flat, well-lit photo - all four corners and every line of text readable.",
            "One document per file. Don't combine different documents into a single upload.",
            "Documents are checked on upload, so a blurry, blank or wrong file will be flagged straight away.",
        ],
        "insurance": [spec_to_dict(s) for s in insurance_documents(category)],
        "financing": {
            "note": (
                "Only needed if you choose Bidii Credit financing. Anything you've already uploaded for your "
                "insurance application is reused automatically - you won't be asked for it twice."
            ),
            "documents": [spec_to_dict(s) for s in financing_documents(is_corporate)],
        },
    }
