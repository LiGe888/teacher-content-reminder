import unittest

from teacher_content_reminder.fetchers.html_list import _looks_like_article_url


class HTMLListURLFilterTests(unittest.TestCase):
    def test_blocked_topic_paths(self) -> None:
        self.assertFalse(
            _looks_like_article_url(
                "https://www.sciencenews.org/topic/artificial-intelligence",
                "https://www.sciencenews.org/",
            )
        )

    def test_blocked_collection_paths(self) -> None:
        self.assertFalse(
            _looks_like_article_url(
                "https://www.sciencenews.org/collections/2019-novel-coronavirus-outbreak",
                "https://www.sciencenews.org/",
            )
        )

    def test_blocked_image_article_paths(self) -> None:
        self.assertFalse(
            _looks_like_article_url(
                "https://www.nasa.gov/image-article/new-perspective-of-home/",
                "https://www.nasa.gov/news-release/feed/",
            )
        )

    def test_accept_real_article_path(self) -> None:
        self.assertTrue(
            _looks_like_article_url(
                "https://www.sciencenews.org/article/hair-chronic-stress-war-refugees",
                "https://www.sciencenews.org/",
            )
        )

