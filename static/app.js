const actionBtn = document.getElementById('actionBtn');
const cancelBtn = document.getElementById('cancelBtn');
const statusText = document.getElementById('status');
const vumeter = document.getElementById('vumeter');
const chatLog = document.getElementById('chatLog');
const sensitivitySlider = document.getElementById('sensitivitySlider');
const sensitivityVal = document.getElementById('sensitivityVal');

// VAD State Elements
let isSessionActive = false;
let isUtteranceActive = false;
let isProcessingNetwork = false;
let currentFetchAbortController = null;

// Audio Pipeline Anchors
let vadAudioContext = null;
let vadWorkletNode = null;
let vadScriptProcessor = null;
let vadGainNode = null;
let vadAnalyser = null;
let globalStream = null;

// Audio Ring Buffer (Pre-roll preserves the first 480ms of speech before trigger)
const SAMPLE_RATE = 16000;
const MAX_PRE_ROLL = 60; // ~480ms at 128 samples/chunk
let preRollChunks = [];
let recordedChunks = [];

// Calibration & Thresholds
const SENSITIVITY_PRESETS = {
    1: { threshold: 0.040, label: "Low" },
    2: { threshold: 0.024, label: "Medium" },
    3: { threshold: 0.016, label: "Normal" },
    4: { threshold: 0.010, label: "High" },    // Default: Very responsive
    5: { threshold: 0.006, label: "Ultra" }   // Catches quiet whispers
};

let currentThreshold = SENSITIVITY_PRESETS[4].threshold;
const SILENCE_DURATION_MS = 1400; // Natural pause duration before sending (1.4s)
const BARGE_IN_THRESHOLD = 0.045;  // User voice level required to interrupt AI playback
let silenceTimer = null;
let consecutiveSpeechFrames = 0;
let lastPlaybackEndTime = 0;

// Stream Playback Engine
let playbackAudioContext = null;
let nextPlayTime = 0;
let isAudioCurrentlyPlaying = false;
let currentAiMessageBubble = null;

// Sensitivity Slider Handling
if (sensitivitySlider && sensitivityVal) {
    sensitivitySlider.addEventListener('input', (e) => {
        const val = parseInt(e.target.value, 10);
        const preset = SENSITIVITY_PRESETS[val] || SENSITIVITY_PRESETS[4];
        currentThreshold = preset.threshold;
        sensitivityVal.innerText = preset.label;
    });
}

function appendMessage(text, isUser) {
    const msgDiv = document.createElement('div');
    msgDiv.classList.add('msg', isUser ? 'user-msg' : 'ai-msg');
    msgDiv.innerText = text;
    chatLog.appendChild(msgDiv);
    chatLog.scrollTop = chatLog.scrollHeight;
    return msgDiv;
}

function handleAudioFrame(inputData) {
    if (!isSessionActive) return;

    // Calculate RMS audio level
    let sumSquares = 0;
    for (let i = 0; i < inputData.length; i++) {
        sumSquares += inputData[i] * inputData[i];
    }
    const rms = Math.sqrt(sumSquares / inputData.length);

    // Update VU meter
    const meterPercent = Math.min(100, Math.round(rms * 450));
    vumeter.style.width = `${meterPercent}%`;

    const now = Date.now();

    // Guard: ignore mic during network processing
    if (isProcessingNetwork) {
        vumeter.classList.remove('talking');
        return;
    }

    // Barge-in check: If AI is speaking and user speaks loud enough, interrupt
    if (isAudioCurrentlyPlaying) {
        if (rms > BARGE_IN_THRESHOLD) {
            console.log("⚡ Barge-in detected! Interrupting AI...");
            interruptPlayback();
        } else {
            vumeter.classList.remove('talking');
            return;
        }
    }

    // Cooldown check (prevent speaker echo loop immediately after AI speech)
    if (now - lastPlaybackEndTime < 400) {
        vumeter.classList.remove('talking');
        return;
    }

    const chunk = new Float32Array(inputData);

    // Voice Activity Detection logic
    if (rms > currentThreshold) {
        vumeter.classList.add('talking');
        consecutiveSpeechFrames++;

        // 2 consecutive frames (~16ms) triggers speech onset
        if (consecutiveSpeechFrames >= 2) {
            if (!isUtteranceActive) {
                isUtteranceActive = true;
                // Prepend rolling pre-roll buffer so initial words and consonants are 100% preserved
                recordedChunks = [...preRollChunks, chunk];
                preRollChunks = [];
                statusText.innerText = "Listening...";
                actionBtn.innerText = "Listening...";
                actionBtn.classList.add('recording');
            } else {
                recordedChunks.push(chunk);
            }

            if (silenceTimer) {
                clearTimeout(silenceTimer);
                silenceTimer = null;
            }
        }
    } else {
        vumeter.classList.remove('talking');
        consecutiveSpeechFrames = 0;

        if (isUtteranceActive) {
            // Keep capturing trailing speech sound while silence timeout runs
            recordedChunks.push(chunk);

            if (!silenceTimer) {
                silenceTimer = setTimeout(() => {
                    commitUtterance();
                }, SILENCE_DURATION_MS);
            }
        } else {
            // Keep rolling pre-roll buffer of last ~480ms
            preRollChunks.push(chunk);
            if (preRollChunks.length > MAX_PRE_ROLL) {
                preRollChunks.shift();
            }
        }
    }
}

