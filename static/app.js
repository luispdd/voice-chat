const actionBtn = document.getElementById('actionBtn');
const cancelBtn = document.getElementById('cancelBtn');
const statusText = document.getElementById('status');
const metricsDiv = document.getElementById('metrics');
const vumeter = document.getElementById('vumeter');
const audioPlayback = document.getElementById('audioPlayback');
const chatLog = document.getElementById('chatLog');

let mediaRecorder = null;
let audioChunks = [];
let globalStream = null;

// VAD State Elements
let isSessionActive = false;       // Master lock tracking if assistant engine is "Awake"
let isRecordingActive = false;     // Tracks if a voice packet is actively streaming to disk
let isProcessingNetwork = false;   // Network lock
let currentFetchAbortController = null;

// Web Audio API Analytics Anchors
let vadAudioContext = null;
let vadAnalyser = null;
let vadAnimationFrameId = null;

// VAD Variable Calibration Constants 
const VOLUME_THRESHOLD = 35;       // Sensitivity floor (lower numbers = more sensitive mic)
const SILENCE_DURATION_MS = 1500;  // Required silence (in ms) to trigger automatic send
let speechEndTimestamp = null;     // Tracks exact moment volume dipped below floor limit

actionBtn.innerText = "Start Hands-Free Session";

function appendMessage(text, isUser, timerText = "") {
    const msgDiv = document.createElement('div');
    msgDiv.classList.add('msg', isUser ? 'user-msg' : 'ai-msg');
    
    if (isUser || !timerText) {
        msgDiv.innerText = text;
    } else {
        const textNode = document.createElement('div');
        textNode.innerText = text;
        msgDiv.appendChild(textNode);
        
        const timeNode = document.createElement('div');
        timeNode.classList.add('msg-timer');
        timeNode.innerText = timerText;
        msgDiv.appendChild(timeNode);
    }
    
    chatLog.appendChild(msgDiv);
    chatLog.scrollTop = chatLog.scrollHeight;
}

function b64toBlob(b64Data, contentType='', sliceSize=512) {
    const byteCharacters = atob(b64Data);
    const byteArrays = [];
    for (let offset = 0; offset < byteCharacters.length; offset += sliceSize) {
        const slice = byteCharacters.slice(offset, offset + sliceSize);
        const byteNumbers = new Array(slice.length);
        for (let i = 0; i < slice.length; i++) {
            byteNumbers[i] = slice.charCodeAt(i);
        }
        const byteArray = new Uint8Array(byteNumbers);
        byteArrays.push(byteArray);
    }
    return new Blob(byteArrays, {type: contentType});
}

function getSupportedMimeType() {
    const types = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4', 'audio/aac'];
    for (const type of types) {
        if (MediaRecorder.isTypeSupported(type)) return type;
    }
    return '';
}

