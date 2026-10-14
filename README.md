# The Daily

A personal newspaper, built every morning at 5 AM Eastern from free news feeds.

## Change sources
Edit `feeds.yaml`. You can do this right on github.com (pencil icon), even from your phone. The next edition uses it.

## Run locally
```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m paper.check_feeds          # is every feed working?
python -m paper.build --out site --editions /tmp/preview-editions
open site/index.html
pytest                               # tests
```

## One-time GitHub setup
1. Create a **public** repo named `daily-paper` and push this folder to it.
2. Settings → Pages → Build and deployment → Source: **GitHub Actions**.
3. Settings → Actions → General → Workflow permissions: **Read and write permissions** → Save.
4. Actions tab → **Daily edition** → **Run workflow**.
5. Your paper is at `https://<your-username>.github.io/daily-paper/`.

## Put it on your devices
- **iPhone / iPad:** open the address in Safari → Share → **Add to Home Screen**.
- **Mac:** open it in Safari → File → **Add to Dock**.

## If something breaks
GitHub emails you when a build fails, and yesterday's paper stays up. Open the Actions tab and select the failed run; the build report lists any broken feeds.
