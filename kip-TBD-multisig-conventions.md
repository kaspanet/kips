```
  KIP: TBD
  Layer: Applications
  Title: Multisig Wallet Conventions for Kaspa
  Author: Kaspian (@KasSigner)
  Comments-URI: (TBD — research.kas.pa discussion thread)
  Status: Draft
  Type: Informational
  created: 2026-04-20
  updated: 2026-04-21
```

# Motivation

The `kaspa-wallet-pskt` crate standardizes the partially-signed
transaction wire format for Kaspa. It does not standardize:

* How cosigners agree they are in the same wallet (descriptor format)
* Which derivation paths cosigner keys are derived at
* Redeem-script construction rules (sort order, M-of-N encoding)
* How the final unlocking `sig_script` is assembled from the
  partial signatures and redeem script
* How the `sigOpCount` field is set for P2SH multisig inputs
* How cosigner extended public keys are exchanged before the
  first transaction

Without conventions at these layers, "2-of-3 multisig on Kaspa"
means different things in different wallet implementations, and
users cannot mix-and-match hardware and software signers from
different vendors.

A secondary concern is inclusivity of constrained signing devices.
The PSKT wire format today — JSON wrapped in hex — is clear and
easy to parse but doubles the wire size of every binary-typed
field (each byte costs 2 hex chars). A 2-of-3 single-input PSKB
measures roughly 2.6-3.2 KB on the wire (depending on how much
key-origin metadata the creator populates), which translates to
roughly 12-25 QR frames at the V9-L to V6-L byte-mode capacities
typical of sub-$20 cameras. Multi-input ceremonies and larger
M-of-N configurations push this into ranges where the UX becomes
impractical on sub-$20 hardware. Flagship hardware wallets with
HD cameras or NFC/USB links are unaffected. This KIP proposes
optional, opt-in compact mechanisms in a later section that, when
advertised by both endpoints, reduce wire size without altering
the semantic format or consensus.

This KIP also clarifies a few places where Kaspa's script engine
and PSKT serialization differ from the Bitcoin PSBT tooling that
most wallet authors will be familiar with. These are existing
Kaspa behaviors, authoritatively defined and tested in
`rusty-kaspa/crypto/txscript/src/lib.rs`. The purpose of restating
them here is to make them easy to find for wallet authors porting
PSBT-multisig patterns, who might otherwise assume Bitcoin
semantics apply unchanged.

# Scope

This KIP is strictly **Informational**. It does not propose any
change to Kaspa consensus, block format, or the PSKT wire format.
It:

1. Defines wallet-level conventions above the existing PSKT
   substrate (derivation path, pubkey ordering, descriptor format,
   sig_script assembly).
2. Points wallet authors to the authoritative script-engine
   implementation (`rusty-kaspa/crypto/txscript`) for a few places
   where Kaspa's semantics diverge from Bitcoin PSBT assumptions.
3. Proposes, in a non-normative appendix, a set of optional
   compact encoding mechanisms for PSKT exchange on
   constrained-device transports, to be considered for upstream
   discussion with `kaspa-wallet-pskt` maintainers.

# Derivation path

Multisig cosigner keys SHOULD be derived at:

```
m / 44' / coin_type' / account' / change / index
```

where:

* `coin_type = 111111` on mainnet, `1` on testnet (per SLIP-44)
* `change = 0` for receive keys, `1` for change keys
* `account` is typically `0`

The `change` level follows BIP-44 naming: `change = 0` for
externally-visible receive addresses, `change = 1` for internal
change addresses returned to the wallet. This is the same
derivation path used for single-signature wallets. Reusing it —
rather than adopting BIP-87-style dual accounts that separate
single-sig and multi-sig — lets one seed serve both use cases
without requiring users to manage multiple accounts. Wallet
authors who prefer dual-account separation are not prohibited
from doing so, but SHOULD document the departure explicitly so
cosigners using other conventions can derive the expected keys.

# Cosigner pubkey ordering

Before constructing the redeem script, cosigner public keys MUST
be sorted lexicographically by the 32-byte x-only Schnorr pubkey
(or the 33-byte compressed pubkey when ECDSA variants are used).

