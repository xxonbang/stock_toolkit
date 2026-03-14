import re
from statistics import mean

NEWS_TYPE_PATTERNS = {
    "FDA 승인": r"FDA.*(승인|허가)",
    "실적 서프라이즈": r"실적.*(서프라이즈|깜짝|호실적|어닝)",
    "대규모 수주": r"(대규모|대형).*(수주|계약)",
    "공매도 리포트": r"(공매도|숏셀링).*(리포트|보고서)",
    "유상증자": r"유상증자",
    "목표가 상향": r"목표가.*(상향|상승)",
    "정부 정책": r"(정부|정책|규제).*(발표|시행)",
    "경영권": r"경영권.*(분쟁|변동)",
}


def classify_news_type(title: str) -> str:
    for news_type, pattern in NEWS_TYPE_PATTERNS.items():
        if re.search(pattern, title):
            return news_type
    return "기타"


def calculate_impact_stats(impacts: list) -> dict:
    if not impacts:
        return {"count": 0}
    d1 = [i.get("return_d1", 0) for i in impacts]
    d3 = [i.get("return_d3", 0) for i in impacts]
    d5 = [i.get("return_d5", 0) for i in impacts]
    return {
        "count": len(impacts),
        "avg_d1": round(mean(d1), 1),
        "avg_d3": round(mean(d3), 1),
        "avg_d5": round(mean(d5), 1),
        "max_d5": round(max(d5), 1),
        "min_d5": round(min(d5), 1),
        "positive_rate_d5": round(sum(1 for v in d5 if v > 0) / len(d5) * 100, 1),
    }


def build_impact_database(theme_history: list) -> dict:
    db = {}
    for snapshot in theme_history:
        data = snapshot.get("data", {})
        date = snapshot.get("date", "")
        for stock in data.get("rising_stocks", []):
            for news in stock.get("news", []):
                news_type = classify_news_type(news.get("title", ""))
                if news_type not in db:
                    db[news_type] = []
                db[news_type].append({
                    "date": date,
                    "code": stock.get("code"),
                    "name": stock.get("name"),
                    "title": news.get("title"),
                    "return_d1": stock.get("return_d1", 0),
                    "return_d3": stock.get("return_d3", 0),
                    "return_d5": stock.get("return_d5", 0),
                })
    return db


def format_news_impact_alert(news_type: str, stats: dict, stock: dict) -> str:
    return (
        f"<b>[뉴스 임팩트] {stock.get('name', '')}</b>\n"
        f"유형: {news_type}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"과거 유사 뉴스 ({stats['count']}건):\n"
        f"  D+1 평균: {stats['avg_d1']:+.1f}%\n"
        f"  D+5 평균: {stats['avg_d5']:+.1f}%\n"
        f"  상승 확률: {stats['positive_rate_d5']}%\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
