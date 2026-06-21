import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import PyPDF2
import docx
import re
import requests

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-large-latest")

# ─────────────────────────────────────────────
# MISTRAL API HANDLER
# ─────────────────────────────────────────────
def call_mistral_api(messages):
    if not MISTRAL_API_KEY:
        raise Exception("MISTRAL_API_KEY tidak ditemukan di file .env")
        
    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    payload = {
        "model": MISTRAL_MODEL,
        "messages": messages,
        "temperature": 0.6,
        "max_tokens": 850 # Increased limit to support both chat reply and generated document output
    }
    
    response = requests.post(url, headers=headers, json=payload, timeout=90)
    
    if response.status_code == 200:
        data = response.json()
        return data["choices"][0]["message"]["content"]
    else:
        raise Exception(f"Mistral API Error: {response.status_code} - {response.text}")


def is_response_complete(text):
    text = text.strip()
    if not text:
        return False
    if text.endswith('...') or text.endswith('..'):
        return False
    if re.search(r'[.?!]["\']?$|[.?!]\s*$', text):
        return True
    return False


def get_complete_response(messages):
    response = call_mistral_api(messages)
    if is_response_complete(response):
        return response.strip()

    continuation_prompt = (
        "Continue the previous answer from where it left off and finish the response in the same language. "
        "Do not repeat content already provided; only continue and complete the last sentence cleanly. "
        "If the response was truncated because of the token limit, finish the thought with a complete sentence."
    )

    history = messages.copy()
    history.append({"role": "assistant", "content": response})
    history.append({"role": "user", "content": continuation_prompt})
    continuation = call_mistral_api(history)
    combined = response.rstrip() + "\n" + continuation.strip()

    if is_response_complete(combined):
        return combined.strip()

    # One more chance to finish cleanly if still incomplete
    final_prompt = (
        "The previous response is still incomplete. Finish the answer fully in the same language, "
        "without repeating what has already been said."
    )
    history.append({"role": "assistant", "content": continuation})
    history.append({"role": "user", "content": final_prompt})
    final_continuation = call_mistral_api(history)
    return (combined.rstrip() + "\n" + final_continuation.strip()).strip()


def parse_json_from_text(text):
    if not text:
        return None
    # Try to find the first JSON object in the text
    try:
        # Direct parse first
        obj = json.loads(text)
        return obj
    except Exception:
        pass

    m = re.search(r'\{.*\}', text, re.S)
    if m:
        candidate = m.group(0)
        try:
            obj = json.loads(candidate)
            return obj
        except Exception:
            return None

    return None


def get_structured_response(messages, max_retries=2):
    # Get initial response (may be long or complete)
    raw = get_complete_response(messages)
    parsed = parse_json_from_text(raw)
    if parsed and 'chat_reply' in parsed and 'document_output' in parsed:
        return parsed

    # Ask the model to reformat strictly as JSON
    reform_instruction = {
        "role": "user",
        "content": "Please reformat your previous response EXACTLY as pure JSON with two keys: 'chat_reply' (max 2-3 sentences) and 'document_output' (markdown string or empty). Return only the JSON object with no additional text or backticks."
    }

    history = messages.copy()
    history.append({"role": "assistant", "content": raw})
    history.append(reform_instruction)

    for attempt in range(max_retries):
        try:
            resp = call_mistral_api(history)
        except Exception:
            resp = ''
        parsed = parse_json_from_text(resp)
        if parsed and 'chat_reply' in parsed and 'document_output' in parsed:
            return parsed

        # prepare next retry
        history.append({"role": "assistant", "content": resp})
        history.append(reform_instruction)

    # Fallback: synthesize minimal JSON
    assistant_excerpt = raw.strip().split('\n', 1)[0]
    return {"chat_reply": assistant_excerpt[:400], "document_output": raw}


def split_assistant_and_generated(response_text):
    marker = '--- GENERATED DOCUMENT ---'
    if marker in response_text:
        assistant_part, generated_part = response_text.split(marker, 1)
        assistant_text = re.sub(r'(?i)^assistant reply:\s*', '', assistant_part.strip()).strip()
        generated_text = re.sub(r'(?i)^generated document output:\s*', '', generated_part.strip()).strip()
        return assistant_text or 'Saya telah menyiapkan hasilnya. Lihat panel kanan untuk dokumen lengkap.', generated_text or response_text.strip()

    sentences = re.split(r'(?<=[.?!])\s+', response_text.strip(), maxsplit=1)
    if len(sentences) > 1:
        assistant_text = sentences[0].strip()
        return assistant_text, response_text.strip()

    return response_text.strip(), response_text.strip()

