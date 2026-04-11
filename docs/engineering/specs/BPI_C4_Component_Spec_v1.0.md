# BRIDGEPOINT INTELLIGENCE INC.
## COMPONENT 4 — DISPUTE CLASSIFIER
## Build Specification v1.0
### Phase 1 Deliverable — Internal Use Only

**Date:** March 4, 2026
**Version:** 1.0
**Lead:** ARIA — ML & AI Engineering
**Support:** NOVA (ISO 20022 message schema), CIPHER (adversarial edge cases),
             REX (EU AI Act Art.13/17), LEX (claim language alignment)
**Status:** ACTIVE BUILD — training corpus required before fine-tuning
**Stealth Mode:** Active — Nothing External

---

## TABLE OF CONTENTS

1.  Purpose & Scope
2.  Why the Keyword Matcher Fails
3.  Why Llama-3 8B
4.  Classification Taxonomy
5.  Input Specification — What C4 Reads
6.  Model Architecture — Fine-Tuning with QLoRA
7.  Inference Quantization & Bank Container Deployment
8.  Training Corpus Specification
9.  Labeling Schema & Annotation Guide
10. The Negation Problem — Dedicated Test Suite
11. Multi-Language Handling
12. Training Pipeline
13. Retraining Pipeline (Quarterly)
14. Validation Requirements (Audit Gate 1.3)
15. Integration with Decision Flow
16. Known Limitations & Honest Ceiling
17. Audit Gate 1.3 Checklist

---

## 1. PURPOSE & SCOPE

C4 is a pre-offer hard gate. It runs before C1 or C2 are consulted
on any payment failure event. Its single responsibility: determine
whether the failed payment involves a genuine commercial dispute.

If yes: the bridge loan offer is HARD BLOCKED regardless of what C1
predicts about the payment failure probability. A disputed receivable
is not recoverable collateral. Funding a loan against a disputed
invoice is not a delayed payment — it is an uncollectible advance.

The current system uses a keyword matcher. Keyword matchers fail on
negation, paraphrase, tense, and multi-language input. The false
negative rate is approximately 8% — meaning roughly 1 in 12 genuinely
disputed payments slips through and receives a bridge loan offer.
Target: reduce FN rate to <2%.

C4 scope:
  - Pre-offer screening of pacs.002 RmtInf field and ancillary fields
  - 4-class classification with conservative hard block logic
  - On-device inference within bank container — zero cloud dependency
  - Dedicated negation test suite
  - Quarterly retraining pipeline

C4 does NOT:
  - Predict payment failure probability (C1)
  - Estimate credit risk (C2)
  - Perform AML screening (C6)
  - Make funding decisions (ELO / C7)

---

## 2. WHY THE KEYWORD MATCHER FAILS

The current keyword matcher searches for terms like "dispute",
"rejected", "goods not received", "claim" in the RmtInf field.
It fails in four documented patterns:

**Pattern 1 — Negation (most common failure mode):**
  "This payment is NOT related to any dispute"
  → Keyword matcher: hits "dispute" → hard block (false positive)
  → Correct: NOT_DISPUTE

  "No dispute — bank processing delay only"
  → Keyword matcher: hits "dispute" → hard block (false positive)
  → Correct: NOT_DISPUTE

**Pattern 2 — Paraphrase (second most common):**
  "Buyer returned merchandise citing quality concerns"
  → Keyword matcher: no hit → passes through (false negative)
  → Correct: DISPUTE_CONFIRMED

  "Sender has placed a hold pending invoice reconciliation"
  → Keyword matcher: no hit → passes through (false negative)
  → Correct: DISPUTE_POSSIBLE

**Pattern 3 — Tense (resolved disputes):**
  "Invoice dispute from March now resolved, please process payment"
  → Keyword matcher: hits "dispute" → hard block (false positive)
  → Correct: NOT_DISPUTE (past dispute, resolved)

**Pattern 4 — Multi-language:**
  "Disputa de factura pendiente de resolución" [Spanish — active dispute]
  → Keyword matcher: misses (searches English only) → false negative
  → Correct: DISPUTE_CONFIRMED

The 8% false negative rate measured on the current system is the
combined effect of Patterns 2 and 4 primarily. Patterns 1 and 3
inflate the false positive rate but do not directly cause loan losses
(they only block legitimate offers — a recoverable cost).

A false negative causes a loan to be funded against a disputed
receivable. Recovery probability on disputed receivables: near zero
in Pattern 2 (goods returned, contractual defense) and lower in
Pattern 4 (cross-jurisdiction enforcement). This is the loss event
C4 is specifically designed to prevent.

---

## 3. WHY LLAMA-3 8B

Alternatives considered:

| Model            | FN Risk | Size  | Deployment  | Negation | Selected |
|------------------|---------|-------|-------------|----------|----------|
| Keyword matcher  | ~8%     | 0MB   | Trivial     | Fails    | No       |
| Fine-tuned BERT  | ~3-4%   | 440MB | Easy        | Moderate | No       |
| Fine-tuned RoBERTa| ~2-3%  | 500MB | Easy        | Good     | Maybe    |
| Fine-tuned DeBERTa| ~2%    | 900MB | Moderate    | Strong   | Maybe    |
| Llama-3 8B QLoRA | <2%    | ~5GB  | Harder      | Excellent| YES      |
| GPT-4 API        | <1%    | N/A   | Cloud only  | Excellent| No       |

