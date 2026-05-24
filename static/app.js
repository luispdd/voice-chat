const actionBtn = document.getElementById('actionBtn');
const cancelBtn = document.getElementById('cancelBtn');
const statusText = document.getElementById('status');
const metricsDiv = document.getElementById('metrics');
const audioPlayback = document.getElementById('audioPlayback');
const chatLog = document.getElementById('chatLog');

let mediaRecorder = null; // Replaced script arrays with the hardware component link
let audioChunks = [];
let globalStream = null;
let isRecording = false;
let isProcessingNetwork = false;
let currentFetchAbortController = null;

actionBtn.innerText = "Click to Record";

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

// Function helper to dynamically choose whatever container compression format this browser supports
function getSupportedMimeType() {
    const types = [
        'audio/webm;codecs=opus',
        'audio/webm',
        'audio/ogg;codecs=opus',
        'audio/mp4',
        'audio/aac'
    ];
    for (const type of types) {
        if (MediaRecorder.isTypeSupported(type)) {
            return type;
        }
    }
    return ''; // Fallback to browser standard configuration selection
}

async function startRecording() {
    if (isProcessingNetwork) return;
    
    audioChunks = []; // Clear array of compressed packets
    cancelBtn.style.display = "none";
    metricsDiv.innerHTML = ""; 
    audioPlayback.pause();
    audioPlayback.src = "";
    
    globalStream = await navigator.mediaDevices.getUserMedia({ 
        audio: { 
            channelCount: 1, 
            sampleRate: 16000,
            echoCancellation: true,
            noiseSuppression: true
        } 
    });
    
    // Instantiating the browser native recording implementation
    const options = { mimeType: getSupportedMimeType() };
    mediaRecorder = new MediaRecorder(globalStream, options);
    
    mediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
            audioChunks.push(e.data);
        }
    };

    // When the recorder stops, it instantly ships data over the network
    mediaRecorder.onstop = () => {
        executeNetworkPayloadSend();
    };

    // Collect chunks dynamically every 250ms
    mediaRecorder.start(250);

    isRecording = true;
    actionBtn.classList.add('recording');
    actionBtn.innerText = "Stop Recording";
    statusText.innerText = "Listening (Hardware Compressed)...";
}

function stopRecording() {
    if (!isRecording) return;
    isRecording = false;

    actionBtn.classList.remove('recording');
    actionBtn.innerText = "Processing...";
    statusText.innerText = "Transcoding audio...";
    
    isProcessingNetwork = true;
    cancelBtn.style.display = "block";

    // Forces mediaRecorder to gather final data slices and fire its onstop() loop hook
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
        mediaRecorder.stop();
    }
    
    if (globalStream) {
        globalStream.getTracks().forEach(track => track.stop());
    }
}

function executeNetworkPayloadSend() {
    // Pack all compressed slices into a uniform data blob file payload assignment
    const audioBlob = new Blob(audioChunks, { type: mediaRecorder.mimeType });
    audioChunks = [];

    const formData = new FormData();
    formData.append('file', audioBlob, 'input_compressed');

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
        actionBtn.innerText = "Click to Record";
        statusText.innerText = "Ready";
        
        appendMessage(data.user_text, true);
        
        if (data.audio_base64) {
            statusText.innerText = "Speaking...";
            const audioBlobPlayback = b64toBlob(data.audio_base64, 'audio/wav');
            const audioUrl = URL.createObjectURL(audioBlobPlayback);
            audioPlayback.src = audioUrl;
            audioPlayback.play();

            const playCheckpoint = performance.now();
            const clientPlaybackLapse = (playCheckpoint - textCheckpoint).toFixed(1);

            const telemetryString = `STT + LLM: ${serverRoundTripLapse}s | TTS Setup: ${clientPlaybackLapse}ms`;
            appendMessage(data.ai_text, false, telemetryString);
            metricsDiv.innerHTML = `STT + LLM: <span>${serverRoundTripLapse}s</span> | TTS Setup: <span>${clientPlaybackLapse}ms</span>`;
        } else {
            cancelBtn.style.display = "none";
            const telemetryString = `Server Processing: ${serverRoundTripLapse}s`;
            appendMessage(data.ai_text, false, telemetryString);
            metricsDiv.innerHTML = `Server Processing: <span>${serverRoundTripLapse}s</span>`;
        }
    })
    .catch(err => {
        isProcessingNetwork = false;
        actionBtn.innerText = "Click to Record";
        cancelBtn.style.display = "none";
        metricsDiv.innerHTML = "";
        if (err.name === 'AbortError') {
            statusText.innerText = "Canceled. Ready.";
        } else {
            console.error(err);
            statusText.innerText = "Server communication failure.";
        }
    });
}

function handleCancelation() {
    if (currentFetchAbortController) {
        currentFetchAbortController.abort();
        currentFetchAbortController = null;
    }
    
    audioPlayback.pause();
    audioPlayback.src = "";
    
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
        mediaRecorder.stop();
    }
    if (globalStream) {
        globalStream.getTracks().forEach(track => track.stop());
    }
    
    isProcessingNetwork = false;
    isRecording = false;
    audioChunks = [];
    
    actionBtn.classList.remove('recording');
    actionBtn.innerText = "Click to Record";
    cancelBtn.style.display = "none";
    metricsDiv.innerHTML = "";
    statusText.innerText = "Canceled successfully. Ready.";
}

audioPlayback.addEventListener('ended', () => {
    cancelBtn.style.display = "none";
    statusText.innerText = "Ready";
});

async function handleButtonClick(e) {
    e.preventDefault();
    if (isProcessingNetwork) return;
    
    if (!isRecording) {
        statusText.innerText = "Connecting microphone...";
        try {
            await startRecording();
        } catch (err) {
            console.error(err);
            statusText.innerText = "Microphone connection blocked.";
        }
    } else {
        stopRecording();
    }
}

actionBtn.addEventListener('click', handleButtonClick);
cancelBtn.addEventListener('click', handleCancelation);