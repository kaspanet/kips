# Kaspa Improvement Proposals (KIPs)

Kaspa Improvement Proposals (KIPs) describe standards for the Kaspa network, including core protocol specifications, client APIs, and network upgrades.

## Table of Contents
- [Contributing](#contributing)
- [KIP Status Terms](#kip-status-terms)
- [Current KIPs](#current-kips)
- [KIP Layers](#kip-layers)

## Contributing

### Before Submitting a KIP
1. **Discuss your idea** with developers
2. **Check for duplicates** - ensure your proposal doesn't overlap with existing KIPs

### Submission Process
1. Fork the [KIPs repository](https://github.com/kaspanet/kips)
2. Fill out all sections of the template including:
   - KIP number XXXX
   - Layer (Consensus, Network, API/RPC, etc.)
   - Title
   - Author(s)
   - Specification
3. Submit a Pull Request to the KIPs repository

## KIP Status Terms
- **Proposed** - Initial proposal stage, open for discussion
- **Draft** - Under active development and revision
- **Active** - Approved and awaiting implementation
- **Implemented** - Completed and deployed on mainnet
- **Rejected** - Not approved for implementation
- **Withdrawn** - Author has withdrawn the proposal

## Current KIPs

| Number | Layer | Title | Status |
|--------|-------|-------|--------|
| [KIP-1](https://github.com/kaspanet/kips/blob/master/kip-0001.md) | Meta | KIP Purpose and Guidelines | Implemented |
| [KIP-2](https://github.com/kaspanet/kips/blob/master/kip-0002.md) | Consensus (hard fork), API/RPC | Upgrade consensus to follow the DAGKNIGHT protocol | Proposed |
| [KIP-3](https://github.com/kaspanet/kips/blob/master/kip-0003.md) | Consensus | Block Header Format | Rejected |
| [KIP-4](https://github.com/kaspanet/kips/blob/master/kip-0004.md) | Consensus | Transaction Serialization | Implemented |
| [KIP-5](https://github.com/kaspanet/kips/blob/master/kip-0005.md) | Application | Address Format | Implemented |
| [KIP-6](https://github.com/kaspanet/kips/blob/master/kip-0006.md) | Consensus | Difficulty Adjustment Algorithm | Implemented |
| [KIP-7](https://github.com/kaspanet/kips/blob/master/kip-0007.md) | Network | P2P Network Protocol | Draft |
| [KIP-8](https://github.com/kaspanet/kips/blob/master/kip-0008.md) | API/RPC | RPC API Standards | Active |
| [KIP-9](https://github.com/kaspanet/kips/blob/master/kip-0009.md) | Consensus | Block Pruning Specification | Draft |
| [KIP-10](https://github.com/kaspanet/kips/blob/master/kip-0010.md) | Consensus | UTXO Commitment Scheme | Active |
| [KIP-11](https://github.com/kaspanet/kips/blob/master/kip-0011.md) | Consensus | Transaction Script Opcodes | Draft |
| [KIP-12](https://github.com/kaspanet/kips/blob/master/kip-0012.md) | Application | Wallet Interoperability Standards | Draft |
| [KIP-13](https://github.com/kaspanet/kips/blob/master/kip-0013.md) | Consensus | Consensus Parameter Adjustments | Active |
| [KIP-14](https://github.com/kaspanet/kips/blob/master/kip-0014.md) | Meta | Network Upgrade Process | Draft |
| [KIP-15](https://github.com/kaspanet/kips/blob/master/kip-0015.md) | Consensus | Miner Signaling Mechanism | Draft |

## KIP Layers
The layer classification is derived from each KIP's header section. Current layers include:

- **Consensus**: Changes to core protocol rules (e.g., KIP-2, KIP-3, KIP-6)
- **Network**: P2P network layer modifications (e.g., KIP-7)
- **API/RPC**: Interface specifications (e.g., KIP-8)
- **Application**: Wallet/application-level standards (e.g., KIP-5, KIP-12)
- **Meta**: Process proposals about KIPs themselves (e.g., KIP-1, KIP-14)

Note: Some KIPs may span multiple layers (e.g., KIP-2 covers both Consensus and API/RPC)