**Why not BERT/RoBERTa/DeBERTa:**
Encoder-only models are strong at classification but handle negation
and long-range context less reliably than decoder-only LLMs of
sufficient size. The 2% FN target is achievable with DeBERTa but
requires careful engineering. Llama-3 8B gives meaningful headroom
below 2% with less negation-specific engineering effort, at the
cost of a larger model footprint.

**Why not GPT-4 API:**
Zero cloud dependency is a hard constraint. Bank container deployment
requires all inference to be on-device behind the firewall. Any cloud
API call from the bank container is a security violation.

**Why Llama-3 specifically:**
- State-of-the-art instruction following at 8B parameter scale
- Strong multilingual capability (better than Llama-2 for non-English)
- LoRA fine-tuning well-characterized at this model size
- 4-bit GPTQ quantization well-supported: ~4.5GB footprint
- Active open-source ecosystem: llama.cpp, vLLM, Transformers all support it

Self-critique: The 5GB model footprint is large for a bank container.
If a bank partner specifies a tighter memory constraint (e.g., 4GB),
DeBERTa becomes the right answer. This spec documents Llama-3 8B as
the primary architecture with DeBERTa-v3-large as the stated fallback.
The fallback path must be implementable without redesigning C4's API.

---

## 4. CLASSIFICATION TAXONOMY

C4 outputs one of four classes per payment event:

```
Class 0: NOT_DISPUTE
  Definition: RmtInf content indicates an operational payment failure
              with no evidence of commercial dispute between buyer and seller.
  Examples:
    - "Bank processing delay — please retry"
    - "Incorrect routing number, resending"
    - "Compliance hold — pending AML review"
    - "Not a dispute — payment delayed by correspondent bank"
    - "Invoice 1234 fully accepted, payment delayed by FX desk"
  Action: Proceed to C1/C2 pipeline. Offer may be generated.

Class 1: DISPUTE_CONFIRMED
  Definition: Explicit or strongly implied commercial dispute between
              buyer and seller regarding the underlying transaction.
  Examples:
    - "Goods received damaged — payment withheld pending credit note"
    - "Invoice amount incorrect — dispute raised with supplier"
    - "Buyer rejected shipment — return in progress"
    - "Legal claim filed regarding contract breach"
    - "Factura rechazada por defectos en mercancía" [Spanish]
  Action: HARD BLOCK. No offer generated. Log with UETR.

Class 2: DISPUTE_POSSIBLE
  Definition: Ambiguous language that could indicate a commercial
              dispute but is not conclusive. Requires conservative handling.
  Examples:
    - "Payment held pending invoice reconciliation"
    - "Awaiting credit note before releasing payment"
    - "Minor discrepancy in delivered quantity under review"
    - "Payment on hold — awaiting clarification from buyer"
  Action: HARD BLOCK (conservative default).
          ELO operator may manually review and override.
          Override requires documented business reason.

Class 3: NEGOTIATION
  Definition: Active commercial negotiation or dispute in process of
              resolution. Prior dispute exists — resolution not confirmed.
  Examples:
    - "Partial payment — balance pending dispute resolution"
    - "Payment of agreed settlement amount for invoice 5678"
    - "Dispute from last quarter resolved, releasing 60% of invoice"
  Action: HARD BLOCK. Even partially resolved disputes have
          uncertain collateral. Do not offer on disputed amount.
```

### 4.1 Hard Block Logic

For the decision engine:
```
IF class == NOT_DISPUTE (0):
    dispute_block = false
    dispute_confidence = model_probability[class_0]
    proceed to C1/C2

IF class IN [DISPUTE_CONFIRMED, DISPUTE_POSSIBLE, NEGOTIATION]:
    dispute_block = true
    dispute_confidence = model_probability[predicted_class]
    hard_block_reason = class_label
    log DisputeBlockRecord {uetr, class, confidence, rmtinf_snippet, timestamp}
    DO NOT proceed to C1/C2
    return DisputeBlockResponse to Decision Engine
```

### 4.2 Why DISPUTE_POSSIBLE Is a Hard Block

There is a deliberate asymmetry here:
  - False positive cost: one legitimate bridge offer is blocked.
    The borrower is inconvenienced. Revenue opportunity lost.
    Borrower can request manual review if they believe it's wrong.
  - False negative cost: a loan is funded against a disputed receivable
    with near-zero recovery probability. Direct loss.

The asymmetry strongly favors false positives. DISPUTE_POSSIBLE
defaults to hard block. Banks can configure manual review for
Class 2 cases — but the system default must be conservative.

---

## 5. INPUT SPECIFICATION — WHAT C4 READS

### 5.1 Primary Input: RmtInf Field

Source: pacs.002 RJCT message
ISO 20022 field: `<RmtInf><Ustrd>` (unstructured remittance info)
  OR `<RmtInf><Strd>` (structured — extract narrative from AddtlRmtInf)
Max length: 140 characters (ISO 20022 Ustrd max)

Additional structured fields checked:
  - `<StsRsnInf><Rsn><Cd>`: rejection reason code (NARR, DISP, LEGL, CUTA)
  - `<StsRsnInf><AddtlInf>`: additional rejection information (free text)
  - `<OrgnlTxRef><RmtInf>`: remittance info from original transaction

