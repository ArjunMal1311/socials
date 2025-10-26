# socials

## Project Overview

`socials` is a project exploring the integration of AI agent capabilities with social media platforms. This repository stands as a dynamic personal learning experiment, pushing the boundaries to understand the intricate capabilities and transformative potential of AI-powered tools in social media management. My goal is to build intelligent agents that not only streamline but also elevate social media presence, driving authentic engagement and strategic growth.

**Disclaimer**: This project is developed purely for educational and experimental purposes. Using tools on social media platforms may violate their respective Terms of Service, which could lead to temporary or permanent suspension of your accounts. Users are solely responsible for adhering to platform policies and bear all risks associated with the use of these tools. This project is **not intended for commercial use** or to circumvent platform rules, but rather to learn about the underlying mechanisms and potential of AI agents. Use at your own risk.

## Features

The project currently includes AI agents designed for social media management across several platforms:

### 1. X/Twitter Management

This section details the various AI-powered tools available for managing your X/Twitter presence.

#### **Important: Initial Login**
Before using any `x/replies.py` or `x/scheduler.py` commands, you need to log in once with `--no-headless` to authenticate your session:
```bash
source venv/bin/activate && PYTHONPATH=. python services/platform/x/replies.py --profile flytdev --no-headless
# or
source venv/bin/activate && PYTHONPATH=. python services/platform/x/scheduler.py --profile flytdev --no-headless
```

#### **Action Mode**
This mode allows for generating and posting replies to tweets using AI analysis, scraping recent tweets, analyzing them with Gemini AI, and generating contextual replies.

**Commands:**
-   **Review Replies**: Generate and review replies without posting.
    ```bash
    source venv/bin/activate && PYTHONPATH=. python services/platform/x/replies.py --profile flytdev --action-review
    ```
    *Additional Options:*
    -   `--online`, `--run-number`: For online integration with Google Sheets.
    -   `--ignore-video-tweets`, `--verbose`, `--no-headless`, `--reply-max-tweets`, `--action-port`, `--community-name`

-   **Generate and Post Replies**: Use API keys to generate replies, then post approved ones.
    ```bash
    source venv/bin/activate && PYTHONPATH=. python services/platform/x/replies.py --profile flytdev --action-generate
    source venv/bin/activate && PYTHONPATH=. python services/platform/x/replies.py --profile flytdev --post-action-approved
    ```

#### **Eternity Mode**
Focuses on collecting tweets from specific target profiles, analyzing them with Gemini AI, and saving generated replies for approval, enabling targeted profile monitoring.

**Commands:**
-   **Run Eternity Mode**:
    ```bash
    source venv/bin/activate && PYTHONPATH=. python services/platform/x/replies.py --profile flytdev --eternity-mode
    ```
    *Additional Options:*
    -   `--eternity-browser {profile}`: Use another profile's browser (fake) instead of the current profile.
    -   `--ignore-video-tweets`, `--verbose`, `--no-headless`, `--reply-max-tweets`, `--port`

-   **Review Eternity Replies**:
    ```bash
    source venv/bin/activate && PYTHONPATH=. python services/platform/x/replies.py --profile flytdev --eternity-review
    ```
-   **Clear Eternity Data**:
    ```bash
    source venv/bin/activate && PYTHONPATH=. python services/platform/x/replies.py --profile flytdev --clear-eternity
    ```
-   **Post Approved Eternity Replies**:
    ```bash
    source venv/bin/activate && PYTHONPATH=. python services/platform/x/replies.py --profile flytdev --post-approved
    ```
    *Additional Option:*
    -   `--limit`: If there's a posting limit.

#### **Community Analysis**
Features to collect tweets from specific X communities based on provided community names and suggest engaging content.

**Commands:**
-   **Scrape Community Tweets**:
    ```bash
    source venv/bin/activate && PYTHONPATH=. python services/platform/x/replies.py --profile flytdev --community-scrape --community-name "Software Engineering"
    ```
    *Additional Option:*
    -   `--browser-profile {profile}`: Use another profile's browser.
    -   `--ignore-video-tweets`, `--verbose`, `--no-headless`

