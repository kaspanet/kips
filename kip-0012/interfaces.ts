/**
 * KIP-12 — TypeScript interface definitions.
 *
 * Companion to ../kip-0012.md; these are the interfaces referenced throughout the
 * specification. Zero dependencies; compiles standalone with `tsc --strict --noEmit`.
 * Wallets copy the wallet-side pieces; web apps copy the app-side pieces.
 */


// Communication Events

//Request wallets to announce themselves. Dispatched on `window` by the web app.
export const KIP12_REQUEST_PROVIDER_EVENT = "kaspa:requestProvider" as const;

//Announces the wallet's presence to the web app; `detail` is a frozen `KIP12ProviderDetail`.
export const KIP12_PROVIDER_EVENT = "kaspa:provider" as const;

// Used to send data from the wallet to the web app.
export const KIP12_EVENT_METHOD = "kaspa:event" as const;

export const KIP12_METHODS = [
  "kaspa:connect",
  "kaspa:disconnect",
  "kaspa:requestAccounts",
  "kaspa:chainId",
  "kaspa:getPublicKey",
  "kaspa:send",
  "kaspa:sign",
  "kaspa:broadcast",
  "kaspa:signPersonal",
  "kaspa:sendTransaction",
  "kaspa:signTransaction",
  "kaspa:broadcastTransaction",
  "kaspa:signPskt",
] as const;

export type KIP12Method = (typeof KIP12_METHODS)[number];
export type KIP12EventMethod = typeof KIP12_EVENT_METHOD;


// Interface Definitions


// Hex-encoded bytes / a serialized PSKB, as produced by the WASM SDK.
export type HexString = string;
export type PSKB = string;

export interface KIP12ErrorPayload {
  message: string;
  code?: string | number;
  details?: unknown;
}


// Amounts are encoded as base-10 sompi strings. Floating-point KAS values MUST
// NOT be used on the wire because IEEE-754 can't represent every sompi value
// exactly. Even a small rounding error can change the amount being signed.
export interface KIP12SimpleTransfer {
  to: string;
  amountSompi: string;
}

// Describes an input the wallet should sign, identified by index.
export interface KIP12SignInput {
  index: number;
  sighashType: number;
}

// `signPskt` argument: a Safe-JSON transaction plus the explicit list of inputs to sign.
// A Safe-JSON transaction is the string produced by the WASM SDK's
// `Transaction.serializeToSafeJSON()`; wallets reconstruct it with
// `Transaction.deserializeFromSafeJSON()`.
export interface KIP12SignPsktArg {
  txJsonString: string;
  options: { signInputs: KIP12SignInput[] };
}

export interface KIP12MethodArgs {
  "kaspa:connect": [];
  "kaspa:disconnect": [];
  "kaspa:requestAccounts": [];
  "kaspa:chainId": [];
  "kaspa:getPublicKey": [];
  "kaspa:send": [HexString];
  "kaspa:sign": [PSKB];
  "kaspa:broadcast": [HexString];
  "kaspa:signPersonal": [string];
  "kaspa:sendTransaction": [KIP12SimpleTransfer];
  // safe JSON representation of the Transaction
  "kaspa:signTransaction": [string];
  "kaspa:broadcastTransaction": [HexString];
  "kaspa:signPskt": [KIP12SignPsktArg];
}

export interface KIP12MethodResult {
  "kaspa:connect": string;
  "kaspa:disconnect": string;
  // Returns array of addresses, no popup if already connected. A locked wallet
  // MAY prompt the user to unlock, or reject with 4900.
  "kaspa:requestAccounts": string[];
  // Returns the current network identifier e.g. "mainnet" | "testnet-10" | "testnet-11"
  "kaspa:chainId": string;
  // Active account public key hex
  "kaspa:getPublicKey": HexString;
  "kaspa:send": HexString[];
  "kaspa:sign": HexString;
  "kaspa:broadcast": HexString;
  "kaspa:signPersonal": HexString;
  "kaspa:sendTransaction": HexString;
  "kaspa:signTransaction": HexString;
  "kaspa:broadcastTransaction": HexString;
  // the re-serialized signed Safe-JSON transaction
  "kaspa:signPskt": string;
}

