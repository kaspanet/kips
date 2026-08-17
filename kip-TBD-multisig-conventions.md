```
KIP: TBD
Layer: Applications
Title: Multisig Wallet Conventions for Kaspa
Author: Kaspian (@KasSigner)
Comments-URI: (TBD, research.kas.pa discussion thread)
Status: Draft
Type: Informational
created: 2026-04-20
updated: 2026-08-17
```

# Motivation

The `kaspa-wallet-pskt` crate standardizes the partially-signed
transaction wire format for Kaspa, and `rusty-kaspa`'s wallet core
defines the multisig derivation path and cosigner-index semantics.
Neither is documented outside the source. Left undocumented, these
are the parts wallet authors get wrong:

- Which derivation path multisig cosigner keys live at, and that it
  is **not** the single-signature path
- That the path carries a **cosigner level**, and what selects it
- How cosigners agree they are in the same wallet (descriptor format ,
  genuinely unstandardized upstream)
- Redeem-script construction rules (sort order, M-of-N encoding)
- How the final unlocking `sig_script` is assembled
- How `sigOpCount` is set for P2SH multisig inputs
- Which addresses a conforming wallet is expected to watch, and the
  interop consequence when two wallets disagree

Without conventions at these layers, "2-of-3 multisig on Kaspa" means
different things in different implementations, and users cannot
mix-and-match hardware and software signers from different vendors.

A secondary concern is inclusivity of constrained signing devices. The
PSKT wire format today, JSON wrapped in hex, is clear and easy to
parse but doubles the wire size of every binary-typed field. A 2-of-3
single-input PSKB measures roughly 2.6-3.2 KB on the wire, which
translates to roughly 12-25 QR frames at capacities typical of sub-$20
cameras. This KIP proposes optional, opt-in compact mechanisms in a
later section that, when advertised by both endpoints, reduce wire
size without altering the semantic format or consensus.

# Revision note (2026-08-17)

An earlier draft of this KIP specified the multisig derivation path as
`m/44'/coin_type'/account'/change/index`, reusing the single-signature
path, and argued against BIP-87-style separation.

**That was wrong.** `rusty-kaspa` has always derived multisig keys
under purpose `45'` with an additional cosigner level. The error was
mine: I wrote the original draft without reading
`wallet/keys/src/derivation/gen1/hd.rs`. Every normative statement in
this revision is cited to the source file that defines it.

The derivation section, the descriptor format, the cosigner-index
section and Appendix A.1 are materially changed. The redeem-script,
`sigOpCount`, `partialSigs` and `sig_script` sections are unchanged ,
those were correct and are independent of the path.

# Scope

This KIP is strictly **Informational**. It does not propose any change
to Kaspa consensus, block format, or the PSKT wire format. It:

1. Documents the multisig derivation path and cosigner-index semantics
   that `rusty-kaspa` already implements, which are currently
   discoverable only by reading the source.
2. Defines wallet-level conventions above the existing PSKT substrate
   where upstream is genuinely silent (descriptor format, pubkey
   ordering, `sig_script` assembly).
3. Points wallet authors to the authoritative script-engine
   implementation for places where Kaspa's semantics diverge from
   Bitcoin PSBT assumptions.
4. Proposes, in a non-normative appendix, optional compact encoding
   mechanisms for constrained-device transports.

# Derivation path

Multisig cosigner keys MUST be derived at:

```
m / 45' / 111111' / account' / cosigner / chain / index
```

This is what `rusty-kaspa` implements. From
`wallet/keys/src/derivation/gen1/hd.rs`, `build_derivate_path`:

```rust
if is_multisig && cosigner_index.is_none() {
    return Err("cosigner_index is required for multisig path derivation".into());
}
let purpose = if is_multisig { 45 } else { 44 };
let mut path = format!("m/{purpose}'/111111'/{account_index}'");
if let Some(cosigner_index) = cosigner_index {
    path = format!("{path}/{}", cosigner_index)
}
if let Some(address_type) = address_type {
    path = format!("{path}/{}", address_type.index());
}
```

Four properties follow, each of which a wallet author porting from
BIP-44 or from Bitcoin multisig tooling is likely to get wrong:

**Purpose is `45'`, not `44'`.** Multisig has its own purpose. A wallet
deriving multisig keys at `44'` produces a different address set from
every conforming implementation, and the mistake is silent: the
addresses are well-formed and spendable by that wallet alone.

**Coin type is `111111'` on all networks.** The value is a literal in
the format string; it does not vary by network. A wallet using SLIP-44
testnet coin type `1` will not interoperate on testnet.

**There is a cosigner level, and it is REQUIRED.** The function returns
an error rather than defaulting. See the next section for what selects
it.