function commitUtterance() {
    if (!isUtteranceActive) return;

    if (silenceTimer) {
        clearTimeout(silenceTimer);
        silenceTimer = null;
    }
    isUtteranceActive = false;
    consecutiveSpeechFrames = 0;

    actionBtn.classList.remove('recording');

    // Minimum utterance: ~25 frames (~200ms)
    if (recordedChunks.length > 25) {
        statusText.innerText = "Processing...";
        actionBtn.innerText = "Processing...";
        const wavBlob = exportWAV(recordedChunks, SAMPLE_RATE);
        recordedChunks = [];
        executeNetworkPayloadSend(wavBlob);
    } else {
        recordedChunks = [];
        resetToListeningState();
    }
}

function interruptPlayback() {
    if (playbackAudioContext) {
        playbackAudioContext.close();
        playbackAudioContext = null;
    }
    isAudioCurrentlyPlaying = false;
    nextPlayTime = 0;
    if (currentFetchAbortController) {
        currentFetchAbortController.abort();
        currentFetchAbortController = null;
    }
    isProcessingNetwork = false;
}

function exportWAV(chunks, sampleRate) {
    let totalLength = 0;
    for (const chunk of chunks) {
        totalLength += chunk.length;
    }

    const merged = new Float32Array(totalLength);
    let offset = 0;
    for (const chunk of chunks) {
        merged.set(chunk, offset);
        offset += chunk.length;
    }

    // Convert to 16-bit PCM WAV
    const buffer = new ArrayBuffer(44 + merged.length * 2);
    const view = new DataView(buffer);

    function writeString(v, off, str) {
        for (let i = 0; i < str.length; i++) {
            v.setUint8(off + i, str.charCodeAt(i));
        }
    }

    // RIFF header
    writeString(view, 0, 'RIFF');
    view.setUint32(4, 36 + merged.length * 2, true);
    writeString(view, 8, 'WAVE');

    // fmt sub-chunk
    writeString(view, 12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true); // PCM
    view.setUint16(22, 1, true); // Mono
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true); // byte rate
    view.setUint16(32, 2, true); // block align
    view.setUint16(34, 16, true); // bits per sample

    // data sub-chunk
    writeString(view, 36, 'data');
    view.setUint32(40, merged.length * 2, true);

    // PCM samples
    let index = 44;
    for (let i = 0; i < merged.length; i++) {
        const s = Math.max(-1, Math.min(1, merged[i]));
        view.setInt16(index, s < 0 ? s * 0x8000 : s * 0x7fff, true);
        index += 2;
    }

    return new Blob([buffer], { type: 'audio/wav' });
}

async function playRawPCMStreamChunk(arrayBufferData) {
    if (!playbackAudioContext) {
        playbackAudioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 22050 });
    }

    const int16Array = new Int16Array(arrayBufferData);
    if (int16Array.length === 0) return;

    const float32Samples = new Float32Array(int16Array.length);
    for (let i = 0; i < int16Array.length; i++) {
        float32Samples[i] = int16Array[i] / 32768.0;
    }

    const audioBuffer = playbackAudioContext.createBuffer(1, float32Samples.length, 22050);
    audioBuffer.getChannelData(0).set(float32Samples);

    const source = playbackAudioContext.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(playbackAudioContext.destination);

    const currentTime = playbackAudioContext.currentTime;
    if (nextPlayTime < currentTime) {
        nextPlayTime = currentTime + 0.05;
    }

    isAudioCurrentlyPlaying = true;
    statusText.innerText = "AI Speaking...";

    source.start(nextPlayTime);
    nextPlayTime += audioBuffer.duration;

    source.onended = () => {
        if (playbackAudioContext && playbackAudioContext.currentTime >= nextPlayTime - 0.02) {
            isAudioCurrentlyPlaying = false;
            lastPlaybackEndTime = Date.now();
            resetToListeningState();
        }
    };
}

