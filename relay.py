#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""微聊 · 邮件中继（云端常驻版）
轮询 api.php?action=mail_pull，用 QQ 邮箱 SMTP 465 把验证码发出去。
配置全部从环境变量读取，不要写死在文件里。
"""
import json, os, ssl, smtplib, sys, time, urllib.request
from email.message import EmailMessage
from email.utils import formataddr, formatdate

API = os.environ.get("WL_API", "https://weiliao.wbuild.top/api.php")
KEY = os.environ.get("WL_KEY", "")
USER = os.environ.get("SMTP_USER", "")
PASS = os.environ.get("SMTP_PASS", "")
NAME = "微聊"
RUN_SECONDS = int(os.environ.get("RUN_SECONDS", "540"))  # 单次运行时长，默认 9 分钟
POLL = 5

LABELS = {"reg": "注册微聊账号", "recover": "找回微聊账号", "pay": "设置支付密码"}


def log(msg):
    print(time.strftime("%F %T"), msg, flush=True)


def _once(url):
    req = urllib.request.Request(url, headers={"User-Agent": "wl-relay/2.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def get(url, tries=3):
    last = None
    for i in range(tries):
        try:
            return _once(url)
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def send_batch():
    j = get(f"{API}?action=mail_pull&mkey={KEY}&_={int(time.time())}")
    if not j.get("ok"):
        log("pull error: %s" % j)
        return
    items = j.get("data", {}).get("list") or []
    if not items:
        return
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        s = smtplib.SMTP_SSL("smtp.qq.com", 465, context=ctx, timeout=25)
        s.login(USER, PASS)
    except Exception as e:
        log("smtp login failed: %s" % e)
        return
    for m in items:
        code = str(m["code"])
        label = LABELS.get(m.get("kind"), "验证")
        try:
            msg = EmailMessage()
            msg["From"] = formataddr((NAME, USER))
            msg["To"] = m["email"]
            msg["Subject"] = f"【微聊】验证码 {code}"
            msg["Date"] = formatdate(localtime=True)
            msg.set_content(f"你的微聊验证码是 {code}\n\n用于{label}，10 分钟内有效，只能用一次。\n\n—— 微聊")
            msg.add_alternative(
                '<div style="font-family:-apple-system,PingFang SC,sans-serif;padding:24px;background:#f5f6f7;">'
                '<div style="max-width:480px;margin:0 auto;background:#fff;border-radius:16px;overflow:hidden;">'
                '<div style="background:#07C160;padding:18px 24px;color:#fff;font-size:16px;font-weight:700;letter-spacing:3px;">微聊</div>'
                '<div style="padding:26px 24px;">'
                f'<div style="font-size:14px;color:#222;">你正在进行 <b>{label}</b>，验证码是：</div>'
                '<div style="margin:18px 0;padding:16px;background:#f2fbf6;border-radius:12px;text-align:center;">'
                f'<span style="font-size:32px;font-weight:800;letter-spacing:8px;color:#0b6b3a;">{code}</span></div>'
                '<div style="font-size:12px;color:#888;line-height:1.8;">10 分钟内有效，只能用一次。不要把这封邮件转发给任何人。</div>'
                '</div></div></div>',
                subtype="html",
            )
            s.send_message(msg)
            log("sent -> %s  code=%s  (%s)" % (m["email"], code, label))
        except Exception as e:
            log("fail -> %s : %s" % (m["email"], e))
    try:
        s.quit()
    except Exception:
        pass


def main():
    if not (KEY and USER and PASS):
        log("missing config: WL_KEY / SMTP_USER / SMTP_PASS")
        sys.exit(2)
    log("relay start, api=%s, run=%ss" % (API, RUN_SECONDS))
    end = time.time() + RUN_SECONDS
    while time.time() < end:
        try:
            send_batch()
        except Exception as e:
            log("loop err: %s" % e)
        time.sleep(POLL)
    log("relay stop (time up)")


if __name__ == "__main__":
    main()