**The cosigner and chain levels are UNHARDENED.** From
`derive_child_pubkey_manager` in the same file:

```rust
public_key = public_key.derive_child(ChildNumber::new(cosigner_index, false)?)?;
public_key = public_key.derive_child(ChildNumber::new(address_type.index(), false)?)?;
```

This is what makes the descriptor useful: an account-level extended
public key `m/45'/111111'/account'` is sufficient to derive **every**
cosigner family, every chain and every index of the wallet. Cosigners
exchange account-level kpubs once, and each can then reproduce any
address in the wallet.

`chain` follows BIP-44 naming: `0` for receive, `1` for change. From
`wallet/bip32/src/address_type.rs`, `Receive = 0, Change = 1`.

`account` is typically `0`.

# The cosigner level

The cosigner level is the part of the path with no analogue in
single-signature wallets or in Bitcoin multisig tooling, and it is
where implementations diverge most easily.

An N-cosigner wallet has **N address families**, one per cosigner
index. Each family has its own receive and change chains and its own
address sequence. All families are derivable by anyone holding the
descriptor, because the level is unhardened. They are distinct
addresses of the same wallet: any of them is spendable by the same
M-of-N signature set, since the redeem script at every family is built
from all N cosigners' keys at that path.

## How `rusty-kaspa` selects a family

At account creation, from `wallet/core/src/wallet/mod.rs`:

```rust
generated_xpubs.sort_unstable();
xpub_keys.extend_from_slice(generated_xpubs.as_slice());
xpub_keys.sort_unstable();

let min_cosigner_index =
    generated_xpubs.first().and_then(|first_generated| xpub_keys.binary_search(first_generated).ok()).map(|v| v as u8);
```

The wallet derives an xpub from each private key the account owns,
sorts them, and takes the position of the **lowest** of its own within
the full sorted cosigner list. That value is stored on the account and
fixes the family for its lifetime.

The rule exists because a `rusty-kaspa` account may own **several** of
the wallet's private keys at once, `prv_key_data_args` is a list, so
"which family am I" needs a deterministic answer independent of the
order the keys were supplied.

Two consequences worth stating for implementers:

**A watch-only multisig account owns no keys**, so `min_cosigner_index`
is `None` and derivation falls back to `cosigner_index.unwrap_or(0)`: family 0, regardless of whose wallet it is.

**`AccountCreateArgs::Multisig` exposes no way to set it.** The public
API takes `prv_key_data_args`, `additional_xpub_keys`, `name` and
`minimum_signatures`. The field exists on the internal `Payload` and on
`MultiSig::try_new`, but there is no supported path for an application
to say "watch family 3".

## How a single-key signer selects a family

A signing device holding one key of the wallet determines its family by
deriving its own account-level key and locating it in the descriptor's
sorted cosigner list. With one key there is exactly one candidate, so
first-match and minimum coincide.

A device that lets the user browse families, issuing addresses from,
or watching, a family other than its own, is conformant: every family
is a valid part of the wallet. But see the interop rule below.

## Interop rule: address families and visibility

**A conforming wallet watches its own family.** An address issued from
family S0 will not appear in the balance of a counterpart whose account
sits at family S1, because that account derives only its own family and
has no API to widen the search. The funds are not lost, the address is
a valid address of the shared wallet, spendable by the same M-of-N set,
and recoverable by anyone with the descriptor, but they are invisible
to the counterpart's wallet software until it is told where to look.

Wallets SHOULD therefore issue receive addresses from their own family
by default.

Wallets that expose family selection SHOULD make the family visible
wherever an address is displayed, so that an address handed out from a
non-default family is recognisable as such. Displaying the address
alone is insufficient: two families of the same wallet produce
addresses that are indistinguishable by inspection.

This also bounds recovery. Recovering a wallet from the descriptor
alone requires scanning N families rather than one; a wallet that scans
only family 0 will not find funds held in family 2. Wallet authors
implementing multisig recovery SHOULD scan all N families, and SHOULD
NOT assume the participant's own family is the only one used.

# Cosigner pubkey ordering

Before constructing the redeem script, cosigner public keys MUST be
sorted lexicographically by the 32-byte x-only Schnorr pubkey (or the
33-byte compressed pubkey when ECDSA variants are used).

This makes the multisig P2SH address deterministic: cosigners produce
the same address regardless of the order in which their keys are
exchanged during wallet setup. This is equivalent in spirit to
Bitcoin's BIP-67 `sortedmulti`.

Upstream `kaspa_txscript::multisig_redeem_script` and
`multisig_redeem_script_ecdsa` emit pubkeys in the caller-supplied
iterator order; they do not sort internally. Wallets therefore MUST
sort before calling these helpers.

