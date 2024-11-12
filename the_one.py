import streamlit as st
import json
from typing import List, Dict, Any
from pydantic import BaseModel
# from groq import Groq
from openai import OpenAI
from typing_extensions import Literal

class Question_Details(BaseModel):
    question: str
    question_type: Literal['radio', 'multiselect']
    question_options: List[str]
    answer: str  

class Module(BaseModel):
    name: str
    sub_modules: List[str]

class Curriculum(BaseModel):
    modules: List[Module]

LEVEL_THRESHOLDS = {
    'beginner': 3,
    'intermediate': 6
}

previous_questions = ["what is a question?"]

client = Groq(api_key="noen") 

def main():
    st.title("AI Tutor")

    if 'initialized' not in st.session_state:
        st.session_state.initialized = False

    if not st.session_state.initialized:
        st.header("Enter your details")
        name = st.text_input("Name")
        email = st.text_input("Email")
        age = st.number_input("Age", min_value=0)
        topic_to_learn = st.text_input("What topic would you like to learn?")
        experience_topic = st.text_input("What topic do you have experience in?")

        if st.button("Submit", key="submit_initial"):
            if not (name and email and age and topic_to_learn and experience_topic):
                st.error("Please fill in all the fields.")
            else:
                st.session_state.name = name
                st.session_state.email = email
                st.session_state.age = age
                st.session_state.topic_to_learn = topic_to_learn
                st.session_state.experience_topic = experience_topic

                st.session_state.current_question = 0
                st.session_state.questions = []
                st.session_state.answers = []
                st.session_state.is_assessment_complete = False
                st.session_state.current_level = 'beginner'
                st.session_state.points = 0 
                st.session_state.correct_answers = 0
                st.session_state.initialized = True

                similarity = checker()
                if not similarity:
                    st.write("Thank You! Lets Kick-Start your Journey!!!")
                    generate_curriculum()
                    return
                else:
                    st.write("Thank you! Now we will start the assessment.")
                    generate_questions()
    else:
        if st.session_state.is_assessment_complete:
            st.write("Assessment complete! Thank you.")
            generate_curriculum()
        else:
            display_question()


def checker():
    prmpt = f''' You got the whole world's knowledge.You compare two topics and give a value between 0 to 1 it can be a decimal value.This value determines or says how close the first topic is related to the second topic.Just the value Nothing else.
    The first topic : {st.session_state.experience_topic}
    The second topic : {st.session_state.topic_to_learn}.
    '''

    response = client.chat.completions.create(
        messages= [{"role":"user","content": prmpt}],
        model="gpt-4o-mini"
    )
    response_content = response.choices[0].message.content.strip()
    if(float(response_content) > 0.65 ):
        return True
    else: 
        return False

def generate_questions():
    if st.session_state.current_question < 10:
        prompt = f"""
        You are a Socratic Tutor, generate a question in {st.session_state.experience_topic} at a '{st.session_state.current_level}'-level.Strictly follow the JSON object model to generate the question and use the following principles:
        - A clear and specific question
        - A 'multiselect' or 'radio' type question
        - A list of options for answers
        - The correct answer from the options for that question

        Make sure the question is new and hasn't been asked before, here is a list of previously asked questions so don't ask questions similar to these: {previous_questions}
        The JSON Object Model:"{json.dumps(Question_Details.model_json_schema(), indent=2)}" 
        """

        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="gpt-4o-mini",
            response_format={"type": "json_object"}
        )

        response_content = response.choices[0].message.content.strip()
        question_data = json.loads(response_content)
        question = Question_Details(**question_data)
        st.session_state.questions.append(question)
        display_question()
        
def display_question():
    if st.session_state.current_question < len(st.session_state.questions):
        question = st.session_state.questions[st.session_state.current_question]
        st.header(question.question)
        previous_questions.append(question.question)

        if question.question_type == 'radio':
            selected_option = st.radio(
                "Choose an option",
                question.question_options,
                key=f"radio_{st.session_state.current_question}"
            )
        elif question.question_type == 'multiselect':
            selected_option = []
            for option in question.question_options:
                if st.checkbox(option, key=f"checkbox_{option}"):
                    selected_option.append(option)

        if st.button("Submit Answer", key=f"submit_{st.session_state.current_question}"):
            result = evaluate_answer(question, selected_option)
            level = st.session_state.current_level
            if result == 'correct':  
                st.session_state.correct_answers += 1
                st.session_state.points += get_points(level)
                update_level()

            st.session_state.answers.append(selected_option)
            st.session_state.current_question += 1

            if st.session_state.current_question >= 10:
                st.session_state.is_assessment_complete = True
                st.write("Assessment complete! Thank you.")
                generate_curriculum()
            else:
                generate_questions()
    else:
        st.session_state.is_assessment_complete = True
        st.write("Assessment complete! Thank you.")
        curriculum = generate_curriculum()

