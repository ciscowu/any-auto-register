import unittest
from unittest.mock import patch
from datetime import datetime, timezone

from core.base_mailbox import MailboxAccount, create_mailbox


class MicMailMailboxTests(unittest.TestCase):
    def _build_mailbox(self, **extra):
        config = {
            "micmail_api_base": "https://micmail.example.com",
            "micmail_api_key": "mic-test",
            "micmail_mailbox": "all",
            "micmail_account_page_size": 50,
            "micmail_message_page_size": 20,
            "micmail_refresh": True,
            "micmail_category_key": "openai_pool",
            "micmail_category_name_zh": "OpenAI 账号池",
            "micmail_category_name_en": "openai_pool",
            "micmail_acquire_tag_key": "unused",
            "micmail_acquire_tag_name": "未用",
            "micmail_acquire_tag_name_en": "unused",
            "micmail_status_acquired_name": "处理中",
            "micmail_status_registered_name": "已注册",
            "micmail_status_success_name": "已完成",
            "micmail_status_register_fail_name": "注册失败",
            "micmail_status_oauth_fail_name": "OAuth 失败",
            "micmail_status_key_acquired": "processing",
            "micmail_status_key_registered": "registered",
            "micmail_status_key_success": "completed",
            "micmail_status_key_register_failed": "register_failed",
            "micmail_status_key_oauth_failed": "oauth_failed",
        }
        config.update(extra)
        return create_mailbox("micmail", extra=config)

    @patch("requests.request")
    def test_get_email_initializes_missing_classifications_and_marks_processing(self, mock_request):
        mock_request.side_effect = [
            _response({"categories": [], "tags": []}),
            _response({}),
            _response({}),
            _response({}),
            _response({}),
            _response({}),
            _response({}),
            _response({}),
            _response(
                {
                    "categories": [{"key": "openai_pool"}],
                    "tags": [
                        {"key": "unused"},
                        {"key": "processing"},
                        {"key": "registered"},
                        {"key": "completed"},
                        {"key": "register_failed"},
                        {"key": "oauth_failed"},
                    ],
                }
            ),
            _response(
                {
                    "accounts": [
                        {
                            "email_id": "demo@example.com",
                            "client_id": "client-1",
                            "status": "active",
                            "category_key": "openai_pool",
                            "tag_keys": ["unused"],
                        }
                    ],
                    "total_pages": 1,
                }
            ),
            _response({}),
            _response(
                {
                    "accounts": [
                        {
                            "email_id": "demo@example.com",
                            "client_id": "client-1",
                            "status": "active",
                            "category_key": "openai_pool",
                            "tag_keys": ["processing"],
                        }
                    ],
                    "total_pages": 1,
                }
            ),
        ]

        mailbox = self._build_mailbox()
        account = mailbox.get_email()

        self.assertEqual(account.email, "demo@example.com")
        self.assertEqual(account.account_id, "demo@example.com")
        self.assertEqual(account.extra["client_id"], "client-1")

        called_urls = [call.args[1] for call in mock_request.call_args_list]
        self.assertIn("https://micmail.example.com/classifications/categories", called_urls)
        self.assertEqual(called_urls.count("https://micmail.example.com/classifications/tags"), 6)
        self.assertIn(
            "https://micmail.example.com/accounts/demo%40example.com/classification",
            called_urls,
        )

    @patch("requests.request")
    def test_get_email_raises_when_tag_still_missing_after_initialization(self, mock_request):
        mock_request.side_effect = [
            _response({"categories": [], "tags": []}),
            _response({}),
            _response({}),
            _response({}),
            _response({}),
            _response({}),
            _response({}),
            _response({}),
            _response(
                {
                    "categories": [{"key": "openai_pool"}],
                    "tags": [{"key": "unused"}],
                }
            ),
        ]

        mailbox = self._build_mailbox()

        with self.assertRaisesRegex(RuntimeError, "micmail_tag_missing:processing"):
            mailbox.get_email()

    @patch("requests.request")
    def test_wait_for_code_reads_detail_and_extracts_code(self, mock_request):
        mock_request.side_effect = [
            _response(
                {
                    "emails": [
                        {
                            "message_id": "m1",
                            "subject": "ChatGPT verification",
                        }
                    ]
                }
            ),
            _response(
                {
                    "message_id": "m1",
                    "subject": "ChatGPT verification code",
                    "body_plain": "Your verification code is 654321",
                    "date": "2026-04-09T12:00:00+00:00",
                }
            ),
        ]

        mailbox = self._build_mailbox()
        code = mailbox.wait_for_code(
            MailboxAccount(email="demo@example.com", account_id="demo@example.com"),
            timeout=5,
        )

        self.assertEqual(code, "654321")
        self.assertEqual(mock_request.call_count, 2)

    def test_parse_message_ts_treats_naive_datetime_as_utc(self):
        mailbox = self._build_mailbox()

        parsed = mailbox._parse_message_ts(
            {"date": "2026-04-09T12:00:00"}
        )

        expected = int(
            datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc).timestamp() * 1000
        )
        self.assertEqual(parsed, expected)


def _response(payload, status_code=200):
    response = unittest.mock.Mock()
    response.status_code = status_code
    response.json.return_value = payload
    response.text = ""
    response.content = b"{}"
    return response


if __name__ == "__main__":
    unittest.main()