Note that this sort is over the keys **derived at the address path**,
not over the account-level kpubs. Sorting at the wrong level produces a
different, silently incorrect address.

Rationale: unsorted multisigs produce different P2SH addresses for the
same set of cosigners depending on exchange order, which has caused
accidental fund loss when a cosigner derives a different address from
the one that was funded. Mandatory sorting eliminates this class of
bug.

# Redeem script construction

For an M-of-N Schnorr multisig, the redeem script is:

```
OP_M  <OP_DATA_32 pk1>  <OP_DATA_32 pk2>  ...  <OP_DATA_32 pkN>
OP_N  OP_CHECKMULTISIG
```

where `pk1..pkN` are the lex-sorted 32-byte x-only pubkeys,
`OP_M = 0x50 + M` (for M in [1,16]), `OP_N = 0x50 + N`,
`OP_DATA_32 = 0x20`, and `OP_CHECKMULTISIG = 0xAE`. For M or N in
[17,20], the numeric opcode is encoded as `OpData1 + <value>` (2 bytes
each) rather than as a small-integer opcode.

Total size (for M,N <= 16): `3 + N*33` bytes. For 2-of-3: 102 bytes.
For 3-of-5: 168 bytes.

The resulting P2SH `scriptPublicKey` is:

```
OP_BLAKE2B  <OP_DATA_32 blake2b-256(redeem_script)>  OP_EQUAL
```

That is 35 bytes: `aa 20 <32-byte hash> 87`.

# PSKT input `sigOpCount` for P2SH multisig

For a P2SH multisig input, the PSKT input's `sigOpCount` field MUST
satisfy:

```
M <= sigOpCount <= N
```

Any value in that range is accepted; the exact number of signature
operations consumed at validation time depends on the script's
execution path and can be computed authoritatively by calling
`get_sig_op_count` in `rusty-kaspa/crypto/txscript/src/lib.rs`.

For wallets following the conventions in this KIP (lex-sorted pubkeys
in the redeem script, partial signatures emitted in that same order),
the script engine matches each signature against its corresponding
pubkey on the first probe, consuming exactly M signature operations.
Under these conventions **`sigOpCount = M` is sufficient and tight.**

N remains a safe upper bound and is always accepted; it over-allocates
sig-op budget at block-mass accounting time but never causes a
rejection.

## Rationale

Kaspa's script engine uses a runtime signature-operation counter (see
`op_check_multisig_schnorr_or_ecdsa`). The counter is decremented on
each signature probe, including probes that do not result in a match.
For scripts with conditional branches or out-of-order signature
assembly the count consumed can be less than or greater than M, up to
N; hence the range.

This is fail-closed: a `sigOpCount` smaller than execution consumes
causes submission-time rejection, never post-confirmation failure, no
fund-loss scenario exists for this specific misconfiguration.

# Partial signature encoding

Each entry of the PSKT input's `partialSigs` map is keyed by the
cosigner's 33-byte compressed pubkey (66-character lowercase hex) and
valued by an object with exactly one variant key:

- `"schnorr"`: value is the 64-byte Schnorr signature as a
  128-character lowercase hex string
- `"ecdsa"`: value is the 64-byte ECDSA signature as a 128-character
  lowercase hex string

Example:

```
"partialSigs": {
  "02b1c0...": { "schnorr": "9bbaf2...66b2" },
  "037684...": { "schnorr": "ea4c25...ed1f" }
}
```

The 1-byte SIGHASH flag is NOT appended to the signature bytes inside
`partialSigs`. Finalizers append it during `sig_script` assembly.

## Rationale

`kaspa-wallet-pskt` models signatures as a typed enum
(`Signature::Schnorr | Signature::Ecdsa`) that serializes to this
externally-tagged JSON form. Documenting this explicitly prevents
wallet authors from guessing at an untagged or differently-tagged shape
and producing incompatible bundles.

# Final `sig_script` assembly for P2SH multisig

Conforming PSKT finalizers MUST assemble `finalScriptSig` for a P2SH
multisig input as:

```
<push 65 bytes: sig1 || 0x01>
<push 65 bytes: sig2 || 0x01>
...
<push 65 bytes: sigM || 0x01>
<OP_PUSHDATA1 redeem_len>
<redeem_script>
```

where:

- each `sigI` is the 64-byte Schnorr signature of cosigner I, followed
  by the 1-byte SIGHASH flag (typically `0x01` for `SIGHASH_ALL`)
