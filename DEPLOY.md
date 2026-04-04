# VERA Research Portal — Deployment Guide
## jeremy.h-edu.solutions

---

## Step 1 — Render: Create the Web Service

1. Go to dashboard.render.com
2. Click **New +** → **Web Service**
3. Choose **Connect a repository** → select **briandemsey/vera-research-portal**
4. Render will auto-detect render.yaml. Confirm these settings:
   - Name: `vera-research-portal`
   - Runtime: Python
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Click **Create Web Service**

---

## Step 2 — Render: Set Environment Variables

In the Render dashboard for vera-research-portal → **Environment** tab → add these three:

| Key | Value |
|---|---|
| SUPABASE_URL | (get from Brian) |
| SUPABASE_SECRET_KEY | (get from Brian) |
| ANTHROPIC_API_KEY | (get from Brian) |

Click **Save Changes**. Render will redeploy automatically.

---

## Step 3 — Render: Add Custom Domain

1. In Render dashboard → vera-research-portal → **Settings** → **Custom Domains**
2. Click **Add Custom Domain**
3. Type: `jeremy.h-edu.solutions`
4. Render will show you a CNAME value — copy it (looks like `vera-research-portal.onrender.com`)

---

## Step 4 — GoDaddy: Add DNS Record

1. Log into GoDaddy → your h-edu.solutions domain → **DNS**
2. Click **Add New Record**
3. Set:
   - Type: **CNAME**
   - Name: `jeremy`
   - Value: paste the Render URL from Step 3 (e.g. `vera-research-portal.onrender.com`)
   - TTL: 600
4. Click **Save**

DNS propagates within 5–30 minutes.

---

## Step 5 — Verify

Visit https://jeremy.h-edu.solutions

You should see the VERA Research Portal dashboard. Click any district in the sidebar
and confirm data loads. Type a question in the AI chat panel and confirm a response.

---

## Ongoing: Updating the Portal

Any future changes work like this:
1. Make changes to the code
2. Commit and push to GitHub (briandemsey/vera-research-portal)
3. Render automatically detects the push and redeploys within ~2 minutes
4. No DNS changes needed — the domain stays pointed at Render permanently
