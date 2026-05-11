import streamlit as st
import pandas as pd
import feedparser
from openai import OpenAI
from dotenv import load_dotenv
import os
import re
from urllib.parse import quote
from datetime import datetime, date

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

st.set_page_config(layout="wide")
st.title("📈 AI 주식 급등 분석 앱")

HISTORY_FILE = "history.csv"
CUSTOM_STOCK_FILE = "custom_stocks.csv"

base_stock_info = {
    "삼성전자": {"시장": "국내", "코드": "005930", "업종": "반도체", "분류": "대형주"},
    "테슬라": {"시장": "해외", "코드": "TSLA", "업종": "전기차", "분류": "성장주"},
    "한화오션": {"시장": "국내", "코드": "042660", "업종": "조선", "분류": "수주/방산"},
    "현대로템": {"시장": "국내", "코드": "064350", "업종": "방산/철도", "분류": "방산주"},
    "에코프로": {"시장": "국내", "코드": "086520", "업종": "2차전지", "분류": "배터리"},
    "두산에너빌리티": {"시장": "국내", "코드": "034020", "업종": "원전/에너지", "분류": "정책주"},
    "NAVER": {"시장": "국내", "코드": "035420", "업종": "인터넷/AI", "분류": "플랫폼"},
    "카카오": {"시장": "국내", "코드": "035720", "업종": "인터넷/콘텐츠", "분류": "플랫폼"}
}

def normalize_bool(value):
    return str(value).lower() in ["true", "1", "yes", "y", "즐겨찾기"]

def safe_int(value, default=0):
    try:
        return int(float(value))
    except:
        return default

def render_news_links(news_text):
    news_lines = str(news_text).split("\n")

    for line in news_lines:
        line = line.strip()

        if not line:
            continue

        if " / http" in line:
            title_part = line.split(" / http")[0]
            link_part = "http" + line.split(" / http")[1]
            clean_title = title_part.split(". ", 1)[-1]
            st.markdown(f"- [{clean_title}]({link_part})")
        else:
            st.markdown(f"- {line}")

def normalize_history(history):
    normalized = []

    for item in history:
        item = dict(item)

        item.setdefault("시간", "")
        item.setdefault("시장", "미분류")
        item.setdefault("코드", "확인필요")
        item.setdefault("업종", "미분류")
        item.setdefault("분류", "직접입력")
        item.setdefault("종목", "")
        item.setdefault("등급", "판단불가")
        item.setdefault("뉴스", "")
        item.setdefault("AI분석", "")
        item.setdefault("메모", "")
        item.setdefault("즐겨찾기", False)
        item.setdefault("상승모멘텀점수", 0)
        item.setdefault("뉴스신뢰도점수", 0)
        item.setdefault("단기과열도점수", 0)
        item.setdefault("종합점수", 0)
        item.setdefault("상승이유", "")
        item.setdefault("리스크", "")

        item["즐겨찾기"] = normalize_bool(item["즐겨찾기"])
        item["상승모멘텀점수"] = safe_int(item["상승모멘텀점수"])
        item["뉴스신뢰도점수"] = safe_int(item["뉴스신뢰도점수"])
        item["단기과열도점수"] = safe_int(item["단기과열도점수"])
        item["종합점수"] = safe_int(item["종합점수"])

        normalized.append(item)

    return normalized

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            history = pd.read_csv(HISTORY_FILE).to_dict("records")
            return normalize_history(history)
        except:
            return []
    return []

def save_history(history):
    pd.DataFrame(normalize_history(history)).to_csv(
        HISTORY_FILE,
        index=False,
        encoding="utf-8-sig"
    )

def load_custom_stocks():
    if os.path.exists(CUSTOM_STOCK_FILE):
        try:
            df = pd.read_csv(CUSTOM_STOCK_FILE)
            custom_data = {}

            for _, row in df.iterrows():
                stock_name = str(row.get("종목명", "")).strip()

                if stock_name:
                    custom_data[stock_name] = {
                        "시장": str(row.get("시장", "미분류")),
                        "코드": str(row.get("코드", "확인필요")),
                        "업종": str(row.get("업종", "미분류")),
                        "분류": str(row.get("분류", "직접등록"))
                    }

            return custom_data
        except:
            return {}

    return {}

def save_custom_stocks(custom_stocks):
    rows = []

    for stock, info in custom_stocks.items():
        rows.append({
            "종목명": stock,
            "시장": info["시장"],
            "코드": info["코드"],
            "업종": info["업종"],
            "분류": info["분류"]
        })

    pd.DataFrame(rows).to_csv(
        CUSTOM_STOCK_FILE,
        index=False,
        encoding="utf-8-sig"
    )

