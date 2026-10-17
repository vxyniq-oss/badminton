# PSAL Badminton website — run it on your PC

The website works on iPhones, Android phones, tablets, Chromebooks and computers. It has everything the desktop apps have: points, lineup, matches, practice, rank-up matches, video quizzes, optional training, 1S training, notes and settings. Each person only sees what their role allows. Players can add it to their home screen so it opens like an app.

Your PC runs the website and stores the data. The data is the same `team_data.json` file the desktop apps use, so the desktop apps on that PC stay in sync with the website.

---

## 1. Start the website

**Option A — the .exe (no Python needed on the PC):** run `build_windows.bat` once, or download from GitHub Actions. You get `PSAL Badminton Server.exe` in the `dist` folder. Double-click **`start_server.bat`**.

**Option B — from the Python files:** install Python 3.10+ from python.org, then double-click **`start_server.bat`**. It installs what it needs the first time.

A window opens and shows the addresses:

```
On this PC:        http://localhost:8080
On the same Wi-Fi: http://192.168.1.23:8080
```

**Keep that window open.** Closing it stops the website.

The first time, Windows asks whether to allow it through the firewall. Tick **Private networks** and press **Allow**. Phones on your home Wi-Fi can then use the second address.

## 2. First-time setup (coach)

1. Open the site and choose **Coach / Manager**. Sign in with your KeyAuth account; Coach-level keys get full access.
2. Go to **Settings → Player sign-in** and set a **team code** (for example `Lions2026`).
3. Go to **Roster** and add your players and managers.
4. Send the team the link and the team code. Each player picks **Player**, types the code, picks their name and makes their own PIN. They don't need a license key.
5. Managers sign in with their level-2 keys. In **Roster → Edit**, put their KeyAuth username and Discord user ID on their roster spot so rank-up requests reach them.

## 3. Let phones open it from anywhere

Never forward ports on your router. Use a **Cloudflare Tunnel**: it's free, gives the site https (the padlock), and doesn't open your home network to the internet.

**Quick test link (free, no account):** with the website running, double-click **`start_public_link.bat`**. It installs Cloudflare's tool the first time, then shows a link like `https://some-words.trycloudflare.com`. Send that link to the team.
The catch: **the link changes every time you start it**, and Cloudflare says quick links are for testing only.

**Permanent address (about $10/year for a domain):**
1. Buy a domain (any registrar, or Cloudflare itself) and add it to a free Cloudflare account.
2. In the Cloudflare dashboard, go to **Zero Trust → Networks → Tunnels → Create a tunnel → Cloudflared**. Name it, pick **Windows**, and run the install command it shows on your PC. That installs it as a service that starts with Windows.
3. Under **Public hostname**, add e.g. `badminton.yourdomain.com` → type **HTTP** → URL **`localhost:8080`**.
4. Done. The team always uses `https://badminton.yourdomain.com`.

## 4. Keep it running

- **Sleep:** Settings → System → Power → set "when plugged in, put my device to sleep after" to **Never**.
- **Start with Windows:** press Win + R, type `shell:startup`, and put a shortcut to `start_server.bat` in that folder.
- **Windows Update restarts:** set your active hours so restarts happen at night. The startup shortcut brings the site back after a restart.
- **Power or internet outages** take the site down until the PC is back on.

## 5. Backups

- Once a day the website copies `team_data.json` into a **`backups`** folder next to it, and keeps the last 30 days.
- A coach can also **download a backup** anytime from **Settings → Data & backups**, and import one there.
- To keep copies off the PC too, start the website with a data folder inside OneDrive or Google Drive. Then the daily backups land there as well:
  `start_server.bat --data "C:\Users\YOU\OneDrive\PSAL Badminton"`
  (Use the same folder in the desktop apps' Settings so they stay in sync.)
- By default the data lives in the desktop apps' folder: `%APPDATA%\PSALBadminton`.

## 6. KeyAuth notes

- **Hardware lock (HWID):** the website signs people in from your PC, not their own device. If a coach or manager gets an "HWID" error, turn **off** the hardware-ID lock for this app in your KeyAuth app settings, or reset that user's HWID. This is needed when people use both the website and the desktop apps.
- Keep **hash check off**, as with the desktop apps.
- Roles come from your subscriptions: **Coach** (level 3), **Managers** (level 2), **Players** (level 1, optional now). The `default` subscription gets coach access.

## 7. Security & privacy

What the website does to protect the team:

- Every action is checked on the server against the person's role. Players can't give themselves points, see notes or settings, or request rank-ups for others.
- Quiz answers never reach players' phones. PINs are stored scrambled (hashed). The Discord webhook and student IDs are only shown to coaches.
- Wrong team codes, PINs and passwords are rate-limited, with growing lockouts. Five wrong PINs lock that name for a minute, then longer.
- Sign-ins use secure, HttpOnly cookies and last 30 days. Resetting someone's PIN signs them out everywhere.
- Strict security headers block other sites from embedding the website and stop injected scripts from running.
- Skipping detection for videos runs on the server, so it can't be faked from a phone.

Because it holds students' names and points, **check with your school before putting it on the internet**. NYC/NY has student-data privacy rules. Leave the Student/OSIS ID field empty if you don't need it.

## 8. Updating

Replace the files (or the .exe) with the new version and restart `start_server.bat`. The data file isn't touched.

## 9. Troubleshooting

| Problem | Fix |
|---|---|
| Phone can't open the Wi-Fi address | Phone and PC must be on the same network. Allow the app in Windows Firewall (Private networks). School and guest Wi-Fi often block this, so use the public link instead. |
| "Address already in use" | Something else uses port 8080. Run `start_server.bat --port 8081` (and use 8081 in the tunnel). |
| A video says it "can't count" | The video's owner turned off embedding. Edit it and pick another YouTube video. No points are taken. |
| Coach sign-in says HWID | See "KeyAuth notes" above. |
| Forgot PIN | Coach: Roster → tap the player → Edit → **Reset PIN**. |
| Players can't see Player sign-in | Set a team code in Settings → Player sign-in. |

**Add to home screen:**
- iPhone: open the link in Safari, then Share → **Add to Home Screen**.
- Android: open it in Chrome, then ⋮ → **Add to Home screen** / **Install app**.
