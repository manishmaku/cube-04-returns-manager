# Cube Buildathon · 04 · Returns Manager

**Round 2 · Individual Build**

> Five agents, one unit, one record that follows it.
> A physical product arrives, gets prepped, gets shipped, comes back. At every step a fast operational judgment has to be made and recorded.

**New here? Read these first:**

1. [`GITHUB-GUIDE.md`](GITHUB-GUIDE.md) explains how to fork the repository, set it up, build and push your work.
2. [`RULES.md`](RULES.md) covers the repository and engineering rules.

---

## Your problem statement: Returns Manager

|                              |                                       |
| ---------------------------- | ------------------------------------- |
| **Position in the chain**    | Step 4 of 5 · Customer return         |
| **Customer**                 | Seller, or prep center acting for one |
| **What gets recorded**       | Condition and disposition             |
| **Who consumes your output** | Recovery Manager                      |

Someone opens a returned parcel. In a few seconds they need to decide:

* Is this the item we sold?
* Is it complete?
* What condition is it in?
* What should happen to it next?

Your agent should make that process structured, consistent and evidence-backed.

### What the agent returns

From appropriate visual/input evidence, the Returns Manager should determine:

* **Identity** against the seller's own catalogue. Is this the ASIN/SKU that was ordered?
* **Completeness** against the expected parts list: accessories, manuals, cables and other required components.
* **Condition** using the published condition scale. Do not invent your own condition scale.
* **Disposition**, such as `restock`, `refurbish`, `liquidate`, `dispose` or `pending_review`.

> Moving even a few percent of returns from liquidation to restock is direct margin. That is the commercial case in one sentence.

---

## The chain you are part of

```text
 Supplier delivery      Inbound to Amazon     Outbound to buyer     Customer return        Money back
 ┌──────────────┐      ┌──────────────┐      ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
 │ 01 Receiving │ ───▶ │ 02 Prep      │ ───▶ │ 03 Pack      │ ───▶ │ 04 Returns   │ ───▶ │ 05 Recovery  │
 │ condition on │      │ compliance   │      │ contents at  │      │ condition &  │      │ reads all    │
 │ arrival      │      │ proof        │      │ seal         │      │ disposition  │      │ four → claim │
 └──────────────┘      └──────────────┘      └──────────────┘      └──────────────┘      └──────────────┘
```

The first four Managers generate operational evidence. Recovery Manager consumes those records downstream.

Your output should therefore be structured, traceable and usable by the next stage.

---

## Reference data

`data/` contains **synthetic** reference data for development and testing. See [`data/README.md`](data/README.md) for the field definitions.

The SKUs, ASINs, FNSKUs, orders, suppliers, operators and amounts are invented. Requirement flags and fee amounts are **not** authoritative Amazon rules or fees.

The `photo_refs` values are placeholders, and images are not included with this repository. Create or use appropriate fixtures for development and evaluation.

All five Buildathon repositories share the same conceptual `unit_id` values, allowing a unit to be followed through the operational chain.

---

## How to build

This is an **individual Round 2 build**.

### Your workflow

```text
Fork
  ↓
Clone
  ↓
Understand the problem
  ↓
Build
  ↓
Test
  ↓
Evaluate
  ↓
Document
  ↓
Deploy / Demo
  ↓
Submit
```

Build your solution in **your own fork** of this repository.

You do not need to create a participant folder in the organiser repository or open a pull request into the organiser repository.

### Running the Foundation Locally (Phase 1)

1. **Set up virtual environment:**
   ```sh
   python -m venv .venv
   # On Windows:
   .\.venv\Scripts\activate
   # On Linux/macOS:
   source .venv/bin/activate
   ```

2. **Install dependencies:**
   ```sh
   pip install -r requirements.txt
   ```

3. **Configure environment:**
   ```sh
   cp .env.example .env
   ```

4. **Run the test suite:**
   ```sh
   pytest -v
   ```

5. **Start the FastAPI backend:**
   ```sh
   uvicorn src.main:app --reload --port 8000
   ```

6. **Verify health & agent endpoints:**
   * Health check: `GET http://localhost:8000/health`
   * Interactive API docs: `http://localhost:8000/docs`
   * Main operation: `POST http://localhost:8000/agent`

### Phase 2: Multimodal Vision Pipeline Setup

1. **Configure Gemini API Key:**
   Add your Gemini API key in `.env`:
   ```sh
   GEMINI_API_KEY=your_actual_gemini_api_key
   GEMINI_MODEL=gemini-2.5-flash
   ```

2. **Image Input Format:**
   Images can be provided directly via `POST /agent` as base64-encoded strings (JPEG, PNG, WEBP, GIF) or local file paths:
   ```json
   {
     "organization_id": "org_demo_alpha",
     "unit_id": "UNIT-0003",
     "order_id": "ORD-DUMMY-50003",
     "ordered_sku": "SKU-PUZZLE-500",
     "ordered_asin": "B0DUMMY729",
     "parts_list": ["puzzle pieces", "poster"],
     "operator_id": "op_chen",
     "images": [
       {
         "filename": "parcel_overview.jpg",
         "content_type": "image/jpeg",
         "data": "<base64_encoded_jpeg>"
       }
     ]
   }
   ```

