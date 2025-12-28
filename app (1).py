import re
import requests
import streamlit as st
from bs4 import BeautifulSoup
from urllib.parse import urlparse

CLICKBAIT_WORDS = ["衝撃","絶対","閲覧注意","暴露","裏ワザ","知らないと損","緊急","拡散希望"]

CONTACT_HINTS = [
    "運営者","会社概要","お問い合わせ","問合せ","連絡先",
    "特定商取引法","編集方針","プライバシー","利用規約",
    "免責","著作権","サイトポリシー","About","運営","法人"
]

AD_PATTERNS = [
    r"ads", r"doubleclick", r"affiliate", r"utm_",
    r"hb\.afl\.rakuten\.co\.jp", r"kaereba\.com", r"スポンサーリンク"
]

def strip_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script","style","noscript"]):
        t.decompose()
    return soup.get_text("\n")

def analyze_site(url: str) -> dict:
    if not re.match(r"^https?://", url, re.I):
        return {"ok": False, "error": "URLは http(s):// から始めてね"}

    host = urlparse(url).hostname or ""
    if host in ["localhost","127.0.0.1","0.0.0.0","169.254.169.254"]:
        return {"ok": False, "error": "blocked host"}

    try:
        r = requests.get(url, timeout=12, headers={"User-Agent":"VerifierMVP/1.0"})
        r.encoding = r.apparent_encoding
        r.raise_for_status()
    except Exception as e:
        return {"ok": False, "error": f"fetch failed: {e}"}

    html = r.text
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    text = strip_text(html)

    hrefs = " ".join(a.get("href","") for a in soup.find_all("a"))
    has_contact = (any(h in text for h in CONTACT_HINTS) or any(h in hrefs for h in CONTACT_HINTS))

    signals = {
        "is_https": url.startswith("https://"),
        "title": title[:200],
        "has_contact_info_like": has_contact,
        "has_any_links": bool(re.search(r"https?://", html)),
        "ad_like_tokens": sum(len(re.findall(p, html, flags=re.I)) for p in AD_PATTERNS),
        "clickbait_in_title": sum(1 for w in CLICKBAIT_WORDS if w in title),
    }

    score = 60
    score += 5 if signals["is_https"] else -10
    score += 10 if signals["has_contact_info_like"] else -10
    score += 5 if signals["has_any_links"] else -8

    if signals["ad_like_tokens"] > 30:
        score -= 12
    elif signals["ad_like_tokens"] > 10:
        score -= 6

    score -= min(signals["clickbait_in_title"] * 6, 18)
    score = max(0, min(100, score))

    if score >= 75:
        verdict = "比較的信頼できそう（ただし要確認）"
    elif score >= 45:
        verdict = "判断保留（わからない / 追加確認推奨）"
    else:
        verdict = "注意（ミスリードや虚偽の可能性）"

    return {"ok": True, "score": score, "verdict": verdict, "signals": signals}


# ---- UI ----
st.set_page_config(page_title="サイト信頼度チェッカー（MVP）", layout="wide")
st.title("サイト信頼度チェッカー（MVP）")
st.caption("※ このツールは断定しません。照合できない場合は「わからない」寄りに表示します。")

# Keep the URL in session so the user can tweak and re-run easily
if "url" not in st.session_state:
    st.session_state.url = ""

col_url, col_btn = st.columns([12, 2], vertical_alignment="bottom")
with col_url:
    st.session_state.url = st.text_input("", value=st.session_state.url, placeholder="https://example.com", label_visibility="collapsed")
with col_btn:
    run = st.button("チェック", use_container_width=True)

if run:
    url = (st.session_state.url or "").strip()
    if not url:
        st.error("URLを入力してください（https:// から）")
    else:
        res = analyze_site(url)
        if not res.get("ok"):
            st.error(f"わからない: {res.get('error')}")
        else:
            st.subheader("結果")
            st.write(f"**スコア:** {res['score']} / 100")
            st.write(f"**判定:** {res['verdict']}")
            with st.expander("根拠（検出シグナル）"):
                st.json(res["signals"])
