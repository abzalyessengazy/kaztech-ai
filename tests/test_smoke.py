import unittest
import os
import tempfile
from datetime import datetime, timedelta, timezone

from agents import publisher, rules_filter
from agents import editor, ranker, telegram_channel
from approval import telegram_bot
from config import settings, style_guide
from core import db, llm


class RulesFilterTests(unittest.TestCase):
    def test_junk_and_local_detection(self):
        self.assertTrue(rules_filter._is_junk("Best deals on AI gadgets"))
        self.assertTrue(rules_filter._is_local({
            "original_title": "Astana Hub launches AI program",
            "original_summary": "For Kazakhstan startups",
            "is_local": 0,
        }))

    def test_used_duplicate_detection(self):
        used = [set(db.normalize_title(
            "Cryptic AI для банков и регуляторов: как ИИ расследует криптотранзакции"
        ).split())]

        self.assertTrue(rules_filter._is_used_duplicate(
            "Cryptic AI для банков: как ИИ расследует криптотранзакции",
            used,
        ))


class PublisherTests(unittest.TestCase):
    def test_compose_text_includes_cta_and_source(self):
        text = publisher.compose_text({
            "body": "Main post",
            "cta": "What do you think?",
            "source_name": "Example News",
            "source_url": "https://example.com/story",
        })

        self.assertIn("Main post", text)
        self.assertIn("What do you think?", text)
        self.assertIn("Дереккөз: Example News", text)
        self.assertIn("https://example.com/story", text)

    def test_payload_uses_configured_visibility(self):
        old_visibility = settings.LINKEDIN_VISIBILITY
        old_author = settings.LINKEDIN_AUTHOR_URN
        try:
            settings.LINKEDIN_VISIBILITY = "CONNECTIONS"
            settings.LINKEDIN_AUTHOR_URN = "urn:li:person:test"
            payload = publisher._payload("hello")
        finally:
            settings.LINKEDIN_VISIBILITY = old_visibility
            settings.LINKEDIN_AUTHOR_URN = old_author

        self.assertEqual(
            payload["visibility"]["com.linkedin.ugc.MemberNetworkVisibility"],
            "CONNECTIONS",
        )

    def test_payload_rejects_invalid_visibility(self):
        old_visibility = settings.LINKEDIN_VISIBILITY
        try:
            settings.LINKEDIN_VISIBILITY = "PRIVATE"
            with self.assertRaises(ValueError):
                publisher._payload("hello")
        finally:
            settings.LINKEDIN_VISIBILITY = old_visibility

    def test_payload_attaches_source_url_as_article_preview(self):
        old_visibility = settings.LINKEDIN_VISIBILITY
        old_author = settings.LINKEDIN_AUTHOR_URN
        try:
            settings.LINKEDIN_VISIBILITY = "PUBLIC"
            settings.LINKEDIN_AUTHOR_URN = "urn:li:person:test"
            payload = publisher._payload("hello", {
                "title": "Post title",
                "source_name": "Example News",
                "source_url": "https://example.com/story",
            })
        finally:
            settings.LINKEDIN_VISIBILITY = old_visibility
            settings.LINKEDIN_AUTHOR_URN = old_author

        content = payload["specificContent"]["com.linkedin.ugc.ShareContent"]
        self.assertEqual(content["shareMediaCategory"], "ARTICLE")
        self.assertEqual(content["media"][0]["originalUrl"], "https://example.com/story")

    def test_linkedin_enabled_flag_can_skip_publish(self):
        old_enabled = settings.LINKEDIN_ENABLED
        old_db_path = settings.DB_PATH
        handle = tempfile.NamedTemporaryFile(delete=False)
        handle.close()
        settings.DB_PATH = handle.name
        settings.LINKEDIN_ENABLED = False
        try:
            db.init_db()
            post_id = db.save_post({
                "news_id": None,
                "title": "Title",
                "body": "Body",
            })
            self.assertIsNone(publisher.publish_post(post_id))
        finally:
            settings.LINKEDIN_ENABLED = old_enabled
            settings.DB_PATH = old_db_path
            os.unlink(handle.name)

    def test_rest_payload_attaches_source_url_as_article_content(self):
        old_visibility = settings.LINKEDIN_VISIBILITY
        old_author = settings.LINKEDIN_AUTHOR_URN
        try:
            settings.LINKEDIN_VISIBILITY = "PUBLIC"
            settings.LINKEDIN_AUTHOR_URN = "urn:li:person:test"
            payload = publisher._rest_payload("hello", {
                "title": "Post title",
                "source_name": "Example News",
                "source_url": "https://example.com/story",
            })
        finally:
            settings.LINKEDIN_VISIBILITY = old_visibility
            settings.LINKEDIN_AUTHOR_URN = old_author

        self.assertEqual(payload["content"]["article"]["source"], "https://example.com/story")
        self.assertEqual(payload["content"]["article"]["title"], "Post title")
        self.assertEqual(payload["distribution"]["feedDistribution"], "MAIN_FEED")

    def test_meta_image_parser_extracts_open_graph_image(self):
        parser = publisher._MetaImageParser()
        parser.feed('<meta property="og:image" content="/image.jpg">')

        self.assertEqual(parser.images, ["/image.jpg"])


