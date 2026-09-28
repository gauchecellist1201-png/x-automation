import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch

import social


class SocialTest(unittest.TestCase):
    def test_daily_has_distinct_copyable_drafts(self):
        posts = social.daily_posts(date(2026, 9, 29))
        self.assertEqual(len(set(posts)), 3)
        self.assertTrue(all(0 < len(post) <= 280 for post in posts))

    def test_daily_and_weekly_only_push_to_line(self):
        now = datetime(2026, 9, 29, 8, tzinfo=ZoneInfo("Asia/Tokyo"))
        with patch.dict("os.environ", {"LINE_CHANNEL_ACCESS_TOKEN": "test", "LINE_USER_ID": "test"}), patch.object(social, "push") as push, patch.object(social, "recent_headlines", return_value=[]):
            social.main("daily", now)
            self.assertEqual(len(push.call_args.args[0]), 3)
            social.main("weekly", now)
            self.assertIn("経営者のためのAI実践室", push.call_args.args[0][0])


if __name__ == "__main__":
    unittest.main()
