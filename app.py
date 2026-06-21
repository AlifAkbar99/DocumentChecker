"""
app.py
==========================================
AI DOCUMENTER CHECKER
Cek kelengkapan berkas pendaftaran (PKM, beasiswa, dll) berdasarkan buku panduan,
lalu generate dokumen yang masih kurang (dengan placeholder data sensitif).

Stack: Flask + LangChain + Mistral API (langchain-mistralai)

Cara jalankan:
    1. pip install -r requirements.txt
    2. cp .env.example .env   -> isi MISTRAL_API_KEY
    3. python app.py
    4. Buka http://127.0.0.1:5000

CATATAN PROTOTYPE:
- State disimpan in-memory (dict Python), per session cookie. Cocok untuk
  development/demo. Untuk produksi sebaiknya pindah ke Redis/DB supaya
  tidak hilang saat server restart & bisa scale ke banyak worker.
==========================================
"""
import os
import re
import uuid

from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, session, send_file

import doc_extract
import llm_utils
import doc_export

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-ganti-ini-di-produksi")
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20 MB per request

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads_tmp")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# In-memory store, key = session_id
SESSIONS = {}


def get_session_state():
    """Ambil (atau buat baru) state untuk session user saat ini."""
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())

    sid = session["session_id"]
    if sid not in SESSIONS:
        SESSIONS[sid] = {
            "role": None,
            "guideline_text": None,
            "checklist": [],
            "documents": [],   # [{filename, text}]
            "check_results": [],
            "drafts": {},       # {req_id: {"name": str, "content": str}}
        }
    return SESSIONS[sid]


def is_identity_document(name: str) -> bool:
    if not name:
        return False
    return bool(re.search(r"\b(ktp|kartu tanda mahasiswa|kartu identitas|passport|paspor|student id|identity card|identitas)\b", name, re.I))


# ------------------------------------------------------------------
# FRONTEND
# ------------------------------------------------------------------
@app.route("/")
def home():
    return render_template("index.html")


# ------------------------------------------------------------------
# 1. PILIH PERAN (MAHASISWA / PEKERJA) -> reset session baru
# ------------------------------------------------------------------
@app.route("/api/start", methods=["POST"])
def api_start():
    data = request.get_json(force=True) or {}
    role = data.get("role")
    if role not in ("mahasiswa", "pekerja"):
        return jsonify({"error": "role harus 'mahasiswa' atau 'pekerja'"}), 400

    # Mulai sesi baru dari nol setiap kali user pilih role (supaya tidak ada
    # data nyangkut dari sesi sebelumnya)
    session["session_id"] = str(uuid.uuid4())
    state = get_session_state()
    state["role"] = role

    return jsonify({"ok": True, "role": role})


# ------------------------------------------------------------------
# 2. UPLOAD BUKU PANDUAN -> extract checklist via LLM
# ------------------------------------------------------------------
@app.route("/api/upload-guideline", methods=["POST"])
def api_upload_guideline():
    state = get_session_state()
    if not state["role"]:
        return jsonify({"error": "Choose a role (student or worker) before uploading."}), 400

    file = request.files.get("file")
    if not file or file.filename == "":
        return jsonify({"error": "No file was uploaded."}), 400
    if not doc_extract.allowed_file(file.filename):
        return jsonify({"error": "Unsupported file format. Use PDF, DOCX, or image (PNG/JPG)."}), 400

    filepath = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}_{file.filename}")
    file.save(filepath)

    try:
        text = doc_extract.extract_text(filepath, file.filename)
        state["guideline_text"] = text

        language = request.form.get("language", "en")
        checklist = llm_utils.extract_checklist(text, state["role"], language)
        state["checklist"] = checklist
        return jsonify({"checklist": checklist})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)


# ------------------------------------------------------------------
# TRANSLATE / REFRESH CHECKLIST LANGUAGE
# ------------------------------------------------------------------
@app.route("/api/translate-checklist", methods=["POST"])
def api_translate_checklist():
    state = get_session_state()
    if not state["role"] or not state["guideline_text"]:
        return jsonify({"error": "No guideline checklist available to translate."}), 400

    data = request.get_json(force=True) or {}
    language = data.get("language", "en")
    try:
        checklist = llm_utils.extract_checklist(state["guideline_text"], state["role"], language)
        state["checklist"] = checklist
        return jsonify({"checklist": checklist})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ------------------------------------------------------------------
# 3. UPLOAD DOKUMEN YANG SUDAH DIMILIKI USER
# ------------------------------------------------------------------
@app.route("/api/upload-documents", methods=["POST"])
def api_upload_documents():
    state = get_session_state()
    if not state["checklist"]:
        return jsonify({"error": "Upload guideline first before uploading documents."}), 400

    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files were uploaded."}), 400

    uploaded_summaries = []
    for file in files:
        if not file or file.filename == "":
            continue
        if not doc_extract.allowed_file(file.filename):
            uploaded_summaries.append({
                "filename": file.filename,
                "error": "Unsupported format, skipped.",
            })
            continue

        filepath = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}_{file.filename}")
        file.save(filepath)
        try:
            text = doc_extract.extract_text(filepath, file.filename)
            state["documents"].append({"filename": file.filename, "text": text})
            uploaded_summaries.append({
                "filename": file.filename,
                "preview": text[:200] + ("..." if len(text) > 200 else ""),
            })
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)

    return jsonify({"documents": uploaded_summaries, "total_documents": len(state["documents"])})