- signatures are ordered by each signer's pubkey position in the
  lex-sorted redeem script (ascending). not by ceremony order. This
  ordering is what lets `sigOpCount = M` be tight at validation time.
  Out-of-order assembly causes the multisig verifier to retry later
  pubkeys for earlier signatures, consuming extra sig ops; in the worst
  case a mis-ordered bundle can exhaust the pubkey list before matching
  all M signatures and be rejected with `TxScriptError::NullFail`
- only the first M signatures are included; any additional partial
  signatures present in the bundle are discarded
- the redeem script is pushed with `OP_PUSHDATA1` (0x4C) length-prefix
  when its length exceeds 75 bytes (always the case for typical
  multisigs)

There is NO leading `OP_0` dummy push. Kaspa's `OpCheckMultiSig` pops
exactly M signatures and N pubkeys. Unlike Bitcoin's
`OP_CHECKMULTISIG`, it does not carry the off-by-one legacy bug that
requires a dummy element on the stack.

## Rationale

Kaspa's `OpCheckMultiSig` semantics are defined by
`op_check_multisig_schnorr_or_ecdsa` in
`rusty-kaspa/crypto/txscript/src/lib.rs`. Concrete test vectors for
both Schnorr and ECDSA multisig live in
`rusty-kaspa/crypto/txscript/src/standard/multisig.rs`.

Wallet code that ports from Bitcoin tooling typically produces a
`sig_script` with a leading OP_0; Kaspa's script engine rejects it with
`TxScriptError::CleanStack`, whose Display form is `"stack contains 1
unexpected items"`. Stating the unlock shape explicitly here saves a
debug round-trip.

This is fail-closed: a misassembled `sig_script` causes submission-time
rejection, never post-confirmation failure.

# Change output conventions

A multisig wallet returning change to the address it just spent from
links every transaction of that wallet on chain and defeats the purpose
of having a change chain. Conforming wallets SHOULD:

- send change to `chain = 1` of the **same cosigner family** as the
  inputs, so that change stays within the family the wallet watches
- select the **first unused index** on that chain, not the index of the
  address being spent

"Unused" MUST be determined from transaction history, not from the UTXO
set alone. An address that was funded and later fully spent holds no
UTXO but has history; treating it as unused sends change back to an
address already published on chain, and rotation silently stops
rotating after one round.

Coordinators SHOULD populate the change output's `bip32Derivations`
with the path they derived it from. A signer holding the descriptor can
then rebuild the address independently and confirm the change output
belongs to the wallet, a check the signer cannot otherwise perform,
because a multisig address is a hash over all N cosigners' keys and one
seed cannot reproduce it.

Three states are worth distinguishing in a signer's UI:

- **verified**: a trusted descriptor reproduces the claimed address
- **unverifiable**: no descriptor is loaded, so the claim cannot be
  checked
- **contradicted**: a descriptor that reproduces this transaction's
  own inputs fails to reproduce the change output

The third is not a missing check, it is a false claim: the descriptor
is demonstrably the right one for this wallet. Signers SHOULD refuse
rather than warn.

# Multi-input and multi-address spending

Each PSKT input carries its own `redeemScript` and its own
`bip32Derivations`. A transaction MAY therefore spend inputs from
several addresses, with each input naming its own
`(cosigner, chain, index)`.

Note that the cosigner level names a BRANCH of the wallet, not an
identity. In family F the redeem script holds all N cosigners' keys
derived at `.../F/chain/index`, so every participant holds a key in
every family and any M of them can sign in any family. Nothing in the
format prevents a single transaction from spending inputs drawn from
several families: a signer needs only its own key derived at each
input's family, one additional derivation per distinct family.

Wallets MAY restrict spending to a single family as a simplifying
choice. Doing so costs nothing in interoperability: a transaction
spending one family is valid input to any conforming wallet.

Wallets SHOULD support this. Without it, change rotation has no exit:
every spend creates a change output that can only ever be spent alone,
so a wallet used N times accumulates N UTXOs that can never be
combined, and the smallest eventually cost more in fee than they hold.
That is dust accumulating with no way out, not a privacy trade.

Wallets SHOULD make the privacy cost explicit at the point of
selection: spending several addresses in one transaction links them
permanently, and every address in that transaction becomes provably one
wallet.

Fee estimation MUST account for the real input count. A multi-input
multisig transaction priced as a single input underpays and is rejected
at relay, after every signer has already signed it.

# Wallet descriptor, two-layer format

Wallet setup requires exchanging "this is an M-of-N wallet with these
keys" information before any transaction exists. Upstream does not
standardize a descriptor format; this section is a proposal rather than
documentation of existing behaviour.

This KIP defines two semantically equivalent formats; wallets MAY
implement one, the other, or both.

## Layer A, Canonical descriptor (human-readable, BIP-compatible)

