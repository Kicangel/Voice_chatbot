import streamlit as st
from dotenv import load_dotenv # Openai Key 설정
import json
from openai import OpenAI
import speech_recognition as sr
from playsound import playsound
from audio_recorder_streamlit import audio_recorder
import io, os, tempfile

# 목소리 입력
def input_speech(recongnizer, timeout=5, phrase_time_limit=10, language='ko-KR'):
    recognizer = recongnizer

    with sr.Microphone() as source:
        # 주변 소음 기준 잡기(0.5~1.0초 권장)
        recognizer.adjust_for_ambient_noise(source, duration=0.6)
        # 오래 기다리지 않도록 제한
        try:
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
        except sr.WaitTimeoutError:
            st.warning("음성이 감지되지 않았습니다. 다시 말씀해 주세요.")
            return ""

    try:
        text = recognizer.recognize_google(audio, language=language) 
        return text.strip()
    except sr.UnknownValueError:
        st.warning("음성을 이해하지 못했습니다. 또렷하게 다시 말씀해 주세요.")
        return ""
    except sr.RequestError as e:
        st.error(f"STT 서버 오류: {e}")
        return ""
    
def transcribe_wav_bytes(wav_bytes: bytes, language='ko-KR') -> str:
    r = sr.Recognizer()
    try:
        with sr.AudioFile(io.BytesIO(wav_bytes)) as source:
            audio = r.record(source)
        return r.recognize_google(audio, language=language).strip()
    except sr.UnknownValueError:
        st.warning("음성을 이해하지 못했습니다. 다시 시도해 주세요.")
        return ""
    except sr.RequestError as e:
        st.error(f"STT 서버 오류: {e}")
        return ""

# TTS (Text - To - Speech)
def tts(client, text, voice = "nova", model = "tts-1"):
    if not text:
        return b""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        tmp_path = tmp.name
    try:
        with client.audio.speech.with_streaming_response.create(
            model=model, voice=voice, input=text
        ) as resp:
            resp.stream_to_file(tmp_path)
        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass

# Chat 시작 
def run_general_chat(client, query, temperature = 0.3):
    user_message = f"""
        {query}
    """
    st.session_state.messages.append({
                    "role":"user",
                    "content":[
                        {
                            "type":"text",
                            "text":user_message
                        }
                    ]
                })
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages = st.session_state.messages,
        response_format={
            "type":"json_object"       
        },
        temperature=temperature,
        max_tokens=2048,
        top_p=1,
        frequency_penalty=1,
        presence_penalty=1
    )

    st.session_state.messages.append(
        {
                "role":"assistant",
                "content":response.choices[0].message.content
            }
    )
    return json.loads(response.choices[0].message.content)
                
