# PSAL Badminton — Team Points & Lineup System

**New: a website for phones.** `PSAL Badminton Server` runs the whole system as a website on your PC. It works on iPhone, Android, tablets and computers, and players can add it to their home screen. Everything below works there too. **Setup: see [WEB_SETUP.md](WEB_SETUP.md).**

Two desktop apps for Windows and Mac, both signed in with KeyAuth and sharing the same team data:

- **PSAL Badminton** (blue) — for players and coaches: points, lineup, matches, practice, video quizzes, optional training, and requesting rank-up matches.
- **PSAL Badminton Manager** (purple) — for managers and coaches: run rank-up matches, rank people up or down, manage the training videos and quizzes, 1st singles training and improvement notes. Players can't sign in to it.

The front-screen sign greets whoever signs in by the username they signed up with ("Hello Coach mcnally!" for coaches, "Hello jlee!" for everyone else). Players who sign in without a key are greeted by their first name.

**Players don't need license keys.** In the team app they pick the **Player** tab, type the team code, choose their name and make their own PIN the first time. Only coaches and managers use KeyAuth keys.

**Built to stay fast on any computer.** Every tab is kept ready in the background and switching just brings it to the front. Screens only redraw when something changed, and long lists load in pages ("Show more"). With a full season of data (40 players, 3,000+ point changes), switching tabs takes about 0.02–0.03 seconds at normal and 150% display scaling.

## Point system

| How | Points |
|---|---|
| Everyone starts with | **100** |
| 1st / 2nd / 3rd Singles win | +60 / +50 / +40 |
| 1st / 2nd Doubles win | +45 / +40 (each partner) |
| Played but lost | +10 |
| Team wins the match | +10 bonus for everyone who played |
| Practice attendance | +10 |
| **Unexcused absence** (no-show) | **−15** |
| Excused absence (reason required) | 0 — reason is saved |
| **Practice scrimmage** win / loss | about +15 / **−10** (skill-based, see below; both partners in doubles) |
| Challenge match win / loss | about +30 (skill-based) / +5 |
| **Video quiz** passed (Beginner / Intermediate / Expert) | +15 / +20 / +30 |
| **Optional training video** watched (Beginner / Intermediate / Expert) | +5 / +10 / +15 |
| **Skipping a training video** (integrity) | **−10**, and that video gives no points |

Every number is editable in **Settings**. Points never go below 0. Every change is logged with who made it, and undoing a match, practice day or scrimmage takes its points back.

## Skill-based points (like Valorant)

Scrimmages and challenges use a **skill rating**, like Valorant's MMR. It starts at 1000, goes up when you win and down when you lose. The gap between the two ratings decides what a game is worth:

- Beat a stronger player: **more** points. Beat a weaker player: **fewer**.
- Lose to a stronger player: lose **less**. Lose to a weaker player: lose **more**.
- Example: with a 200-point skill gap, the favorite winning a scrimmage gets +7, an upset gets +23.

Before you save a scrimmage or challenge, the app shows each side's win chance and the exact points for each result. Doubles use the partners' average rating. PSAL matches against other schools keep their fixed position points. Players see their own rating; coaches and managers see everyone's.

Undoing a game fixes the ratings too. A new season moves ratings halfway back to 1000. In Settings, **K** sets how fast ratings move (32 normal, **0 = off**), and the smallest/biggest change is 25%–200% of normal.

The full plain-language guide to everything is **HOW_IT_WORKS.txt**.

## Ranks are earned with a rank-up match

Bronze → Silver → Gold → Platinum → Diamond → Champion → Legend.

1. Every 500 points **qualifies** a player for a rank-up match (500 for Silver, 1000 for Gold, …). Hitting 500 doesn't rank you up by itself.
2. The player presses **Request rank-up match** on their Dashboard and picks a manager. That manager gets a Discord ping (if the webhook is set up and their Discord user ID is on the roster).
3. In the **Manager app → Rank-Up Matches**, the manager schedules the match and records the result. **Passed** = rank up. **Did not pass** = they keep training and can request again.
4. Managers and coaches can also **rank someone up or down by hand** (a reason is required and logged).

Coaches can request a match for any qualified player from the Roster ("Rank-up" button).

## Video Quizzes and Optional Training

Both have **Beginner / Intermediate / Expert** sections (harder = more points) and categories: Footwork, Shots, Grip, Plyometrics (quizzes also have Rules & Strategy).

- **Video Quizzes:** watch the whole video in the app, then the quiz unlocks. 70% to pass, 3 tries (both changeable). A coach or manager can reset someone's tries.
- **Optional Training:** watch the whole video for extra points — no quiz.
- Press **Add starter videos** to load 13 training videos and 6 quizzes (every category at every level). Preview them and swap any you don't like with **Edit**; add your own with **+ Add video** (YouTube links only).

