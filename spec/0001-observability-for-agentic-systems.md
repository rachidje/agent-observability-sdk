# RFC 0001: Observability for Agentic Systems  
## From Signals to Responsibility

**Status:** Draft (Revision 1)  
**Type:** Foundational  
**Audience:** Senior engineers, SREs, architects, AI system designers  
**Scope:** Agentic and automated decision systems

---

## 1. Motivation

As software systems evolve from deterministic services to **agentic systems**, traditional observability practices become insufficient.

Classic observability answers questions such as:
- Is the service available?
- Is it fast enough?
- Is it failing within acceptable limits?

Agentic systems introduce a different class of questions:
- Why was this decision made?
- Which alternatives were considered and rejected?
- Which assumptions were treated as facts?
- Where does human responsibility begin and end?

Without clear answers to these questions, observability degrades into **dashboard theater**:  
signals without understanding, metrics without accountability.

This RFC proposes a framework for **decision-centric observability**, designed to preserve the human ability to understand, contest, and assume responsibility for decisions made by agentic systems.

---

## 2. Definitions

- **Agentic system**: A system capable of interpreting intent (human or organizational), making contextual decisions, and executing actions autonomously.
- **Decision**: A committed choice that affects system state, users, or downstream processes.
- **Observability**: The ability for a human to reconstruct, explain, and evaluate a decision based on information emitted by the system.
- **Delegation**: The explicit or implicit transfer of decision authority from a human to an automated system.
- **Override**: Any mechanism allowing a human or organization to interrupt, correct, compensate, or invalidate an automated decision, either in real time or retrospectively.

---

## 3. Core Principle (Normative)

> **An agentic system MUST be considered observable only if a human can understand, explain, contest, and, when necessary, neutralize the effects of its decisions.**

Neutralization does not necessarily imply real-time intervention.  
It may take the form of suspension, rollback, compensatory action, or an explicitly documented decision of non-intervention.

If this condition is not met, the system MUST be treated as non-observable, regardless of the quantity of logs, metrics, or traces it produces.

Observability is a **human and organizational property**, not merely a technical one.

---

## 4. A Necessary Reframing

### 4.1 Incorrect Assumption

> Agents can be observed like services.

### 4.2 Correct Framing (Normative)

- Agents MUST be treated as **decision-making processes**, not simple software components.
- Observability MUST NOT be limited to execution signals.
- Observability MUST include:
  - intent interpretation,
  - decision reasoning,
  - responsibility delegation,
  - and long-term impact.

---

## 5. The Five Dimensions of Agent Observability

### 5.1 Intent Observability

**Problem**  
Agents do not act on raw input; they act on interpreted intent, which may be incomplete, ambiguous, or contradictory.

**Requirements**
- The system MUST record the original human or organizational intent when available.
- The system MUST record the intent as interpreted by the agent.
- Transformations between the two MUST be observable.
- Detected ambiguities SHOULD be recorded.
- Ignored ambiguities MUST be explicitly identifiable.

**Note**  
Intent observability also aims to surface organizational incoherence rather than conceal it behind artificial consistency.

**Key Question**  
> Is the agent acting on what was requested, or on what it inferred in the absence of clarity?

---

### 5.2 Reasoning Observability (Without Illusion)

This RFC explicitly rejects full chain-of-thought exposure as a requirement.

The objective is not to expose the internal truth of a model, but to make the decision **externally justifiable**.

**Requirements**
- Decision points (bifurcations) MUST be observable.
- Implicit assumptions MUST be surfaced.
- Applied heuristics SHOULD be identifiable.
- Defaults and fallback mechanisms MUST be recorded.

**Non-Goals**
- Exhaustive reconstruction of internal reasoning
- Disclosure of model-specific internal processes

**Key Question**  
> What did the agent treat as obvious without verification?

---

### 5.3 Decision Observability

A decision is observable only if it is contextualized, comparable, and bounded.

**Requirements**
- Final decisions MUST be recorded.
- Considered alternatives MUST be identifiable.
- Rejection criteria MUST be explicit.
- Confidence level SHOULD be recorded.
- Reversibility or irreversibility MUST be assessed.

**Operational Note**  
Not all decisions require human intervention.  
All decisions MUST remain **contestable a posteriori**, via thresholds, sampling, or incident review.

**Key Question**  
> Could a human reasonably defend a different decision after the fact?

---

### 5.4 Delegation Observability

Delegation is a first-class observability concern.

**Requirements**
- The system MUST document which decisions could have been made by humans.
- Delegated decisions MUST be explicitly marked.
- Automation by convenience SHOULD be distinguishable from deliberate delegation.
- Removed escalation paths MUST be observable.

**Key Question**  
> Did we delegate by design, or by organizational exhaustion?

Any unobserved delegation MUST be treated as a system failure.

---

### 5.5 Impact Observability

Local success does not imply systemic success.

**Requirements**
- Cumulative effects of decisions MUST be observable.
- Bias reinforcement SHOULD be monitored.
- Irreversible decisions MUST be flagged.
- Cognitive debt imposed on humans SHOULD be assessed.
- Long-term behavioral drift SHOULD be observable.

**Key Question**  
> Is this agent making future human judgment easier or harder?

---

## 6. Explicit Rejections (Normative)

The following statements MUST be considered observability failures:

- “99.9% of decisions succeeded”
- “The agent chose the optimal solution”
- “The model decided”
- “The system behaved as expected”

These formulations obscure responsibility and MUST NOT be used as observability claims.

---

## 7. Relationship to SRE

This RFC extends, not replaces, SRE principles.

SRE has shown that loss of visibility creates invisible debt until a major incident occurs.

Similarly, loss of decision comprehensibility creates **strategic debt**, whose cost only becomes visible under stress.

The objective is not perfect decision-making, but **understandability under pressure**.

---

## 8. Non-Goals

This RFC does not:
- prescribe tools or vendors,
- define implementation details,
- mandate model architectures.

Tooling choices MUST follow this RFC, not precede it.

---

## 9. Future Work

This RFC enables, but does not define:
- Decision SLOs
- Decision error budgets
- Reasoning postmortems
- Agent audit trail formats

These topics will be addressed in subsequent RFCs.

---

## 10. Final Statement

Agentic systems do not become dangerous because they automate decisions.

They become dangerous when humans can no longer:
- understand them,
- challenge them,
- or take responsibility for their outcomes.

**Observability is the final safeguard.**