### 5.2 Rejection Code Pre-Filter

Before invoking the LLM, apply a deterministic rejection code check:

```
HARD_BLOCK_CODES = {
  "DISP": DISPUTE_CONFIRMED,   // Explicit dispute indicator
  "LEGL": DISPUTE_CONFIRMED,   // Legal proceedings
}

DISPUTE_FLAG_CODES = {
  "NARR": DISPUTE_POSSIBLE,    // Narrative — escalate to LLM with flag
  "CUTA": DISPUTE_POSSIBLE,    // Customer request — escalate to LLM
}

PASS_THROUGH_CODES = {
  "AC01", "RC01", "AM04", "DS04",   // Formatting / liquidity — NOT dispute
  "MS03", "AG01", "RR04",           // Compliance / compliance — NOT dispute
  // ... all Class A/B/C operational codes
}
```

If rejection code is in HARD_BLOCK_CODES:
  → Immediate hard block without invoking LLM (saves latency)
  → class = DISPUTE_CONFIRMED, source = "rejection_code"

If rejection code is in PASS_THROUGH_CODES AND RmtInf is empty:
  → class = NOT_DISPUTE (operational failure, no dispute signal)
  → Do not invoke LLM (saves latency)

All other cases: invoke LLM with full context.

This pre-filter is expected to handle ~40-50% of payments without
invoking the LLM at all — critical for latency management.

### 5.3 Constructed Prompt

For the LLM invocation, a structured prompt is constructed:

```
SYSTEM:
You are a financial payment dispute classifier. Your task is to
determine whether a SWIFT payment message indicates a commercial
dispute between a buyer and seller.

Classify the following payment information into exactly one category:
  0 = NOT_DISPUTE: operational delay, bank issue, no buyer-seller conflict
  1 = DISPUTE_CONFIRMED: explicit commercial dispute about goods/services
  2 = DISPUTE_POSSIBLE: ambiguous — could be a dispute, unclear
  3 = NEGOTIATION: dispute exists but being resolved

Rules:
- Negation words (not, no, never) change the meaning — apply carefully
- Past tense disputes that are now resolved = NOT_DISPUTE
- Partial payments due to disputes = NEGOTIATION
- Bank processing issues = NOT_DISPUTE
- Compliance/regulatory holds = NOT_DISPUTE

Respond with ONLY a single digit: 0, 1, 2, or 3.

USER:
Rejection code: {rejection_code}
Rejection description: {rejection_code_description}
Remittance information: {rmtinf_text}
Additional info: {additional_info}

Classification:
```

Output: single token (one of "0", "1", "2", "3")
Only one token generated — this is what makes inference fast.
The model generates exactly one token and stops.

### 5.4 Input Length Budget

Total prompt length: ~200-300 tokens
  System prompt: ~150 tokens (fixed)
  User content: ~50-150 tokens (variable)

At 200-300 input tokens + 1 output token:
  Llama-3 8B GPTQ 4-bit on T4 GPU: ~15-25ms
  This is within the C4 latency budget.

---

## 6. MODEL ARCHITECTURE — FINE-TUNING WITH QLORA

### 6.1 Base Model

Model: meta-llama/Llama-3-8B-Instruct
  (Instruction-tuned variant — better instruction following than base)
  (Requires Meta Llama license — internal use only)

### 6.2 QLoRA Configuration

QLoRA = Quantized LoRA: base model loaded in 4-bit NF4 during
training to reduce GPU memory. LoRA adapters remain in BF16.

```
LoRA configuration:
  r (rank)         : 16
  lora_alpha       : 32   (scaling = alpha/r = 2.0)
  lora_dropout     : 0.1
  bias             : none
  task_type        : CAUSAL_LM

Target modules (which weight matrices receive LoRA adapters):
  q_proj, k_proj, v_proj, o_proj   // Attention projections
  gate_proj, up_proj, down_proj    // FFN projections
  (All linear layers — maximizes adaptation capacity for fine-tuning)

Trainable parameters: ~20M / 8B total = 0.25%
  This is the efficiency of LoRA — 99.75% of parameters frozen.
```

Base model quantization during training:
  - BitsAndBytesConfig: load_in_4bit=True, bnb_4bit_quant_type="nf4"
  - compute_dtype: bfloat16
  - Training GPU requirement: T4 16GB (sufficient for 8B at 4-bit)

### 6.3 Training Configuration

```
Framework: HuggingFace Transformers + PEFT + TRL (SFTTrainer)

Hyperparameters:
  max_seq_length   : 512    // More than enough for prompt + 1 output token
  per_device_batch : 4      // Per GPU
  gradient_accum   : 4      // Effective batch size = 16
  learning_rate    : 2e-4   // Standard QLoRA recommendation
  lr_scheduler     : cosine
  warmup_ratio     : 0.1
  num_train_epochs : 3      // With early stopping on val FN rate
  weight_decay     : 0.01
  optimizer        : paged_adamw_8bit  // Memory-efficient optimizer

Early stopping:
  Monitor: false_negative_rate on validation set
  Patience: 2 epochs
  Stop if: val FN rate < 1.5% (already exceeds target)
  Stop if: val FN rate not improving after 2 epochs

Loss:
  Standard next-token prediction loss on the output token only
  (Using output_only masking — loss computed only on "0"/"1"/"2"/"3")
```

