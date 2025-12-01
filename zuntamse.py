import streamlit as st
from PIL import Image
import numpy as np
import easyocr
import time
import re
import random
import json
import os
from datetime import datetime

# ==========================================
# 💾 0. [Database] 로컬 DB (자동 저장)
# ==========================================
DB_FILE = "gem_database.json"

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        return {}

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_user_data(username, db):
    if username not in db:
        db[username] = {
            "level": 1,
            "xp": 0,
            "tickets": 0,
            "streak": 1,
            "last_login": datetime.now().strftime("%Y-%m-%d"),
            "inventory": [],
            "logs": []
        }
        save_db(db)
    return db[username]

# ==========================================
# ⚙️ 1. [Backend] AI 엔진
# ==========================================

@st.cache_resource
def load_ocr_model():
    with st.spinner("AI 엔진 가동 중..."):
        reader = easyocr.Reader(['ko', 'en'], gpu=False)
    return reader

def real_ai_ocr_process(image):
    reader = load_ocr_model()
    image_np = np.array(image)
    result_list = reader.readtext(image_np, detail=0)
    full_text = "\n".join(result_list)
    return full_text

def analyze_text_to_data(text):
    data = {'subject': '자율 학습', 'time_min': 0, 'volume_bonus': False}
    t_match = re.findall(r'(\d+)\s*(시간|h|H)', text)
    m_match = re.findall(r'(\d+)\s*(분|m|M)', text)
    for t in t_match: data['time_min'] += int(t[0]) * 60
    for m in m_match: data['time_min'] += int(m[0])

    if '수학' in text: data['subject'] = '수학 📐'
    elif '영어' in text or 'English' in text: data['subject'] = '영어 🇺🇸'
    elif '과학' in text or '물리' in text: data['subject'] = '과학 🧬'
    elif '코딩' in text or 'Python' in text: data['subject'] = '코딩 💻'
    elif '국어' in text: data['subject'] = '국어 📚'
    
    if re.search(r'[pP]\.|쪽|개|지문|회독|문제', text):
        data['volume_bonus'] = True
    return data

def calculate_simple_xp(data):
    if data['time_min'] == 0: base_score = 30 
    else: base_score = int(data['time_min'] * 1.5)
    bonus = 50 if data['volume_bonus'] else 0
    return base_score + bonus

def get_avatar(level):
    if level < 5: return "🥚"
    elif level < 10: return "🐣"
    elif level < 20: return "🐥"
    else: return "👑"

# ==========================================
# 🖥️ 2. [Frontend] UI
# ==========================================

st.set_page_config(page_title="GEM Service", page_icon="💎", layout="centered")

# --- CSS: 애니메이션 및 스타일 ---
st.markdown("""
<style>
    .login-title { font-size: 40px; font-weight: bold; color: #4CAF50; text-align: center; }
    .xp-gain { font-size: 28px; font-weight: bold; color: #4CAF50; animation: bounce 0.5s; }
    .avatar { font-size: 50px; text-align: center; }
    
    /* 국소적 팡파르 박스 */
    .levelup-box {
        border: 2px solid #FFD700; background-color: #FFFFE0; padding: 15px;
        border-radius: 15px; text-align: center; margin-top: 10px;
        animation: pop 0.5s ease-out;
    }
    .levelup-title { font-size: 30px; font-weight: 900; color: #FFD700; text-shadow: 1px 1px 2px black; }
    
    @keyframes bounce { 0% { transform: scale(1); } 50% { transform: scale(1.2); } 100% { transform: scale(1); } }
    @keyframes pop { 0% { transform: scale(0.5); opacity: 0; } 100% { transform: scale(1); opacity: 1; } }
</style>
""", unsafe_allow_html=True)

db = load_db()

# 세션 관리
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'username' not in st.session_state: st.session_state['username'] = ""
if 'last_processed' not in st.session_state: st.session_state['last_processed'] = None

# ----------------------------------------------------------------
# [Part 1] 로그인 화면
# ----------------------------------------------------------------
if not st.session_state['logged_in']:
    st.markdown("<p class='login-title'>💎 GEM Login</p>", unsafe_allow_html=True)
    with st.container():
        # [복구됨] 이시우 프리셋
        user_input = st.text_input("아이디 (Student ID)", value="이시우")
        if st.button("로그인 / 시작하기", use_container_width=True):
            if user_input:
                st.session_state['logged_in'] = True
                st.session_state['username'] = user_input
                st.rerun()
    st.stop()

# ----------------------------------------------------------------
# [Part 2] 메인 앱
# ----------------------------------------------------------------
user_id = st.session_state['username']
user_data = get_user_data(user_id, db) 

# 상단 정보
c1, c2, c3 = st.columns([1, 2, 1])
with c1: st.markdown(f"<div class='avatar'>{get_avatar(user_data['level'])}</div>", unsafe_allow_html=True)
with c2: 
    st.markdown(f"### {user_id}님")
    st.caption(f"Lv.{user_data['level']} | {user_data['xp']} XP")
with c3:
    st.metric("연속 학습", f"{user_data['streak']}일🔥")

tab1, tab2 = st.tabs(["🏠 학습 인증", "🎁 선물함"])

