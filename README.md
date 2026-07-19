# Appe — Mobile App for Frappe & ERPNext
<p align="center">
  <img src="https://appetech.io/files/logo.png" alt="Appe Banner" width="200" />
</p>

> **Frappe, anywhere you go.**  
> A mobile-first app for Frappe and ERPNext, making your business accessible on the move.

---

## Description

**Appe** is a mobile extension for the [Frappe Framework](https://frappeframework.com/) and [ERPNext](https://erpnext.com/), designed to make your ERP and custom Frappe apps easy to use on mobile devices.  
With Appe, you can connect to **Frappe**, **ERPNext**, or any other Frappe-based applications — all from one app.

Whether you are running a business on ERPNext or managing custom Frappe modules, Appe gives you **fast, secure, and convenient** mobile access to your data.

---

## Key Features
- **Mobile-First Experience** – Clean and responsive UI optimized for small screens.
- **Multi-App Connectivity** – Access ERPNext and other Frappe apps from one place.
- **Fast & Lightweight** – Smooth performance even on slower devices.
- **Secure Login** – Works with your existing Frappe authentication system (Employee Location Tracking).
- **Connect from Anywhere** – Use your cloud-hosted or self-hosted Frappe instance.
- **Easy Installation** – Install Appe directly from your Frappe site.

---

## Extra Features
- **Location Tracking** – Store employee locations automatically every 15 minutes.

## Install Mobile App
- **Android** – [Appe Mobile App](https://play.google.com/store/apps/details?id=com.kameshkumar.appe&pcampaignid=web_share)  
- **IOS** – [Appe ERPNext Mobile App](https://apps.apple.com/us/app/appe/id6759156081)  


## Installation

1. Register at: [www.appetech.io/signup](https://appetech.io/signup)

2. Install **Appe** using the [bench](https://github.com/frappe/bench) CLI
<p>Run following commands:</p>

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app https://github.com/appetech/Appe.git --branch develop
bench install-app appe

```
## Face Recognition Setup

<p>Run following commands:</p>

```bash
cd $PATH_TO_YOUR_BENCH
sudo apt update

sudo apt install -y build-essential cmake libopenblas-dev liblapack-dev libx11-dev libgtk-3-dev

bench pip install -e appe

```

## Help & Support
If you have any questions, issues, or feature requests, we’re here to help.

📧 Email Support: info@appetech.in, appetechnologies@gmail.com

🌐 Website: https://appetech.io

🎫 Support Portal: https://appetech.io/support

You can also create an issue on this GitHub repository for bug reports or feature suggestions.
