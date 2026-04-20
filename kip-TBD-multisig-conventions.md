```
  KIP: TBD
  Layer: Applications
  Title: Multisig Wallet Conventions for Kaspa
  Author: Kaspian (@KasSigner)
  Comments-URI: (TBD — research.kas.pa discussion thread)
  Status: Draft
  Type: Informational
  created: 2026-04-20
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
easy to parse but approximately 2x the size of an equivalent
binary encoding. A 2-of-3 single-input PSKB is about 3.2 KB on the
wire, which translates to 18-32 QR frames on low-resolution
cameras. Multi-input ceremonies and larger M-of-N configurations
push this into ranges where the UX becomes impractical on
sub-$20 hardware. Flagship hardware wallets with HD cameras or
NFC/USB links are unaffected. This KIP proposes optional, opt-in
compact mechanisms in a later section that, when advertised by
both endpoints, reduce wire size without altering the semantic
format or consensus.

This KIP also documents three Kaspa-specific behaviors of the
consensus layer that differ from the Bitcoin tooling most wallet
authors will be familiar with. These behaviors are not proposed
changes — they are existing behaviors that are currently not
documented anywhere a wallet author can easily find them, and
that fail-close at broadcast time when missed.

# Scope

This KIP is strictly **Informational**. It does not propose any
change to Kaspa consensus, block format, or the PSKT wire format.
It:

1. Defines wallet-level conventions above the existing PSKT
   substrate (derivation path, pubkey ordering, descriptor format,
   sig_script assembly).
2. Documents three existing Kaspa consensus behaviors that
   currently lack documentation.
3. Proposes, in a non-normative appendix, a set of optional
   compact encoding mechanisms for PSKT exchange on
   constrained-device transports, to be considered for upstream
   discussion with `kaspa-wallet-pskt` maintainers.

# Derivation path

Multisig cosigner keys SHOULD be derived at:

```
m / 44' / coin_type' / account' / chain / index
```

where:

* `coin_type = 111111` on mainnet, `1` on testnet (per SLIP-44)
* `chain = 0` for receive keys, `1` for change keys
* `account` is typically `0`

This is the same derivation path used for single-signature wallets.
Reusing it — rather than adopting BIP-87-style dual accounts that
separate single-sig and multi-sig — lets one seed serve both use
cases without requiring users to manage multiple accounts. Wallet
authors who prefer dual-account separation are not prohibited from
doing so, but SHOULD document the departure explicitly so
cosigners using other conventions can derive the expected keys.

# Cosigner pubkey ordering

Before constructing the redeem script, cosigner public keys MUST
be sorted lexicographically by the 32-byte x-only Schnorr pubkey
(or the 33-byte compressed pubkey when ECDSA variants are used).

This makes the multisig P2SH address deterministic: cosigners
produce the same address regardless of the order in which their
keys are exchanged during wallet setup. This is equivalent in
spirit to Bitcoin's BIP-67 `sortedmulti`.

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
`OP_M = 0x50 + M`, `OP_N = 0x50 + N`, `OP_DATA_32 = 0x20`, and
`OP_CHECKMULTISIG = 0xAE`.

Total size: `2 + N * 33` bytes. For 2-of-3: 101 bytes.

The resulting P2SH `scriptPublicKey` is:

```
OP_BLAKE2B  <OP_DATA_32 blake2b-256(redeem_script)>  OP_EQUAL
```

— 35 bytes: `aa 20 <32-byte hash> 87`.

# PSKT input `sigOpCount` for P2SH multisig

For a P2SH multisig input, the PSKT input's `sigOpCount` field
MUST equal **N** (the total number of cosigner pubkeys in the
redeem script), NOT M (the signature threshold).

## Rationale

Kaspa consensus `get_sig_op_count` pre-counts signature operations
in an input's `sig_script` by walking the redeem script and
counting `OP_CHECKMULTISIG` as worth N operations. A UTXO that
declares a `sigOpCount` smaller than N triggers the error
`"sig op count exceeds passed limit of M"` at broadcast time, and
the transaction is rejected by the node.

This behavior already exists in Kaspa consensus and is not under
discussion. The purpose of documenting it here is so that wallet
authors do not discover it via mainnet broadcast rejection.

Some PSBT-multisig tooling in the Bitcoin ecosystem sets the
equivalent field to M. Kaspa PSKT producers MUST use N.

This is fail-closed: a misconfigured `sigOpCount` causes
submission-time rejection, never post-confirmation failure — no
fund-loss scenario exists.

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
  lex-sorted redeem script (ascending) — not by ceremony order
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

This behavior already exists in Kaspa consensus (see
`rusty-kaspa/crypto/txscript/` and the test vector at
`crypto/txscript/src/lib.rs:1000`). The purpose of documenting it
here is so that wallet authors porting PSBT-multisig logic from
the Bitcoin ecosystem do not discover it via mainnet broadcast
rejection — the default Bitcoin-tooling behavior produces a
`sig_script` with a leading OP_0, which Kaspa rejects with
`"stack contains 1 unexpected items"`.

This is fail-closed: a misassembled `sig_script` causes
submission-time rejection, never post-confirmation failure — no
fund-loss scenario exists.

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
[cosigner 1: 65 bytes compressed pubkey with key-origin]
[cosigner 2: 65 bytes compressed pubkey with key-origin]
...
[cosigner N: 65 bytes compressed pubkey with key-origin]
```

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
envelope. Useful reference points:

