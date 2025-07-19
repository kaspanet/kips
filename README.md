# Kaspa Improvement Proposals (KIPs)

Kaspa Improvement Proposals (KIPs) describe standard proposals for the Kaspa network, including core protocol specifications, network upgrades and client APIs.

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

| Number | Layer | Title | Owner | Status |
|--------|-------|-------|--------|--------|
| [1](kip-0001.md) | Consensus, Node | Rewriting the Kaspa Full-Node in the Rust Programming Language | Michael Sutton, Ori Newman | Implemented |
| [2](kip-0002.md) | Consensus, API/RPC | Upgrade consensus to follow the DAGKNIGHT protocol | Yonatan Sompolinsky, Michael Sutton | Proposed |
| [3](kip-0003.md) | Consensus | Block sampling for efficient DAA with high BPS | Shai Wyborski, Michael Sutton | Rejected |
| [4](kip-0004.md) | Consensus | Sparse Difficulty Windows | Shai Wyborski, Michael Sutton, Georges Künzli | Active |
| [5](kip-0005.md) | Applications | Message Signing | coderofstuff | Active |
| [6](kip-0006.md) | Consensus, Applications | Proof of Chain Membership (PoChM) | Shai Wyborski | Draft |
| [9](kip-0009.md) | Consensus, Mempool, P2P | Extended mass formula for mitigating state bloat | Michael Sutton, Ori Newman, Shai Wyborski, Yonatan Sompolinsky | Active |
| [10](kip-0010.md) | Consensus, Script Engine | New Transaction Opcodes for Enhanced Script Functionality | Maxim Biryukov, Ori Newman | Active |
| [13](kip-0013.md) | Consensus | Transient Storage Handling | Michael Sutton, coderofstuff | Active |
| [14](kip-0014.md) | Consensus | The Crescendo Hardfork | Michael Sutton | Active |
| [15](kip-0015.md) | Consensus | Canonical Transaction Ordering and Sequencing Commitments | Mike Zak, Ro Ma | Active |

## KIP Layers
The layer classification is derived from each KIP's header section. Current layers include:

- **Consensus**: Changes to core protocol rules (e.g., KIP-2, KIP-3, KIP-6)
- **Network**: P2P network layer modifications (e.g., KIP-7)
- **API/RPC**: Interface specifications (e.g., KIP-8)
- **Application**: Wallet/application-level standards (e.g., KIP-5, KIP-12)
- **Meta**: Process proposals about KIPs themselves (e.g., KIP-1, KIP-14)

Note: Some KIPs may span multiple layers (e.g., KIP-2 covers both Consensus and API/RPC)
