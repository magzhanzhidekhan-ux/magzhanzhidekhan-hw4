# HW4 — submission

**AI assistance:** <!-- what you used, and for what. "None" is an answer too. -->
 I used two AI tools:
- **ChatGPT**: to explain Part A to me and to help me write my first draft of Part A (the steps, the tool definitions and the Q-09 walkthrough).
- **Claude (claude.ai)**:
  - to explain the assignment to me;
  - to check my Part A draft for mistakes (it pointed out overlapping steps, an incorrect statement about NR-16 in A3, and missing details such as units and 365 days in a year); after that I corrected Part A myself and committed it before writing any `.py` file;
  - to suggest starter code for `tools.py`, the tests, `strategies.py` and `run.py`, and to help me fix errors (the `reasoning_effort` error in S3 and the S2 voting);
  - to help with Git and PowerShell commands.

---

## Part A — Plan on paper (Easy)

> Commit this whole part before any `.py` file exists.

### A1 — The steps

| # | Step | What goes in (types) | What comes out (types) | When it goes wrong | Tool, loop, or model? |
|---|---|---|---|---|---|
| 1 | Understand the question | Question text (`str`) | District names (`list[str]`), required fields (`list[str]`), calculation goal (`str`) | If the question is unclear or the districts or fields cannot be identified, the model does not guess: it gives no ANSWER line and the question is marked unanswered (there is no human in the loop to ask for clarification) | Model |
| 2 | Request facts | One district name and one field name (`str`, `str`) | Tool call arguments as a JSON string, for example `{"district":"Brightwater","field":"area_km2"}` (`str`) | If an argument is missing, has the wrong type or is not valid JSON, the loop (step 9) catches it before anything runs and returns an `invalid_arguments` error for that `tool_call_id`; the model can then correct the call | Model |
| 3 | Find the district | District name (`str`) | District id such as `"brightwater"` (`str`) | Nothing found: error `district_not_found` with up to three "did you mean" suggestions. Two or more close matches (for example Ossbridge and Ossford): error `ambiguous_district` listing the candidates. The tool never picks one automatically | lookup tool |
| 4 | Pick the current profile | District id (`str`) | The 2025 profile of that district (`dict` with `id`, `title`, `text`) | A profile whose title contains ARCHIVED (NR-13, NR-14) is never used. If a district has only an archived profile, the error is `no_current_profile`. If two current profiles are found, the error is `ambiguous_profile` | lookup tool |
| 5 | Apply corrections | Profile (`dict`) and the list of correction notices from the corpus (`list[dict]`) | Profile with corrected figures and the id of the document that supplied the value (`dict`) | If a notice names a figure that cannot be found in the profile, the tool returns the profile value together with a `warning`. A correction always takes priority over the profile it corrects (NR-00): the result then names the notice (for example NR-16) as its source | lookup tool |
| 6 | Extract the field and normalise the unit | Profile (`dict`) and field name (`str`) | Value (`float`), unit (`str`), source document id (`str`) | Unknown field: error `field_not_found`. Number cannot be read from the text: error `unreadable_value`. Unit not recognised: error `unknown_unit`. Water use in cubic metres (Lindenmoor, NR-08) is converted to megalitres by the tool (1 megalitre = 1,000 cubic metres) and the original figure is shown in a `note` | lookup tool |
| 7 | Prepare calculations | Verified facts: values, units and sources (`list[dict]`) | Arithmetic expressions using only numbers and `+ - * / ( )` (`list[str]`) | If a needed fact is missing or an earlier lookup returned an error, the model does not invent a number and does not calculate; it repeats the lookup or ends as unanswered | Model |
| 8 | Calculate values | Arithmetic expression (`str`) | `{"result": float}` or an error (`dict`) | Division by zero: `division_by_zero`. Invalid syntax: `invalid_expression`. Function calls, attributes, names or `**`: `unsafe_expression`. Longer than the length limit: `expression_too_long`. Result too large or not finite: `number_too_large` or `invalid_result`. Nothing is ever run with `eval` or `exec` | calculate tool |
| 9 | Manage tool calls | The model's message with `tool_calls` (list) and each `arguments` string (`str`) | One `role: "tool"` message per `tool_call_id`, the updated conversation, and a log entry (`list[dict]`) | Malformed JSON, wrong argument names or an unknown tool name: an error message is still sent back for that `tool_call_id`. If the fixed round limit is reached, the loop stops and the question is marked unanswered | Loop |
| 10 | Compare and answer | Verified facts and calculated values (`list[dict]`) | Final answer line `ANSWER: <name or yes/no> \| <number>` (`str`) | If a result cannot be determined, or the model's reply has no valid ANSWER line, the question is marked unanswered and no number is invented. Rounding happens only here, to the number of decimals the question asks for | Model |

**How the steps connect:**