class TelegramChannelTests(unittest.TestCase):
    def test_channel_trim_keeps_message_under_limit(self):
        text = telegram_channel._trim("x" * 5000)

        self.assertLessEqual(len(text), telegram_channel.MAX_MESSAGE_CHARS)
        self.assertTrue(text.endswith("…"))

    def test_channel_enabled_flag_can_skip_publish(self):
        old_enabled = settings.TELEGRAM_CHANNEL_ENABLED
        old_db_path = settings.DB_PATH
        handle = tempfile.NamedTemporaryFile(delete=False)
        handle.close()
        settings.DB_PATH = handle.name
        settings.TELEGRAM_CHANNEL_ENABLED = False
        try:
            db.init_db()
            post_id = db.save_post({
                "news_id": None,
                "title": "Title",
                "body": "Body",
            })
            self.assertIsNone(telegram_channel.publish_post(post_id))
        finally:
            settings.TELEGRAM_CHANNEL_ENABLED = old_enabled
            settings.DB_PATH = old_db_path
            os.unlink(handle.name)


class ChooseStoryCardTests(unittest.TestCase):
    def test_pick_card_lists_all_finalists_with_reason(self):
        finalists = [
            {"original_title": "Story A", "theme": "kz-local", "editorial": 8.1, "rank_reason": "Local impact"},
            {"original_title": "Story B", "theme": "ai-tooling", "editorial": 7.5, "rank_reason": "New model"},
        ]
        card = telegram_bot._pick_card(finalists)

        self.assertIn("1️⃣", card)
        self.assertIn("2️⃣", card)
        self.assertIn("Story A", card)
        self.assertIn("Story B", card)
        self.assertIn("Local impact", card)

    def test_pick_buttons_have_one_callback_per_story_plus_skip(self):
        buttons = telegram_bot._pick_buttons(3)

        pick_row = buttons[0]
        self.assertEqual([b["callback_data"] for b in pick_row], ["pick_0", "pick_1", "pick_2"])
        self.assertEqual(buttons[1][0]["callback_data"], "skip")


class TelegramCardTests(unittest.TestCase):
    def test_card_contains_short_story_summary_and_post(self):
        card = telegram_bot._card(
            {
                "original_title": "Kazakhstan AI startup raises funding",
                "original_summary": "A local team raised a seed round.",
                "selection_reason": "Local AI business impact.",
                "source_name": "Example News",
                "source_url": "https://example.com/story",
                "editorial": 8.2,
            },
            {
                "theme": "startup",
                "source_name": "Example News",
                "title": "AI startup gets fuel",
                "body": "LinkedIn body",
                "cta": "Thoughts?",
                "satire_note": "Light irony",
            },
            8.2,
            0,
        )

        self.assertIn("Қысқаша:", card)
        self.assertIn("Неге таңдадық:", card)
        self.assertIn("ҰСЫНЫЛҒАН LINKEDIN ПОСТ", card)
        self.assertIn("LinkedIn body", card)

    def test_card_stays_under_telegram_limit(self):
        card = telegram_bot._card(
            {
                "original_title": "Long story",
                "original_summary": "summary " * 1000,
                "selection_reason": "reason " * 1000,
                "source_name": "Example News",
            },
            {
                "theme": "startup",
                "source_name": "Example News",
                "title": "Long post",
                "body": "body " * 1000,
                "cta": "Thoughts?",
                "satire_note": "note " * 1000,
            },
            8.2,
            0,
        )

        self.assertLessEqual(len(card), telegram_bot.MAX_CARD_CHARS)


