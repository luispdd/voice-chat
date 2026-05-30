const actionBtn = document.getElementById('actionBtn');
const cancelBtn = document.getElementById('cancelBtn');
const statusText = document.getElementById('status');
const metricsDiv = document.getElementById('metrics');
const vumeter = document.getElementById('vumeter');
const chatLog = document.getElementById('chatLog');

let mediaRecorder = null;
let audioChunks = [];
let globalStream = null;

// VAD State Elements
let isSessionActive = false;       
let isRecordingActive = false;     
let isProcessingNetwork = false;   
let currentFetchAbortController = null;

// Audio Monitor Anchors
let vadAudioContext = null;
let vadAnalyser = null;
let vadAnimationFrameId = null;

// Calibration Constraints 
const VOLUME_THRESHOLD = 35;       
const SILENCE_DURATION_MS = 1500;  
let speechEndTimestamp = null;     

// Stream Playback Engine
let playbackAudioContext = null;
let nextPlayTime = 0; 
let isAudioCurrentlyPlaying = false; 

// Tracks UI elements across stream cycles
let currentAiMessageBubble = null;

function appendMessage(text, isUser) {
    const msgDiv = document.createElement('div');
    msgDiv.classList.add('msg', isUser ? 'user-msg' : 'ai-msg');
    msgDiv.innerText = text;
    chatLog.appendChild(msgDiv);
    chatLog.scrollTop = chatLog.scrollHeight;
    return msgDiv;
}

function getSupportedMimeType() {
    const types = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4', 'audio/aac'];
    for (const type of types) {
        if (MediaRecorder.isTypeSupported(type)) return type;
    }
    return '';
}

function processAudioMonitorLoop() {
    if (!isSessionActive) return;

    const dataArray = new Uint8Array(vadAnalyser.frequencyBinCount);
    vadAnalyser.getByteFrequencyData(dataArray);

    let sum = 0;
    for (let i = 0; i < dataArray.length; i++) { sum += dataArray[i]; }
    const currentVolume = sum / dataArray.length;

    const meterPercent = Math.min(100, (currentVolume / 120) * 100);
    vumeter.style.width = `${meterPercent}%`;

    if (isProcessingNetwork || isAudioCurrentlyPlaying) {
        vumeter.classList.remove('talking');
        speechEndTimestamp = null;
        vadAnimationFrameId = requestAnimationFrame(processAudioMonitorLoop);
        return;
    }

    if (currentVolume > VOLUME_THRESHOLD) {
        vumeter.classList.add('talking');
        speechEndTimestamp = null; 

        if (!isRecordingActive) {
            triggerRecordingStart();
        }
    } else {
        vumeter.classList.remove('talking');

        if (isRecordingActive) {
            if (!speechEndTimestamp) { speechEndTimestamp = Date.now(); }

            const elapsedSilence = Date.now() - speechEndTimestamp;
            if (elapsedSilence >= SILENCE_DURATION_MS) {
                triggerRecordingStop();
            }
        }
    }

    vadAnimationFrameId = requestAnimationFrame(processAudioMonitorLoop);
}

async function triggerRecordingStart() {
    isRecordingActive = true;
    audioChunks = [];
    statusText.innerText = "Listening...";
    actionBtn.innerText = "Listening...";
    actionBtn.classList.add('recording');

    const options = { mimeType: getSupportedMimeType() };
    mediaRecorder = new MediaRecorder(globalStream, options);
    
    mediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) audioChunks.push(e.data);
    };
    
    mediaRecorder.onstop = () => {
        executeNetworkPayloadSend();
    };

    mediaRecorder.start(250);
}

function triggerRecordingStop() {
    isRecordingActive = false;
    speechEndTimestamp = null;
    statusText.innerText = "Processing...";
    actionBtn.innerText = "Processing...";
    actionBtn.classList.remove('recording');

    if (mediaRecorder && mediaRecorder.state !== "inactive") {
        mediaRecorder.stop();
    }
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
            resetToListeningState();
        }
    };
}