1. The model reads the question (step 1) and produces district names, fields and a calculation goal.
2. For each fact it needs, the model writes a lookup request (step 2).
3. The loop (step 9) parses the `arguments` string, validates it, and calls `lookup`. Inside `lookup` the data flows through steps 3 → 4 → 5 → 6: district name → district id → current profile → corrected profile → value, unit and source.
4. The loop sends the lookup result back to the model as a tool message with the same `tool_call_id`.
5. The model turns the verified facts into arithmetic expressions (step 7).
6. The loop (step 9) validates the expression and calls `calculate` (step 8), then sends the numeric result back with the same `tool_call_id`.
7. The model repeats steps 2 to 8 if it still needs facts or further calculations, up to the round limit.
8. The model compares the results and writes the final answer (step 10).

```
1 → 2 → [9 Loop: parse + validate] → 3 → 4 → 5 → 6 → facts back to model
      → 7 → [9 Loop: parse + validate] → 8 → numbers back to model → 10
```

The final answer must use this format:
ANSWER: <name or yes/no> | <number>

**What I am assuming:**

<!-- census year, archived profiles, corrections, units, where rounding happens, ... -->
Population figures come from the 2025 census unless the question explicitly requests another year. For growth questions the 2020 census figure is used as the starting point.
Budgets and household water usage refer to 2025 unless otherwise specified.
School enrollment figures refer to the 2025/26 academic year.
The water tariff is the 2025 tariff of 142.35 tenge per cubic metre, the same in every district (NR-15).
Archived profiles NR-13 and NR-14 must not replace the current district profiles. They are recognised by the word ARCHIVED in the title, never by guessing, and `lookup` never returns a value from them.
Correction notice NR-16 takes priority over NR-05 (NR-00: corrections take precedence over the profile they correct). Brightwater's correct area is 921.4 km². `lookup` reads the notice from the corpus and returns the corrected value with NR-16 as its source.
District names are matched exactly (ignoring upper and lower case), so Ossbridge and Ossford are treated as different districts. If a name is misspelled, `lookup` returns an error with suggestions and does not pick a district by itself.
Units are converted by the `lookup` tool, not by the model. Water use is always returned in megalitres. One megalitre equals 1,000 cubic metres, so Lindenmoor's 2,151,400 cubic metres (NR-08) becomes 2,151.4 megalitres, and the original figure is shown in a note.
For per-day calculations a year has 365 days (2025 is not a leap year), and one megalitre equals 1,000,000 litres.
Intermediate calculations should keep full precision. Rounding happens only when producing the final answer, using the precision requested by the question.
If a required fact is unavailable or an error cannot be resolved, the model should not invent a value.
The assumption my solution is most sensitive to is that the correction notice NR-16 is applied. Without it, Brightwater's area would be 912.4 km² and Q-09 would give 0.1 residents per km² instead of 0.6.

### A2 — The two tools

#### `lookup`

The `lookup` tool retrieves a specific fact about a district from the Nine Rivers Region documents. It uses current 2025 profiles, ignores archived profiles, and applies correction notices. It also converts units (water use is always returned in megalitres). Every successful result includes the source document ID, and every error includes an error code and a short message that the model can read and act on.

```json
{
  "type": "function",
  "function": {
    "name": "lookup",
    "description": "Find one specific fact about a Nine Rivers Region district or the regional water tariff. Use exact district names; if a name is misspelled the tool returns suggestions and you must call it again with the correct name. Returns the value, its unit, and the source document ID. Only current 2025 profiles are used: archived profiles are ignored and correction notices are applied (the source then names the notice). Water use is always returned in megalitres. Call this tool to get every number before using it in a calculation; never guess a figure.",
    "parameters": {
      "type": "object",
      "properties": {
        "district": {
          "type": "string",
          "description": "Exact district name, or 'region' for regional information such as water tariffs."
        },
        "field": {
          "type": "string",
          "description": "Requested field: population_2025, population_2020, area_km2, budget_million_tenge, water_megalitres, schools, pupils, roads_km, founded_year, or water_tariff_2025."
        }
      },
      "required": ["district", "field"],
      "additionalProperties": false
    }
  }
}
```

| Case | What the tool returns |
|---|---|
| Success | JSON containing `district`, `field`, `value`, `unit`, and `source`, for example `{"district":"Brightwater","field":"area_km2","value":921.4,"unit":"km2","source":"NR-16"}` |
| Unknown district | `{"error": "district_not_found", "message": "No matching district found"}` |
| Misspelled district | `{"error": "district_not_found", "message": "No district named Ossbrige; did you mean Ossbridge or Ossford?"}`: suggestions are given, but the tool never chooses one automatically |
| Ambiguous district | `{"error": "ambiguous_district", "message": "Multiple possible district matches", "candidates": [...]}` |
| Unknown field | `{"error": "field_not_found", "message": "The requested field is unavailable"}` |
| Archived profile | The current 2025 value is used instead of the archived value |
| Only an archived profile exists | `{"error": "no_current_profile", "message": "Only an archived profile exists for this district"}` |
| Corrected value | The corrected value is returned with the correction notice as its source |
| Water use in cubic metres (Lindenmoor) | Value converted to megalitres, with a `note` giving the original figure |
| Unreadable number | `{"error": "unreadable_value", "message": "The number could not be read from the profile"}` |
| Unknown unit | `{"error": "unknown_unit", "message": "The unit in the profile is not recognised"}` |
| Invalid arguments | `{"error": "invalid_arguments", "message": "District and field must be valid strings"}` |
| Document loading failure | `{"error": "data_error", "message": "Unable to read the corpus"}` |

