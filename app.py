import json
import random
import streamlit as st
from supabase import create_client

st.set_page_config(page_title="스마트 오답 노트", page_icon="📝")
FIELDS = ("과목", "문제", "오답", "정답", "해설")
COLUMNS = dict(zip(FIELDS, ("subject", "question", "wrong_answer", "correct_answer", "explanation")))

def valid_notes(value):
    return isinstance(value, list) and len(value) <= 500 and all(isinstance(n, dict) and all(isinstance(n.get(f), str) and 0 < len(n[f].strip()) <= 10000 for f in FIELDS) for n in value)

try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
except Exception:
    st.error("관리자 설정이 필요합니다. Streamlit Secrets에 SUPABASE_URL과 SUPABASE_KEY를 입력해 주세요.")
    st.stop()
# 절대 cache_resource로 공유하지 않습니다. 사용자 세션마다 별도 인증 클라이언트입니다.
if "db" not in st.session_state:
    st.session_state.db = create_client(url, key)
db = st.session_state.db
st.title("📝 스마트 오답 노트")

if not st.session_state.get("uid"):
    login_tab, signup_tab = st.tabs(["로그인", "회원가입"])
    with login_tab:
        with st.form("login"):
            email = st.text_input("이메일")
            password = st.text_input("비밀번호", type="password")
            submitted = st.form_submit_button("로그인")
        if submitted:
            try:
                result = db.auth.sign_in_with_password({"email": email.strip(), "password": password})
                if result.user and result.session:
                    st.session_state.uid = result.user.id
                    st.session_state.email = result.user.email
                    st.rerun()
                else:
                    st.error("이메일 인증 후 다시 로그인해 주세요.")
            except Exception:
                st.error("로그인하지 못했습니다. 이메일·비밀번호, 이메일 인증 여부 및 인터넷 연결을 확인해 주세요.")
    with signup_tab:
        with st.form("signup"):
            name = st.text_input("닉네임 (실명 대신 별명을 사용하세요)", max_chars=40)
            new_email = st.text_input("가입 이메일")
            new_password = st.text_input("가입 비밀번호 (12자 이상)", type="password")
            confirm = st.text_input("비밀번호 확인", type="password")
            consent = st.checkbox("이메일·닉네임·오답이 외부 클라우드에 저장됨을 확인했습니다.")
            signup = st.form_submit_button("회원가입")
        if signup:
            if not name.strip() or not new_email.strip() or len(new_password) < 12 or new_password != confirm or not consent:
                st.error("입력 항목, 비밀번호 길이·일치 여부, 저장 안내 확인을 점검해 주세요.")
            else:
                try:
                    db.auth.sign_up({"email": new_email.strip(), "password": new_password, "options": {"data": {"display_name": name.strip()}}})
                    st.success("가입 요청을 보냈습니다. 이메일 인증을 켜둔 경우 메일의 인증 링크를 누른 뒤 로그인해 주세요. 메일이 없으면 스팸함을 확인하세요.")
                except Exception:
                    st.error("가입 요청에 실패했습니다. 이메일 형식, 비밀번호 정책 또는 잠시 후 재시도를 확인하세요.")
    st.caption("비밀번호는 앱 데이터베이스에 직접 저장하지 않고 Supabase Auth가 처리합니다.")
    st.stop()

uid = st.session_state.uid
st.sidebar.caption(st.session_state.get("email", ""))
if st.sidebar.button("로그아웃"):
    try:
        db.auth.sign_out()
    except Exception:
        pass
    st.session_state.clear()
    st.rerun()

def db_action(action):
    try:
        return action()
    except Exception:
        st.error("저장소 요청이 실패했습니다. 네트워크·DB 설정을 확인하거나 다시 로그인해 주세요. 저장 완료가 표시되지 않았다면 저장되지 않았을 수 있습니다.")
        st.stop()

def add_note(values):
    payload = {COLUMNS[f]: values[f].strip() for f in FIELDS}
    payload["user_id"] = uid
    db_action(lambda: db.table("notes").insert(payload).execute())

def update_note(note_id, values):
    payload = {COLUMNS[f]: values[f].strip() for f in FIELDS}
    db_action(lambda: db.table("notes").update(payload).eq("id", note_id).eq("user_id", uid).execute())

def delete_note(note_id):
    db_action(lambda: db.table("notes").delete().eq("id", note_id).eq("user_id", uid).execute())

rows = []
start = 0
while True:
    batch = db_action(lambda: db.table("notes").select("*").eq("user_id", uid).order("created_at").order("id").range(start, start + 499).execute()).data
    rows.extend(batch)
    if len(batch) < 500:
        break
    start += 500
notes = [{"id": r["id"], **{f: r[c] for f, c in COLUMNS.items()}} for r in rows]
st.caption("로그인 계정별 클라우드 저장 · 앱을 껐다 켜도 저장된 오답을 다시 불러옵니다.")
page = st.sidebar.radio("메뉴", ["오답 등록", "퀴즈 풀기", "조회 · 수정 · 삭제", "백업 · 가져오기"])

