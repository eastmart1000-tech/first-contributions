# internbot

Searches LinkedIn for internships that match your config, scores them, and submits
Easy Apply applications, with a daily cap, slow human-paced delays, and a review mode.

Built with Python, Playwright (sync API) and PyYAML. Your LinkedIn password is never
stored. You log in by hand once and the session lives in a local Chromium profile
(`browser_profile/`).

## Read this first

**LinkedIn's User Agreement prohibits bots and automated access, including automated
applying.** LinkedIn can and does restrict or ban accounts it flags. Using this tool
is your call and your risk. To keep that risk and the odds of a bad submission low:

- Start with `--dry`, then use `--review` for your first several runs and read every form
  before you answer `y`.
- Keep `daily_cap` low (default 15) and leave the 45-120 s delays alone.
- Don't run it from several machines or in headless mode.

## Setup

```bash
cd internbot
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
```

Then edit `config.yaml`. Every value that says `FILL_ME` must be filled in, or
`apply.py run` refuses to start:

| Key | What to put |
| --- | --- |
| `profile.phone` | your phone number, digits only |
| `profile.linkedin_url` | your full LinkedIn profile URL |
| `profile.authorized_to_work_us` | `"Yes"` or `"No"` (quoted) |
| `profile.needs_sponsorship` | `"Yes"` or `"No"` (quoted) |
| `resume_path` | path to your resume PDF (relative to this folder is fine) |

Copy your resume PDF into this folder. `.gitignore` keeps PDFs, `applied.csv` and
`browser_profile/` out of git, so your resume, your log and your logged-in session
never get committed.

## The three run modes

First, once (and again whenever LinkedIn logs you out):

```bash
python apply.py login
```

A Chromium window opens on LinkedIn's login page. Log in by hand, 2FA included. When
you can see your feed, press Enter in the terminal to save the session.

Then:

```bash
python apply.py run --dry       # search + score, print ranked matches, submit nothing
python apply.py run --review    # apply, but ask y/n in the terminal before each submit
python apply.py run             # apply on its own, up to daily_cap
```

`--dry` never opens a form, so it wins if you pass both flags.

## How it works

1. **Search.** For every `searches` x `locations` pair, it builds a LinkedIn job search URL
   with the Easy Apply filter (`f_AL=true`), Internship experience level (`f_E=1`), and a
   posted-within-N-days filter (`f_TPR`). It pages through up to `max_pages_per_search`
   pages and clicks each card to read title, company and description. Jobs already in
   `applied.csv` are skipped. Cards whose title already fails the title rules are not
   opened, which saves a lot of clicking.
2. **Score.** A title without "intern", "internship", "co-op" or "coop" is dropped. A title
   containing any `exclude_title_words` entry is dropped. Everything else gets keyword
   points (title hits count `title_multiplier` times), `title_boost` points, and
   `preferred_company_bonus` (+5) for `preferred_companies`. Jobs at or above `min_score`
   are applied to, highest score first.
3. **Apply.** Opens the posting, clicks Easy Apply, and walks the modal (Next, Review,
   Submit application; 10 steps max). On each step it uploads your resume if there's a
   resume upload, unchecks "Follow company", and fills empty text fields, dropdowns,
   radio groups and typeahead fields from the ordered `answers` rules (first match
   wins). Prefilled values are left alone.
4. **No guessing.** If a required question has no matching rule, or LinkedIn rejects an
   answer, it clicks Dismiss, then Discard, logs `skipped_unanswered` with the question in
   the `note` column, and moves on. Add a rule for that question and the next posting
   that asks it will go through.
5. **Confirm.** After Submit it waits for LinkedIn's "application sent" confirmation and
   logs `applied` only if it sees one (otherwise `failed`).

## applied.csv

Every attempt is logged with `date, job_id, title, company, score, status, url, note`.

Statuses: `applied`, `skipped_unanswered`, `skipped_no_easy_apply`,
`skipped_already_applied`, `declined_review`, `failed`, `error`.

- `daily_cap` counts today's `applied` rows, so the cap holds across runs.
- Any job_id in the file is skipped on later runs, whatever its status. To retry one
  (say, after adding a rule for a question that blocked it), delete its row.

## When LinkedIn changes its pages

LinkedIn changes its markup often, and this tool will break when it does. All CSS
selectors are in the `SEL` dict at the top of `apply.py`. The functions that depend on
them, in the order they run:

| Symptom | Function(s) to adjust |
| --- | --- |
| Search finds no cards, or wrong titles | `Bot.search_url`, `Bot.collect_jobs` |
| Title/company/description come back empty | `Bot.read_job_details` |
| "skipped_no_easy_apply" on jobs that have Easy Apply | `Bot.find_easy_apply_button` |
| Modal never detected | `Bot.get_modal` |
| Stuck on a step / "no Next/Review/Submit button" | `Bot.click_step_button`, `Bot.run_modal` |
| Fields not filled, or wrong question text | `Bot.fill_fields` (and `LABEL_JS` / `LEGEND_JS`) |
| Resume not attached | `Bot.upload_resume` |
| Still following companies | `Bot.uncheck_follow` |
| Form left open after a skip | `Bot.close_form` |
| Applied but logged as `failed` | `Bot.detect_success` |

Use `--review` while you fix selectors, so nothing goes out that you haven't seen.