**Worst thing it could do with strange or dangerous input:**

The model could provide extremely long strings, unknown field names, or misleading district names. Without validation, the tool might return the wrong fact or process unnecessary data. I will restrict input lengths, validate the field names against a fixed list, and search only the local corpus. The tool returns a single fact, never whole documents, and it reads only the one fixed corpus file, so it cannot be made to open arbitrary files or execute user-provided commands.

#### `calculate`

The `calculate` tool evaluates arithmetic expressions safely. It supports addition, subtraction, multiplication, division, parentheses, and unary plus/minus. It uses Python's `ast` module with an explicit allowlist of operations instead of `eval` or `exec`.

```json
{
  "type": "function",
  "function": {
    "name": "calculate",
    "description": "Safely calculate a numerical arithmetic expression using +, -, *, /, parentheses, and unary signs. Use this tool for all arithmetic: population density, percentages, growth rates, per-resident and per-day figures, financial comparisons, and differences. Exponentiation (**) is not supported. Do not send Python code, variable names, or function calls; write plain numbers, using the exact values returned by lookup without rounding them first. Returns the result or a clear error.",
    "parameters": {
      "type": "object",
      "properties": {
        "expression": {
          "type": "string",
          "description": "An arithmetic expression containing numeric constants, +, -, *, /, parentheses, and unary signs. Example: '44675 / 921.4'."
        }
      },
      "required": ["expression"],
      "additionalProperties": false
    }
  }
}
```

| Case | What the tool returns |
|---|---|
| Success | `{"result": 48.486}` for `44675 / 921.4` (a full-precision float; shortened here because this is a hand calculation) |
| Division by zero | `{"error": "division_by_zero", "message": "Cannot divide by zero"}` |
| Invalid expression | `{"error": "invalid_expression", "message": "Invalid arithmetic expression"}` |
| Python function call | `{"error": "unsafe_expression", "message": "Function calls are not allowed"}` |
| Attribute access | `{"error": "unsafe_expression", "message": "Attribute access is not allowed"}` |
| Variable or other names | `{"error": "unsafe_expression", "message": "Names are not allowed"}` |
| Non-numeric constant (string, boolean, None) | `{"error": "invalid_expression", "message": "Only numbers are allowed"}` |
| Exponentiation | `{"error": "unsafe_expression", "message": "Exponentiation is not allowed"}` |
| Excessively long input | `{"error": "expression_too_long", "message": "Expression exceeds the length limit"}` |
| Excessively large result | `{"error": "number_too_large", "message": "Result exceeds the allowed numeric range"}` |
| Non-finite result | `{"error": "invalid_result", "message": "Result must be finite"}` |
| Invalid arguments | `{"error": "invalid_arguments", "message": "Expression must be a non-empty string"}` |

**Worst thing it could do with strange or dangerous input:**

If arithmetic expressions were executed as Python code, the model could request file access, system commands, or expensive computations. I will parse expressions using `ast` and allow only numeric constants and approved arithmetic operators. Function calls, attributes, names, and exponentiation will be rejected, so inputs like `__import__('os').system('echo hi')`, `(1).__class__` and `9**9**9` are refused without being run. I will also limit expression length, AST depth, and numeric magnitude to reduce the risk of excessive CPU or memory usage.

### A3 — Q-09 by hand

**Question:** Which district has the higher population density in 2025, Brightwater or Millbrook, and by how many residents per square kilometre?

**Expected conversation between the model and the tools:**

