import os
import html
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from deep_translator import GoogleTranslator

JST = timezone(timedelta(hours=9))

INT_SOURCES = {
    'Reuters':         'https://news.google.com/rss/search?q=site:reuters.com&hl=en-US&gl=US&ceid=US:en',
    'AP News':         'https://news.google.com/rss/search?q=site:apnews.com&hl=en-US&gl=US&ceid=US:en',
    'Financial Times': 'https://news.google.com/rss/search?q=site:ft.com&hl=en-US&gl=US&ceid=US:en',
    'Bloomberg':       'https://news.google.com/rss/search?q=site:bloomberg.com&hl=en-US&gl=US&ceid=US:en',
    'BBC':             'https://feeds.bbci.co.uk/news/world/rss.xml',
}

JP_SOURCES = {
    'Yahoo!ニュース': 'https://news.yahoo.co.jp/rss/topics/top-picks.xml',
}

# Japanese → English keyword map for cross-referencing
JP_EN_MAP = {
    'トランプ': ['trump'],
    '習近平': ['xi', 'jinping'],
    'プーチン': ['putin'],
    'バイデン': ['biden'],
    'イスラエル': ['israel'],
    'ウクライナ': ['ukraine'],
    '中国': ['china', 'chinese'],
    '米国': ['united states', 'us ', 'america'],
    'アメリカ': ['united states', 'america'],
    'ロシア': ['russia', 'russian'],
    '北朝鮮': ['north korea'],
    '韓国': ['south korea'],
    'ガザ': ['gaza'],
    'イラン': ['iran'],
    '台湾': ['taiwan'],
    '日銀': ['bank of japan', 'boj'],
    'NATO': ['nato'],
    'EU': ['european union', ' eu '],
    'イギリス': ['uk', 'britain', 'british'],
    'フランス': ['france', 'french'],
    'ドイツ': ['germany', 'german'],
    'インド': ['india', 'indian'],
    'パレスチナ': ['palestine', 'palestinian'],
    'ホワイトハウス': ['white house'],
    '国連': ['united nations', ' un '],
    '連邦準備': ['federal reserve', 'fed '],
}


MEDIA_NS = 'http://search.yahoo.com/mrss/'


def extract_image(item):
    # media:content
    el = item.find(f'{{{MEDIA_NS}}}content')
    if el is not None:
        url = el.get('url', '')
        if url:
            return url
    # media:thumbnail
    el = item.find(f'{{{MEDIA_NS}}}thumbnail')
    if el is not None:
        url = el.get('url', '')
        if url:
            return url
    # enclosure
    el = item.find('enclosure')
    if el is not None and (el.get('type', '').startswith('image')):
        url = el.get('url', '')
        if url:
            return url
    # img tag inside description
    desc = item.findtext('description', '')
    if '<img' in desc:
        import re
        m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', desc)
        if m:
            return m.group(1)
    return None


def fetch_rss(url, limit=8):
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; NewsDashboard/1.0)'}
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    items = []
    for item in root.findall('.//item')[:limit]:
        title = item.findtext('title', '').strip()
        link = item.findtext('link', '').strip()
        if ' - ' in title:
            title = title.rsplit(' - ', 1)[0]
        image = extract_image(item)
        items.append({'title': title, 'link': link, 'image': image})
    return items


def translate(text):
    try:
        return GoogleTranslator(source='auto', target='ja').translate(text[:500])
    except Exception:
        return text


def find_related(jp_title, int_articles_flat):
    related = []
    for article in int_articles_flat:
        en_lower = article['title'].lower()
        for jp_kw, en_kws in JP_EN_MAP.items():
            if jp_kw in jp_title:
                if any(en_kw in en_lower for en_kw in en_kws):
                    if article not in related:
                        related.append(article)
                    break
    return related[:3]


def img_html(image):
    if not image:
        return ''
    src = html.escape(image)
    return f'<img class="card-img" src="{src}" alt="" loading="lazy" onerror="this.style.display=\'none\'">'


def card_int(article):
    ja = translate(article['title'])
    link = html.escape(article.get('link', '#'))
    return f'''
    <a class="card" href="{link}" target="_blank" rel="noopener">
      {img_html(article.get("image"))}
      <div class="card-body">
        <div class="card-ja">{html.escape(ja)}</div>
        <div class="card-en">{html.escape(article["title"])}</div>
      </div>
    </a>'''


def card_jp(article, related):
    link = html.escape(article.get('link', '#'))
    if related:
        rel_html = '<div class="related"><span class="rel-label">🌍 海外でも報道：</span>'
        for r in related:
            r_link = html.escape(r.get('link', '#'))
            rel_html += f'<a class="rel-item" href="{r_link}" target="_blank" rel="noopener"><span class="rel-src">{html.escape(r["source"])}</span> {html.escape(r["title"])}</a>'
        rel_html += '</div>'
    else:
        rel_html = '<div class="only-jp">🇯🇵 国内のみ</div>'

    return f'''
    <div class="card jp-card">
      {img_html(article.get("image"))}
      <div class="card-body">
        <a class="card-ja jp-title" href="{link}" target="_blank" rel="noopener">{html.escape(article["title"])}</a>
        {rel_html}
      </div>
    </div>'''