# ------------------------------------------------------------------
# 4. JALANKAN PENGECEKAN: checklist vs dokumen yang ada
# ------------------------------------------------------------------
@app.route("/api/check", methods=["POST"])
def api_check():
    state = get_session_state()
    if not state["checklist"]:
        return jsonify({"error": "No checklist yet. Upload the guideline first."}), 400

    data = request.get_json(force=True) or {}
    language = data.get("language", "en")

    try:
        results = llm_utils.check_requirements(state["checklist"], state["documents"], language)
        state["check_results"] = results
        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ------------------------------------------------------------------
# 5. GENERATE DRAFT DOKUMEN YANG MASIH KURANG
# ------------------------------------------------------------------
@app.route("/api/generate", methods=["POST"])
def api_generate():
    state = get_session_state()
    data = request.get_json(force=True) or {}
    requirement_ids = data.get("requirement_ids", [])
    context_notes = data.get("context_notes", "")
    language = data.get("language", "en")

    if not requirement_ids:
        return jsonify({"error": "Select at least one requirement to generate."}), 400

    checklist_by_id = {item["id"]: item for item in state["checklist"]}
    generated = {}

    for req_id in requirement_ids:
        requirement = checklist_by_id.get(req_id)
        if not requirement:
            continue
        localized_name = requirement.get(f"name_{language}") or requirement.get("name") or req_id
        if is_identity_document(localized_name):
            generated[req_id] = {
                "name": localized_name,
                "error": "Identity documents are not generated by this tool.",
            }
            continue
        try:
            requirement_for_generation = requirement.copy()
            requirement_for_generation["name"] = localized_name
            if requirement.get(f"description_{language}"):
                requirement_for_generation["description"] = requirement[f"description_{language}"]
            content = llm_utils.generate_document(requirement_for_generation, state["role"], context_notes, language)
            placeholders = llm_utils.list_placeholders(content)
            state["drafts"][req_id] = {"name": localized_name, "content": content}
            generated[req_id] = {
                "name": localized_name,
                "content": content,
                "placeholders": placeholders,
            }
        except Exception as e:
            generated[req_id] = {"name": requirement.get("name", req_id), "error": str(e)}

    return jsonify({"drafts": generated})


# ------------------------------------------------------------------
# 6. UPDATE DRAFT SETELAH USER REVIEW/EDIT
# ------------------------------------------------------------------
@app.route("/api/update-draft", methods=["POST"])
def api_update_draft():
    state = get_session_state()
    data = request.get_json(force=True) or {}
    req_id = data.get("requirement_id")
    content = data.get("content", "")

    if req_id not in state["drafts"]:
        return jsonify({"error": "Draft not found."}), 404

    state["drafts"][req_id]["content"] = content
    placeholders = llm_utils.list_placeholders(content)
    return jsonify({"ok": True, "placeholders": placeholders})


# ------------------------------------------------------------------
# 7. EXPORT DRAFT -> PDF atau DOCX
# ------------------------------------------------------------------
@app.route("/api/export", methods=["POST"])
def api_export():
    state = get_session_state()
    data = request.get_json(force=True) or {}
    req_id = data.get("requirement_id")
    fmt = data.get("format", "docx")

    draft = state["drafts"].get(req_id)
    if not draft:
        return jsonify({"error": "Draft not found."}), 404

    title = draft["name"]
    content = draft["content"]
    safe_name = "".join(c if c.isalnum() or c in " -_" else "" for c in title).strip().replace(" ", "_") or "document"

    if fmt == "pdf":
        file_bytes = doc_export.text_to_pdf_bytes(title, content)
        mimetype = "application/pdf"
        filename = f"{safe_name}.pdf"
    else:
        file_bytes = doc_export.text_to_docx_bytes(title, content)
        mimetype = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        filename = f"{safe_name}.docx"

    import io
    return send_file(
        io.BytesIO(file_bytes),
        mimetype=mimetype,
        as_attachment=True,
        download_name=filename,
    )


# ------------------------------------------------------------------
# 8. RESET SESSION (mulai ulang dari awal)
# ------------------------------------------------------------------
@app.route("/api/reset", methods=["POST"])
def api_reset():
    sid = session.get("session_id")
    if sid and sid in SESSIONS:
        del SESSIONS[sid]
    session.pop("session_id", None)
    return jsonify({"ok": True})


if __name__ == "__main__":
    print("\n--- AI DOCUMENTER CHECKER ---")
    print("Buka browser dan akses: http://127.0.0.1:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)