```json
[
  {
    "role": "user",
    "content": "Which district has the higher population density in 2025, Brightwater or Millbrook, and by how many residents per square kilometre?"
  },
  {
    "role": "assistant",
    "tool_calls": [
      {
        "id": "call_01",
        "type": "function",
        "function": {
          "name": "lookup",
          "arguments": "{\"district\":\"Brightwater\",\"field\":\"population_2025\"}"
        }
      },
      {
        "id": "call_02",
        "type": "function",
        "function": {
          "name": "lookup",
          "arguments": "{\"district\":\"Brightwater\",\"field\":\"area_km2\"}"
        }
      },
      {
        "id": "call_03",
        "type": "function",
        "function": {
          "name": "lookup",
          "arguments": "{\"district\":\"Millbrook\",\"field\":\"population_2025\"}"
        }
      },
      {
        "id": "call_04",
        "type": "function",
        "function": {
          "name": "lookup",
          "arguments": "{\"district\":\"Millbrook\",\"field\":\"area_km2\"}"
        }
      }
    ]
  },
  {
    "role": "tool",
    "tool_call_id": "call_01",
    "content": "{\"district\":\"Brightwater\",\"field\":\"population_2025\",\"value\":44675,\"unit\":\"residents\",\"source\":\"NR-05\"}"
  },
  {
    "role": "tool",
    "tool_call_id": "call_02",
    "content": "{\"district\":\"Brightwater\",\"field\":\"area_km2\",\"value\":921.4,\"unit\":\"km2\",\"source\":\"NR-16\"}"
  },
  {
    "role": "tool",
    "tool_call_id": "call_03",
    "content": "{\"district\":\"Millbrook\",\"field\":\"population_2025\",\"value\":37203,\"unit\":\"residents\",\"source\":\"NR-11\"}"
  },
  {
    "role": "tool",
    "tool_call_id": "call_04",
    "content": "{\"district\":\"Millbrook\",\"field\":\"area_km2\",\"value\":758.6,\"unit\":\"km2\",\"source\":\"NR-11\"}"
  },
  {
    "role": "assistant",
    "tool_calls": [
      {
        "id": "call_05",
        "type": "function",
        "function": {
          "name": "calculate",
          "arguments": "{\"expression\":\"44675 / 921.4\"}"
        }
      },
      {
        "id": "call_06",
        "type": "function",
        "function": {
          "name": "calculate",
          "arguments": "{\"expression\":\"37203 / 758.6\"}"
        }
      }
    ]
  },
  {
    "role": "tool",
    "tool_call_id": "call_05",
    "content": "{\"result\":48.4859996}"
  },
  {
    "role": "tool",
    "tool_call_id": "call_06",
    "content": "{\"result\":49.0416557}"
  },
  {
    "role": "assistant",
    "tool_calls": [
      {
        "id": "call_07",
        "type": "function",
        "function": {
          "name": "calculate",
          "arguments": "{\"expression\":\"49.0416557 - 48.4859996\"}"
        }
      }
    ]
  },
  {
    "role": "tool",
    "tool_call_id": "call_07",
    "content": "{\"result\":0.5556561}"
  },
  {
    "role": "assistant",
    "content": "Millbrook has the higher population density in 2025. The difference is approximately 0.6 residents per square kilometre.\nANSWER: Millbrook | 0.6"
  }
]
```

**My arithmetic:**

Population density = population / area.

Brightwater:

- Population (2025): 44,675 residents (NR-05)
- Corrected area: 921.4 km² (NR-16)
- Density = 44,675 / 921.4 = 48.486 residents/km²

Millbrook:

- Population (2025): 37,203 residents (NR-11)
- Area: 758.6 km² (NR-11)
- Density = 37,203 / 758.6 = 49.042 residents/km²

Difference:

49.0417 - 48.4860 ≈ 0.5557

Rounded to one decimal place: 0.6 residents/km².

**Final answer:**

`ANSWER: Millbrook | 0.6`

The correction notice NR-16 matters. Without it, Brightwater's area would be taken as 912.4 km², its density would be about 48.964, and the difference from Millbrook would be about 0.077, which rounds to 0.1 instead of 0.6. The winner stays Millbrook, but the number is wrong.

### A4 — Why I split it this way

<!-- one other way to split the task, and why you did not choose it -->
I divided the task into two tools because finding facts and performing calculations are different operations.

The lookup tool is responsible for retrieving reliable information from the documents. It checks district names, ignores archived profiles, and applies corrections.

The calculate tool is responsible for arithmetic. It receives numerical expressions and evaluates them safely without executing arbitrary Python code.

An alternative design would be to create one large tool called answer_question, which receives the whole question and automatically searches the documents, performs calculations, and returns the final answer.

I did not choose this approach because it would be harder to test and debug. If the final answer was wrong, I would not easily know whether the problem came from document retrieval, unit conversion, or arithmetic.

With two separate tools, I can test each operation independently and inspect every tool call in the logs. This also allows the model to decide which facts and calculations are needed for each question.

The disadvantage is that the model may need several tool calls, increasing execution time and token usage. However, I think the additional transparency and control are worth this cost for this homework.

## Part B — Build it and run it (Medium)

### What I changed from Part A while coding

Part A itself is unchanged. These are the differences between the plan and the code:

