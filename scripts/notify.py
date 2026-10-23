#!/usr/bin/env python3
"""按已配置的渠道发送一条通知：飞书自定义机器人、邮件（SMTP）。

消息来自环境变量 NOTIFY_TITLE、NOTIFY_CONTENT、NOTIFY_URL、NOTIFY_STATUS、NOTIFY_SOURCE，渠道配置见 README。
一个渠道都没配置时只打印提示，不算失败；某个渠道配置不完整或发送失败时，其余渠道照常发送，最后以非零状态退出。
只用标准库，GitHub 托管的运行器上可以直接运行。
"""

import base64
import hashlib
import hmac
import json
import os
import re
import smtplib
import ssl
import sys
import time
from dataclasses import dataclass
from email.message import EmailMessage
from urllib.request import Request, urlopen

TIMEOUT = 15

# 飞书卡片标题颜色
CARD_COLORS = {"success": "green", "failure": "red", "info": "blue"}


class ConfigError(Exception):
    pass


@dataclass
class Message:
    title: str
    content: str = ""
    url: str = ""
    status: str = "info"
    source: str = ""


def feishu_sign(timestamp, secret):
    """飞书机器人「签名校验」：以 timestamp + "\\n" + 密钥为 key，对空串做 HMAC-SHA256 后 Base64。"""
    key = f"{timestamp}\n{secret}".encode()
    return base64.b64encode(hmac.new(key, digestmod=hashlib.sha256).digest()).decode()


def feishu_payload(msg, secret, now):
    elements = []
    if msg.content:
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": msg.content}})
    if msg.url:
        elements.append({
            "tag": "action",
            "actions": [{
                "tag": "button",
                "text": {"tag": "plain_text", "content": "查看详情"},
                "type": "primary",
                "url": msg.url,
            }],
        })
    if msg.source:
        elements.append({"tag": "note", "elements": [{"tag": "plain_text", "content": f"来自 {msg.source}"}]})
    if not elements:
        # 卡片至少要有一个元素
        elements.append({"tag": "div", "text": {"tag": "plain_text", "content": msg.title}})
    payload = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": CARD_COLORS.get(msg.status, "blue"),
                "title": {"tag": "plain_text", "content": msg.title},
            },
            "elements": elements,
        },
    }
    if secret:
        timestamp = str(int(now))
        payload["timestamp"] = timestamp
        payload["sign"] = feishu_sign(timestamp, secret)
    return payload


def send_feishu(cfg, msg):
    body = json.dumps(feishu_payload(msg, cfg["secret"], time.time())).encode()
    req = Request(cfg["webhook"], data=body, headers={"Content-Type": "application/json; charset=utf-8"})
    with urlopen(req, timeout=TIMEOUT) as resp:
        result = json.load(resp)
    # 成功时返回 code 为 0（旧版接口为 StatusCode）；失败时 HTTP 状态仍可能是 200，只能看 code
    code = result.get("code", result.get("StatusCode"))
    if code != 0:
        raise RuntimeError(f"飞书返回错误 {code}：{result.get('msg', '')}")


def markdown_to_text(content):
    """邮件正文用纯文本：去掉 **加粗**，[文字](链接) 改成「文字（链接）」。"""
    content = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1（\2）", content)
    return content.replace("**", "")


def build_email(msg, sender, recipients):
    em = EmailMessage()
    em["Subject"] = msg.title
    em["From"] = sender
    em["To"] = ", ".join(recipients)
    parts = [markdown_to_text(msg.content)] if msg.content else []
    if msg.url:
        parts.append(f"详情：{msg.url}")
    if msg.source:
        parts.append(f"来自 {msg.source}")
    em.set_content("\n\n".join(parts) or msg.title)
    return em


def send_email(cfg, msg):
    em = build_email(msg, cfg["sender"], cfg["recipients"])
    context = ssl.create_default_context()
    if cfg["port"] == 465:
        server = smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=TIMEOUT, context=context)
    else:
        # 其他端口（一般是 587）必须升级到 STARTTLS，不明文发送密码
        server = smtplib.SMTP(cfg["host"], cfg["port"], timeout=TIMEOUT)
        server.starttls(context=context)
    with server:
        server.login(cfg["username"], cfg["password"])
        server.send_message(em)


def require(env, channel, names):
    missing = [name for name in names if not env.get(name)]
    if missing:
        raise ConfigError(f"{channel}配置不完整，缺少 {', '.join(missing)}")


def feishu_config(env):
    if not env.get("FEISHU_WEBHOOK") and not env.get("FEISHU_SECRET"):
        return None
    require(env, "飞书", ["FEISHU_WEBHOOK"])
    return {"webhook": env["FEISHU_WEBHOOK"], "secret": env.get("FEISHU_SECRET", "")}


EMAIL_SETTINGS = ["SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM", "EMAIL_TO"]


def email_config(env):
    if not any(env.get(name) for name in EMAIL_SETTINGS):
        return None
    require(env, "邮件", ["SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "EMAIL_TO"])
    port = env.get("SMTP_PORT") or "465"
    if not port.isdigit():
        raise ConfigError(f"邮件配置有误，SMTP_PORT 不是端口号：{port}")
    recipients = [addr for addr in re.split(r"[,;\s]+", env["EMAIL_TO"]) if addr]
    return {
        "host": env["SMTP_HOST"],
        "port": int(port),
        "username": env["SMTP_USERNAME"],
        "password": env["SMTP_PASSWORD"],
        "sender": env.get("SMTP_FROM") or env["SMTP_USERNAME"],
        "recipients": recipients,
    }


CHANNELS = [("飞书", feishu_config, send_feishu), ("邮件", email_config, send_email)]

EMAIL_ADDRESS = re.compile(r"[^\s,;<>]+@[^\s,;<>]+")


def mask_addresses(env, out):
    """邮件配置是 Secret，日志只会打码整串值；发送失败的报错（例如收件人被拒）里会出现单个地址，逐个注册打码。"""
    for name in ("SMTP_USERNAME", "SMTP_FROM", "EMAIL_TO"):
        for addr in EMAIL_ADDRESS.findall(env.get(name, "")):
            print(f"::add-mask::{addr}", file=out)


def run(env, out=sys.stdout):
    mask_addresses(env, out)
    msg = Message(
        title=env.get("NOTIFY_TITLE", "").strip(),
        content=env.get("NOTIFY_CONTENT", "").strip(),
        url=env.get("NOTIFY_URL", "").strip(),
        status=env.get("NOTIFY_STATUS", "").strip() or "info",
        source=env.get("NOTIFY_SOURCE", "").strip(),
    )
    if not msg.title:
        print("::error::缺少 NOTIFY_TITLE", file=out)
        return 1

    failed = 0
    configured = 0
    for name, config, send in CHANNELS:
        try:
            cfg = config(env)
            if cfg is None:
                continue
            configured += 1
            send(cfg, msg)
            print(f"{name}：已发送", file=out)
        except Exception as e:  # noqa: BLE001 一个渠道失败不影响其他渠道
            failed += 1
            print(f"::error::{name}：{e}", file=out)

    if configured == 0 and failed == 0:
        print("::notice::未配置任何通知渠道，跳过", file=out)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run(os.environ))