async function executeNetworkPayloadSend() {
    if (audioChunks.length === 0) {
        resetToListeningState();
        return;
    }

    const audioBlob = new Blob(audioChunks, { type: mediaRecorder.mimeType });
    audioChunks = [];

    const formData = new FormData();
    formData.append('file', audioBlob, 'input_compressed');

    isProcessingNetwork = true;
    cancelBtn.style.display = "block";
    statusText.innerText = "AI is thinking...";
    currentAiMessageBubble = null;

    currentFetchAbortController = new AbortController();
    const signal = currentFetchAbortController.signal;
    const targetUrl = `${window.location.protocol}//${window.location.hostname}:8000/chat`;

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
            
            // Combine new data chunk with any leftover bytes from the previous read
            let combined = new Uint8Array(leftoverBuffer.length + value.length);
            combined.set(leftoverBuffer);
            combined.set(value, leftoverBuffer.length);
            
            let offset = 0;
            while (offset < combined.length) {
                // Peek ahead to check what type of package has arrived
                if (offset + 5 <= combined.length) {
                    const header = String.fromCharCode(...combined.slice(offset, offset + 5));
                    
                    if (header === "TEXT:") {
                        // Text packets are terminated by a newline character (\n)
                        let newlineIndex = -1;
                        for (let i = offset; i < combined.length; i++) {
                            if (combined[i] === 10) { // 10 is the ASCII code for \n
                                newlineIndex = i;
                                break;
                            }
                        }
                        
                        if (newlineIndex !== -1) {
                            const lineBytes = combined.slice(offset + 5, newlineIndex);
                            const textLine = new TextDecoder().decode(lineBytes);
                            
                            // Route the text based on its internal target subheader string
                            if (textLine.startsWith("USER:")) {
                                appendMessage(textLine.replace("USER:", ""), true);
                            } else if (textLine.startsWith("AI_TOKEN:")) {
                                const token = textLine.replace("AI_TOKEN:", "");
                                if (!currentAiMessageBubble) {
                                    currentAiMessageBubble = appendMessage("", false);
                                }
                                currentAiMessageBubble.innerText += token;
                                chatLog.scrollTop = chatLog.scrollHeight;
                            } else if (textLine.startsWith("AI:")) {
                                appendMessage(textLine.replace("AI:", ""), false);
                            }
                            
                            offset = newlineIndex + 1;
                            continue;
                        } else {
                            // Incomplete line, break out and wait for more data to arrive
                            break;
                        }
                    } else if (header === "AUDIO") {
                        // Ensure we have the full 6-byte "AUDIO:" tag prefix before reading data
                        if (offset + 6 <= combined.length) {
                            // Process audio payload frames in efficient 1024-byte chunks
                            const payloadSize = 1024;
                            if (offset + 6 + payloadSize <= combined.length) {
                                const audioBytes = combined.slice(offset + 6, offset + 6 + payloadSize);
                                await playRawPCMStreamChunk(audioBytes.buffer);
                                offset += 6 + payloadSize;
                                continue;
                            } else {
                                break;
                            }
                        } else {
                            break;
                        }
                    } else {
                        // Fallback fallback handler if bytes get unaligned
                        offset++;
                    }
                } else {
                    break;
                }
            }
            // Retain unparsed stream remainders for the next reader cycle
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
    metricsDiv.innerHTML = "";
    statusText.innerText = "Waking audio systems...";

    globalStream = await navigator.mediaDevices.getUserMedia({ 
        audio: { channelCount: 1, sampleRate: 16000, echoCancellation: true, noiseSuppression: true } 
    });

    vadAudioContext = new (window.AudioContext || window.webkitAudioContext)();
    const source = vadAudioContext.createMediaStreamSource(globalStream);
    vadAnalyser = vadAudioContext.createAnalyser();
    vadAnalyser.fftSize = 256; 
    source.connect(vadAnalyser);

    isSessionActive = true;
    resetToListeningState();
    processAudioMonitorLoop(); 
}

function stopHandsFreeSession() {
    isSessionActive = false;
    isRecordingActive = false;
    isProcessingNetwork = false;
    isAudioCurrentlyPlaying = false;
    speechEndTimestamp = null;

    if (currentFetchAbortController) currentFetchAbortController.abort();
    if (vadAnimationFrameId) cancelAnimationFrame(vadAnimationFrameId);
    
    if (mediaRecorder && mediaRecorder.state !== "inactive") mediaRecorder.stop();
    if (globalStream) globalStream.getTracks().forEach(track => track.stop());
    if (vadAudioContext) vadAudioContext.close();
    
    if (playbackAudioContext) {
        playbackAudioContext.close();
        playbackAudioContext = null;
    }

    actionBtn.classList.remove('recording');
    actionBtn.innerText = "Start Hands-Free Session";
    cancelBtn.style.display = "none";
    vumeter.style.width = "0%";
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
    if (currentFetchAbortController) currentFetchAbortController.abort();
    if (playbackAudioContext) {
        playbackAudioContext.close();
        playbackAudioContext = null;
    }
    isAudioCurrentlyPlaying = false;
    isProcessingNetwork = false;
    isRecordingActive = false;
    audioChunks = [];
    resetToListeningState();
});