1. **Three sentence templates, not two.** The 12 district profiles are written in three different sentence patterns (for example NR-01 "Founded in ... covers ...", NR-02 "has 14 schools, which enrolled ...", NR-03 "lies on ... and was founded in ..."). So `lookup` uses a list of regular expressions per field instead of one, and a test checks that every profile parses every field.
2. **Fixed list of fields.** In A2 I listed the fields in the tool description. In the code they are a fixed dictionary (`FIELDS`), and an unknown field returns `field_not_found` together with the list of available fields, so the model can correct itself.
3. **How corrections are applied.** In A1 I described step 5 in general terms. In the code the notice is parsed once from the corpus (a document whose title starts with "Correction"), and its value replaces the profile value. Right now only the `area_km2` pattern is implemented, because NR-16 is the only notice in the corpus. A different kind of notice would need a new pattern.
4. **Ambiguous names.** `ambiguous_district` is returned when the input is a prefix of more than one district (for example "Oss" matches Ossbridge and Ossford). A misspelled name such as "Ossbrige" returns `district_not_found` with up to three suggestions and never picks a district by itself.
5. **Answer precision in the prompt.** The model does not know how many decimals a question needs (the `decimals` field is not given to it). I added "at most 3 decimal places, no units, no thousands separators" to the shared answer-format rule, so that one parser can check all strategies.
6. **Water unit.** The conversion of Lindenmoor's cubic metres to megalitres is done inside `lookup`, as planned, and the result carries a `note` with the original figure.
7. **Region tariff.** `lookup("region", "water_tariff_2025")` reads NR-15. In A2 this was only mentioned in the description; the tests now cover it.
8. **Round limit.** `MAX_ROUNDS = 10` for S3. Part A did not fix a number. Q-09 needs about 3 to 4 rounds, so 10 leaves margin and still stops a runaway loop.
9. **Reasoning turned off.** The first S3 test failed with `Function tools with reasoning_effort are not supported for gpt-5.6-luna in /v1/chat/completions`. I set `reasoning_effort="none"` for all three strategies so that they stay comparable.
10. **S2 voting changed.** In my first version the five answers were voted on as exact (name, number) pairs. In a test on Q-09 the five numbers were all different, so the vote did nothing. Now I vote on the name and take the median number of the winning name.

### B2 — Tests

```text
(.venv) PS C:\Users\Asus\magzhanzhidekhan-hw4> python -m pytest -v
======================================================== test session starts =========================================================
platform win32 -- Python 3.12.1, pytest-9.1.1, pluggy-1.7.0 -- C:\Users\Asus\magzhanzhidekhan-hw4\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\Asus\magzhanzhidekhan-hw4
plugins: anyio-4.15.1
collected 28 items                                                                                                                    

tests/test_tools.py::test_lookup_correct_2025_number PASSED                                                                     [  3%]
tests/test_tools.py::test_lookup_misspelled_name_gives_suggestion_not_a_guess PASSED                                            [  7%]
tests/test_tools.py::test_lookup_similar_names_are_different_districts PASSED                                                   [ 10%]
tests/test_tools.py::test_lookup_ignores_archived_profile PASSED                                                                [ 14%]
tests/test_tools.py::test_lookup_applies_correction_notice PASSED                                                               [ 17%]
tests/test_tools.py::test_lookup_converts_cubic_metres_to_megalitres PASSED                                                     [ 21%]
tests/test_tools.py::test_lookup_unknown_field_and_bad_arguments PASSED                                                         [ 25%]
tests/test_tools.py::test_lookup_tariff PASSED                                                                                  [ 28%]
tests/test_tools.py::test_lookup_every_profile_parses_every_field[Ossbridge] PASSED                                             [ 32%]
tests/test_tools.py::test_lookup_every_profile_parses_every_field[Ossford] PASSED                                               [ 35%]
tests/test_tools.py::test_lookup_every_profile_parses_every_field[Tarnvale] PASSED                                              [ 39%]
tests/test_tools.py::test_lookup_every_profile_parses_every_field[Kelmarsh] PASSED                                              [ 42%]
tests/test_tools.py::test_lookup_every_profile_parses_every_field[Brightwater] PASSED                                           [ 46%]
tests/test_tools.py::test_lookup_every_profile_parses_every_field[Stonecairn] PASSED                                            [ 50%]
tests/test_tools.py::test_lookup_every_profile_parses_every_field[Harrowfield] PASSED                                           [ 53%]
tests/test_tools.py::test_lookup_every_profile_parses_every_field[Lindenmoor] PASSED                                            [ 57%]
tests/test_tools.py::test_lookup_every_profile_parses_every_field[Redfen] PASSED                                                [ 60%]
tests/test_tools.py::test_lookup_every_profile_parses_every_field[Ashgrove] PASSED                                              [ 64%]
tests/test_tools.py::test_lookup_every_profile_parses_every_field[Millbrook] PASSED                                             [ 67%]
tests/test_tools.py::test_lookup_every_profile_parses_every_field[Coldharbour] PASSED                                           [ 71%]
tests/test_tools.py::test_calculate_basic_multiplication PASSED                                                                 [ 75%]
tests/test_tools.py::test_calculate_division_and_precedence PASSED                                                              [ 78%]
tests/test_tools.py::test_calculate_division_by_zero PASSED                                                                     [ 82%]
tests/test_tools.py::test_calculate_refuses_dangerous_input[__import__('os').system('echo hi')] PASSED                          [ 85%]
tests/test_tools.py::test_calculate_refuses_dangerous_input[(1).__class__] PASSED                                               [ 89%]
tests/test_tools.py::test_calculate_refuses_dangerous_input[9**9**9] PASSED                                                     [ 92%]
tests/test_tools.py::test_calculate_refuses_names_strings_and_garbage PASSED                                                    [ 96%]
tests/test_tools.py::test_calculate_limits PASSED                                                                               [100%]

========================================================= 28 passed in 0.06s =========================================================
(.venv) PS C:\Users\Asus\magzhanzhidekhan-hw4> 
```