```
ksh(sortedmulti(M, kpub1, kpub2, ..., kpubN))
```

where:

- `ksh(...)` is Kaspa script hash (P2SH). Deliberately distinct from
  Bitcoin's `sh(...)` so that parsers consuming descriptors from both
  chains do not confuse them.
- `sortedmulti(M, ...)` is lex-sort-by-pubkey multisig, as in BIP-67.
- each `kpubI` is a Kaspa-encoded extended public key at the
  **account-level path** `m/45'/111111'/account'`, optionally preceded
  by `[fingerprint/derivation]` key-origin metadata per BIP-380.

Example:

```
ksh(sortedmulti(2,
  [12345678/45h/111111h/0h]kpub661MyMwAq...,
  [87654321/45h/111111h/0h]kpub661MyMwAq...,
  [abcdef12/45h/111111h/0h]kpub661MyMwAq...
))
```

The account-level key is the correct exchange point: the cosigner and
chain levels below it are unhardened, so every family and every address
of the wallet is derivable from the descriptor alone.

**The descriptor does not name a family.** It describes the whole
wallet. Which family a given participant uses is a property of that
participant's wallet, determined as described in "The cosigner level".
Wallets exchanging descriptors out of band SHOULD also communicate
which family each participant intends to use, or accept that recovery
requires scanning all N.

**Key-origin metadata carries the purpose.** A `kpub` at
`m/45'/111111'/0'` and one at `m/44'/111111'/0'` are byte-identical in
their encoded form, the encoding carries depth and parent fingerprint
but not the path. Only the `[fingerprint/derivation]` prefix
distinguishes them. Wallets exporting a cosigner key for multisig
SHOULD include key-origin metadata, and wallets importing one SHOULD
verify the purpose level is `45'` before accepting it. Without this,
a single-signature account key can be enrolled as a cosigner key and
produce a wallet no participant can reproduce.

## Layer B, Compact binary descriptor (QR/NFC-friendly)

For air-gapped ceremonies where descriptor size is constrained by the
transport, wallets MAY exchange a compact binary form:

```
[magic: 3 bytes "KMS"]
[version: 1 byte = 0x01]
[M: 1 byte]
[N: 1 byte]
[cosigner 1: 65 bytes, 33-byte compressed pubkey || 32-byte chain_code]
...
[cosigner N: 65 bytes, 33-byte compressed pubkey || 32-byte chain_code]
```

Each entry is the "body" of a BIP32 extended public key without the
4-byte version prefix, 1-byte depth, 4-byte parent fingerprint, 4-byte
child number, or Base58Check wrapper. Both endpoints share a known
account-level path, so depth and child-number context are inferred
rather than transmitted.

Total: `6 + 65 * N` bytes. For 2-of-3: 201 bytes, a single QR code
with room to spare, or a single NFC burst.

Layer B is promotable to Layer A given the receiving wallet's
fingerprint knowledge or default key-origin metadata.

Wallets SHOULD accept Layer A for interop with general-purpose software
wallets. Wallets MAY emit Layer B for constrained-device ceremonies.

# PSKT/PSKB wire format

Conforming wallets MUST use `kaspa-wallet-pskt` `Bundle` as the
serialized wire format for transaction exchange. This KIP does not
redefine PSKT; it defers to `kaspa-wallet-pskt` as the normative
source.

The wire envelope is:

```
"PSKB" + hex_lowercase(serde_json::to_string(&bundle))
```

Single-PSKT payloads MAY use the shorter:

```
"PSKT" + hex_lowercase(serde_json::to_string(&pskt))
```

Both envelopes are accepted by `kaspa_wallet_pskt::PSKT::from_hex` and
`Bundle::deserialize`.

# Transport framing

This KIP is transport-agnostic. Wallets MAY transmit PSKB bytes over
any channel (QR, NFC, USB, file, email, IPFS).

## Multi-frame QR

When the transport is QR, wallets SHOULD split the wire bytes across
multiple QR codes using the following framing per payload:

```
[frame_idx: 1 byte (0-based)]
[total_frames: 1 byte]
[frag_len: 1 byte]
[payload: frag_len bytes]
```

Frame payload capacity depends on the receiving camera's optical
envelope and the QR error-correction level chosen. Reference points for
byte-mode payload (ISO/IEC 18004), with 3 bytes deducted for the
framing header:

- V6 byte-mode ECC-L: 134 B raw, 131 B payload per frame
- V9 byte-mode ECC-L: 230 B raw, 227 B payload per frame
- V14 byte-mode ECC-L: 458 B raw, 455 B payload per frame

A minimal 2-of-3 single-input PSKB measured at 2656 bytes in a
representative ceremony; a fuller PSKB with all three cosigners'
`bip32Derivations` populated is closer to 3.2 KB. Frame counts
(ceiling division, including framing header):