if page == "오답 등록":
    with st.form("register", clear_on_submit=True):
        values = {f: st.text_area(f) if f in ("문제", "해설") else st.text_input(f) for f in FIELDS}
        submitted = st.form_submit_button("저장하기")
    if submitted:
        if all(v.strip() for v in values.values()):
            add_note(values)
            st.success("오답을 저장했어요!")
        else:
            st.error("모든 항목을 입력해 주세요.")

elif page == "퀴즈 풀기":
    subjects = sorted({n["과목"] for n in notes})
    subject = st.selectbox("복습할 과목", ["전체 과목"] + subjects)
    if st.button("새 퀴즈 시작 / 다시 시작"):
        candidates = [i for i, n in enumerate(notes) if subject == "전체 과목" or n["과목"] == subject]
        if not candidates:
            st.info("먼저 오답을 등록해 주세요.")
        else:
            indices = random.sample(candidates, min(5, len(candidates)))
            st.session_state.quiz = {"pool": [notes[i] for i in indices], "pos": 0, "score": 0, "checked": False, "correct": False}
    q = st.session_state.get("quiz")
    if q:
        if q["pos"] >= len(q["pool"]):
            st.success(f"퀴즈 완료! {q['score']} / {len(q['pool'])}문제 정답")
        else:
            item = q["pool"][q["pos"]]
            st.subheader(f"문제 {q['pos'] + 1} / {len(q['pool'])} · {item['과목']}")
            st.write(item["문제"])
            with st.form(f"answer_{q['pos']}"):
                answer = st.text_input("정답", disabled=q["checked"])
                check = st.form_submit_button("정답 확인", disabled=q["checked"])
            if check and not q["checked"]:
                if not answer.strip():
                    st.warning("정답을 입력해 주세요.")
                else:
                    correct = answer.strip() == item["정답"].strip()
                    if correct:
                        delete_note(item["id"])
                        q["score"] += 1
                    q["checked"] = True
                    q["correct"] = correct
                    st.rerun()
            if q["checked"]:
                if q["correct"]:
                    st.success("정답! 이 문제를 오답 노트에서 삭제했어요.")
                else:
                    st.error("아쉽지만 오답이에요.")
                    st.write("정답:", item["정답"])
                    st.write("내가 썼던 오답:", item["오답"])
                st.write("해설:", item["해설"])
                if st.button("다음 문제"):
                    q["pos"] += 1
                    q["checked"] = False
                    st.rerun()

elif page == "조회 · 수정 · 삭제":
    st.subheader(f"등록된 오답 {len(notes)}개")
    if not notes:
        st.info("등록된 오답이 없습니다.")
    else:
        index = st.selectbox("문제 선택", range(len(notes)), format_func=lambda i: f"{i+1}. [{notes[i]['과목']}] {notes[i]['문제']}")
        note = notes[index]
        with st.form(f"edit_{note['id']}"):
            updated = {f: st.text_area(f, value=note[f]) for f in FIELDS}
            update = st.form_submit_button("수정 저장")
        if update:
            if all(v.strip() for v in updated.values()):
                update_note(note["id"], updated)
                st.session_state.pop("quiz", None)
                st.success("수정했습니다. 다른 메뉴로 이동하면 변경 내용을 볼 수 있어요.")
            else:
                st.error("모든 항목을 입력해 주세요.")
        confirm = st.checkbox("선택한 문제를 삭제하는 데 동의합니다.", key=f"confirm_{note['id']}")
        if st.button("선택한 문제 삭제", disabled=not confirm):
            delete_note(note["id"])
            st.session_state.pop("quiz", None)
            st.rerun()

else:
    backup = [{f: n[f] for f in FIELDS} for n in notes]
    st.download_button("📥 오답 JSON 백업", json.dumps(backup, ensure_ascii=False, indent=2), file_name="wrong_notes.json", mime="application/json")
    uploaded = st.file_uploader("기존 JSON 가져오기 (최대 500개)", type=["json"])
    st.caption("기존 오답을 삭제하지 않고 추가합니다. 같은 파일을 다시 가져오면 중복됩니다.")
    if st.button("내 계정으로 가져오기", disabled=uploaded is None):
        try:
            restored = json.loads(uploaded.getvalue().decode("utf-8-sig"))
            if not valid_notes(restored):
                raise ValueError("항목과 개수를 확인하세요.")
        except (ValueError, UnicodeError):
            st.error("올바른 오답 JSON인지 확인해 주세요. 각 항목은 1~10000자, 최대 500개입니다.")
        else:
            payload = [{"user_id": uid, **{COLUMNS[f]: n[f].strip() for f in FIELDS}} for n in restored]
            if payload:
                db_action(lambda: db.table("notes").insert(payload).execute())
            st.session_state.pop("quiz", None)
            st.success("가져왔습니다. 조회 메뉴에서 확인해 주세요.")
