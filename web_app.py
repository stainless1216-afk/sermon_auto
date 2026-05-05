import streamlit as st
from google import genai
import json
import os
import io
from PIL import Image
from datetime import datetime

# ---------------------------------------------------------
# 1. 기본 설정 및 데이터 로드 기능
# ---------------------------------------------------------
st.set_page_config(page_title="AI LEADER 자동화 시스템", page_icon="🚀", layout="wide")

PROMPTS_FILE = "web_prompts.json"

def load_prompts():
    default_prompts = {
        '나눔 질문': "다음 설교문을 바탕으로 [질문 작성 3단계 패턴]을 지켜 가족 나눔 질문 12개를 만들어줘.\n1단계(4개): 삶의 성찰과 경험 나눔\n2단계(4개): 말씀의 적용과 원리 이해\n3단계(4개): 구체적 실천 결단 및 기도\n\n작성 조건: 따뜻하고 격려하는 어조.",
        '교사 지침서': "다음 설교문을 바탕으로 아래 양식에 맞춰 교사 지침서를 작성해줘.\n지침: 따뜻하고 확신에 찬 어조, 어린이 눈높이 비유, 정통 신학 기반.\n\n출력 양식:\n1. 말씀 핵심포인트\n2. 신앙적 질문\n3. 목회 팁",
        '공과 내용': "다음 설교문을 분석하여 어린이 성경 공부를 위한 '공과 내용'을 작성해줘.\n구조: 공과 제목, 성경 구절, 학습 목표, READ(이야기 요약), EXPLAIN(질문), CHANGE(적용), PRAY(기도).",
        '이미지 프롬프트 설계': "다음 설교문과 앞서 작성된 [공과 내용]을 바탕으로 AI 이미지 생성기에 입력할 최적화된 '영문 프롬프트'들을 작성해줘.\n\n1. [미션 2: 유튜브 썸네일] (16:9)\n2. [미션 4: 공과 활동지 (A4)]\n3. [미션 5: 어린이 설교 PPT 5컷] (16:9)"
    }
    if os.path.exists(PROMPTS_FILE):
        try:
            with open(PROMPTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: pass
    return default_prompts

def save_prompts(prompts_dict):
    with open(PROMPTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(prompts_dict, f, ensure_ascii=False, indent=4)

# 세션 상태 초기화 (웹은 새로고침될 때 데이터가 날아가는 걸 방지해야 함)
if 'prompts' not in st.session_state:
    st.session_state.prompts = load_prompts()
if 'generated_text' not in st.session_state:
    st.session_state.generated_text = ""
if 'gonggwa_cache' not in st.session_state:
    st.session_state.gonggwa_cache = ""

# ---------------------------------------------------------
# 2. 사이드바 (설정 및 탭 추가 영역)
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 시스템 설정")
    # API 키를 코드에 박지 않고, 웹 화면에서 안전하게 입력받도록 개선!
    api_key = st.text_input("🔑 구글 Gemini API 키 입력", type="password", help="발급받은 API 키를 여기에 입력하세요.")
    
    st.divider()
    st.subheader("➕ 새 프롬프트 추가")
    new_tab_name = st.text_input("새로 만들 자료의 이름 (예: 묵상노트)")
    if st.button("탭 추가하기", use_container_width=True):
        if new_tab_name and new_tab_name not in st.session_state.prompts:
            st.session_state.prompts[new_tab_name] = f"다음 설교문을 바탕으로 '{new_tab_name}' 자료를 작성해줘.\n\n[작성 지침]\n1. 목적: \n2. 어조: \n3. 양식: "
            save_prompts(st.session_state.prompts)
            st.success(f"'{new_tab_name}' 추가 완료!")
            st.rerun() # 화면 새로고침

    st.divider()
    if st.button("💾 모든 프롬프트 영구 저장", type="primary", use_container_width=True):
        save_prompts(st.session_state.prompts)
        st.toast("프롬프트가 안전하게 저장되었습니다!")

# ---------------------------------------------------------
# 3. 메인 웹 화면
# ---------------------------------------------------------
st.title("🚀 AI LEADER 교육 자료 통합 자동화 시스템")
st.markdown("설교문 하나로 공과, 지침서, 나눔 질문, 그리고 이미지까지 한 번에 생성하세요.")

# 1. 설교문 입력
st.header("📝 1. 설교문 입력")
sermon_text = st.text_area("이곳에 이번 주 설교문을 붙여넣어 주세요.", height=200)

# 2. 프롬프트 탭 구성
st.header("🛠️ 2. 프롬프트 수정")
tab_names = list(st.session_state.prompts.keys())
tabs = st.tabs(tab_names)

for i, tab_name in enumerate(tab_names):
    with tabs[i]:
        # 사용자가 수정한 프롬프트를 실시간으로 세션에 반영
        updated_prompt = st.text_area(f"[{tab_name}] 프롬프트 내용", value=st.session_state.prompts[tab_name], height=200, key=f"prompt_{tab_name}")
        st.session_state.prompts[tab_name] = updated_prompt

st.divider()

# ---------------------------------------------------------
# 4. 생성 로직 및 결과 출력
# ---------------------------------------------------------
col1, col2 = st.columns([1, 1])

with col1:
    st.header("⚙️ 3. 텍스트 자동 생성")
    if st.button("▶ 모든 텍스트 자료 생성 시작", type="primary", use_container_width=True):
        if not api_key:
            st.error("앗! 좌측 사이드바에 API 키를 먼저 입력해 주세요.")
        elif not sermon_text:
            st.warning("설교문을 입력해 주세요.")
        else:
            try:
                client = genai.Client(api_key=api_key)
                all_results = ""
                st.session_state.gonggwa_cache = ""
                
                # 프로그레스 바와 상태 메시지
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                total_tabs = len(tab_names)
                
                for idx, tab_name in enumerate(tab_names):
                    status_text.text(f"[{tab_name}] 자료를 생성하고 있습니다... ({idx+1}/{total_tabs})")
                    base_prompt = st.session_state.prompts[tab_name]
                    
                    if '이미지' in tab_name and st.session_state.gonggwa_cache:
                        full_prompt = base_prompt + f"\n\n설교문: {sermon_text}\n\n[공과 내용]:\n{st.session_state.gonggwa_cache}"
                    else:
                        full_prompt = base_prompt + f"\n\n설교문: {sermon_text}"
                    
                    response = client.models.generate_content(model='gemini-2.5-pro', contents=full_prompt)
                    
                    if '공과' in tab_name:
                        st.session_state.gonggwa_cache = response.text
                        
                    all_results += f"=== [{tab_name}] ===\n{response.text}\n\n{'='*60}\n\n"
                    progress_bar.progress((idx + 1) / total_tabs)
                
                st.session_state.generated_text = all_results
                status_text.success("✨ 모든 텍스트 자료 생성이 완료되었습니다!")
            except Exception as e:
                st.error(f"오류가 발생했습니다: {e}")

# 결과 출력 창 및 TXT 다운로드 버튼
if st.session_state.generated_text:
    st.text_area("결과 확인", value=st.session_state.generated_text, height=400)
    
    today_str = datetime.now().strftime("%Y%m%d")
    st.download_button(
        label="📄 전체 결과를 TXT 파일로 다운로드",
        data=st.session_state.generated_text,
        file_name=f"교육자료_생성결과_{today_str}.txt",
        mime="text/plain",
        use_container_width=True
    )

st.divider()

# ---------------------------------------------------------
# 5. 이미지 생성기 (웹 화면 바로 출력)
# ---------------------------------------------------------
st.header("🖼️ 4. 실제 이미지 생성 (Imagen 4.0)")
st.info("💡 위 결과 창에서 생성된 '영문 프롬프트' 중 하나를 복사해서 아래에 붙여넣으세요.")

img_prompt = st.text_area("영문 프롬프트 입력창")
img_ratio = st.selectbox("이미지 비율 선택", ["16:9", "1:1", "3:4", "4:3", "9:16"])

if st.button("🎨 이 프롬프트로 웹에서 이미지 생성하기", type="primary"):
    if not api_key:
        st.error("사이드바에 API 키를 입력해 주세요.")
    elif not img_prompt:
        st.warning("영문 프롬프트를 입력해 주세요.")
    else:
        with st.spinner("AI가 이미지를 화폭에 그리고 있습니다... (약 10초 소요)"):
            try:
                client = genai.Client(api_key=api_key)
                result = client.models.generate_images(
                    model='imagen-4.0-generate-001',
                    prompt=img_prompt,
                    config=dict(
                        number_of_images=1,
                        aspect_ratio=img_ratio,
                        output_mime_type="image/jpeg"
                    )
                )
                image_bytes = result.generated_images[0].image.image_bytes
                image = Image.open(io.BytesIO(image_bytes))
                
                # 웹 화면에 이미지 짠! 하고 보여주기
                st.image(image, caption="생성된 AI 이미지", use_container_width=True)
                
                # 이미지 다운로드 버튼
                buf = io.BytesIO()
                image.save(buf, format="JPEG")
                byte_im = buf.getvalue()
                st.download_button(
                    label="📥 이 이미지 내 컴퓨터로 다운로드",
                    data=byte_im,
                    file_name="sermon_image.jpeg",
                    mime="image/jpeg",
                    use_container_width=True
                )
                st.success("이미지 생성 성공!")
            except Exception as e:
                st.error(f"이미지 생성 중 오류 발생: {e}")