### 6.4 Output Head Note

Llama-3 8B has a vocabulary of ~128K tokens. We constrain the output
to exactly 4 tokens: "0", "1", "2", "3".

At inference: logit_bias applied to force output to one of these 4
tokens. The probability distribution over just these 4 tokens
gives us the confidence score per class.

confidence = softmax(logits[[token_0, token_1, token_2, token_3]])
predicted_class = argmax(confidence)

This gives calibrated per-class probabilities without a separate
classification head — the generative model becomes a 4-way classifier.

---

## 7. INFERENCE QUANTIZATION & BANK CONTAINER DEPLOYMENT

### 7.1 Quantization Strategy

After fine-tuning: merge LoRA adapters into base model weights,
then quantize the merged model for deployment.

**Primary: GPTQ 4-bit (GPU deployment)**
  - Format: GPTQ (Generative Pre-trained Quantization)
  - Bits: 4
  - Group size: 128
  - Implementation: AutoGPTQ + vLLM or llama.cpp server
  - Approximate size: 4.5-5.0 GB
  - Inference latency on T4 GPU: 15-25ms for this prompt length
  - Memory requirement: 6GB GPU (4.5GB model + 1.5GB KV cache)

**Fallback: GGUF Q4_K_M (CPU deployment)**
  - Format: GGUF (for llama.cpp)
  - Quantization: Q4_K_M (4-bit with mixed precision in attention layers)
  - Approximate size: 4.7 GB
  - Inference latency on 4-core CPU: 50-80ms
  - Memory requirement: 6GB RAM
  - This fallback handles bank containers without GPU allocation

### 7.2 Bank Container Specification

C4 is deployed as a containerized microservice within bank infrastructure.

```
Container specification:
  Base image   : Python 3.11 + CUDA 12.1 (GPU) or Python 3.11 (CPU)
  RAM          : 8GB minimum
  GPU          : NVIDIA T4 or equivalent (GPU path)
               : None required (CPU fallback path)
  vCPU         : 4 cores minimum
  Storage      : 10GB (model weights + working space)

Exposed endpoint:
  POST /classify
  Request: DisputeClassifyRequest (Architecture Spec S4.5)
  Response: DisputeClassifyResponse (Architecture Spec S4.5)
  Timeout: 100ms (hard limit — if exceeded, return DISPUTE_POSSIBLE as safe default)

Network policy:
  INBOUND: only from MIPLO/Decision Engine (internal network only)
  OUTBOUND: NONE — zero external network calls
  Verified by: network isolation test (Audit Gate 1.3)
```

### 7.3 Timeout Safety Behavior

If inference exceeds 100ms (e.g., model loading delay, cold start):
  Return: class = DISPUTE_POSSIBLE (conservative fallback)
  Log: c4_timeout = true, rmtinf_snippet = first 50 chars
  Do NOT return NOT_DISPUTE on timeout — defaulting to "safe" means
  defaulting to "block" under uncertainty.

### 7.4 Model Loading

At container start: model loaded into GPU/CPU memory.
Cold start time: ~5-8 seconds for GPTQ load.
This is acceptable — containers stay warm in production.
First request after cold start: add 5-8s (handled by container
readiness probe, not customer-facing).

---

## 8. TRAINING CORPUS SPECIFICATION

### 8.1 The Core Challenge

This is the hardest part of C4. 50,000 labeled SWIFT RmtInf
messages is a substantial data collection effort. This corpus
does not exist publicly. It must be sourced, generated, or
constructed specifically for this project.

The spec defines exactly what is needed so that when the
data sourcing effort begins, the requirements are unambiguous.

### 8.2 Corpus Size Target

Minimum: 50,000 labeled examples
Target: 100,000 labeled examples (for robust minority class coverage)

Class distribution target:
  Class 0 (NOT_DISPUTE)    : ~55% of corpus (dominant class)
  Class 1 (DISPUTE_CONFIRMED): ~20% of corpus
  Class 2 (DISPUTE_POSSIBLE) : ~15% of corpus
  Class 3 (NEGOTIATION)    : ~10% of corpus

Rationale: over-representing dispute classes vs. their natural rate
(which is much lower) prevents the model from being biased toward
NOT_DISPUTE. This is intentional — we want high recall on disputes.

### 8.3 Data Sources (Priority Order)

**Source A — Bank partner historical data (preferred):**
  Partner bank provides historical pacs.002/pain.002 messages
  with human-labeled dispute outcomes (was this payment ultimately
  disputed? was it recovered?). Gold standard labels.
  Requirement: Data Processing Agreement, GDPR Art.28 compliance.
  PII handling: all entity names, account numbers removed.
  Retain: RmtInf text, rejection code, outcome label only.

**Source B — Synthetic generation (bridge until Source A available):**
  Generate synthetic RmtInf messages covering all class types.
  Use a capable LLM (internal, not cloud) to generate varied examples:
    - Multiple phrasings per dispute type
    - Multiple languages (English 60%, German 15%, French 10%,
      Spanish 10%, other 5%)
    - Multiple negation patterns
    - Multiple tense variations (current vs. resolved disputes)
  Human review of 10% sample to validate generation quality.
  Label quality: acceptable for initial training, lower than Source A.

