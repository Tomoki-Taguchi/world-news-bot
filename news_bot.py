import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from deep_translator import GoogleTranslator

BOT_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
CHAT_ID = os.environ['TELEGRAM_CHAT_ID']
MODE = os.environ.get('MODE', 'regular')  # 'regular' or 'breaking'

JST = timezone(timedelta(hours=9))

SOURCES = {
    'Reuters':          'https://news.google.com/rss/search?q=site:reuters.com&hl=en-US&gl=US&ceid=US:en',
    'AP News':          'https://news.google.com/rss/search?q=site:apnews.com&hl=en-US&gl=US&ceid=US:en',
    'Financial Times':  'https://news.google.com/rss/search?q=site:ft.com&hl=en-US&gl=US&ceid=US:en',
    'Bloomberg':        'https://news.google.com/rss/search?q=site:bloomberg.com&hl=en-US&gl=US&ceid=US:en',
}

BREAKING_FEEDS = [
    'https://news.google.com/rss/search?q=breaking+news&hl=en-US&gl=US&ceid=US:en',
    'https://news.google.com/rss/search?q=site:reuters.com+breaking&hl=en-US&gl=US&ceid=US:en',
    'https://news.google.com/rss/search?q=site:apnews.com+urgent&hl=en-US&gl=US&ceid=US:en',
]

BREAKING_KEYWORDS = [
    'breaking', 'urgent', 'emergency', 'attack', 'explosion', 'earthquake',
    'tsunami', 'crash', 'killed', 'assassination', 'coup', 'war declared',
    'nuclear', 'missile strike', 'mass shooting', 'collapsed',
]


def fetch_rss(url, limit=4):
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; NewsBot/1.0)'}
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    items = []
    for item in root.findall('.//item')[:limit]:
        title = item.findtext('title', '').strip()
        if ' - ' in title:
            title = title.rsplit(' - ', 1)[0]
        pub_date = item.findtext('pubDate', '')
        items.append({'title': title, 'pub_date': pub_date})
    return items


def translate(text):
    try:
        return GoogleTranslator(source='auto', target='ja').translate(text[:500])
    except Exception:
        return text


def send_telegram(text):
    if len(text) > 4096:
        text = text[:4090] + '...'
    r = requests.post(
        f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
        data={'chat_id': CHAT_ID, 'text': text, 'parse_mode': 'HTML'},
        timeout=15,
    )
    r.raise_for_status()


def run_regular():
    now = datetime.now(JST)
    date_str = now.strftime('%Y年%m月%d日')
    hour = now.hour
    if hour < 12:
        label = '朝刊'
    elif hour < 17:
        label = '昼刊'
    else:
        label = '夕刊'

    lines = [f'🌍 <b>世界ニュース{label}</b> — {date_str}\n']

    for source, url in SOURCES.items():
        lines.append('━━━━━━━━━━━━━━')
        lines.append(f'📡 <b>{source}</b>\n')
        try:
            items = fetch_rss(url)
            for i, item in enumerate(items, 1):
                ja = translate(item['title'])
                lines.append(f'{i}. <b>{ja}</b>')
            lines.append('')
        except Exception as e:
            lines.append(f'取得エラー: {e}\n')

    lines += ['━━━━━━━━━━━━━━', '🔍 ソース: Google News RSS経由', '⏰ 配信: Claude News Bot']
    send_telegram('\n'.join(lines))
    print('Regular news sent.')


def run_breaking():
    seen = set()
    alerts = []

    for url in BREAKING_FEEDS:
        try:
            items = fetch_rss(url, limit=10)
            for item in items:
                title_lower = item['title'].lower()
                if any(kw in title_lower for kw in BREAKING_KEYWORDS):
                    key = title_lower[:60]
                    if key not in seen:
                        seen.add(key)
                        alerts.append(item['title'])
        except Exception:
            continue

    if not alerts:
        print('No breaking news. Nothing sent.')
        return

    lines = ['🚨 <b>速報</b>\n']
    for title in alerts[:3]:
        ja = translate(title)
        lines.append(f'• <b>{ja}</b>')
    lines += ['', '🔍 ソース: Google News RSS経由']
    send_telegram('\n'.join(lines))
    print(f'Breaking news sent: {len(alerts)} item(s).')


if __name__ == '__main__':
    if MODE == 'breaking':
        run_breaking()
    else:
        run_regular()