class DbTests(unittest.TestCase):
    def test_get_candidates_excludes_stale_items(self):
        old_db_path = settings.DB_PATH
        handle = tempfile.NamedTemporaryFile(delete=False)
        handle.close()
        settings.DB_PATH = handle.name
        try:
            db.init_db()
            db.add_news({
                "source_url": "https://example.com/global",
                "original_title": "Global AI story",
                "source_name": "Global",
                "source_weight": 1.0,
                "is_local": 0,
            })
            db.add_news({
                "source_url": "https://example.com/local",
                "original_title": "Kazakhstan AI story",
                "source_name": "Local",
                "source_weight": 1.0,
                "is_local": 1,
            })
            for item in db.get_inbox(10):
                db.set_status(item["id"], "candidate")

            with db.connect() as conn:
                conn.execute(
                    "UPDATE news SET fetched_at=? WHERE source_url=?",
                    ((datetime.now(timezone.utc) - timedelta(days=4)).isoformat(),
                     "https://example.com/global"),
                )

            candidates = db.get_candidates(1)
        finally:
            settings.DB_PATH = old_db_path
            os.unlink(handle.name)

        self.assertEqual(candidates[0]["source_url"], "https://example.com/local")

    def test_get_finalists_uses_threshold_to_gate_the_day_not_each_option(self):
        old_db_path = settings.DB_PATH
        handle = tempfile.NamedTemporaryFile(delete=False)
        handle.close()
        settings.DB_PATH = handle.name
        try:
            db.init_db()
            for index, editorial in enumerate((8.0, 5.5)):
                db.add_news({
                    "source_url": f"https://example.com/finalist-{index}",
                    "original_title": f"Story {index}",
                    "source_name": "Example",
                })
            for item, editorial in zip(db.get_inbox(10), (8.0, 5.5)):
                db.save_ranking(item["id"], {
                    "importance": editorial,
                    "novelty": editorial,
                    "kz_relevance": editorial,
                    "ai_relevance": editorial,
                    "virality": editorial,
                    "satire_potential": editorial,
                    "editorial": editorial,
                })

            finalists = db.get_finalists(5, 6.5)
        finally:
            settings.DB_PATH = old_db_path
            os.unlink(handle.name)

        self.assertEqual([story["editorial"] for story in finalists], [8.0, 5.5])

    def test_used_news_includes_chosen_rejected_and_published(self):
        old_db_path = settings.DB_PATH
        handle = tempfile.NamedTemporaryFile(delete=False)
        handle.close()
        settings.DB_PATH = handle.name
        try:
            db.init_db()
            for status in ("chosen", "rejected", "published"):
                db.add_news({
                    "source_url": f"https://example.com/{status}",
                    "original_title": f"{status} story",
                    "source_name": "Example",
                })
            for item in db.get_inbox(10):
                db.set_status(item["id"], item["source_url"].rsplit("/", 1)[-1])

            statuses = {item["status"] for item in db.get_used_news()}
        finally:
            settings.DB_PATH = old_db_path
            os.unlink(handle.name)

        self.assertEqual(statuses, {"chosen", "rejected", "published"})


class RankerTests(unittest.TestCase):
    def test_ranker_skips_candidates_similar_to_used_stories(self):
        old_db_path = settings.DB_PATH
        old_score_batch = ranker._score_batch
        handle = tempfile.NamedTemporaryFile(delete=False)
        handle.close()
        settings.DB_PATH = handle.name
        try:
            db.init_db()
            db.add_news({
                "source_url": "https://example.com/used",
                "original_title": "Cryptic AI для банков и регуляторов расследует криптотранзакции",
                "source_name": "Used",
            })
            db.add_news({
                "source_url": "https://example.com/candidate",
                "original_title": "Cryptic AI для банков расследует криптотранзакции",
                "source_name": "Candidate",
            })
            rows = db.get_inbox(10)
            for row in rows:
                status = "rejected" if row["source_name"] == "Used" else "candidate"
                db.set_status(row["id"], status)

            ranker._score_batch = lambda candidates: self.fail("duplicate candidate should not be ranked")
            result = ranker.run()
        finally:
            ranker._score_batch = old_score_batch
            settings.DB_PATH = old_db_path
            os.unlink(handle.name)

        self.assertIsNone(result)


class EditorPromptTests(unittest.TestCase):
    def test_editor_prompt_demands_clean_natural_kazakh(self):
        system = style_guide.build_editor_system_prompt()

        self.assertIn("KAZAKH LANGUAGE QUALITY", system)
        self.assertIn("Russian syntax hidden inside Kazakh vocabulary", system)
        self.assertIn("80–250 words", system)
        self.assertIn("Түймені бас", system)
        self.assertIn("ChatGPT пе", system)

    def test_editor_user_template_demands_short_clean_structure(self):
        self.assertIn("80-250 сөз", editor.USER_TEMPLATE)
        self.assertIn("орысша сөйлем/тіркес қоспа", editor.USER_TEMPLATE)
        self.assertIn("түйме/сілтеме туралы айтпа", editor.USER_TEMPLATE)
        self.assertIn("ағылшын брендтеріне", editor.USER_TEMPLATE)

    def test_editor_polishes_known_bad_brand_particles(self):
        text = editor._polish_known_kazakh_issues("ChatGPT пе, Gemini пе деп таласып жатырмыз")

        self.assertEqual(text, "ChatGPT ме, Gemini ме деп таласып жатырмыз")


class LlmJsonTests(unittest.TestCase):
    def test_lenient_json_escapes_raw_newline_inside_string(self):
        parsed = llm._loads_json_lenient('{"body": "first line\nsecond line"}')

        self.assertEqual(parsed["body"], "first line\nsecond line")

    def test_first_json_object_ignores_extra_text(self):
        raw = '{"body": "ok"}\nextra explanation {"ignored": true}'

        self.assertEqual(llm._first_json_object(raw), '{"body": "ok"}')


if __name__ == "__main__":
    unittest.main()