async function executeNetworkPayloadSend(audioBlob) {
    const formData = new FormData();
    formData.append('file', audioBlob, 'mic.wav');

    isProcessingNetwork = true;
    cancelBtn.style.display = "block";
    statusText.innerText = "AI is thinking...";
    currentAiMessageBubble = null;

    currentFetchAbortController = new AbortController();
    const signal = currentFetchAbortController.signal;
    const targetUrl = `${window.location.protocol}//${window.location.hostname}:${window.location.port || 8000}/chat`;

    try {
        const response = await fetch(targetUrl, {
            method: 'POST',
            body: formData,
            signal: signal
        });

        if (!response.ok) throw new Error("Server transmission error");

        const reader = response.body.getReader();
        nextPlayTime = 0;
        let leftoverBuffer = new Uint8Array(0);

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            let combined = new Uint8Array(leftoverBuffer.length + value.length);
            combined.set(leftoverBuffer);
            combined.set(value, leftoverBuffer.length);

            let offset = 0;
            while (offset < combined.length) {
                if (offset + 6 <= combined.length) {
                    const header = String.fromCharCode(...combined.slice(offset, offset + 6));

                    if (header.startsWith("TEXT:")) {
                        let newlineIndex = -1;
                        for (let i = offset; i < combined.length; i++) {
                            if (combined[i] === 10) {
                                newlineIndex = i;
                                break;
                            }
                        }

                        if (newlineIndex !== -1) {
                            const lineBytes = combined.slice(offset + 5, newlineIndex);
                            const textLine = new TextDecoder().decode(lineBytes);

                            if (textLine.startsWith("USER:")) {
                                appendMessage(textLine.replace("USER:", ""), true);
                            } else if (textLine.startsWith("AI_TOKEN:")) {
                                const token = textLine.replace("AI_TOKEN:", "");
                                if (!currentAiMessageBubble) {
                                    currentAiMessageBubble = appendMessage("", false);
                                }
                                currentAiMessageBubble.innerText += token;
                                chatLog.scrollTop = chatLog.scrollHeight;
                            }

                            offset = newlineIndex + 1;
                            continue;
                        } else {
                            break;
                        }
                    } else if (header === "AUDIO:") {
                        if (offset + 10 <= combined.length) {
                            const lengthBytes = combined.slice(offset + 6, offset + 10);
                            const view = new DataView(lengthBytes.buffer, lengthBytes.byteOffset, lengthBytes.byteLength);
                            const payloadSize = view.getUint32(0, false);

                            if (offset + 10 + payloadSize <= combined.length) {
                                const audioBytes = combined.slice(offset + 10, offset + 10 + payloadSize);
                                await playRawPCMStreamChunk(audioBytes.buffer);
                                offset += 10 + payloadSize;
                                continue;
                            } else {
                                break;
                            }
                        } else {
                            break;
                        }
                    } else {
                        offset++;
                    }
                } else {
                    break;
                }
            }
            leftoverBuffer = combined.slice(offset);
        }

    } catch (err) {
        console.error(err);
        if (err.name === 'AbortError') {
            statusText.innerText = "Canceled.";
        } else {
            statusText.innerText = "Connection lost.";
        }
    } finally {
        isProcessingNetwork = false;
        currentFetchAbortController = null;
        if (!isAudioCurrentlyPlaying) {
            lastPlaybackEndTime = Date.now();
            resetToListeningState();
        }
    }
}

function resetToListeningState() {
    cancelBtn.style.display = "none";
    if (isSessionActive && !isAudioCurrentlyPlaying && !isProcessingNetwork) {
        statusText.innerText = "Waiting for you to speak...";
        actionBtn.innerText = "Hands-Free Listening Active";
        actionBtn.classList.remove('recording');
    }
}

