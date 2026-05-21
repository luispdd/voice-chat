import queue
import sys
import json
import sounddevice as sd
from vosk import Model, KaldiRecognizer

# Thread-safe queue to pass raw microphone buffer streams
audio_queue = queue.Queue()

def audio_callback(indata, frames, time, status):
    """This function is called by sounddevice for every audio block captured."""
    if status:
        print(status, file=sys.stderr)
    audio_queue.put(bytes(indata))

def listen_to_user() -> str:
    """Captures system audio using sounddevice and streams it directly to Vosk."""
    # Point directly to the folder you just unzipped in your project directory
    model_path = "vosk-model-small-en-us-0.15"
        
    try:
        model = Model(model_path)
    except Exception:
        return "Error: Local Vosk model folder not found in project directory. Please check Step 1."

    sample_rate = 16000
    recognizer = KaldiRecognizer(model, sample_rate)
    
    print("\n" + "="*40)
    print("[Microphone Online - Start speaking now...]")
    print("="*40)
    
    # Open the native PipeWire device stream input channel
    try:
        with sd.RawInputStream(samplerate=sample_rate, blocksize=4000, dtype='int16',
                               channels=1, callback=audio_callback):
            
            silence_counter = 0
            while True:
                data = audio_queue.get()
                
                if recognizer.AcceptWaveform(data):
                    result_json = json.loads(recognizer.Result())
                    text = result_json.get("text", "")
                    if text.strip():
                        return text
                else:
                    # Check partial results to see if speech has ended
                    partial = json.loads(recognizer.PartialResult())
                    partial_text = partial.get("partial", "")
                    
                    # If user spoke and then stopped, break out after a brief pause
                    if partial_text:
                        silence_counter = 0
                    else:
                        silence_counter += 1
                        
                    # Auto-break out if there's continuous silence after starting
                    if silence_counter > 30: 
                        final_json = json.loads(recognizer.FinalResult())
                        text = final_json.get("text", "")
                        if text.strip():
                            return text
                        silence_counter = 0
                    
    except KeyboardInterrupt:
        return ""
    except Exception as e:
        return f"Hardware Streaming Error: {e}"

if __name__ == "__main__":
    spoken_text = listen_to_user()
    if spoken_text:
        print(f"\n🎉 Success! Captured Text: '{spoken_text}'")
    else:
        print("\n❌ Empty signal captured.")
