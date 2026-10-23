import base64
import hashlib
import hmac
import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent))
import notify  # noqa: E402

FEISHU = {"FEISHU_WEBHOOK": "https://open.feishu.cn/open-apis/bot/v2/hook/x"}
EMAIL = {
    "SMTP_HOST": "smtp.example.com",
    "SMTP_USERNAME": "bot@example.com",
    "SMTP_PASSWORD": "pw",
    "EMAIL_TO": "a@example.com, b@example.com;c@example.com",
}
MESSAGE = {
    "NOTIFY_TITLE": "token-market v1.0.0 发布成功",
    "NOTIFY_CONTENT": "**版本**：v1.0.0\n[更新说明](https://example.com/notes)",
    "NOTIFY_URL": "https://example.com/release",
    "NOTIFY_STATUS": "success",
    "NOTIFY_SOURCE": "yx-token/token-market",
}


def feishu_response(body):
    resp = mock.MagicMock()
    resp.__enter__.return_value = io.BytesIO(json.dumps(body).encode())
    return resp


def run(env):
    out = io.StringIO()
    return notify.run(env, out), out.getvalue()


class FeishuTest(unittest.TestCase):
    def test_sign(self):
        expected = base64.b64encode(
            hmac.new(b"1700000000\nsecret", b"", hashlib.sha256).digest()
        ).decode()
        self.assertEqual(notify.feishu_sign("1700000000", "secret"), expected)

    def test_payload(self):
        msg = notify.Message(**{
            "title": "t", "content": "**c**", "url": "https://u", "status": "failure", "source": "org/repo",
        })
        payload = notify.feishu_payload(msg, "", 1700000000)
        self.assertNotIn("sign", payload)
        card = payload["card"]
        self.assertEqual(card["header"]["template"], "red")
        self.assertEqual([e["tag"] for e in card["elements"]], ["div", "action", "note"])
        self.assertEqual(card["elements"][1]["actions"][0]["url"], "https://u")

        signed = notify.feishu_payload(msg, "secret", 1700000000.9)
        self.assertEqual(signed["timestamp"], "1700000000")
        self.assertEqual(signed["sign"], notify.feishu_sign("1700000000", "secret"))

    def test_payload_title_only(self):
        payload = notify.feishu_payload(notify.Message(title="t"), "", 0)
        self.assertEqual(len(payload["card"]["elements"]), 1)

    def test_send(self):
        with mock.patch.object(notify, "urlopen", return_value=feishu_response({"code": 0})) as urlopen:
            code, out = run({**MESSAGE, **FEISHU})
        self.assertEqual(code, 0)
        self.assertIn("飞书：已发送", out)
        req = urlopen.call_args.args[0]
        self.assertEqual(req.full_url, FEISHU["FEISHU_WEBHOOK"])
        self.assertEqual(json.loads(req.data)["card"]["header"]["title"]["content"], MESSAGE["NOTIFY_TITLE"])

    def test_error_code(self):
        resp = feishu_response({"code": 19021, "msg": "sign match fail"})
        with mock.patch.object(notify, "urlopen", return_value=resp):
            code, out = run({**MESSAGE, **FEISHU})
        self.assertEqual(code, 1)
        self.assertIn("19021", out)

    def test_secret_without_webhook(self):
        code, out = run({**MESSAGE, "FEISHU_SECRET": "s"})
        self.assertEqual(code, 1)
        self.assertIn("FEISHU_WEBHOOK", out)


class EmailTest(unittest.TestCase):
    def test_send_ssl(self):
        with mock.patch.object(notify.smtplib, "SMTP_SSL") as smtp_ssl:
            code, out = run({**MESSAGE, **EMAIL})
        self.assertEqual(code, 0, out)
        self.assertEqual(smtp_ssl.call_args.args[:2], ("smtp.example.com", 465))
        server = smtp_ssl.return_value
        server.login.assert_called_once_with("bot@example.com", "pw")
        em = server.send_message.call_args.args[0]
        self.assertEqual(em["Subject"], MESSAGE["NOTIFY_TITLE"])
        self.assertEqual(em["From"], "bot@example.com")
        self.assertEqual(em["To"], "a@example.com, b@example.com, c@example.com")
        body = em.get_content()
        self.assertIn("版本：v1.0.0", body)
        self.assertIn("更新说明（https://example.com/notes）", body)
        self.assertIn("详情：https://example.com/release", body)

    def test_starttls(self):
        env = {**MESSAGE, **EMAIL, "SMTP_PORT": "587", "SMTP_FROM": "通知 <bot@example.com>"}
        with mock.patch.object(notify.smtplib, "SMTP") as smtp:
            code, out = run(env)
        self.assertEqual(code, 0, out)
        smtp.return_value.starttls.assert_called_once()
        em = smtp.return_value.send_message.call_args.args[0]
        self.assertIn("bot@example.com", em["From"])

    def test_incomplete(self):
        code, out = run({**MESSAGE, "SMTP_HOST": "smtp.example.com"})
        self.assertEqual(code, 1)
        self.assertIn("SMTP_USERNAME, SMTP_PASSWORD, EMAIL_TO", out)

    def test_bad_port(self):
        code, out = run({**MESSAGE, **EMAIL, "SMTP_PORT": "abc"})
        self.assertEqual(code, 1)
        self.assertIn("SMTP_PORT", out)

    def test_mask_addresses(self):
        # 每个地址在任何输出之前注册打码
        env = {**MESSAGE, **EMAIL, "SMTP_FROM": "通知 <from@example.com>", "SMTP_PORT": "abc"}
        code, out = run(env)
        self.assertEqual(code, 1)
        lines = out.splitlines()
        self.assertEqual(lines[:5], [
            "::add-mask::bot@example.com",
            "::add-mask::from@example.com",
            "::add-mask::a@example.com",
            "::add-mask::b@example.com",
            "::add-mask::c@example.com",
        ])
        self.assertIn("::error::邮件", lines[5])


class RunTest(unittest.TestCase):
    def test_no_channel(self):
        code, out = run({**MESSAGE, "SMTP_PORT": ""})
        self.assertEqual(code, 0)
        self.assertIn("未配置任何通知渠道", out)

    def test_missing_title(self):
        code, out = run({**FEISHU, "NOTIFY_TITLE": "  "})
        self.assertEqual(code, 1)
        self.assertIn("NOTIFY_TITLE", out)

    def test_one_channel_fails_others_still_sent(self):
        # 邮件配置不完整，飞书照常发送，整体失败
        with mock.patch.object(notify, "urlopen", return_value=feishu_response({"code": 0})) as urlopen:
            code, out = run({**MESSAGE, **FEISHU, "EMAIL_TO": "a@example.com"})
        self.assertEqual(code, 1)
        urlopen.assert_called_once()
        self.assertIn("飞书：已发送", out)
        self.assertIn("::error::邮件", out)


if __name__ == "__main__":
    unittest.main()