async function startHandsFreeSession() {
    statusText.innerText = "Waking audio systems...";

    globalStream = await navigator.mediaDevices.getUserMedia({
        audio: {
            channelCount: 1,
            sampleRate: SAMPLE_RATE,
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true
        }
    });

    vadAudioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: SAMPLE_RATE });
    const source = vadAudioContext.createMediaStreamSource(globalStream);

    vadAnalyser = vadAudioContext.createAnalyser();
    vadAnalyser.fftSize = 512;

    vadGainNode = vadAudioContext.createGain();
    vadGainNode.gain.value = 0; // Mute input to prevent feedback loop to speakers

    preRollChunks = [];
    recordedChunks = [];
    isUtteranceActive = false;

    // Use modern AudioWorklet if supported, else ScriptProcessor fallback
    let workletInitialized = false;
    if (vadAudioContext.audioWorklet) {
        try {
            const workletCode = `
                class AudioRecorderProcessor extends AudioWorkletProcessor {
                    process(inputs) {
                        const input = inputs[0];
                        if (input && input[0] && input[0].length > 0) {
                            this.port.postMessage(input[0]);
                        }
                        return true;
                    }
                }
                registerProcessor('audio-recorder-processor', AudioRecorderProcessor);
            `;
            const blob = new Blob([workletCode], { type: 'application/javascript' });
            const workletUrl = URL.createObjectURL(blob);
            await vadAudioContext.audioWorklet.addModule(workletUrl);
            URL.revokeObjectURL(workletUrl);

            vadWorkletNode = new AudioWorkletNode(vadAudioContext, 'audio-recorder-processor');
            vadWorkletNode.port.onmessage = (e) => {
                handleAudioFrame(e.data);
            };

            source.connect(vadAnalyser);
            vadAnalyser.connect(vadWorkletNode);
            vadWorkletNode.connect(vadGainNode);
            vadGainNode.connect(vadAudioContext.destination);

            workletInitialized = true;
        } catch (e) {
            console.warn("AudioWorklet setup failed, using ScriptProcessor fallback:", e);
        }
    }

    if (!workletInitialized) {
        // Fallback for environments where AudioWorklet is blocked
        vadScriptProcessor = vadAudioContext.createScriptProcessor(512, 1, 1);
        vadScriptProcessor.onaudioprocess = (e) => {
            const input = e.inputBuffer.getChannelData(0);
            handleAudioFrame(input);
        };

        source.connect(vadAnalyser);
        vadAnalyser.connect(vadScriptProcessor);
        vadScriptProcessor.connect(vadGainNode);
        vadGainNode.connect(vadAudioContext.destination);
    }

    isSessionActive = true;
    resetToListeningState();
}

function stopHandsFreeSession() {
    isSessionActive = false;
    isUtteranceActive = false;
    isProcessingNetwork = false;
    isAudioCurrentlyPlaying = false;
    if (silenceTimer) {
        clearTimeout(silenceTimer);
        silenceTimer = null;
    }

    if (currentFetchAbortController) currentFetchAbortController.abort();

    if (vadWorkletNode) {
        vadWorkletNode.port.onmessage = null;
        vadWorkletNode.disconnect();
        vadWorkletNode = null;
    }
    if (vadScriptProcessor) {
        vadScriptProcessor.onaudioprocess = null;
        vadScriptProcessor.disconnect();
        vadScriptProcessor = null;
    }
    if (vadGainNode) {
        vadGainNode.disconnect();
        vadGainNode = null;
    }
    if (vadAnalyser) {
        vadAnalyser.disconnect();
        vadAnalyser = null;
    }
    if (globalStream) {
        globalStream.getTracks().forEach(track => track.stop());
        globalStream = null;
    }
    if (vadAudioContext && vadAudioContext.state !== 'closed') {
        vadAudioContext.close();
        vadAudioContext = null;
    }

    if (playbackAudioContext && playbackAudioContext.state !== 'closed') {
        playbackAudioContext.close();
        playbackAudioContext = null;
    }

    actionBtn.classList.remove('recording');
    actionBtn.innerText = "Start Hands-Free Session";
    cancelBtn.style.display = "none";
    vumeter.style.width = "0%";
    vumeter.classList.remove('talking');
    statusText.innerText = "Session turned off.";
}

actionBtn.addEventListener('click', (e) => {
    e.preventDefault();
    if (!isSessionActive) {
        startHandsFreeSession().catch(err => {
            console.error(err);
            statusText.innerText = "Permissions blocked.";
        });
    } else {
        stopHandsFreeSession();
    }
});

cancelBtn.addEventListener('click', () => {
    interruptPlayback();
    isUtteranceActive = false;
    recordedChunks = [];
    resetToListeningState();
});