* V6 byte-mode ECC-L: ~104 B payload per frame
* V9 byte-mode ECC-L: ~180 B payload per frame
* V14 byte-mode ECC-L: ~334 B payload per frame

A 3.2 KB PSKB is 31 frames at V6, 18 frames at V9, 10 frames at
V14. Selection should trade off camera capability against decode
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

`bip32_derivations` is `Option<...>` in the upstream type, meaning
its absence is already spec-legal. Each entry carries a 4-byte
fingerprint plus a derivation path (~28 bytes typical), costing
60-80 bytes per cosigner per input after JSON encoding.

When a wallet descriptor has been established out-of-band during
setup, the signing device already knows its own derivation —
`bip32Derivations` provides no additional information and can be
omitted. Proposed opt-in mechanism: a `"minimal": true` flag on
the PSKT global indicating the creator has deliberately omitted
this field.

Savings on a 2-of-3 single-input PSKB: 180-240 bytes.

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

JSON + hex introduces approximately 2x overhead before any content
is considered. A bincode-serialized alternative — when both
endpoints advertise support via a version bit in the magic prefix —
uses the same struct layout `kaspa-wallet-pskt` already serializes
internally via `serde_bincode`. Ceremonies using bincode framing
are approximately half the wire size of JSON+hex ceremonies.

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
etc.) are invited to add entries as they ship conforming
support. The intent is for this appendix to grow into a compat
matrix across the Kaspa wallet ecosystem over time.

# Security Considerations

* **Lex-sorted pubkeys eliminate a multisig footgun.** Unsorted
  multisigs produce different P2SH addresses for the same
  cosigners depending on exchange order. Mandatory sorting
  eliminates this class of bug.
* **Sig-op accounting and script-assembly quirks are
  fail-closed.** Wallets that set `sigOpCount` incorrectly, or
  that assemble the `sig_script` with a leading OP_0, fail at
  broadcast time (rejected by node), never at confirmation time.
  No fund-loss scenario exists for these specific
  misconfigurations — a rejected transaction leaves the UTXO
  untouched.
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

# Acknowledgements

Thanks to Michael Sutton and the `kaspa-wallet-pskt` maintainers
for the upstream PSKT crate that this KIP builds on. Thanks also
to the Kaspa community members active on hardware wallet support
and multisig (the multisig issue `rusty-kaspa#254` framed the
original problem space).
