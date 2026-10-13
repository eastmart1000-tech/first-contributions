#!/usr/bin/env python3
"""internbot: search LinkedIn for internships and submit Easy Apply applications.

    python apply.py login              log in by hand once; the session is saved in browser_profile/
    python apply.py run --dry          search and score, list matches, submit nothing
    python apply.py run --review       ask y/n in the terminal before every submit
    python apply.py run                search, score, and apply

No LinkedIn password is ever stored. The session lives in the persistent
Chromium profile that `login` creates.
"""
import argparse
import csv
import datetime as dt
import random
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

import yaml
from playwright.sync_api import Error as PWError
from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = HERE / "config.yaml"
PROFILE_DIR = HERE / "browser_profile"
LOG_PATH = HERE / "applied.csv"
LOG_FIELDS = ["date", "job_id", "title", "company", "score", "status", "url", "note"]
MAX_STEPS = 10
RESULTS_PER_PAGE = 25
FILL_ME = "FILL_ME"

# ---------------------------------------------------------------------------
# LinkedIn selectors. LinkedIn changes its markup often; when something stops
# working, start here and in the functions named in the README.
# ---------------------------------------------------------------------------
SEL = {
    # search results
    "job_card": "li[data-occludable-job-id]",
    "card_title": ".job-card-list__title, .job-card-list__title--link, "
                  ".job-card-container__link, a[href*='/jobs/view/']",
    "no_results": ".jobs-search-no-results-banner, .jobs-search-two-pane__no-results-banner--expand",
    # job details (right-hand pane on search, or the /jobs/view/ page)
    "detail_title": ".job-details-jobs-unified-top-card__job-title, "
                    ".jobs-unified-top-card__job-title, h1.t-24",
    "detail_company": ".job-details-jobs-unified-top-card__company-name, "
                      ".jobs-unified-top-card__company-name",
    "detail_description": "#job-details, .jobs-description__content, .jobs-box__html-content",
    "easy_apply_button": "button.jobs-apply-button, button[aria-label*='Easy Apply']",
    # Easy Apply modal
    "modal": ".jobs-easy-apply-modal, div[data-test-modal][role='dialog']",
    "submit": "button[aria-label='Submit application']",
    "review": "button[aria-label='Review your application']",
    "next": "button[aria-label='Continue to next step']",
    "dismiss": "button[aria-label='Dismiss']",
    "discard": "button[data-control-name='discard_application_confirm_btn'], "
               "button[data-test-dialog-primary-btn]",
    "field_error": ".artdeco-inline-feedback--error",
    "follow_checkbox": "input#follow-company-checkbox",
    "text_inputs": "input:not([type]), input[type='text'], input[type='tel'], input[type='email'], "
                   "input[type='number'], input[type='url'], textarea",
    "typeahead_option": "[role='listbox'] [role='option'], .search-typeahead-v2__hit, "
                        ".basic-typeahead__selectable",
    "file_input": "input[type='file']",
    "post_apply": "[data-test-modal-id='post-apply-modal'], .artdeco-modal:has-text('application was sent')",
}

SUCCESS_TEXT = re.compile(r"application (was )?sent|application submitted", re.I)
ALREADY_APPLIED_TEXT = re.compile(r"\bApplied \d+\s+\w+ ago\b|\bApplication submitted\b", re.I)
PLACEHOLDER_OPTION = re.compile(r"^\s*(select an option|select|choose|--.*|)\s*$", re.I)
INTERN_RE = re.compile(r"(?<![a-z])(intern|interns|internship|internships|co-?op|co-?ops)(?![a-z])", re.I)

# JS helpers that read the visible question text for a form control.
LABEL_JS = r"""el => {
  const clean = s => (s || '').replace(/\s+/g, ' ').trim();
  let t = '';
  if (el.id) {
    const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
    if (l) t = l.innerText;
  }
  if (!clean(t)) t = el.getAttribute('aria-label') || '';
  if (!clean(t)) {
    const g = el.closest('[data-test-form-element], .fb-dash-form-element, .jobs-easy-apply-form-element, .jobs-easy-apply-form-section__grouping');
    if (g) { const l = g.querySelector('label, legend'); t = l ? l.innerText : ''; }
  }
  return clean(t);
}"""
LEGEND_JS = r"""fs => {
  const clean = s => (s || '').replace(/\s+/g, ' ').trim();
  const l = fs.querySelector('legend, [data-test-form-builder-radio-button-form-component__title]');
  return clean(l ? l.innerText : '');
}"""
REQUIRED_JS = r"""el => {
  if (el.required || el.getAttribute('aria-required') === 'true') return true;
  const g = el.closest('fieldset, [data-test-form-element], .fb-dash-form-element, .jobs-easy-apply-form-element');
  return !!(g && g.querySelector('[required], [aria-required="true"]'));
}"""


