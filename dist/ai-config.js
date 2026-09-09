/**
 * Where the AI features send their requests.
 *
 * The app POSTs to api/ai/guide-chat, api/ai/translate and api/ai/plan-itinerary.
 * GitHub Pages is a static host and answers POST with 405, which is why the
 * concierge says "Em An is momentarily busy" there.
 *
 * Deploy worker/inside-hoi-an-ai.js (see worker/README.md), then paste its URL
 * below. Leave it empty to keep the current same-origin behaviour.
 *
 *   window.__AI_ENDPOINT = "https://inside-hoi-an-ai.YOUR-SUBDOMAIN.workers.dev";
 */
window.__AI_ENDPOINT = "";