This makes the multisig P2SH address deterministic: cosigners
produce the same address regardless of the order in which their
keys are exchanged during wallet setup. This is equivalent in
spirit to Bitcoin's BIP-67 `sortedmulti`.

Upstream `kaspa_txscript::multisig_redeem_script` and
`multisig_redeem_script_ecdsa` emit pubkeys in the caller-supplied
iterator order; they do not sort internally. Wallets therefore
MUST sort before calling these helpers (or before constructing
the redeem script by hand).

Rationale: unsorted multisigs produce different P2SH addresses for
the same set of cosigners depending on exchange order, which has
caused accidental fund loss when a cosigner derives a different
address from the one that was funded. Mandatory sorting eliminates
this class of bug.

# Redeem script construction

For an M-of-N Schnorr multisig, the redeem script is:

```
OP_M  <OP_DATA_32 pk1>  <OP_DATA_32 pk2>  ...  <OP_DATA_32 pkN>
OP_N  OP_CHECKMULTISIG
```

where `pk1..pkN` are the lex-sorted 32-byte x-only pubkeys,
`OP_M = 0x50 + M` (for M ∈ [1,16]), `OP_N = 0x50 + N` (for N ∈
[1,16]), `OP_DATA_32 = 0x20`, and `OP_CHECKMULTISIG = 0xAE`. For M
or N in the range [17,20], the numeric opcode is encoded as
`OpData1 + <value>` (2 bytes each) rather than as a small-integer
opcode.

Total size (for M,N ≤ 16): `3 + N*33` bytes — 1 byte for `OP_M`,
`N * 33` for the pubkey pushes, 1 byte for `OP_N`, 1 byte for
`OP_CHECKMULTISIG`. For 2-of-3: 102 bytes. For 3-of-5: 168 bytes.

The resulting P2SH `scriptPublicKey` is:

```
OP_BLAKE2B  <OP_DATA_32 blake2b-256(redeem_script)>  OP_EQUAL
```

— 35 bytes: `aa 20 <32-byte hash> 87`.

# PSKT input `sigOpCount` for P2SH multisig

For a P2SH multisig input, the PSKT input's `sigOpCount` field
MUST satisfy:

```
M ≤ sigOpCount ≤ N
```

where M is the signature threshold and N is the total number of
cosigner pubkeys in the redeem script. Any value in that range is
accepted; the exact number of signature operations consumed at
validation time depends on the script's execution path and can be
computed authoritatively by calling `get_sig_op_count` in
`rusty-kaspa/crypto/txscript/src/lib.rs`, which simulates input
validation and returns the count actually used.

For wallets following the conventions in this KIP — lex-sorted
pubkeys in the redeem script and partial signatures emitted in
that same order — the script engine matches each signature against
its corresponding pubkey on the first probe, consuming exactly
M signature operations. Under these conventions **`sigOpCount = M`
is sufficient and tight.**

N remains a safe upper bound and is always accepted; it
over-allocates sig-op budget at block-mass accounting time but
never causes a rejection.

## Rationale

Kaspa's script engine uses a runtime signature-operation counter
(see `op_check_multisig_schnorr_or_ecdsa` in
`rusty-kaspa/crypto/txscript/src/lib.rs`). The counter is
decremented on each signature probe — including probes that do
not result in a match. For scripts with conditional branches or
out-of-order signature assembly the count consumed can be less
than or greater than M, up to N; hence the range.

Some PSBT-multisig tooling in the Bitcoin ecosystem sets the
equivalent field to M by convention, which remains correct in
Kaspa provided the signer follows the ordered-emission convention.
Tooling that cannot guarantee ordered emission should either use
`get_sig_op_count` to compute the exact value or set `sigOpCount
= N` as a safe upper bound.

This is fail-closed: a `sigOpCount` smaller than execution
consumes causes submission-time rejection, never post-confirmation
failure — no fund-loss scenario exists for this specific
misconfiguration.

# Partial signature encoding

Each entry of the PSKT input's `partialSigs` map is keyed by the
cosigner's 33-byte compressed pubkey (66-character lowercase hex)
and valued by an object with exactly one variant key:

