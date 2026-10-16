#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Парсер экспорта Telegram Desktop HTML для дашборда Пиратской Станции.
Обрабатывает как ZIP-архив, так и распакованную папку ChatExport_*.
Формирует chat_dashboard_data.json и обновляет dashboard_data_latest.js.
"""

import os
import re
import sys
import json
import math

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import zipfile
import tempfile
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict
from bs4 import BeautifulSoup

RUSSIAN_STOPWORDS = {
    "и", "в", "во", "не", "что", "он", "на", "я", "с", "со", "как", "а", "то", "все", "она",
    "так", "его", "но", "да", "ты", "к", "у", "же", "вы", "за", "бы", "по", "только", "ее",
    "мне", "было", "вот", "от", "меня", "еще", "нет", "о", "из", "ему", "теперь", "когда",
    "даже", "ну", "вдруг", "ли", "если", "уже", "или", "ни", "быть", "был", "него", "до",
    "вас", "нибудь", "опять", "уж", "вам", "ведь", "там", "потом", "себя", "ничего", "ей",
    "может", "они", "тут", "где", "есть", "надо", "ней", "для", "мы", "тебя", "их", "чем",
    "была", "сам", "чтоб", "без", "будто", "чего", "раз", "тоже", "себе", "под", "будет",
    "ж", "тогда", "кто", "этот", "того", "потому", "этого", "какой", "совсем", "ним", "здесь",
    "этом", "один", "почти", "мой", "тем", "чтобы", "нее", "сейчас", "были", "куда", "зачем",
    "всех", "никогда", "можно", "при", "наконец", "два", "об", "другой", "хоть", "после",
    "над", "больше", "тот", "через", "эти", "нас", "про", "всего", "них", "какая", "много",
    "разве", "три", "эту", "моя", "впрочем", "хорошо", "свою", "этой", "перед", "иногда",
    "лучше", "чуть", "том", "нельзя", "такой", "им", "более", "всегда", "конечно", "всю",
    "между", "это", "просто", "свои", "будут", "могу", "буду", "очень"
}

EMOJI_PATTERN = re.compile(
    r"[\U00010000-\U0010ffff\u2600-\u26ff\u2700-\u27bf\u1f300-\u1f5ff\u1f600-\u1f64f\u1f680-\u1f6ff\u1f1e0-\u1f1ff]",
    flags=re.UNICODE
)
URL_PATTERN = re.compile(r"https?://(?:www\.)?([^\s/$.?#].[^\s/]*)", re.IGNORECASE)
HASHTAG_PATTERN = re.compile(r"#(\w+)", re.UNICODE)
MENTION_PATTERN = re.compile(r"@([a-zA-Z0-9_]+)")
WORD_PATTERN = re.compile(r"[a-zA-Zа-яА-ЯёЁ0-9_-]{2,}")
LAUGH_PATTERN = re.compile(r"(?:х[аеиох]{2,}|[aа]хах|кек|лол|lol|xd|хд|😂|🤣)", re.IGNORECASE)


def parse_export_source(source_path: Path):
    temp_dir = None
    if source_path.is_file() and source_path.suffix.lower() == ".zip":
        print(f"📦 Распаковка ZIP-архива: {source_path}...")
        temp_dir = tempfile.TemporaryDirectory()
        with zipfile.ZipFile(source_path, "r") as z:
            z.extractall(temp_dir.name)
        root_dir = Path(temp_dir.name)
    else:
        root_dir = source_path

    def get_file_index(p):
        m = re.search(r"messages(\d+)?\.html$", p.name)
        if not m or not m.group(1):
            return 1
        return int(m.group(1))

    html_files = sorted(root_dir.glob("**/messages*.html"), key=get_file_index)
    if not html_files:
        raise FileNotFoundError(f"Файлы messages*.html не найдены в {source_path}")

    export_dir = html_files[0].parent
    print(f"📁 Найдена папка с экспортом: {export_dir}")
    print(f"📄 Найдено HTML файлов: {len(html_files)}")
    return html_files, export_dir, temp_dir


def scan_assets(export_dir: Path):
    folders_count = Counter()
    ext_count = Counter()
    total_files = 0
    key_counts = {
        "photos": 0,
        "photoThumbs": 0,
        "stickers": 0,
        "animatedStickers": 0,
        "videoFiles": 0,
        "videoStickers": 0,
        "voiceMessages": 0,
        "roundVideoMessages": 0,
        "files": 0
    }

    for root, dirs, files in os.walk(export_dir):
        rel_root = Path(root).relative_to(export_dir)
        folder_name = rel_root.parts[0] if rel_root.parts else ""
        for f in files:
            total_files += 1
            ext = Path(f).suffix.lower()
            ext_count[ext] += 1
            if folder_name:
                folders_count[folder_name] += 1

            # Key counts mapping
            if "photo" in folder_name:
                if "thumb" in f.lower():
                    key_counts["photoThumbs"] += 1
                else:
                    key_counts["photos"] += 1
            elif "round_video" in folder_name:
                key_counts["roundVideoMessages"] += 1
            elif "video_files" in folder_name or "video" in folder_name:
                if ext == ".webm":
                    key_counts["videoStickers"] += 1
                else:
                    key_counts["videoFiles"] += 1
            elif "voice" in folder_name:
                key_counts["voiceMessages"] += 1
            elif "sticker" in folder_name:
                if ext == ".tgs":
                    key_counts["animatedStickers"] += 1
                elif ext == ".webm":
                    key_counts["videoStickers"] += 1
                else:
                    key_counts["stickers"] += 1
            elif "files" in folder_name:
                key_counts["files"] += 1

    return {
        "folders": [{"name": k, "value": v} for k, v in folders_count.most_common()],
        "extensions": [{"name": k, "value": v} for k, v in ext_count.most_common() if k],
        "keyCounts": key_counts,
        "totalFiles": total_files
    }


def parse_messages(html_files):
    total_html_messages = 0
    ignored_service = 0
    ignored_moderation = 0

    messages = []
    current_sender = "Неизвестно"
    current_iso_date = None

    for file_path in html_files:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            soup = BeautifulSoup(f.read(), "lxml")

        msg_divs = soup.find_all("div", class_=lambda c: c and "message" in c)
        for msg in msg_divs:
            classes = msg.get("class", [])
            total_html_messages += 1

            if "service" in classes:
                ignored_service += 1
                continue

            # Sender name (if block continues from same user, sender might be omitted)
            sender_elem = msg.find("div", class_="from_name")
            if sender_elem:
                current_sender = sender_elem.get_text(strip=True)

            # Moderation / bot check
            if current_sender in ("Group Butler", "Butler", "Telegram"):
                ignored_moderation += 1
                continue

            body = msg.find("div", class_="body")
            if not body:
                body = msg

            # Date details
            date_elem = body.find(class_=lambda c: c and "date" in c)
            iso_date = None
            if date_elem and date_elem.get("title"):
                raw_dt = date_elem["title"]
                # Format: 06.05.2026 15:43:09 UTC+02:00
                m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}:\d{2}:\d{2})\s*(?:UTC([+-]\d{2}:\d{2}))?", raw_dt)
                if m:
                    d, mo, y, t, tz = m.groups()
                    tz_suffix = tz if tz else "+00:00"
                    iso_date = f"{y}-{mo}-{d}T{t}{tz_suffix}"
                    current_iso_date = iso_date
            if not iso_date:
                iso_date = current_iso_date

            # Text
            text_elem = body.find("div", class_="text")
            text = text_elem.get_text(separator=" ", strip=True) if text_elem else ""

            # Check moderation commands
            if text.startswith(("/", "!warn", "!ban", "!kick", "!mute")):
                ignored_moderation += 1
                continue

            # Reply
            reply_elem = body.find("div", class_="reply_to")
            is_reply = bool(reply_elem)

            # Media detection
            media_type = None
            media_wrap = body.find(class_=lambda c: c and ("media_wrap" in c or "media" in c))
            if media_wrap:
                title_elem = media_wrap.find(class_="title")
                title_text = title_elem.get_text(strip=True).lower() if title_elem else ""

                if "sticker" in title_text or media_wrap.find(class_=lambda c: c and "sticker" in c):
                    if ".webm" in str(media_wrap) or "video" in str(media_wrap):
                        media_type = "video_sticker"
                    elif ".tgs" in str(media_wrap) or "animated" in str(media_wrap):
                        media_type = "animated_sticker"
                    else:
                        media_type = "sticker"
                elif "animation" in title_text or "gif" in title_text:
                    media_type = "video_sticker"
                elif "round video" in title_text or media_wrap.find(class_=lambda c: c and "round" in c):
                    media_type = "round_video"
                elif "video file" in title_text or "video" in title_text or media_wrap.find(class_=lambda c: c and "media_video" in c):
                    media_type = "video"
                elif "voice message" in title_text or media_wrap.find(class_=lambda c: c and "voice" in c):
                    media_type = "voice"
                elif "photo" in title_text or media_wrap.find(class_=lambda c: c and "photo" in c):
                    media_type = "photo"
                elif media_wrap.find(class_=lambda c: c and "media_file" in c) or "." in title_text:
                    media_type = "file"
                else:
                    media_type = "media"

            # Reactions
            reactions = []
            react_div = body.find(class_=lambda c: c and "reactions" in c)
            if react_div:
                for r_span in react_div.find_all(class_=lambda c: c and "reaction" in c):
                    emoji = r_span.find(class_=lambda c: c and "emoji" in c)
                    em_text = emoji.get_text(strip=True) if emoji else ""
                    cnt_elem = r_span.find(class_=lambda c: c and "count" in c)
                    userpics = r_span.find_all(class_=lambda c: c and "userpic" in c)
                    if cnt_elem and cnt_elem.get_text(strip=True).isdigit():
                        cnt_val = int(cnt_elem.get_text(strip=True))
                    elif userpics:
                        cnt_val = len(userpics)
                    else:
                        cnt_val = 1
                    if em_text:
                        reactions.append((em_text, cnt_val))

            messages.append({
                "sender": current_sender,
                "date": iso_date,
                "text": text,
                "is_reply": is_reply,
                "media_type": media_type,
                "reactions": reactions
            })

    return messages, total_html_messages, ignored_service, ignored_moderation


def compile_statistics(messages, total_html, ignored_service, ignored_moderation, asset_inventory, export_dir, source_files_count):
    if not messages:
        raise ValueError("Нет сообщений для анализа!")

    messages.sort(key=lambda m: m["date"])
    date_start = messages[0]["date"]
    date_end = messages[-1]["date"]

    dt_start = datetime.fromisoformat(date_start[:19])
    dt_end = datetime.fromisoformat(date_end[:19])
    days_span = max((dt_end - dt_start).days + 1, 1)

    analyzed_count = len(messages)
    user_msgs = defaultdict(list)
    days_map = defaultdict(lambda: {"messages": 0, "words": 0, "media": 0, "users": set(), "user_counts": Counter()})
    hours_count = Counter()
    weekdays_count = Counter()
    heatmap_count = Counter()
    minute_count = Counter()

    words_raw = Counter()
    words_meaningful = Counter()
    bigrams = Counter()
    trigrams = Counter()
    hashtags = Counter()
    mentions = Counter()
    domains = Counter()
    emojis = Counter()
    reaction_emojis = Counter()
    media_types_count = Counter()

    total_words = 0
    total_chars = 0
    reply_count = 0
    media_messages_count = 0
    media_items_count = 0
    link_items_count = 0
    reaction_items_count = 0

    lang_counts = Counter()
    message_lengths = []
    reacted_messages = []

    weekday_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

    for m in messages:
        sender = m["sender"]
        user_msgs[sender].append(m)
        text = m["text"]
        dt = datetime.fromisoformat(m["date"][:19])
        date_str = dt.strftime("%Y-%m-%d")
        hour_str = dt.strftime("%H")
        weekday_idx = dt.weekday()
        weekday_str = weekday_names[weekday_idx]
        minute_str = dt.strftime("%Y-%m-%d %H:%M")

        # Time distributions
        hours_count[hour_str] += 1
        weekdays_count[weekday_str] += 1
        heatmap_count[(weekday_str, hour_str)] += 1
        minute_count[minute_str] += 1

        # Text metrics
        chars = len(text)
        total_chars += chars
        message_lengths.append(chars)

        # Words
        tokens = [w.lower() for w in WORD_PATTERN.findall(text)]
        w_count = len(tokens)
        total_words += w_count

        # Language detection
        if not text:
            lang_counts["no_text"] += 1
        else:
            cyrillic_chars = len(re.findall(r"[а-яА-ЯёЁ]", text))
            latin_chars = len(re.findall(r"[a-zA-Z]", text))
            if cyrillic_chars > latin_chars:
                lang_counts["cyrillic"] += 1
            elif latin_chars > cyrillic_chars:
                lang_counts["latin"] += 1
            else:
                lang_counts["other_text"] += 1

        for w in tokens:
            words_raw[w] += 1
            if len(w) >= 3 and w not in RUSSIAN_STOPWORDS:
                words_meaningful[w] += 1

        for i in range(len(tokens) - 1):
            w1, w2 = tokens[i], tokens[i + 1]
            if len(w1) >= 3 and len(w2) >= 3:
                bigrams[f"{w1} {w2}"] += 1

        for i in range(len(tokens) - 2):
            w1, w2, w3 = tokens[i], tokens[i + 1], tokens[i + 2]
            if len(w1) >= 3 and len(w2) >= 3 and len(w3) >= 3:
                trigrams[f"{w1} {w2} {w3}"] += 1

        # Links & Domains
        found_urls = URL_PATTERN.findall(text)
        link_items_count += len(found_urls)
        for dom in found_urls:
            dom_clean = dom.split(":")[0].lower()
            domains[dom_clean] += 1

        # Hashtags & Mentions
        for h in HASHTAG_PATTERN.findall(text):
            hashtags[h.lower()] += 1
        for men in MENTION_PATTERN.findall(text):
            mentions[f"@{men.lower()}"] += 1

        # Emojis in text
        for em in EMOJI_PATTERN.findall(text):
            emojis[em] += 1

        # Media
        is_media = bool(m["media_type"])
        if is_media:
            media_messages_count += 1
            media_items_count += 1
            media_types_count[m["media_type"]] += 1

        # Replies
        if m["is_reply"]:
            reply_count += 1

        # Reactions
        total_react_msg = sum(c for _, c in m["reactions"])
        reaction_items_count += total_react_msg
        for r_em, r_cnt in m["reactions"]:
            reaction_emojis[r_em] += r_cnt

        if total_react_msg >= 3:
            reacted_messages.append({
                "sender": sender,
                "date": m["date"],
                "reactions": total_react_msg,
                "emojis": " ".join(r[0] for r in m["reactions"]),
                "preview": (text[:160] + "…") if len(text) > 160 else text
            })

        # Day breakdown
        d_info = days_map[date_str]
        d_info["messages"] += 1
        d_info["words"] += w_count
        if is_media:
            d_info["media"] += 1
        d_info["users"].add(sender)
        d_info["user_counts"][sender] += 1

    # Lexical entropy
    lexical_entropy = 0.0
    if total_words > 0:
        for cnt in words_meaningful.values():
            p = cnt / total_words
            if p > 0:
                lexical_entropy -= p * math.log2(p)

    # Top users calculation
    top_users = []
    top_media_users_cnt = Counter()
    top_questioners_cnt = Counter()
    top_exclaimers_cnt = Counter()
    top_laughers_cnt = Counter()
    top_reply_users_cnt = Counter()
    top_link_users_cnt = Counter()

    for user, u_msgs in user_msgs.items():
        u_msg_cnt = len(u_msgs)
        u_words = 0
        u_chars = 0
        u_media = 0
        u_replies = 0
        u_links = 0
        u_reactions_received = 0
        u_questions = 0
        u_exclamations = 0
        u_laughs = 0
        u_active_days = set()
        u_words_cnt = Counter()
        u_media_cnt = Counter()

        for um in u_msgs:
            t = um["text"]
            u_active_days.add(um["date"][:10])
            u_chars += len(t)
            tokens = [w.lower() for w in WORD_PATTERN.findall(t)]
            u_words += len(tokens)
            for w in tokens:
                if len(w) >= 3 and w not in RUSSIAN_STOPWORDS:
                    u_words_cnt[w] += 1

            if um["is_reply"]:
                u_replies += 1
            if um["media_type"]:
                u_media += 1
                u_media_cnt[um["media_type"]] += 1
            if "?" in t:
                u_questions += 1
            if "!" in t:
                u_exclamations += 1
            if LAUGH_PATTERN.search(t):
                u_laughs += 1
            found_urls = URL_PATTERN.findall(t)
            u_links += len(found_urls)
            u_reactions_received += sum(c for _, c in um["reactions"])

        top_word = u_words_cnt.most_common(1)[0][0] if u_words_cnt else ""
        fav_media = u_media_cnt.most_common(1)[0][0] if u_media_cnt else ""

        top_users.append({
            "name": user,
            "messages": u_msg_cnt,
            "share": round((u_msg_cnt / analyzed_count) * 100, 2),
            "words": u_words,
            "avgWords": round(u_words / u_msg_cnt, 2),
            "chars": u_chars,
            "avgChars": round(u_chars / u_msg_cnt, 1),
            "media": u_media,
            "replies": u_replies,
            "links": u_links,
            "reactionsReceived": u_reactions_received,
            "questions": u_questions,
            "exclamations": u_exclamations,
            "laughs": u_laughs,
            "activeDays": len(u_active_days),
            "first": u_msgs[0]["date"],
            "last": u_msgs[-1]["date"],
            "topWord": top_word,
            "favoriteMedia": fav_media
        })

        top_media_users_cnt[user] = u_media
        top_questioners_cnt[user] = u_questions
        top_exclaimers_cnt[user] = u_exclamations
        top_laughers_cnt[user] = u_laughs
        top_reply_users_cnt[user] = u_replies
        top_link_users_cnt[user] = u_links

    top_users.sort(key=lambda u: u["messages"], reverse=True)

    # Days list
    days_list = []
    for d_str in sorted(days_map.keys()):
        info = days_map[d_str]
        top_day_user, top_day_user_cnt = info["user_counts"].most_common(1)[0]
        days_list.append({
            "date": d_str,
            "messages": info["messages"],
            "words": info["words"],
            "media": info["media"],
            "activeUsers": len(info["users"]),
            "topUser": top_day_user,
            "topUserMessages": top_day_user_cnt
        })

    top_days = sorted(days_list, key=lambda d: d["messages"], reverse=True)

    # Percentiles
    message_lengths.sort()
    def get_pct(p):
        if not message_lengths:
            return 0
        idx = int(len(message_lengths) * (p / 100.0))
        return message_lengths[min(idx, len(message_lengths) - 1)]

    # Longest messages
    longest_messages = []
    for m in sorted(messages, key=lambda x: len(x["text"]), reverse=True)[:10]:
        if len(m["text"]) > 100:
            longest_messages.append({
                "sender": m["sender"],
                "date": m["date"],
                "chars": len(m["text"]),
                "words": len(WORD_PATTERN.findall(m["text"])),
                "preview": (m["text"][:210] + "…") if len(m["text"]) > 210 else m["text"]
            })

    reacted_messages.sort(key=lambda r: r["reactions"], reverse=True)

    return {
        "meta": {
            "generatedAt": datetime.now().isoformat()[:19],
            "exportDir": str(export_dir),
            "sourceFiles": source_files_count,
            "note": "Group Butler, service messages and moderation commands/results are excluded from analytic rankings."
        },
        "overview": {
            "totalHtmlMessages": total_html,
            "analyzedMessages": analyzed_count,
            "ignoredService": ignored_service,
            "ignoredModeration": ignored_moderation,
            "participants": len(top_users),
            "dateStart": date_start,
            "dateEnd": date_end,
            "days": days_span,
            "totalWords": total_words,
            "uniqueWords": len(words_raw),
            "uniqueMeaningfulWords": len(words_meaningful),
            "avgMessagesPerDay": round(analyzed_count / days_span, 1),
            "avgWordsPerMessage": round(total_words / analyzed_count, 2),
            "avgCharsPerMessage": round(total_chars / analyzed_count, 1),
            "replyRate": round((reply_count / analyzed_count) * 100, 1),
            "mediaMessages": media_messages_count,
            "mediaItems": media_items_count,
            "linkItems": link_items_count,
            "reactionItems": reaction_items_count,
            "lexicalEntropy": round(lexical_entropy, 2)
        },
        "activity": {
            "topUsers": top_users,
            "top10Users": top_users[:10],
            "days": days_list,
            "topDays": top_days[:15],
            "hours": [{"hour": f"{h:02d}", "messages": hours_count[f"{h:02d}"]} for h in range(24)],
            "weekdays": [{"weekday": w, "messages": weekdays_count[w]} for w in weekday_names],
            "heatmap": [{"weekday": w, "hour": f"{h:02d}", "messages": heatmap_count[(w, f"{h:02d}")]} for w in weekday_names for h in range(24)],
            "mostLoadedMinutes": [{"minute": k, "messages": v} for k, v in minute_count.most_common(10)]
        },
        "content": {
            "topWords": [{"name": k, "value": v} for k, v in words_meaningful.most_common(80)],
            "topWordsRaw": [{"name": k, "value": v} for k, v in words_raw.most_common(40)],
            "topBigrams": [{"name": k, "value": v} for k, v in bigrams.most_common(40)],
            "topTrigrams": [{"name": k, "value": v} for k, v in trigrams.most_common(30)],
            "topHashtags": [{"name": k, "value": v} for k, v in hashtags.most_common(20)],
            "topMentions": [{"name": k, "value": v} for k, v in mentions.most_common(30)],
            "topDomains": [{"name": k, "value": v} for k, v in domains.most_common(30)],
            "topEmojis": [{"name": k, "value": v} for k, v in emojis.most_common(30)],
            "reactionEmojis": [{"name": k, "value": v} for k, v in reaction_emojis.most_common(30)],
            "language": [{"name": k, "value": v} for k, v in lang_counts.most_common()],
            "messageLength": {
                "min": min(message_lengths) if message_lengths else 0,
                "p50": get_pct(50),
                "p75": get_pct(75),
                "p90": get_pct(90),
                "p99": get_pct(99),
                "max": max(message_lengths) if message_lengths else 0
            },
            "longestMessages": longest_messages[:10],
            "topReactedMessages": reacted_messages[:15]
        },
        "media": {
            "types": [{"name": k, "value": v} for k, v in media_types_count.most_common()],
            "topMediaUsers": [{"name": k, "value": v} for k, v in top_media_users_cnt.most_common(15)],
            "assetInventory": asset_inventory
        },
        "behavior": {
            "topQuestioners": [{"name": k, "value": v} for k, v in top_questioners_cnt.most_common(10)],
            "topExclaimers": [{"name": k, "value": v} for k, v in top_exclaimers_cnt.most_common(10)],
            "topLaughers": [{"name": k, "value": v} for k, v in top_laughers_cnt.most_common(10)],
            "topReplyUsers": [{"name": k, "value": v} for k, v in top_reply_users_cnt.most_common(10)],
            "topLinkUsers": [{"name": k, "value": v} for k, v in top_link_users_cnt.most_common(10)]
        }
    }


def main():
    if len(sys.argv) < 2:
        print("Использование: python parse_export.py <путь_к_архиву_или_папке>")
        sys.exit(1)

    source = Path(sys.argv[1].strip('"'))
    if not source.exists():
        print(f"Ошибка: Путь не найден: {source}")
        sys.exit(1)

    html_files, export_dir, temp_dir = parse_export_source(source)
    print("⏳ Сканирование медиафайлов и каталогов...")
    assets = scan_assets(export_dir)

    print("⏳ Разбор сообщений из HTML файлов...")
    messages, total_html, ignored_service, ignored_moderation = parse_messages(html_files)

    print(f"📊 Собрано сообщений для анализа: {len(messages)} (сервисных: {ignored_service}, модераторских: {ignored_moderation})")
    print("⏳ Расчёт полной аналитической статистики...")
    result_data = compile_statistics(
        messages,
        total_html,
        ignored_service,
        ignored_moderation,
        assets,
        export_dir,
        len(html_files)
    )

    # Сохраняем chat_dashboard_data.json и chat_dashboard_data_latest.json
    project_dir = Path(__file__).resolve().parent
    json_path = project_dir / "chat_dashboard_data.json"
    latest_json_path = project_dir / "chat_dashboard_data_latest.json"
    js_latest_path = project_dir / "dashboard_data_latest.js"
    js_bundle_path = project_dir / "dashboard_data.js"

    print(f"💾 Запись {json_path}...")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)

    with open(latest_json_path, "w", encoding="utf-8") as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)

    compact_json = json.dumps(result_data, ensure_ascii=False, separators=(",", ":"))
    print(f"💾 Запись {js_latest_path}...")
    with open(js_latest_path, "w", encoding="utf-8") as f:
        f.write(f"window.CHAT_DATA_LATEST = {compact_json};\n")

    # Also keep dashboard_data.js up to date
    with open(js_bundle_path, "w", encoding="utf-8") as f:
        f.write(f"window.CHAT_DASHBOARD_DATA = {compact_json};\n")

    if temp_dir:
        temp_dir.cleanup()

    print("🎉 Успешно завершено!")
    print(f"Период: {result_data['overview']['dateStart']} — {result_data['overview']['dateEnd']}")
    print(f"Участников: {result_data['overview']['participants']}, Сообщений: {result_data['overview']['analyzedMessages']}")


if __name__ == "__main__":
    main()