**Source C — Trade finance legal case descriptions:**
  Published trade finance dispute case summaries (public domain).
  Extract dispute language patterns. Useful for Class 1 and 3.
  Volume: limited (~2,000-5,000 examples max from public sources).
  Label quality: high for dispute classes, no NOT_DISPUTE examples.

**Source D — SWIFT published datasets:**
  SWIFT Innotribe and SWIFTRef publish some payment data samples.
  Check for any publicly available RmtInf corpora.
  Volume: likely very limited for this specific use case.

**Corpus composition for initial training:**
  If Source A not yet available: Source B (40K) + Source C (5K) + Source D (5K)
  Once Source A available: retrain with Source A dominant (>60% of corpus)

### 8.4 Dataset Schema

```
CorpusRecord {
  record_id           : string
  rmtinf_text         : string    // Raw RmtInf content (de-identified)
  rejection_code      : string    // SWIFT reason code (or "NONE" if absent)
  additional_info     : string    // Additional message text (de-identified)
  language            : string    // ISO 639-1 language code
  source              : string    // A, B, C, or D
  label               : int       // 0, 1, 2, or 3
  label_confidence    : string    // "certain", "probable", "uncertain"
  annotator_id        : string    // For inter-annotator agreement tracking
  contains_negation   : bool      // Tag for negation test suite assembly
  contains_tense_shift: bool      // Tag for past-dispute cases
  language_non_english: bool      // Tag for multilingual test
}
```

### 8.5 Labeling Difficulty Tiers

Not all examples are equally straightforward to label. Three tiers:

**Tier I — Clear cases (can be labeled by rule/template):**
  - Explicit dispute keywords: DISPUTE_CONFIRMED
  - Explicit operational codes + empty RmtInf: NOT_DISPUTE
  - ~50% of corpus

**Tier II — Requires linguistic judgment:**
  - Negation patterns, paraphrase, tense
  - Need annotator with trade finance domain knowledge
  - ~35% of corpus

**Tier III — Requires trade finance expertise:**
  - Ambiguous legal language, jurisdiction-specific terms
  - "Pending credit note" (is this a dispute or routine adjustment?)
  - ~15% of corpus

