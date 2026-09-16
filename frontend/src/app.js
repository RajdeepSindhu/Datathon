document.addEventListener("DOMContentLoaded", () => {
    const chatThread = document.getElementById("chat-thread");
    const chatForm = document.getElementById("chat-form");
    const userInput = document.getElementById("user-input");
    const sendBtn = document.getElementById("send-btn");
    const presetList = document.getElementById("preset-list");
    const quickChips = document.getElementById("quick-chips");
    const menuToggle = document.getElementById("menu-toggle");
    const sidebar = document.getElementById("sidebar");

    let isSubmitting = false;
    // Conversation history — last 5 turns (user + bot)
    const MAX_HISTORY = 5;
    let conversationHistory = [];

    // Toggle sidebar on mobile
    if (menuToggle && sidebar) {
        menuToggle.addEventListener("click", () => {
            sidebar.classList.toggle("open");
        });
    }

    const API_BASE =
        window.location.protocol === "file:" ||
        (window.location.port && window.location.port !== "8000")
            ? "http://127.0.0.1:8000"
            : "";

    // Load Suggested Queries and Metadata
    async function loadInitialData() {
        try {
            const [healthRes, queryRes] = await Promise.all([
                fetch(`${API_BASE}/api/health`),
                fetch(`${API_BASE}/api/suggested-queries`),
            ]);

            if (healthRes.ok) {
                const health = await healthRes.json();
                const statMandis = document.getElementById("stat-mandis");
                const statCrops = document.getElementById("stat-crops");
                if (statMandis)
                    statMandis.textContent = health.total_mandis || "57";
                if (statCrops)
                    statCrops.textContent = health.total_crops || "7";
            }

            if (queryRes.ok) {
                const queries = await queryRes.json();
                renderPresets(queries);
                renderQuickChips(queries.slice(0, 4));
            }
        } catch (e) {
            console.error("Could not load initial metadata:", e);
        }
    }

    function renderPresets(queries) {
        if (!presetList) return;
        presetList.innerHTML = "";
        queries.forEach((q) => {
            const btn = document.createElement("button");
            btn.className = "preset-btn";
            btn.type = "button";
            btn.innerHTML = `
        <span class="preset-badge">${q.category}</span>
        <span>${q.query}</span>
      `;
            btn.addEventListener("click", (e) => {
                e.preventDefault();
                submitQuery(q.query);
                if (window.innerWidth <= 1024 && sidebar) {
                    sidebar.classList.remove("open");
                }
            });
            presetList.appendChild(btn);
        });
    }

    function renderQuickChips(queries) {
        if (!quickChips) return;
        quickChips.innerHTML = "";
        queries.forEach((q) => {
            const chip = document.createElement("button");
            chip.className = "chip";
            chip.type = "button";
            chip.textContent = q.query;
            chip.addEventListener("click", (e) => {
                e.preventDefault();
                submitQuery(q.query);
            });
            quickChips.appendChild(chip);
        });
    }

    // Robust Query Submitter
    async function submitQuery(queryText) {
        const query = (queryText || userInput.value).trim();
        if (!query || isSubmitting) return;

        // Hide welcome card once first message is submitted
        const welcomeCard = document.getElementById("welcome-card");
        if (welcomeCard) {
            welcomeCard.style.display = "none";
        }

        // Append User Message
        appendUserMessage(query);
        userInput.value = "";
        isSubmitting = true;
        sendBtn.disabled = true;

        // Append Thinking Indicator
        const thinkingEl = appendThinkingIndicator();
        scrollToBottom();

        try {
            const response = await fetch(`${API_BASE}/api/chat`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ query, history: conversationHistory }),
            });

            const data = await response.json();
            thinkingEl.remove();

            // Store this turn in history
            const botSummary = data.summary || data.answer || "";
            conversationHistory.push({ role: "user", content: query });
            conversationHistory.push({
                role: "assistant",
                content: botSummary,
            });
            if (conversationHistory.length > MAX_HISTORY * 2) {
                conversationHistory = conversationHistory.slice(
                    -MAX_HISTORY * 2,
                );
            }

            appendBotResponse(data);
        } catch (err) {
            thinkingEl.remove();
            appendErrorMessage(
                "Error connecting to Mandi server. Please ensure the backend is running at http://localhost:8000.",
            );
            console.error(err);
        } finally {
            isSubmitting = false;
            sendBtn.disabled = false;
            userInput.focus();
            scrollToBottom();
        }
    }

    // Prevent any form submission reload
    chatForm.addEventListener("submit", (e) => {
        e.preventDefault();
        e.stopPropagation();
        submitQuery();
        return false;
    });

    sendBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        submitQuery();
    });

    userInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            e.stopPropagation();
            submitQuery();
        }
    });

    function appendUserMessage(text) {
        const group = document.createElement("div");
        group.className = "message-group";
        group.innerHTML = `<div class="user-message">${escapeHtml(text)}</div>`;
        chatThread.appendChild(group);
    }

    function appendThinkingIndicator() {
        const el = document.createElement("div");
        el.className = "thinking-indicator";
        el.innerHTML = `
      <div class="spinner"></div>
      <span>Reasoning with Gemini & executing deterministic Pandas calculation...</span>
    `;
        chatThread.appendChild(el);
        return el;
    }

    function appendErrorMessage(msg) {
        const group = document.createElement("div");
        group.className = "message-group";
        group.innerHTML = `
      <div class="bot-response" style="border-color: rgba(239, 68, 68, 0.3);">
        <div class="ai-summary-header" style="color: #ef4444;">System Message</div>
        <div class="ai-summary-text">${escapeHtml(msg)}</div>
      </div>
    `;
        chatThread.appendChild(group);
    }

    function appendBotResponse(resp) {
        const group = document.createElement("div");
        group.className = "message-group";

        const botCard = document.createElement("div");
        botCard.className = "bot-response";

        // 1. Answer heading (short direct result — shown ABOVE chart)
        const answerSection = document.createElement("div");
        answerSection.className = "ai-summary-block";
        answerSection.innerHTML = `
      <div class="ai-summary-header">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="16" x2="12" y2="12"></line>
          <line x1="12" y1="8" x2="12.01" y2="8"></line>
        </svg>
        AI Summary
      </div>
      <div class="ai-answer-heading">${escapeHtml(resp.answer || "")}</div>
    `;
        botCard.appendChild(answerSection);

        // 2. Applied Filters Badges (ABOVE chart)
        if (
            resp.filters_applied &&
            Object.keys(resp.filters_applied).length > 0
        ) {
            const filtersEl = document.createElement("div");
            filtersEl.className = "filter-tags";
            for (const [k, v] of Object.entries(resp.filters_applied)) {
                if (v !== null && v !== undefined && v !== "") {
                    const badge = document.createElement("span");
                    badge.className = "filter-badge";
                    badge.innerHTML = `<strong>${k.replace(/_/g, " ")}:</strong> ${escapeHtml(String(v))}`;
                    filtersEl.appendChild(badge);
                }
            }
            if (resp.data_range) {
                const rangeBadge = document.createElement("span");
                rangeBadge.className = "filter-badge";
                rangeBadge.innerHTML = `<strong>period:</strong> ${resp.data_range.start} → ${resp.data_range.end}`;
                filtersEl.appendChild(rangeBadge);
            }
            botCard.appendChild(filtersEl);
        }

        // 3. Visualization Section (Interactive Chart)
        if (resp.chart) {
            const vizContainer = document.createElement("div");
            vizContainer.className = "viz-container";

            const vizHeader = document.createElement("div");
            vizHeader.className = "viz-header";
            vizHeader.innerHTML = `
        <span class="viz-title">${escapeHtml(resp.chart.title || "Interactive Visualization")}</span>
        <span class="chart-type-tag">${resp.chart.type || "Chart"}</span>
      `;
            vizContainer.appendChild(vizHeader);

            const chartWrap = document.createElement("div");
            const chartId = `viz_wrap_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`;
            chartWrap.id = chartId;
            chartWrap.className =
                resp.chart.type === "kpi" ? "kpi-container" : "chart-wrapper";
            vizContainer.appendChild(chartWrap);

            botCard.appendChild(vizContainer);

            // Render chart after DOM attach
            setTimeout(() => {
                window.ChartRenderer.render(chartId, resp.chart);
            }, 50);
        }

        // 4. Detailed AI summary (shown BELOW chart)
        if (resp.summary && resp.summary !== resp.answer) {
            const summarySection = document.createElement("div");
            summarySection.className = "ai-detail-block";
            summarySection.innerHTML = `
        <div class="ai-detail-header">Analysis</div>
        <div class="ai-summary-text">${escapeHtml(resp.summary)}</div>
      `;
            botCard.appendChild(summarySection);
        }

        // 4. Supporting Data Table (Collapsible)
        if (
            resp.data &&
            resp.data.length > 0 &&
            (!resp.chart || resp.chart.type !== "table")
        ) {
            const detailsToggle = document.createElement("button");
            detailsToggle.className = "details-toggle";
            detailsToggle.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="6 9 12 15 18 9"></polyline>
        </svg>
        <span>View Verified Data Table (${resp.data.length} records)</span>
      `;

            const tableWrapper = document.createElement("div");
            tableWrapper.style.display = "none";
            tableWrapper.className = "table-container";

            const cols = Object.keys(resp.data[0]);
            let ths = cols
                .map((c) => `<th>${c.replace(/_/g, " ")}</th>`)
                .join("");
            let trs = resp.data
                .slice(0, 25)
                .map((r) => {
                    return `<tr>${cols.map((c) => `<td>${r[c] !== null && r[c] !== undefined ? r[c] : "-"}</td>`).join("")}</tr>`;
                })
                .join("");

            tableWrapper.innerHTML = `
        <table class="data-table">
          <thead><tr>${ths}</tr></thead>
          <tbody>${trs}</tbody>
        </table>
      `;

            detailsToggle.addEventListener("click", () => {
                const isHidden = tableWrapper.style.display === "none";
                tableWrapper.style.display = isHidden ? "block" : "none";
                detailsToggle.querySelector("span").textContent = isHidden
                    ? `Hide Verified Data Table (${resp.data.length} records)`
                    : `View Verified Data Table (${resp.data.length} records)`;
            });

            botCard.appendChild(detailsToggle);
            botCard.appendChild(tableWrapper);
        }

        group.appendChild(botCard);
        chatThread.appendChild(group);
    }

    function scrollToBottom() {
        chatThread.scrollTop = chatThread.scrollHeight;
    }

    function escapeHtml(str) {
        if (!str) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // Load initial data
    loadInitialData();
});