- 2.6 KB PSKB: 21 / 12 / 6 frames at V6-L / V9-L / V14-L
- 3.2 KB PSKB: 25 / 15 / 8 frames at V6-L / V9-L / V14-L

## NFC / USB / short-range

No framing. Transmit the wire bytes as a single payload.

# Appendix A, Optional PSKT size reductions (informative)

The proposals below are opt-in and do not change the default PSKT wire
format. Their purpose is to expand the set of devices that can
participate in Kaspa multisig ceremonies, in particular, hobbyist
hardware signers built on sub-$20 boards with low-resolution cameras.

A wallet that does not advertise or recognize these extensions behaves
as it does today.

## A.1 Derivation hints: a correction, and what they are actually for

An earlier draft of this KIP proposed eliding `bip32Derivations` as a
size saving, on the reasoning that "the signing device already knows
its own derivation path". With the cosigner level in the path, that
reasoning does not hold, and the correction is worth stating plainly
because it inverts the recommendation.

**What a stateless signer needs.** To sign a multisig input, a signer
must find which of the N pubkeys in the redeem script is its own, which
requires knowing `(cosigner, chain, index)`. The descriptor supplies
the cosigner level. The chain and index are per-input and are not
recoverable from the descriptor, only by deriving candidates and
matching against the redeem script.

**What it costs to search.** Measured on an ESP32-S3 at 240 MHz, one
BIP32 child derivation costs approximately 47 ms. Searching one family
across two chains and 40 indices is 80 derivations, under four seconds
per input. Searching all families of a 2-of-3 across the same range is
609 derivations, approximately 29 seconds per input, per key slot.

**Where the field comes from.** In `rusty-kaspa`,
`bip32_derivations` is written in `pass_signature` /
`pass_signature_sync` (`wallet/pskt/src/pskt.rs`), by each signer,
alongside its own signature, the `KeySource` is built inside the
signing path at `wallet/core/src/account/pskb.rs`. Nothing populates it
at construction time. A PSKB from a coordinator therefore arrives with
the map **empty**, and the earlier draft's measured "saving" describes
bytes that are frequently not present to begin with.

**Recommendation, reversed.** Coordinators SHOULD populate
`bip32Derivations` for each input with the path the input's address was
derived from, and for change outputs with the path the change address
was derived from. This is spec-legal, the field is
`BTreeMap<PublicKey, Option<KeySource>>` and a coordinator may write
what it knows, costs approximately 139 bytes per entry, and is what
makes a constrained signer viable at all.

Wallets that cannot populate it SHOULD expect signers to fall back to a
bounded search within the family named by the descriptor, and SHOULD
NOT expect a stateless signer to search all N families.

The size problem this section originally addressed is real; A.4 is the
correct place to solve it.

## A.2 Drop `scriptPublicKey` version prefix when zero

Every `scriptPublicKey` field carries a 2-byte version prefix encoded
as 4 hex characters. The prefix is almost always zero. A compact mode
could omit it, with receivers inferring version 0.

Savings: 4 hex chars x (|inputs| + |outputs|). Small but trivial.

## A.3 Short-form field names

An opt-in `"compact": true` global flag could alias frequently-appearing
JSON keys to single- or two-letter equivalents:

| Canonical         | Compact |
| ----------------- | ------- |
| `partialSigs`     | `ps`    |
| `redeemScript`    | `rs`    |
| `sigHashType`     | `sh`    |
| `sigOpCount`      | `so`    |
| `scriptPublicKey` | `spk`   |

Savings: ~30 bytes per input on typical PSKBs.

## A.4 Binary framing

JSON + hex doubles the wire size of binary-typed fields, and JSON
object keys add further overhead. `kaspa-wallet-pskt` already has
`bincode = "1.3.3"` in its direct dependency list, so the machinery for
an opt-in binary envelope is already in the tree; a wire-format change
would amount to adding a magic prefix advertising binary framing and
calling the existing bincode entry points rather than
`serde_json::to_string`. A browser-side gzip measurement on a
representative 2-of-3 PSKB observed roughly 3:1 compression of the JSON
form (2656 -> 852 bytes), suggesting comparable savings from a binary
format alone.

A measured data point from a binary encoding that carries per-input
derivation hints rather than eliding them: a 2-of-3 single-input bundle
of 7752 hex characters reduced to 794, a 90% reduction. A three-input
bundle reduced from 14668 to 1646 hex characters, 89%. Both figures
INCLUDE the hint records described in A.1.

