# HW4 — submission

**AI assistance:** <!-- what you used, and for what. "None" is an answer too. -->

---

## Part A — Plan on paper (Easy)

> Commit this whole part before any `.py` file exists.

### A1 — The steps

| # | Step | What goes in (types) | What comes out (types) | When it goes wrong | Tool, loop, or model? |
|---|---|---|---|---|---|
| 1 | Understand the question | Question (str)| District names, required fields, calculation goal (str, list[str])| If the question is unclear, request clarification or return unanswered| Model|
| 2 | Request facts | District name and field (str, str) | Tool call arguments (dict) | If required information is missing, request another lookup | Model |
| 3 | Look up current facts | District name and field (str, str) | Value, unit, document ID (dict) | Return an error for unknown or ambiguous names, missing fields, or invalid input | lookup tool |
| 4 | Validate sources | Matching documents and correction notices (list[dict]) | Current verified facts (dict) | Ignore archived profiles; apply corrections; report unresolved conflicts | lookup tool |
| 5 | Prepare calculations | Verified facts and units (dict) | Arithmetic expressions (str) | If units are incompatible or data is missing, do not calculate | Model |
| 6 | Calculate values | Arithmetic expression (str) | Numeric result or error (dict) | Reject invalid expressions, division by zero, unsafe operations, and excessively large calculations | calculate tool |
| 7 | Manage tool calls | Model tool calls and JSON arguments (list, str) | Tool results and updated conversation (list[dict]) | Return an error for malformed JSON; stop at the round limit | Loop |
| 8 | Compare and answer | Verified facts and calculated values (dict) | Final answer (str) | If the result cannot be determined, mark the question unanswered | Model |

**How the steps connect:**

<!-- which step feeds which: a list, an ASCII diagram, or an image committed to the repo -->
1. The model reads the question and identifies the districts and required fields.
2. The model requests the necessary facts using lookup.
3. The loop validates the tool arguments, executes lookup, and returns the results.
4. The lookup tool selects current documents, ignores archived profiles, and applies correction notices.
5. The model prepares arithmetic expressions using the verified facts.
6. The loop executes calculate and returns the numeric results.
7. The model compares the results and produces the final answer.

The final answer must use this format:
ANSWER: <name or yes/no> | <number>

**What I am assuming:**

<!-- census year, archived profiles, corrections, units, where rounding happens, ... -->
Population figures come from the 2025 census unless the question explicitly requests another year.
Budgets and household water usage refer to 2025 unless otherwise specified.
School enrollment figures refer to the 2025/26 academic year.
Archived profiles NR-13 and NR-14 must not replace the current district profiles.
Correction notice NR-16 takes priority over NR-05. Brightwater's correct area is 921.4 km².
District names must match exactly, so Ossbridge and Ossford are treated as different districts.
Units must be converted before calculations. One megalitre equals 1,000 cubic metres.
Intermediate calculations should keep full precision. Rounding happens only when producing the final answer, using the precision requested by the question.
If a required fact is unavailable or an error cannot be resolved, the model should not invent a value.

### A2 — The two tools

#### `lookup`

The `lookup` tool retrieves a specific fact about a district from the Nine Rivers Region documents. It uses current 2025 profiles, ignores archived profiles, and applies correction notices. Every successful result includes the source document ID.