# ─────────────────────────────────────────────
# UTILS: EKSTRAK TEKS DOKUMEN
# ─────────────────────────────────────────────
def extract_text_from_file(file):
    filename = secure_filename(file.filename).lower()
    text = ""
    
    try:
        if filename.endswith('.pdf'):
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
        elif filename.endswith('.docx'):
            doc = docx.Document(file)
            for para in doc.paragraphs:
                text += para.text + "\n"
        elif filename.endswith('.txt'):
            text = file.read().decode('utf-8')
        else:
            return None, "Format file tidak didukung. Gunakan PDF, DOCX, atau TXT."
    except Exception as e:
        return None, f"Gagal membaca file: {str(e)}"
        
    return text, None

# ─────────────────────────────────────────────
# SESSION MANAGER (Menyimpan Konteks Chat)
# ─────────────────────────────────────────────
class ChatSession:
    def __init__(self):
        self.sessions = {}
        self.system_prompt = {
            "role": "system",
            "content": (
                "You are a professional, meticulous, and solution-oriented AI Document Reviewer. "
                "English is the primary language, but if the user writes in Indonesian or Malay, answer in that same language. "
                "If the user writes in any other language, respond in English. "
                "Your main task is to analyse documents uploaded by users based on the instructions (prompts) they provide. "
                "For complex requests regarding document deficiencies, file completeness, or document audits, provide longer, structured, and specific answers. "
                "IMPORTANT: Every single response MUST be returned as pure JSON (no surrounding backticks or commentary) with exactly two keys: \n"
                "1) \"chat_reply\": a short reply for the chat panel (max 2-3 sentences).\n"
                "2) \"document_output\": the full generated or reviewed document in Markdown format, or an empty string if no document is requested.\n"
                "Use the JSON keys exactly as specified. Do not include extra keys. For the document content, use Markdown.\n"
                "Provide an in-depth analysis of the document's content, explaining which sections are compliant and which are incomplete. "
                "Use bold text only for section headings, not for large amounts of text within the answer. "
            )
        }
        
    def get_history(self, session_id):
        if session_id not in self.sessions:
            self.sessions[session_id] = [self.system_prompt]
        return self.sessions[session_id]

    def add_message(self, session_id, role, content):
        history = self.get_history(session_id)
        history.append({"role": role, "content": content})
        # Jaga agar token tidak membengkak, namun simpan lebih banyak konteks percakapan
        if len(history) > 12:
            self.sessions[session_id] = [self.system_prompt] + history[-11:]

chat_session = ChatSession()

# ─────────────────────────────────────────────
# ROUTES API
# ─────────────────────────────────────────────

# Route untuk chat teks biasa
@app.route('/chat', methods=['POST'])
def chat():
    try:
        print("/chat called")
        data = request.json
        user_message = data.get('message', '').strip()
        session_id = data.get('session_id', 'default')

        if not user_message:
            return jsonify({'error': 'Pesan kosong'}), 400

        chat_session.add_message(session_id, 'user', user_message)
        messages = chat_session.get_history(session_id)
        
        structured = get_structured_response(messages)
        assistant_text = structured.get('chat_reply', '')
        generated_text = structured.get('document_output', '')
        # Save the structured JSON as the assistant's entry in history
        chat_session.add_message(session_id, 'assistant', json.dumps(structured, ensure_ascii=False))

        return jsonify({'assistant': assistant_text, 'generated': generated_text})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Route untuk chat yang disertai dokumen