-   **Suggest Engaging Tweets from Community**: AI-driven analysis of scraped community tweets to identify the most engaging content.
    ```bash
    source venv/bin/activate && PYTHONPATH=. python services/platform/x/replies.py --profile flytdev --suggest-engaging-tweets
    ```
    *Additional Option:*
    -   `--verbose`: To show output.

#### **Scheduled Posting (Scheduler)**
Tools for planning and publishing tweets at specified times.

**Commands:**
-   **Process Tweets for Scheduling**:
    ```bash
    source venv/bin/activate && PYTHONPATH=. python services/platform/x/scheduler.py --profile flytdev --process-tweets
    ```
    *Additional Options:*
    -   `--no-headless`, `--verbose`

-   **Schedule Tomorrow's Tweets**:
    ```bash
    source venv/bin/activate && PYTHONPATH=. python services/platform/x/scheduler.py --profile flytdev --sched-tom
    ```

-   **Generate Sample Schedule**:
    ```bash
    source venv/bin/activate && PYTHONPATH=. python services/platform/x/scheduler.py --profile flytdev --generate-sample
    ```
    *Additional Options:*
    -   `--min-gap-hours`, `--min-gap-minutes`, `--max-gap-hours`, `--max-gap-minutes`, `--fixed-gap-hours`, `--fixed-gap-minutes`, `--tweet-text`, `--start-image-number`, `--num-days`, `--start-date`, `--verbose`

-   **Monitor and Post Scheduled Tweets**:
    ```bash
    source venv/bin/activate && PYTHONPATH=. python services/platform/x/scheduler.py --profile flytdev --post-watch --post-watch-profiles flytdev
    ```

### 2. YouTube Management (Under Testing)
-   **Comment Replies**: AI-powered responses to comments on YouTube videos, maintaining context and tone.
-   **Video Scheduling**: Tools for scheduling video uploads and publications.
-   **Metadata Scraping**: Tools for extracting video metadata for analysis or content optimization.

### 3. Instagram Management (Under Testing)
-   **Post Scheduling**: Tools for scheduling and publishing of Instagram posts.
-   **Auto-replies**: AI-generated responses to comments and direct messages on Instagram.
-   **Engagement Tracking**: Features to monitor and analyze engagement metrics for posts.

## Future Enhancements & Vision

I'm working to expand the capabilities of `socials`.

-   **Unified AI Agent for All Social Media**: My goal is to develop a single, intelligent AI agent capable of seamlessly managing all your social media platforms.
-   **LinkedIn Integration**: LinkedIn management features are coming soon, allowing for professional networking and content scheduling.
-   **Enhanced AI Capabilities**: Further advancements in AI models for more nuanced understanding of engagement, content generation, and audience growth.
-   **Smart Platform Mapping**: An upcoming AI agent will intelligently map and manage all your social media accounts, streamlining your online presence (X-tested & working, YouTube and Instagram under testing).

## Setup and Installation

To get started with `socials`, follow these general steps:

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/arjumal1311/socials.git
    cd socials
    ```

2.  **Initialize a virtual environment**:
    It is highly recommended to use a virtual environment to manage dependencies.
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Profiles**:
    Rename `profiles.sample.py` to `profiles.py` and populate it with your specific social media profiles. This file is crucial for the AI agents to function.
    ```bash
    mv profiles.sample.py profiles.py
    # Edit profiles.py with your configurations
    ```

5.  **Browser Configuration**:
    The project uses `chromium` for browser interaction by default. If you wish to use a different browser (e.g., Chrome, Firefox), you can adjust the settings in `services/support/web_driver_handler.py`.

6.  **Generate Commands with `atg.py`**:
    Use the interactive `atg.py` script to easily generate and understand CLI commands for various tasks.
    ```bash
    source venv/bin/activate && PYTHONPATH=. python atg.py
    ```
    Follow the prompts to select your desired action and configure its parameters. The script will then display the full command for review.

## Contributing

Contributions are welcome! If you have suggestions for improvements, new features, or bug fixes, please feel free to open an issue or submit a pull request.

## License

This project is licensed under the MIT License. See the `LICENSE` file for more details.

As an open-source educational project, I encourage collaboration and learning. If you create a derivative work or copy of this project, I kindly request that you also maintain its open-source nature to further foster a collaborative learning environment.