// Master loop running 60fps to track your voice volume envelope
function processAudioMonitorLoop() {
    if (!isSessionActive) return;

    const dataArray = new Uint8Array(vadAnalyser.frequencyBinCount);
    vadAnalyser.getByteFrequencyData(dataArray);

    // Compute simple average amplitude from spectrum array
    let sum = 0;
    for (let i = 0; i < dataArray.length; i++) {
        sum += dataArray[i];
    }
    const currentVolume = sum / dataArray.length;

    // Visual Meter UI scaling adjustment
    const meterPercent = Math.min(100, (currentVolume / 120) * 100);
    vumeter.style.width = `${meterPercent}%`;

    // --- VAD DECISION ROUTINE ENGINE ---
    // Rule A: If AI is talking or thinking, ignore all room noise inputs
    if (isProcessingNetwork || !audioPlayback.paused) {
        vumeter.classList.remove('talking');
        speechEndTimestamp = null;
        vadAnimationFrameId = requestAnimationFrame(processAudioMonitorLoop);
        return;
    }

    if (currentVolume > VOLUME_THRESHOLD) {
        // Voice Detected! 
        vumeter.classList.add('talking');
        speechEndTimestamp = null; // Clear out old silence memory counters

        if (!isRecordingActive) {
            triggerRecordingStart();
        }
    } else {
        // Room Silence Detected
        vumeter.classList.remove('talking');

        if (isRecordingActive) {
            // Anchor timestamp tracking precisely when the silence began
            if (!speechEndTimestamp) {
                speechEndTimestamp = Date.now();
            }

            // Check if silence has endured longer than our calibration constraint limit
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
    
    statusText.innerText = "Processing automated turn submission...";
    actionBtn.innerText = "Processing...";
    actionBtn.classList.remove('recording');

    if (mediaRecorder && mediaRecorder.state !== "inactive") {
        mediaRecorder.stop();
    }
}

function executeNetworkPayloadSend() {
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

    currentFetchAbortController = new AbortController();
    const signal = currentFetchAbortController.signal;

    const targetUrl = `${window.location.protocol}//${window.location.hostname}:8000/chat`;
    const startCheckpoint = performance.now();

    fetch(targetUrl, {
        method: 'POST',
        body: formData,
        signal: signal
    })
    .then(response => response.json())
    .then(data => {
        const textCheckpoint = performance.now();
        const serverRoundTripLapse = ((textCheckpoint - startCheckpoint) / 1000).toFixed(2);

        isProcessingNetwork = false;
        currentFetchAbortController = null;
        
        appendMessage(data.user_text, true);

        if (data.audio_base64) {
            statusText.innerText = "Speaking...";
            const audioBlobPlayback = b64toBlob(data.audio_base64, 'audio/wav');
            const audioUrl = URL.createObjectURL(audioBlobPlayback);
            audioPlayback.src = audioUrl;
            
            const playCheckpoint = performance.now();
            const clientPlaybackLapse = (playCheckpoint - textCheckpoint).toFixed(1);
            const telemetryString = `STT + LLM: ${serverRoundTripLapse}s | TTS Setup: ${clientPlaybackLapse}ms`;
            
            appendMessage(data.ai_text, false, telemetryString);
            metricsDiv.innerHTML = `STT + LLM: <span>${serverRoundTripLapse}s</span> | TTS Setup: <span>${clientPlaybackLapse}ms</span>`;
            
            audioPlayback.play();
        } else {
            cancelBtn.style.display = "none";
            const telemetryString = `Server Processing: ${serverRoundTripLapse}s`;
            appendMessage(data.ai_text, false, telemetryString);
            metricsDiv.innerHTML = `Server Processing: <span>${serverRoundTripLapse}s</span>`;
            resetToListeningState();
        }
    })
    .catch(err => {
        isProcessingNetwork = false;
        currentFetchAbortController = null;
        metricsDiv.innerHTML = "";
        if (err.name === 'AbortError') {
            statusText.innerText = "Canceled.";
        } else {
            console.error(err);
            statusText.innerText = "Communication failure.";
        }
        resetToListeningState();
    });
}

function resetToListeningState() {
    cancelBtn.style.display = "none";
    if (isSessionActive) {
        statusText.innerText = "Waiting for you to speak...";
        actionBtn.innerText = "Hands-Free Listening Active";
        actionBtn.classList.remove('recording');
    }
}

// Automatically bind the cleanup hook to reset listeners when AI voice narration runs dry
audioPlayback.addEventListener('ended', () => {
    resetToListeningState();
});

async function startHandsFreeSession() {
    metricsDiv.innerHTML = "";
    statusText.innerText = "Waking audio systems...";

    globalStream = await navigator.mediaDevices.getUserMedia({ 
        audio: { channelCount: 1, sampleRate: 16000, echoCancellation: true, noiseSuppression: true } 
    });

    // Create standard monitoring nodes
    vadAudioContext = new (window.AudioContext || window.webkitAudioContext)();
    const source = vadAudioContext.createMediaStreamSource(globalStream);
    vadAnalyser = vadAudioContext.createAnalyser();
    vadAnalyser.fftSize = 256; // High frequency, light frame analytical slices
    source.connect(vadAnalyser);

    isSessionActive = true;
    resetToListeningState();
    processAudioMonitorLoop(); // Kickoff loop
}

function stopHandsFreeSession() {
    isSessionActive = false;
    isRecordingActive = false;
    isProcessingNetwork = false;
    speechEndTimestamp = null;

    if (currentFetchAbortController) currentFetchAbortController.abort();
    if (vadAnimationFrameId) cancelAnimationFrame(vadAnimationFrameId);
    
    if (mediaRecorder && mediaRecorder.state !== "inactive") mediaRecorder.stop();
    if (globalStream) globalStream.getTracks().forEach(track => track.stop());
    if (vadAudioContext) vadAudioContext.close();

    audioPlayback.pause();
    audioPlayback.src = "";

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
    audioPlayback.pause();
    audioPlayback.src = "";
    isProcessingNetwork = false;
    isRecordingActive = false;
    audioChunks = [];
    resetToListeningState();
});