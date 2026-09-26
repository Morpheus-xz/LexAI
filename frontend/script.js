(() => {
  "use strict";

  const MAX_DOCUMENT_CHARS = 50000;

  const docTextEl = document.getElementById("doc-text");
  const docLabelEl = document.getElementById("doc-label");
  const docTextBEl = document.getElementById("doc-text-b");
  const docLabelBEl = document.getElementById("doc-label-b");
  const askQuestionEl = document.getElementById("ask-question");
  const simplifyFocusEl = document.getElementById("simplify-focus");
  const charCountEl = document.getElementById("char-count");

  const comparePanel = document.getElementById("compare-panel");
  const askPanel = document.getElementById("ask-panel");
  const simplifyPanel = document.getElementById("simplify-panel");

  const welcomeState = document.getElementById("welcome-state");
  const loadingState = document.getElementById("loading-state");
  const errorState = document.getElementById("error-state");
  const resultsContent = document.getElementById("results-content");

  const historyList = document.getElementById("history-list");

  const actionButtons = Array.from(document.querySelectorAll(".action-btn"));

  let activeAction = null;
  let requestInFlight = false;

  /** HTML-encodes a string before any innerHTML assignment. Prevents XSS
   * from AI-generated or user-supplied text ever being rendered as markup. */
  function safeHTML(value) {
    const div = document.createElement("div");
    div.textContent = value == null ? "" : String(value);
    return div.innerHTML;
  }

  /** Renders a <use> reference into the shared icon sprite defined in
   * index.html — the single source of truth for every icon, static or
   * dynamically injected. */
  function icon(name) {
    return `<svg class="icon" aria-hidden="true"><use href="#icon-${name}"/></svg>`;
  }

  function showPanel(panel) {
    [welcomeState, loadingState, errorState, resultsContent].forEach((el) => {
      el.hidden = el !== panel;
    });
  }

  function updateCharCount() {
    const len = docTextEl.value.length;
    charCountEl.textContent = `${len.toLocaleString()} / ${MAX_DOCUMENT_CHARS.toLocaleString()} characters`;
    charCountEl.classList.toggle("over-limit", len > MAX_DOCUMENT_CHARS);
  }

  docTextEl.addEventListener("input", () => {
    updateCharCount();
    showPanel(welcomeState);
  });

  updateCharCount();

  function setActiveAction(action) {
    activeAction = action;
    actionButtons.forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.action === action);
    });
    comparePanel.hidden = action !== "compare";
    askPanel.hidden = action !== "ask";
    simplifyPanel.hidden = action !== "simplify";
  }

  actionButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      setActiveAction(btn.dataset.action);
      runAction(btn.dataset.action);
    });
  });

  function showError(message) {
    errorState.innerHTML = `${icon("alert")}<span>${safeHTML(message)}</span>`;
    showPanel(errorState);
  }

  async function callApi(endpoint, payload) {
    const resp = await fetch(API_BASE_URL + endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!resp.ok) {
      let detail = `Request failed (${resp.status}).`;
      try {
        const data = await resp.json();
        if (data && data.detail) {
          detail =
            typeof data.detail === "string"
              ? data.detail
              : "The document could not be processed. Please try again.";
        }
      } catch (_) {
        /* response body was not JSON; keep default message */
      }
      if (resp.status === 502) {
        detail = "LexAI's AI service is temporarily unavailable. Please try again shortly.";
      }
      throw new Error(detail);
    }
    return resp.json();
  }

  // ---- Debounce guards against double-submission on rapid clicks ----
  function debounceGuard(fn) {
    return async (...args) => {
      if (requestInFlight) return;
      requestInFlight = true;
      try {
        await fn(...args);
      } finally {
        requestInFlight = false;
      }
    };
  }

  const runAction = debounceGuard(async (action) => {
    const text = docTextEl.value.trim();
    if (text.length < 20) {
      showError("Please paste at least 20 characters of document text.");
      return;
    }
    if (text.length > MAX_DOCUMENT_CHARS) {
      showError(`Document is too long — please keep it under ${MAX_DOCUMENT_CHARS.toLocaleString()} characters.`);
      return;
    }

    showPanel(loadingState);

    try {
      let data;
      switch (action) {
        case "analyze":
          data = await callApi("/analyze", { text, label: docLabelEl.value || undefined });
          renderAnalyze(data);
          break;
        case "simplify":
          data = await callApi("/simplify", {
            text,
            focus: simplifyFocusEl.value || undefined,
          });
          renderSimplify(data);
          break;
        case "summarize":
          data = await callApi("/summarize", { text, label: docLabelEl.value || undefined });
          renderSummarize(data);
          break;
        case "compare": {
          const textB = docTextBEl.value.trim();
          if (textB.length < 20) {
            showError("Please paste a second document (at least 20 characters) to compare.");
            return;
          }
          data = await callApi("/compare", {
            doc_a: text,
            doc_b: textB,
            label_a: docLabelEl.value || undefined,
            label_b: docLabelBEl.value || undefined,
          });
          renderCompare(data);
          break;
        }
        case "ask": {
          const question = askQuestionEl.value.trim();
          if (question.length < 5) {
            showError("Please enter a question of at least 5 characters.");
            return;
          }
          data = await callApi("/ask", { text, question });
          renderAsk(data);
          break;
        }
        case "prepare":
          data = await callApi("/prepare", { text, label: docLabelEl.value || undefined });
          renderPrepare(data);
          break;
        default:
          return;
      }
      loadHistory();
    } catch (err) {
      showError(err.message || "Something went wrong. Please try again.");
    }
  });

  function disclaimerBlock(disclaimer) {
    return `<p class="disclaimer-line">${icon("alert")}<span>${safeHTML(disclaimer)}</span></p>`;
  }

  function listItems(items) {
    return items.map((item) => `<li>${safeHTML(item)}</li>`).join("");
  }

  function cardHeading(iconName, title) {
    return `<h3>${icon(iconName)}<span>${safeHTML(title)}</span></h3>`;
  }

  function renderAnalyze(data) {
    const stats = data.stats;
    const riskHtml = data.risk_flags.length
      ? data.risk_flags
          .map(
            (r) => `
        <div class="risk-flag">
          <span class="risk-icon">${icon("alert")}</span>
          <span>
            <span class="risk-category">${safeHTML(r.category)}</span>
            ${safeHTML(r.context)}
          </span>
        </div>`
          )
          .join("")
      : "<p>No risk-indicator keywords were detected.</p>";

    resultsContent.innerHTML = `
      <div class="result-card">
        ${cardHeading("file", "Document overview")}
        <div class="stats-bar">
          <span class="stat-chip">${stats.word_count} words</span>
          <span class="stat-chip">${stats.estimated_reading_minutes} min read</span>
          <span class="stat-chip">${stats.sentence_count} sentences</span>
          <span class="stat-chip">${data.clauses.length} clauses detected</span>
        </div>
        <p>${safeHTML(data.ai_summary)}</p>
      </div>
      <div class="result-card">
        ${cardHeading("alert", "Risk flags")}
        ${riskHtml}
      </div>
      <div class="result-card">
        ${cardHeading("check", "Obligations")}
        <ul class="plain-list">${listItems(data.obligations)}</ul>
      </div>
      <div class="result-card">
        ${cardHeading("unlock", "Rights")}
        <ul class="plain-list">${listItems(data.rights)}</ul>
      </div>
      <div class="result-card">
        ${cardHeading("calendar", "Key dates")}
        <ul class="plain-list">${listItems(data.key_dates)}</ul>
      </div>
      ${disclaimerBlock(data.disclaimer)}
    `;
    showPanel(resultsContent);
  }

  function renderSimplify(data) {
    resultsContent.innerHTML = `
      <div class="result-card">
        ${cardHeading("edit", "Plain-English rewrite")}
        <p>${safeHTML(data.plain_english)}</p>
      </div>
      <div class="result-card">
        ${cardHeading("check", "Key points")}
        <ul class="plain-list">${listItems(data.key_points)}</ul>
      </div>
      ${disclaimerBlock(data.disclaimer)}
    `;
    showPanel(resultsContent);
  }

  function renderSummarize(data) {
    resultsContent.innerHTML = `
      <div class="result-card">
        ${cardHeading("file", "Executive summary")}
        <p>${safeHTML(data.executive_summary)}</p>
      </div>
      <div class="result-card">
        ${cardHeading("check", "Key points")}
        <ul class="plain-list">${listItems(data.key_points)}</ul>
      </div>
      <div class="result-card">
        ${cardHeading("clipboard", "Important clauses")}
        <ul class="plain-list">${listItems(data.important_clauses)}</ul>
      </div>
      <div class="result-card">
        ${cardHeading("arrow-circle", "Action items")}
        <ul class="plain-list">${listItems(data.action_items)}</ul>
      </div>
      ${disclaimerBlock(data.disclaimer)}
    `;
    showPanel(resultsContent);
  }

  function structuralColumn(label, s) {
    return `
      <div>
        <h4>${safeHTML(label)}</h4>
        <span class="stat-chip">${s.risk_count} risks</span>
        <span class="stat-chip">${s.obligation_count} obligations</span>
        <span class="stat-chip">${s.right_count} rights</span>
        <span class="stat-chip">${s.clause_count} clauses</span>
      </div>`;
  }

  function renderCompare(data) {
    resultsContent.innerHTML = `
      <div class="result-card">
        ${cardHeading("compare", "Structural comparison")}
        <div class="compare-columns">
          ${structuralColumn("Document A", data.doc_a_structural)}
          ${structuralColumn("Document B", data.doc_b_structural)}
        </div>
        <p>${safeHTML(data.ai_comparison)}</p>
      </div>
      <div class="result-card">
        ${cardHeading("alert", "Key differences")}
        <ul class="plain-list">${listItems(data.key_differences)}</ul>
      </div>
      <div class="result-card">
        ${cardHeading("check", "Recommendation")}
        <p>${safeHTML(data.recommendation)}</p>
      </div>
      ${disclaimerBlock(data.disclaimer)}
    `;
    showPanel(resultsContent);
  }

  function renderAsk(data) {
    const confidenceClass =
      data.confidence && data.confidence.startsWith("high")
        ? "confidence-high"
        : data.confidence && data.confidence.startsWith("medium")
        ? "confidence-medium"
        : "confidence-low";
    resultsContent.innerHTML = `
      <div class="result-card">
        <span class="confidence-badge ${confidenceClass}">Confidence: ${safeHTML(data.confidence)}</span>
        ${cardHeading("help", "Answer")}
        <p>${safeHTML(data.answer)}</p>
      </div>
      ${disclaimerBlock(data.disclaimer)}
    `;
    showPanel(resultsContent);
  }

  function renderPrepare(data) {
    resultsContent.innerHTML = `
      <div class="result-card">
        ${cardHeading("file", "Document summary")}
        <p>${safeHTML(data.document_summary)}</p>
      </div>
      <div class="result-card">
        ${cardHeading("help", "Questions for your lawyer")}
        <ul class="plain-list">${listItems(data.questions_for_lawyer)}</ul>
      </div>
      <div class="result-card">
        ${cardHeading("check", "Checklist")}
        <ul class="plain-list">${listItems(data.checklist)}</ul>
      </div>
      <div class="result-card">
        ${cardHeading("alert", "Red flags")}
        <ul class="plain-list">${listItems(data.red_flags)}</ul>
      </div>
      ${disclaimerBlock(data.disclaimer)}
    `;
    showPanel(resultsContent);
  }

  // ---- Session document history ----

  async function loadHistory() {
    try {
      const resp = await fetch(API_BASE_URL + "/documents");
      if (!resp.ok) return;
      const docs = await resp.json();
      renderHistory(docs);
    } catch (_) {
      /* history is a convenience feature; failures are silent */
    }
  }

  function renderHistory(docs) {
    if (!docs.length) {
      historyList.innerHTML = "<li>No documents yet.</li>";
      return;
    }
    historyList.innerHTML = docs
      .map(
        (d) => `
      <li class="history-item" data-id="${safeHTML(d.id)}">
        <button type="button" class="history-load" aria-label="Load document ${safeHTML(d.label)}">
          ${icon("file")}<span>${safeHTML(d.label)}</span>
        </button>
        <button type="button" class="history-delete" aria-label="Delete document ${safeHTML(d.label)}">
          ${icon("trash")}
        </button>
      </li>`
      )
      .join("");
  }

  historyList.addEventListener("click", async (event) => {
    const item = event.target.closest(".history-item");
    if (!item) return;
    const docId = item.dataset.id;

    // .closest() (not a direct classList check) so a click on the icon
    // <svg>/<use> nested inside these buttons still resolves correctly.
    if (event.target.closest(".history-load")) {
      const resp = await fetch(`${API_BASE_URL}/documents/${encodeURIComponent(docId)}`);
      if (resp.ok) {
        const doc = await resp.json();
        docTextEl.value = doc.text;
        updateCharCount();
        showPanel(welcomeState);
      }
    } else if (event.target.closest(".history-delete")) {
      await fetch(`${API_BASE_URL}/documents/${encodeURIComponent(docId)}`, { method: "DELETE" });
      loadHistory();
    }
  });

  loadHistory();
})();