3. **Conservative Uncertainty Handling (RULES.md §2.3 & §2.4):**
   * **First-Class UNCERTAIN:** When photographs are obscured, accessories cannot be confirmed, or markings are unreadable, checks output `UNCERTAIN` and the parcel routes to `pending_review`.
   * **Fail Open:** If `GEMINI_API_KEY` is not configured, or if the vision API encounters a network timeout, the system does not crash or fabricate decisions. It records a structured evidence record with `UNCERTAIN` verdicts, `pending_review` disposition, and documents the failure reason for human review.

---

## What you should focus on

Your Returns Manager should be able to:

```text
Input / Return Evidence
        ↓
     Identity
        ↓
   Completeness
        ↓
     Condition
        ↓
    Disposition
        ↓
Structured Evidence Record
```

The exact internal architecture is up to you.

Focus on making the core workflow work reliably before adding unnecessary features.

A worked Returns example may be available in the repository resources. **Read it to understand the expected standard. Do not simply copy it.**

---

## Evidence & Decision Traceability

Your agent should produce structured evidence for its decisions.

The official evidence contract includes concepts such as:

* `record_id`
* `schema_version`
* `organization_id`
* `client_id`
* `agent`
* `subject`
* `captured_at`
* `operator_label`
* `images`
* `checks`
* `outcome`
* `overrides`
* `status`

Each check should make the result understandable through its verdict, confidence and supporting detail where applicable.

Use:

* **PASS** when the evidence supports the condition.
* **FAIL** when the evidence supports that the condition is not met.
* **UNCERTAIN** when the evidence is insufficient for a reliable judgment.

`UNCERTAIN` is a valid outcome. Do not force ambiguous cases into PASS or FAIL.

---

## Cross-Manager Compatibility

Round 2 is individual, but your output will eventually be consumed by Recovery Manager.

Use the **official evidence contract provided by the organisers** as the baseline for interoperability.

Do not create a separate negotiated cross-pod contract for Round 2.

Your decision should allow another system to understand:

```text
What was returned?
      ↓
What was checked?
      ↓
What did the agent decide?
      ↓
Why?
      ↓
What evidence supports it?
```

---

## Engineering expectations

Keep the system practical and reliable.

### Tenancy isolation

If you store persistent data, organisation/client data should remain properly isolated.

### Efficient model usage

Avoid unnecessary repeated model calls. Batch related reasoning where appropriate.

### Fail open

If a model or dependency fails, do not silently discard the input. Preserve the available information and move the case into an appropriate pending/review state.

### Authoritative rules

Where an external rule or requirement is needed, use the authoritative source rather than relying on model memory or synthetic sample values.

---

## Evaluation

Evaluation is part of your Round 2 score.

For the visual checks, build an appropriate unseen/held-out evaluation set. Where applicable, use at least **50 unseen units** and have two humans independently label the cases before comparing agent performance.

Report:

* results per important check,
* false positives,
* false negatives,
* `UNCERTAIN` / review rate,
* important failure modes,
* latency/cost where relevant.

Do not evaluate only on examples that make the system look successful.

For condition and other visual checks, use genuinely varied cases, including difficult or ambiguous examples.

---

## Round 2 evaluation — 100 points

| Criterion                                    |  Points |
| -------------------------------------------- | ------: |
| Problem Understanding & Solution Relevance   |  **15** |
| Agent Functionality & Decision Quality       |  **25** |
| Evaluation, Accuracy & Uncertainty Handling  |  **25** |
| Evidence, Traceability & Engineering Quality |  **20** |
| UX, Demo & Documentation                     |  **15** |
| **TOTAL**                                    | **100** |

Your Round 2 score is important because participants selected for Round 3 will carry their Round 2 score into the final combined result.

---

## Submission

### Submissions open

**27 September 2026**

### Final deadline

**1 October 2026 · 6:00 PM IST**

The submission form closes permanently at the deadline.

**There is no reopening and no resubmission.**

Your final submission should include:

* your GitHub fork,
* working implementation,
* `README.md`,
* `ARCHITECTURE.md`,
* evaluation results,
* demo video,
* deployment URL where applicable,
* required submission links.

### LinkedIn — Mandatory

You must publish a LinkedIn post about your Round 2 build.

The post must:

* mention your Returns Manager build,
* explain what you built,
* tag **CodeQuesters**,
* tag **Sydon.AI**.

Include the LinkedIn post URL in the submission form.

The organisers will share the official LinkedIn post template separately.

---

## Commit rule

All code commits forming your Round 2 submission must be made during the authorised build phase.

Once the build phase ends, do not continue making Round 2 code changes.

---

## Final checklist

```text
[ ] Returns Manager implementation works
[ ] Working in my own fork
[ ] README.md complete
[ ] ARCHITECTURE.md complete
[ ] Identity tested
[ ] Completeness tested
[ ] Condition tested
[ ] Disposition tested
[ ] UNCERTAIN / review handling tested
[ ] Evidence trace implemented
[ ] Evaluation completed
[ ] Failure modes documented
[ ] Demo ready
[ ] LinkedIn post published
[ ] CodeQuesters tagged
[ ] Sydon.AI tagged
[ ] Submission links verified
[ ] Final submission ready before 1 October · 6:00 PM IST
```

> **Build → Test → Measure → Document → Publish → Submit**

---

**Cube Buildathon · 04 · Returns Manager**

**Round 2 · Individual Build**