def get_points(level):
    if level == 'beginner':
        return 1
    elif level == 'intermediate':
        return 2
    elif level == 'expert':
        return 3
    return 0

def update_level():
    if st.session_state.current_level in LEVEL_THRESHOLDS:
        threshold = LEVEL_THRESHOLDS[st.session_state.current_level]
        if st.session_state.points >= threshold:
            if st.session_state.current_level == 'beginner':
                st.session_state.current_level = 'intermediate'
            elif st.session_state.current_level == 'intermediate':
                st.session_state.current_level = 'advanced'
            
            st.session_state.points = 0  
            st.session_state.correct_answers = 0

def evaluate_answer(question: Question_Details, answer: Any) -> str:
    if isinstance(answer, list):
        return 'correct' if question.answer in answer else 'incorrect'
    return 'correct' if answer == question.answer else 'incorrect'

def generate_curriculum() -> Dict[str, Any]:
    similarity = checker()
    if similarity:
        prompt = f"""
            Based on the student's level of knowledge in experienced topic , create a structured curriculum for learning topic they wish to learn. The curriculum should be detailed and tailored to their proficiency level. The curriculum should include:
            Experienced Topic : {st.session_state.experience_topic}
            Experience in that topic: {st.session_state.current_level} level 
            Topic they wish to learm : {st.session_state.topic_to_learn}
            - A list of modules
            - Each module should have a list of sub-modules
            - Ensure the curriculum is clear and organized
            - If the new topic shares similarities with the experienced topic, start with a module covering overlapping concepts. For instance, if the student is experienced in Python and wants to learn Java, include a module about Python concepts relevant to Java.

            Make sure to format the response as a JSON object following this schema: 
            {{
            "modules": [
                {{
                "name": "Module Name",
                "sub_modules": ["Sub-module 1", "Sub-module 2"]
                }}
            ]
            }}
    """
        # {json.dumps(Curriculum.model_json_schema(), indent=2)}
    else:
        prompt = f"""
        You are a Socratic tutor. Use the following principles in responding to students:
        Topic : {st.session_state.topic_to_learn}
        - You generate a curriculum in the topic the student wish to learn
        - You generate the curriculum in such a way that even total beginner/a baby can throughly understand the nuke and corner of the topic 
        - You provide a list of modules
        - You alse provide a list of sub-modules for each module created
        - Ensure the JSON object format follows this schema:
            {{
                "modules": [
                    {{
                    "name": "Module Name",
                    "sub_modules": ["Sub-module 1", "Sub-module 2"]
                    }}
                ]
                }}
        """
    response = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="gpt-4o-mini",
        response_format={"type": "json_object"}
    )

    response_content = response.choices[0].message.content.strip()
    st.write("Raw response content:", response_content) # for raw content

    curriculum_data = json.loads(response_content) # for parsed json content
    st.write("Parsed curriculum data:", curriculum_data)

    return display_curriculum(curriculum_data)
    
    
def display_curriculum(curriculum):
    st.write("### Your Curated Curriculum")

    # if "modules" in curriculum:
    modules = curriculum['modules']
    
    if not modules:
        st.write("No modules found.")
        return
    
    for module in modules:
        module_name = module.get('name', 'Unnamed Module')
        sub_modules = module.get('sub_modules', [])

        with st.expander(module_name, expanded=True):
            if sub_modules:
                st.write("**Sub-Modules:**")
                for sub_module in sub_modules:
                    st.write(f"- {sub_module}")
            else:
                st.write("No sub-modules available for this module.")
    # else:
    #     st.write("No curriculum data available or the data format is incorrect.")

if __name__ == "__main__":
    main()