@app.route('/chat-doc', methods=['POST'])
def chat_doc():
    try:
        print("/chat-doc called")
        session_id = request.form.get('session_id', 'default')
        user_prompt = request.form.get('message', 'Please check if I am eligible to register and whether these documents are sufficient for registration.')
        
        if 'document' not in request.files:
            return jsonify({'error': 'Tidak ada dokumen yang dilampirkan'}), 400
            
        file = request.files['document']
        document_text, err = extract_text_from_file(file)
        
        if err:
            return jsonify({'error': err}), 400
            
        if not document_text.strip():
            return jsonify({'error': 'Dokumen kosong atau teks tidak bisa dibaca.'}), 400

        # Gabungkan instruksi user dengan isi dokumen
        # Batasi panjang teks dokumen agar tidak melebihi context window Mistral
        max_chars = 20000 
        truncated_doc = document_text[:max_chars]
        
        combined_content = (
            f"Instruksi/Prompt: {user_prompt}\n\n"
            "Tugas: review dokumen dan jelaskan apakah pengguna cocok untuk mendaftar serta apakah berkas ini sudah cukup untuk proses pendaftaran. "
            "Berikan analisis mendalam dengan merujuk ke bagian dokumen yang ada, jelaskan kekurangan dan apa yang sudah lengkap. "
            "Untuk permintaan yang sederhana, jawaban ringkas saja. Untuk analisis yang kompleks seperti kekurangan dokumen atau kelengkapan berkas, jawaban harus lebih panjang dan spesifik. "
            "Jika berkas belum lengkap, sebutkan dokumen tambahan yang dibutuhkan. "
            "Gunakan bold hanya pada judul bagian, tidak pada seluruh paragraf.\n\n"
            f"--- ISI DOKUMEN ---\n{truncated_doc}\n-------------------"
        )
        
        chat_session.add_message(session_id, 'user', combined_content)
        messages = chat_session.get_history(session_id)
        
        structured = get_structured_response(messages)
        assistant_text = structured.get('chat_reply', '')
        generated_text = structured.get('document_output', '')
        chat_session.add_message(session_id, 'assistant', json.dumps(structured, ensure_ascii=False))

        return jsonify({'assistant': assistant_text, 'generated': generated_text})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/mock-test', methods=['GET'])
def mock_test():
    # Simple mock response for frontend integration testing
    sample = {
        'assistant': 'Ini balasan singkat (mock). Silakan cek panel kanan untuk dokumen yang dihasilkan.',
        'generated': '# Mock Generated Document\n\nIni adalah contoh dokumen yang dihasilkan oleh mock untuk pengujian.\n\n- Contoh item 1\n- Contoh item 2\n\n**Catatan:** Ini format Markdown.'
    }
    print('/mock-test called, returning sample payload')
    return jsonify(sample)

@app.route('/reset', methods=['POST'])
def reset_conversation():
    session_id = request.json.get('session_id', 'default')
    if session_id in chat_session.sessions:
        del chat_session.sessions[session_id]
    return jsonify({'message': 'Sesi di-reset!'})

