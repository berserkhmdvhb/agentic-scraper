# Agents




The Agent layer (in `backend/scraper/agents/`) transforms raw HTML into structured output by selecting relevant fields and filling a JSON schema. The agent used is determined by the `AGENT_MODE` setting.

Each strategy is implemented as a self-contained module and shares a common interface.

---

## Agent Modes 

#### `rule_based` (baseline benchmark)

* Implements classic parsing with BeautifulSoup4.
* Uses heuristics (e.g., heading tags, price regex) to extract fields.
* No LLMs involved.
* **Fastest and most deterministic.**
* Good for simple product/job/blog pages.

#### `llm_fixed`

* Prompts OpenAI to extract a **predefined schema**: title, price, description, etc.
* Always expects these fields, even if they're not present in the page.
* Simple, schema-first design.
* Does not retry or adapt.

#### `llm_dynamic`

* Gives the LLM freedom to **choose relevant fields** based on the page content.
* Useful for heterogeneous or unknown page types.
* Adds minor prompt conditioning to bias field detection.

#### `llm_dynamic_adaptive`

* Builds on `llm_dynamic` by adding:

  * **Field coverage scoring** using `field_utils.py`
  * **Retry loop** up to `LLM_SCHEMA_RETRIES`
  * **Context hints**: page meta tags, URL segments, and expected field importance
* Selects the best result across multiple attempts.
* Enables **robust, schema-aware, self-healing extraction**.

Each agent returns a `ScrapedItem` that conforms to the schema and may include fallback values or nulls.

---


## 🧠 Adaptive Retry Logic (for LLM Agents)

Only the `llm-dynamic-adaptive` agent supports **field-aware retrying** when critical fields (e.g. `title`, `price`, `job_title`) are missing.

### How It Works:

1. Performs an initial LLM extraction attempt.
2. Evaluates field coverage using `field_utils.score_fields()`.
3. If important fields are missing, it re-prompts with hints and context.
4. Repeats up to `LLM_SCHEMA_RETRIES` times.
5. Returns the best-scoring result among attempts.

→ Enables **self-healing extraction** and **schema robustness** on diverse webpages.


---

## Diagrams



### LLM-dynamic

#### Flow Overview


```
[Page Text + URL + Context]
        |
        v
Generate Prompt → build_prompt()
        |
        v
Send to LLM with Retry → AsyncOpenAI().chat.completions.create()
        |
        v
Parse LLM Response → parse_llm_response()
        |
        v
Preprocess Output
- Normalize keys
- Inject metadata (URL)
- Detect unavailable fields
- Score field coverage
        |
        v
Normalize & Validate
- Convert types
- Add screenshot (optional)
- Schema validation
        |
        v
✅ Return ScrapedItem
or
❌ Return None (on failure)

```

### Flow Detailed

```
START: extract_structured_data()
    |
    v
Retry wrapper:
→ AsyncRetrying on OpenAIError (exponential backoff)
    |
    v
_call → _extract_impl()
    |
    v
Build dynamic prompt
→ build_prompt(text, url, context_hints)
    |
    v
Send message to LLM
→ client.chat.completions.create()
    |
    v
If response content is empty:
→ log warning, return None
    |
    v
Parse JSON content
→ parse_llm_response(content)
    |
    └── If parsing fails → return None
    |
    v
Post-processing:
→ normalize_keys(raw_data)
→ inject "url" into raw_data
→ detect_unavailable_fields()
→ score_nonempty_fields()
    |
    v
normalize_fields()
→ prepare for final schema validation
    |
    v
(Optional) capture_screenshot()
→ if successful: attach screenshot_path
    |
    v
Validate schema
→ try_validate_scraped_item(normalized)
    |
    ├─ Valid → return ScrapedItem ✅
    └─ Invalid → return None ❌
```

---

### LLM-dynamic-adaptive


#### Flow Overview


```
[LLM Response]
   |
   v
parse_llm_response()
→ Extract raw fields (unnormalized JSON)
   |
   v
Detect:
- non-empty fields
- missing required fields (based on page_type)
- explicitly unavailable fields ("N/A", "Not specified", etc.)
   |
   v
Evaluate:
- Is result valid? (try_validate_scraped_item)
- Is it complete? (no required fields missing)
- Should we exit early? (no new fields, no improvement)
   |
   v
If retry needed:
→ build_retry_or_fallback_prompt(best_fields, missing_fields)
→ add to ctx.messages for next LLM call
   |
   v
After all retries:
→ Choose best_valid_item or best_fields
   |
   v
normalize_fields()  (applied once to final candidate)
   |
   v
validate with ScrapedItem schema → ✅ final structured output

```

#### Flow Detailed

```
START: extract_adaptive_data()
    |
    v
Build initial prompt
→ build_prompt(text, context_hints)
    |
    v
LLM Call (Attempt 1)
→ run_llm_with_retries(messages = initial system + user)
    |
    v
Parse LLM response
→ parse_llm_response(content) → raw_data
    |
    v
Evaluate raw_data:
→ extract non-empty fields, detect placeholders ("N/A", "Not specified")
→ get missing required fields (get_required_fields(page_type) - seen - unavailable)
    |
    v
Validate structured item
→ try_validate_scraped_item(normalized raw_data) → item (valid or None)
    |
    v
Score fields and update context
→ score_and_log_fields()
→ update best_fields, best_valid_item, all_fields
    |
    v
Is item valid AND no required fields missing AND discovery not yet done?
    |
    ├─ Yes ─► Trigger 1 final discovery retry (to explore optional fields)
    |          |
    |          v
    |     LLM Call (Discovery Retry)
    |     → with previous messages (no prompt change)
    |          |
    |          v
    |     Parse, score, validate again → continue
    |
    v
Should exit early?
→ should_exit_early(): No new fields + no missing fields filled?
    |
    ├─ Yes ─► RETURN best_valid_item ✅
    |
    └─ No
        |
        v
    Build retry prompt
    → build_retry_or_fallback_prompt(best_fields, missing_fields)
        |
        v
    Update ctx.messages:
    → [system, last assistant, new retry prompt]
        |
        v
    LLM Call Retry N
    → run_llm_with_retries(ctx.messages)
        |
        v
    Parse, score, validate again
        |
        v
    Update context if improved
    → best_valid_item, best_fields, all_fields
        |
        v
    Are max retries reached?
        |
        ├─ Yes ─► handle_fallback()
        |           |
        |           ├─ Try best_valid_item ✅
        |           └─ Else try best_fields → validate again
        |
        └─ No ─► loop: Build next retry prompt

```



