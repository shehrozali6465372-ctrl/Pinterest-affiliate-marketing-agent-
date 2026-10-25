# CONTEXT — Pinterest Affiliate Marketing Agent

Last updated: 2026-10-25

## Model 1 architecture
Target audience: USA and UK; home decor and kitchen.
Core flow: product idea/details → image generation → title, description and alt text → affiliate URL → Pinterest API publish → analytics ingestion and measured learning loop.
Stack: FastAPI, Render, Neon PostgreSQL, Pinterest API, Cloudflare Workers AI / Cloudflare Images, DeepSeek.

## Verified current status

### Cloudflare Workers AI — REAL IMAGE GENERATION VERIFIED LOCALLY
- On 2026-10-25, the local Termux script called Cloudflare Workers AI model `@cf/black-forest-labs/flux-1-schnell`.
- The API returned **HTTP 200** with `Content-Type: application/json`.
- The script decoded the returned image data successfully and wrote a real image file of **438,335 bytes** (about 429 KB) to `~/cloudflare-test.png`.
- The image was copied successfully to Android Downloads as `~/storage/shared/Download/cloudflare-test.png` and visually confirmed by the user in the file manager. It depicts a kitchen countertop spice rack with spice jars.
- Conclusion: the Cloudflare token/account configuration used in that local test is valid for this Workers AI inference request, and real image generation works. This confirms image generation only; it does **not** yet verify Cloudflare Images upload, a public HTTPS variant URL, or Pinterest publishing.
- The token was entered through hidden terminal input and is **not stored in this context file**. Never paste credentials into chat, commit them, or print them in logs.

### Remaining verification / blockers
- Test Cloudflare Images upload separately and verify the returned public HTTPS variant URL.
- Confirm the production Render service has matching working Cloudflare credentials and the deployed image-generation path works end-to-end; local success does not automatically prove Render's environment is correct.
- Pinterest account read access was previously verified, but read access does not prove write scopes or a successful Pin publish.
- Do not publish a Pin until the user supplies/confirms their own affiliate URL. Never use an affiliate tag that may belong to another person.
- The real analytics-based Learning Loop is not implemented yet; do not label it as machine learning or report it as working until ingestion, evaluation and persistence are real.
- Do not run billable diagnostic calls or upload public test images without explicit user approval.
- Never claim a Pin was published without a real Pinterest Pin ID and database verification.

## Deployment references
- GitHub repository: https://github.com/shehrozali6465372-ctrl/Pinterest-affiliate-marketing-agent-
- Render service: https://pinterest-affiliate-marketing-agent.onrender.com
- Keep Modern Living Hub service unchanged unless the user explicitly authorizes changes.

## Next steps
1. Run an explicit Cloudflare Images upload test using the already-generated local PNG; confirm upload response and HTTPS variant URL. This may create a public image and incur usage, so obtain approval first.
2. Verify Render environment and image-generation endpoint without exposing secrets.
3. Complete authenticated Pinterest publish test only after the user's affiliate URL is confirmed.
4. Implement real Pinterest analytics ingestion and a measurable learning loop.