# [탭 1] 학습 인증
with tab1:
    st.write("📸 **학습 플래너 업로드 (자동 분석 & 저장)**")
    uploaded_file = st.file_uploader(" ", type=['png', 'jpg', 'jpeg'], label_visibility="collapsed")

    # --- [복구됨] 레벨 바 위치 (항상 보이게) ---
    LEVEL_THRESHOLD = 100
    st.write(f"**Level Progress (Lv.{user_data['level']})**")
    
    # 애니메이션을 위해 빈 컨테이너 준비
    bar_container = st.empty()
    
    # 현재 상태 표시 (기본값)
    current_p = (user_data['xp'] % LEVEL_THRESHOLD) / LEVEL_THRESHOLD
    bar_container.progress(current_p)

    if uploaded_file is not None:
        current_file_id = uploaded_file.name + str(uploaded_file.size)
        
        if st.session_state['last_processed'] != current_file_id:
            
            # 1. OCR UI
            image = Image.open(uploaded_file)
            st.image(image, width=300)
            
            prog = st.progress(0)
            status = st.empty()
            
            status.write("AI 분석 중...")
            prog.progress(40)
            text = real_ai_ocr_process(image)
            
            status.write("점수 계산 중...")
            prog.progress(80)
            data = analyze_text_to_data(text)
            
            prog.progress(100)
            time.sleep(0.2)
            prog.empty()
            status.empty()
            
            # 2. 데이터 계산
            gained_xp = calculate_simple_xp(data)
            
            # [중요] 애니메이션을 위한 이전 상태 저장
            prev_xp_total = user_data['xp']
            prev_level = user_data['level']
            prev_p = (prev_xp_total % LEVEL_THRESHOLD) / LEVEL_THRESHOLD
            
            # DB 업데이트
            user_data['xp'] += gained_xp
            user_data['level'] = 1 + (user_data['xp'] // LEVEL_THRESHOLD)
            
            # 로그 저장
            user_data['logs'].append({
                "date": datetime.now().strftime("%m-%d %H:%M"),
                "subject": data['subject'],
                "xp": gained_xp
            })
            save_db(db)
            
            st.divider()
            st.markdown(f"<p class='xp-gain'>+{gained_xp} XP 획득!</p>", unsafe_allow_html=True)
            
            # 3. [복구됨] 레벨 바 애니메이션 로직
            curr_level = user_data['level']
            
            if curr_level > prev_level:
                # [Scenario A] 레벨업 발생!
                
                # 1단계: 기존 게이지가 끝까지(100%) 차오름
                for i in range(int(prev_p * 100), 101, 5):
                    bar_container.progress(i / 100)
                    time.sleep(0.01)
                
                # 2단계: 국소적 팡파르 효과 (Balloons 아님!)
                st.snow() # 은은한 눈송이
                st.markdown(f"""
                <div class='levelup-box'>
                    <div class='levelup-title'>🎉 LEVEL UP!</div>
                    <p>Lv.{prev_level} ➔ Lv.{curr_level}로 성장했습니다!</p>
                </div>
                """, unsafe_allow_html=True)
                
                # 10레벨 단위 보상 체크
                if curr_level % 10 == 0:
                    user_data['tickets'] += 1
                    save_db(db)
                    st.info("🎁 특별 보상: 추첨권 1장 획득!")
                
                time.sleep(1) # 감상 시간
                
                # 3단계: 0%에서 다시 새로운 %까지 차오름
                new_target_p = (user_data['xp'] % LEVEL_THRESHOLD) / LEVEL_THRESHOLD
                for i in range(0, int(new_target_p * 100) + 1, 2):
                    bar_container.progress(i / 100)
                    time.sleep(0.01)
                    
            else:
                # [Scenario B] 일반 XP 획득
                new_target_p = (user_data['xp'] % LEVEL_THRESHOLD) / LEVEL_THRESHOLD
                # 부드럽게 증가
                start_p_int = int(prev_p * 100)
                end_p_int = int(new_target_p * 100)
                
                if end_p_int > start_p_int:
                    for i in range(start_p_int, end_p_int + 1, 2):
                        bar_container.progress(i / 100)
                        time.sleep(0.01)
                else:
                    bar_container.progress(new_target_p)
            
            st.session_state['last_processed'] = current_file_id
            
        else:
            st.success("✅ 저장 완료")

    # 히스토리
    st.divider()
    st.subheader("📜 학습 기록")
    if user_data['logs']:
        for log in reversed(user_data['logs']):
            st.markdown(f"- **{log['subject']}** (+{log['xp']} XP) <span style='color:grey; font-size:12px'>{log['date']}</span>", unsafe_allow_html=True)

# [탭 2] 선물함
with tab2:
    st.subheader("🎁 아이템 샵")
    st.metric("나의 티켓", f"{user_data['tickets']}장")
    
    if st.button("🎟️ 티켓 사용하기"):
        if user_data['tickets'] > 0:
            user_data['tickets'] -= 1
            item = random.choice(["아메리카노", "편의점상품권", "치킨쿠폰", "XP부스터"])
            user_data['inventory'].append({"item": item, "date": datetime.now().strftime("%m-%d")})
            
            save_db(db)
            st.toast(f"{item} 당첨!", icon="🎉")
            st.snow()
            st.rerun()
        else:
            st.error("티켓이 부족합니다.")
            
    st.markdown("**📦 보관함**")
    for inv in reversed(user_data['inventory']):
        st.write(f"- {inv['item']} ({inv['date']})")