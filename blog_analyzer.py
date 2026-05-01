# -*- coding: utf-8 -*-
import streamlit as st
import requests
from bs4 import BeautifulSoup
from google import genai
import time
import re

st.set_page_config(page_title="블로그 투자 인사이트 분석기", layout="wide")

def get_all_post_urls(blog_id, max_pages, status_text):
    urls = []
    for page in range(1, max_pages + 1):
        list_url = f"https://blog.naver.com/PostTitleListAsync.naver?blogId={blog_id}&currentPage={page}&countPerPage=30"
        try:
            response = requests.get(list_url)
            response.raise_for_status()
            log_nos = re.findall(r'logNo=(\d+)', response.text)
            
            if not log_nos: break
                
            for log_no in set(log_nos):
                post_url = f"https://blog.naver.com/{blog_id}/{log_no}"
                if post_url not in urls: urls.append(post_url)
            
            status_text.text(f"🔍 {page}페이지 탐색 완료... (현재까지 총 {len(urls)}개 글 URL 수집됨)")
            time.sleep(0.5)
            
        except Exception as e:
            st.error(f"URL 수집 중 오류 발생: {e}")
            break
    return urls

def get_blog_text(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        iframe = soup.find('iframe', id='mainFrame')
        if not iframe: return ""
        
        real_url = "https://blog.naver.com" + iframe['src']
        real_response = requests.get(real_url)
        real_response.raise_for_status()
        real_soup = BeautifulSoup(real_response.text, 'html.parser')
        
        content = real_soup.find('div', class_='se-main-container')
        if content: return content.get_text(strip=True)
        return ""
    except:
        return ""

st.title("📈 네이버 블로그 투자 인사이트 AI 분석기")
st.markdown("특정 블로거의 글을 대량으로 수집하여, **전문 애널리스트 관점에서 팩트 위주로 요약**합니다.")

with st.sidebar:
    st.header("⚙️ 설정")
    # [수정됨] API 키 입력란을 완전히 삭제했습니다!
    blog_id_input = st.text_input("분석할 네이버 블로그 ID", value="doctordk")
    max_pages_input = st.slider("수집할 페이지 수 (1페이지당 약 30글)", min_value=1, max_value=10, value=2)
    st.info("⚠️ 페이지 수를 너무 높이면 무료 API 한도 초과(429 에러)가 발생할 수 있습니다.")
    
    start_button = st.button("🚀 분석 시작", use_container_width=True)

if start_button:
    # [수정됨] 스트림릿 비밀 금고에서 API 키를 몰래 꺼내옵니다.
    try:
        api_key_hidden = st.secrets["GOOGLE_API_KEY"]
    except KeyError:
        st.error("서버에 API 키가 설정되지 않았습니다. 관리자(개발자)에게 문의하세요.")
        st.stop() # 키가 없으면 프로그램 중단

    if not blog_id_input:
        st.warning("👈 네이버 블로그 ID를 입력해 주세요.")
    else:
        status_text = st.empty()
        progress_bar = st.progress(0)
        
        target_urls = get_all_post_urls(blog_id_input, max_pages_input, status_text)
        
        if not target_urls:
            st.error("수집된 게시글이 없습니다. 블로그 ID를 확인해 주세요.")
        else:
            st.success(f"총 {len(target_urls)}개의 게시글 URL 수집 완료! 본문을 추출합니다...")
            
            collected_texts = ""
            for i, url in enumerate(target_urls):
                progress_bar.progress((i + 1) / len(target_urls))
                status_text.text(f"📝 텍스트 추출 중... ({i+1}/{len(target_urls)})")
                
                text = get_blog_text(url)
                if text: collected_texts += f"\n--- [새로운 글] ---\n{text}\n"
                time.sleep(0.3)
            
            status_text.text("🧠 AI가 애널리스트 모드로 분석을 진행 중입니다... (1~2분 소요)")
            
            # 여기서 숨겨둔 키(api_key_hidden)를 사용하여 AI를 호출합니다.
            client = genai.Client(api_key=api_key_hidden)
            
            analyst_prompt = f"""
            당신은 여의도 탑티어 주식 애널리스트입니다. 제공된 텍스트는 특정 투자 블로거의 게시글 모음입니다.
            감정적이고 부차적인 내용은 배제하고, 철저히 '팩트'와 '투자 인사이트' 위주로 간결하게 분석하세요.

            특히, 수많은 언급 종목 중 투자자가 '선택과 집중'을 할 수 있도록, 글의 문맥과 뉘앙스를 분석하여 **우선순위 랭킹**을 매겨주세요.
            순위 산정 기준은 1) 언급 빈도(여러 글에서 반복되는가), 2) 확신도(강한 어조로 추천하는가), 3) 분석의 구체성입니다.

            [보고서 양식]
            ### 1. 🏆 Top 5 최우선 관심 종목 (우선순위 랭킹)
            (아래 기준에 따라 마크다운 표(Table) 형식으로 깔끔하게 작성하세요. 5개가 안 되면 있는 만큼만 작성합니다.)
            | 순위 | 종목 및 섹터명 | 추천 확신도(상/중/하) | 반복 언급 | 핵심 추천 사유 (1줄 요약) |
            |---|---|---|---|---|
            | 1 | ... | ... | ... | ... |

            ### 2. 핵심 투자 철학 (개조식, 3줄 이내 요약)
            ### 3. 거시 경제/시장 전망 (강세/약세 포지션 및 핵심 근거 간략히)
            ### 4. 분석가 코멘트 (투자 관점에서 주목할 만한 블로거의 특이점이나 패턴 1~2가지)

            [블로그 글 내용]
            {collected_texts}
            """
            
            max_retries = 3
            retry_delay = 5
            
            for attempt in range(max_retries):
                try:
                    response = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=analyst_prompt,
                    )
                    
                    status_text.empty()
                    progress_bar.empty()
                    
                    st.subheader("📊 AI 애널리스트 분석 리포트")
                    st.markdown(response.text)
                    break 
                    
                except Exception as e:
                    error_msg = str(e)
                    if "503" in error_msg or "UNAVAILABLE" in error_msg:
                        if attempt < max_retries - 1:
                            status_text.warning(f"⚠️ 구글 서버 접속 지연 중... {retry_delay}초 후 자동으로 재시도합니다. (시도 횟수: {attempt + 1}/{max_retries})")
                            time.sleep(retry_delay)
                        else:
                            st.error("❌ 구글 서버 지연으로 분석을 완료하지 못했습니다. 잠시 후 [분석 시작] 버튼을 다시 눌러주세요.")
                    else:
                        st.error(f"❌ AI 분석 중 알 수 없는 오류가 발생했습니다: {e}")
                        break