# ─────────────────────────────────────────────
# FRONTEND (UI HTML + JS)
# ─────────────────────────────────────────────
@app.route('/')
def home():
    return '''
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DocuChecker AI</title>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        :root { --primary: #000000; --bg: #f3f4f6; --panel-bg: #ffffff; --bot-msg: #f9fafb; --user-msg: #e5e7eb; }
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Inter', -apple-system, sans-serif; }
        body { background-color: var(--bg); min-height: 100vh; display: flex; justify-content: center; padding: 12px; }
        .container { width: 100%; max-width: 1400px; display: grid; grid-template-columns: 0.85fr 1.15fr; gap: 22px; min-height: calc(100vh - 24px); }
        .panel { background: var(--panel-bg); border-radius: 22px; box-shadow: 0 14px 60px rgba(0,0,0,0.08); overflow: hidden; display: flex; flex-direction: column; min-height: 0; }
        .panel-header { padding: 20px 24px; border-bottom: 1px solid #e5e7eb; display: flex; justify-content: space-between; align-items: center; }
        .panel-header h2 { font-size: 1.1rem; color: var(--primary); letter-spacing: 0.02em; }
        .panel-header p { font-size: 0.95rem; color: #6b7280; line-height: 1.6; }
        .panel .chat-container { flex: 1; overflow-y: auto; min-height: 0; }
        .panel .generate-content { flex: 1; overflow: hidden; min-height: 0; }
        .chat-panel .chat-body { display: flex; flex-direction: column; min-height: 0; height: 100%; }
        .chat-container { padding: 16px; display: flex; flex-direction: column; gap: 16px; min-height: 0; overflow-y: auto; }
        .message { display: flex; flex-direction: column; max-width: 85%; }
        .message.user { align-self: flex-end; }
        .message.bot { align-self: flex-start; }
        .msg-bubble { padding: 15px 20px; border-radius: 12px; line-height: 1.6; font-size: 0.95rem; }
        .user .msg-bubble { background: var(--user-msg); color: #1f2937; border-bottom-right-radius: 2px; }
        .bot .msg-bubble { background: var(--bot-msg); color: #1f2937; border: 1px solid #e5e7eb; border-bottom-left-radius: 2px; }
        .bot .msg-bubble p { margin-bottom: 10px; }
        .bot .msg-bubble strong { color: #111827; }
        .bot .msg-bubble ul, .bot .msg-bubble ol { margin-left: 20px; margin-bottom: 10px; }
        .bot .msg-bubble pre { background: #1f2937; color: white; padding: 10px; border-radius: 6px; overflow-x: auto; margin-bottom: 10px; }
        .bot .msg-bubble code { background: #e5e7eb; padding: 2px 5px; border-radius: 4px; font-family: monospace; }
        .bot .msg-bubble pre code { background: none; padding: 0; }
        .generate-content { padding: 18px; display: flex; flex-direction: column; gap: 14px; min-height: 0; }
        .generate-box { flex: 1; padding: 16px; border: 1px solid #e5e7eb; border-radius: 16px; background: #fafafa; overflow-y: auto; min-height: 0; }
        .generate-box p { color: #475569; line-height: 1.7; }
        .generate-box h3 { margin-bottom: 10px; font-size: 1rem; color: #111827; }
        .input-container { padding: 16px 18px 18px; border-top: 1px solid #e5e7eb; background: var(--chat-bg); }
        .file-preview { display: none; padding: 10px; background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; margin-bottom: 10px; font-size: 0.9rem; color: #1d4ed8; align-items: center; justify-content: space-between; }
        .file-preview.active { display: flex; }
        .remove-file { cursor: pointer; color: #ef4444; font-weight: bold; border:none; background:none; }
        .input-box { display: flex; gap: 10px; align-items: flex-end; border: 1px solid #d1d5db; border-radius: 12px; padding: 8px; background: white; transition: border-color 0.2s; }
        .input-box:focus-within { border-color: #6b7280; }
        .attach-btn { background: none; border: none; padding: 10px; cursor: pointer; color: #6b7280; border-radius: 8px; }
        .attach-btn:hover { background: #f3f4f6; color: #111827; }
        textarea { flex: 1; border: none; resize: none; outline: none; padding: 10px; font-size: 1rem; max-height: 150px; background: transparent; font-family: inherit; }
        .send-btn { background: var(--primary); color: white; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-weight: 500; transition: opacity 0.2s; }
        .send-btn:hover { opacity: 0.9; }
        .send-btn:disabled { background: #9ca3af; cursor: not-allowed; }
        .reset-btn { background: #111827; color: white; border: none; border-radius: 10px; padding: 10px 16px; cursor: pointer; font-size: 0.95rem; transition: opacity 0.2s; }
        .reset-btn:hover { opacity: 0.9; }
        .loading { display: none; padding: 10px 20px; font-size: 0.9rem; color: #6b7280; }
        .loading.active { display: block; }
        .debug-panel { font-family: monospace; font-size: 0.85rem; padding: 10px; background: #0f172a; color: #e2e8f0; border-radius: 8px; max-height: 140px; overflow: auto; }
        .debug-small { font-size: 0.8rem; color: #94a3b8; }
    </style>
</head>
<body>

<div class="container">
    <div style="grid-column: 1 / -1; margin-bottom: 10px;">
        <div class="debug-panel" id="debugArea">Debug: ready</div>
    </div>
    <div class="panel chat-panel">
        <div class="panel-header">
            <div>
                <h2>AI Chat (Prompt Bridge)</h2>
                <p>Ketik prompt atau lanjutan pertanyaan di sini. AI chat hanya mengumpulkan instruksi; hasil dokumen atau analisis lengkap akan tampil di panel kanan.</p>
            </div>
            <div style="display:flex;gap:8px;align-items:center;">
                <button class="reset-btn" onclick="resetChat()">Reset Session</button>
                <button class="reset-btn" style="background:#0ea5a4;" onclick="testMock()">Test LLM</button>
            </div>
        </div>

        <div class="chat-body">
            <div class="chat-container" id="chatArea">
                <div class="message bot">
                    <div class="msg-bubble">
                        Halo! Di sini Anda hanya menulis prompt dan melanjutkan percakapan. Hasil dokumen lengkap akan ditampilkan di panel kanan.
                    </div>
                </div>
            </div>
            <div class="loading" id="loading">Analyzing...</div>
            <div class="input-container">
                <div class="file-preview" id="filePreview">
                    <span id="fileName">File Name.pdf</span>
                    <button class="remove-file" onclick="removeFile()">✕ Remove</button>
                </div>
                <form id="chatForm" class="input-box" onsubmit="handleSend(event)">
                    <input type="file" id="fileInput" accept=".pdf,.txt,.docx" style="display: none;" onchange="handleFileSelect(event)">
                    <button type="button" class="attach-btn" onclick="document.getElementById('fileInput').click()" title="Attach Document">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"></path></svg>
                    </button>
                    <textarea id="messageInput" placeholder="Type your prompt here..." rows="1" oninput="autoResize(this)" onkeydown="handleEnter(event)"></textarea>
                    <button type="submit" class="send-btn" id="sendBtn">Send</button>
                </form>
            </div>
        </div>
    </div>

    <div class="panel generate-panel">
        <div class="panel-header">
            <div>
                <h2>Generated Document Output</h2>
                <p>AI produces the full reviewed or improved document here. If hasil kurang, ulangi prompt di panel kiri untuk perbaikan.</p>
            </div>
        </div>
        <div class="generate-content">
            <div class="generate-box" id="generateArea">
                <h3>Generated document or review appears here</h3>
                <p>Kirim prompt atau unggah dokumen. Hasil AI akan tampil di panel ini sebagai dokumen tercetak untuk diperiksa dan disempurnakan.</p>
            </div>
        </div>
    </div>
</div>

<script>
    const sessionId = 'doc_session_' + Math.random().toString(36).substr(2, 9);
    let currentFile = null;

    function autoResize(textarea) {
        textarea.style.height = 'auto';
        textarea.style.height = (textarea.scrollHeight < 150 ? textarea.scrollHeight : 150) + 'px';
    }

    function handleEnter(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend(e);
        }
    }

    function handleFileSelect(e) {
        const file = e.target.files[0];
        if (file) {
            currentFile = file;
            document.getElementById('fileName').textContent = '📄 ' + file.name;
            document.getElementById('filePreview').classList.add('active');
            document.getElementById('messageInput').focus();
            // Jika prompt kosong, isi otomatis
            if(!document.getElementById('messageInput').value) {
                document.getElementById('messageInput').value = "Please check whether these documents are sufficient for registration and explain any deficiencies.";
                autoResize(document.getElementById('messageInput'));
            }
        }
    }

    function removeFile() {
        currentFile = null;
        document.getElementById('fileInput').value = '';
        document.getElementById('filePreview').classList.remove('active');
    }

    function addMessage(text, sender) {
        const chatArea = document.getElementById('chatArea');
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${sender}`;
        
        const bubble = document.createElement('div');
        bubble.className = 'msg-bubble';
        
        if (sender === 'bot') {
            bubble.innerHTML = marked.parse(text); // Convert Markdown to HTML
        } else {
            bubble.textContent = text;
        }
        
        msgDiv.appendChild(bubble);
        chatArea.appendChild(msgDiv);
        chatArea.scrollTop = chatArea.scrollHeight;
        debugLog('CHAT ' + sender + ': ' + (typeof text === 'string' ? text.substring(0,200) : JSON.stringify(text).substring(0,200)));
    }

    function setGeneratedOutput(text) {
        const generateArea = document.getElementById('generateArea');
        generateArea.innerHTML = marked.parse(text);
        debugLog('GENERATED updated (' + (typeof text === 'string' ? text.substring(0,120) : JSON.stringify(text).substring(0,120)) + ')');
    }

    function debugLog(msg) {
        const debug = document.getElementById('debugArea');
        const time = new Date().toISOString().split('T')[1].split('.')[0];
        debug.textContent = time + ' - ' + msg + '\n' + debug.textContent;
    }

    async function handleSend(e) {
        e.preventDefault();
        const input = document.getElementById('messageInput');
        const text = input.value.trim();
        const sendBtn = document.getElementById('sendBtn');
        const loading = document.getElementById('loading');

        if (!text && !currentFile) return;

        let displayMsg = text;
        if (currentFile) displayMsg = `[Melampirkan File: ${currentFile.name}]\n${text}`;
        
        addMessage(displayMsg, 'user');
        
        input.value = '';
        input.style.height = 'auto';
        sendBtn.disabled = true;
        loading.classList.add('active');

        try {
            let response;
            console.log('Sending request. currentFile=', currentFile, 'text=', text);
            if (currentFile) {
                // Mode Chat dengan Lampiran (FormData)
                const formData = new FormData();
                formData.append('document', currentFile);
                formData.append('message', text || "Review dokumen ini.");
                formData.append('session_id', sessionId);

                response = await fetch('/chat-doc', {
                    method: 'POST',
                    body: formData
                });
            } else {
                // Mode Chat Biasa (JSON)
                response = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: text, session_id: sessionId })
                });
            }

            // Check HTTP status first
            if (!response.ok) {
                const txt = await response.text().catch(() => '');
                console.error('Server error', response.status, txt);
                debugLog('HTTP error ' + response.status + ' - ' + txt);
                throw new Error('Server error: ' + response.status + ' ' + txt);
            }

            let data;
            try {
                data = await response.json();
            } catch (err) {
                const text = await response.text().catch(() => '');
                console.warn('Response not JSON, raw text:', text);
                throw new Error('Invalid JSON response from server');
            }

            console.log('Received response:', data);
            debugLog('Received response: ' + JSON.stringify(Object.keys(data)));            

            if (data.error) throw new Error(data.error);

            // Support multiple possible response key names from backend/LLM
            const assistant = data.assistant || data.chat_reply || data.chatbot || '';
            let generated = data.generated || data.document_output || data.generate || data.generated_output || '';

            // If generated is an object, stringify as JSON block
            if (generated && typeof generated === 'object') {
                generated = '```json\n' + JSON.stringify(generated, null, 2) + '\n```';
            }

            const assistantMsg = assistant || (generated ? 'Permintaan diterima. Hasil dokumen yang digenerate akan muncul di panel kanan.' : 'Permintaan diterima.');
            addMessage(assistantMsg, 'bot');
            setGeneratedOutput(generated || '<em>Tidak ada output yang dihasilkan.</em>');
            
        } catch (error) {
            addMessage(`❌ Terjadi kesalahan: ${error.message}`, 'bot');
            setGeneratedOutput(`<strong>Error:</strong> ${error.message}`);
        } finally {
            removeFile(); // Bersihkan file setelah dikirim
            sendBtn.disabled = false;
            loading.classList.remove('active');
        }
    }

    function resetChat() {
        fetch('/reset', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId })
        }).then(() => {
            const chatArea = document.getElementById('chatArea');
            chatArea.innerHTML = `
                <div class="message bot">
                    <div class="msg-bubble">
                        Sesi telah direset. Silakan unggah dokumen baru.
                    </div>
                </div>`;
            removeFile();
        });
    }

    async function testMock() {
        console.log('Calling /mock-test for integration test');
        try {
            const resp = await fetch('/mock-test');
            if (!resp.ok) {
                const txt = await resp.text().catch(()=>'');
                throw new Error('Server error: ' + resp.status + ' ' + txt);
            }
            const data = await resp.json();
            console.log('Mock test response:', data);
            addMessage(data.assistant || 'Mock assistant message', 'bot');
            setGeneratedOutput(data.generated || '<em>No generated output</em>');
        } catch (err) {
            console.error('Mock test failed', err);
            addMessage('❌ Mock test failed: ' + err.message, 'bot');
        }
    }
</script>
</body>
</html>
'''

if __name__ == '__main__':
    print("Menjalankan DocuChecker di http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)