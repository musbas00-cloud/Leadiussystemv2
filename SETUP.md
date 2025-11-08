# 🚀 Quick Setup Guide

## What You Need

1. **GitHub account** (free) - https://github.com
2. **Render account** (free) - https://render.com
3. **PayPal account** - Already configured: `reveriopaypal@gmail.com`

---

## Step-by-Step Setup

### 1. Upload to GitHub (5 min)

**Option A: GitHub Desktop (Easiest)**
1. Download: https://desktop.github.com/
2. Install and sign in
3. File → Add Local Repository
4. Choose: `C:\Users\emman\Desktop\Leadius System`
5. Publish repository (make it PUBLIC)

**Option B: Command Line**
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin YOUR-REPO-URL
git push -u origin main
```

### 2. Deploy to Render (10 min)

1. Go to: https://render.com
2. Sign up with GitHub
3. New + → Web Service
4. Select your repository
5. Settings:
   - Environment: Python 3
   - Build: `pip install -r requirements.txt`
   - Start: `gunicorn app:app`
6. Add Environment Variable:
   - Key: `PAYPAL_EMAIL`
   - Value: `reveriopaypal@gmail.com`
7. Create Web Service
8. Wait 5-10 minutes

### 3. Done! 🎉

Your site is live at: `https://YOUR-NAME.onrender.com`

---

## Test Your Site

1. Visit your site URL
2. Click "Registrera" (Register)
3. Create an account
4. Log in
5. Click "Generera nytt lead" (Generate new lead)
6. View your leads in dashboard

---

## Important Notes

- **Free tier:** Site sleeps after 15 min inactivity
- **First visit:** May take 30-60 seconds to wake up
- **Leads:** System scrapes automatically every 30 minutes
- **Credits:** Users need credits to generate leads (you add manually for now)

---

## Need Help?

- Check Render logs if something doesn't work
- Make sure repository is PUBLIC
- Verify environment variable is set

---

**That's it! You're ready to go! 🚀**

