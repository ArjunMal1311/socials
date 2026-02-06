# socials

> scaled a faceless X account to 15k followers, got bored hunting content. Built this to automate replies, find trends, posts. Started on X, now building for other platforms, app shown below is just supabase connection, you can connect your own Supabase to power it

---

https://github.com/user-attachments/assets/b902f9dc-25e8-4512-a247-07ff7b1230de


https://github.com/user-attachments/assets/3008b074-1482-4c9b-bcc7-8517ee61790b



## What it does currently
- **X (Twitter)**: Direct messages, follows, posts, replies, and retrieves content from communities and specific profiles
- **Reddit**: Retrieves the latest posts from subreddits
- **Product Hunt**: Retrieves the latest leaderboard items
- **LinkedIn**: Sends connection requests, direct messages, posts, replies, and retrieves content from feeds
- **Y Combinator**: Retrieves companies listed on YC
- **Instagram, YouTube, Google**: Functionality in development

## Utility Modules

- **Action**: Handles multi-platform replies, integrated with Supabase for remote posting. For local replies, use individual platform reply modules.
- **Connection**: Sends connection requests on LinkedIn and follow requests on X
- **Suggestions**: Manages trends, retrieves content, filters, approves, generates similar content, creates new content, reviews, schedules, and posts. Reply generation will improve as you post more and more, as it gains context from your approved content.

This tool uses **browser automation and API** wherever applicable.

---

## 🚀 Quick start

```bash
git clone && cd socials
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp sample.env .env
./socials <new-profile-name> global init
./socials utils <new-profile-name> action
```

**Note on Browsers:** This project uses **Chromium** for browser automation. You might encounter issues if your Chromium setup isn't standard. Adjustments might be needed in `services/support/web_driver_handler.py`.

---

## 📝 Available Commands

### Global Commands
- `./socials profile-sync`: Synchronize profiles from Supabase
- `./socials <profile> global init`: Initialize a new profile
- `./socials <profile> global delete`: Delete a profile
- `./socials <profile> global upload`: Upload all profiles to Supabase
- `./socials <profile> global <platform> login`: Login to a specific platform (e.g., `x`, `linkedin`). All login information and browser data is stored locally on your machine in the `tmp/browser-data` directory; nothing is sent to Supabase.
- `./socials <profile> global <platform> check-credentials`: Check API credentials for a platform

### Platform-Specific Commands
- **X (Twitter)**
  - `./socials x <profile> dm`: Send direct messages
  - `./socials x <profile> follow`: Manage follows
  - `./socials x <profile> post`: Create and send posts
  - `./socials x <profile> reply`: Generate and send replies
  - `./socials x <profile> scraper`: Retrieve content (e.g., home feed, community, profiles)

- **LinkedIn**
  - `./socials linkedin <profile> connection`: Send connection requests
  - `./socials linkedin <profile> dm`: Send direct messages
  - `./socials linkedin <profile> post`: Create and send posts
  - `./socials linkedin <profile> reply`: Generate and send replies
  - `./socials linkedin <profile> scraper`: Retrieve content from feeds

- **Product Hunt**
  - `./socials producthunt <profile> scraper`: Retrieve latest leaderboard items

- **Y Combinator**
  - `./socials ycombinator <profile> scraper`: Retrieve companies listed on YC

- **Reddit**
  - `./socials reddit <profile> scraper`: Retrieve latest posts from subreddits

### Utility Commands
- **Action**
  - `./socials utils <profile> action`: Handles multi-platform replies (integrated with Supabase for remote posting)

- **Connection**
  - `./socials utils <profile> connection`: Sends connection requests on LinkedIn and follow requests on X

- **Suggestions**
  - `./socials utils <profile> suggestions <platform> [scrape, filter, web, download, trends, generate, generate_new, review, schedule, post]`: Gets trends, retrieves content, filters, approves, generates similar content, creates new content, reviews, schedules, and posts.

---

**Built for creators who want to scale**

---

> New to open source, so there might be some faults, and instructions could be a little unclear. Features might also be a work in progress. Your understanding and contributions are highly welcome!

## Disclaimer

This is an educational project. Using automation on social platforms may violate their Terms of Service. You're responsible for following platform rules. Use at your own risk.

I built this to solve my own problem. Sharing it because others might find it useful.

Built by developers, for everyone who'd rather be building.

---