The relevance to this KIP is that size and signer capability are not in
tension. The size problem is the hex-of-JSON envelope, not the
derivation metadata, and a binary envelope solves it with room to spare
for metadata a constrained signer needs. A format eliding hints to save
bytes is optimising the wrong term.

This is the most significant of the four proposals and the right
subject for a PSKT v2 discussion upstream, not a unilateral addition to
this KIP.

# Appendix B, Reference implementations

This KIP does not require any particular reference implementation.
Wallets from any vendor are welcome to be listed here as they implement
the conventions.

At time of writing:

- **KasSigner** (`github.com/InKasWeRust/KasSigner`), an air-gapped
  hardware signer, with **KasSee**, a browser-based watch-only
  coordinator. Schnorr 45' multisig covering the derivation path with
  cosigner level, descriptor-driven family resolution, change rotation
  on chain 1, multi-input spending, and the `partialSigs` and
  `sig_script` conventions above.

The transactions below are cited as evidence that the conventions in
this KIP are consistent and accepted by consensus, not as an
endorsement of any implementation. Mainnet, 45' multisig, 2-of-2:

- `6b032c0c28b490dfae77f1dd6bafe1ce7d615bf4b905f4b6494f0fc816f9a204`
  (single input, change to the first unused index on chain 1)
- `7267ee0581532e3a57f79074450743e24e73b22e31505a6f3ad1c90b5e46bf56`
  (two inputs from two different addresses, one output)
- `ddf3baf86732696e5b90f3f3fa5923d2fd62f7bcd4dca9b4e9566acf7c9a075b`
  (three-input consolidation)
- `4195e96595bf43fdfb971d8e347f9a3f54b75eaa2cd9f919ac6e2467a666958f`
  (coordinator between two air-gapped signers, compact relay both hops)

An earlier 44'-derived transaction was cited in the first draft of this
KIP. It is not a conforming multisig transaction under the corrected
derivation path and has been removed.

Other implementations (Keystone, KasWare, Tangem, Ledger, Kaspium,
Kaspa-NG, etc.) are invited to add entries as they ship conforming
support.

# Security Considerations

- **The derivation path is a silent-failure surface.** A wallet
  deriving multisig keys at `44'`, or omitting the cosigner level,
  produces well-formed addresses that no conforming implementation can
  reproduce. Nothing rejects it; the funds are simply unreachable by
  the other cosigners' software. This KIP exists in large part because
  the author made this mistake.
- **Lex-sorted pubkeys eliminate a multisig footgun.** Unsorted
  multisigs produce different P2SH addresses for the same cosigners
  depending on exchange order.
- **Sig-op accounting and script-assembly quirks are fail-closed.** A
  `sigOpCount` below what execution consumes, or a `sig_script` with a
  leading OP_0, fails at broadcast. These never confirm and never
  produce a fund-loss scenario.
- **Address families are a visibility surface, not a security one.**
  An address from a family a counterpart does not watch is invisible to
  them but remains spendable by the M-of-N set and recoverable from the
  descriptor.
- **Spending is disclosure.** P2SH publishes the redeem script, so the
  threshold and every cosigner's key at that index become public the
  moment an address is spent from. Derived material alone can receive
  privately; it cannot spend privately.
- **The descriptor is a second secret.** A seed alone cannot find or
  spend its own multisig funds: the address is a hash over all N
  cosigners' keys, recorded nowhere on chain. Wallets MUST make clear
  that the descriptor requires backup alongside the seed.
- **PSKT itself carries no private-key material.** `partialSigs`
  entries are public signatures. PSKB bundles can be transmitted over
  untrusted channels.
- **Optional compact mechanisms do not affect consensus.** The
  transaction submitted to nodes is always the standard consensus
  `Transaction` format.

# Backwards compatibility

This KIP documents existing `rusty-kaspa` behaviour for the derivation
path and cosigner semantics; wallets already following the reference
implementation are conformant without change.

Wallets that shipped 44'-derived multisig, including the reference
implementation before 2026-08, hold funds at addresses no conforming
wallet reproduces. Those wallets MUST retain the ability to spend the
legacy path, and SHOULD migrate new wallet creation to `45'`. Migration
is a fund movement, not a re-derivation: the legacy addresses remain
spendable only by software that knows the legacy path.

The conventions above the path (descriptor format, change rotation,
multi-address spending) are forward-looking. The optional compact
mechanisms in Appendix A are strictly opt-in.

This KIP does not propose or require any consensus change.

# Technical references

## Derivation and account semantics

**`kaspa_wallet_keys::derivation::gen1::WalletDerivationManager::build_derivate_path`**
(`wallet/keys/src/derivation/gen1/hd.rs`). constructs the derivation
path. Defines `purpose = 45` for multisig, the hardcoded `111111` coin
type, and the requirement that `cosigner_index` be present.