* `"schnorr"` — value is the 64-byte Schnorr signature as a
  128-character lowercase hex string
* `"ecdsa"` — value is the 64-byte ECDSA signature as a 128-character
  lowercase hex string

Example:

```json
"partialSigs": {
  "02b1c0...": { "schnorr": "9bbaf2...66b2" },
  "037684...": { "schnorr": "ea4c25...ed1f" }
}
```

The 1-byte SIGHASH flag is NOT appended to the signature bytes
inside `partialSigs`. Finalizers append it during `sig_script`
assembly (see next section).

## Rationale

`kaspa-wallet-pskt` models signatures as a typed enum
(`Signature::Schnorr | Signature::Ecdsa`) that serializes to this
externally-tagged JSON form. Documenting this explicitly prevents
wallet authors from guessing at an untagged or differently-tagged
shape and producing incompatible bundles.

# Final `sig_script` assembly for P2SH multisig

Conforming PSKT finalizers MUST assemble `finalScriptSig` for a
P2SH multisig input as:

```
<push 65 bytes: sig1 || 0x01>
<push 65 bytes: sig2 || 0x01>
...
<push 65 bytes: sigM || 0x01>
<OP_PUSHDATA1 redeem_len>
<redeem_script>
```

where:

* each `sigI` is the 64-byte Schnorr signature of cosigner I,
  followed by the 1-byte SIGHASH flag (typically `0x01` for
  `SIGHASH_ALL`)
* signatures are ordered by each signer's pubkey position in the
  lex-sorted redeem script (ascending) — not by ceremony order.
  This ordering is what lets `sigOpCount = M` be tight at
  validation time. Out-of-order assembly causes the multisig
  verifier to retry later pubkeys for earlier signatures,
  consuming extra sig ops; in the worst case a mis-ordered bundle
  can exhaust the pubkey list before matching all M signatures and
  be rejected with `TxScriptError::NullFail`
* only the first M signatures are included; any additional partial
  signatures that may be present in the bundle are discarded
* the redeem script is pushed with `OP_PUSHDATA1` (0x4C)
  length-prefix when its length exceeds 75 bytes (always the case
  for typical multisigs)

There is NO leading `OP_0` dummy push. Kaspa's `OpCheckMultiSig`
pops exactly M signatures and N pubkeys. Unlike Bitcoin's
`OP_CHECKMULTISIG`, it does not carry the off-by-one legacy bug
that requires a dummy element on the stack.

## Rationale

Kaspa's `OpCheckMultiSig` semantics are defined by
`op_check_multisig_schnorr_or_ecdsa` in
`rusty-kaspa/crypto/txscript/src/lib.rs`. Concrete test vectors
for both Schnorr and ECDSA multisig (1-of-2, 2-of-2, wrong-signer
and insufficient-signer rejection cases) live in
`rusty-kaspa/crypto/txscript/src/standard/multisig.rs` and
demonstrate the expected unlock script shape: the signature
script is assembled directly as `<sig1><sig2>...<sigM>`
concatenated with the redeem-script push, with no OP_0 dummy.

This differs from Bitcoin's `OP_CHECKMULTISIG`, which carries an
off-by-one legacy bug requiring a dummy element on the stack.
Wallet code that ports from Bitcoin tooling typically produces a
`sig_script` with a leading OP_0; Kaspa's script engine rejects
it with `TxScriptError::CleanStack`, whose Display form is
`"stack contains 1 unexpected items"`. Stating the unlock shape
explicitly here saves a debug round-trip.

This is fail-closed: a misassembled `sig_script` causes
submission-time rejection, never post-confirmation failure — no
fund-loss scenario exists for this specific misconfiguration.

# Wallet descriptor — two-layer format

Wallet setup requires exchanging "this is an M-of-N wallet with
these keys" information before any transaction exists. This KIP
defines two semantically equivalent descriptor formats; wallets
MAY implement one, the other, or both.

## Layer A — Canonical descriptor (human-readable, BIP-compatible)

```
ksh(sortedmulti(M, xpub1, xpub2, ..., xpubN))
```

where:

* `ksh(...)` is Kaspa script hash (P2SH). Deliberately distinct
  from Bitcoin's `sh(...)` so that descriptor parsers consuming
  descriptors from both chains do not confuse them.
