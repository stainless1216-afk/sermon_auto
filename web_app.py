import streamlit as st
from google import genai
import io
from PIL import Image
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# 1. 연결 설정 (아까 만든 스프레드시트 URL을 따옴표 안에 넣어주세요!)
SHEET_URL = "여기에_스프레드시트_전체_주소를_붙여넣으세요"

st.set_page_config(page_title="AI LEADER 자동화 시스템", page_icon="🚀", layout="wide")

# 구글 시트 연결 함수
@st.cache_resource
def init_gsheets():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_info = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
    client = gspread.authorize(creds)
    sheet = client.open_by_url(SHEET_URL).sheet1
    return sheet

def load_prompts():
    default_prompts = {
        '나눔 질문': "다음 설교문을 바탕으로 [질문 작성 3단계 패턴]을 지켜 가족 나눔 질문 12개를 만들어줘.\n\n작성 조건: 따뜻하고 격려하는 어조.",
        '교사 지침서': "다음 설교문을 바탕으로 아래 양식에 맞춰 교사 지침서를 작성해줘.\n지침: 따뜻하고 확신에 찬 어조, 어린이 눈높이 비유, 정통 신학 기반.",
        '공과 내용': "다음 설교문을 분석하여 어린이 성경 공부를 위한 '공과 내용'을 작성해줘.",
        '이미지 프롬프트 설계': "다음 설교문과 앞서 작성된 [공과 내용]을 바탕으로 AI 이미지 생성기에 입력할 '영문 프롬프트'를 작성해줘."
    }
    try:
        sheet = init_gsheets()
        records = sheet.get_all_records()
        if not records:
            return default_prompts
        loaded = {row['TabName']: row['Prompt'] for row in records}
        return loaded
    except Exception as e:
        return default_prompts

def save_prompts(prompts_dict):
    try:
        sheet = init_gsheets()
        sheet.clear() 
        sheet.append_row(['TabName', 'Prompt']) 
        rows = [[k, str(v)] for k, v in prompts_dict.items()]
        sheet.append_rows(rows)
        return True
    except Exception as e:
        st.error(f"저장 실패: {e}")
        return False

# 세션 초기화
if 'prompts' not in st.session_state:
    st.session_state.prompts = load_prompts()
if 'generated_text' not in st.session_state:
    st.session_state.generated_text = ""
if 'gonggwa_cache' not in st.session_state:
    st.session_state.gonggwa_cache = ""

# 사이드바
with st.sidebar:
    st.header("⚙️ 시스템 설정")
    api_key = st.text_input("🔑 구글 Gemini API 키 입력", type="password")
    
    st.divider()
    st.subheader("➕ 새 프롬프트 추가")
    new_tab_name = st.text_input("새로 만들 자료의 이름")
    if st.button("탭 추가하기", use_container_width=True):
        if new_tab_name and new_tab_name not in st.session_state.prompts:
            st.session_state.prompts[new_tab_name] = f"'{new_tab_name}' 자료를 작성해줘."
            save_prompts(st.session_state.prompts)
            st.success(f"'{new_tab_name}' 추가 및 구글 시트 저장 완료!")
            st.rerun()

    st.divider()
    if st.button("💾 모든 프롬프트 영구 저장 (DB)", type="primary", use_container_width=True):
        if save_prompts(st.session_state.prompts):
            st.toast("구글 스프레드시트에 영구 저장되었습니다!")

# 메인 화면
st.title("🚀 AI LEADER 교육 자료 통합 자동화 시스템")
st.markdown("수정된 프롬프트는 구글 스프레드시트(DB)에 영구 보존됩니다.")

sermon_text = st.text_area("📝 1. 이번 주 설교문 입력", height=200)

st.header("🛠️ 2. 프롬프트 수정")
tab_names = list(st.session_state.prompts.keys())
tabs = st.tabs(tab_names)

for i, tab_name in enumerate(tab_names):
    with tabs[i]:
        updated_prompt = st.text_area(f"[{tab_name}] 프롬프트", value=st.session_state.prompts[tab_name], height=200, key=f"prompt_{tab_name}")
        st.session_state.prompts[tab_name] = updated_prompt

st.divider()
col1, col2 = st.columns([1, 1])

with col1:
    st.header("⚙️ 3. 텍스트 자동 생성")
    if st.button("▶ 생성 시작", type="primary", use_container_width=True):
        if not api_key: st.error("API 키를 입력하세요.")
        elif not sermon_text: st.warning("설교문을 입력하세요.")
        else:
            client = genai.Client(api_key=api_key)
            all_results = ""
            st.session_state.gonggwa_cache = ""
            progress_bar = st.progress(0)
            
            for idx, tab_name in enumerate(tab_names):
                base_prompt = st.session_state.prompts[tab_name]
                full_prompt = base_prompt + f"\n\n설교문: {sermon_text}"
                if '이미지' in tab_name and st.session_state.gonggwa_cache:
                    full_prompt += f"\n\n[공과 내용]:\n{st.session_state.gonggwa_cache}"
                
                res = client.models.generate_content(model='gemini-2.5-pro', contents=full_prompt)
                if '공과' in tab_name: st.session_state.gonggwa_cache = res.text
                all_results += f"=== [{tab_name}] ===\n{res.text}\n\n{'='*60}\n\n"
                progress_bar.progress((idx + 1) / len(tab_names))
            
            st.session_state.generated_text = all_results
            st.success("✨ 완료!")

if st.session_state.generated_text:
    st.text_area("결과 확인", value=st.session_state.generated_text, height=400)
    st.download_button("📄 TXT로 다운로드", data=st.session_state.generated_text, file_name=f"결과_{datetime.now().strftime('%Y%m%d')}.txt", mime="text/plain")

st.divider()
st.header("🖼️ 4. 실제 이미지 생성 (Imagen 4.0)")
img_prompt = st.text_area("영문 프롬프트 입력창")
img_ratio = st.selectbox("비율", ["16:9", "1:1", "3:4", "4:3", "9:16"])

if st.button("🎨 이미지 생성하기", type="primary"):
    if api_key and img_prompt:
        with st.spinner("이미지 생성 중..."):
            client = genai.Client(api_key=api_key)
            res = client.models.generate_images(model='imagen-4.0-generate-001', prompt=img_prompt, config=dict(number_of_images=1, aspect_ratio=img_ratio, output_mime_type="image/jpeg"))
            image = Image.open(io.BytesIO(res.generated_images[0].image.image_bytes))
            st.image(image)
            buf = io.BytesIO()
            image.save(buf, format="JPEG")
            st.download_button("📥 다운로드", data=buf.getvalue(), file_name="image.jpeg", mime="image/jpeg")