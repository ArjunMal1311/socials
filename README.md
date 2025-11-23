# socials

**tl;dr:** I was spending 3 hours daily on social media just to stay visible while building. So I'm building AI agents to handle it. Open sourcing everything.

[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-building%20in%20public-yellow)](https://github.com/arjumal1311/socials)

---

## The Problem

You're building something cool. But if you're not active on social media, nobody knows you exist.

So you spend hours daily:
- Scrolling X/Twitter for engagement opportunities
- Replying to Reddit posts in your niche
- Coming up with content ideas
- Scheduling posts across platforms
- Trying to stay consistent

**This is backwards.** You should be building, not managing social media.

---

## The Solution

AI agents that handle your social media while you focus on building.

**Not another scheduling tool.** Not another analytics dashboard.

An actual AI agent that:
- Reads posts across platforms
- Decides what's worth engaging with
- Generates replies in YOUR voice
- Suggests content ideas from trending topics
- Posts at optimal times
- Learns what works and improves

**Think of it as hiring a social media manager who knows your voice, works 24/7, and costs $20/month (high usage) in AI API fees.**

---

## What's Built (Right Now)

### Content Intelligence Engine ✅
Scrapes content from X, Reddit, YouTube, Google → Scores by engagement → AI analyzes for content ideas

**Why it matters:** Never run out of content ideas. AI finds what's trending and suggests what to make.

### X/Twitter Automation ✅
- **Action Mode:** AI reads your timeline, generates replies, you approve
- **Eternity Mode:** Monitors specific profiles, auto-engages when they post
- **Community Tracker:** Scrapes communities, finds high-value posts
- **Smart Scheduler:** Posts at optimal times based on your audience

**Why it matters:** Stay active on Twitter without being glued to it.

### Reddit Automation ✅
- Scrapes subreddits for trending posts
- AI suggests where to comment
- Generates contextual replies
- Auto-posts approved content

**Why it matters:** Reddit drives traffic if you engage consistently. This does it for you.

### YouTube/Instagram/Linkedin 🧪
Basic automation working, still testing.

---

## What's Next (The AI Agent)

Right now, you run commands and approve suggestions. That works, but it's not autonomous.

**v1.0 goal:** One AI agent that handles everything.

**How it'll work:**

1. **Style Learning**
   - Analyzes your past posts/replies
   - Learns your tone, topics, patterns
   - Generates content that sounds like you

2. **Autonomous Decisions**
   - Scrapes all platforms daily
   - Scores opportunities (engagement potential)
   - Decides: reply, create content, or ignore
   - Queues everything for your approval

3. **Cross-Platform Intelligence**
   - Same idea, adapted for each platform
   - Tweet → LinkedIn post → Reddit comment
   - One piece of content → maximum distribution

4. **Continuous Learning**
   - Tracks what performs well
   - Adjusts strategy based on data
   - Gets better over time

**Timeline:** Building this publicly over next 6-8 weeks. Follow along.

---

## Why Open Source?

Because the alternative sucks.

**SaaS tools:**
- Cost $100+/month
- Lock you into their platform
- Generic AI that doesn't sound like you
- Can't customize prompts
- Your data on their servers

**Socials:**
- Free forever (just AI API costs)
- Runs locally, you own your data
- Customize everything (code + prompts)
- No vendor lock-in
- Transparent (read the code)

Plus, I'm learning by building this publicly. If it helps others, even better.

---

## Quick Start
```bash
# Clone & setup
git clone https://github.com/arjumal1311/socials.git
cd socials
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Configure
cp profiles.sample.py profiles.py
# Edit profiles.py with your accounts and AI API keys

# Run interactive command generator
python atg.py

# Or jump straight in (example: Twitter replies)
python services/platform/x/replies.py --profile YOUR_PROFILE --action-review
```

**Full docs:** [Setup Guide](docs/SETUP.md) • [Commands](docs/COMMANDS.md) • [Platform Guides](docs/PLATFORMS.md)

---

## Real Talk

**This is a work in progress.** The core automation works. The AI agent is being built.

**It's not perfect.** There are bugs. Some features are experimental. I'm learning as I go.

**But it's useful.** I'm using it daily to manage my own social media. It saves me 10+ hours per week.

**And it's getting better.** Every week I ship improvements based on what I learn.

If you're a developer who wants to build in public but hates managing social media, this might help.

---

## Use Cases

**For indie hackers:**
- Launch a product → Socials keeps you visible while you build
- Engage with communities without spending hours scrolling

**For developers:**
- Build in public without context-switching constantly
- Stay active on X/Reddit/LinkedIn consistently

**For small startups:**
- Automate community engagement
- Generate content from trending topics
- Distribute updates across all platforms

**Not for:**
- Spamming (please don't)
- Fake engagement (sounds like you because it learns from you)
- Replacing authentic relationships (it's a tool, not a replacement)

---

## The Stack

- **Python 3.8+** - CLI tool, runs anywhere
- **Gemini API** - AI for analysis and generation
- **Playwright/Selenium** - Browser automation
- **Local storage** - Your data stays on your machine
- **Google Sheets** - Easy Visualization of Data

No database. No cloud service. Just Python scripts and AI APIs.

---

## Roadmap

**Phase 1: Automation** ✅
- [x] Multi-platform scraping
- [x] Content scoring
- [x] Reply generation
- [x] Basic scheduling

**Phase 2: Intelligence** 🔄 (current)
- [x] Content idea generation
- [ ] Style learning from your posts
- [ ] Approval queue system
- [ ] Autonomous posting

**Phase 3: Agent** 📅 (next)
- [ ] One unified agent for all platforms
- [ ] Cross-platform content adaptation
- [ ] Performance tracking & learning
- [ ] Self-improvement from data

---

## Contributing

Building this in public. Contributions welcome.

**Ways to help:**
- Try it, report bugs
- Suggest features
- Improve docs
- Submit PRs

See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for details.

---

## Disclaimer

This is an educational project. Using automation on social platforms may violate their Terms of Service. You're responsible for following platform rules. Use at your own risk.

I built this to solve my own problem. Sharing it because others might find it useful.

---

## Follow Along

Building v1.0 publicly:
- **Twitter:** [@flytdev](https://twitter.com/flytdev)
- **Updates:** Watch this repo
- **Weekly progress:** Committed to shipping weekly

If this resonates with you, star the repo ⭐

---

**Built by developers, for everyone who'd rather be building.**

MIT License • [Read the code](https://github.com/arjumal1311/socials) • [Report issues](https://github.com/arjumal1311/socials/issues)