**Videos can't be skipped.** They play on a page the app runs on your own computer, with no seek bar, no keyboard shortcuts and the speed locked at 1×. The app checks the playback position against real time every 2 seconds, so jumping ahead, changing the speed or faking progress is detected. If skipping is detected, that video gives no points and the player loses 10 integrity points. Pausing or switching tabs just pauses the video, with no penalty. A coach or manager can press **Allow re-watch** on a flagged video, but the −10 stays.

If a video owner has turned off embedding, the app says the video can't play and gives no penalty. Swap it for another video.

## 1. Set up KeyAuth (keyauth.cc)

The apps are connected to your KeyAuth app `psal badminton` (owner ID `jiSHQAsHVQ`, version `1.0`).

1. **Subscriptions** — yours are already right: **Coach** (level 3), **Managers** (level 2), **Players** (level 1). Make license keys at level 3 for coaches and level 2 for managers. They choose **Register** (username + password + key) the first time. Accounts on `default` only get coach access.
2. **Players — no keys:** in **Settings → Player sign-in**, set a team code (for example `Lions2026`) and tell the team. Each player signs in with the team code, their name from the roster and a 4–8 digit PIN they make the first time. PINs are stored scrambled (hashed), 5 wrong tries locks that name for 60 seconds, and **Roster → Edit → Reset PIN** fixes a forgotten one. Clear the code to turn player sign-in off. (You can still give a player a level-1 key if you want; then link them with step 3.)
3. **Link key accounts to the roster:** for anyone who signs in with a key, type their KeyAuth username in **Roster → Edit → KeyAuth username**. For managers, also add their **Discord user ID** so rank-up requests ping them.
4. **Hash check:** leave it **off**. If you turn it on, add the hash of each new build in KeyAuth or no one can log in.
5. **New version:** change `version` in `main.py` and in KeyAuth. Put a download link in KeyAuth and old copies will show a "Download update" button.

## 2. Get the Windows and Mac apps

**Easiest — GitHub builds both for you:** make a GitHub repo, upload this whole folder, open the **Actions** tab, and download `PSAL-Badminton-Windows` (both .exe files) and `PSAL-Badminton-Mac` (both .apps, zipped) from the latest run.

**Or build on the computer itself** (needs Python 3.10+ from python.org):
- **Windows:** double-click `build_windows.bat` → `dist\PSAL Badminton.exe` and `dist\PSAL Badminton Manager.exe`
- **Mac:** in Terminal, `cd` into this folder and run `./build_mac.sh` → `dist/PSAL Badminton.app` and `dist/PSAL Badminton Manager.app`

The scripts delete old builds first, and they stop with an error if they're run from old files. They also launch each finished app once with `--selftest` and fail if anything is missing, so a broken app never gets handed out.

**Run without building:** `pip install -r requirements.txt`, then `python main.py` (team app) or `python manager_main.py` (manager app).

Mac note: the apps aren't signed by Apple, so the first time **right-click → Open → Open**. If you use Homebrew Python, also run `brew install python-tk`.

## 3. Share the same data across computers

Data is saved in a file called `team_data.json`. For players' rank-up requests to reach the Manager app, and for everyone to see the same points, every computer has to use the same data folder. Go to **Settings → Data & backups → Change…** and pick a folder inside OneDrive, Google Drive or Dropbox that's shared with the team. Do the same on every computer. Changes from other computers show up within a few seconds, and the app reloads before each save so people don't overwrite each other. (Discord pings still go out from any computer that has the webhook set.)

Also in Settings: export a backup (.json), import one, export the leaderboard (.csv), and start a new season (resets points to 100 and ranks to Bronze, archives the old season, keeps the roster and videos).

## 4. Discord webhook for managers

In Discord: **Server Settings → Integrations → Webhooks → New Webhook**, choose the managers' channel, **Copy Webhook URL**. Paste it in **Settings → Discord**, press **Send test message**. It's used for improvement notes, rank-up requests (pinging the chosen manager) and rank-up results. To ping a Managers role on notes, put `<@&ROLE_ID>` in the ping box.

## Files

| File | What it does |
|---|---|
| `main.py` | Team app — start here. Your KeyAuth app details. |
| `manager_main.py` | Manager app (same KeyAuth app, purple theme) |
| `keyauth_client.py`, `ed25519_verify.py` | KeyAuth sign-in with signature checking (plain Python, nothing compiled) |
| `data_store.py` | Points, earned ranks, rank-up requests, lineup, matches, practice, videos, quizzes, notes |
| `watch_server.py` | The unskippable video player and skip detection |
| `starter_content.py` | Starter training videos and quizzes |
| `discord_notify.py` | Discord messages |
| `app.py`, `pages.py`, `ui_kit.py` | The interface |
| `web_server.py`, `web/` | The website (server + phone-friendly app) |
| `start_server.bat`, `start_public_link.bat` | Start the website / get a public link for it |
| `roles.py` | Who can do what (shared by the apps and the website) |
| `build_windows.bat`, `build_mac.sh`, `.github/workflows/build.yml` | Build the apps (and the website server on Windows) |
