import streamlit as st
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline, TFAutoModelForSequenceClassification
from langchain import LLMChain, PromptTemplate
from langchain_community import llms
from langchain.llms import HuggingFacePipeline
from langchain.memory.buffer import ConversationBufferMemory
from langchain_core.output_parsers import StrOutputParser
from peft import PeftModel, LoraConfig, get_peft_model
import torch

# Custom CSS to style the app
st.markdown("""
    <style>
    body {
        background-size: cover;
    }
    .main {
        background: radial-gradient(circle at 10% 20%, rgb(69, 86, 102) 0%, rgb(34, 34, 34) 90%);
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0px 0px 10px rgba(0, 0, 0, 0.1);
    }
    .message {
        padding: 10px;
        border-radius: 10px;
        margin-bottom: 10px;
    }
    .user {
        background-color: #6897ab;
    }
    .assistant {
        background-color: #848a86;
        color: white;
    }
    </style>
""", unsafe_allow_html=True)

class StoryCreativityChain:
    def __init__(self, model, tokenizer):
        self.llmPipeline = pipeline(
            "text-generation",
            model=model,
            tokenizer=tokenizer,
            torch_dtype=torch.float16,
            device_map="auto",
            max_new_tokens=1000,
            do_sample=True,
            top_k=30,
            num_return_sequences=1,
            eos_token_id=tokenizer.eos_token_id
        )
        self.llm = HuggingFacePipeline(pipeline=self.llmPipeline, model_kwargs={'temperature': 0.7, 'max_length': 5, 'top_k': 50})

    def getPromptFromTemplate(self):
        system_prompt = """You are a creative assistant specializing in generating detailed and imaginative stories, crafting interesting and well-structured recipes, and composing beautiful poetry. Follow these guidelines:

        1. **Stories:** Create engaging, detailed, and imaginative stories with vivid descriptions, compelling characters, and cohesive plots. Always consider the user's mood when crafting the story.
        2. **Recipes:** Generate step-by-step instructions for recipes that are easy to follow, include all necessary ingredients, and result in delicious dishes. Respond to recipe-related queries such as:
           - "What is the recipe of..."
           - "How do I make..."
           - "How can I make..."
           - "I want to cook..."
        3. **Poetry:** Write poems that are meaningful, expressive, and emotionally resonant, taking the user's mood into account.

        For any other requests, respond politely and concisely with:
        "I'm sorry, but I can only assist with stories, recipes, and poetry. Let's focus on those areas."

        Additionally, do not generate or provide code in any programming language such as C++, Python, JavaScript, etc. If asked about coding or any other topics outside stories, recipes, and poetry, respond with:
        "I'm sorry, but I can only assist with stories, recipes, and poetry. Let's focus on those areas."

        Remember:
        - Stick strictly to stories, recipes, and poetry even if the user repeatedly asks questions other than these.
        - Maintain a polite and helpful tone.
        - Do not provide information or assistance outside the specified scope, regardless of user insistence.
        """
        
        B_INST, E_INST = "[INST]", "[/INST]"
        B_SYS, E_SYS = "<<SYS>>\n", "\n<</SYS>>\n\n"
        SYSTEM_PROMPT1 = B_SYS + system_prompt + E_SYS

        instruction = """
        History: {history} \n
        User's Mood: {user's mood} \n
        User: {question}"""

        prompt_template = B_INST + SYSTEM_PROMPT1 + instruction + E_INST
        prompt = PromptTemplate(input_variables=["history", "question", "user's mood"], template=prompt_template)

        return prompt

    def getNewChain(self):
        prompt = self.getPromptFromTemplate()
        memory = ConversationBufferMemory(input_key="question", memory_key="history", max_len=5)

        # Initialize LLMChain with proper parameters
        llm_chain = LLMChain(prompt=prompt, llm=self.llm, verbose=True, memory=memory, output_parser=CustomOutputParser())

        # Return a callable that processes inputs using the chain
        def run_chain(inputs):
            question = inputs.get("question", "")
            mood = inputs.get("user's mood", "")
            return llm_chain.run({"history": "", "question": question, "user's mood": mood})

        return run_chain

