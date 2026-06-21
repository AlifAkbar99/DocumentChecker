"""
llm_utils.py
==========================================
All LLM interactions (Mistral via API, through LangChain) are here:

1. extract_checklist()  -> read guideline, generate checklist of document requirements
2. check_requirements()  -> compare checklist vs documents already uploaded by user
3. generate_document()   -> generate draft for missing documents (with placeholders)

All functions return Python dict/list (already parsed from JSON),
with error handling so slightly off-format LLM output doesn't crash the app.
==========================================
"""
import json
import os
import re

from langchain_mistralai import ChatMistralAI
from langchain_core.messages import SystemMessage, HumanMessage

MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-large-latest")

# Limit on document text length sent to LLM
# to avoid exceeding context window / wasting tokens.
MAX_CHARS_PER_DOC = 6000


def get_llm(temperature: float = 0.3) -> ChatMistralAI:
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise RuntimeError(
            "MISTRAL_API_KEY belum diset. Buat file .env berdasarkan .env.example "
            "dan isi dengan API key dari https://console.mistral.ai/"
        )
    return ChatMistralAI(model=MISTRAL_MODEL, api_key=api_key, temperature=temperature)


def _truncate(text: str, max_chars: int = MAX_CHARS_PER_DOC) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...[text truncated due to length]..."


def _parse_json_response(raw_text: str):
    """LLM kadang membungkus JSON dengan ```json ... ``` atau menambah kalimat
    pembuka. Fungsi ini membersihkan itu sebelum json.loads()."""
    cleaned = raw_text.strip()
    cleaned = re.sub(r"^```(json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()

    # Kalau masih ada teks di luar JSON, coba ambil blok [...] atau {...} terluar
    match = re.search(r"(\[.*\]|\{.*\})", cleaned, re.DOTALL)
    if match:
        cleaned = match.group(1)

    return json.loads(cleaned)


# ------------------------------------------------------------------
# 1. EKSTRAKSI CHECKLIST DARI BUKU PANDUAN
# ------------------------------------------------------------------
def extract_checklist(guideline_text: str, role: str, language: str = "en") -> list:
    """
    role: "mahasiswa" atau "pekerja"
    language: "en", "id", atau "ms"
    Mengembalikan list of dict:
    [{ "id": "req_1", "name_en": "...", "description_en": "...", "name_id": "...", "description_id": "...", "name_ms": "...", "description_ms": "...", "category_en": "...", "category_id": "...", "category_ms": "...", "category": "..." }, ...]
    """
    language_name = {"en": "English", "id": "Indonesian", "ms": "Malay"}.get(language, "English")
    category_default_labels = {"en": "Administrative", "id": "Administratif", "ms": "Pentadbiran"}
    category_label = category_default_labels.get(language, category_default_labels["en"])

    system_prompt = (
        "You are an expert administrative assistant who reads an official guideline document "
        "and extracts a checklist of required documents or application items.\n\n"
        f"The applicant using this checklist has status: '{role}'. "
        "Include only items relevant to that status.\n\n"
        "For each checklist item, provide the requirement title and description in all three languages: English, Indonesian, and Malay. "
        "Also provide the category label in all three languages. Keep the meaning consistent across languages and faithfully reflect the source document.\n\n"
        "Answer ONLY with a JSON array (no markdown, no introductory or closing sentences), using this format:\n"
        "[{\n"
        "  \"id\": \"req_1\",\n"
        "  \"name_en\": \"Requirement title in English\",\n"
        "  \"description_en\": \"Brief explanation in English...\",\n"
        "  \"name_id\": \"Judul persyaratan dalam Bahasa Indonesia\",\n"
        "  \"description_id\": \"Penjelasan singkat dalam Bahasa Indonesia...\",\n"
        "  \"name_ms\": \"Tajuk syarat dalam Bahasa Melayu\",\n"
        "  \"description_ms\": \"Penerangan ringkas dalam Bahasa Melayu...\",\n"
        "  \"category_en\": \"Administrative\",\n"
        "  \"category_id\": \"Administratif\",\n"
        "  \"category_ms\": \"Pentadbiran\",\n"
        f"  \"category\": \"{category_label}\"\n"
        "}]\n"
        "Use sequential ids req_1, req_2, etc. Return up to 20 items and focus on the most important ones."
    )

    human_prompt = (
        "Berikut isi (potongan) dokumen buku panduan:\n\n"
        f"{_truncate(guideline_text)}"
    )

    llm = get_llm(temperature=0.2)
    response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=human_prompt)])

    try:
        checklist = _parse_json_response(response.content)
        if not isinstance(checklist, list):
            raise ValueError("Response is not a list")
        return checklist
    except Exception as e:
        raise RuntimeError(
            f"Failed to parse checklist from AI response: {e}\n\nRaw response:\n{response.content}"
        )