def start_chat():
    client = OpenAI()
    chat = st.session_state.get("chat", [])
    last_idx = len(chat) - 1
    st.session_state.setdefault("tts_cache", {})
    for idx, m in enumerate(st.session_state.get("chat", [])):
        role = m.get("role", "assistant")
        if role == "system":
            continue

        text = m.get("content", "")
        with st.chat_message(role):
            st.write(text)

            if role == "assistant":
                btn_key   = f"tts_btn_{idx}"
                shown_key = f"tts_shown_{idx}"

                if st.button("▶️ 음성으로 듣기", key=btn_key):
                    audio_bytes = st.session_state.tts_cache.get(text)
                    if not audio_bytes:
                        audio_bytes = tts(client, text)  
                        st.session_state.tts_cache[text] = audio_bytes
                    st.session_state[shown_key] = True  

                if st.session_state.get(shown_key):
                    audio_bytes = st.session_state.tts_cache.get(text, b"")
                    if audio_bytes:
                        st.audio(audio_bytes, format="audio/mp3")
            
            if idx == last_idx:
                with st.popover("🎤 음성 입력", use_container_width=False):
                    st.caption("녹음 버튼을 누르고 말씀한 뒤 전송을 누르세요.")
                    wav_bytes = audio_recorder(sample_rate=16000, pause_threshold=1.2, text="녹음 시작/정지")
                    if wav_bytes:
                        st.audio(wav_bytes, format="audio/wav")
                        if st.button("전송", key=f"send_voice_{idx}"):
                            text_from_voice = transcribe_wav_bytes(wav_bytes)
                            if text_from_voice:
                                st.session_state["pending_query"] = text_from_voice
                                st.rerun()
                            else:
                                st.warning("음성 인식 결과가 비어 있습니다.")
    query = st.session_state.pop("pending_query", None)
    if not query:
        query = st.chat_input('대화를 입력하세요', key='chat_input_main')

    if query and query.strip():
        if query =='종료':
            st.chat_message('assistant').write('종료합니다')
            return
        
        st.session_state.chat.append({
                "role":"user",
                "content":query
        })

        st.chat_message('user').write(query)
        response = run_general_chat(client, query)
        jl = response.get('json_list', [])
        response_text = ' '.join(str(s).strip() for s in jl)
        
        st.session_state.chat.append({
                "role":"assistant",
                "content":response_text
        })
        st.chat_message('assistant').write(response_text)
        with st.chat_message('assistant'):
            st.write(response_text)

            # ✅ 새 응답은 TTS를 미리 만들어 캐시에 저장 (버튼 누르면 바로 재생 가능)
            if response_text and response_text not in st.session_state.tts_cache:
                audio_bytes = tts(client, response_text)
                st.session_state.tts_cache[response_text] = audio_bytes

            # 같은 런에서 바로 버튼 + 재생도 가능
            new_idx = len(st.session_state.chat) - 1
            if st.button("▶️ 음성으로 듣기", key=f"tts_btn_{new_idx}"):
                ab = st.session_state.tts_cache.get(response_text)
                if not ab:
                    ab = tts(client, response_text)
                    st.session_state.tts_cache[response_text] = ab
                st.session_state[f"tts_shown_{new_idx}"] = True
            if st.session_state.get(f"tts_shown_{new_idx}"):
                ab = st.session_state.tts_cache.get(response_text, b"")
                if ab:
                    st.audio(ab, format="audio/mp3")
        

    return


load_dotenv()

situations = ['마감기한을 못지키는 상황', '요구를 거절해야하는 상황', '실수를 보고하는 상황']

my_choice = st.selectbox('상황을 선택하세요', situations)

if 'last_choice' not in st.session_state:
    st.session_state['last_choice'] = None

if my_choice != st.session_state['last_choice']:
    st.session_state.pop("chat", None)
    st.session_state.pop('messages', None)   
    st.session_state['last_choice'] = my_choice

if my_choice == situations[0]:
    system_instruction = """
        당신은 30년동안 회사에서 근무한 한 회사의 50대 임원입니다. 신입 회사원이 마감기한을 지키지 못하여 이에 대해 이야기 하는 상황극을 연출 할 것.
        사용자의 말을 듣고 이에 대해 적절한 응답을 할 것
        적절한 응답이란 너무 전문적이지 않고, 일상적인 응답일 것
        
            ### 지시 형식 ###
        사용자가 먼저 자신의 상황/해명을 말하면, 그 발화를 기반으로만 응답한다(추측 최소화).

        - 기본 톤: 차분하고 일상적인 톤.
        - 다음 경우가 하나라도 있으면 ‘경고 톤’으로 전환한다.
        (경우) 반말/명령조로 상사를 대함, 비꼼/조롱, 욕설·비하, 책임 전가·허위 보고, 회사/규정 조롱, 조롱조의 업무 거부.
        - 경고 톤은 엄중하고 단호하되, 예의는 유지한다. 비속어/인신공격/차별 표현 금지.

        비난/납득 강요 금지. 책임 회피가 심할 때도 사실-영향-요청 틀로 차분히 정리.

        필요 시 한 가지 확인 질문만(선택): 일정 재산정 근거, 차단 요인 등.


            ### 출력 형식 ###
        json 형식으로 반환할것
        - 첫번째 객체는 json_list여야 한다.
        -json_list 안에 단어 단위 객체를 넣지 말고, 완성 문장만 넣어라.

        출력 형식
        [응답] : 응답

    """
    if 'messages' not in st.session_state:
        st.session_state.messages = [{
                    "role":"system",
                    "content":[
                        {
                            "type":"text",
                            "text":system_instruction
                        }
                    ]
                },
                {"role": "assistant", "content": "저번에 맡은 프로젝트, 어떻게 진행되고 있어?"}]
        
    if "chat" not in st.session_state:
        st.session_state.chat = [
            {"role": "assistant", "content": "저번에 맡은 프로젝트, 어떻게 진행되고 있어?"}
        ]

    start_chat()

