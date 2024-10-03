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
  capabilities: string[]
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


# KaspaProviderDetail
`KaspaProviderDetail` is an object that MUST include the following 

```typescript
interface KaspaProviderDetail {
info: KaspaProviderInfo
provider: KaspaProvider
}
```



# `KaspaProvider`



# `KaspaProviderInfo`
`id` (unique extension identifier, typically a UUID or an ID accessible from the extension as `browser.runtime.id`)
`name : string`
`icon : string`
`capabilities : string[]`



# The connect method

function connect(){
    emit connect event
    wait for response
    resolve or reject promise
}
# The disconnect method

function disconnect(){
    emit disconnect event
    wait for response
    resolve or reject promise
}



# The request method
The request method should have extension id hardcoded
function request() {
    emit invoke event
    wait for response
    resolve or reject promise
}


Wallet Capabilities Object
Wallet capabilities object is comprised of keys and values where the key is the protocol name and the value is the string array of the protocol-specific API methods.  API method names MUST be specified in "kebab-case" format.
```typescript
capabilities : {
	"KASPA" : ["get-account", "send", "sign-message"],
	"KRC-20" : ["get-account", "send", "mint", "deploy"],
	"KSC" : ["execute"]
}
```
Note about messages transmitted between extensions and clients: ALL messages transmitted to an extension should be accompanied by an id property containing a unique ID, in the event of a response from an extension the response MUST reference the initial ID sent by the client.

```typescript
request = {
  protocol : "KASPA",
  method : "send",
  params : [
    "kaspa:...",
    "123.45",
    "1.0"
  ]
}
```




```typescript
let info: KaspaProviderInfo;
let provider: KaspaProvider;
const announceEvent: KaspaAnnounceProviderEvent = new CustomEvent(
  "kaspa:announceProvider",
  { detail: Object.freeze({ info, provider }) }
);
// The Wallet dispatches an announce event which is heard by
// the Web App code that had run earlier
window.dispatchEvent(announceEvent);
// The Wallet listens to the request events which may be
// dispatched later and re-dispatches the `EIP6963AnnounceProviderEvent`
window.addEventListener("kaspa:requestProvider", () => {
  window.dispatchEvent(announceEvent);
});
```
```typescript
// The Web App listens to announced providers
window.addEventListener(
  "kaspa:announceProvider",
  (event: KaspaAnnounceProviderEvent) => {}
);
// The Web App dispatches a request event which will be heard by 
// Wallets' code that had run earlier
window.dispatchEvent(new Event("kaspa:requestProvider"));
```
```typescript
function onPageLoad() {

  function announceProvider() {
    const info: KaspaProviderInfo = {
	      uuid: "eccb1a1a-9e1b-43ea-bf3e-915f8f9de7c6",
	      name: "Example Wallet",
      	icon: "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg'/>",
	};
    window.dispatchEvent(
      new CustomEvent("kaspa:provider", {
        detail: Object.freeze({ info, provider }),
      })
    );
  }

  window.addEventListener(
    "kaspa:requestProvider",
    (event: KaspaRequestProviderEvent) => {
      announceProvider();
    }
  );
  announceProvider();
}

```
