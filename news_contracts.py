"""Small, explicit JSON contracts used locally and sent to Gemini.

The validator implements only the keyword subset used by these fixed contracts;
it is not a general-purpose JSON Schema implementation.
"""
import math


class ContractError(ValueError):
    """Fixed diagnostic; never echo untrusted model output."""


def obj(properties):
    return {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}


def array(items, minimum=0, maximum=5):
    return {"type": "array", "items": items, "minItems": minimum,
            "maxItems": maximum}


def text(maximum=400):
    return {"type": "string", "minLength": 1, "maxLength": maximum}


SOURCE_IDS = array(text(40), 1, 8)
EVENT_ID = {"type": "string",
            "enum": ["event_1", "event_2", "event_3", "event_4", "event_5"]}
SHORTLIST_SCHEMA = obj({
    "events": array(obj({
        "event_id": EVENT_ID,
        "working_headline": text(180),
        "category": {"type": "string",
                     "enum": ["World", "Economy", "Technology", "Science"]},
        "priority": {"type": "integer", "minimum": 0, "maximum": 100},
        "rationale": text(500),
        "source_ids": SOURCE_IDS,
        "search_query": text(160),
    })),
})
ASSESSMENT_SCHEMA = obj({
    "events": array(obj({
        "event_id": EVENT_ID,
        "draft_summary": text(600),
        "why_it_matters": text(400),
        "unresolved_issues": array(text(250), 0, 6),
        "claims": array(obj({
            "text": text(350),
            "proposed_status": {
                "type": "string",
                "enum": ["corroborated", "disputed", "insufficient_evidence"],
            },
            "evidence": array(obj({
                "source_id": text(40),
                "relationship": {"type": "string",
                                 "enum": ["supports", "contradicts"]},
                "quote": text(1000),
            }), 1, 8),
        }), 1, 4),
    })),
})


def validate_contract(value, schema):
    """Validate exact keys, types, finite numbers, enums, and bounded lengths."""
    kind = schema["type"]
    valid_type = {
        "object": type(value) is dict,
        "array": type(value) is list,
        "string": type(value) is str,
        "integer": type(value) is int,
    }.get(kind, False)
    if not valid_type:
        raise ContractError("model_contract_type_mismatch")
    if "enum" in schema and value not in schema["enum"]:
        raise ContractError("model_contract_enum_mismatch")
    if kind == "object":
        if set(value) != set(schema["required"]):
            raise ContractError("model_contract_keys_mismatch")
        for name, child in schema["properties"].items():
            validate_contract(value[name], child)
    elif kind == "array":
        if not schema["minItems"] <= len(value) <= schema["maxItems"]:
            raise ContractError("model_contract_array_limit")
        for item in value:
            validate_contract(item, schema["items"])
    elif kind == "string":
        if not schema.get("minLength", 0) <= len(value) <= schema.get("maxLength", 10000):
            raise ContractError("model_contract_text_limit")
        if not value.strip():
            raise ContractError("model_contract_empty_text")
    elif kind == "integer":
        if not math.isfinite(value) or not schema["minimum"] <= value <= schema["maximum"]:
            raise ContractError("model_contract_number_limit")


def provider_schema(schema):
    """Keep the decoding schema small; enforce all size bounds locally.

    Nested bounded arrays can multiply the provider's decoder state space.
    Types, required keys and enums remain in the request; lengths and counts
    are checked by validate_contract after decoding.
    """
    result = {}
    for key, value in schema.items():
        if key in ("minLength", "maxLength", "minItems", "maxItems"):
            continue
        if key == "properties":
            result[key] = {}
            for name, child in value.items():
                result[key][name] = provider_schema(child)
        elif key == "items":
            result[key] = provider_schema(value)
        else:
            result[key] = value
    return result
