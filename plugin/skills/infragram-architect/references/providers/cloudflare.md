# Cloudflare library

Load this reference when a diagram uses Cloudflare edge or developer-platform
services. The theme is [`cloudflare.json`](../../assets/themes/cloudflare.json)
(`theme="cloudflare"`). Coverage: **reviewed** - the library offers the four
Cloudflare product marks beside 33 service tiles (below), 37 components in
nine categories:

- **Cloudflare** - DNS, WAF, CDN, bot protection, and edge (`cloudflare:cloudflare`)
- **Cloudflare Workers** - edge serverless runtime (`cloudflare:workers`)
- **Cloudflare Pages** - edge web hosting (`cloudflare:pages`)
- **Cloudflare Workers AI** - edge inference (`cloudflare:workers-ai`)

In Python the marks and the tiles share one package, in the same categories
the sidebar uses: `cloudflare.compute.Workers` and `cloudflare.security.WAF`
compose the same way, and `cloudflare.WAF` finds the class without naming the
category.

## Frames

Cloudflare's frames are ownership boundaries, not placement: an edge network
has no regions or subnets to draw, so place Cloudflare components where
traffic enters - outside the cloud or site frame they front - and connect
them with `solid` or `dashed` links into the origin.

| Frame | Holds |
|---|---|
| Cloudflare account | Zones, and the global network frame |
| Cloudflare zone | One domain: its DNS records, WAF and CDN behaviour |
| Cloudflare global network | Workers, Pages and Workers AI, which are account-scoped |

The starter stack is Account → zone. `cloudflare-edge-platform` is the
shipped worked example: a zone in front of an on-premises origin reached
through a tunnel.

## Artwork

Preserve Cloudflare product colors and proportions. Do not use the generic
Cloudflare mark when a specific product (Workers, Pages, Workers AI) is known,
and never infer that a Cloudflare capability is deployed because its component
exists in the library.

## Terms

Cloudflare product marks. Cloudflare trademark terms apply.

## Service tiles

Beside the four product marks, 33 service tiles drawn for this
project (a white glyph on Cloudflare orange; this repository's own artwork, not
Cloudflare's icons) cover the rest of the platform:

| Component | Category | Id |
|---|---|---|
| Cloudflare DNS | networking | `cloudflare:dns` |
| Cloudflare CDN | networking | `cloudflare:cdn` |
| Web Application Firewall | security | `cloudflare:waf` |
| DDoS Protection | security | `cloudflare:ddos-protection` |
| Load Balancing | networking | `cloudflare:load-balancing` |
| Cloudflare Tunnel | networking | `cloudflare:tunnel` |
| Zero Trust Access | security | `cloudflare:zero-trust-access` |
| Zero Trust Gateway | security | `cloudflare:zero-trust-gateway` |
| WARP Client | security | `cloudflare:warp-client` |
| Cloudflare R2 | storage | `cloudflare:r2` |
| Cloudflare D1 | databases | `cloudflare:d1` |
| Workers KV | databases | `cloudflare:kv` |
| Durable Objects | databases | `cloudflare:durable-objects` |
| Hyperdrive | databases | `cloudflare:hyperdrive` |
| Vectorize | ai-machine-learning | `cloudflare:vectorize` |
| AI Gateway | ai-machine-learning | `cloudflare:ai-gateway` |
| Cloudflare Queues | integration | `cloudflare:queues` |
| Email Routing | integration | `cloudflare:email-routing` |
| Cloudflare Stream | web | `cloudflare:stream` |
| Cloudflare Images | web | `cloudflare:images` |
| Cloudflare Registrar | networking | `cloudflare:registrar` |
| Spectrum | networking | `cloudflare:spectrum` |
| Magic WAN | networking | `cloudflare:magic-wan` |
| Magic Transit | networking | `cloudflare:magic-transit` |
| Argo Smart Routing | networking | `cloudflare:argo-smart-routing` |
| Rate Limiting | security | `cloudflare:rate-limiting` |
| API Shield | security | `cloudflare:api-shield` |
| Bot Management | security | `cloudflare:bot-management` |
| Turnstile | security | `cloudflare:turnstile` |
| Logpush | analytics | `cloudflare:logpush` |
| Web Analytics | analytics | `cloudflare:web-analytics` |
| Cron Triggers | compute | `cloudflare:workers-cron` |
| Browser Rendering | compute | `cloudflare:browser-rendering` |