if "history" not in st.session_state:
    st.session_state.history = load_history()

if "custom_stocks" not in st.session_state:
    st.session_state.custom_stocks = load_custom_stocks()

stock_info = {
    **base_stock_info,
    **st.session_state.custom_stocks
}

def get_stock_info(stock):
    return stock_info.get(stock, {
        "시장": "미분류",
        "코드": "확인필요",
        "업종": "미분류",
        "분류": "직접입력"
    })

def get_news_titles(stock):
    try:
        search_query = quote(f'{stock} 주식 OR 증권 OR 실적 OR 수주 OR 투자')
        news_url = f"https://news.google.com/rss/search?q={search_query}&hl=ko&gl=KR&ceid=KR:ko"
        feed = feedparser.parse(news_url)

        news_titles = []
        news_links = []

        for entry in feed.entries[:3]:
            news_titles.append(entry.title)
            news_links.append(entry.link)

        if len(news_titles) == 0:
            return [f"{stock} 관련 최신 뉴스가 충분하지 않습니다."], [""]

        return news_titles, news_links

    except Exception:
        return [f"{stock} 뉴스 조회 중 오류가 발생했습니다."], [""]

def extract_number(text, keyword):
    pattern = rf"{keyword}[^0-9]*(\d+)"
    match = re.search(pattern, text)

    if match:
        return safe_int(match.group(1))

    return 0

def extract_section(text, keyword):
    lines = text.splitlines()
    capture = False
    result_lines = []

    for line in lines:
        clean = line.strip()

        if keyword in clean:
            capture = True
            result_lines.append(clean.replace("-", "").strip())
            continue

        if capture:
            if clean.startswith("-") or clean.startswith("•"):
                result_lines.append(clean.replace("-", "").replace("•", "").strip())
            elif clean.startswith("[") and clean.endswith("]"):
                break

    return " / ".join([x for x in result_lines if x])[:300]

def calculate_total_score(momentum, reliability, overheat):
    score = int((momentum * 0.45) + (reliability * 0.35) - (overheat * 0.20))
    return max(0, min(100, score))

def calibrate_grade(ai_grade, total_score, overheat_score):
    if overheat_score >= 80:
        return "🔴 과열주의"

    if total_score >= 70:
        return "🟢 관심"

    if total_score >= 45:
        return "🟡 관망"

    if "과열주의" in ai_grade:
        return "🔴 과열주의"

    if "관망" in ai_grade:
        return "🟡 관망"

    if "관심" in ai_grade:
        return "🟢 관심"

    return "판단불가"

def analyze_stock(stock):
    info = get_stock_info(stock)
    news_titles, news_links = get_news_titles(stock)
    joined_news = "\n".join(news_titles)

    prompt = f"""
아래 뉴스들을 기준으로 투자 분석을 진행해주세요.

종목명: {stock}
종목분류: {info["시장"]} / {info["코드"]} / {info["업종"]} / {info["분류"]}

뉴스:
{joined_news}

반드시 아래 형식으로 작성해주세요.

[투자등급]
관심 / 관망 / 과열주의 중 하나만 출력

[AI 점수]
- 상승 모멘텀 점수: 0~100 숫자
- 뉴스 신뢰도 점수: 0~100 숫자
- 단기 과열도 점수: 0~100 숫자

[상승 이유]
- 핵심 상승 이유를 1~2줄로 작성

[리스크]
- 핵심 리스크를 1~2줄로 작성

[분석 요약]
- 핵심 이슈
- 투자 참고 의견

매수/매도 확정 표현은 피해주세요.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}]
        )

        result = response.choices[0].message.content

    except Exception as e:
        result = f"""
[투자등급]
판단불가

[AI 점수]
- 상승 모멘텀 점수: 0
- 뉴스 신뢰도 점수: 0
- 단기 과열도 점수: 0

[상승 이유]
- AI 분석 실패

[리스크]
- 오류 내용: {str(e)}

