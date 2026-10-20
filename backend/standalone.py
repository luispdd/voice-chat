"""
Standalone Voice Companion Runner.

Direct terminal execution utilizing PipeWire audio I/O, Whisper STT,
streaming LLM tokens, and Piper TTS without running any browser or web server.
"""

import asyncio
import re
import sys
import time
from backend import config, stt, llm, tts
from backend.pipewire import PipeWireRecorder, PipeWirePlayer


def _split_sentences(text: str):
    """Split text into completed sentences and leftover buffer."""
    parts = re.split(r'(?<=[.!?])\s+', text)
    if len(parts) > 1:
        return parts[:-1], parts[-1]
    return [], text


async def _stream_llm_and_play(history, player: PipeWirePlayer):
    """
    Stream tokens from LLM, display them in real-time,
    and synthesize/play each completed sentence via PipeWire.
    """
    sys.stdout.write("🤖 AI: ")
    sys.stdout.flush()

    response_stream = await llm.get_chat_stream(history)

    text_buffer = ""
    full_response = ""

    async for chunk in response_stream:
        token = chunk.choices[0].delta.content if chunk.choices[0].delta.content else ""
        if token:
            sys.stdout.write(token)
            sys.stdout.flush()
            text_buffer += token
            full_response += token

            completed_sentences, text_buffer = _split_sentences(text_buffer)
            for sentence in completed_sentences:
                cleaned = sentence.strip()
                if cleaned:
                    # Stream Piper speech chunks directly to pw-play
                    player.play_stream(tts.synthesize_stream(cleaned))

    # Remaining text at end of stream
    remaining = text_buffer.strip()
    if remaining:
        player.play_stream(tts.synthesize_stream(remaining))

    sys.stdout.write("\n\n")
    sys.stdout.flush()
    return full_response


def run_standalone():
    """Main execution loop for standalone voice companion."""
    print("\n" + "=" * 60)
    print("🔥 INITIALIZING STANDALONE ENGINES (PIPEWIRE MODE)...")
    print("=" * 60)

    stt.init_stt()
    tts.init_tts()
    llm.init_llm()

    print("\n" + "=" * 60)
    print("🚀 OFFLINE VOICE COMPANION ONLINE (STANDALONE)")
    print(f"🧠 Selected LLM:  [{config.ENGINE.upper()}] -> {config.MODEL}")
    print(f"👂 STT Model:     Whisper.cpp ({config.STT_MODEL_NAME})")
    print(f"🔊 Audio Backend: PipeWire (Native CLI Pipes)")
    print("=" * 60)
    print("💡 Start speaking naturally into your microphone.")
    print("   Say 'quit', 'exit', or press Ctrl+C to terminate.\n")

    player = PipeWirePlayer(sample_rate=22050, channels=1)

    def on_speech_start():
        sys.stdout.write("\r[🗣️ Recording speech...]       ")
        sys.stdout.flush()

    def on_speech_end():
        sys.stdout.write("\r[⚙️ Transcribing audio...]      ")
        sys.stdout.flush()

    import os
    speech_threshold = float(os.getenv("SPEECH_THRESHOLD", "0.012"))
    silence_duration_s = float(os.getenv("SILENCE_DURATION", "0.85"))

    recorder = PipeWireRecorder(
        sample_rate=16000,
        speech_threshold=speech_threshold,
        silence_duration_s=silence_duration_s,
        pre_roll_duration_s=0.4,
        on_speech_start=on_speech_start,
        on_speech_end=on_speech_end,
    )

    history = [{"role": "system", "content": config.SYSTEM_INSTRUCTIONS}]

    try:
        recorder.start()

        # Optional initial greeting
        greeting = "System operational. I am ready to converse."
        sys.stdout.write(f"🤖 AI: {greeting}\n\n")
        sys.stdout.flush()
        player.play_stream(tts.synthesize_stream(greeting))

        while True:
            sys.stdout.write("\r[🎙️ Listening...]              ")
            sys.stdout.flush()

            audio_data = recorder.get_utterance(timeout=0.5)
            if audio_data is None:
                continue

            stt_start = time.perf_counter()
            user_text = stt.transcribe_audio_array(audio_data)
            stt_time = time.perf_counter() - stt_start

            if not user_text.strip():
                continue

            # Clear status line and show user input
            sys.stdout.write(f"\r👤 You: {user_text}  ({stt_time:.2f}s)\n")
            sys.stdout.flush()

            if user_text.strip().lower() in ["exit", "quit", "goodbye"]:
                sys.stdout.write("🤖 AI: Shutting down. Goodbye!\n")
                sys.stdout.flush()
                player.play_stream(tts.synthesize_stream("Goodbye!"))
                break

            history.append({"role": "user", "content": user_text})

            # Temporarily pause recorder while AI speaks to prevent echo loopback
            recorder.pause()
            try:
                ai_text = asyncio.run(_stream_llm_and_play(history, player))
                history.append({"role": "assistant", "content": ai_text})

                # Prune history if needed
                if len(history) > 11:
                    history = [history[0]] + history[-10:]
            finally:
                recorder.resume()

    except KeyboardInterrupt:
        print("\n\n🛑 Received keyboard interrupt. Shutting down...")
    finally:
        player.stop()
        recorder.stop()
        print("✅ Standalone session ended cleanly.\n")