### B3 — The loop

- Round limit, and why: `MAX_ROUNDS = 10`. A typical two-district question needs about 3 to 4 rounds (one round of lookups, one or two rounds of calculations, one final answer), so 10 leaves a margin for retries after tool errors and still stops a runaway loop. A question that reaches the limit is marked unanswered and wrong.
- Where the logs are: `outputs/run<label>/logs/Q-xx.json` (one file per question for S3: every round, each tool call with its id, arguments, result and seconds). Summaries are in `outputs/run<label>/results_S1.json`, `results_S2.json`, `results_S3.json`.
- Real Q-09 conversation compared with my A3 version, what is different: (to be written after the runs, from `outputs/run1/logs/Q-09.json`)

### B4 — Three strategies

**What I kept the same:**

- Model `gpt-5.6-luna`, Chat Completions API, for all three strategies.
- `reasoning_effort="none"` in every call of every strategy. My first S3 test failed with an error: this model does not allow function tools when reasoning is on. I turned reasoning off everywhere (not only in S3), so the comparison stays fair. This also means the step-by-step thinking in S2 is written in the reply text and is not hidden.
- The same 20 questions from `data/questions.json`, in the same order. Only the question text is sent to the model; the correct answers are never in a prompt.
- The same answer-format rule in every prompt: end with `ANSWER: <name or yes/no> | <number>`, at most 3 decimal places, no units, no thousands separators. One parser and one checker score all three strategies.
- S1 and S2 use the same system prompt with all 17 documents. S2 only adds "Think step by step and show your calculation before the final line". S3 has no documents, only the two tools and an instruction to use them.
- S2: k = 5 samples, temperature 1.0, calls made one after another. The model accepted `temperature` (`temperature_rejected: false`). S1 and S3 use the default temperature.
- S2 voting: the vote is taken on the name (the most common name wins; if tied, the one seen first). The number is the median of the numbers given with that name. I first voted on the exact (name, number) pair, but this does not work: without a calculator the model gives slightly different numbers each time (for Q-09 I saw 0.568, 0.572, 0.573), so no two answers matched and the "vote" just picked the first sample.
- S3: `MAX_ROUNDS = 10`, the same `lookup` and `calculate` definitions as in Part A.
- Tokens are counted from the `usage` field of every call (all 5 samples in S2, every round in S3). Time is wall-clock seconds per question.
- Cost = input tokens × $1 per 1M + output tokens × $6 per 1M (GPT-5.6 Luna prices from the OpenAI pricing page, 20 Oct 2026). I did not apply cache discounts, so the real bill may be a bit lower, especially for S2, which sends the same documents 5 times.

**My rule for a correct answer** (written before the first full run):

An answer is correct if the name in the ANSWER line equals the expected name (ignoring upper and lower case, yes/no included) and the number differs from the expected `value` by at most 10^-decimals (one unit in the last digit of the expected number). A reply with no parseable ANSWER line, or an S3 question that hits the round limit, is counted as unanswered and as wrong. In S2 the five answers are voted on by name, and the number is the median of the numbers with the winning name.

| Run | Strategy | Correct /20 | Unanswered | Input tokens | Output tokens | Median seconds per question | Total seconds | Cost ($) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | S1 direct | 16 | 0 | 43,780 | 1,403 | 1.75 | 36.0 | 0.0522 |
| 1 | S2 think and vote (k = 5) | 15 | 0 | 220,200 | 11,966 | 9.06 | 181.2 | 0.2920 |
| 1 | S3 tools | 20 | 0 | 61,595 | 4,388 | 5.21 | 103.0 | 0.0879 |
| 2 | S1 direct | 12 | 0 | 43,780 | 1,421 | 1.85 | 37.2 | 0.0523 |
| 2 | S2 think and vote (k = 5) | 14 | 0 | 220,200 | 12,012 | 10.17 | 201.7 | 0.2923 |
| 2 | S3 tools | 19 | 0 | 58,814 | 4,439 | 6.08 | 114.0 | 0.0854 |

**Per question (run 1):**

| Question | S1 | S2 | S3 |
|---|:---:|:---:|:---:|
| Q-01 | ✓ | ✓ | ✓ |
| Q-02 | ✓ | ✓ | ✓ |
| Q-03 | ✓ | ✓ | ✓ |
| Q-04 | ✓ | ✓ | ✓ |
| Q-05 | ✗ | ✗ | ✓ |
| Q-06 | ✓ | ✓ | ✓ |
| Q-07 | ✓ | ✓ | ✓ |
| Q-08 | ✗ | ✓ | ✓ |
| Q-09 | ✓ | ✓ | ✓ |
| Q-10 | ✓ | ✓ | ✓ |
| Q-11 | ✓ | ✓ | ✓ |
| Q-12 | ✓ | ✓ | ✓ |
| Q-13 | ✓ | ✓ | ✓ |
| Q-14 | ✗ | ✓ | ✓ |
| Q-15 | ✓ | ✗ | ✓ |
| Q-16 | ✓ | ✓ | ✓ |
| Q-17 | ✓ | ✗ | ✓ |
| Q-18 | ✓ | ✗ | ✓ |
| Q-19 | ✓ | ✓ | ✓ |
| Q-20 | ✗ | ✗ | ✓ |