[분석 요약]
- API 키, 인터넷 연결, OpenAI 사용량 제한을 확인해주세요.
"""

    momentum_score = extract_number(result, "상승 모멘텀")
    reliability_score = extract_number(result, "뉴스 신뢰도")
    overheat_score = extract_number(result, "단기 과열도")
    total_score = calculate_total_score(momentum_score, reliability_score, overheat_score)

    if "과열주의" in result:
        raw_grade = "🔴 과열주의"
    elif "관망" in result:
        raw_grade = "🟡 관망"
    elif "관심" in result:
        raw_grade = "🟢 관심"
    else:
        raw_grade = "판단불가"

    grade = calibrate_grade(raw_grade, total_score, overheat_score)

    news_text_list = []

    for i, title in enumerate(news_titles):
        link = news_links[i] if i < len(news_links) else ""

        if link:
            news_text_list.append(f"{i+1}. {title} / {link}")
        else:
            news_text_list.append(f"{i+1}. {title}")

    return {
        "시간": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "시장": info["시장"],
        "코드": info["코드"],
        "업종": info["업종"],
        "분류": info["분류"],
        "종목": stock,
        "등급": grade,
        "뉴스": "\n".join(news_text_list),
        "AI분석": result,
        "메모": "",
        "즐겨찾기": False,
        "상승모멘텀점수": momentum_score,
        "뉴스신뢰도점수": reliability_score,
        "단기과열도점수": overheat_score,
        "종합점수": total_score,
        "상승이유": extract_section(result, "상승 이유"),
        "리스크": extract_section(result, "리스크")
    }

def upsert_history(record, keep_old_meta=True):
    old_memo = ""
    old_favorite = False

    if keep_old_meta:
        for item in st.session_state.history:
            if item.get("종목") == record.get("종목"):
                old_memo = item.get("메모", "")
                old_favorite = normalize_bool(item.get("즐겨찾기", False))
                break

    record["메모"] = old_memo
    record["즐겨찾기"] = old_favorite

    st.session_state.history = [
        item for item in st.session_state.history
        if item.get("종목") != record.get("종목")
    ]

    st.session_state.history.insert(0, record)
    save_history(st.session_state.history)

if st.button("🗑️ 전체 분석 기록 삭제"):
    st.session_state.history = []

    if os.path.exists(HISTORY_FILE):
        os.remove(HISTORY_FILE)

    st.success("전체 분석 기록이 삭제되었습니다.")
    st.rerun()

st.markdown("---")
st.subheader("➕ 종목 정보 관리")

with st.expander("직접 종목 등록 / 수정 / 삭제", expanded=False):
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        new_stock_name = st.text_input("종목명", placeholder="예: 현대차")

    with col2:
        new_market = st.selectbox("시장", ["국내", "해외", "미분류"])

    with col3:
        new_code = st.text_input("코드", placeholder="예: 005380")

    with col4:
        new_industry = st.text_input("업종", placeholder="예: 자동차")

    with col5:
        new_category = st.text_input("분류", placeholder="예: 완성차")

    if st.button("➕ 종목 등록 / 수정"):
        if new_stock_name.strip():
            st.session_state.custom_stocks[new_stock_name.strip()] = {
                "시장": new_market,
                "코드": new_code.strip() if new_code.strip() else "확인필요",
                "업종": new_industry.strip() if new_industry.strip() else "미분류",
                "분류": new_category.strip() if new_category.strip() else "직접등록"
            }

            save_custom_stocks(st.session_state.custom_stocks)
            st.success(f"{new_stock_name} 종목 정보가 저장되었습니다.")
            st.rerun()
        else:
            st.warning("종목명을 입력해주세요.")

    if len(st.session_state.custom_stocks) > 0:
        st.markdown("### 직접 등록한 종목")

        custom_df = pd.DataFrame([
            {
                "종목명": stock,
                "시장": info["시장"],
                "코드": info["코드"],
                "업종": info["업종"],
                "분류": info["분류"]
            }
            for stock, info in st.session_state.custom_stocks.items()
        ])

        st.dataframe(custom_df, use_container_width=True)

        delete_custom_stock = st.selectbox(
            "삭제할 직접 등록 종목 선택",
            list(st.session_state.custom_stocks.keys())
        )

        if st.button("🗑️ 선택 종목 삭제"):
            del st.session_state.custom_stocks[delete_custom_stock]
            save_custom_stocks(st.session_state.custom_stocks)
            st.success(f"{delete_custom_stock} 종목 정보가 삭제되었습니다.")
            st.rerun()

stock_info = {
    **base_stock_info,
    **st.session_state.custom_stocks
}

registered_df = pd.DataFrame([
    {
        "시장": info["시장"],
        "코드": info["코드"],
        "업종": info["업종"],
        "분류": info["분류"],
        "종목명": stock
    }
    for stock, info in stock_info.items()
])

st.markdown("---")
st.subheader("📊 AI 분석 기록 요약")

total_count = len(st.session_state.history)
favorite_count = len([item for item in st.session_state.history if normalize_bool(item.get("즐겨찾기", False))])
interest_count = len([item for item in st.session_state.history if "관심" in str(item.get("등급", ""))])
watch_count = len([item for item in st.session_state.history if "관망" in str(item.get("등급", ""))])
overheat_count = len([item for item in st.session_state.history if "과열주의" in str(item.get("등급", ""))])

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("전체 기록", total_count)
col2.metric("⭐ 즐겨찾기", favorite_count)
col3.metric("🟢 관심", interest_count)
col4.metric("🟡 관망", watch_count)
col5.metric("🔴 과열주의", overheat_count)

st.markdown("---")
st.subheader("📌 등록 종목 목록")
st.dataframe(registered_df, use_container_width=True)

st.markdown("---")
st.subheader("🔍 여러 종목 일괄 분석")

multi_input = st.text_area(
    "분석할 종목명을 입력하세요. 쉼표 또는 줄바꿈으로 여러 개 입력 가능",
    "삼성전자, 한화오션, 현대로템"
)

stocks = [
    s.strip()
    for s in multi_input.replace("\n", ",").split(",")
    if s.strip()
]

st.info(f"분석 대상: {', '.join(stocks)}")

if st.button("AI 일괄 분석 실행"):
    progress_bar = st.progress(0)
    status_text = st.empty()

    for idx, stock in enumerate(stocks):
        status_text.write(f"현재 분석 중: {stock} ({idx + 1}/{len(stocks)})")

        with st.spinner(f"{stock} 분석중..."):
            record = analyze_stock(stock)

        upsert_history(record, keep_old_meta=True)

        st.markdown("---")
        st.subheader(f"📌 {stock} 분석 결과")

        st.metric("종합점수", record["종합점수"])

        if "관심" in record["등급"]:
            st.success(f"AI 투자등급: {record['등급']}")
        elif "관망" in record["등급"]:
            st.warning(f"AI 투자등급: {record['등급']}")
        elif "과열주의" in record["등급"]:
            st.error(f"AI 투자등급: {record['등급']}")
        else:
            st.info("AI 투자등급: 판단불가")

        score_col1, score_col2, score_col3 = st.columns(3)
        score_col1.metric("상승 모멘텀", record["상승모멘텀점수"])
        score_col2.metric("뉴스 신뢰도", record["뉴스신뢰도점수"])
        score_col3.metric("단기 과열도", record["단기과열도점수"])

        st.markdown(f"""
