// ==========================================
// script.js — logic wizard "Berkas Beres"
// ==========================================

const state = {
  role: null,
  checklist: [],
  results: [],
  drafts: {},
  missingIds: new Set(), // requirement id selected for generation
  language: localStorage.getItem("appLanguage") || "en",
};

const TRANSLATIONS = {
  en: {
    languageLabel: "Language",
    stepRole: "Role",
    stepGuideline: "Guideline",
    stepDocuments: "Documents",
    stepCheck: "Check",
    stepComplete: "Complete",
    stepCounter: "Step {step} of 5",
    restartBtn: "Restart",
    resetBtnTitle: "Restart from the beginning",
    headingRole: "Which role are you applying as?",
    ledeRole: "This determines which requirements are relevant for you — some application guides have different documents for students and professionals.",
    roleStudent: "Student",
    roleStudentDesc: "Applications via campus — PKM, scholarships, community programs, etc.",
    roleWorker: "Worker / Professional",
    roleWorkerDesc: "Applications via company/institution — advanced study funding, grants, etc.",
    headingGuideline: "Upload guideline document",
    ledeGuideline: "Official document that contains the application requirements. Example: PKM guide, scholarship guideline, etc. Format: PDF, DOCX, or photo/scan (PNG/JPG).",
    dropzoneClick: "Click to choose a file",
    dropzoneFilesClick: "Click to choose files",
    dropzoneOr: "or",
    dropzoneHint: "One file, up to 20MB",
    dropzoneFilesHint: "Multiple files allowed",
    btnAnalyzeGuideline: "Read & analyze guideline",
    checklistTitle: "AI-detected checklist",
    checklistHint: "These are the requirements the AI found in your guideline, filtered for the selected status <strong id=\"rolePreviewLabel\"></strong>. Continue when they look correct.",
    btnToStep2: "Continue: upload my documents",
    headingDocuments: "Upload the documents you already have",
    ledeDocuments: "Upload all documents you currently have — certificates, letters, transcripts, ID, etc. You can upload multiple files. The AI will compare these with the checklist.",
    btnSkipDocs: "Skip, I don't have any documents yet",
    btnRunCheck: "Check my document completeness",
    headingCheck: "Check results",
    checkSummaryText: "AI is comparing your documents to the checklist...",
    btnGoToGenerate: "Generate missing documents",
    headingComplete: "Complete missing documents",
    ledeComplete: "The AI creates drafts for documents you still need. Personal or sensitive data that the AI does not know will be marked as [PLACEHOLDER] — be sure to replace all placeholders with real data before using the documents officially.",
    contextNotesLabel: "Additional notes for AI (optional)",
    contextNotesPlaceholder: "Example: program name, proposal title, university name, etc. Helps the AI make the draft more accurate.",
    btnGenerateDrafts: "Generate drafts now",
    fileReady: "Ready to upload",
    fileRead: "Read",
    fileUnsupported: "Unsupported format, skipped.",
    noDocsSelected: "No documents selected for generation. Go back to the previous step to choose.",
    confirmRestart: "Restart from the beginning? All current progress will be lost.",
    generateThisDocument: "Generate this document for me",
    generateIdentityNote: "Identity documents such as ID cards, KTP, passport, or student ID will not be generated.",
    placeholderWarning: "Replace the following data before using the document officially:",
    saveChanges: "Save changes",
    downloadDocx: "Download .docx",
    downloadPdf: "Download .pdf",
    saving: "Saving...",
    changesSaved: "Changes saved.",
    preparingFile: "Preparing file...",
    failedCreateFile: "Failed to create file.",
    failedGenerate: "Failed to generate:",
    missingResultsSummary: "Out of {total} requirements, {count} are still missing or incomplete. You can ask the AI to generate drafts in the next step.",
    allFulfilledSummary: "Great! All checklist items appear fulfilled based on your uploaded documents.",
    fulfilledLabel: "Fulfilled",
    partialLabel: "Partial",
    missingLabel: "Missing",
    noDraftsEligibleSummary: "No eligible missing documents found for generation. Identity documents are excluded.",
    generateSelectionTitle: "Pick documents to generate",
    generateSelectionHint: "Select the missing documents you want the AI to draft. Private data will stay as placeholders for you to fill locally.",
    downloadText: "Download .txt",
  },
  id: {
    languageLabel: "Bahasa",
    stepRole: "Peran",
    stepGuideline: "Panduan",
    stepDocuments: "Dokumen",
    stepCheck: "Pemeriksaan",
    stepComplete: "Selesai",
    stepCounter: "Langkah {step} dari 5",
    restartBtn: "Mulai ulang",
    resetBtnTitle: "Mulai ulang dari awal",
    headingRole: "Peran apa yang kamu pilih?",
    ledeRole: "Ini menentukan syarat mana yang relevan untukmu — beberapa buku panduan aplikasi memiliki dokumen yang berbeda untuk mahasiswa dan pekerja.",
    roleStudent: "Mahasiswa",
    roleStudentDesc: "Aplikasi dari kampus — PKM, beasiswa, program komunitas, dll.",
    roleWorker: "Pekerja / Profesional",
    roleWorkerDesc: "Aplikasi lewat perusahaan/institusi — pendanaan studi lanjut, hibah, dll.",
    headingGuideline: "Unggah dokumen panduan",
    ledeGuideline: "Dokumen resmi yang berisi persyaratan pendaftaran. Contoh: panduan PKM, panduan beasiswa, dll. Format: PDF, DOCX, atau foto/scan (PNG/JPG).",
    dropzoneClick: "Klik untuk memilih file",
    dropzoneFilesClick: "Klik untuk memilih file",
    dropzoneOr: "atau",
    dropzoneHint: "Satu file, hingga 20MB",
    dropzoneFilesHint: "Boleh unggah beberapa file",
    btnAnalyzeGuideline: "Baca & analisis panduan",
    checklistTitle: "Checklist yang dideteksi AI",
    checklistHint: "Ini adalah persyaratan yang ditemukan AI dalam panduan Anda, disaring untuk status yang dipilih <strong id=\"rolePreviewLabel\"></strong>. Lanjutkan jika sudah sesuai.",
    btnToStep2: "Lanjut: unggah dokumen saya",
    headingDocuments: "Unggah dokumen yang sudah Anda miliki",
    ledeDocuments: "Unggah semua dokumen yang Anda miliki — sertifikat, surat, transkrip, identitas, dll. AI akan membandingkan ini dengan checklist.",
    btnSkipDocs: "Lewati, saya belum punya dokumen",
    btnRunCheck: "Periksa kelengkapan dokumen saya",
    headingCheck: "Hasil pemeriksaan",
    checkSummaryText: "AI sedang membandingkan dokumen Anda dengan checklist...",
    btnGoToGenerate: "Buat dokumen yang kurang",
    headingComplete: "Selesaikan dokumen yang kurang",
    ledeComplete: "AI membuat draf untuk dokumen yang masih Anda butuhkan. Data pribadi atau sensitif yang tidak diketahui AI akan ditandai sebagai [PLACEHOLDER] — ganti semua placeholder dengan data riil sebelum menggunakan dokumen secara resmi.",
    contextNotesLabel: "Catatan tambahan untuk AI (opsional)",
    contextNotesPlaceholder: "Contoh: nama program, judul proposal, nama universitas, dll. Membantu AI membuat draf lebih akurat.",
    btnGenerateDrafts: "Buat draf sekarang",
    fileReady: "Siap diunggah",
    fileRead: "Tersimpan",
    fileUnsupported: "Format tidak didukung, dilewati.",
    noDocsSelected: "Tidak ada dokumen yang dipilih untuk dibuat. Kembali ke langkah sebelumnya untuk memilih.",
    confirmRestart: "Mulai ulang dari awal? Semua progres saat ini akan hilang.",
    generateThisDocument: "Buat dokumen ini untuk saya",
    generateIdentityNote: "Dokumen identitas seperti kartu, KTP, paspor, atau kartu mahasiswa tidak akan dibuat.",
    placeholderWarning: "Ganti data berikut sebelum menggunakan dokumen secara resmi:",
    saveChanges: "Simpan perubahan",
    downloadDocx: "Unduh .docx",
    downloadPdf: "Unduh .pdf",
    saving: "Menyimpan...",
    changesSaved: "Perubahan tersimpan.",
    preparingFile: "Menyiapkan file...",
    failedCreateFile: "Gagal membuat file.",
    failedGenerate: "Gagal membuat:",
    missingResultsSummary: "Dari {total} persyaratan, {count} masih kurang atau tidak lengkap. Anda bisa minta AI membuat draf di langkah berikutnya.",
    allFulfilledSummary: "Bagus! Semua item checklist terlihat terpenuhi berdasarkan dokumen Anda.",
    fulfilledLabel: "Terealisasi",
    partialLabel: "Sebagian",
    missingLabel: "Kurang",
    noDraftsEligibleSummary: "Tidak ditemukan dokumen kurang yang bisa dibuat. Dokumen identitas dikecualikan.",
    generateSelectionTitle: "Pilih dokumen untuk dibuat",
    generateSelectionHint: "Pilih dokumen yang ingin AI buat. Data pribadi akan tetap menjadi placeholder untuk Anda isi secara lokal.",
    downloadText: "Unduh .txt",
    failedCheckSummary: "Gagal menjalankan pemeriksaan.",
    btnWritingDrafts: "AI sedang membuat draf...",
  },
  ms: {
    languageLabel: "Bahasa",
    stepRole: "Peranan",
    stepGuideline: "Garis Panduan",
    stepDocuments: "Dokumen",
    stepCheck: "Semak",
    stepComplete: "Selesai",
    stepCounter: "Langkah {step} dari 5",
    restartBtn: "Mulakan semula",
    resetBtnTitle: "Mulakan semula dari awal",
    headingRole: "Peranan apa yang anda pilih?",
    ledeRole: "Ini menentukan syarat mana yang relevan untuk anda — beberapa garis panduan aplikasi mempunyai dokumen berbeza untuk pelajar dan pekerja.",
    roleStudent: "Pelajar",
    roleStudentDesc: "Permohonan melalui kampus — PKM, biasiswa, program komuniti, dan lain-lain.",
    roleWorker: "Pekerja / Profesional",
    roleWorkerDesc: "Permohonan melalui syarikat/institusi — pembiayaan kajian lanjutan, geran, dan lain-lain.",
    headingGuideline: "Muat naik dokumen panduan",
    ledeGuideline: "Dokumen rasmi yang mengandungi syarat permohonan. Contoh: panduan PKM, panduan biasiswa, dan lain-lain. Format: PDF, DOCX, atau foto/imbasan (PNG/JPG).",
    dropzoneClick: "Klik untuk memilih fail",
    dropzoneFilesClick: "Klik untuk memilih fail",
    dropzoneOr: "atau",
    dropzoneHint: "Satu fail, sehingga 20MB",
    dropzoneFilesHint: "Boleh muat naik berbilang fail",
    btnAnalyzeGuideline: "Baca & analisis panduan",
    checklistTitle: "Semak imbas checklist AI",
    checklistHint: "Ini adalah syarat yang ditemui AI dalam panduan anda, ditapis untuk status yang dipilih <strong id=\"rolePreviewLabel\"></strong>. Teruskan jika sudah betul.",
    btnToStep2: "Teruskan: muat naik dokumen saya",
    headingDocuments: "Muat naik dokumen yang sudah anda ada",
    ledeDocuments: "Muat naik semua dokumen yang anda ada — sijil, surat, transkrip, ID, dan lain-lain. AI akan membandingkannya dengan checklist.",
    btnSkipDocs: "Langkau, saya belum ada dokumen",
    btnRunCheck: "Semak kelengkapan dokumen saya",
    headingCheck: "Hasil semakan",
    checkSummaryText: "AI sedang membandingkan dokumen anda dengan checklist...",
    btnGoToGenerate: "Hasilkan dokumen yang kurang",
    headingComplete: "Lengkapkan dokumen yang kurang",
    ledeComplete: "AI menghasilkan draf untuk dokumen yang masih anda perlukan. Data peribadi atau sensitif yang tidak diketahui AI akan ditandakan sebagai [PLACEHOLDER] — pastikan menggantikan semua placeholder dengan data sebenar sebelum menggunakan dokumen secara rasmi.",
    contextNotesLabel: "Nota tambahan untuk AI (pilihan)",
    contextNotesPlaceholder: "Contoh: nama program, tajuk proposal, nama universiti, dan lain-lain. Membantu AI membuat draf lebih tepat.",
    btnGenerateDrafts: "Hasilkan draf sekarang",
    fileReady: "Sedia dimuat naik",
    fileRead: "Dibaca",
    fileUnsupported: "Format tidak disokong, diabaikan.",
    noDocsSelected: "Tiada dokumen dipilih untuk dihasilkan. Kembali ke langkah sebelumnya untuk memilih.",
    confirmRestart: "Mulakan semula dari awal? Semua kemajuan semasa akan hilang.",
    generateThisDocument: "Hasilkan dokumen ini untuk saya",
    generateIdentityNote: "Dokumen identiti seperti kad, KTP, pasport atau kad pelajar tidak akan dihasilkan.",
    placeholderWarning: "Gantikan data berikut sebelum menggunakan dokumen secara rasmi:",
    saveChanges: "Simpan perubahan",
    downloadDocx: "Muat turun .docx",
    downloadPdf: "Muat turun .pdf",
    saving: "Menyimpan...",
    changesSaved: "Perubahan disimpan.",
    preparingFile: "Menyediakan fail...",
    failedCreateFile: "Gagal membuat fail.",
    failedGenerate: "Gagal menghasilkan:",
    missingResultsSummary: "Daripada {total} syarat, {count} masih kurang atau tidak lengkap. Anda boleh minta AI menghasilkan draf di langkah berikutnya.",
    allFulfilledSummary: "Bagus! Semua item checklist nampaknya dipenuhi berdasarkan dokumen anda.",
    fulfilledLabel: "Tercapai",
    partialLabel: "Sebahagian",
    missingLabel: "Belum lengkap",
    noDraftsEligibleSummary: "Tiada dokumen kurang layak dihasilkan. Dokumen identiti dikecualikan.",
    generateSelectionTitle: "Pilih dokumen untuk dihasilkan",
    generateSelectionHint: "Pilih dokumen yang anda mahu AI hasilkan. Data peribadi akan kekal sebagai placeholder untuk anda isi secara tempatan.",
    downloadText: "Muat turun .txt",
    failedCheckSummary: "Gagal menjalankan semakan.",
    btnWritingDrafts: "AI sedang menghasilkan draf...",
  },
};