---

## Part C — Explain and choose (Hard)

### C1 — Does the tool description matter?

I re-ran S3 on five questions with the `lookup` description replaced by "Looks things up." (run `c1_vague`). "Calls" counts all tool calls (lookup and calculate).

| Question | Calls (your description) | Calls (vague) | Answer (yours) | Answer (vague) |
|---|---:|---:|---|---|
| Q-03 | 7 | 7 | lindenmoor 5.34 | lindenmoor 5.34 |
| Q-08 | 4 | 6 | brightwater 72.456 | brightwater 72.456 |
| Q-09 | 7 | 7 | millbrook 0.556 | millbrook 0.556 |
| Q-13 | 9 | 9 | coldharbour 4.159 | coldharbour 4.159 |
| Q-18 | 3 | 3 | yes 40013.391 | yes 40013.391 |

All five answers stayed correct and identical. The number of calls was the same on four questions. Only Q-08 changed: with the vague description the model made 6 calls instead of 4 (5 lookups instead of 3), so it asked for two extra facts. There were no tool errors in either version. The vague version used fewer input tokens in total (12,306 against 13,907), simply because the description is shorter and is sent on every round.

Why so little changed: my test only replaced the top-level description. The `field` parameter still lists all field names, the system prompt still tells the model to use `lookup` for every fact, and a wrong field returns the list of valid ones. So the model got the same guidance from other places. The result shows that the description is one of several sources of guidance, not that descriptions never matter. A stricter test, removing the field list from the schema and the prompt too, would be needed to see a real effect. Five questions is also a small sample: the extra calls on Q-08 could be random variation.

### C2 — Three mistakes explained

**S1, Q-05 (run 1): `Coldharbour | 14341.590`, expected 14235.**
Log (`results_S1.json`): "Stonecairn: 2,884.6 million ÷ 14,926 = 193,166.957 tenge per resident ... Coldharbour: 2,366.9 million ÷ 11,407 = 207,508.547". The model chose the right districts and figures, and its subtraction is consistent (207,508.547 − 193,166.957 = 14,341.590). The error is in the two divisions: the exact values are about 193,260 and 207,495. The reply also begins "Stonecairn had the larger 2025 budget per resident", the opposite of the final answer. With reasoning off, the model writes a conclusion first and computes afterwards. It has no mechanism that guarantees exact long division. It predicts digits one token at a time, so each division can be off by a small amount, and the answer only counts if the final difference is within the tolerance.

**S2, Q-15 (run 1): voted answer `Redfen | 17.973`, expected 17.61.**
Log (`results_S2.json`, `votes`): 17.973, 17.973, 17.609, 17.973, 18.336. Three of the five samples wrote "3,268 ÷ 11 = 296.727", but the correct value is 297.091. The vote therefore chose the wrong answer, because the same error was repeated. Voting reduces variance (errors that differ between samples cancel in the median), but it cannot remove a bias that most samples share. In Q-17 the samples were 888.493, 887.296, 881.5, 887.65 and 891.733. Here the problem is different: the spread is wider than the tolerance of ±1, so the median of five noisy answers is still 3 away. The cost was 220,200 input tokens for 20 questions, 5.0 times S1, because the documents are sent 5 times. Run 2 also got Q-15 wrong with 17.973.

**S3, Q-18 (run 2): `Millbrook | 40013.391`, expected `yes`.**
Log (`outputs/run2/logs/Q-18.json`): round 2 called `calculate` with `37203 * (1 + (37203 - 34590) / 34590)` and received 40013.391413703386. The final message says "Millbrook would exceed 40,000 residents in 2030" and ends with `ANSWER: Millbrook | 40013.391`. The number is exact because `calculate` is deterministic code. The mistake is in the name slot: the question asks both "will it exceed" and "give the population", and the model put the district name there. The tool removes arithmetic errors but not misunderstanding of the answer format. The same question was right in run 1, so this looks like a random slip, not a systematic failure. It is also partly my prompt's fault, because the format rule said "name or yes/no" without saying which one to use here.

**Why the loop needs several rounds, and why each round costs more.**
In Q-02 (run 1) the model made 4 lookups in round 1, then one `calculate` call in each of rounds 2, 3 and 4 (the growth of Tarnvale, the growth of Harrowfield, then their difference), and answered in round 5. The prompt tokens per round were 572, 850, 898, 947 and 1001 (total 4,268). Each round sends the whole conversation again, including all earlier tool calls and results, so the input grows. The first two calculations were independent and could have been sent together, and a single expression would have worked (as in Q-18, which took 3 rounds).

### C3 — Which strategy I would use, and what would change it

