PROFILES = {
    "profilename": {
        "name": "profilename",
        "data": {
            "google_search": {
                "num_results": 0,
                "time_filter": "",
                "search_queries": [],
                "google_user_prompt": ""
            },
            "youtube_scraper": {
                "max_videos": 0,
                "time_filter": "",
                "search_query": "",
                "youtube_user_prompt": "",
                "max_duration_minutes": 0
            }
        },
        "properties": {
            "utils": {
                "action": {
                    "count": 10,
                    "platforms": {
                        "x": ["myprofile", "myprofile2"], # myprofile2 must be some other profile here
                        "linkedin": ["myprofile", "myprofile2"]
                    },
                    "ignore_video_tweets": False
                },
                "connection": {
                    "count": 17
                },
                "suggestions": {
                    "content_filter": {
                        "max_posts": 25,
                        "max_age_days": 30,
                        "min_age_days": 7,
                        "max_posts_per_profile": 5
                    },
                    "count_linkedin": 17,
                    "count_x_profile": 50,
                    "count_x_community": 50,
                    "new_linkedin_posts": 3
                }
            },
            "global": {
                "verbose": True,
                "headless": True,
                "model_name": "gemini-2.5-flash-lite",
                "push_to_db": False,
                "browser_profile": "some_fake_account_browser" # This browser profile is for retrieving content from profiles/communities without involving a real personal account.
            },
            "platform": {
                "x": {
                    "post": {
                        "gap_type": "random",
                        "num_days": 1,
                        "tweet_text": "This is a sample tweet!",
                        "max_gap_hours": 20,
                        "min_gap_hours": 15,
                        "fixed_gap_hours": 2,
                        "max_gap_minutes": 30,
                        "min_gap_minutes": 30,
                        "fixed_gap_minutes": 0,
                        "start_image_number": 1,
                        "post_watcher_interval": 60
                    },
                    "reply": {
                        "count": 17,
                        "ignore_video_tweets": False
                    },
                    "scraper": {
                        "max_tweets": 20,
                        "communities": [],
                        "specific_url": "",
                        "target_profiles": []
                    }
                },
                "reddit": {
                    "max_posts": 0,
                    "subreddits": [],
                    'time_filter': ['day', 'yesterday'],
                    "min_comments": 0,
                    "include_comments": False
                },
                "linkedin": {
                    "reply": {
                        "count": 10
                    },
                    "scraper": {
                        "count": 3,
                        "target_profiles": []
                    }
                },
                "producthunt": {
                    "scraper": {
                        "count": 20
                    }
                },
                "ycombinator": {
                    "scraper": {
                        "count": 20,
                        "scroll_attempts": 5
                    }
                }
            }
        },
        "prompts": {
            "idea_prompt": "",
            "content_ideas": "",
            "reply_generation": "Generate a casual, insightful reply (max 2 lines) like a real builder. Use simple words, share a quick take or lesson. Avoid corporate jargon. Example: 'agent stuff getting crowded but niche tools still have room'",
            "caption_generation": "Generate a short, casual caption (5-6 words) for this social media post. Make it sound natural and conversational, like something a real person would say. Example: 'this is so hot'",
            "reddit_user_prompt": "",
            "script_generation_prompt": ""
        }
    }
}

