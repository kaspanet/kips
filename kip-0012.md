```
KIP: 12
Layer: 		WASM32 Wallet SDK, Browser Extension Wallet APIs
Title: 		Specification for Browser Extension Wallet APIs
Authors: 	@aspect, @starkbamse, @KaffinPX, @mattoo
Status: 	DRAFT / WIP
```

# Motivation

There are several emerging Browser Extension Wallet standards for interfacing with Kaspa ecosystem web applications. This KIP looks to standardize the methodology, by which wallets expose themselves to and communicate with web applications.
In addition, this KIP aims to provide a common way for wallets to expose their capabilities related to the ability to perform different functions (for example, support PSKTs) and support different emerging protocols including but not limited to:
- KRC-20 protocol by Kasplex
- KSC protocol (future Sparkle Smart Contract assets)
This document is loosely based on [EIP-6963](https://eips.ethereum.org/EIPS/eip-6963) in the Ethereum ecosystem

# Specification
The key words “MUST”, “MUST NOT”, “REQUIRED”, “SHALL”, “SHALL NOT”, “SHOULD”, “SHOULD NOT”, “RECOMMENDED”, “MAY”, and “OPTIONAL” in this document are to be interpreted as described in [RFC-2119](https://datatracker.ietf.org/doc/html/rfc2119).

# Definitions

## Wallet
An browser-compatible extension that has a non-exclusive functionality of storing funds in one way or the other on the Kaspa blockchain. Examples of these are: Chrome Extensions, Firefox Extensions.

## Web App
An application accessible via a web browser that aims to somehow utilize the funds stored in the [wallet](#wallet), in order to provide some functionality to the end user of the web app. 

# Contents

## Icons/Images
The icon string MUST be a data URI as defined in [RFC-2397](https://datatracker.ietf.org/doc/html/rfc2397). The image SHOULD be a square with 96x96px minimum resolution. The image format is RECOMMENDED to be either lossless or vector-based such as PNG, WebP, or SVG to make the image easy to render on the Web App. Since SVG images can execute Javascript, applications and libraries MUST render SVG images using the <img> tag to ensure no untrusted Javascript execution can occur.

## Default/Initial behavior
The wallet MUST NOT react to ANY requests except the [kaspa:connect](#kaspaconnect) event. Only after an explicit connection request MAY the wallet react to subsequent requests made by the [Web App](#web-app).

## Window Events

### General
In order to prevent race conditions and collisions between providers, Web Apps and wallets must interact via an event concurrency loop. This involves emitting and listening to events using `window.dispatchEvent` and `window.addEventListener`.

**ALL** events should be instances of the [`CustomEvent`](https://developer.mozilla.org/en-US/docs/Web/API/CustomEvent/CustomEvent) object. The type property of the object **MUST** be the identifier of the event, and detail **MUST** include the contents of the Kaspa event.

```typescript
new CustomEvent(type, {"detail":eventData})
```

## Provider Events
This section contains all the events that are part of this KIP as well as their specified content, with description of the expected behavior.

### `kaspa:provider`

```
Sender: Wallet
Purpose: Allow Web App to discover the wallet.
```

```typescript
interface KaspaProviderDetail {
  info: KaspaProviderInfo
  provider: KaspaProvider
}

interface KaspaProviderInfo {
  id: string;
  name: string;
  icon: string;
  capabilities: Capability[] 
}

interface Capability {
  protocol: string; // Protocol name, e.g. "KASPA", "KRC-20", "KSC"
  methods: string[]; // Array of method names in kebab-case : "get-account", "send", "sign-message
}


interface KaspaProvider {
  request: (args:Request)=>Promise<unknown>;
  connect: ()=>Promise<void>;
  disconnect(): ()=>Promise<void>;
}

interface Request {
  protocol: string,
  method: string,
  params: Object
}

interface Request {
  protocol: string,
  method: string,
  params: Object
}

interface Event {
  eventId:string, // UUID as [0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}
  extensionId:string, // `browser.runtime.id`
  data:Request,
  error:string | undefined
}

async function request(request:Request):Promise<unknown>{
  const requestEvent = new CustomEvent("kaspa:invoke", {
      detail: Object.freeze({
        eventId: uuidv4(),
        extensionId: browser.runtime.id,
        data: request,
        error: undefined,
      })
    }
  );

  window.dispatchEvent(requestEvent);

  return new Promise((resolve, reject) => {
    window.addEventListener("kaspa:event", (event: Event) => {
      if (event.eventId === request.eventId) {
        if (event.error) {
          reject(event.error);
        } else {
          resolve(event.data);
        }
      }
    });
  });
}

async function connect():Promise<void>{
  const connectEvent = new CustomEvent("kaspa:connect", {
    detail: Object.freeze({
      eventId: uuidv4(),
      extensionId: browser.runtime.id,
    }),
  });

  window.dispatchEvent(connectEvent);

  return new Promise((resolve, reject) => {
    window.addEventListener("kaspa:event", (event: Event) => {
      if (event.eventId === connectEvent.eventId) {
        if (event.error) {
          reject(event.error);
        } else {
          resolve();
        }
      }
    });
  });
}

async function disconnect():Promise<void>{
  const disconnectEvent = new CustomEvent("kaspa:disconnect", {
    detail: Object.freeze({
      eventId: uuidv4(),
      extensionId: browser.runtime.id,
      reason: "User initiated",
    }),
  });

  window.dispatchEvent(disconnectEvent);

  return new Promise((resolve, reject) => {
    window.addEventListener("kaspa:event", (event: Event) => {
      if (event.eventId === disconnectEvent.eventId) {
        if (event.error) {
          reject(event.error);
        } else {
          resolve();
        }
      }
    });
  });
}
```

### `kaspa:connect`

```
Sender: Web app
Purpose: Establish a connection between the Web App and the wallet, allowing further communication.
```
```typescript
interface Connect {
  eventId:string, // UUID as [0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12
  extensionId:string, // `browser.runtime.id`
}
```

### `kaspa:event`

```
Sender: Wallet
Purpose: Used to send data from the wallet to the web app.
```


```typescript
interface Response {
  protocol: string,
  data: any
}

interface Event {
  eventId:string, // UUID as [0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}
  extensionId:string, // `browser.runtime.id`
  data:Response,
  error:string | undefined
}
```

### `kaspa:disconnect`

```
Sender: Wallet or Web App
Purpose: To signal to the corresponding party that a connection has been terminated from the sending part, and that the sender party will no longer respond to requests nor react to any kind of data transmitted by the sender.
```

```typescript
interface Disconnect {
  eventId:string, // UUID as [0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12
  extensionId:string, // `browser.runtime.id`
  reason:string
}
```


### `kaspa:requestProvider`

```
Sender: Web App
Purpose: To request wallets to announce themselves by emitting the kaspa:provider event.
```

```typescript
// No additional data
```


### `kaspa:invoke`
Sent by the Web App, contains a request that the wallet needs to handle. It allows the Web App to invoke specific actions or requests in the wallet.
This event contains a Request object that the wallet needs to handle. The Request includes an id, protocol, method, and params, which define the specific action or request the Web App is invoking in the wallet.

```
Sender: Web App
Purpose: Used internally, by the provided request() method to request the wallet for a specific action. Not intended for direct usage.
```

```typescript
interface Request {
  protocol: string,
  method: string,
  params: Object
}

interface Event {
  eventId:string, // UUID as [0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}
  extensionId:string, // `browser.runtime.id`
  data:Request,
  error:string | undefined
}
```
