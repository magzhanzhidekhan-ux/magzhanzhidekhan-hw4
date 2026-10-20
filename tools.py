import ast
import difflib
import functools
import json
import math
import operator
import re
from pathlib import Path

CORPUS_PATH = Path(__file__).parent / "data" / "corpus.jsonl"
MAX_ARG_LEN = 100
MAX_EXPR_LEN = 200
MAX_ABS = 1e15


def _err(code, message, **extra):
    return {"error": code, "message": message, **extra}


@functools.lru_cache(maxsize=1)
def _corpus():
    with open(CORPUS_PATH, encoding="utf-8") as f:
        return tuple(json.loads(line) for line in f if line.strip())


FIELDS = {
    "population_2025": ("residents", [
        r"2025 census (?:recorded|counted) ([\d,]+) residents",
        r"Census population: [\d,]+ in 2020 and ([\d,]+) in 2025"]),
    "population_2020": ("residents", [
        r"2020 census had recorded ([\d,]+)",
        r"Census population: ([\d,]+) in 2020",
        r"up from ([\d,]+) at the 2020 census"]),
    "area_km2": ("km2", [r"([\d,]+(?:\.\d+)?) square kilometres"]),
    "budget_million_tenge": ("million tenge", [r"([\d,]+(?:\.\d+)?) million tenge"]),
    "water_megalitres": ("megalitres", [r"([\d,]+) (?:megalitres|cubic metres)"]),
    "schools": ("schools", [r"(?:has|runs|are) (\d+) schools"]),
    "pupils": ("pupils", [r"([\d,]+) pupils"]),
    "roads_km": ("km", [r"([\d,]+(?:\.\d+)?) km (?:long|of paved road)"]),
    "founded_year": ("year", [r"[Ff]ounded in (\d{4})"]),
}
ALL_FIELDS = sorted(list(FIELDS) + ["water_tariff_2025"])

CORRECTION_PATTERNS = {
    "area_km2": r"correct area is ([\d,]+(?:\.\d+)?) square kilometres",
}


def _num(s):
    s = s.replace(",", "")
    v = float(s)
    return int(v) if "." not in s else v


def _profiles(docs):
    """name -> {'current': [docs], 'archived': [docs]}"""
    out = {}
    for d in docs:
        m = re.match(r"(.+?) district profile", d["title"])
        if not m:
            continue
        kind = "archived" if "ARCHIVED" in d["title"].upper() else "current"
        out.setdefault(m.group(1), {"current": [], "archived": []})[kind].append(d)
    return out


def _corrections(docs):
    out = {}
    for d in docs:
        if not d["title"].lower().startswith("correction"):
            continue
        name = d["title"].split(" - ")[-1].strip().lower()
        for field, pat in CORRECTION_PATTERNS.items():
            m = re.search(pat, d["text"])
            if m:
                out[(name, field)] = (_num(m.group(1)), d["id"])
    return out


def lookup(district, field):
    if (not isinstance(district, str) or not isinstance(field, str)
            or not district.strip() or not field.strip()
            or len(district) > MAX_ARG_LEN or len(field) > MAX_ARG_LEN):
        return _err("invalid_arguments",
                    "District and field must be non-empty strings (max 100 characters)")
    try:
        docs = _corpus()
    except (OSError, ValueError):
        return _err("data_error", "Unable to read the corpus")

    field = field.strip().lower()
    if field not in ALL_FIELDS:
        return _err("field_not_found",
                    "The requested field is unavailable. Available: " + ", ".join(ALL_FIELDS))
    key = district.strip().lower()

    # regional tariff
    if key in ("region", "regional"):
        if field != "water_tariff_2025":
            return _err("field_not_found", "For 'region' only water_tariff_2025 is available")
        for d in docs:
            m = re.search(r"tariff is ([\d.]+) tenge per cubic metre", d["text"])
            if m:
                return {"district": "region", "field": field, "value": float(m.group(1)),
                        "unit": "tenge per cubic metre", "source": d["id"]}
        return _err("unreadable_value", "The tariff could not be read")
    if field == "water_tariff_2025":
        return _err("invalid_arguments", "water_tariff_2025 needs district='region'")

    profiles = _profiles(docs)
    by_lower = {n.lower(): n for n in profiles}

    if key not in by_lower:
        prefix = sorted(n for l, n in by_lower.items() if len(key) >= 3 and l.startswith(key))
        if len(prefix) > 1:
            return _err("ambiguous_district",
                        "Multiple possible district matches: " + ", ".join(prefix),
                        candidates=prefix)
        close = difflib.get_close_matches(key, list(by_lower), n=3, cutoff=0.6)
        hint = ", ".join(by_lower[c] for c in close)
        msg = f"No district named {district.strip()}"
        msg += f"; did you mean {hint}?" if hint else "; no similar name found"
        return _err("district_not_found", msg)

    name = by_lower[key]
    cur = profiles[name]["current"]
    if not cur:
        return _err("no_current_profile", "Only an archived profile exists for this district")
    if len(cur) > 1:
        return _err("ambiguous_profile", "More than one current profile found")
    doc = cur[0]

    # correction notices win over the profile
    corr = _corrections(docs).get((key, field))
    if corr:
        return {"district": name, "field": field, "value": corr[0],
                "unit": FIELDS[field][0], "source": corr[1],
                "note": f"corrected value; profile {doc['id']} has an error"}

    unit, patterns = FIELDS[field]
    m = None
    for pat in patterns:
        m = re.search(pat, doc["text"])
        if m:
            break
    if not m:
        return _err("unreadable_value", "The number could not be read from the profile")
    try:
        value = _num(m.group(1))
    except ValueError:
        return _err("unreadable_value", "The number could not be read from the profile")

    result = {"district": name, "field": field, "value": value, "unit": unit,
              "source": doc["id"]}
    if field == "water_megalitres":
        if "cubic metres" in m.group(0):
            result["value"] = value / 1000
            result["note"] = f"source gives {m.group(1)} cubic metres; converted to megalitres"
        elif "megalitres" not in m.group(0):
            return _err("unknown_unit", "The unit in the profile is not recognised")
    return result