**분류:** {record["시장"]} / {record["코드"]} / {record["업종"]} / {record["분류"]}
""")

        st.markdown(f"**상승 이유:** {record['상승이유']}")
        st.markdown(f"**리스크:** {record['리스크']}")

        st.subheader("📰 관련 뉴스")
        render_news_links(record["뉴스"])

        st.subheader("🤖 AI 분석")
        st.success(record["AI분석"])

        progress_bar.progress((idx + 1) / len(stocks))

    status_text.write("AI 분석이 완료되었습니다.")
    st.success("AI 분석이 완료되었고, 분석 기록이 저장되었습니다.")
    st.rerun()

st.markdown("---")
st.subheader("🕒 분석 기록 관리")

if len(st.session_state.history) > 0:
    filter_col1, filter_col2, filter_col3, filter_col4, filter_col5 = st.columns(5)

    with filter_col1:
        search_keyword = st.text_input("종목명 검색", placeholder="예: 삼성전자")

    with filter_col2:
        grade_filter = st.selectbox(
            "등급 필터",
            ["전체", "관심", "관망", "과열주의", "판단불가"]
        )

    with filter_col3:
        market_filter = st.selectbox(
            "시장 필터",
            ["전체", "국내", "해외", "미분류"]
        )

    with filter_col4:
        favorite_filter = st.selectbox(
            "즐겨찾기 필터",
            ["전체", "즐겨찾기만"]
        )

    with filter_col5:
        today_filter = st.selectbox(
            "날짜 필터",
            ["전체", "오늘 분석"]
        )

    hide_unknown = st.checkbox("판단불가 제외", value=False)

    history_df = pd.DataFrame(normalize_history(st.session_state.history))
    history_df["원본인덱스"] = history_df.index

    if search_keyword:
        history_df = history_df[
            history_df["종목"].astype(str).str.contains(search_keyword, case=False, na=False)
        ]

    if grade_filter != "전체":
        history_df = history_df[
            history_df["등급"].astype(str).str.contains(grade_filter, na=False)
        ]

    if market_filter != "전체":
        history_df = history_df[
            history_df["시장"].astype(str) == market_filter
        ]

    if favorite_filter == "즐겨찾기만":
        history_df = history_df[
            history_df["즐겨찾기"].apply(normalize_bool)
        ]

    if today_filter == "오늘 분석":
        today_str = date.today().strftime("%Y-%m-%d")
        history_df = history_df[
            history_df["시간"].astype(str).str.startswith(today_str)
        ]

    if hide_unknown:
        history_df = history_df[
            ~history_df["등급"].astype(str).str.contains("판단불가", na=False)
        ]

    if len(history_df) > 0:
        display_df = history_df.copy()
        display_df["즐겨찾기"] = display_df["즐겨찾기"].apply(lambda x: "⭐" if normalize_bool(x) else "")

        display_columns = [
            "시간", "즐겨찾기", "시장", "코드", "업종", "분류", "종목",
            "등급", "종합점수", "상승모멘텀점수", "뉴스신뢰도점수", "단기과열도점수",
            "상승이유", "리스크", "메모"
        ]

        st.dataframe(display_df[display_columns], use_container_width=True)

        filtered_csv = history_df.drop(columns=["원본인덱스"]).to_csv(
            index=False,
            encoding="utf-8-sig"
        ).encode("utf-8-sig")

        st.download_button(
            label="📥 현재 필터 결과 CSV 다운로드",
            data=filtered_csv,
            file_name=f"stock_ai_filtered_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

        st.markdown("### 기록별 관리")

        for _, row in history_df.iterrows():
            i = int(row["원본인덱스"])
            item = st.session_state.history[i]

            with st.expander(
                f"{'⭐ ' if normalize_bool(item.get('즐겨찾기', False)) else ''}"
                f"{item['종목']} / {item['등급']} / 점수 {item.get('종합점수', 0)} / {item['시간']}"
            ):
                score_col1, score_col2, score_col3, score_col4 = st.columns(4)
                score_col1.metric("종합점수", item.get("종합점수", 0))
                score_col2.metric("상승 모멘텀", item.get("상승모멘텀점수", 0))
                score_col3.metric("뉴스 신뢰도", item.get("뉴스신뢰도점수", 0))
                score_col4.metric("단기 과열도", item.get("단기과열도점수", 0))

                st.markdown(f"""