# ------------------------------------------------------------------
# 2. CEK STATUS PEMENUHAN SYARAT
# ------------------------------------------------------------------
def check_requirements(checklist: list, documents: list, language: str = "en") -> list:
    """
    documents: list of {"filename": ..., "text": ...}
    Mengembalikan list of dict:
    [{ "id", "name", "status": "fulfilled"|"missing"|"partial",
       "evidence": "...", "note": "..." }, ...]
    """
    docs_summary = "\n\n".join(
        f"--- Document: {d['filename']} ---\n{_truncate(d['text'], 3000)}"
        for d in documents
    ) or "(No documents uploaded by user)"

    checklist_json = json.dumps(checklist, ensure_ascii=False)
    language_name = {"en": "English", "id": "Indonesian", "ms": "Malay"}.get(language, "English")

    system_prompt = (
        "You are an assistant that checks application document completeness. "
        "You will receive (1) a requirements checklist and (2) extracted text from documents the user has uploaded.\n\n"
        "For EACH checklist item, determine its status:\n"
        "- 'fulfilled' if there is clear evidence the item is already provided\n"
        "- 'partial' if there is related documentation but it seems incomplete or not fully meeting the criteria\n"
        "- 'missing' if there is no evidence the item exists\n\n"
        f"Write all notes in {language_name}. "
        "Answer ONLY with a JSON array (no markdown), using this format:\n"
        '[{"id": "req_1", "name": "...", "status": "fulfilled|partial|missing", '
        '"evidence": "Short quote or reason from the relevant document, or empty if missing", '
        '"note": "Short, friendly, clear note for the user"}, ...]'
    )

    human_prompt = (
        f"CHECKLIST:\n{checklist_json}\n\n"
        f"DOCUMENTS ALREADY UPLOADED BY USER:\n{docs_summary}"
    )

    llm = get_llm(temperature=0.2)
    response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=human_prompt)])

    try:
        results = _parse_json_response(response.content)
        if not isinstance(results, list):
            raise ValueError("Response is not a list")

        checklist_by_id = {item["id"]: item for item in checklist if "id" in item}
        for result in results:
            checklist_item = checklist_by_id.get(result.get("id"))
            if checklist_item:
                for suffix in ["en", "id", "ms"]:
                    for base in ["name", "description", "category"]:
                        key = f"{base}_{suffix}"
                        if key in checklist_item:
                            result[key] = checklist_item[key]
                if "name" not in result and "name_en" in checklist_item:
                    result["name"] = checklist_item["name_en"]
        return results
    except Exception as e:
        raise RuntimeError(
            f"Failed to parse check results from AI response: {e}\n\nRaw response:\n{response.content}"
        )


# ------------------------------------------------------------------
# 3. GENERATE DRAFT DOKUMEN YANG BELUM ADA
# ------------------------------------------------------------------
def generate_document(requirement: dict, role: str, context_notes: str = "", language: str = "en") -> str:
    """
    requirement: { "id", "name", "description", "category" }
    Mengembalikan teks draft dokumen (plain text, tanpa markdown),
    dengan placeholder [SEMUA_HURUF_BESAR] untuk data sensitif/pribadi yang tidak diketahui AI.
    """
    language_name = {"en": "English", "id": "Indonesian", "ms": "Malay"}.get(language, "English")
    system_prompt = (
        f"You are an assistant that writes formal administrative or academic documents in {language_name}. "
        "Your task is to create a DRAFT document based on the requirement name and description provided, "
        f"for an applicant with status '{role}'.\n\n"
        "IMPORTANT RULES:\n"
        "1. Do not invent any personal or sensitive data that is not provided (name, student/employee ID, identification number, "
        "address, phone number, specific institution name, dates, supervisor/manager name, etc.). "
        "For all such information, use placeholders in the format [UPPERCASE_WITH_UNDERSCORES], "
        "for example [FULL_NAME], [STUDENT_ID], [INSTITUTION_NAME], [DATE], [SUPERVISOR_NAME].\n"
        f"2. Write in formal {language_name} appropriate for official or academic documents.\n"
        "3. Include an appropriate structure for the document type (for example: a motivation letter should have an opening, body describing motivation and purpose, and a closing; a reference letter should include a header, body, and signature placeholder).\n"
        "4. Output ONLY the finished document text (plain text, no markdown, no extra explanation, no introductory sentence like 'Here is the draft:')."
    )

    human_prompt = (
        f"Document/requirement name: {requirement.get('name')}\n"
        f"Description/criteria: {requirement.get('description')}\n"
        f"Category: {requirement.get('category', '-')}\n"
    )
    if context_notes:
        human_prompt += f"\nAdditional context from user: {context_notes}\n"

    llm = get_llm(temperature=0.5)
    response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=human_prompt)])
    return response.content.strip()


def list_placeholders(text: str) -> list:
    """Find all placeholders [LIKE_THIS] in the text to show the user as a list they need to fill before download."""
    return sorted(set(re.findall(r"\[([A-Z0-9_]+)\]", text)))