```json
{
  "type": "function",
  "function": {
    "name": "lookup",
    "description": "Find a specific fact about a Nine Rivers Region district or the regional water tariff. Use exact district names. Return the value, unit, and source document ID. Prefer current 2025 data, ignore archived profiles, and apply correction notices. Call this tool before using numerical facts in calculations.",
    "parameters": {
      "type": "object",
      "properties": {
        "district": {
          "type": "string",
          "description": "Exact district name, or 'region' for regional information such as water tariffs."
        },
        "field": {
          "type": "string",
          "description": "Requested field, such as population_2025, population_2020, area_km2, budget_million_tenge, water_megalitres, schools, pupils, roads_km, founded_year, or water_tariff_2025."
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
| Success | JSON containing `district`, `field`, `value`, `unit`, and `source` |
| Unknown district | `{"error": "district_not_found", "message": "No matching district found"}` |
| Misspelled district | An error with possible district-name suggestions, without automatically choosing one |
| Ambiguous district | `{"error": "ambiguous_district", "message": "Multiple possible district matches"}` |
| Unknown field | `{"error": "field_not_found", "message": "The requested field is unavailable"}` |
| Archived profile | The current 2025 value is used instead of the archived value |
| Corrected value | The corrected value is returned with the correction notice as its source |
| Invalid arguments | `{"error": "invalid_arguments", "message": "District and field must be valid strings"}` |
| Document loading failure | `{"error": "data_error", "message": "Unable to read the corpus"}` |

**Worst thing it could do with strange or dangerous input:**

The model could provide extremely long strings, unknown field names, or misleading district names. Without validation, the tool might return the wrong fact or process unnecessary data. I will restrict input lengths, validate the field names, and search only the local corpus. The tool will not execute user-provided commands or access arbitrary files.

#### `calculate`

The `calculate` tool evaluates arithmetic expressions safely. It supports addition, subtraction, multiplication, division, parentheses, and unary plus/minus. It uses Python's `ast` module with an explicit allowlist of operations instead of `eval` or `exec`.

```json
{
  "type": "function",
  "function": {
    "name": "calculate",
    "description": "Safely calculate a numerical arithmetic expression using +, -, *, /, parentheses, and unary signs. Use this tool for population density, percentages, unit conversions, financial comparisons, and other arithmetic. Do not send Python code, variable names, or function calls. Return the calculated result or a clear error.",
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
| Success | `{"result": 48.48599956587801}` |
| Division by zero | `{"error": "division_by_zero", "message": "Cannot divide by zero"}` |
| Invalid expression | `{"error": "invalid_expression", "message": "Invalid arithmetic expression"}` |
| Python function call | `{"error": "unsafe_expression", "message": "Function calls are not allowed"}` |
| Attribute access | `{"error": "unsafe_expression", "message": "Attribute access is not allowed"}` |
| Exponentiation | `{"error": "unsafe_expression", "message": "Exponentiation is not allowed"}` |
| Excessively long input | `{"error": "expression_too_long", "message": "Expression exceeds the length limit"}` |
| Excessively large result | `{"error": "number_too_large", "message": "Result exceeds the allowed numeric range"}` |
| Non-finite result | `{"error": "invalid_result", "message": "Result must be finite"}` |

**Worst thing it could do with strange or dangerous input:**

If arithmetic expressions were executed as Python code, the model could request file access, system commands, or expensive computations. I will parse expressions using `ast` and allow only numeric constants and approved arithmetic operators. Function calls, attributes, names, and exponentiation will be rejected. I will also limit expression length, AST complexity, and numeric magnitude to reduce the risk of excessive CPU or memory usage.

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
    "content": "{\"result\":48.48599956587801}"
  },
  {
    "role": "tool",
    "tool_call_id": "call_06",
    "content": "{\"result\":49.041655681518584}"
  },
  {
    "role": "assistant",
    "tool_calls": [
      {
        "id": "call_07",
        "type": "function",
        "function": {
          "name": "calculate",
          "arguments": "{\"expression\":\"49.041655681518584 - 48.48599956587801\"}"
        }
      }
    ]
  },
  {
    "role": "tool",
    "tool_call_id": "call_07",
    "content": "{\"result\":0.5556561156405735}"
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

49.0416556815 - 48.4859995659 = 0.5556561156

Rounded to one decimal place: 0.6 residents/km².

**Final answer:**

`ANSWER: Millbrook | 0.6`

The correction notice NR-16 is essential. Without it, Brightwater's area would be incorrectly taken as 912.4 km², which could change the comparison result.

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

<!-- what changed in your plan, and why. "None" is an answer too. -->

### B2 — Tests

```text
<!-- pytest output -->
```

### B3 — The loop

- Round limit, and why:
- Where the logs are:
- Real Q-09 conversation compared with my A3 version, what is different:

### B4 — Three strategies

**What I kept the same:**

<!-- model, temperature, k, prompts, answer format, anything else -->

**My rule for a correct answer** (written before the first full run):

| Run | Strategy | Correct /20 | Unanswered | Input tokens | Output tokens | Median seconds per question | Total seconds | Cost ($) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | S1 direct | | | | | | | |
| 1 | S2 think and vote (k = ) | | | | | | | |
| 1 | S3 tools | | | | | | | |
| 2 | S1 direct | | | | | | | |
| 2 | S2 think and vote (k = ) | | | | | | | |
| 2 | S3 tools | | | | | | | |

**Per question (run 1):**

| Question | S1 | S2 | S3 |
|---|:---:|:---:|:---:|
| Q-01 | | | |
| Q-02 | | | |
| Q-03 | | | |
| Q-04 | | | |
| Q-05 | | | |
| Q-06 | | | |
| Q-07 | | | |
| Q-08 | | | |
| Q-09 | | | |
| Q-10 | | | |
| Q-11 | | | |
| Q-12 | | | |
| Q-13 | | | |
| Q-14 | | | |
| Q-15 | | | |
| Q-16 | | | |
| Q-17 | | | |
| Q-18 | | | |
| Q-19 | | | |
| Q-20 | | | |

---

## Part C — Explain and choose (Hard)

### C1 — Does the tool description matter?

| Question | Calls (your description) | Calls (vague) | Answer (yours) | Answer (vague) |
|---|---:|---:|---|---|
| | | | | |

### C2 — Three mistakes explained

### C3 — Which strategy I would use, and what would change it

### C4 — How sure I can be

### Final questions

1.
2.
3.
4.
5.
6.
7.
8.
