# Orbix Health

Orbix is a multilingual health support platform with AI chat, medical lookup, and a toll-free healthcare support flow designed for rural users without smartphones.

## What is ready now
- AI symptom guidance and red-flag detection
- Multilingual support for Hindi, Odia, English, Spanish, and French
- Toll-free health triage flow with emergency escalation
- Twilio-compatible voice IVR endpoints
- SQLite-backed call history with an admin dashboard
- Live-call monitoring page at `/page/call-center`

## Twilio integration setup
1. Copy `Twilio.env.example` to `Twilio.env`.
2. Fill in your real Twilio values:
   - `TWILIO_ACCOUNT_SID`
   - `TWILIO_AUTH_TOKEN`
   - `TWILIO_PHONE_NUMBER`
   - `BASE_URL`
3. Use the public HTTPS domain, not localhost. Example:
   `https://orbix-health.ngrok.app` or `https://your-app-name.azurewebsites.net`
4. Start the Flask app with those variables loaded.
5. Expose the app publicly with `ngrok http 5000` or deploy it to Azure App Service.
6. In Twilio, set the phone webhook to:
   `https://your-public-domain.example/api/twilio/voice`
7. In Twilio, configure the IVR callback endpoints as:
   - `https://your-public-domain.example/api/twilio/voice/handle`
   - `https://your-public-domain.example/api/twilio/voice/final`
8. Use the same public URL for all IVR callbacks and keep `BASE_URL` aligned with the live domain.

### Twilio Video setup
1. In Twilio Console, create a Video API key and secret.
2. Add `TWILIO_API_KEY_SID` and `TWILIO_API_KEY_SECRET` to `Twilio.env`.
3. Install the Python dependency with `pip install -r requirements.txt`.
4. Open Care Hub, create a `Video consultation` request, and use `Join video` from the request history.
5. The patient and care provider must join the same consultation room. The browser needs camera and microphone permission and a public HTTPS deployment.

The server never sends the Twilio API secret to the browser. It issues a short-lived room token through `/api/teleconsult/<request_id>/video-token` only for an active video request.

## Final live webhook checklist
- Voice webhook: `https://your-public-domain.example/api/twilio/voice`
- Handle webhook: `https://your-public-domain.example/api/twilio/voice/handle`
- Final webhook: `https://your-public-domain.example/api/twilio/voice/final`
- Phone number format: E.164 like `+91XXXXXXXXXX` or `+1XXXXXXXXXX`
- Make sure the domain is HTTPS and publicly reachable.
- Test the URL in a browser once: it should return TwiML/XML, not a 404 or HTML page.

## Local run
```bash
cd orbix
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy Twilio.env.example Twilio.env
python app.py
```
Open `http://localhost:5000` and sign in.

## Production deployment notes
### Ngrok
```bash
ngrok http 5000
```
Use the HTTPS URL shown by ngrok as `BASE_URL` and as your Twilio webhook host.

### Azure App Service
1. Create an App Service for this Flask project.
2. Add the same environment variables in App Service settings.
3. Set `BASE_URL` to the public website URL.
4. Register the Twilio webhook to the App Service URL.

## Call center dashboard
Open the admin page here after login:
`/page/call-center`
This page lists recent emergency calls and all saved call records.

## Backend call log storage
The app stores call records in a SQLite table called `tollfree_calls` by default. If `DATABASE_URL` is configured, it will prefer PostgreSQL instead.

## Emergency workflow
- User calls the toll-free number.
- IVR welcomes them and asks for a language.
- User describes the problem by voice or keypad selection.
- Flask checks the problem for emergency signals.
- If emergency symptoms are found, the system returns an emergency message and flags the record as high priority.

## Multi-language IVR script
- English: press `1`
- Hindi: press `2`
- Odia: press `3`
- Spanish: press `4`
- French: press `5`

## Key routes
- `/api/tollfree` — toll-free health triage
- `/api/tollfree/logs` — recent call history
- `/api/call-records` — admin summary data for dashboard
- `/api/phone/ivr` — Twilio IVR entry point
- `/api/twilio/voice` — Twilio voice webhook alias
- `/api/phone/ivr/handle` — IVR handling after user input
- `/api/phone/ivr/final` — final IVR outcome

## Notes
The Groq API key remains server-side in `app.py`; browser code never receives it.
