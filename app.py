import json
import random
from pathlib import Path
import streamlit as st

st.set_page_config(page_title="스마트 오답 노트", page_icon="📝")
DATA = Path(__file__).with_name("wrong_notes.json")
FIELDS = ("과목", "문제", "오답", "정답", "해설")

def valid_notes(value):
    return isinstance(value, list) and all(isinstance(n, dict) and all(isinstance(n.get(f), str) and n[f].strip() for f in FIELDS) for n in value)

def save():
    try:
        DATA.write_text(json.dumps(st.session_state.notes, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        st.warning("서버 파일 저장에 실패했습니다. JSON 백업을 다운로드해 주세요.")

if "notes" not in st.session_state:
    try:
        data = json.loads(DATA.read_text(encoding="utf-8"))
        if not valid_notes(data):
            raise ValueError("잘못된 데이터 형식")
        st.session_state.notes = data
    except FileNotFoundError:
        st.session_state.notes = []
    except (OSError, ValueError):
        st.session_state.notes = []
        st.warning("저장 파일을 읽지 못했습니다. 백업 파일을 불러와 주세요.")

st.title("📝 스마트 오답 노트")
st.caption("개인 테스트용 · 서버 파일은 영구 보관이 보장되지 않습니다. 중요한 내용은 JSON 백업을 받으세요.")
st.warning("이 버전은 로그인·사용자별 저장 기능이 없습니다. 공개 배포하면 다른 방문자와 데이터가 공유될 수 있으므로 개인정보는 입력하지 마세요.")
page = st.sidebar.radio("메뉴", ["오답 등록", "퀴즈 풀기", "조회 · 수정 · 삭제", "백업 · 복원"])
notes = st.session_state.notes

if page == "오답 등록":
    with st.form("register", clear_on_submit=True):
        values = {f: st.text_area(f) if f in ("문제", "해설") else st.text_input(f) for f in FIELDS}
        submitted = st.form_submit_button("저장하기")
    if submitted:
        if all(v.strip() for v in values.values()):
            notes.append({f: v.strip() for f, v in values.items()})
            save()
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
                    q["checked"] = True
                    q["correct"] = answer.strip() == item["정답"].strip()
                    if q["correct"]:
                        q["score"] += 1
                        for i, n in enumerate(notes):
                            if n is item:
                                del notes[i]
                                save()
                                break
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
        with st.form(f"edit_{index}"):
            updated = {f: st.text_area(f, value=note[f]) for f in FIELDS}
            update = st.form_submit_button("수정 저장")
        if update:
            if all(v.strip() for v in updated.values()):
                notes[index] = {f: v.strip() for f, v in updated.items()}
                st.session_state.pop("quiz", None)
                save()
                st.success("수정했습니다. 다른 메뉴로 이동하면 변경 내용을 볼 수 있어요.")
            else:
                st.error("모든 항목을 입력해 주세요.")
        confirm = st.checkbox("선택한 문제를 삭제하는 데 동의합니다.", key=f"confirm_{index}")
        if st.button("선택한 문제 삭제", disabled=not confirm):
            del notes[index]
            st.session_state.pop("quiz", None)
            save()
            st.rerun()

else:
    st.download_button("📥 오답 JSON 백업", json.dumps(notes, ensure_ascii=False, indent=2), file_name="wrong_notes.json", mime="application/json")
    uploaded = st.file_uploader("백업 JSON 불러오기", type=["json"])
    st.caption("복원하면 기존 목록을 백업 파일의 내용으로 교체합니다.")
    agree = st.checkbox("기존 목록 교체에 동의합니다.")
    if st.button("백업으로 복원", disabled=uploaded is None or not agree):
        try:
            restored = json.loads(uploaded.getvalue().decode("utf-8-sig"))
            if not valid_notes(restored):
                raise ValueError("필수 항목이 누락되었거나 형식이 잘못되었습니다.")
            st.session_state.notes = restored
            st.session_state.pop("quiz", None)
            save()
            st.success("복원했습니다.")
        except (ValueError, UnicodeError) as e:
            st.error(f"파일을 확인해 주세요: {e}")
