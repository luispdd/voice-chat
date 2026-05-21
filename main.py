import time
from openai import OpenAI

from ear import listen_to_user
import mouth

# Initialize LM Studio Client Endpoint
client = OpenAI(base_url="http://127.0.0.1:1234/v1", api_key="lm-studio")

def chat_with_brain(system_prompt: str, model_name: str):
    conversation_history = [{"role": "system", "content": system_prompt}]
    
    print("\n" + "="*50)
    print("🤖 OFFLINE VOICE ASSISTANT ONLINE")
    print("   Brain Engine: google/gemma-3-4b-it (via LM Studio)")
    print("   Voice Core: Piper TTS (en_US-amy-medium)")
    print("="*50)
    
    initial_greeting = "System operational. I am ready to converse."
    print(f"\n🤖 AI: {initial_greeting}", flush=True)
    mouth.speak_text(initial_greeting)
    
    while True:
        # 1. EAR: Pause and listen normally for your voice input via Vosk
        user_text = listen_to_user()
        
        if not user_text.strip():
            continue
            
        print(f"\n👤 You: {user_text}", flush=True)
        
        # Check for system termination requests
        if user_text.lower() in ["exit", "quit", "goodbye"]:
            print(f"\n🤖 AI: Shutting down systems. Goodbye.", flush=True)
            mouth.speak_text("Goodbye.")
            break
            
        conversation_history.append({"role": "user", "content": user_text})
        print("\n🤖 AI is thinking...", flush=True)
        
        try:
            # 2. BRAIN: Send conversation tree history to local LM Studio server
            response = client.chat.completions.create(
                model=model_name,
                messages=conversation_history,
                stream=False
            )
            ai_text_response = response.choices[0].message.content
            
            # Print response to the terminal
            print(f"\n🤖 AI TEXT TO BE SPOKEN:\n{ai_text_response}\n", flush=True)
            conversation_history.append({"role": "assistant", "content": ai_text_response})
            
            # 3. MOUTH: Speak out the response text sequentially
            mouth.speak_text(ai_text_response)
            
        except Exception as e:
            print(f"\n🚨 Brain Core Connection Error: {e}", flush=True)
            time.sleep(2)

if __name__ == "__main__":
    SYSTEM_INSTRUCTIONS = (
        "You are a helpful, brief, local terminal voice assistant. "
        "Keep your answers short and highly conversational. Avoid lists, bullets, or symbols."
    )
    MODEL_IDENTIFIER = "google/gemma-3-4b-it"
    chat_with_brain(SYSTEM_INSTRUCTIONS, MODEL_IDENTIFIER)