elif my_choice == situations[1]:
    st.session_state.pop("messages", None)
    system_instruction = """
        당신은 30년동안 회사에서 근무한 한 회사의 50대 임원입니다. 당신이 어떤 요구를 신입 회사원에게 했지만 신입 회사원은 이를 요구를 거절해야 하는 상황극을 연출 할 것.
        사용자의 말을 듣고 이에 대해 적절한 응답을 할 것
        적절한 응답이란 너무 전문적이지 않고, 일상적인 응답일 것
        
            ### 지시 형식 ###
        사용자가 먼저 자신의 상황/해명을 말하면, 그 발화를 기반으로만 응답한다(추측 최소화).

        - 기본 톤: 차분하고 일상적인 톤.
        - 다음 경우가 하나라도 있으면 ‘경고 톤’으로 전환한다.
        (경우) 반말/명령조로 상사를 대함, 비꼼/조롱, 욕설·비하, 책임 전가·허위 보고, 회사/규정 조롱, 조롱조의 업무 거부.
        - 경고 톤은 엄중하고 단호하되, 예의는 유지한다. 비속어/인신공격/차별 표현 금지.

        비난/납득 강요 금지. 책임 회피가 심할 때도 사실-영향-요청 틀로 차분히 정리.

        필요 시 한 가지 확인 질문만(선택): 일정 재산정 근거, 차단 요인 등.

            ### 출력 형식 ###
        json 형식으로 반환할것
        - 첫번째 객체는 json_list여야 한다.
        -json_list 안에 단어 단위 객체를 넣지 말고, 완성 문장만 넣어라.

    """
    if 'messages' not in st.session_state:
        st.session_state.messages = [{
                    "role":"system",
                    "content":[
                        {
                            "type":"text",
                            "text":system_instruction
                        }
                    ]
                },
                {"role": "assistant", "content": "오늘 자료 검토 좀 대신 가능해? 급해서…"}]
    
    if "chat" not in st.session_state:
        st.session_state.chat = [
            {"role": "assistant", "content": "오늘 자료 검토 좀 대신 가능해? 급해서…"}
        ]
        
    start_chat()

elif my_choice == situations[2]:
    st.session_state.pop("messages", None)
    system_instruction = """
        당신은 30년동안 회사에서 근무한 한 회사의 50대 임원입니다. 신입 회사원이 당신에게 실수를 보고하는 상황극을 연출 할 것.
        사용자의 말을 듣고 이에 대해 적절한 응답을 할 것
        적절한 응답이란 너무 전문적이지 않고, 일상적인 응답일 것
        
            ### 지시 형식 ###
        사용자가 먼저 자신의 상황/해명을 말하면, 그 발화를 기반으로만 응답한다(추측 최소화).

        - 기본 톤: 차분하고 일상적인 톤.
        - 다음 경우가 하나라도 있으면 ‘경고 톤’으로 전환한다.
        (경우) 반말/명령조로 상사를 대함, 비꼼/조롱, 욕설·비하, 책임 전가·허위 보고, 회사/규정 조롱, 조롱조의 업무 거부.
        - 경고 톤은 엄중하고 단호하되, 예의는 유지한다. 비속어/인신공격/차별 표현 금지.

        비난/납득 강요 금지. 책임 회피가 심할 때도 사실-영향-요청 틀로 차분히 정리.

        필요 시 한 가지 확인 질문만(선택): 일정 재산정 근거, 차단 요인 등.

            ### 출력 형식 ###
        json 형식으로 반환할것
        - 첫번째 객체는 json_list여야 한다.
        - json_list 안에 단어 단위 객체를 넣지 말고, 완성 문장만 넣어라.

    """
    if 'messages' not in st.session_state:
        st.session_state.messages = [{
                    "role":"system",
                    "content":[
                        {
                            "type":"text",
                            "text":system_instruction
                        }
                    ]
                },
                {"role": "assistant", "content": "오늘 왜 지각하셨죠?"}]
    
    if "chat" not in st.session_state:
        st.session_state.chat = [
            {"role": "assistant", "content": "오늘 왜 지각하셨죠?"}
        ]
    
    start_chat()