# Deploy AquaSentinel on Render

Follow these steps to host AquaSentinel on Render and configure your Gemini API key.

---

## 1. Push your code to GitHub

- Create a repo (e.g. `aquasentinel`) and push your **Aqua-Sentinel** folder contents.
- Or push the whole project and use the **Root Directory** option in Render (see step 3).

---

## 2. Create a Web Service on Render

1. Go to [render.com](https://render.com) and sign in (or sign up with GitHub).
2. Click **New +** → **Web Service**.
3. Connect your GitHub account if needed, then select the repository that contains AquaSentinel.
4. If the app lives in a subfolder (e.g. `Aqua-Sentinel`), set **Root Directory** to that folder (e.g. `Aqua-Sentinel`).

---

## 3. Configure Build & Start

Use these exactly (or leave default if you use **render.yaml**):

| Setting        | Value                                      |
|---------------|--------------------------------------------|
| **Runtime**   | Python                                     |
| **Build Command** | `pip install -r requirements.txt`     |
| **Start Command** | `gunicorn app:app`                     |

---

## 4. How to give / set the API key (Gemini)

Render uses **Environment Variables** for secrets like your Gemini API key.

### Option A: In the Render Dashboard (recommended)

1. Open your **Web Service** on Render.
2. Go to the **Environment** tab.
3. Click **Add Environment Variable**.
4. Add:

   | Key             | Value                          |
   |-----------------|--------------------------------|
   | `GEMINI_API_KEY` | `your-actual-gemini-api-key`  |

5. Paste your [Google AI Studio](https://aistudio.google.com/apikey) API key as the value.
6. Click **Save Changes**. Render will redeploy with the new variable.

### Option B: Using render.yaml (Blueprint)

In your repo you **must not** put the real key in the file. In `render.yaml` you can leave:

```yaml
- key: GEMINI_API_KEY
  sync: false
```

Then in the Dashboard → **Environment**, add `GEMINI_API_KEY` and paste the key there.  
Blueprint deployments will pick it up.

---

## 5. Optional: Secret key and database

- **SECRET_KEY**  
  For production, set a long random string in **Environment** (e.g. `SECRET_KEY`).  
  If you use the Blueprint with `generateValue: true`, Render can create one for you.

- **Persistent database (PostgreSQL)**  
  - In Render: **New +** → **PostgreSQL** (free plan is fine).  
  - In the new database, copy the **Internal Database URL**.  
  - In your Web Service → **Environment**, add:
    - **Key:** `DATABASE_URL`  
    - **Value:** paste the Internal Database URL  
  The app already uses `DATABASE_URL` when set; otherwise it uses SQLite (data may not persist on free tier).

---

## 6. Deploy

- Click **Create Web Service** (or **Save** if you only changed environment variables).
- Wait for the build and deploy to finish.
- Your app will be at a URL like: `https://aquasentinel-xxxx.onrender.com`

---

## Summary: Giving the API key on Render

1. Dashboard → your **Web Service**.
2. **Environment** tab.
3. **Add Environment Variable**: key = `GEMINI_API_KEY`, value = your Gemini API key.
4. Save; Render redeploys automatically.

Never commit the real API key to Git or put it in `render.yaml`; always use Environment variables.