class CalcError(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message


_BIN = {ast.Add: operator.add, ast.Sub: operator.sub,
        ast.Mult: operator.mul, ast.Div: operator.truediv}
_UN = {ast.USub: operator.neg, ast.UAdd: operator.pos}


def _ev(node):
    if isinstance(node, ast.Expression):
        return _ev(node.body)
    if isinstance(node, ast.Constant):
        if type(node.value) in (int, float):
            return node.value
        raise CalcError("invalid_expression", "Only numbers are allowed")
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Pow):
            raise CalcError("unsafe_expression", "Exponentiation is not allowed")
        if type(node.op) in _BIN:
            return _BIN[type(node.op)](_ev(node.left), _ev(node.right))
        raise CalcError("invalid_expression", "Operator not allowed")
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UN:
        return _UN[type(node.op)](_ev(node.operand))
    if isinstance(node, ast.Call):
        raise CalcError("unsafe_expression", "Function calls are not allowed")
    if isinstance(node, ast.Attribute):
        raise CalcError("unsafe_expression", "Attribute access is not allowed")
    if isinstance(node, ast.Name):
        raise CalcError("unsafe_expression", "Names are not allowed")
    raise CalcError("invalid_expression", "Invalid arithmetic expression")


def calculate(expression):
    if not isinstance(expression, str) or not expression.strip():
        return _err("invalid_arguments", "Expression must be a non-empty string")
    if len(expression) > MAX_EXPR_LEN:
        return _err("expression_too_long", "Expression exceeds the length limit")
    try:
        tree = ast.parse(expression.strip(), mode="eval")
        result = _ev(tree)
    except CalcError as e:
        return _err(e.code, e.message)
    except ZeroDivisionError:
        return _err("division_by_zero", "Cannot divide by zero")
    except OverflowError:
        return _err("number_too_large", "Result exceeds the allowed numeric range")
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return _err("invalid_expression", "Invalid arithmetic expression")
    if not math.isfinite(result):
        return _err("invalid_result", "Result must be finite")
    if abs(result) > MAX_ABS:
        return _err("number_too_large", "Result exceeds the allowed numeric range")
    return {"result": result}


LOOKUP_DESCRIPTION = (
    "Find one specific fact about a Nine Rivers Region district or the regional water tariff. "
    "Use exact district names; if a name is misspelled the tool returns suggestions and you must "
    "call it again with the correct name. Returns the value, its unit, and the source document ID. "
    "Only current 2025 profiles are used: archived profiles are ignored and correction notices are "
    "applied (the source then names the notice). Water use is always returned in megalitres. "
    "Call this tool to get every number before using it in a calculation; never guess a figure.")

CALCULATE_DESCRIPTION = (
    "Safely calculate a numerical arithmetic expression using +, -, *, /, parentheses, and unary "
    "signs. Use this tool for all arithmetic: population density, percentages, growth rates, "
    "per-resident and per-day figures, financial comparisons, and differences. Exponentiation (**) "
    "is not supported. Do not send Python code, variable names, or function calls; write plain "
    "numbers, using the exact values returned by lookup without rounding them first. Returns the "
    "result or a clear error.")


def build_tools(lookup_description=None):
    return [
        {"type": "function", "function": {
            "name": "lookup",
            "description": lookup_description or LOOKUP_DESCRIPTION,
            "parameters": {"type": "object", "properties": {
                "district": {"type": "string", "description":
                    "Exact district name, or 'region' for regional information such as water tariffs."},
                "field": {"type": "string", "description":
                    "Requested field: population_2025, population_2020, area_km2, "
                    "budget_million_tenge, water_megalitres, schools, pupils, roads_km, "
                    "founded_year, or water_tariff_2025."}},
                "required": ["district", "field"], "additionalProperties": False}}},
        {"type": "function", "function": {
            "name": "calculate",
            "description": CALCULATE_DESCRIPTION,
            "parameters": {"type": "object", "properties": {
                "expression": {"type": "string", "description":
                    "An arithmetic expression containing numeric constants, +, -, *, /, "
                    "parentheses, and unary signs. Example: '44675 / 921.4'."}},
                "required": ["expression"], "additionalProperties": False}}},
    ]


TOOLS = build_tools()
REGISTRY = {"lookup": lookup, "calculate": calculate}