# How to Win Your First Hackathon: A Complete Guide

A hackathon is a short, intense event (usually 24–48 hours) where teams build a working project from scratch and present it to judges. You don't need to be an expert to win. Judges reward **a clear problem, a working demo, and a great pitch** far more than they reward clever code nobody gets to see.

This guide walks you through every phase: before, during, and after the event.

---

## Table of Contents

1. [Understand How Hackathons Are Judged](#1-understand-how-hackathons-are-judged)
2. [Before the Event](#2-before-the-event)
3. [Building Your Team](#3-building-your-team)
4. [Choosing the Right Idea](#4-choosing-the-right-idea)
5. [Planning the Build](#5-planning-the-build)
6. [During the Hack](#6-during-the-hack)
7. [Hardware Hacks](#7-hardware-hacks)
8. [The Demo and Pitch](#8-the-demo-and-pitch)
9. [Your Submission Page](#9-your-submission-page)
10. [After the Hackathon](#10-after-the-hackathon)
11. [Common Mistakes to Avoid](#11-common-mistakes-to-avoid)
12. [Quick Checklist](#12-quick-checklist)

---

## 1. Understand How Hackathons Are Judged

Before you write a single line of code, read the judging criteria. They are usually published on the event website or Devpost page. Most events score on some mix of:

| Criterion | What judges are really asking |
|---|---|
| **Impact / Usefulness** | Does this solve a real problem for real people? |
| **Technical Difficulty** | Did the team build something non-trivial? |
| **Completeness** | Does it actually work in the demo? |
| **Creativity / Originality** | Have I seen this ten times already today? |
| **Design / UX** | Is it easy and pleasant to use? |
| **Presentation** | Did they explain it clearly and convincingly? |

Judges often see dozens of projects in a few hours. They may spend only **3–5 minutes** with yours. Everything you do should be aimed at making those minutes count.

### Prize tracks are your secret weapon

Most hackathons have a grand prize plus many **sponsor tracks** ("Best use of X API", "Best hardware hack", "Best sustainability project", "Best beginner hack"). Sponsor tracks usually have far fewer entries than the grand prize. Picking one or two tracks that fit your idea dramatically improves your odds.

> **Tip:** Many events have a "Best First-Time Hacker" or "Best Beginner Team" prize. If you're eligible, target it on purpose.

---

## 2. Before the Event

Preparation is the biggest advantage a first-timer can have.

### Find an event
- [MLH (Major League Hacking)](https://mlh.io/) lists student hackathons worldwide.
- [Devpost](https://devpost.com/hackathons) lists online and in-person hackathons.
- Check your university's engineering college, computer science club, IEEE branch, and entrepreneurship center.

### Prepare your tools (the week before)
- Install and test your editor, Git, language runtimes, and package managers.
- Create accounts you'll likely need: GitHub, a cloud host (Vercel, Netlify, Render, Firebase), and any sponsor APIs announced in advance.
- Make a **starter template** you already know works — for example, a basic web app with a frontend, a backend, and a deployed "Hello World." Starting from something that runs saves hours.
- Make sure you're comfortable with the basics of Git — branching, committing, pushing, and resolving merge conflicts. (The [rest of this repository](../../README.md) is a great place to practice!)

> **Rules check:** Most hackathons require that project code be written *during* the event. Boilerplate and public libraries are fine; a half-finished project is not. Read the rules.

### Pack well (in-person events)
- Laptop, charger, phone charger, and a **power strip** (you'll be very popular)
- Headphones
- Water bottle, snacks, and any medications
- A hoodie or blanket — venues get cold at 3 a.m.
- Toiletries and a change of clothes
- For hardware hacks: your own microcontrollers, cables, and a multimeter if you have them

---

## 3. Building Your Team

Most hackathons allow teams of **up to 4 people**. A balanced team usually beats four people with identical skills.

### The ideal roles
| Role | Responsibilities |
|---|---|
| **Frontend / Design** | UI, user flow, making it look polished |
| **Backend / Data** | APIs, databases, logic, integrations |
| **Hardware / Specialist** | Sensors, ML model, domain expertise — whatever makes the project special |
| **Product / Pitch** | Defines the problem, keeps scope tight, builds slides, practices the demo, handles the submission |

Roles will overlap — that's fine. What matters is that **someone owns the pitch**. Teams that leave the presentation to the last hour almost never win.

### Where to find teammates
- Friends from classes, clubs, or labs
- The event's Discord/Slack `#team-formation` channel (often opens a week early)
- The team-formation mixer at the start of the event

### Non-programmers are valuable
Business, accounting, design, and domain-expert teammates can define the real-world problem, research the market, estimate costs or savings, design the UI, and deliver the pitch. A project that says *"this would save a small business ~$4,000 per year"* is much more convincing than one that doesn't. See [Things a non-programmer can do](Things%20a%20non%20Programmer%20can%20do.md) for more ideas.

---

## 4. Choosing the Right Idea

The idea is where most hackathons are won or lost.

### A good hackathon idea is:
1. **Specific** — "Help college students split utility bills fairly" beats "A finance app."
2. **Demoable** — Judges can *see* it work in under 2 minutes.
3. **Buildable in ~60% of the time you have** — you will lose time to bugs, food, and sleep.
4. **Matched to a prize track** — ideally the grand prize *and* one or two sponsor tracks.
5. **Something you care about** — passion shows in the pitch.

### Ways to generate ideas
- Think about something that frustrated you this week.
- Talk to the sponsors at their booths — ask what problems they wish people would solve with their tools.
- Combine a sponsor API with a specific audience (e.g., "speech-to-text API + students taking lab notes").
- Look at the event theme and ask, "Who is underserved here?"

### Validate quickly (15 minutes, max)
Ask each idea:
- Can we describe it in one sentence?
- What is the single "wow" moment in the demo?
- What is the smallest version that still delivers that wow moment?

If you can't answer all three, move on. **Don't spend more than 1–2 hours choosing an idea.**

---

## 5. Planning the Build

### Define your MVP (Minimum Viable Product)
Write down the **one core user flow** that must work for the demo. For example:

> User uploads a receipt photo → app extracts the total → app splits it among roommates → each roommate gets a notification.

Everything outside that flow is a **stretch goal**.

### Use a simple scope ladder
| Tier | Description | Must be done by |
|---|---|---|
| **Must-have** | The core demo flow, end to end | ~50% of event time |
| **Should-have** | Polish, better UI, one extra feature | ~75% of event time |
| **Nice-to-have** | Everything else | Only if you're ahead |

### Split work along clear boundaries
Agree on interfaces early (e.g., "the backend returns JSON shaped like this"). Then each person can work independently without blocking the others. Use **mock data** so the frontend doesn't wait on the backend.

### Set up the repo immediately
- One person creates the GitHub repo and adds everyone.
- Each person works on their own branch and merges often.
- Commit small and frequently — a broken laptop at 4 a.m. shouldn't end your hackathon.

---

## 6. During the Hack

### A sample 24-hour timeline
| Time | Focus |
|---|---|
| Hours 0–2 | Opening ceremony, team formation, pick idea, plan MVP |
| Hours 2–10 | Build the core flow; get *something* working end to end |
| Hours 10–12 | Integration checkpoint: connect all the pieces |
| Hours 12–16 | Fix bugs, sleep in shifts (seriously) |
| Hours 16–20 | Polish UI, add one stretch feature, **feature freeze** |
| Hours 20–22 | Build slides, record backup video, write submission |
| Hours 22–24 | Practice the pitch repeatedly, submit early |

### Golden rules
- **Get it working end to end first, then make it better.** An ugly app that works beats a beautiful app that crashes.
- **Feature freeze** several hours before the deadline. After that, only fix bugs and polish.
- **Deploy early.** "It works on my laptop" is risky; a live URL is not.
- **Fake what you must, but be honest about it.** Hard-coding a sample dataset for the demo is normal. Claiming a feature exists when it doesn't is not.
- **Use mentors.** Mentors and sponsor engineers are there to help — and they often talk to judges. Asking for help when you've been stuck for 30+ minutes is a strength, not a weakness.
- **Sleep a little.** Even 2–3 hours makes you a far better presenter.
- **Eat real food and drink water.** Energy drinks are not a meal plan.

### Check in as a team every few hours
Ask three questions:
1. What's done?
2. What's blocking you?
3. Are we still on track for the MVP? If not, what do we cut?

---

## 7. Hardware Hacks

Hardware projects stand out because judges can physically *see and touch* them — and hardware tracks often have fewer entries. But they come with extra risk.

- **Use parts you've used before.** A hackathon is not the time to learn a brand-new sensor protocol from scratch.
- **Check the hardware lab early.** Many events (especially MLH events) lend out Arduinos, Raspberry Pis, ESP32s, sensors, and motors. Popular parts run out fast.
- **Bring spares.** Wires break, boards get fried, and USB cables mysteriously stop working.
- **Prototype on a breadboard first,** and only make things permanent once they work.
- **Have a software fallback.** Record a video of the hardware working the moment it does, in case something fails during judging.
- **Connect it to software.** A sensor that sends data to a live dashboard or phone app tells a much better story than a blinking LED.
- **Power is the #1 failure point.** Double-check voltage, current draw, and grounds before you plug anything in.

---

## 8. The Demo and Pitch

This is where hackathons are won. A great pitch can lift an average project; a bad pitch can sink a great one.

### Structure for a 2–3 minute pitch
1. **Hook (15 s):** A relatable problem or surprising statistic.
   > "College students in the U.S. lose an estimated $X each year to unfair bill splits and forgotten payments."
2. **Problem (20 s):** Who has this problem and why existing solutions fall short.
3. **Solution (15 s):** One sentence describing what you built.
4. **Live demo (60–90 s):** Walk through the core flow as a *story* about a user. Show, don't tell.
5. **How it works (20 s):** A quick look at your tech stack and the hardest technical challenge you solved.
6. **Impact & next steps (15 s):** Who this helps, and what you'd build next.
7. **Close (5 s):** Team name, project name, thank you.

### Demo tips
- **Rehearse the demo at least 3–5 times**, ideally with a timer.
- Pre-load data, log in ahead of time, and close unrelated tabs and notifications.
- Use a **mobile hotspot** in case the venue Wi-Fi fails.
- Have a **backup video** of the demo ready to play if anything breaks.
- Zoom in your browser / increase font size so judges can read the screen.
- Let one person drive the demo while another narrates.

### Answering judge questions
Common questions include:
- "What was the hardest part?"
- "How is this different from [existing product]?"
- "What would you do with more time?"
- "Which parts are fully working vs. mocked?"

Answer honestly and briefly. Judges respect teams that know their project's limits.

---

## 9. Your Submission Page

Many judges read the submission (often on Devpost) before or after seeing your demo. Treat it like a mini-pitch.

Include:
- **Project name and one-line tagline**
- **Inspiration** — the problem and why you care
- **What it does** — with screenshots or a GIF
- **How we built it** — technologies and architecture
- **Challenges we ran into** — judges love honest stories of problem-solving
- **Accomplishments we're proud of**
- **What we learned**
- **What's next**
- **Links:** GitHub repo, live demo URL, and demo video (2 minutes or less)
- **Prize tracks** you're submitting to

> **Submit early!** Submit a draft at least an hour before the deadline, then update it. Late submissions are often not accepted, and the submission site can slow down right before the deadline.

---

## 10. After the Hackathon

Whether you win or not, the hackathon isn't over when the judging ends.

- **Clean up your repo:** add a clear README with screenshots, setup steps, and credits to every teammate.
- **Post about it** on LinkedIn — tag your teammates, the event, and the sponsors. Recruiters notice.
- **Add it to your resume** under Projects, with a specific result (e.g., "Won Best Hardware Hack out of 60 teams").
- **Thank mentors and sponsors** you talked to and connect with them.
- **Keep building** if you're excited about the idea. Some of the best startups and open-source projects began at hackathons.
- **Reflect as a team:** what went well, and what would you do differently next time?

---

## 11. Common Mistakes to Avoid

| Mistake | Better approach |
|---|---|
| Picking an idea that's too big | Cut scope until the MVP fits in half the time |
| Learning a brand-new framework at the event | Use tools you already know; learn one small new thing at most |
| Spending hours on login/authentication | Hard-code a demo user — judges don't care about your sign-up page |
| Leaving integration to the last hour | Connect frontend and backend early, even with mock data |
| Not sleeping at all | Sleep in shifts; you'll present much better |
| No backup plan for the demo | Record a demo video as soon as the core flow works |
| Starting the pitch an hour before judging | Assign a pitch owner from the start |
| Ignoring sponsor prize tracks | Target 1–2 tracks that genuinely fit your project |
| Over-explaining the tech, under-explaining the problem | Lead with *why it matters*, then show *how it works* |

---

## 12. Quick Checklist

**Before the event**
- [ ] Registered and read the rules and judging criteria
- [ ] Tools installed, accounts created, starter template tested
- [ ] Team formed (or plan to join one at the event)
- [ ] Bag packed (charger, power strip, snacks, hoodie)

**During the event**
- [ ] Idea chosen within the first 2 hours
- [ ] MVP defined and prize tracks selected
- [ ] Repo created and everyone can push
- [ ] Core flow working end to end by the halfway point
- [ ] Feature freeze set and respected
- [ ] App deployed to a live URL
- [ ] Backup demo video recorded

**Before judging**
- [ ] Slides finished
- [ ] Pitch rehearsed at least 3 times
- [ ] Submission page complete with links, screenshots, and video
- [ ] Submitted *before* the deadline

**After the event**
- [ ] README cleaned up
- [ ] Project shared on LinkedIn/social media
- [ ] Mentors, sponsors, and teammates thanked

---

## Final Words

Your first hackathon is about **learning, meeting people, and shipping something real** in a short time. Winning is a great bonus — and it becomes much more likely when you pick a focused idea, build a working demo, and tell a clear story about why it matters.

Good luck, and happy hacking! 🚀