class CustomOutputParser(StrOutputParser):
    def parse(self, response: str):
        # Ensure response only contains content after the instruction end tag
        return response.split('[/INST]')[-1].strip()

# Cache the model and tokenizer to load them only once
@st.cache_resource
def load_model_and_tokenizer():
    model_id = "NousResearch/Llama-2-7b-chat-hf"
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(model_id, device_map="auto", torch_dtype=torch.float16)



    # Load pre-trained emotion classifier
    emotion_tokenizer = AutoTokenizer.from_pretrained("distilbert-base-uncased")
    emotion_model = TFAutoModelForSequenceClassification.from_pretrained("AaronMarker/emotionClassifier", num_labels=9)
    emotion_classifier = pipeline("text-classification", model=emotion_model, tokenizer=emotion_tokenizer)

    # Define the emotion mapping
    emotions = {
        'LABEL_0': 'Joy',
        'LABEL_1': 'Desire',
        'LABEL_2': 'Admiration',
        'LABEL_3': 'Approval',
        'LABEL_4': 'Curiosity',
        'LABEL_5': 'Fear',
        'LABEL_6': 'Sadness',
        'LABEL_7': 'Anger',
        'LABEL_8': 'Neutral'
    }

    return model, tokenizer, emotions, emotion_classifier

model, tokenizer, emotions, emotion_classifier = load_model_and_tokenizer()

# device = torch.device('cuda:1')
# model.to(device)

# Initialize the StoryCreativityChain
story_chain = StoryCreativityChain(model, tokenizer)

# Initialize session state if not already done
if "chain" not in st.session_state:
    st.session_state.chain = story_chain.getNewChain()
    st.session_state.history = []

# Streamlit app code
st.title("Hey! How can I help you?")

# Sidebar with helper text
st.sidebar.title("Creative Assistant")
st.sidebar.write("Hey, I am here to help you with amazing stories, recipes, and poetry.")
st.sidebar.markdown("**Let's get creative!**")
st.sidebar.header("Quick Tips:")
st.sidebar.markdown("""
- **For stories:** Use prompts like "Tell me a story about a brave knight" or "Write a story about an adventure in space."
- **For recipes:** Try asking "Can you give me a recipe for chocolate cake?" or "How do I make a delicious pasta?"
- **For poetry:** Try prompts like "Write a poem about love" or "Compose a poem about nature."
- **Stay on topic:** Remember, I specialize in stories, recipes, and poetry. Let's keep our chat focused on these!
""")

# User input
user_input = st.text_input("Enter your prompt:")

# Function to predict emotion
def predict_emotion(sentence):
    prediction = emotions[emotion_classifier(sentence)[0]["label"]]
    return prediction

# Function to convert text to audio
def text_to_audio(text, filename="response.mp3"):
    tts = gTTS(text)
    tts.save(filename)
    return filename

if st.button("Generate Response"):
    if user_input:
        # Add user message to history
        st.session_state.history.append({"role": "user", "content": user_input})
        
        # Generate response
        response = st.session_state.chain({"question": user_input, "user's mood": predict_emotion(user_input)})
        
        # Convert response to audio
        audio_file = text_to_audio(response)
        
        # Add assistant response to history
        st.session_state.history.append({"role": "assistant", "content": response})
        
        # Display audio player
        st.audio(audio_file)

    else:
        st.write("Please enter a prompt.")

# Display chat history
st.write('<div class="main">', unsafe_allow_html=True)
for message in st.session_state.history:
    role_class = "user" if message["role"] == "user" else "assistant"
    st.write(f'<div class="message {role_class}">{message["content"]}</div>', unsafe_allow_html=True)
st.write('</div>', unsafe_allow_html=True)
