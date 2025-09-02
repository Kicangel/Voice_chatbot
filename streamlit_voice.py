import streamlit as st
from dotenv import load_dotenv # Openai Key 설정
import json
from openai import OpenAI
import speech_recognition as sr
from playsound import playsound
from audio_recorder_streamlit import audio_recorder

# 목소리 입력
def input_speech(recongnizer):
    recognizer = recongnizer

    with sr.Microphone() as source:
        audio = recognizer.listen(source)
        txt = recognizer.recognize_google(audio, language = 'ko-KR')
        
    return txt

# TTS (Text - To - Speech)
def tts(client, input):
    with client.audio.speech.with_streaming_response.create(
    model = 'tts-1',
    voice = 'nova',
    input = input
    ) as response:
        response.stream_to_file('tts_output.mp3')
    playsound("tts_output.mp3")

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
    recongnizer = sr.Recognizer()
    for m in st.session_state.messages:
        if m.get("role") == "system": 
            continue
        with st.chat_message(m['role']):
            st.write(m['content'])

    if (query := st.chat_input('대화를 입력하세요')) and query.strip():
        if query =='종료':
            st.chat_message('assistant').write('종료합니다')
            return
        st.chat_message('user').write(query)
        response = run_general_chat(client, query)
        jl = response.get('json_list', [])
        if isinstance(jl, dict):
            jl = list(jl.values())

        response = ' '.join(
            str(v) for d in jl if isinstance(d, dict) for v in d.values()
        )
        
        st.chat_message('assistant').write(response)
        # tts(client,response)
        

    return


load_dotenv()

situations = ['마감기한을 못지키는 상황', '요구를 거절해야하는 상황', '실수를 보고하는 상황']

my_choice = st.selectbox('상황을 선택하세요', situations)

if my_choice == situations[0]:
    st.session_state.pop("messages", None)
    system_instruction = """
        당신은 30년동안 회사에서 근무한 한 회사의 50대 임원입니다. 신입 회사원이 마감기한을 지키지 못하여 이에 대해 이야기 하는 상황극을 연출 할 것.
        사용자의 말을 듣고 이에 대해 적절한 응답을 할 것
        적절한 응답이란 너무 전문적이지 않고, 일상적인 응답일 것
        
            ### 지시 형식 ###
        사용자가 먼저 자신의 상황/해명을 말하면, 그 발화를 기반으로만 응답한다(추측 최소화).

        응답 톤: “너무 전문적이지 않고, 일상적인 표현”. 한 문단 길이의 짧은 문장 위주.

        비난/납득 강요 금지. 책임 회피가 심할 때도 사실-영향-요청 틀로 차분히 정리.

        필요 시 한 가지 확인 질문만(선택): 일정 재산정 근거, 차단 요인 등.

            ### 출력 형식 ###
        json 형식으로 반환할것
        - 첫번째 객체는 json_list여야 한다.
        - list 하위에 단어별로 json_obejct가 연속된다

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

    start_chat()

elif my_choice == situations[1]:
    st.session_state.pop("messages", None)
    system_instruction = """
        당신은 30년동안 회사에서 근무한 한 회사의 50대 임원입니다. 당신이 어떤 요구를 신입 회사원에게 했지만 신입 회사원은 이를 요구를 거절해야 하는 상황극을 연출 할 것.
        사용자의 말을 듣고 이에 대해 적절한 응답을 할 것
        적절한 응답이란 너무 전문적이지 않고, 일상적인 응답일 것
        
            ### 지시 형식 ###
        사용자가 먼저 자신의 상황/해명을 말하면, 그 발화를 기반으로만 응답한다(추측 최소화).

        응답 톤: “너무 전문적이지 않고, 일상적인 표현”. 한 문단 길이의 짧은 문장 위주.

        비난/납득 강요 금지. 책임 회피가 심할 때도 사실-영향-요청 틀로 차분히 정리.

        필요 시 한 가지 확인 질문만(선택): 일정 재산정 근거, 차단 요인 등.

            ### 출력 형식 ###
        json 형식으로 반환할것
        - 첫번째 객체는 json_list여야 한다.
        - list 하위에 단어별로 json_obejct가 연속된다

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

    start_chat()

elif my_choice == situations[2]:
    st.session_state.pop("messages", None)
    system_instruction = """
        당신은 30년동안 회사에서 근무한 한 회사의 50대 임원입니다. 신입 회사원이 당신에게 실수를 보고하는 상황극을 연출 할 것.
        사용자의 말을 듣고 이에 대해 적절한 응답을 할 것
        적절한 응답이란 너무 전문적이지 않고, 일상적인 응답일 것
        
            ### 지시 형식 ###
        사용자가 먼저 자신의 상황/해명을 말하면, 그 발화를 기반으로만 응답한다(추측 최소화).

        응답 톤: “너무 전문적이지 않고, 일상적인 표현”. 한 문단 길이의 짧은 문장 위주.

        비난/납득 강요 금지. 책임 회피가 심할 때도 사실-영향-요청 틀로 차분히 정리.

        필요 시 한 가지 확인 질문만(선택): 일정 재산정 근거, 차단 요인 등.

            ### 출력 형식 ###
        json 형식으로 반환할것
        - 첫번째 객체는 json_list여야 한다.
        - list 하위에 단어별로 json_obejct가 연속된다

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

    start_chat()