**`WalletDerivationManager::derive_child_pubkey_manager`** (same file). derives the cosigner and chain levels as UNHARDENED children.

**`Wallet::create_account_multisig`** (`wallet/core/src/wallet/mod.rs`). computes `min_cosigner_index` at account creation.

**`AccountCreateArgs::Multisig`** (`wallet/core/src/wallet/args.rs`). the public creation API. Takes `prv_key_data_args`,
`additional_xpub_keys`, `name`, `minimum_signatures`; does not expose
`cosigner_index`.

**`AddressType`** (`wallet/bip32/src/address_type.rs`). `Receive = 0`,
`Change = 1`.

## Upstream PSKT integration points

**`kaspa_wallet_pskt::pskt::PSKT<Finalizer>::finalize_sync`**: the
crate's finalize entry point, taking a caller-supplied closure. Upstream
does not assemble multisig unlock scripts itself; the closure must
produce `signature_bytes || add_data(redeem_script)` for each P2SH
multisig input.

**`PSKT::pass_signature` / `pass_signature_sync`**
(`wallet/pskt/src/pskt.rs`). where `bip32_derivations` is populated, by
the signer, alongside its own signature.

**`kaspa_txscript::script_builder::ScriptBuilder::add_data`**: the
canonical helper for pushing data with correct opcode selection.

**`kaspa_txscript::standard::pay_to_script_hash_signature_script`**: the canonical P2SH sig_script assembler.

**`PartialSigs = BTreeMap<secp256k1::PublicKey, Signature>`**: the
`Ord` implementation is lexicographic on the 33-byte compressed
serialization, so BTreeMap iteration order matches the redeem-script
order for **ECDSA** multisig. For **Schnorr** multisig, where the redeem
script uses 32-byte x-only pubkeys, iteration order does NOT in general
match, the 1-byte parity prefix can invert the comparison. Wallets
finalizing a Schnorr P2SH multisig input MUST explicitly re-sort partial
signatures by x-only pubkey position; relying on BTreeMap's default
iteration is a silent correctness bug.

**`kaspa_wallet_pskt::pskt::Signature`**: enum with `ECDSA` and
`Schnorr` variants, serde-serialized with `rename_all = "camelCase"`.
Signatures are raw 64-byte payloads; the SIGHASH flag is appended by
the wallet during sig_script assembly.

## Consensus validation reference

**`kaspa_txscript::op_check_multisig_schnorr_or_ecdsa`**
(`crypto/txscript/src/lib.rs`). the script engine's multisig
verification path, consuming one sig-op per pubkey probe.

**`kaspa_txscript::get_sig_op_count`** (same file). simulates input
validation and returns the exact sig-op count for a given `sig_script` +
`script_public_key`.

**Limits.** Two of these are gated on the Toccata hardfork and a wallet
author reading only the pre-fork values will document stale numbers:

- `MAX_SCRIPTS_SIZE_PRE_TOCCATA = 10_000`,
  `MAX_SCRIPTS_SIZE_POST_TOCCATA = 1_000_000`
- `MAX_SCRIPT_ELEMENT_SIZE_PRE_TOCCATA = 520`,
  `MAX_SCRIPT_ELEMENT_SIZE_POST_TOCCATA = 1_000_000`
- `MAX_OPS_PER_SCRIPT_PRE_TOCCATA = 201`,
  `MAX_OPS_PER_SCRIPT_POST_TOCCATA = 1_000_000`
- `MAX_STACK_SIZE = 244` (not gated)
- `MAX_PUB_KEYS_PER_MUTLTISIG = 20` (not gated)

Note the spelling of the last constant: `MUTLTISIG`, a typo in the
upstream source. A wallet author grepping for the correct spelling finds
nothing, which is worth knowing before concluding the limit is
undefined.

A 20-of-20 Schnorr redeem script is `2 + 20*33 + 2 + 1 = 665` bytes,
below even the pre-Toccata script-size limit, so no multisig of
practical size is at risk of script-size rejection under either
regime.

# Acknowledgements

Thanks to Michael Sutton and the `kaspa-wallet-pskt` maintainers for the
upstream PSKT crate this KIP builds on, and to the Kaspa community
members active on hardware wallet support and multisig (the multisig
issue `rusty-kaspa#254` framed the original problem space).

Thanks to Maksim Biryukov (@biryukovmaxim) for review feedback on the
first draft, in particular for correcting the `sigOpCount` rule from a
fixed `N` to the range `M <= sigOpCount <= N` and pointing at the
authoritative `get_sig_op_count` and
`op_check_multisig_schnorr_or_ecdsa` implementations.