Inter-annotator agreement (IAA) target: κ (Cohen's Kappa) ≥ 0.80
If IAA < 0.70 on Tier III: escalate to domain expert review.
All Tier III disagreements documented in annotation log.

---

## 9. LABELING SCHEMA & ANNOTATION GUIDE

### 9.1 Decision Tree for Annotators

```
Is the rejection caused by a BANK or NETWORK issue (not buyer-seller)?
  YES → NOT_DISPUTE (0)
  NO  → continue

Does the message contain explicit dispute language (dispute, reject,
  defect, claim, breach, returned goods, quantity short)?
  YES → Check for negation:
        Is the dispute explicitly negated or in past tense?
          YES → NOT_DISPUTE (0)
          NO  → DISPUTE_CONFIRMED (1)
  NO  → continue

Is the payment held "pending" something (reconciliation, credit note,
  clarification, review)?
  YES → DISPUTE_POSSIBLE (2)
  NO  → continue

Does the message describe a partial payment or ongoing resolution
  of a prior dispute?
  YES → NEGOTIATION (3)
  NO  → NOT_DISPUTE (0)
```

### 9.2 Negation Handling Rules for Annotators

Negation patterns that flip the label to NOT_DISPUTE:
  - "NOT a dispute"
  - "no dispute"
  - "dispute resolved / has been resolved / was resolved"
  - "no longer disputed"
  - "payment NOT held due to dispute"
  - "previously disputed — now accepted"

Negation patterns that do NOT flip to NOT_DISPUTE:
  - "undisputed amount" followed by "disputed balance" → NEGOTIATION
  - "dispute not yet resolved" → DISPUTE_CONFIRMED (still active)
  - "no agreement reached" → DISPUTE_CONFIRMED

### 9.3 Special Cases

**Invoice reconciliation without explicit dispute language:**
  "Awaiting invoice reconciliation before payment" → DISPUTE_POSSIBLE
  "Routine end-of-quarter reconciliation" → NOT_DISPUTE
  Key distinction: "awaiting" (payment withheld) vs "routine"

**Partial payments:**
  "Partial payment, balance withheld" → NEGOTIATION
  "Partial payment due to FX shortfall" → NOT_DISPUTE
  Key distinction: commercial reason vs operational reason

**Legal / regulatory language:**
  "Legal hold per court order" → DISPUTE_CONFIRMED (Class 1)
  "Regulatory compliance hold" → NOT_DISPUTE (operational)
  "Sanctions screening hold" → NOT_DISPUTE (C6 handles this)

---

## 10. THE NEGATION PROBLEM — DEDICATED TEST SUITE

### 10.1 Why Negation Gets Its Own Section

The keyword matcher's 8% FN rate is primarily caused by:
  1. Paraphrase (Pattern 2): ~60% of false negatives
  2. Multi-language (Pattern 4): ~25% of false negatives
  3. Tense (Pattern 3): ~10% of false negatives
  4. Other: ~5%

But the keyword matcher's FALSE POSITIVE rate is primarily caused by:
  1. Negation (Pattern 1): ~70% of false positives

False positives block legitimate offers. At scale, if 5% of all
payment failures have "dispute" mentioned in their RmtInf in a
negating context, blocking all of them is a significant revenue loss.
Negation handling is critical for both false positive and false
negative control.

### 10.2 Negation Test Suite — Required Cases

500 manually constructed test cases specifically for negation.
These are NOT in the training set — held out for evaluation only.

```
Category A: Simple negation (100 cases)
  Pattern: "NOT/NO/NEVER + dispute-related term"
  Expected: all NOT_DISPUTE (0)
  Examples:
    "Not a dispute — bank error in routing"
    "No goods dispute — processing delay only"
    "Payment is not related to any invoice dispute"
    "This is not a commercial dispute"

Category B: Past-tense resolution (100 cases)
  Pattern: dispute mentioned but in past tense + resolved
  Expected: all NOT_DISPUTE (0)
  Examples:
    "Invoice dispute from Q3 now resolved, releasing payment"
    "Dispute was settled last month — final payment follows"
    "Previously held due to dispute — now cleared"

Category C: Active disputes with explicit language (100 cases)
  Pattern: clear dispute language, no negation
  Expected: all DISPUTE_CONFIRMED (1)
  Examples:
    "Payment withheld — goods arrived damaged"
    "Buyer disputes invoice amount — credit note requested"
    "Merchandise returned due to quality failure"

Category D: Negation with residual dispute (100 cases)
  Pattern: partial negation — dispute exists but in specific form
  Expected: DISPUTE_POSSIBLE (2) or NEGOTIATION (3)
  Examples:
    "Not a full dispute — partial rejection of goods only"
    "Dispute not covering full invoice amount"
    "No formal dispute but buyer requesting adjustment"

Category E: Double negation and complex syntax (100 cases)
  Pattern: complex sentence structures
  Expected: mix of classes
  Examples:
    "Not accepting payment — not because of dispute but bank error"
      → NOT_DISPUTE (bank error, not commercial)
    "Payment cannot be released — dispute unresolved"
      → DISPUTE_CONFIRMED (double negative effectively = active dispute)
    "No payment will be made without dispute resolution"
      → DISPUTE_CONFIRMED (conditional on dispute)
```

### 10.3 Test Suite Metrics

Negation test suite pass criteria:
  - Category A FP rate: < 5% (must correctly identify as NOT_DISPUTE)
  - Category B FP rate: < 5%
  - Category C FN rate: < 2% (must correctly flag as DISPUTE)
  - Category D accuracy: > 80% (ambiguous — acceptable range)
  - Category E accuracy: > 75% (complex — acceptable range)

If Category A or B FP rate > 10%: model is over-triggering on
dispute keywords regardless of negation. Increase negation examples
in training data and retrain.

---

## 11. MULTI-LANGUAGE HANDLING

### 11.1 Language Coverage

Llama-3 8B Instruct has strong multilingual capabilities, particularly
for high-resource languages. Language coverage in training corpus:

  English     : 60% of corpus (primary deployment language)
  German      : 15% (significant SEPA corridor volume)
  French      : 10% (francophone Africa corridors)
  Spanish     : 10% (Latin America corridors)
  Other       :  5% (Dutch, Italian, Portuguese, Mandarin romanized)

### 11.2 Language Detection

Before constructing the prompt, detect the language of the RmtInf field.
Use: langdetect library (lightweight, no network call).
If detected language is in {English, German, French, Spanish}: proceed.
If detected language is OTHER:
  - Proceed with inference (Llama-3 has some capability)
  - Set: non_primary_language = true in DisputeClassifyResponse
  - Confidence threshold lowered: if max_class_probability < 0.70,
    return DISPUTE_POSSIBLE as conservative fallback

### 11.3 Non-English Test Coverage

Test suite must include 50 non-English examples per language
(German, French, Spanish) covering all 4 classes.
Minimum per-language accuracy: 80% (lower than English target
because training data is English-dominant).

---

## 12. TRAINING PIPELINE

```
Stage 1: Corpus Validation
  - Schema check: all required fields present
  - Label distribution check: report count per class
  - Language distribution check
  - IAA score computed and logged
  - Negation / tense_shift / non_english tag counts logged
  - No duplicate record_ids

Stage 2: Train/Val/Test Split
  IMPORTANT: split must preserve:
    - Class stratification (each split has same class distribution)
    - Language stratification
    - Negation/non-negation balance
  Splits: 70% train, 15% validation, 15% test
  Negation test suite (500 cases): SEPARATE held-out set
    NOT included in any of train/val/test

Stage 3: Prompt Construction
  Build prompt for each record as per Section 5.3
  Tokenize: measure actual token lengths, ensure < 512 max_seq_length
  If any prompt > 512 tokens: truncate RmtInf text from the right

Stage 4: QLoRA Fine-Tuning
  Load Llama-3 8B Instruct in 4-bit NF4
  Apply LoRA adapters per Section 6.2
  Train with SFTTrainer
  Log: train loss, val FN rate per epoch
  Save checkpoint at best val FN rate

Stage 5: Post-Training Quantization
  Merge LoRA adapters into base model
  Quantize to GPTQ 4-bit (primary)
  Quantize to GGUF Q4_K_M (fallback)
  Verify model sizes match targets

Stage 6: Validation (OOT test set)
  FN rate: primary metric
  Per-class precision/recall
  Confidence calibration: is max_class_probability a reliable
    indicator of prediction correctness? Plot calibration curve.

Stage 7: Negation Test Suite
  Run all 500 negation test cases
  Report per-category accuracy
  Gate: Category A FP < 5%, Category C FN < 2%

Stage 8: Latency Test (bank container hardware)
  Spin up container with target specs (8GB RAM, T4 GPU)
  Run 1,000 inference requests
  Measure p50, p99 latency
  Gate: p99 < 50ms on GPU, p99 < 100ms on CPU

Stage 9: Network Isolation Test
  Deploy container with network monitoring
  Run 1,000 inferences
  Verify: zero outbound network calls
  Gate: no external calls detected

Stage 10: Memory Footprint Test
  Measure model memory usage in container
  GPU path: < 6GB GPU VRAM
  CPU path: < 6GB RAM
  Gate: fits within 8GB container allocation with 2GB headroom

Stage 11: MLflow Logging
  All parameters, metrics, artifacts logged
  Model registered as C4_v1.0.0
  Tagged "staging" pending Audit Gate 1.3
```

---

## 13. RETRAINING PIPELINE (QUARTERLY)

### 13.1 Retraining Trigger

Automatic: quarterly (every 90 days)
Event-triggered: if running FN rate estimate (from operator review)
  exceeds 3% on any 30-day rolling window

### 13.2 Human Review Input

Each quarter, the bank operator reviews a sample of blocked payments:
  - Sample: 200 randomly selected hard-blocked cases from the quarter
  - Task: confirm label (was this correct to block?)
  - False positives identified: add to NOT_DISPUTE training set
  - Label corrections: update corpus

Additionally:
  - Any payment that was hard-blocked but subsequently found to have
    settled operationally (C1 confirmed later): review for false positive
  - Any payment that was NOT blocked but resulted in a funded loan that
    defaulted due to dispute: critical false negative — add to training
    with DISPUTE_CONFIRMED label, flag for immediate retraining

### 13.3 Retraining Protocol

Full fine-tuning retraining (not incremental):
  - Merge new labeled examples into corpus
  - Repeat Stages 1-11 of training pipeline
  - New model version: C4_v1.x.0 (MINOR bump for new data, same arch)
  - Deploy via hot-swap canary protocol (same as C1/C2)

### 13.4 Model Drift Detection

Between retraining cycles, monitor:
  - Hard block rate: if block rate drops >30% from baseline, alert
    (could indicate language drift in RmtInf content)
  - Class distribution of blocks: if DISPUTE_POSSIBLE >> DISPUTE_CONFIRMED,
    investigate — may indicate over-triggering on ambiguous text

---

## 14. VALIDATION REQUIREMENTS (AUDIT GATE 1.3)

### 14.1 False Negative Rate

Primary metric. Measured on OOT test set.
  - FN = examples labeled 1/2/3 that model predicted 0 (NOT_DISPUTE)
  - FN rate = FN / total actual disputes
  - Target: < 2%
  - Report: honest measured value

If FN rate is 2.5-3%: flag but acceptable — proceed with monitoring
If FN rate is > 3%: do not deploy — requires additional training data
  or architecture change (consider DeBERTa fallback)

### 14.2 Negation Test Suite

All 500 cases run. Per Section 10.3:
  - Category A FP rate < 5%
  - Category B FP rate < 5%
  - Category C FN rate < 2%
  - Category D accuracy > 80%
  - Category E accuracy > 75%

ALL category gates must pass.

### 14.3 On-Device Inference Confirmation

Network isolation test: zero outbound calls confirmed
Hardware: T4 GPU (primary) and CPU-only (fallback)
Latency: p99 < 50ms (GPU), p99 < 100ms (CPU)
Timeout behavior: DISPUTE_POSSIBLE returned on timeout (tested)

### 14.4 Memory Footprint

GPU path: < 6GB VRAM
CPU path: < 6GB RAM
Both verified in container environment (not developer laptop)

### 14.5 Retraining Pipeline Test

Retraining pipeline documented and tested (dry run):
  - Add 100 new synthetic examples to corpus
  - Run full retraining pipeline end-to-end
  - Verify new model version registered in MLflow
  - Verify hot-swap works without downtime

---

## 15. INTEGRATION WITH DECISION FLOW

### 15.1 Position in Pipeline

C4 executes BEFORE C1. The order matters:

```
pacs.002 RJCT event received
         |
         v
[C4 — Dispute Classifier]
  |              |
NOT_DISPUTE    DISPUTE_CONFIRMED
  |            DISPUTE_POSSIBLE
  v            NEGOTIATION
[C1 — Failure         |
  Classifier]         v
  |            [Hard Block — log
  v             DisputeBlockRecord]
[C2 — PD Model]
  |
  v
[Decision Engine — offer or no offer]
```

### 15.2 C4 Response Schema

Per Architecture Spec S4.5:
```
DisputeClassifyResponse {
  uetr                    : string
  dispute_class           : int       // 0, 1, 2, 3
  dispute_block           : bool
  class_probabilities     : float[4]  // softmax over 4 classes
  confidence              : float     // max(class_probabilities)
  model_version           : string    // C4_v1.0.0
  inference_latency_ms    : float
  c4_timeout              : bool      // true if timeout occurred
  rejection_code_triggered: bool      // true if hard_block from code pre-filter
  non_primary_language    : bool      // true if non-English/DE/FR/ES
  rmtinf_snippet          : string    // First 50 chars (for log only)
}
```

### 15.3 Block Record for Audit Log

Every hard block persisted to DecisionLogEntry (Architecture Spec S4.8):
  dispute_block = true
  dispute_class = class label
  dispute_confidence = confidence score
  This satisfies EU AI Act Art.13 logging for blocked decisions.

---

## 16. KNOWN LIMITATIONS & HONEST CEILING

1. **Training corpus quality dependency.** If training corpus is
   dominated by synthetic data (Source B), model performance will
   be lower than a corpus dominated by real bank data (Source A).
   The FN rate on synthetic-trained models may be 3-4% rather than
   <2%. The 2% target is achievable with real data. Document the
   corpus composition and its effect on FN rate.

2. **Context window limitation.** RmtInf is 140 characters max.
   But some payment messages have dispute language distributed
   across multiple fields. If the dispute context is only in
   a field not included in the prompt, C4 will miss it. The
   input specification (Section 5.1) is designed to capture
   all available dispute-relevant fields, but edge cases may exist.

3. **Language coverage.** For RmtInf in languages not in the
   training corpus (e.g., Arabic, Japanese, Vietnamese), model
   performance is uncharacterized. The conservative fallback
   (DISPUTE_POSSIBLE on low confidence) mitigates this but
   will increase false positives for these corridors.

4. **Model size constraint risk.** If bank partners specify
   tighter container memory limits than 8GB, Llama-3 8B may
   not fit. DeBERTa-v3-large (900MB) is the documented fallback.
   C4's API contract is identical regardless of which underlying
   model is deployed — the swap is internal to C4.

5. **FN rate honest ceiling.** ARIA's estimate of achievable FN
   rate with real training data: 1.5-2.5%. The 2% target is at
   the aggressive end. With synthetic data only: 3-4% is more
   realistic. Without a bank data partnership, the target may not
   be achievable on initial deployment. Document this clearly.

---

## 17. AUDIT GATE 1.3 CHECKLIST

Gate passes when ALL items checked.
ARIA signs. NOVA verifies ISO 20022 input schema. CIPHER verifies
adversarial edge cases. REX verifies Art.13 compliance.

**False Negative Rate:**
  [ ] FN rate on OOT test set documented (target < 2%, honest actual)
  [ ] Per-class precision/recall documented (all 4 classes)
  [ ] Training corpus composition documented (Source A/B/C/D split)

**Negation Test Suite:**
  [ ] All 500 negation test cases run
  [ ] Category A FP rate < 5% ✓/✗
  [ ] Category B FP rate < 5% ✓/✗
  [ ] Category C FN rate < 2% ✓/✗
  [ ] Category D accuracy > 80% ✓/✗
  [ ] Category E accuracy > 75% ✓/✗
  [ ] All 5 category gates passed before proceeding

**On-Device Inference:**
  [ ] Network isolation test: zero outbound calls confirmed
  [ ] Latency on T4 GPU: p99 < 50ms documented
  [ ] Latency on CPU-only: p99 < 100ms documented
  [ ] Timeout behavior tested: DISPUTE_POSSIBLE returned on timeout

**Container:**
  [ ] GPTQ 4-bit model size < 5.5GB documented
  [ ] GGUF Q4_K_M fallback built and tested
  [ ] Memory usage in container < 6GB GPU/RAM documented
  [ ] Container specs documented (8GB RAM, T4 GPU)
  [ ] Cold start time documented

**Retraining Pipeline:**
  [ ] Dry run completed end-to-end
  [ ] New model version registered correctly
  [ ] Hot-swap (canary) protocol tested

**Multi-Language:**
  [ ] Non-English test set (DE/FR/ES) accuracy ≥ 80%
  [ ] Language detection integrated and tested
  [ ] Low-confidence fallback (DISPUTE_POSSIBLE) verified

**Integration:**
  [ ] DisputeClassifyResponse schema matches Architecture Spec S4.5
  [ ] Hard block logic tested end-to-end with Decision Engine (staging)
  [ ] DecisionLogEntry correctly populated for blocked decisions
  [ ] Rejection code pre-filter tested (DISP/LEGL → immediate block)

**EU AI Act Art.13:**
  [ ] Every block decision logged with class, confidence, model_version
  [ ] Operator override capability documented (for Class 2 reviews)
  [ ] Retraining pipeline documented for Art.17 quality management

**Gate Outcome:**
  [ ] ARIA signs: FN rate honest result documented, negation suite passed
  [ ] NOVA signs: ISO 20022 input schema correctly implemented
  [ ] CIPHER signs: adversarial edge cases (timing attacks on C4) reviewed
  [ ] REX signs: Art.13 logging and Art.17 retraining pipeline compliant

---

*Internal document. Stealth mode active. Nothing external.*
*Last updated: March 4, 2026*
*Status: ACTIVE BUILD — awaiting training corpus*
*Phase 1 — Component 4 — Final ML component*