export type KIP12Args<TMethod extends KIP12Method> = KIP12MethodArgs[TMethod];

export type KIP12Result<TMethod extends KIP12Method> =
  KIP12MethodResult[TMethod];

export interface KIP12BaseMessage {
  eventId: string;
  extensionId?: string;
}

export interface KIP12RequestMessage<TMethod extends KIP12Method = KIP12Method>
  extends KIP12BaseMessage {
  method: TMethod;
  args?: KIP12Args<TMethod>;
}

export interface KIP12EventSuccess<TData = unknown> extends KIP12BaseMessage {
  method: KIP12EventMethod;
  data: TData;
  error?: undefined;
}

export interface KIP12EventError extends KIP12BaseMessage {
  method: KIP12EventMethod;
  data?: undefined;
  error: KIP12ErrorPayload;
}

export type KIP12EventMessage<TData = unknown> =
  | KIP12EventSuccess<TData>
  | KIP12EventError;

export type KIP12ExtensionMessage = KIP12RequestMessage | KIP12EventMessage;

export interface KIP12ProviderInfo {
  readonly id: string;
  readonly name: string;
  readonly icon: string;
  readonly methods: readonly KIP12Method[];
  // UUIDv4, freshly generated per page load. Instance identity, used by web apps for dedupe.
  readonly uuid: string;
  // Reverse-DNS id, e.g. "com.kasware". STABLE across page loads; enables session restore.
  readonly rdns?: string;
}

export interface KIP12Provider {
// Core provider methods. Every provider implements `requestAccounts`.
// Everything else is optional, so web apps should check for a method before
// calling it (for example, `typeof provider.signPskt === "function"`).



  requestAccounts(): Promise<string[]>;
  getNetwork?(): Promise<string>;
  getPublicKey?(): Promise<string>;
  signMessage?(message: string): Promise<string>;
  // Sign ONLY the listed inputs; all other inputs stay untouched.
  signPskt?(arg: KIP12SignPsktArg): Promise<string>;
  // Generic escape hatch for current and future protocol methods.
  request?<TMethod extends KIP12Method>(
    method: TMethod,
    args: KIP12Args<TMethod>,
  ): Promise<KIP12Result<TMethod>>;
  connect?(): Promise<void>;
  disconnect?(): Promise<void>;
  on?(event: string, handler: (...args: unknown[]) => void): void;
  removeListener?(event: string, handler: (...args: unknown[]) => void): void;
}


// Provider Info and Multi-Wallet Discovery


// The `detail` of a `kaspa:provider` event is
// `Object.freeze({ info, provider })`.
//
// Freezing the object prevents it from being modified after it's dispatched.
// It does not verify who dispatched the event.



export interface KIP12ProviderDetail {
  readonly info: KIP12ProviderInfo;
  readonly provider: KIP12Provider;
}

declare global {
  interface WindowEventMap {
    "kaspa:provider": CustomEvent<KIP12ProviderDetail>;
    "kaspa:requestProvider": Event;
  }
}


// Network Identifiers


// Network ids are the node's own strings. Some existing injected wallet APIs use
// `kaspa_`-prefixed variants (`kaspa_mainnet`, `kaspa_testnet_10`); adapters SHOULD
// normalize those to the canonical ids.
export const KIP12_NETWORKS = {
  MAINNET: "mainnet",
  TESTNET_10: "testnet-10",
  TESTNET_11: "testnet-11",
  DEVNET: "devnet",
} as const;

export type KIP12NetworkId = (typeof KIP12_NETWORKS)[keyof typeof KIP12_NETWORKS];


// Errors


// Standard codes mirror EIP-1193 so integrators coming from EVM tooling get familiar
// values. A wallet MUST reject an unknown method with 4200 rather than silently
// ignoring it.
export const KIP12_ERRORS = {
  //The user rejected the request.
  USER_REJECTED: 4001,
  //Origin not authorized (connect first).
  UNAUTHORIZED: 4100,
  //Method not supported by this wallet.
  UNSUPPORTED_METHOD: 4200,
  //Wallet locked or unavailable.
  WALLET_UNAVAILABLE: 4900,
} as const;
