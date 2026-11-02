```
KIP: XXXX
Layer: Consensus
Title: Epoch-Bound LtHash State Commitments and Threat Mitigation
Type: Consensus change (state commitment)
Author: 619b6414e3649858a14f75d46757f3ebaad1a575c2d63b3cb262a847348d4c61
created: 2026-10-23
updated: 2026-10-23
Status: Proposed
```

# Architectural Specification: Epoch-Bound LtHash State Commitments and Threat Mitigation

**Document Reference:** Architectural Proposal / Design Draft  

- **Cryptographic Security Reference:** [Two-Bit Lifting for Ternary SIS: Polynomial-Time Collision Attacks on LtHash](https://eprint.iacr.org/2026/2083)
- **Context & Benchmarking Reference:** [LtHash Shadow Accumulator](https://github.com/aglov413/rusty-kaspa/tree/dk-lthash-shadow/crypto/lthash) *(Work-in-progress reference implementation; active experimental branch with open questions and preliminary benchmarking data)*

## Abstract

This document outlines an architectural proposal for integrating LtHash into Kaspa node architecture. It establishes the formal security rationale for this design, demonstrating how it neutralizes critical attack vectors—specifically offline lattice grinding and identity-padding via repetition—that threaten lattice-based cryptographic accumulators in distributed state replication.

---

## 1. Vulnerabilities of Static Lattice Accumulators

When evaluating LtHash, a direct drop-in replacement without auxiliary hardening faces fundamental vulnerabilities. Note that this represents the primary threat vectors identified during current protocol analysis rather than an exhaustive security audit:

* **Offline Collision Generation:** If a public mapping or matrix remains static, an adversary can execute advanced lattice-reduction algorithms offline over extended periods to compute a valid collision vector. Upon completion, the adversary can inject a forged state matching the valid hash commitment, thereby bypassing standard state reconciliation.
* **Limitations of Database Constraints:** While secondary database-level constraints (such as strict key-value set definitions) mitigate multiset count inflation and database poisoning flaws, they do not prevent an adversary from persistently computing an offline mathematical collision against a fixed target.
* **Construction-Specific Security Context:** Recent security analyses—including the two-bit-lifting attack—reduce the collision-finding work for LtHash. While alternative parameterizations (such as prime-modulus lanes) alter algebraic attack profiles, static mappings inherently leave accumulators susceptible to unbounded preparation time.

---

## 2. Epoch-Bound Domain Separation Architecture

To neutralize the threat of offline pre-computation, this architecture introduces rolling, epoch-scoped domain separation tied directly to consensus metadata.

* **Deterministic Consensus Parameters:** The epoch boundary is defined as a fixed consensus parameter rather than an operator-configurable setting. It **MUST** be identical and deterministically derivable by every network node from the DAG state (e.g., pruning point blocks), analogous to consensus-sensitive constants defined within protocol parameters rather than local configuration files. 
* **Design-Time vs. Runtime Configurability:** The term "selectable" within this specification refers solely to the design-time choice established by protocol developers during parameter specification, precluding node-local or runtime configurability. Divergent epoch selections across nodes would yield disparate element-to-lane mappings for identical logical UTXO sets, violating consensus agreement on the commitment digest.
* **Leveraging Pruning Points for Granular Epochs:** Rather than introducing a separate tracking mechanism, the design leverages existing pruning points as the underlying data source. Since pruning points are permanently retained, they provide an immutable historical log. This allows epoch lengths to be configured flexibly at $n \times \text{pruning point}$ granularity without significant architectural modifications or additional storage overhead.
* **Systematic Pre-Computation Obsolescence:** Modifying the epoch alters the element-to-vector mapping itself rather than solely updating the final commitment digest. At each eligible epoch transition, the complete UTXO set is remapped, and the LtHash state is recomputed from scratch. Consequently, any pre-computed collision vector derived under a preceding mapping is rendered obsolete upon epoch rollover (barring independent recurrence under the new mapping).
* **Bounded Advance Knowledge and Preparation Windows:** The mitigation strategy restricts the temporal horizon during which an adversary can anticipate the domain-separation value governing a future full-state remapping. The effective preparation window is governed by the epoch schedule and entropy availability. 
* **Attacker Model Constraints & Bootstrap Systemic Impact:** Epoch rotation bounds the useful lifetime of an adversary's pre-computation rather than establishing a static security floor. Under a targeted bootstrapping attack, an adversary must generate a valid collision under a specific mapping, satisfy structural state constraints (including element counts), and execute the exploit before epoch rotation renders the collision obsolete. If successful, forged UTXOs achieve consensus validity. While standard database write constraints prevent a poisoned node from directly bootstrapping honest peers, successfully compromising reference nodes shrinks the pool of valid bootstrap sources, concentrating peer reliance and compounding the systemic probability of subsequent bootstrap poisoning across the network.

---

## 3. Element-Count Binding and Mitigation of Repetition-Padding Attacks

A distinct attack vector exists independently of lattice-reduction or epoch-rotation mechanics: **identity-padding via element repetition**.

Because LtHash lane values accumulate additively modulo a fixed parameter `lane_mod`, (e.g., $2^{16}$ for vanilla `LtHash16`), an adversary requires no cryptographic collision search. By submitting a single forged UTXO key-value entry exactly `lane_mod` times (e.g., $2^{16}$ repetitions), each lane's running sum wraps back to the additive identity. This yields a net contribution of zero to the finalized lattice state, leaving the digest indistinguishable from the honest set while introducing unauthorized rows into the storage layer.

### 3.1 Commitment-Level Element Binding

To structurally eliminate this vulnerability, the protocol binds the aggregate element count directly into the finalized commitment:

$$\text{Commitment} = \text{Hash}(\text{LtHashState} \parallel \text{count})$$

* **Implicit Wire Transmission:** The count parameter does not require dedicated wire serialization; it is implicitly bound within the single finalized hash comparison utilized during block validation and import routines.
* **Structural Infeasibility of Wraparound:** A 32-bit counter is insufficient, as modern node memory capacities can physically accommodate $2^{32}$ entries, leaving vulnerability to engineered wraparound (padding to $2^{32} + k$ to fold a 32-bit counter back to $k$). A **64-bit counter** entirely removes counter-wraparound as an exploitable vector.
* **Detection Mechanics:** During Initial Block Download (IBD), the node imports and writes blocks to the database, subsequently derives the element count directly from its own persisted database, and verifies this derived count against the header-committed value. Once IBD is complete and the local database count is fully verified, the count transitions into a homomorphic accumulator, being updated incrementally per block rather than requiring a full-database re-scan or re-derivation on every subsequent block.
* **Acceptance Criterion:** The commitment verification mechanism **MUST** remain fully secure against repetition-padding attacks independently of auxiliary database sanity-check flags, ensuring architectural robustness against commitment-to-database divergence.

> **Technical Clarification on Modulus Independence:** While prime-modulus lane configurations are selected to mitigate algebraic lattice attacks (such as Regev–CLZ), they do not address the repetition-padding vector. Because any additive group modulo $M$ (whether a power-of-two or a prime $p$) satisfies $M \cdot v \equiv 0 \pmod M$ when an entry is repeated $M$ times, the lane contribution collapses to the additive identity regardless of the modulus type. Therefore, explicit element-count binding remains an independent architectural requirement, regardless of whether a power-of-two or prime lane modulus is chosen.

---

## 4. Adversarial Control Profiles in Domain Separation Candidate Selection

To ensure that rolling domain separation mechanisms cannot be subverted, potential header and state entropy sources are evaluated against strict adversarial control criteria:

* **Control Distribution:** The design criterion dictates that no single adversarial entity maintains unilateral control over the domain-separation value utilized for remapping. While the schedule and timing of when a new mapping rolls over are publicly known and deterministically governed by consensus, the value itself must remain unpredictable to any adversary—preventing any prediction better than a brute-force guess—until it is officially derived and revealed.
* **Exclusion of Pure Miner Control:** Fields characterized by high miner predictability or direct unilateral manipulation (e.g., block nonces, difficulty bits, score counters) are strictly excluded. Utilization of such fields would permit powerful miners to selectively grind domain-separation values.
* **Leveraging Collective Mergeset State:** Preferred entropy candidates derive state from collective network dynamics and mergeset transaction flows (e.g., mergeset root commitments or global UTXO accumulators). Because no single participant controls the broader mergeset history, these metrics restrict targeted manipulation.
* **Construction and Lane-Modulus Considerations:** Epoch-bound domain separation functions complementarily with the underlying LtHash parameterization. Transitioning to prime-modulus lanes mitigates specific algebraic attacks, provided that the underlying mapping preserves required cryptographic properties (e.g., employing a wider cryptographic expansion, such as a 32-bit expansion reduced modulo a 16-bit prime, to ensure uniform random distribution over the field).

---

## 5. System Integration Principles

The proposed architecture minimizes engineering overhead by aligning with established asynchronous state-management primitives:

1. **Predictable Epoch Boundaries:** Pruning-point rollovers serve as a viable trigger mechanism for epoch transitions, leveraging existing full-state UTXO recomputation routines (such as those executed during node sanity validation), though any consensus-derived boundary functions equivalently.
2. **Incremental Delta Tracking:** Live state transitions are maintained homomorphically within active epochs, precluding the necessity for continuous database re-scans.
3. **Finality-Gated Asynchronous Remapping:** Incremental updates accumulate throughout the active epoch. Full-state remapping executes asynchronously upon satisfaction of finality conditions, preventing transaction processing stalls on virtual state worker threads and decoupling heavy cryptographic recomputation from critical path block validation.