def build_html(int_news, jp_news, int_articles_flat):
    now = datetime.now(JST)
    updated = now.strftime('%Y年%m月%d日 %H:%M JST')

    int_section = ''
    for source, articles in int_news.items():
        cards = ''.join(card_int(a) for a in articles[:5])
        int_section += f'''
    <section class="source">
      <h2><span class="badge badge-int">{html.escape(source)}</span></h2>
      <div class="grid">{cards}</div>
    </section>'''

    jp_section = ''
    for source, articles in jp_news.items():
        cards = ''.join(card_jp(a, find_related(a['title'], int_articles_flat)) for a in articles)
        jp_section += f'''
    <section class="source">
      <h2><span class="badge badge-jp">🇯🇵 {html.escape(source)}</span> <span class="caution-tag">参考程度</span></h2>
      <div class="grid">{cards}</div>
    </section>'''

    return f'''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>World News Dashboard</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0f172a;color:#e2e8f0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;line-height:1.6}}
header{{background:#1e293b;padding:14px 20px;border-bottom:1px solid #1e3a5f;position:sticky;top:0;z-index:10}}
header h1{{font-size:1.1rem;font-weight:700;color:#f1f5f9}}
.updated{{font-size:.72rem;color:#64748b;margin-top:2px}}
main{{max-width:1280px;margin:0 auto;padding:24px 16px}}
.section-label{{font-size:.7rem;font-weight:700;letter-spacing:.1em;color:#475569;text-transform:uppercase;margin:32px 0 16px;padding-bottom:8px;border-bottom:1px solid #1e293b}}
.source{{margin-bottom:28px}}
.source h2{{display:flex;align-items:center;gap:8px;margin-bottom:10px}}
.badge{{padding:3px 10px;border-radius:4px;font-size:.78rem;font-weight:600}}
.badge-int{{background:#1e3a8a;color:#93c5fd}}
.badge-jp{{background:#7f1d1d;color:#fca5a5}}
.caution-tag{{font-size:.68rem;color:#f87171;background:#450a0a;padding:2px 8px;border-radius:4px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:10px}}
.card{{background:#1e293b;border:1px solid #334155;border-radius:8px;overflow:hidden;text-decoration:none;color:inherit;display:block;transition:border-color .15s}}
.card:hover{{border-color:#3b82f6}}
.card-img{{width:100%;height:160px;object-fit:cover;display:block}}
.card-body{{padding:12px}}
.card-ja{{font-size:.88rem;font-weight:600;color:#f1f5f9;margin-bottom:4px}}
.card-en{{font-size:.72rem;color:#64748b}}
.jp-card{{cursor:default}}
.jp-title{{font-size:.88rem;font-weight:600;color:#fca5a5;text-decoration:none;display:block;margin-bottom:6px}}
.jp-card .card-body{{padding:12px}}
.jp-title:hover{{text-decoration:underline}}
.related{{margin-top:8px;padding-top:8px;border-top:1px solid #1e293b}}
.rel-label{{font-size:.7rem;color:#6ee7b7;display:block;margin-bottom:4px}}
.rel-item{{display:block;font-size:.7rem;color:#93c5fd;text-decoration:none;margin-top:3px;line-height:1.4}}
.rel-item:hover{{text-decoration:underline}}
.rel-src{{font-weight:700}}
.only-jp{{display:inline-block;font-size:.68rem;color:#f87171;background:#450a0a;padding:2px 8px;border-radius:4px;margin-top:6px}}
</style>
</head>
<body>
<header>
  <h1>🌍 World News Dashboard</h1>
  <div class="updated">最終更新: {updated}</div>
</header>
<main>
  <div class="section-label">🌐 国際報道</div>
  {int_section}
  <div class="section-label">🇯🇵 国内報道（参考程度）</div>
  {jp_section}
</main>
</body>
</html>'''


def main():
    int_news, int_flat = {}, []
    for source, url in INT_SOURCES.items():
        try:
            articles = fetch_rss(url)
            for a in articles:
                a['source'] = source
            int_news[source] = articles
            int_flat.extend(articles)
            print(f'✓ {source}: {len(articles)} articles')
        except Exception as e:
            print(f'✗ {source}: {e}')

    jp_news = {}
    for source, url in JP_SOURCES.items():
        try:
            jp_news[source] = fetch_rss(url, limit=12)
            print(f'✓ {source}: {len(jp_news[source])} articles')
        except Exception as e:
            print(f'✗ {source}: {e}')

    os.makedirs('docs', exist_ok=True)
    with open('docs/index.html', 'w', encoding='utf-8') as f:
        f.write(build_html(int_news, jp_news, int_flat))
    print('✓ Site generated: docs/index.html')


if __name__ == '__main__':
    main()
