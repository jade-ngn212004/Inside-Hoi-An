# The AI backend

## Why this exists

The app POSTs to three endpoints:

| endpoint | sends | expects back |
|---|---|---|
| `api/ai/guide-chat` | `{ message, chatHistory, language }` | `{ reply }` |
| `api/ai/translate` | `{ text, sourceLanguage, targetLanguage, mode }` | `{ translatedText, pronunciation, ... }` |
| `api/ai/plan-itinerary` | `{ days, vibe, group, pace, language }` | `{ title, summary, stops, daysPlan, ... }` |

GitHub Pages is a **static** host. It answers GET and HEAD, and returns **405 Method Not
Allowed** to a POST. That is the whole reason the concierge replies "Em An is momentarily
busy" on the live site. Nothing is broken in the app; there is simply no server behind it.

Verified on the live site: `POST api/ai/guide-chat` returns 405, and the app falls back
gracefully rather than crashing.

`inside-hoi-an-ai.js` is that missing server, as a Cloudflare Worker. It holds the Gemini
key server-side, so the key never reaches the browser.

## Deploy it

You need a Cloudflare account (the free tier is enough) and a **real** Gemini API key from
<https://aistudio.google.com/apikey>. The key in `.env.local` is a placeholder.

```bash
cd worker
npx wrangler login
npx wrangler secret put GEMINI_API_KEY     # paste the key when prompted
npx wrangler deploy
```

Wrangler prints a URL like `https://inside-hoi-an-ai.<your-subdomain>.workers.dev`.

## Point the app at it

Edit **`dist/ai-config.js`**, one line:

```js
window.__AI_ENDPOINT = "https://inside-hoi-an-ai.YOUR-SUBDOMAIN.workers.dev";
```

Commit and push. The Pages workflow redeploys and the concierge starts answering.

Leaving it empty keeps today's behaviour exactly, so this is safe to ship unconfigured.

## How the routing works

`dist/index.html` patches `window.fetch`. When `__AI_ENDPOINT` is set, any request whose URL
contains `api/ai/` is sent to that origin instead. Everything else, including
`api/bookings`, is untouched. No change to the compiled bundle was needed.

## Check it worked

```bash
curl -X POST https://YOUR-WORKER.workers.dev/api/ai/guide-chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Where should I eat cao lau?","chatHistory":[],"language":"en"}'
```

You should get `{"reply":"..."}`. Common failures:

| response | meaning |
|---|---|
| `{"error":"GEMINI_API_KEY is not set on the Worker"}` | the secret was never set |
| `{"error":"Gemini 400: ..."}` | bad or restricted key |
| `{"error":"Gemini 429: ..."}` | out of quota |
| CORS error in the browser | `ALLOWED_ORIGINS` in `wrangler.toml` does not list your site |

## Cost and abuse

Gemini Flash is cheap but not free at volume, and this Worker sits on the public internet.
`ALLOWED_ORIGINS` restricts which sites may call it, which stops casual misuse but not a
determined one, since an origin header can be forged. If this ever goes beyond a demo, add
rate limiting per IP and consider restricting the Gemini key by referrer in Google Cloud.