class Unanswerable(Exception):
    """A required question has no matching rule (or no option fits the rule)."""


class ApplyError(Exception):
    """The form did something we don't know how to handle."""


@dataclass
class Job:
    job_id: str
    title: str
    company: str
    description: str
    score: int = 0
    reason: str = ""

    @property
    def url(self):
        return f"https://www.linkedin.com/jobs/view/{self.job_id}/"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
def load_config(path):
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict):
        sys.exit(f"{path} is empty or not a mapping.")
    for key in ("searches", "locations", "answers", "keywords", "resume_path", "profile"):
        if key not in cfg:
            sys.exit(f"{path} is missing '{key}'.")
    return cfg


def find_fill_me(node, path=""):
    """Return the config paths whose value still contains FILL_ME."""
    hits = []
    if isinstance(node, dict):
        for k, v in node.items():
            hits += find_fill_me(v, f"{path}.{k}" if path else str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            hits += find_fill_me(v, f"{path}[{i}]")
    elif isinstance(node, str) and FILL_ME in node:
        hits.append(path)
    return hits


def _as_text(v):
    if isinstance(v, bool):
        return "Yes" if v else "No"
    return "" if v is None else str(v)


def compile_rules(cfg):
    """Ordered list of (regex, [answers]). Answers may use {profile_key} placeholders."""
    profile = {k: _as_text(v) for k, v in (cfg.get("profile") or {}).items()}

    def fill(s):
        return re.sub(r"\{(\w+)\}", lambda m: profile.get(m.group(1), m.group(0)), _as_text(s))

    rules = []
    for i, r in enumerate(cfg["answers"]):
        try:
            rx = re.compile(r["pattern"], re.I)
        except re.error as e:
            sys.exit(f"answers[{i}] pattern {r['pattern']!r} is not a valid regex: {e}")
        ans = r["answer"] if isinstance(r["answer"], list) else [r["answer"]]
        ans = [fill(a) for a in ans if _as_text(a).strip()]
        if ans:
            rules.append((rx, ans))
    return rules


def find_answer(rules, question):
    for rx, ans in rules:
        if rx.search(question):
            return ans
    return None


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def _word_rx(term):
    return re.compile(r"(?<![a-z0-9])" + re.escape(term.lower()) + r"(?![a-z0-9])", re.I)


class Scorer:
    def __init__(self, cfg):
        self.exclude = [(w, _word_rx(w)) for w in cfg.get("exclude_title_words", [])]
        self.keywords = [(_word_rx(k), int(w)) for k, w in (cfg.get("keywords") or {}).items()]
        self.boosts = [(_word_rx(k), int(w)) for k, w in (cfg.get("title_boost") or {}).items()]
        self.companies = [_word_rx(c) for c in cfg.get("preferred_companies", [])]
        self.title_mult = int(cfg.get("title_multiplier", 2))
        self.company_bonus = int(cfg.get("preferred_company_bonus", 5))

    def title_gate(self, title):
        """Return a drop reason, or None if the title is allowed."""
        if not INTERN_RE.search(title):
            return "title lacks intern/co-op"
        for word, rx in self.exclude:
            if rx.search(title):
                return f"excluded word '{word}'"
        return None

    def score(self, job):
        reason = self.title_gate(job.title)
        if reason:
            return 0, reason
        s = 0
        for rx, w in self.keywords:
            if rx.search(job.title):
                s += w * self.title_mult
            if rx.search(job.description):
                s += w
        for rx, w in self.boosts:
            if rx.search(job.title):
                s += w
        if any(rx.search(job.company) for rx in self.companies):
            s += self.company_bonus
        return s, ""


# ---------------------------------------------------------------------------
# applied.csv
# ---------------------------------------------------------------------------
class AppliedLog:
    def __init__(self, path):
        self.path = path
        self.rows = []
        if path.exists():
            with open(path, newline="", encoding="utf-8") as f:
                self.rows = list(csv.DictReader(f))

    def job_ids(self):
        return {r["job_id"] for r in self.rows}

    def applied_today(self):
        today = dt.date.today().isoformat()
        return sum(1 for r in self.rows if r["date"] == today and r["status"] == "applied")

    def write(self, job, status, note=""):
        row = {"date": dt.date.today().isoformat(), "job_id": job.job_id, "title": job.title,
               "company": job.company, "score": job.score, "status": status, "url": job.url,
               "note": note}
        new = not self.path.exists()
        with open(self.path, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=LOG_FIELDS)
            if new:
                w.writeheader()
            w.writerow(row)
        self.rows.append({k: str(v) for k, v in row.items()})


# ---------------------------------------------------------------------------
# Browser helpers
# ---------------------------------------------------------------------------
def launch(p, headless=False):
    ctx = p.chromium.launch_persistent_context(
        str(PROFILE_DIR), headless=headless, viewport={"width": 1366, "height": 900})
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.set_default_timeout(15000)
    return ctx, page


def norm(s):
    return re.sub(r"\s+", " ", (s or "").replace("’", "'")).strip().lower()


def clean_question(label):
    q = re.sub(r"\s+", " ", label or "").strip()
    return re.sub(r"\s*(\*|\bRequired\b)\s*$", "", q, flags=re.I)


def pick_option(options, answers):
    """Return the option text that best matches the first answer that fits any option."""
    opts = [(o, norm(o)) for o in options if not PLACEHOLDER_OPTION.match(o or "")]
    for a in answers:
        na = norm(a)
        for test in (lambda no: no == na,
                     lambda no: no.startswith(na),
                     lambda no: re.search(r"(?<![a-z0-9])" + re.escape(na) + r"(?![a-z0-9])", no)):
            for o, no in opts:
                if test(no):
                    return o
    return None


def visible(locator):
    return [el for el in locator.all() if el.is_visible()]


class Bot:
    def __init__(self, page, cfg, rules, resume, review=False):
        self.page = page
        self.cfg = cfg
        self.rules = rules
        self.resume = resume
        self.review = review
        lo, hi = cfg.get("action_pause_seconds", [0.8, 2.5])
        self.pause_range = (float(lo), float(hi))

    def pause(self, scale=1.0):
        time.sleep(random.uniform(*self.pause_range) * scale)

    # ----------------------------------------------------------------- search
    def search_url(self, keywords, location, page_no):
        days = int(self.cfg.get("posted_within_days", 14))
        q = {
            "keywords": keywords,
            "location": location,
            "f_AL": "true",                  # Easy Apply only
            "f_E": "1",                      # experience level: Internship
            "f_TPR": f"r{days * 86400}",     # posted within N days
            "distance": str(self.cfg.get("distance_miles", 25)),
            "sortBy": "DD",
            "start": str(page_no * RESULTS_PER_PAGE),
        }
        return "https://www.linkedin.com/jobs/search/?" + urlencode(q)

    def collect_jobs(self, scorer, skip_ids):
        """Walk every search x location, page through results, read each viable card."""
        found = {}
        max_pages = int(self.cfg.get("max_pages_per_search", 2))
        for kw in self.cfg["searches"]:
            for loc in self.cfg["locations"]:
                for pg in range(max_pages):
                    print(f"[search] {kw!r} in {loc} (page {pg + 1})")
                    self.page.goto(self.search_url(kw, loc, pg), wait_until="domcontentloaded")
                    self.pause(1.5)
                    if self.page.locator(SEL["no_results"]).count():
                        break
                    cards = self.page.locator(SEL["job_card"])
                    n = cards.count()
                    for i in range(n):
                        card = cards.nth(i)
                        jid = card.get_attribute("data-occludable-job-id")
                        if not jid or jid in found or jid in skip_ids:
                            continue
                        try:
                            card.scroll_into_view_if_needed(timeout=5000)
                            self.pause(0.3)
                            t = card.locator(SEL["card_title"]).first
                            card_title = t.inner_text(timeout=3000).split("\n")[0].strip() if t.count() else ""
                            # Cheap pre-filter: no need to open cards that fail the title gate.
                            if card_title and scorer.title_gate(card_title):
                                continue
                            card.click()
                            job = self.read_job_details(jid)
                        except (PWTimeout, PWError) as e:
                            print(f"  ! could not read card {jid}: {e.__class__.__name__}")
                            continue
                        if job:
                            found[jid] = job
                        self.pause(0.5)
                    if n < RESULTS_PER_PAGE:
                        break
        return list(found.values())

    def read_job_details(self, jid):
        """Read title/company/description from the details pane for job `jid`."""
        try:
            self.page.wait_for_url(re.compile(rf"currentJobId={jid}|/jobs/view/{jid}"), timeout=8000)
        except PWTimeout:
            pass
        self.pause(0.7)
        desc_el = self.page.locator(SEL["detail_description"]).first
        desc_el.wait_for(timeout=10000)
        title = self.page.locator(SEL["detail_title"]).first.inner_text().strip()
        comp = self.page.locator(SEL["detail_company"]).first
        company = comp.inner_text().strip() if comp.count() else ""
        return Job(jid, title.split("\n")[0], company.split("\n")[0], desc_el.inner_text())

    # ------------------------------------------------------------------ apply
    def find_easy_apply_button(self):
        for b in visible(self.page.locator(SEL["easy_apply_button"])):
            label = (b.get_attribute("aria-label") or "") + " " + b.inner_text()
            if "easy apply" in label.lower():
                return b
        return None

    def get_modal(self):
        m = self.page.locator(SEL["modal"]).first
        m.wait_for(state="visible", timeout=10000)
        return m

    def apply(self, job):
        """Return (status, note)."""
        self.page.goto(job.url, wait_until="domcontentloaded")
        self.pause(1.5)
        btn = self.find_easy_apply_button()
        if not btn:
            if self.page.get_by_text(ALREADY_APPLIED_TEXT).count():
                return "skipped_already_applied", ""
            return "skipped_no_easy_apply", ""
        btn.click()
        self.pause()
        try:
            return self.run_modal(job)
        except Unanswerable as e:
            print(f"  - no rule for required question: {e}")
            self.close_form()
            return "skipped_unanswered", str(e)
        except (ApplyError, PWTimeout, PWError) as e:
            print(f"  ! {e.__class__.__name__}: {str(e).splitlines()[0][:200]}")
            self.close_form()
            return "error", str(e).splitlines()[0][:200]

    def run_modal(self, job):
        uploaded = False
        for _ in range(MAX_STEPS):
            modal = self.get_modal()
            uploaded = self.upload_resume(modal) or uploaded
            self.uncheck_follow(modal)
            self.fill_fields(modal)

            submit = modal.locator(SEL["submit"])
            if submit.count() and submit.first.is_visible():
                if self.review:
                    ans = input(f"\n  Submit to {job.title} @ {job.company} (score {job.score})? [y/N] ")
                    if ans.strip().lower() not in ("y", "yes"):
                        self.close_form()
                        return "declined_review", ""
                self.pause()
                submit.first.click()
                ok = self.detect_success()
                self.close_post_apply()
                return ("applied", "") if ok else ("failed", "no confirmation after submit")

            if not self.click_step_button(modal):
                raise ApplyError("no Next/Review/Submit button found")
            self.pause()
            errors = [e.inner_text().strip() for e in visible(modal.locator(SEL["field_error"]))]
            if errors:
                raise Unanswerable("form rejected answers: " + "; ".join(errors)[:200])
        raise ApplyError(f"more than {MAX_STEPS} steps")

    def click_step_button(self, modal):
        for key in ("review", "next"):
            b = modal.locator(SEL[key])
            if b.count() and b.first.is_visible():
                b.first.click()
                return True
        b = modal.get_by_role("button", name=re.compile(r"^\s*(review|next)\s*$", re.I))
        if b.count():
            b.first.click()
            return True
        return False

    def upload_resume(self, modal):
        inputs = modal.locator(SEL["file_input"])
        for i in range(inputs.count()):
            el = inputs.nth(i)
            ident = " ".join(filter(None, [el.get_attribute("id"), el.get_attribute("name"),
                                           el.evaluate(LABEL_JS)])).lower()
            if "cover" in ident:
                continue
            if "resume" not in ident and "cv" not in ident and inputs.count() > 1:
                continue
            if self.resume.name.lower() in norm(modal.inner_text()):
                return False  # LinkedIn already has this exact file selected
            el.set_input_files(str(self.resume))
            self.pause()
            return True
        return False

    def uncheck_follow(self, modal):
        cb = modal.locator(SEL["follow_checkbox"])
        if not cb.count() or not cb.first.is_checked():
            return
        lbl = modal.locator("label[for='follow-company-checkbox']")
        if lbl.count() and lbl.first.is_visible():
            lbl.first.click()
        elif cb.first.is_visible():
            cb.first.uncheck()
        else:
            return  # not on this step
        self.pause(0.5)

    def fill_fields(self, modal):
        """Fill every empty field from the answer rules. Raises Unanswerable."""
        # text inputs and textareas
        for el in visible(modal.locator(SEL["text_inputs"])):
            if el.input_value().strip():
                continue  # prefilled; leave it
            q = clean_question(el.evaluate(LABEL_JS))
            ans = find_answer(self.rules, q)
            if not ans:
                if el.evaluate(REQUIRED_JS) or q.endswith("*"):
                    raise Unanswerable(q or "(unlabeled text field)")
                continue
            is_typeahead = (el.get_attribute("role") == "combobox"
                            or el.get_attribute("aria-autocomplete") in ("list", "both"))
            el.click()
            el.press_sequentially(ans[0], delay=random.randint(50, 130))
            if is_typeahead:
                opt = self.page.locator(SEL["typeahead_option"]).first
                try:
                    opt.wait_for(state="visible", timeout=4000)
                    opt.click()
                except PWTimeout:
                    pass
            print(f"    {q[:70]!r} -> {ans[0]!r}")
            self.pause(0.5)

        # selects
        for el in visible(modal.locator("select")):
            current = el.evaluate("s => s.selectedIndex >= 0 ? s.options[s.selectedIndex].text : ''")
            if not PLACEHOLDER_OPTION.match(current or ""):
                continue
            q = clean_question(el.evaluate(LABEL_JS))
            ans = find_answer(self.rules, q)
            options = el.evaluate("s => Array.from(s.options).map(o => o.text.trim())")
            choice = pick_option(options, ans) if ans else None
            if not choice:
                if el.evaluate(REQUIRED_JS):
                    raise Unanswerable(q if not ans else f"{q} (no option matches {ans})")
                continue
            el.select_option(label=choice)
            print(f"    {q[:70]!r} -> {choice!r}")
            self.pause(0.5)

        # radio groups and checkbox groups
        for fs in visible(modal.locator("fieldset")):
            kind = "radio" if fs.locator("input[type='radio']").count() else (
                "checkbox" if fs.locator("input[type='checkbox']").count() else None)
            if not kind or fs.locator("#follow-company-checkbox").count():
                continue
            if fs.locator(f"input[type='{kind}']:checked").count():
                continue
            q = clean_question(fs.evaluate(LEGEND_JS))
            ans = find_answer(self.rules, q)
            boxes = fs.locator(f"input[type='{kind}']").all()
            labels = [b.evaluate(LABEL_JS) for b in boxes]
            choice = pick_option(labels, ans) if ans else None
            if not choice:
                if fs.evaluate(REQUIRED_JS):
                    raise Unanswerable(q if not ans else f"{q} (no option matches {ans})")
                continue
            box = boxes[labels.index(choice)]
            bid = box.get_attribute("id")
            lbl = fs.locator(f"label[for='{bid}']") if bid else None
            if lbl is not None and lbl.count():
                lbl.first.click()
            else:
                box.check(force=True)
            print(f"    {q[:70]!r} -> {choice!r}")
            self.pause(0.5)

    def close_form(self):
        """Dismiss the Easy Apply modal and discard the draft."""
        try:
            m = self.page.locator(SEL["modal"]).first
            d = m.locator(SEL["dismiss"])
            if d.count():
                d.first.click()
            else:
                self.page.keyboard.press("Escape")
            self.pause(0.6)
            discard = self.page.locator(SEL["discard"])
            if not discard.count():
                discard = self.page.get_by_role("button", name=re.compile(r"^\s*discard\s*$", re.I))
            discard.first.click(timeout=5000)
            self.pause(0.6)
        except (PWTimeout, PWError):
            pass

    def detect_success(self, timeout=20):
        end = time.time() + timeout
        while time.time() < end:
            if self.page.locator(SEL["post_apply"]).count():
                return True
            if self.page.get_by_text(SUCCESS_TEXT).count():
                return True
            time.sleep(0.5)
        return False

    def close_post_apply(self):
        try:
            d = self.page.locator(SEL["dismiss"])
            if d.count() and d.first.is_visible():
                d.first.click()
            else:
                self.page.keyboard.press("Escape")
        except (PWTimeout, PWError):
            pass


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
def is_logged_in(page):
    page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
    time.sleep(2)
    return not re.search(r"/login|/authwall|/checkpoint|/uas/", page.url)


def cmd_login(args):
    with sync_playwright() as p:
        ctx, page = launch(p, headless=False)
        page.goto("https://www.linkedin.com/login")
        input("\nLog in to LinkedIn in the browser window (2FA included).\n"
              "When you can see your feed, press Enter here to save the session... ")
        ok = is_logged_in(page)
        ctx.close()
    print("Session saved in browser_profile/." if ok
          else "Still not logged in. Run `python apply.py login` again.")


def cmd_run(args):
    cfg = load_config(args.config)
    missing = find_fill_me(cfg)
    if missing:
        print("Refusing to start: these config values still say FILL_ME:")
        for m in missing:
            print(f"  - {m}")
        sys.exit(1)

    rules = compile_rules(cfg)
    scorer = Scorer(cfg)
    resume = Path(cfg["resume_path"]).expanduser()
    if not resume.is_absolute():
        resume = HERE / resume
    if not resume.is_file():
        sys.exit(f"resume_path not found: {resume}")
    if not PROFILE_DIR.exists():
        sys.exit("No browser_profile/ yet. Run `python apply.py login` first.")

    log = AppliedLog(LOG_PATH)
    cap = int(cfg.get("daily_cap", 15))
    min_score = int(cfg.get("min_score", 8))
    lo, hi = cfg.get("delay_between_applications_seconds", [45, 120])
    if not args.dry and log.applied_today() >= cap:
        print(f"Daily cap reached ({log.applied_today()}/{cap} applied today). Try again tomorrow.")
        return

    with sync_playwright() as p:
        ctx, page = launch(p, headless=bool(cfg.get("headless", False)))
        try:
            if not is_logged_in(page):
                sys.exit("Not logged in. Run `python apply.py login` first.")
            bot = Bot(page, cfg, rules, resume, review=args.review)
            jobs = bot.collect_jobs(scorer, log.job_ids())
            for j in jobs:
                j.score, j.reason = scorer.score(j)
            matches = sorted((j for j in jobs if not j.reason and j.score >= min_score),
                             key=lambda j: j.score, reverse=True)
            dropped = len(jobs) - len(matches)

            print(f"\n{len(jobs)} new postings read, {len(matches)} at or above min_score {min_score}"
                  f" ({dropped} dropped).")
            for j in matches:
                print(f"  {j.score:>3}  {j.title[:55]:<55}  {j.company[:28]:<28}  {j.url}")
            if args.dry:
                left = max(cap - log.applied_today(), 0)
                print(f"\n--dry: nothing submitted. Today's cap would allow {left} more.")
                return

            attempted = 0
            for j in matches:
                if log.applied_today() >= cap:
                    print(f"Daily cap reached ({cap}). Stopping.")
                    break
                if attempted:
                    wait = random.uniform(float(lo), float(hi))
                    print(f"  waiting {wait:.0f}s before the next application...")
                    time.sleep(wait)
                attempted += 1
                print(f"\n[apply] {j.score}  {j.title} @ {j.company}\n        {j.url}")
                status, note = bot.apply(j)
                log.write(j, status, note)
                print(f"  => {status}")
            print(f"\nDone. Applied today: {log.applied_today()}/{cap}. Log: {LOG_PATH.name}")
        except KeyboardInterrupt:
            print("\nStopped by user.")
        finally:
            ctx.close()


def main():
    ap = argparse.ArgumentParser(description="Search LinkedIn for internships and Easy Apply.")
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("login", help="open the browser profile so you can log in by hand")
    run = sub.add_parser("run", help="search, score, and apply")
    run.add_argument("--dry", action="store_true", help="list scored matches, submit nothing")
    run.add_argument("--review", action="store_true", help="ask y/n before each submit")
    args = ap.parse_args()
    {"login": cmd_login, "run": cmd_run}[args.cmd](args)


if __name__ == "__main__":
    main()
