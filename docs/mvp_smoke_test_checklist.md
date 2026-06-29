# MVP Smoke Test Checklist

Use this checklist before internal demo, handoff, or release review.

## 1. Start Mock Service

```bash
unset OPENAI_API_KEY
unset OPENAI_MODEL
CONTENT_FACTORY_PROVIDER=mock python3 -m content_factory.api --host 127.0.0.1 --port 8000
```

## 2. Homepage

1. Open `http://127.0.0.1:8000/`.
2. Confirm `Internal Workflow Navigation` appears.
3. Confirm the following buttons still exist:
   - `Use Spikex Brazil Profile`
   - `Spikex Brazil Demo`
   - `BLOCKED Risk Demo`
   - `Clear Form`

## 3. Generate Creatives

1. Click `Use Spikex Brazil Profile`.
2. Click generate.
3. Confirm status is `GENERATED`.
4. Confirm 5 creative cards are shown.
5. Confirm every card has a Creative ID such as `SPK-BR-FB-...-C001`.
6. Confirm `Creative Brief Markdown` appears.
7. Confirm `Media Buyer Launch Brief` appears.
8. Confirm copy buttons are available.

## 4. Generation History

1. Open `/history`.
2. Confirm the generated record appears.
3. Open the generation detail.
4. Confirm Creative Brief, Media Buyer Launch Brief, Creative ID and Raw JSON are visible.

## 5. Performance CSV Analyzer

1. Open `/performance`.
2. Confirm `Sample CSV` appears.
3. Copy or use the sample CSV.
4. Paste it into the analyzer textarea.
5. Click `Analyze Performance`.
6. Confirm `Saved Performance Report` appears.
7. Confirm `Creative Performance Table` appears.
8. Confirm `Copy Performance Summary` appears.

## 6. Performance Reports

1. Open `/performance/history`.
2. Confirm the saved report appears.
3. Open the report detail.
4. Confirm `Summary`.
5. Confirm `Creative Performance Table`.
6. Confirm `Internal Action Notes`.
7. Confirm `Next Round Creative Recommendations`.
8. Confirm `Copy Next Round Plan`.
9. Confirm `Next Round Creative Brief Request`.
10. Confirm `Copy Next Round Request`.
11. Confirm `Suggested Naming` contains `V2A` or `RECUT-V2A`.

## 7. Stop Service

Stop the local process with `Ctrl-C`.

## 8. Automated Verification

```bash
unset OPENAI_API_KEY
unset OPENAI_MODEL
CONTENT_FACTORY_PROVIDER=mock PYTHONPYCACHEPREFIX=/private/tmp/codex_pycache python3 -m unittest discover -v

PYTHONPYCACHEPREFIX=/private/tmp/codex_pycache python3 -m compileall content_factory tests
```
