# 🇸🇪 Leadius - Swedish Lead Generation System

**Your PayPal Email:** `reveriopaypal@gmail.com` ✅ (Already configured!)

---

## 📋 What This Is

A login-based system where users can:
- Register and log in
- Generate Swedish business leads
- Browse and manage their leads
- Track lead status (Ny, Kontaktad, Konverterad, Borttagen)

**Market:** Swedish companies only 🇸🇪

---

## 🚀 Quick Setup (15 minutes)

### Step 1: Upload to GitHub (5 minutes)

1. Download **GitHub Desktop**: https://desktop.github.com/
2. Sign in with your GitHub account
3. Click **"File"** → **"Add Local Repository"**
4. Browse to: `C:\Users\emman\Desktop\Leadius System`
5. Click **"Publish repository"**
6. Make it **PUBLIC** ✅
7. Name it: `leadius` (or any name)

### Step 2: Deploy to Render (10 minutes)

1. Go to: **https://render.com**
2. Sign up with GitHub (free)
3. Click **"New +"** → **"Web Service"**
4. Select your repository
5. Configure:
   - **Name:** `leadius`
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
6. Add Environment Variable:
   - **Key:** `PAYPAL_EMAIL`
   - **Value:** `reveriopaypal@gmail.com`
7. Click **"Create Web Service"**
8. Wait 5-10 minutes

### Step 3: Your Site is Live! 🎉

Your site will be at: `https://leadius.onrender.com` (or your chosen name)

---

## ✅ What's Already Done

- ✅ Login/Registration system
- ✅ Lead generation system
- ✅ Dashboard with statistics
- ✅ Lead status tracking
- ✅ Swedish lead scraping (automatic every 30 min)
- ✅ PayPal email configured
- ✅ Logo integrated

---

## 📁 Folder Structure

```
📁 Your Project
│
├── 📄 app.py ................... Main application
├── 📄 requirements.txt ......... Dependencies
├── 📄 README.md ................ This file
│
├── 📁 templates/ ................ Website pages
│   ├── login.html .............. Login page
│   ├── register.html .......... Registration page
│   └── leads.html .............. Dashboard
│
├── 📁 static/ ................... Images & assets
│   └── images/
│       └── logo.png ............ Your logo
│
└── ⚙️ Config files .............. For deployment
    ├── Procfile
    ├── runtime.txt
    └── .gitignore
```

---

## 🎯 How It Works

1. **Users register** → Create account with email/password
2. **Users log in** → Access dashboard
3. **Users generate leads** → Click "Generera nytt lead"
4. **System assigns leads** → Swedish companies from database
5. **Users manage leads** → Update status, track progress

---

## 💰 How to Earn Money

1. Users need credits to generate leads
2. They pay via PayPal to: `reveriopaypal@gmail.com`
3. You manually add credits to their account (for now)
4. They use credits to generate leads

**To add credits manually:**
- Use the database or create an admin panel later
- Or implement PayPal IPN for automatic verification

---

## 🆘 Troubleshooting

**Logo not showing?**
- Make sure `static/images/logo.png` exists
- Restart the Flask app
- Clear browser cache

**Can't log in?**
- Make sure database is created (runs automatically)
- Check that users table exists

**Leads not generating?**
- System scrapes leads every 30 minutes automatically
- First leads appear after first scrape cycle
- Or visit `/update` to manually trigger

---

## 📝 Next Steps

1. ✅ Deploy to Render (follow steps above)
2. ✅ Test login and registration
3. ✅ Test lead generation
4. ✅ Share your site URL
5. ✅ Start earning!

---

**Everything is ready! Just deploy and start using! 🚀**