I would use **S3 (tools)**. It scored 20/20 and 19/20, against 16 and 12 for S1 and 15 and 14 for S2. It cost $0.0879 and $0.0854 per 20 questions: 1.7 times S1 ($0.052) but 3.3 times less than S2 ($0.292). Its median time was 5.2 and 6.1 s per question, between S1 (1.8 s) and S2 (9.1 and 10.2 s).

- **Why not S1:** it is the cheapest and fastest, but it scored 16 and then 12 out of 20. Its errors come from mental arithmetic (Q-05, Q-14, Q-20), and it sometimes states a conclusion before computing (Q-05).
- **Why not S2:** it is the most expensive (5.6 times S1) and the slowest, and it was no more accurate than S1 (15 and 14 against 16 and 12). Voting does not fix an error that most samples share (Q-15), or noise wider than the tolerance (Q-17, Q-20).

What would change my choice:
- **Small budget or strict time limit, and questions with no arithmetic** (like Q-10 or Q-06, which S1 got right in both runs): S1.
- **1,000 times more documents** (about 2.3 million tokens): S1 and S2 no longer fit in the prompt, so S3, with `lookup` using a search index.
- **Questions that need judgement over text, with no calculation:** S2, because voting reduces random variation and no calculator is needed.

### C4 — How sure I can be

- **Difference between my two runs:** S1 changed by 4 questions (16 and 12), S2 by 1 (15 and 14), S3 by 1 (20 and 19).
- **Is the gap between the best strategies bigger?** Yes for S3 against S2. The gap was 5 questions in both runs, larger than any run-to-run change except S1's. On the questions where only one of the two was right, S3 won 5 to 0 in both runs (sign test, p ≈ 0.06 each). Against S1 the gap was 4 in run 1, the same size as S1's own swing (sign test 4 to 0, p ≈ 0.125), and 8 in run 2 (8 to 1, p ≈ 0.04). S1 and S2 are within the noise of each other.
- **Limits:** the ranking S3 first is likely, but two runs of 20 questions are weak evidence. One question is 5 points. I used one model, one prompt wording and one temperature. My scoring rule is also lenient: Q-09 counts as correct for 0.571 (exact value 0.556) because the tolerance is 0.1, and it treats large numbers differently (Q-18 failed S2 at 40014.6, a gap of 0.004%). The lenient rule makes S1 and S2 look better than they are.
- **How many questions I would need:** S1 moved by 20 points between two runs, so I would want at least 100 questions and several runs per strategy to trust a gap of about 10 points (my estimate, not a calculation).

### Final questions

1. **What has run when a `tool_calls` message arrives?** Nothing. The message is only the model's request (a tool name and arguments as text). My code decides whether to run anything, and only then calls `lookup` or `calculate`.
2. **Why is `arguments` a string?** The model produces text, so the API passes the JSON as text. Passing it straight into my function gives a `str` where a `dict` is needed, and `lookup(**args)` fails with a `TypeError`. The model can also produce invalid JSON, so I use `json.loads` inside `try/except` and send an error back for that `tool_call_id`.
3. **Tokens added by the two definitions:** I measured 441 prompt tokens for a short request with the tools and 9 without, so the two definitions add 432 tokens. They are sent again on every round of every S3 question, so a 4-round question pays for them 4 times.
4. **How much more did S2 cost than S1?** About 5.6 times: $0.292 against $0.0522 in run 1 and $0.2923 against $0.0523 in run 2. Input tokens are 5.0 times higher (220,200 against 43,780) because the documents are sent 5 times. Output tokens are 8.5 times higher (11,966 against 1,403) because every sample writes out its reasoning.
5. **Question with the most rounds in S3:** Q-02 in run 1, 5 rounds (no question needed more than 4 in run 2). The model made 4 lookups in round 1, then sent the three calculations one per round (rounds 2-4) and answered in round 5. The first two calculations did not depend on each other, so they could have gone in one round, which shows that the number of rounds depends on how the model plans its calls, not only on the question. By number of tool calls, Q-20 and Q-11 were largest with 10 calls each in both runs, because they compare three districts.
6. **With 100,000 documents:** I would stop scanning the whole corpus with regular expressions on every call. I would build an index once (keyword search such as BM25, or embeddings), return only the top few passages, extract facts into a table when loading, and keep the source id in every result. I would also load archives and corrections as metadata, so they can be filtered before searching.
7. **What stops `calculate` from running dangerous code?** It parses with `ast` and evaluates only numbers, `+ - * /` and unary signs. Function calls, attributes, names and `**` are rejected before anything runs, and my tests cover `__import__('os').system('echo hi')`, `(1).__class__` and `9**9**9`. The model can still send a long expression (limited by length and result size) or choose a wrong formula, because the tool checks safety, not meaning.
8. **Where tools helped most and least:** most on multi-step arithmetic such as Q-05, Q-17 and Q-20, where S1 and S2 were wrong in at least one run and S3 was right in both. Least on simple questions like Q-10, Q-06 and Q-16, which all three strategies got right in both runs.