* `sortedmulti(M, ...)` is lex-sort-by-pubkey multisig, as in
  BIP-67.
* each `xpubI` is a Kaspa-encoded extended public key at the
  account-level path (`m/44'/111111'/0'` by default), optionally
  preceded by `[fingerprint/derivation]` key-origin metadata per
  BIP-380.

Example:

```
ksh(sortedmulti(2,
  [12345678/44h/111111h/0h]kpub661MyMwAq...,
  [87654321/44h/111111h/0h]kpub661MyMwAq...,
  [abcdef12/44h/111111h/0h]kpub661MyMwAq...
))
```

## Layer B — Compact binary descriptor (QR/NFC-friendly)

For air-gapped ceremonies where descriptor size is constrained by
the transport channel, wallets MAY exchange a compact binary form:

```
[magic: 3 bytes "KMS"]
[version: 1 byte = 0x01]
[M: 1 byte]
[N: 1 byte]
[cosigner 1: 65 bytes — 33-byte compressed pubkey || 32-byte chain_code]
[cosigner 2: 65 bytes — 33-byte compressed pubkey || 32-byte chain_code]
...
[cosigner N: 65 bytes — 33-byte compressed pubkey || 32-byte chain_code]
```

Each cosigner entry is a fixed-width 65-byte payload equivalent to
the "body" of a BIP32 extended public key (the 33-byte compressed
pubkey and its 32-byte chain_code), without the 4-byte version
prefix, 1-byte depth, 4-byte parent fingerprint, 4-byte child
number, or the Base58Check wrapper that `kpub...` encoding carries.
Both cosigners in a ceremony share a known account-level derivation
path (typically `m/44'/111111'/0'`), so depth and child-number
context are inferred at the receiving end rather than transmitted.

Total: `6 + 65 * N` bytes. For 2-of-3: 201 bytes — fits in a
single QR code with room to spare, or a single NFC burst.

Layer B is promotable to Layer A: given the receiving wallet's
fingerprint knowledge (when it derives its own share) or default
key-origin metadata, the compact pubkeys reconstruct the canonical
`ksh(sortedmulti(...))` descriptor.

Wallets SHOULD be able to accept Layer A for interop with
Bitcoin-derived tooling and general-purpose software wallets.
Wallets MAY emit Layer B for interop with constrained-device
ceremonies.

# PSKT/PSKB wire format

Conforming wallets MUST use `kaspa-wallet-pskt` `Bundle` as the
serialized wire format for transaction exchange. This KIP does
not redefine PSKT; it defers to `kaspa-wallet-pskt` as the
normative source.

The wire envelope is:

```
"PSKB" + hex_lowercase(serde_json::to_string(&bundle))
```

Single-PSKT payloads MAY use the shorter:

```
"PSKT" + hex_lowercase(serde_json::to_string(&pskt))
```

Both envelopes are accepted by `kaspa_wallet_pskt::PSKT::from_hex`
and `Bundle::deserialize`.

# Transport framing

This KIP is transport-agnostic. Wallets MAY transmit PSKB bytes
over any channel (QR, NFC, USB, file, email, IPFS). Two common
cases are worth noting.

## Multi-frame QR

When the transport is QR, wallets SHOULD split the wire bytes
across multiple QR codes using the following framing per payload:

```
[frame_idx: 1 byte (0-based)]
[total_frames: 1 byte]
[frag_len: 1 byte]
[payload: frag_len bytes]
```

Frame payload capacity depends on the receiving camera's optical
envelope and the QR error-correction level chosen. Useful
reference points for byte-mode payload (authoritative values from
ISO/IEC 18004), with 3 bytes deducted for the framing header
above:

* V6 byte-mode ECC-L: 134 B raw, 131 B payload per frame
* V9 byte-mode ECC-L: 230 B raw, 227 B payload per frame
* V14 byte-mode ECC-L: 458 B raw, 455 B payload per frame

A minimal 2-of-3 single-input PSKB measured at 2656 bytes in a
representative ceremony; a fuller PSKB with all three cosigners'
`bip32Derivations` populated is closer to 3.2 KB. Frame counts
(ceiling division, including framing header):

