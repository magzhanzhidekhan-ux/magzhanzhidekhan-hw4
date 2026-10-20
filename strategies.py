import collections
import json
import re
import time

from dotenv import load_dotenv
from openai import BadRequestError, OpenAI

from tools import REGISTRY, TOOLS

load_dotenv()                       # reads OPENAI_API_KEY from .env, never printed
client = OpenAI()

MODEL = "gpt-5.6-luna"
REASONING_EFFORT = "none"           # same for S1, S2, S3; required for function tools on this model
MAX_ROUNDS = 10                     # S3: typical question needs 3-4 rounds; 10 leaves margin
K = 5                               # S2 samples
TEMPERATURE_S2 = 1.0                # S1 and S3 use the API default
NO_TEMPERATURE = False              # set to True if the model rejects temperature

FORMAT_RULE = (
    "End your reply with exactly one final line in this format:\n"
    "ANSWER: <name or yes/no> | <number>\n"
    "Use the district name (or yes/no for yes/no questions), then the number with at most "
    "3 decimal places, no units and no thousands separators.")


def _docs_text():
    from tools import _corpus
    return "\n\n".join(f"[{d['id']}] {d['title']}\n{d['text']}" for d in _corpus())


SYS_DOCS = ("You answer questions about the Nine Rivers Region using only the documents below.\n\n"
            + _docs_text() + "\n\n" + FORMAT_RULE)
SYS_DOCS_COT = SYS_DOCS + "\n\nThink step by step and show your calculation before the final line."
SYS_TOOLS = ("You answer questions about the Nine Rivers Region. You have no documents: use the "
             "lookup tool for every fact and the calculate tool for every calculation. Do not "
             "guess figures and do not do arithmetic in your head.\n\n" + FORMAT_RULE)


def chat(**kw):
    global NO_TEMPERATURE
    if NO_TEMPERATURE:
        kw.pop("temperature", None)
    try:
        return client.chat.completions.create(model=MODEL, reasoning_effort=REASONING_EFFORT, **kw)
    except BadRequestError as e:
        if "temperature" in kw and "temperature" in str(e).lower():
            NO_TEMPERATURE = True
            kw.pop("temperature")
            return client.chat.completions.create(model=MODEL, reasoning_effort=REASONING_EFFORT, **kw)
        raise


def parse_answer(text):
    found = re.findall(r"ANSWER:\s*([^|\n]+?)\s*\|\s*(-?[\d.,]+)", text or "", re.I)
    if not found:
        return None
    name, num = found[-1]
    try:
        return name.strip(" *`").lower(), float(num.replace(",", "").rstrip(".,"))
    except ValueError:
        return None


def is_correct(parsed, q):
    """name equal (case-insensitive) and |number - value| <= 10**-decimals."""
    if parsed is None:
        return False
    name, num = parsed
    return name == q["answer"].lower() and abs(num - q["value"]) <= 10 ** -q["decimals"] + 1e-9


def s1(question):
    t0 = time.perf_counter()
    r = chat(messages=[{"role": "system", "content": SYS_DOCS},
                       {"role": "user", "content": question}])
    text = r.choices[0].message.content
    parsed = parse_answer(text)
    return {"parsed": parsed, "unanswered": parsed is None, "text": text,
            "in": r.usage.prompt_tokens, "out": r.usage.completion_tokens,
            "sec": time.perf_counter() - t0}


def s2(question):
    t0 = time.perf_counter()
    votes, texts, tin, tout = [], [], 0, 0
    for _ in range(K):
        r = chat(messages=[{"role": "system", "content": SYS_DOCS_COT},
                           {"role": "user", "content": question}],
                 temperature=TEMPERATURE_S2)
        tin += r.usage.prompt_tokens
        tout += r.usage.completion_tokens
        text = r.choices[0].message.content
        texts.append(text)
        p = parse_answer(text)
        if p:
            votes.append((p[0], round(p[1], 3)))
    if votes:
        name = collections.Counter(n for n, _ in votes).most_common(1)[0][0]
        nums = sorted(v for n, v in votes if n == name)
        winner = (name, nums[len(nums) // 2])
    else:
        winner = None
    return {"parsed": winner, "unanswered": winner is None, "votes": votes, "texts": texts,
            "in": tin, "out": tout, "sec": time.perf_counter() - t0}


def s3(question, tools=TOOLS):
    t0 = time.perf_counter()
    messages = [{"role": "system", "content": SYS_TOOLS},
                {"role": "user", "content": question}]
    log, tin, tout, text = [], 0, 0, None
    for rnd in range(1, MAX_ROUNDS + 1):
        r = chat(messages=messages, tools=tools)
        tin += r.usage.prompt_tokens
        tout += r.usage.completion_tokens
        msg = r.choices[0].message
        if not msg.tool_calls:
            text = msg.content
            log.append({"round": rnd, "final": text, "prompt_tokens": r.usage.prompt_tokens})
            break
        messages.append(msg)                       # unchanged
        calls = []
        for tc in msg.tool_calls:                  # every tool_call_id gets an answer
            t1 = time.perf_counter()
            name, raw = tc.function.name, tc.function.arguments
            try:
                args = json.loads(raw)
                if not isinstance(args, dict):
                    raise ValueError("arguments must be a JSON object")
                if name not in REGISTRY:
                    result = {"error": "unknown_tool", "message": f"no tool named {name}"}
                else:
                    result = REGISTRY[name](**args)
            except (json.JSONDecodeError, ValueError, TypeError) as e:
                result = {"error": "invalid_arguments", "message": f"bad arguments: {e}"}
            calls.append({"id": tc.id, "tool": name, "arguments": raw, "result": result,
                          "seconds": round(time.perf_counter() - t1, 5)})
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result)})
        log.append({"round": rnd, "prompt_tokens": r.usage.prompt_tokens, "tool_calls": calls})
    parsed = parse_answer(text) if text else None
    return {"parsed": parsed, "unanswered": parsed is None, "text": text, "log": log,
            "rounds": len(log), "in": tin, "out": tout, "sec": time.perf_counter() - t0}


RUN = {"S1": s1, "S2": s2, "S3": s3}