**시장:** {item["시장"]}  
**코드:** {item["코드"]}  
**업종:** {item["업종"]}  
**분류:** {item.get("분류", "직접입력")}  
**상승 이유:** {item.get("상승이유", "")}  
**리스크:** {item.get("리스크", "")}  
""")

                st.markdown("#### 📰 뉴스")
                render_news_links(item.get("뉴스", ""))

                st.markdown("#### 🤖 AI 분석")
                st.info(item.get("AI분석", ""))

                memo_value = st.text_area(
                    "메모",
                    value=item.get("메모", ""),
                    key=f"memo_{i}"
                )

                col_a, col_b, col_c, col_d = st.columns(4)

                with col_a:
                    if st.button("💾 메모 저장", key=f"save_memo_{i}"):
                        st.session_state.history[i]["메모"] = memo_value
                        save_history(st.session_state.history)
                        st.success("메모가 저장되었습니다.")
                        st.rerun()

                with col_b:
                    fav_label = "⭐ 즐겨찾기 해제" if normalize_bool(item.get("즐겨찾기", False)) else "⭐ 즐겨찾기"
                    if st.button(fav_label, key=f"favorite_{i}"):
                        st.session_state.history[i]["즐겨찾기"] = not normalize_bool(item.get("즐겨찾기", False))
                        save_history(st.session_state.history)
                        st.success("즐겨찾기 상태가 변경되었습니다.")
                        st.rerun()

                with col_c:
                    if st.button("🔄 재분석", key=f"reanalyze_{i}"):
                        with st.spinner(f"{item['종목']} 재분석중..."):
                            new_record = analyze_stock(item["종목"])

                        upsert_history(new_record, keep_old_meta=True)
                        st.success(f"{item['종목']} 재분석이 완료되었습니다.")
                        st.rerun()

                with col_d:
                    if st.button("🗑️ 삭제", key=f"delete_history_{i}"):
                        st.session_state.history.pop(i)
                        save_history(st.session_state.history)
                        st.success(f"{item['종목']} 분석 기록이 삭제되었습니다.")
                        st.rerun()
    else:
        st.info("검색 또는 필터 조건에 맞는 분석 기록이 없습니다.")

else:
    st.info("아직 분석 기록이 없습니다.")