function translate(key, params = {}) {
  const strings = TRANSLATIONS[state.language] || TRANSLATIONS.en;
  let value = strings[key] || TRANSLATIONS.en[key] || key;
  Object.entries(params).forEach(([param, text]) => {
    value = value.replace(`{${param}}`, text);
  });
  return value;
}

function localizedField(item, fieldBase) {
  if (!item) return "";
  const ln = state.language;
  return item[`${fieldBase}_${ln}`] || item[fieldBase] || item[`${fieldBase}_en`] || item[`${fieldBase}_id`] || item[`${fieldBase}_ms`] || "";
}

function applyTranslations() {
  document.documentElement.lang = state.language;
  document.getElementById("langSelect").value = state.language;
  document.querySelectorAll("[data-i18n]").forEach(el => {
    el.textContent = translate(el.dataset.i18n);
    if (el.dataset.i18n === "checklistHint") {
      el.innerHTML = translate(el.dataset.i18n);
    }
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach(el => {
    el.placeholder = translate(el.dataset.i18nPlaceholder);
  });
  document.querySelectorAll(".eyebrow[data-i18n=stepCounter]").forEach(el => {
    const step = el.dataset.stepNumber;
    el.textContent = translate("stepCounter", { step });
  });
  if (document.getElementById("checklistPreview")?.style.display === "block") {
    renderChecklistPreview(state.checklist);
  }
  if (document.getElementById("resultList")?.children.length) {
    renderResults(state.check_results || []);
  }
}

function isIdentityDocument(name) {
  if (!name) return false;
  return /\b(ktp|kartu tanda mahasiswa|kartu identitas|passport|paspor|student id|identity card|identitas)\b/i.test(name);
}

function stampLabel(status) {
  const labels = {
    fulfilled: translate("fulfilledLabel") || "Fulfilled",
    partial: translate("partialLabel") || "Partial",
    missing: translate("missingLabel") || "Missing",
  };
  return labels[status] || status;
}

async function refreshChecklistLanguage() {
  if (!state.checklist || !state.checklist.length) return;
  const example = state.checklist[0];
  if (example?.name_en || example?.name_id || example?.name_ms) {
    return; // already has multilingual translations
  }

  try {
    const data = await postJSON("/api/translate-checklist", { language: state.language });
    state.checklist = data.checklist;
    if (document.getElementById("checklistPreview")?.style.display === "block") {
      renderChecklistPreview(state.checklist);
    }
  } catch (e) {
    showToast(e.message, true);
  }
}

window.addEventListener("DOMContentLoaded", () => {
  applyTranslations();
  document.getElementById("langSelect").addEventListener("change", async event => {
    state.language = event.target.value;
    localStorage.setItem("appLanguage", state.language);
    applyTranslations();
    await refreshChecklistLanguage();
  });
});

// ---------- helpers umum ----------
function showToast(message, isError = false) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.className = "toast show" + (isError ? " error" : "");
  setTimeout(() => { toast.className = "toast"; }, 3500);
}

function goToStep(stepIndex) {
  document.querySelectorAll(".screen").forEach(s => s.classList.remove("active"));
  document.getElementById(`screen-${stepIndex}`).classList.add("active");

  document.querySelectorAll(".step-dot").forEach(dot => {
    const idx = parseInt(dot.dataset.step, 10);
    dot.classList.remove("active", "done");
    if (idx < stepIndex) dot.classList.add("done");
    if (idx === stepIndex) dot.classList.add("active");
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function postJSON(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "An error occurred on the server.");
  return data;
}

async function postForm(url, formData) {
  const res = await fetch(url, { method: "POST", body: formData });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "An error occurred on the server.");
  return data;
}

function setBusy(button, busyLabel, isBusy) {
  if (isBusy) {
    button.dataset.originalLabel = button.textContent;
    button.textContent = busyLabel;
    button.disabled = true;
  } else {
    button.textContent = button.dataset.originalLabel || button.textContent;
    button.disabled = false;
  }
}

// =====================================================
// STEP 0 — PILIH PERAN
// =====================================================
document.querySelectorAll(".role-card").forEach(card => {
  card.addEventListener("click", async () => {
    const role = card.dataset.role;
    try {
      await postJSON("/api/start", { role });
      state.role = role;
      document.getElementById("rolePreviewLabel").textContent = role;
      goToStep(1);
    } catch (e) {
      showToast(e.message, true);
    }
  });
});

// =====================================================
// STEP 1 — UPLOAD BUKU PANDUAN
// =====================================================
const dropzoneGuideline = document.getElementById("dropzone-guideline");
const fileGuidelineInput = document.getElementById("fileGuideline");
const guidelineFileChip = document.getElementById("guidelineFileChip");
const btnAnalyzeGuideline = document.getElementById("btnAnalyzeGuideline");
let guidelineFile = null;

function setupDropzone(zoneEl, inputEl, onFiles) {
  zoneEl.addEventListener("click", () => inputEl.click());
  zoneEl.addEventListener("dragover", e => { e.preventDefault(); zoneEl.classList.add("dragover"); });
  zoneEl.addEventListener("dragleave", () => zoneEl.classList.remove("dragover"));
  zoneEl.addEventListener("drop", e => {
    e.preventDefault();
    zoneEl.classList.remove("dragover");
    onFiles(e.dataTransfer.files);
  });
  inputEl.addEventListener("change", () => onFiles(inputEl.files));
}

setupDropzone(dropzoneGuideline, fileGuidelineInput, files => {
  if (!files.length) return;
  guidelineFile = files[0];
  guidelineFileChip.style.display = "inline-flex";
  guidelineFileChip.innerHTML = `&#128206; ${guidelineFile.name}`;
  btnAnalyzeGuideline.disabled = false;
});

btnAnalyzeGuideline.addEventListener("click", async () => {
  if (!guidelineFile) return;
  setBusy(btnAnalyzeGuideline, "AI is reading the guideline...", true);
  try {
    const formData = new FormData();
    formData.append("file", guidelineFile);
    formData.append("language", state.language);
    const data = await postForm("/api/upload-guideline", formData);
    state.checklist = data.checklist;
    renderChecklistPreview(data.checklist);
  } catch (e) {
    showToast(e.message, true);
  } finally {
    setBusy(btnAnalyzeGuideline, "", false);
  }
});

function renderChecklistPreview(checklist) {
  const container = document.getElementById("checklistItems");
  container.innerHTML = "";
  checklist.forEach(item => {
    const li = document.createElement("li");
    li.innerHTML = `
      <span class="req-cat">${localizedField(item, "category") || "General"}</span>
      <div class="req-name">${localizedField(item, "name")}</div>
      <div class="req-desc">${localizedField(item, "description") || ""}</div>
    `;
    container.appendChild(li);
  });
  document.getElementById("checklistPreview").style.display = "block";
}

document.getElementById("btnToStep2").addEventListener("click", () => goToStep(2));

// =====================================================
// STEP 2 — UPLOAD DOKUMEN USER
// =====================================================
const dropzoneDocs = document.getElementById("dropzone-documents");
const fileDocsInput = document.getElementById("fileDocuments");
const documentFileList = document.getElementById("documentFileList");
const btnRunCheck = document.getElementById("btnRunCheck");
let pendingDocFiles = [];

setupDropzone(dropzoneDocs, fileDocsInput, files => {
  pendingDocFiles = [...pendingDocFiles, ...Array.from(files)];
  renderPendingDocs();
});

function renderPendingDocs() {
  documentFileList.innerHTML = "";
  pendingDocFiles.forEach(f => {
    const li = document.createElement("li");
    li.innerHTML = `<span>&#128196; ${f.name}</span><span class="file-status">${translate("fileReady")}</span>`;
    documentFileList.appendChild(li);
  });
  btnRunCheck.disabled = pendingDocFiles.length === 0;
}

async function uploadPendingDocs() {
  if (!pendingDocFiles.length) return;
  const formData = new FormData();
  pendingDocFiles.forEach(f => formData.append("files", f));
  const data = await postForm("/api/upload-documents", formData);

  documentFileList.innerHTML = "";
  (data.documents || []).forEach(d => {
    const li = document.createElement("li");
    const ok = !d.error;
    li.innerHTML = `<span>&#128196; ${d.filename}</span>
      <span class="file-status ${ok ? "" : "error"}">${ok ? translate("fileRead") : d.error}</span>`;
    documentFileList.appendChild(li);
  });
  pendingDocFiles = [];
}

document.getElementById("btnSkipDocs").addEventListener("click", async () => {
  goToStep(3);
  await runCheck();
});

btnRunCheck.addEventListener("click", async () => {
  setBusy(btnRunCheck, "Uploading documents...", true);
  try {
    await uploadPendingDocs();
    goToStep(3);
    await runCheck();
  } catch (e) {
    showToast(e.message, true);
  } finally {
    setBusy(btnRunCheck, "", false);
  }
});

// =====================================================
// STEP 3 — HASIL PENGECEKAN
// =====================================================

async function runCheck() {
  const summaryText = document.getElementById("checkSummaryText");
  const resultList = document.getElementById("resultList");
  summaryText.textContent = translate("checkSummaryText");
  summaryText.className = "lede loading-text";
  resultList.innerHTML = "";

  try {
    const data = await postJSON("/api/check", { language: state.language });
    const results = data.results || [];
    state.results = results;
    const eligibleMissing = results.filter(r => r.status !== "fulfilled" && !isIdentityDocument(localizedField(r, "name"))).length;
    const totalMissing = results.filter(r => r.status !== "fulfilled").length;

    summaryText.className = "lede";
    if (eligibleMissing === 0) {
      if (totalMissing === 0) {
        summaryText.textContent = translate("allFulfilledSummary");
      } else {
        summaryText.textContent = translate("noDraftsEligibleSummary");
      }
    } else {
      summaryText.textContent = translate("missingResultsSummary", {
        total: String(results.length),
        count: String(eligibleMissing),
      });
    }

    renderResults(results);
    document.getElementById("btnGoToGenerate").disabled = eligibleMissing === 0;
  } catch (e) {
    summaryText.className = "lede";
    summaryText.textContent = translate("failedCheckSummary") || "Failed to run the check.";
    showToast(e.message, true);
  }
}

function renderResults(results) {
  const resultList = document.getElementById("resultList");
  resultList.innerHTML = "";
  state.missingIds = new Set();

  results.forEach(r => {
    const card = document.createElement("div");
    card.className = "result-card";

    const localizedName = localizedField(r, "name");
    const stampClass = `stamp-${r.status}`;
    const isMissing = r.status !== "fulfilled";
    const isIdentity = isMissing && isIdentityDocument(localizedName || r.name);

    const actionHtml = isMissing
      ? isIdentity
        ? `<div class="result-note identity-note">${translate("generateIdentityNote")}</div>`
        : `<label class="gen-toggle">
             <input type="checkbox" class="gen-checkbox" data-id="${r.id}" checked>
             ${translate("generateThisDocument")}
           </label>`
      : "";

    card.innerHTML = `
      <div class="result-main">
        <div class="result-name">${localizedName || r.name}</div>
        ${r.note ? `<div class="result-note">${r.note}</div>` : ""}
        ${r.evidence ? `<div class="result-evidence">"${r.evidence}"</div>` : ""}
        ${actionHtml}
      </div>
      <span class="stamp ${stampClass}">${stampLabel(r.status)}</span>
    `;
    resultList.appendChild(card);

    if (isMissing && !isIdentity) state.missingIds.add(r.id);
  });

  resultList.querySelectorAll(".gen-checkbox").forEach(cb => {
    cb.addEventListener("change", () => {
      if (cb.checked) state.missingIds.add(cb.dataset.id);
      else state.missingIds.delete(cb.dataset.id);
    });
  });
}

document.getElementById("btnGoToGenerate").addEventListener("click", () => {
  goToStep(4);
  renderGenerateSelection();
});

function renderGenerateSelection() {
  const list = document.getElementById("generateList");
  const draftArea = document.getElementById("draftsArea");
  list.innerHTML = "";
  draftArea.innerHTML = "";

  const missingItems = state.results.filter(r => r.status !== "fulfilled" && !isIdentityDocument(localizedField(r, "name")));
  if (!missingItems.length) {
    list.innerHTML = `<li class="generate-empty">${translate("noDraftsEligibleSummary")}</li>`;
    document.getElementById("btnGenerateDrafts").disabled = true;
    return;
  }

  missingItems.forEach(item => {
    const selected = state.missingIds.has(item.id);
    const node = document.createElement("li");
    node.className = "generate-item";
    node.innerHTML = `
      <label class="generate-item-card">
        <input type="checkbox" class="generate-select" data-id="${item.id}" ${selected ? "checked" : ""}>
        <div>
          <div class="generate-item-name">${localizedField(item, "name") || item.name}</div>
          <div class="generate-item-desc">${localizedField(item, "description") || item.description || ""}</div>
        </div>
      </label>
    `;
    list.appendChild(node);
  });

  list.querySelectorAll(".generate-select").forEach(input => {
    input.addEventListener("change", () => {
      if (input.checked) state.missingIds.add(input.dataset.id);
      else state.missingIds.delete(input.dataset.id);
      document.getElementById("btnGenerateDrafts").disabled = state.missingIds.size === 0;
    });
  });
  document.getElementById("btnGenerateDrafts").disabled = state.missingIds.size === 0;
}

// =====================================================
// STEP 4 — GENERATE & REVIEW DRAFT
// =====================================================
document.getElementById("btnGenerateDrafts").addEventListener("click", async () => {
  const btn = document.getElementById("btnGenerateDrafts");
  const ids = Array.from(state.missingIds);
  if (!ids.length) {
    showToast(translate("noDocsSelected"), true);
    return;
  }
  const contextNotes = document.getElementById("contextNotes").value;

  setBusy(btn, translate("btnWritingDrafts") || "AI is writing drafts...", true);
  try {
    const data = await postJSON("/api/generate", { requirement_ids: ids, context_notes: contextNotes, language: state.language });
    renderDrafts(data.drafts);
  } catch (e) {
    showToast(e.message, true);
  } finally {
    setBusy(btn, "", false);
  }
});

function renderDrafts(drafts) {
  const area = document.getElementById("draftsArea");
  area.innerHTML = "";

  Object.entries(drafts).forEach(([reqId, draft]) => {
    state.drafts[reqId] = draft;
    const card = document.createElement("div");
    card.className = "draft-card";

    if (draft.error) {
      card.innerHTML = `<h3>&#9888; ${draft.name}</h3><p class="muted">${translate("failedGenerate")} ${draft.error}</p>`;
      area.appendChild(card);
      return;
    }

    const placeholderHtml = draft.placeholders && draft.placeholders.length
      ? `<div class="placeholder-warning">
           ${translate("placeholderWarning")}
           ${draft.placeholders.map(p => `<span class="mono">[${p}]</span>`).join(" ")}
         </div>`
      : "";

    card.innerHTML = `
      <h3>&#128221; ${draft.name}</h3>
      ${placeholderHtml}
      <textarea class="draft-textarea" data-req-id="${reqId}">${draft.content}</textarea>
      <div class="draft-actions">
        <button class="btn btn-secondary btn-save" data-req-id="${reqId}">${translate("saveChanges")}</button>
        <button class="btn btn-primary btn-download" data-req-id="${reqId}" data-format="txt">${translate("downloadText")}</button>
      </div>
    `;
    area.appendChild(card);
  });

  area.querySelectorAll(".btn-save").forEach(btn => {
    btn.addEventListener("click", () => saveDraft(btn.dataset.reqId, btn));
  });
  area.querySelectorAll(".btn-download").forEach(btn => {
    btn.addEventListener("click", () => downloadDraft(btn.dataset.reqId, btn.dataset.format, btn));
  });
}

function saveDraft(reqId, btn) {
  const textarea = document.querySelector(`.draft-textarea[data-req-id="${reqId}"]`);
  setBusy(btn, translate("saving"), true);
  try {
    const draft = state.drafts[reqId];
    if (draft) {
      draft.content = textarea.value;
      showToast(translate("changesSaved"));
    }
  } catch (e) {
    showToast(e.message, true);
  } finally {
    setBusy(btn, "", false);
  }
}

function downloadDraft(reqId, format, btn) {
  const textarea = document.querySelector(`.draft-textarea[data-req-id="${reqId}"]`);
  setBusy(btn, translate("preparingFile"), true);
  try {
    const content = textarea.value;
    const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${state.drafts[reqId]?.name || reqId}.${format}`.replace(/[^a-zA-Z0-9-_. ]/g, "_");
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  } catch (e) {
    showToast(e.message, true);
  } finally {
    setBusy(btn, "", false);
  }
}