* 2.6 KB PSKB: 21 / 12 / 6 frames at V6-L / V9-L / V14-L
* 3.2 KB PSKB: 25 / 15 / 8 frames at V6-L / V9-L / V14-L

Selection should trade off camera capability against decode
reliability.

## NFC / USB / short-range

No framing. Transmit the wire bytes as a single payload. Typical
short-range transports handle the full PSKB in a single burst.

# Appendix A — Optional PSKT size reductions (informative)

The proposals below are opt-in and do not change the default PSKT
wire format. Their purpose is to expand the set of devices that
can participate in Kaspa multisig ceremonies — in particular,
hobbyist hardware signers built on sub-$20 boards with
low-resolution cameras.

A wallet that does not advertise or recognize these extensions
behaves as it does today. A wallet that does MAY emit and consume
the compact forms when both endpoints support them.

These proposals are candidates for upstream discussion with the
`kaspa-wallet-pskt` maintainers; the KIP documents them here to
frame the motivation for a future upstream discussion.

## A.1 Omit `bip32Derivations` in hardware-wallet flows

`Input::bip32_derivations` is declared as
`BTreeMap<PublicKey, Option<KeySource>>` in `kaspa-wallet-pskt`.
An empty map is spec-legal and serializes to an empty JSON object
(`{}`, 2 bytes) on the wire. Each populated entry carries a
compressed pubkey key plus a `KeySource` value
(`{keyFingerprint, derivationPath}`). Measured on a
representative entry with a 5-level BIP-44 path
(`m/44h/111111h/0h/0/0`), the on-wire cost is approximately
**139 bytes per cosigner per input** after camelCase JSON
serialization.

When a wallet descriptor has been established out-of-band during
setup, the signing device already knows its own derivation path —
`bip32Derivations` provides no additional information to the
signer and could be emitted as an empty map by mutual agreement.
A proposed opt-in mechanism: a `"minimal": true` flag on the PSKT
global indicating the creator has deliberately elided cosigner
key-origin metadata. Signers that don't recognize the flag see an
empty map and fall back to descriptor-driven derivation.

Measured savings on a PSKB where the creator has populated
`bip32Derivations` with one entry per cosigner (3 entries for a
2-of-3): ~417 bytes per input. If the PSKB carries only the
signer's own entry (1 per input, a common pattern), savings are
~139 bytes per input. On a three-input PSKB with full
three-cosigner population: ~1.25 KB.

## A.2 Drop `scriptPublicKey` version prefix when zero

Every `scriptPublicKey` field carries a 2-byte version prefix
encoded as 4 hex characters. The prefix is almost always zero.
A compact mode could omit it, with receivers inferring version 0.

Savings: 4 hex chars × (|inputs| + |outputs|). Small but trivial.

## A.3 Short-form field names

An opt-in `"compact": true` global flag could alias
frequently-appearing JSON keys to single- or two-letter
equivalents:

| Canonical          | Compact |
|--------------------|---------|
| `partialSigs`      | `ps`    |
| `redeemScript`     | `rs`    |
| `sigHashType`      | `sh`    |
| `sigOpCount`       | `so`    |
| `scriptPublicKey`  | `spk`   |

Savings: ~30 bytes per input on typical PSKBs.

## A.4 Binary framing

JSON + hex doubles the wire size of binary-typed fields (every
byte costs 2 hex characters), and JSON object keys add further
overhead. `kaspa-wallet-pskt` already has `bincode = "1.3.3"` in
its direct dependency list, so the machinery for an opt-in binary
envelope is already in the tree; a wire-format change would
amount to adding a magic prefix bit advertising binary framing
and calling the existing bincode entry points rather than
`serde_json::to_string`. A browser-side gzip measurement on a
representative 2-of-3 multisig PSKB observed roughly 3:1
compression of the JSON form (2656 → 852 bytes), suggesting
comparable savings are achievable from a binary format alone.

This is the most significant of the four proposals. It is the
right subject for a PSKT v2 discussion upstream, not a unilateral
addition to this KIP. The KIP documents the proposal here as
motivation for that upstream discussion.

# Appendix B — Reference implementations

This KIP does not require any particular reference implementation.
Wallets from any vendor are welcome to be listed here as they
implement the conventions.

At time of writing:

* **KasSigner** (`github.com/InKasWeRust/KasSigner`) — embedded
  Rust `no_std` hardware signer on ESP32-S3. Implements the PSKT
  reader/signer/emitter and the three normative clauses
  (`sigOpCount = N`, `partialSigs` variant encoding,
  `sig_script` assembly without OP_0). First end-to-end mainnet
  reference transaction:
  `407d948930db9cf5ca77eb0448f0a64182643fcaded423a752a5aebfc86e8c4e`
* **KasSee** — companion browser-based WASM watch-only wallet.
  Implements the PSKT reader, finalizer, and broadcast flow,
  emitting consensus transactions directly via
  `submit_consensus_tx` without intermediate formats.

Other implementations (Keystone, KasWare, Tangem, Ledger, Kaspium,
Kaspa-NG, etc.) are invited to add entries as they ship conforming
support. The intent is for this appendix to grow into a compat
matrix across the Kaspa wallet ecosystem over time.

# Security Considerations

* **Lex-sorted pubkeys eliminate a multisig footgun.** Unsorted
  multisigs produce different P2SH addresses for the same
  cosigners depending on exchange order. Mandatory sorting
  eliminates this class of bug.
* **Sig-op accounting and script-assembly quirks are
  fail-closed.** A `sigOpCount` set below `M` causes consensus to
  reject the transaction at broadcast time with
  `TxScriptError::ExceededSigOpLimit`. The `sig_script` assembly
  with a leading OP_0 likewise fails at broadcast, with
  `TxScriptError::CleanStack`. These misconfigurations never
  confirm and never produce a fund-loss scenario — a rejected
  transaction leaves the UTXO untouched. Setting `sigOpCount`
  above `M` (up to `N`) is consensus-valid but wastes
  mass-budget and is discouraged by the conventions in this KIP.
* **PSKT itself carries no private-key material.** `partialSigs`
  entries are public signatures. PSKB bundles can be safely
  transmitted over untrusted channels (QR, NFC, email, IPFS,
  public file shares).
* **Optional compact mechanisms do not affect consensus.** The
  proposals in Appendix A change only how wallets encode PSKT
  data between themselves. The transaction submitted to Kaspa
  nodes is always the standard consensus `Transaction` format,
  regardless of which compact modes the originating wallets used.

# Backwards compatibility

This KIP is a forward-looking conventions layer. Wallets that do
not yet implement multisig are unaffected. Wallets that ship
proprietary multisig formats today are encouraged to migrate to
these conventions; the Layer B compact descriptor is small enough
that existing QR-ceremony UX can be preserved.

The optional compact mechanisms in Appendix A are strictly
opt-in. A wallet that does not recognize them sees a standard
PSKB and processes it normally.

This KIP does not propose or require any consensus change.

# Technical references

This section collects the specific functions and types in
`rusty-kaspa` that a wallet implementing this KIP interacts with.
It is informational — the normative rules are in the sections
above — and is provided so that implementers know exactly which
upstream hooks their code connects to.

## Upstream PSKT integration points

**`kaspa_wallet_pskt::pskt::PSKT<Finalizer>::finalize_sync`** — the
crate's finalize entry point. It takes a caller-supplied closure
`final_sig_fn: FnOnce(&Inner) -> Result<Vec<Vec<u8>>, E>` and
stores the returned bytes as each input's `final_script_sig`. The
closure is the wallet's responsibility; it is where the sig_script
assembly rules in this KIP apply. Upstream does not assemble
multisig unlock scripts itself — the closure must produce
`signature_bytes || add_data(redeem_script)` for each P2SH
multisig input, following the conventions specified in this KIP.

**`kaspa_txscript::script_builder::ScriptBuilder::add_data`** — the
canonical helper for pushing data with the correct opcode
selection. At data length ≤ 75 bytes it emits a direct `OpData{n}`
push; at 76–255 bytes it emits `OpPushData1` + 1-byte length;
above that, `OpPushData2`. Wallets SHOULD use this helper rather
than open-coding push opcodes, which matches how Kaspa test
vectors and reference scripts are written.

**`kaspa_txscript::standard::pay_to_script_hash_signature_script`** —
the canonical P2SH sig_script assembler. Given concatenated
signature pushes and a redeem script, it produces
`signature_pushes || add_data(redeem_script)`. This is the shape
the multisig rules in this KIP conform to.

**`PartialSigs = BTreeMap<secp256k1::PublicKey, Signature>`** (see
`kaspa_wallet_pskt::pskt::PartialSigs`). The crate stores per-input
partial signatures in a BTreeMap keyed by the 33-byte compressed
pubkey. The `Ord` implementation of `secp256k1::PublicKey` (via
`secp256k1_ec_pubkey_cmp`) is lexicographic on the 33-byte
compressed serialization, so BTreeMap iteration order matches the
KIP's ordering for **ECDSA** multisig (where the redeem script
also uses 33-byte compressed pubkeys). For **Schnorr** multisig,
where the redeem script uses 32-byte x-only pubkeys, BTreeMap
iteration order does NOT in general match the redeem-script order
— the 1-byte parity prefix on the 33-byte compressed form can
invert the comparison relative to the 32-byte x-only form. Wallets
finalizing a Schnorr P2SH multisig input MUST therefore explicitly
re-sort partial signatures by each signer's 32-byte x-only pubkey
position in the redeem script (see "Final `sig_script` assembly"
above); relying on BTreeMap's default iteration is a silent
correctness bug for Schnorr multisig.

**`kaspa_wallet_pskt::pskt::Signature`** — enum with variants
`ECDSA(secp256k1::ecdsa::Signature)` and
`Schnorr(secp256k1::schnorr::Signature)`. Serde-serialized with
`#[serde(rename_all = "camelCase")]` at the enum level, which
lower-cases the variant names on the wire to `ecdsa` and
`schnorr`. Signatures are stored as raw 64-byte payloads; the
1-byte SIGHASH flag is not part of `Signature` and MUST be
appended by the wallet during sig_script assembly.

## Consensus validation reference

**`kaspa_txscript::op_check_multisig_schnorr_or_ecdsa`**
(`crypto/txscript/src/lib.rs`) — the script engine's multisig
verification path. Walks signatures and pubkeys with a single
forward-only iterator, consuming one sig-op from the runtime
counter per pubkey probe. This is the function whose behavior
determines the tight-vs-upper-bound semantics of
`sigOpCount`.

**`kaspa_txscript::get_sig_op_count`**
(`crypto/txscript/src/lib.rs`) — simulates input validation and
returns the exact number of sig-ops consumed for a given
`sig_script` + `script_public_key` combination. Wallets
unsure which `sigOpCount` value to set for an input can call
this and use the returned value as the tight bound.

**Limits.** `MAX_SCRIPT_ELEMENT_SIZE = 520` (max single push data
size), `MAX_PUB_KEYS_PER_MULTISIG = 20` (max cosigners in a
single `OpCheckMultiSig`). For reference: a 20-of-20 Schnorr
redeem script is `2 + 20*33 + 2 + 1 = 665` bytes (M and N each
encoded as `OpData1 + 1 byte` since values above 16 do not have
small-int opcodes; each pubkey pushed as `OpData32 + 32 bytes`),
which is well below the 10,000-byte `MAX_SCRIPTS_SIZE` limit. No
multisig of practical size is at risk of script-size rejection.

# Acknowledgements

Thanks to Michael Sutton and the `kaspa-wallet-pskt` maintainers
for the upstream PSKT crate that this KIP builds on. Thanks also
to the Kaspa community members active on hardware wallet support
and multisig (the multisig issue `rusty-kaspa#254` framed the
original problem space).

Thanks to Maksim Biryukov (@biryukovmaxim) for review feedback
on a preview of this KIP — in particular for correcting the
`sigOpCount` rule from a fixed `N` to the range `M ≤ sigOpCount
≤ N` and pointing at the authoritative `get_sig_op_count` and
`op_check_multisig_schnorr_or_ecdsa` implementations in
`rusty-kaspa/crypto/txscript/src/lib.rs`.
