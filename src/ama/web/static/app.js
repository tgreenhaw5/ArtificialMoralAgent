document.addEventListener("DOMContentLoaded", () => {
    // DOM Elements
    const dilemmaInput = document.getElementById("dilemma-input");
    const modelSelectWrapper = document.getElementById("model-select-wrapper");
    const modelSelect = document.getElementById("model-select");
    const submitBtn = document.getElementById("submit-btn");
    const submitBtnText = document.getElementById("submit-btn-text");
    const guestModeHint = document.getElementById("guest-mode-hint");
    const loadingSpinner = document.getElementById("loading-spinner");
    const loadingText = document.getElementById("loading-text");
    const crisisAlert = document.getElementById("crisis-alert");
    const resultsSection = document.getElementById("results-section");
    const mainWorkspace = document.getElementById("main-workspace");
    const homeLogoBtn = document.getElementById("home-logo-btn");

    const utilitarianRes = document.getElementById("utilitarian-res");
    const deontologyRes = document.getElementById("deontology-res");
    const virtueRes = document.getElementById("virtue-res");
    const careRes = document.getElementById("care-res");
    const verdictRes = document.getElementById("verdict-res");

    const utilitarianBadge = document.getElementById("utilitarian-badge");
    const deontologyBadge = document.getElementById("deontology-badge");
    const virtueBadge = document.getElementById("virtue-badge");
    const careBadge = document.getElementById("care-badge");
    const verdictCachedBadge = document.getElementById("verdict-cached-badge");
    const verdictModelBadge = document.getElementById("verdict-model-badge");

    const searchInput = document.getElementById("search-input");
    const searchBtn = document.getElementById("search-btn");
    const dilemmaList = document.getElementById("dilemma-list");

    // Modal Elements
    const aboutBtn = document.getElementById("about-btn");
    const aboutModal = document.getElementById("about-modal");
    const closeModalBtn = document.getElementById("close-modal-btn");
    const modalOkBtn = document.getElementById("modal-ok-btn");

    // Guest Pop-up Modal Elements
    const guestPopupModal = document.getElementById("guest-popup-modal");
    const closeGuestPopupBtn = document.getElementById("close-guest-popup-btn");
    const guestPopupOkBtn = document.getElementById("guest-popup-ok-btn");

    // Auth Elements
    const loginOpenBtn = document.getElementById("login-open-btn");
    const closeLoginBtn = document.getElementById("close-login-btn");
    const lockOverlay = document.getElementById("lock-overlay");
    const lockInput = document.getElementById("lock-input");
    const unlockBtn = document.getElementById("unlock-btn");
    const lockError = document.getElementById("lock-error");
    const lockBtn = document.getElementById("lock-btn");

    // Admin Review Screen Elements
    const reviewScreenBtn = document.getElementById("review-screen-btn");
    const pendingCountBadge = document.getElementById("pending-count-badge");
    const submissionsScreen = document.getElementById("submissions-screen");
    const submissionsTableContainer = document.getElementById("submissions-table-container");
    const backToMainBtn = document.getElementById("back-to-main-btn");
    const filterAllBtn = document.getElementById("filter-all-btn");
    const filterPendingBtn = document.getElementById("filter-pending-btn");
    const filterDoneBtn = document.getElementById("filter-done-btn");

    // Feedback Elements
    const thumbUpBtn = document.getElementById("thumb-up-btn");
    const thumbDownBtn = document.getElementById("thumb-down-btn");
    const feedbackAck = document.getElementById("feedback-ack");
    let currentDilemmaId = null;

    // Navigation Elements
    const kbNavBtn = document.getElementById("kb-nav-btn");
    const returnToTopBtn = document.getElementById("return-to-top-btn");

    // App State
    let isAuthenticated = false;
    let availableModels = ["gemini/gemini-3.5-flash-lite"];
    let currentSubmissionFilter = "all";

    // Helper to resolve API paths seamlessly whether at root '/' or reverse proxy subpath '/ama/'
    function getApiUrl(endpoint) {
        let base = window.location.pathname;
        if (!base.endsWith('/')) {
            base = base.substring(0, base.lastIndexOf('/') + 1);
        }
        const cleanEndpoint = endpoint.startsWith('/') ? endpoint.slice(1) : endpoint;
        return base + cleanEndpoint;
    }

    // Auth Helpers
    function getAuthToken() {
        return sessionStorage.getItem("ama_session_token");
    }

    function getAuthHeaders() {
        const headers = { "Content-Type": "application/json" };
        const token = getAuthToken();
        if (token) {
            headers["Authorization"] = `Bearer ${token}`;
        }
        return headers;
    }

    // Explicitly guarantee lock overlay is closed by default
    closeLoginModal();

    // Initial Boot
    checkAuthStatus();

    async function checkAuthStatus() {
        try {
            const res = await fetch(getApiUrl("/api/auth/status"), { headers: getAuthHeaders() });
            const data = await res.json();
            isAuthenticated = Boolean(data.authenticated);
            applyAuthUIState();
            fetchDilemmas();
            if (isAuthenticated) {
                await fetchModels();
                await fetchSubmissions();
            }
        } catch (e) {
            console.error("Auth check failed:", e);
            isAuthenticated = false;
            applyAuthUIState();
            fetchDilemmas();
        }
    }

    function applyAuthUIState() {
        // Ensure login modal is closed during state transitions
        closeLoginModal();

        if (isAuthenticated) {
            loginOpenBtn.classList.add("hidden");
            lockBtn.classList.remove("hidden");
            reviewScreenBtn.classList.remove("hidden");
            modelSelectWrapper.classList.remove("hidden");
            submitBtnText.textContent = "Evaluate Moral Dilemma";
            if (guestModeHint) {
                guestModeHint.textContent = "Logged in: Select an AI model and evaluate dilemmas immediately across all four ethical frameworks.";
            }
        } else {
            loginOpenBtn.classList.remove("hidden");
            lockBtn.classList.add("hidden");
            reviewScreenBtn.classList.add("hidden");
            modelSelectWrapper.classList.add("hidden");
            submissionsScreen.classList.add("hidden");
            mainWorkspace.classList.remove("hidden");
            submitBtnText.textContent = "Submit Moral Dilemma";
            if (guestModeHint) {
                guestModeHint.textContent = (window.AMA_CONFIG && window.AMA_CONFIG.public_demo)
                    ? `Public demo: up to ${window.AMA_CONFIG.demo_per_ip_per_day} free evaluations a day. Results stay private unless the site owner publishes them.`
                    : "Public Guest Mode: Submit a dilemma to our review queue, or log in to evaluate immediately.";
            }
        }
    }

    function openLoginModal() {
        lockOverlay.classList.remove("hidden");
        lockInput.value = "";
        lockError.style.opacity = "0";
        setTimeout(() => lockInput.focus(), 50);
    }

    function closeLoginModal() {
        lockOverlay.classList.add("hidden");
    }

    async function handleLogin() {
        const password = lockInput.value.trim();
        if (!password) return;
        
        unlockBtn.textContent = "Logging in...";
        unlockBtn.disabled = true;
        lockError.style.opacity = "0";
        
        try {
            const res = await fetch(getApiUrl("/api/auth/login"), {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ password, user: (document.getElementById("lock-user") || {}).value || undefined })
            });
            if (res.ok) {
                const data = await res.json();
                sessionStorage.setItem("ama_session_token", data.token);
                isAuthenticated = true;
                closeLoginModal();
                applyAuthUIState();
                await fetchModels();
                await fetchSubmissions();
            } else {
                lockError.textContent = "Wrong user name or password.";
                lockError.style.opacity = "1";
            }
        } catch (e) {
            lockError.textContent = "Network error. Try again.";
            lockError.style.opacity = "1";
        } finally {
            unlockBtn.textContent = "Log In";
            unlockBtn.disabled = false;
        }
    }

    async function handleLogout() {
        try {
            await fetch(getApiUrl("/api/auth/logout"), {
                method: "POST",
                headers: getAuthHeaders()
            });
        } catch (e) { }
        sessionStorage.removeItem("ama_session_token");
        isAuthenticated = false;
        applyAuthUIState();
    }

    // Auth Listeners
    loginOpenBtn.addEventListener("click", openLoginModal);
    closeLoginBtn.addEventListener("click", closeLoginModal);
    lockOverlay.addEventListener("click", (e) => {
        if (e.target === lockOverlay) closeLoginModal();
    });
    unlockBtn.addEventListener("click", handleLogin);
    lockInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter") handleLogin();
    });
    lockBtn.addEventListener("click", handleLogout);

    // Guest Pop-up Modal Controls
    function openGuestPopup() {
        guestPopupModal.classList.remove("hidden");
    }
    function closeGuestPopup() {
        guestPopupModal.classList.add("hidden");
    }
    closeGuestPopupBtn.addEventListener("click", closeGuestPopup);
    guestPopupOkBtn.addEventListener("click", closeGuestPopup);
    guestPopupModal.addEventListener("click", (e) => {
        if (e.target === guestPopupModal) closeGuestPopup();
    });

    // Screen Navigation (Main Workspace vs Submitted Dilemmas Review Screen)
    function showMainWorkspace() {
        submissionsScreen.classList.add("hidden");
        mainWorkspace.classList.remove("hidden");
    }

    function showSubmissionsScreen() {
        if (!isAuthenticated) {
            openLoginModal();
            return;
        }
        mainWorkspace.classList.add("hidden");
        submissionsScreen.classList.remove("hidden");
        fetchSubmissions();
    }

    reviewScreenBtn.addEventListener("click", () => {
        if (submissionsScreen.classList.contains("hidden")) {
            showSubmissionsScreen();
        } else {
            showMainWorkspace();
        }
    });
    backToMainBtn.addEventListener("click", showMainWorkspace);
    if (homeLogoBtn) {
        homeLogoBtn.addEventListener("click", showMainWorkspace);
    }

    // Filter Buttons on Review Screen
    function updateFilterButtons(activeBtn, filterVal) {
        currentSubmissionFilter = filterVal;
        [filterAllBtn, filterPendingBtn, filterDoneBtn].forEach(b => b.classList.remove("active-filter"));
        activeBtn.classList.add("active-filter");
        fetchSubmissions();
    }
    filterAllBtn.addEventListener("click", () => updateFilterButtons(filterAllBtn, "all"));
    filterPendingBtn.addEventListener("click", () => updateFilterButtons(filterPendingBtn, "pending"));
    filterDoneBtn.addEventListener("click", () => updateFilterButtons(filterDoneBtn, "done"));

    // Event Listeners
    submitBtn.addEventListener("click", handleSubmit);
    searchBtn.addEventListener("click", handleSearch);
    searchInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter") handleSearch();
    });

    kbNavBtn.addEventListener("click", () => {
        showMainWorkspace();
        const kbSection = document.getElementById("knowledge-base");
        if (kbSection) {
            kbSection.scrollIntoView({ behavior: "smooth" });
        }
    });

    returnToTopBtn.addEventListener("click", () => {
        window.scrollTo({ top: 0, behavior: "smooth" });
    });

    window.addEventListener("scroll", () => {
        if (window.scrollY > 300) {
            returnToTopBtn.classList.remove("hidden");
        } else {
            returnToTopBtn.classList.add("hidden");
        }
    });

    // About Modal Controls
    aboutBtn.addEventListener("click", () => aboutModal.classList.remove("hidden"));
    closeModalBtn.addEventListener("click", () => aboutModal.classList.add("hidden"));
    modalOkBtn.addEventListener("click", () => aboutModal.classList.add("hidden"));
    aboutModal.addEventListener("click", (e) => {
        if (e.target === aboutModal) aboutModal.classList.add("hidden");
    });
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            aboutModal.classList.add("hidden");
            closeGuestPopup();
            closeLoginModal();
        }
    });

    // Feedback Buttons
    thumbUpBtn.addEventListener("click", () => sendFeedback(1));
    thumbDownBtn.addEventListener("click", () => sendFeedback(-1));

    async function sendFeedback(rating) {
        if (!currentDilemmaId) return;
        try {
            const res = await fetch(getApiUrl(`/api/feedback/${currentDilemmaId}`), {
                method: "POST",
                headers: getAuthHeaders(),
                body: JSON.stringify({ rating })
            });
            if (!res.ok) return;
            feedbackAck.classList.remove("hidden");
            thumbUpBtn.style.opacity = rating === 1 ? "1" : "0.5";
            thumbDownBtn.style.opacity = rating === -1 ? "1" : "0.5";
        } catch (e) {
            console.error("Feedback error:", e);
        }
    }

    // ==========================================
    // DYNAMIC MODEL SELECTION (LOGGED IN ONLY)
    // ==========================================

    async function fetchModels() {
        if (!isAuthenticated) return;
        try {
            const res = await fetch(getApiUrl("/api/models"), { headers: getAuthHeaders() });
            if (!res.ok) return;
            const data = await res.json();
            availableModels = data.models || ["gemini-3.5-flash-lite"];
            const defaultModel = data.default || "gemini-3.5-flash-lite";

            modelSelect.innerHTML = "";
            availableModels.forEach(m => {
                const opt = document.createElement("option");
                opt.value = m;
                opt.textContent = m;
                if (m === defaultModel) {
                    opt.selected = true;
                }
                modelSelect.appendChild(opt);
            });
        } catch (err) {
            console.error("Failed to load models:", err);
        }
    }

    // ==========================================
    // SUBMIT OR EVALUATE DILEMMA
    // ==========================================

    async function handleSubmit() {
        const text = dilemmaInput.value.trim();
        if (!text || text.length < 10) {
            alert("Please enter a detailed moral dilemma (at least 10 characters).");
            return;
        }

        // GUEST FLOW: Submit to DB without evaluating and show pop-up
        // (with the public demo enabled, guests get a full evaluation instead, within daily limits)
        if (!isAuthenticated && !(window.AMA_CONFIG && window.AMA_CONFIG.public_demo)) {
            submitBtn.disabled = true;
            submitBtnText.textContent = "Saving Dilemma...";
            try {
                const response = await fetch(getApiUrl("/api/dilemmas"), {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ dilemma_text: text })
                });
                if (!response.ok) {
                    const err = await response.json();
                    throw new Error(err.detail || "Failed to submit dilemma.");
                }
                dilemmaInput.value = "";
                openGuestPopup();
            } catch (error) {
                alert("Error: " + error.message);
            } finally {
                submitBtn.disabled = false;
                submitBtnText.textContent = "Submit Moral Dilemma";
            }
            return;
        }

        // LOGGED-IN USER FLOW: Full 2-Stage DAG Evaluation
        const selectedModel = modelSelect.value || ((window.AMA_CONFIG && window.AMA_CONFIG.default_model) || "gemini/gemini-3.5-flash-lite");

        resultsSection.classList.add("hidden");
        crisisAlert.classList.add("hidden");
        loadingSpinner.classList.remove("hidden");
        loadingText.textContent = `Executing 2-Stage Directed Acyclic Graph with ${selectedModel}: Concurrently querying Utilitarianism, Deontology, Care Ethics & the 6-Sage Council with Conviction Weights...`;
        submitBtn.disabled = true;
        feedbackAck.classList.add("hidden");
        thumbUpBtn.style.opacity = "1";
        thumbDownBtn.style.opacity = "1";

        let isProcessing = true;
        const scrollTimer = setTimeout(() => {
            if (isProcessing) {
                loadingSpinner.scrollIntoView({ behavior: "smooth", block: "center" });
            }
        }, 300);

        try {
            const response = await fetch(getApiUrl("/api/dilemmas"), {
                method: "POST",
                headers: getAuthHeaders(),
                body: JSON.stringify({
                    dilemma_text: text,
                    model: selectedModel
                })
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || "Failed to analyze dilemma.");
            }

            const data = await response.json();
            isProcessing = false;
            clearTimeout(scrollTimer);

            if (data.is_crisis) {
                renderCrisisAlert(data);
            } else if (data.queued) {
                openGuestPopup();
                if (data.message && window.amaShowNotice) window.amaShowNotice(data.message);
            } else {
                currentDilemmaId = data.id;
                displayResults(data);
                if (window.amaShowDisclaimer) window.amaShowDisclaimer(data);
                fetchDilemmas();
                if (isAuthenticated) fetchSubmissions();
            }
        } catch (error) {
            alert("Error: " + error.message);
        } finally {
            isProcessing = false;
            clearTimeout(scrollTimer);
            loadingSpinner.classList.add("hidden");
            submitBtn.disabled = false;
        }
    }

    // ==========================================
    // ADMIN REVIEW SCREEN: SUBMISSIONS QUEUE
    // ==========================================

    async function fetchSubmissions() {
        if (!isAuthenticated) return;
        try {
            const filterParam = currentSubmissionFilter !== "all" ? `?status_filter=${currentSubmissionFilter}` : "";
            const res = await fetch(getApiUrl(`/api/submissions${filterParam}`), { headers: getAuthHeaders() });
            if (!res.ok) return;
            const items = await res.json();

            // Update pending count badge
            if (currentSubmissionFilter === "all") {
                const pendingCount = items.filter(i => i.status === "pending").length;
                if (pendingCount > 0) {
                    pendingCountBadge.textContent = pendingCount;
                    pendingCountBadge.classList.remove("hidden");
                } else {
                    pendingCountBadge.classList.add("hidden");
                }
            }

            renderSubmissionsList(items);
        } catch (err) {
            console.error("Failed to fetch submissions:", err);
        }
    }

    function renderSubmissionsList(items) {
        submissionsTableContainer.innerHTML = "";
        if (!items || items.length === 0) {
            submissionsTableContainer.innerHTML = `<p class="loading-text" style="text-align:center; padding: 2rem;">No submitted dilemmas found for this filter.</p>`;
            return;
        }

        items.forEach(item => {
            const isPending = item.status === "pending";
            const statusClass = isPending ? "status-pending" : "status-done";
            const statusLabel = isPending ? "Pending Review" : "Done";
            const dateStr = item.created_at ? new Date(item.created_at).toLocaleString() : "";
            const hasVerdict = Boolean(item.verdict);

            const row = document.createElement("div");
            row.className = "submission-row";

            // Build model selector for this submission row
            const modelOptionsHtml = availableModels.map(m => {
                const sel = (item.model_details && item.model_details === m) || (!item.model_details && m === "gemini-3.5-flash-lite") ? "selected" : "";
                return `<option value="${escapeHtml(m)}" ${sel}>${escapeHtml(m)}</option>`;
            }).join("");

            row.innerHTML = `
                <div class="submission-info">
                    <div class="submission-meta">
                        <span class="status-pill ${statusClass}">${statusLabel}</span>
                        <span class="badge-model">${escapeHtml(item.model_details || "Pending Evaluation")}</span>
                        <span>Submitted: ${escapeHtml(dateStr)}</span>
                    </div>
                    <div class="submission-text">${escapeHtml(item.dilemma_text)}</div>
                </div>
                <div class="submission-actions">
                    <select class="glass-select row-model-select" aria-label="Model for evaluation">
                        ${modelOptionsHtml}
                    </select>
                    <button class="glass-btn primary-btn small-btn row-eval-btn">
                        ⚡ Evaluate
                    </button>
                    ${isPending ? `
                        <button class="glass-btn btn-success small-btn row-done-btn">
                            ✓ Mark as Done
                        </button>
                    ` : ""}
                    ${hasVerdict ? `
                        <button class="glass-btn secondary-btn small-btn row-view-btn">
                            👁️ View Verdict
                        </button>
                    ` : ""}
                </div>
            `;

            const rowModelSelect = row.querySelector(".row-model-select");
            const evalBtn = row.querySelector(".row-eval-btn");
            const doneBtn = row.querySelector(".row-done-btn");
            const viewBtn = row.querySelector(".row-view-btn");

            evalBtn.addEventListener("click", async () => {
                const chosenModel = rowModelSelect.value || "gemini-3.5-flash-lite";
                evalBtn.disabled = true;
                evalBtn.textContent = "⏳ Evaluating...";
                try {
                    const res = await fetch(getApiUrl(`/api/submissions/${item.id}/evaluate`), {
                        method: "POST",
                        headers: getAuthHeaders(),
                        body: JSON.stringify({ model: chosenModel })
                    });
                    if (!res.ok) {
                        const err = await res.json();
                        throw new Error(err.detail || "Evaluation failed.");
                    }
                    const evaluatedData = await res.json();
                    await fetchSubmissions();
                    await fetchDilemmas();

                    // Switch to Main Workspace and display the newly evaluated results
                    showMainWorkspace();
                    dilemmaInput.value = item.dilemma_text;
                    if (evaluatedData.is_crisis) {
                        renderCrisisAlert(evaluatedData);
                    } else {
                        currentDilemmaId = evaluatedData.id;
                        displayResults(evaluatedData);
                    }
                } catch (e) {
                    alert("Evaluation Error: " + e.message);
                    evalBtn.disabled = false;
                    evalBtn.textContent = "⚡ Evaluate";
                }
            });

            if (doneBtn) {
                doneBtn.addEventListener("click", async () => {
                    doneBtn.disabled = true;
                    doneBtn.textContent = "Marking...";
                    try {
                        const res = await fetch(getApiUrl(`/api/submissions/${item.id}/done`), {
                            method: "POST",
                            headers: getAuthHeaders()
                        });
                        if (!res.ok) throw new Error("Failed to mark as done.");
                        await fetchSubmissions();
                        await fetchDilemmas();
                    } catch (e) {
                        alert(e.message);
                        doneBtn.disabled = false;
                        doneBtn.textContent = "✓ Mark as Done";
                    }
                });
            }

            if (viewBtn) {
                viewBtn.addEventListener("click", () => {
                    showMainWorkspace();
                    dilemmaInput.value = item.dilemma_text;
                    currentDilemmaId = item.id;
                    displayResults(item);
                });
            }

            submissionsTableContainer.appendChild(row);
        });
    }

    // ==========================================
    // CRISIS & RESULTS RENDERERS
    // ==========================================

    function renderCrisisAlert(data) {
        let hotlinesHtml = "";
        if (data.hotlines && data.hotlines.length > 0) {
            hotlinesHtml = data.hotlines.map(h => `
                <div class="crisis-hotline-item">
                    <div class="crisis-hotline-name">${escapeHtml(h.name)}</div>
                    <div class="crisis-hotline-contact">${escapeHtml(h.contact)}</div>
                </div>
            `).join("");
        }

        crisisAlert.innerHTML = `
            <div class="crisis-header">
                <span class="crisis-icon">🚨</span>
                <h3>Emergency &amp; Crisis Support Detected</h3>
            </div>
            <p class="crisis-text">${escapeHtml(data.disclaimer || "If you or someone you know is in acute danger, please reach out for help immediately.")}</p>
            <div class="crisis-hotlines">
                ${hotlinesHtml}
            </div>
        `;
        crisisAlert.classList.remove("hidden");
        crisisAlert.scrollIntoView({ behavior: "smooth" });
    }

    function displayResults(data) {
        if (!data || !data.verdict) return;

        if (verdictModelBadge) {
            verdictModelBadge.textContent = data.model_details || modelSelect.value;
        }

        if (data.cached) {
            verdictCachedBadge.textContent = data.cache_type === "exact_match"
                ? "⚡ Retrieved from Database (Exact Match)"
                : "⚡ Retrieved from Database (PGVector Cache)";
            verdictCachedBadge.classList.remove("hidden");
        } else {
            verdictCachedBadge.classList.add("hidden");
        }

        renderVerdict(data.verdict);
        renderUtilitarian(data.utilitarian_response);
        renderDeontology(data.deontology_response);
        renderVirtueEthics(data.virtue_ethics_response);
        renderCareEthics(data.care_ethics_response);

        resultsSection.classList.remove("hidden");
        resultsSection.scrollIntoView({ behavior: "smooth" });
    }

    function renderVerdict(verdict) {
        if (!verdict) return;
        if (typeof verdict === "string") {
            try {
                verdict = JSON.parse(verdict);
            } catch {
                verdictRes.innerHTML = `<div class="markdown-content">${typeof marked !== "undefined" ? marked.parse(verdict) : escapeHtml(verdict)}</div>`;
                return;
            }
        }

        let convictionsHtml = "";
        if (verdict.framework_convictions) {
            const fc = verdict.framework_convictions;
            const frameworksList = [
                { key: "utilitarianism", label: "Utilitarianism", icon: "📊" },
                { key: "deontology", label: "Deontology", icon: "📜" },
                { key: "care_ethics", label: "Care Ethics", icon: "🤝" },
                { key: "virtue_ethics", label: "Virtue Council", icon: "🏛️" }
            ];

            const itemsHtml = frameworksList.map(item => {
                const data = fc[item.key] || {};
                const weight = data.weight !== undefined ? Number(data.weight).toFixed(1) : "-";
                const action = data.action || "Recommended Action";
                const rationale = data.rationale || "";
                return `
                    <div class="conviction-item">
                        <div class="conviction-item-header">
                            <span class="conviction-framework-name">${item.icon} ${item.label}</span>
                            <span class="conviction-weight-badge">Conviction: ${weight} / 10</span>
                        </div>
                        <div class="conviction-action">${escapeHtml(action)}</div>
                        <div class="conviction-rationale">${escapeHtml(rationale)}</div>
                    </div>
                `;
            }).join("");

            convictionsHtml = `
                <div class="info-block">
                    <div class="info-block-title">Framework Decision Conviction Weights (1 to 10 Scale)</div>
                    <div class="conviction-grid">
                        ${itemsHtml}
                    </div>
                </div>
            `;
        }

        let moralDutyHtml = "";
        if (verdict.collective_moral_duty) {
            const isHighAlignment = verdict.alignment_status === "High Alignment" || !verdict.dissenting_perspectives || verdict.dissenting_perspectives.length === 0;
            const bannerTitle = isHighAlignment ? "🌟 Unified Collective Moral Duty (High Framework Alignment)" : "⚖️ Core Shared Moral Ground";
            moralDutyHtml = `
                <div class="moral-duty-banner">
                    <div class="moral-duty-banner-title">${bannerTitle}</div>
                    <p class="moral-duty-text">${escapeHtml(verdict.collective_moral_duty)}</p>
                </div>
            `;
        }

        let majorityHtml = "";
        if (verdict.majority_response) {
            const maj = verdict.majority_response;
            const combinedWeight = maj.combined_weight !== undefined ? `Combined Weight: ${Number(maj.combined_weight).toFixed(1)}` : "";
            majorityHtml = `
                <div class="majority-action-card">
                    <div class="majority-header">
                        <span class="majority-title">Leading Course of Action (Sorted by Conviction Weight)</span>
                        ${combinedWeight ? `<span class="majority-badge">${combinedWeight}</span>` : ""}
                    </div>
                    <div class="majority-action-text">${escapeHtml(maj.action || "")}</div>
                    <p style="color: #cbd5e1; font-size: 0.9rem;">${escapeHtml(maj.plain_english_summary || "")}</p>
                </div>
            `;
        }

        let dissentingHtml = "";
        if (verdict.dissenting_perspectives && Array.isArray(verdict.dissenting_perspectives) && verdict.dissenting_perspectives.length > 0) {
            const cardsHtml = verdict.dissenting_perspectives.map(d => `
                <div class="dissent-card">
                    <div class="dissent-header">
                        <span>⚠️ ${escapeHtml(d.framework || "Dissenting Framework")}</span>
                        <span class="dissent-badge">Weight: ${d.weight !== undefined ? Number(d.weight).toFixed(1) : "-"} / 10</span>
                    </div>
                    ${d.alternate_action ? `<div style="font-weight: 600; color: #ffffff; font-size: 0.85rem;">Alternate Recommendation: ${escapeHtml(d.alternate_action)}</div>` : ""}
                    <p class="dissent-perspective">${escapeHtml(d.perspective || "")}</p>
                </div>
            `).join("");

            dissentingHtml = `
                <div class="info-block">
                    <div class="info-block-title" style="color: #fca5a5;">Dissenting Moral Perspectives &amp; Alternate Courses</div>
                    <div class="dissent-grid">
                        ${cardsHtml}
                    </div>
                </div>
            `;
        }

        let stepsHtml = "";
        if (verdict.actionable_guidance && Array.isArray(verdict.actionable_guidance)) {
            stepsHtml = `
                <div class="info-block">
                    <div class="info-block-title">Actionable Moral Guidance (Plain English Steps)</div>
                    <ul class="guidance-steps">
                        ${verdict.actionable_guidance.map(step => `<li>${escapeHtml(step)}</li>`).join("")}
                    </ul>
                </div>
            `;
        }

        verdictRes.innerHTML = `
            <div class="verdict-title-banner">
                ${escapeHtml(verdict.verdict_title || "Chief Moral Arbiter Verdict")}
            </div>

            ${moralDutyHtml}
            ${majorityHtml}
            
            <div class="info-block">
                <div class="info-block-title">Conflict-Resolution Principle Applied</div>
                <p><strong>${escapeHtml(verdict.conflict_resolution_principle_applied || "Weighted Conviction Blend")}</strong></p>
                ${verdict.principle_explanation ? `<p style="margin-top: 0.3rem; color: var(--text-muted); font-size: 0.9rem;">${escapeHtml(verdict.principle_explanation)}</p>` : ""}
            </div>

            ${convictionsHtml}
            ${dissentingHtml}

            <div class="info-block">
                <div class="info-block-title">Definitive Ruling (Plain English)</div>
                <p style="font-size: 1.05rem; font-weight: 500; color: #ffffff;">${escapeHtml(verdict.definitive_ruling || "")}</p>
            </div>

            ${stepsHtml}
        `;
    }

    function renderUtilitarian(data) {
        if (!data) return;
        if (typeof data === "string") {
            try { data = JSON.parse(data); } catch {
                utilitarianRes.innerHTML = escapeHtml(data);
                return;
            }
        }

        const score = data.score !== undefined ? data.score : "-";
        const conviction = data.conviction_score !== undefined ? ` • Conviction: ${data.conviction_score}/10` : "";
        utilitarianBadge.innerText = `${score} / 10${conviction}`;
        utilitarianBadge.setAttribute("aria-label", `Utilitarian Score ${score} out of 10`);

        let alternativesHtml = "";
        if (data.alternative_actions_evaluated && Array.isArray(data.alternative_actions_evaluated)) {
            alternativesHtml = `
                <div class="info-block">
                    <div class="info-block-title">Candidate Actions &amp; Calculus (V = D &times; N &times; T &times; P)</div>
                    <table class="alternatives-table">
                        <thead>
                            <tr>
                                <th>Action</th>
                                <th>D</th>
                                <th>N</th>
                                <th>T (days)</th>
                                <th>P</th>
                                <th>Net V</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${data.alternative_actions_evaluated.map(alt => {
                                const vClass = alt.net_v >= 0 ? "net-v-positive" : "net-v-negative";
                                return `
                                    <tr>
                                        <td><strong>${escapeHtml(alt.action_name || "")}</strong><br><small style="color:var(--text-dim);">${escapeHtml(alt.analysis || "")}</small></td>
                                        <td>${alt.d_pleasure_pain ?? "-"}</td>
                                        <td>${alt.n_affected ?? "-"}</td>
                                        <td>${alt.t_duration_days ?? "-"}</td>
                                        <td>${alt.p_probability ?? "-"}</td>
                                        <td class="${vClass}">${alt.net_v !== undefined ? Number(alt.net_v).toFixed(1) : "-"}</td>
                                    </tr>
                                `;
                            }).join("")}
                        </tbody>
                    </table>
                </div>
            `;
        }

        utilitarianRes.innerHTML = `
            ${alternativesHtml}
            <div class="info-block">
                <div class="info-block-title">Recommended Action &amp; Conviction Weight</div>
                <p><strong>${escapeHtml(data.recommended_action || data.optimal_action || "Standard Action")}</strong></p>
                ${data.conviction_rationale ? `<p style="margin-top:0.3rem; color:var(--text-muted); font-size:0.85rem;"><em>Conviction Rationale:</em> ${escapeHtml(data.conviction_rationale)}</p>` : ""}
            </div>
            <div class="info-block">
                <div class="info-block-title">Consequentialist Plain English Summary</div>
                <p>${escapeHtml(data.consequentialist_summary || "")}</p>
            </div>
        `;
    }

    function renderDeontology(data) {
        if (!data) return;
        if (typeof data === "string") {
            try { data = JSON.parse(data); } catch {
                deontologyRes.innerHTML = escapeHtml(data);
                return;
            }
        }

        const score = data.score !== undefined ? data.score : "-";
        const conviction = data.conviction_score !== undefined ? ` • Conviction: ${data.conviction_score}/10` : "";
        deontologyBadge.innerText = `${score} / 10${conviction}`;
        deontologyBadge.setAttribute("aria-label", `Deontology Score ${score} out of 10`);

        const renderDutyList = (duties) => {
            if (!duties || duties.length === 0) return `<p style="color:var(--text-dim);">None identified</p>`;
            return `
                <ul class="duty-list">
                    ${duties.map(d => `
                        <li>
                            <span class="duty-tag ${d.type === 'Perfect' ? 'duty-perfect' : 'duty-imperfect'}">${escapeHtml(d.type || 'Duty')}</span>
                            <strong>${escapeHtml(d.duty || "")}</strong>: ${escapeHtml(d.justification || "")}
                        </li>
                    `).join("")}
                </ul>
            `;
        };

        deontologyRes.innerHTML = `
            <div class="info-block">
                <div class="info-block-title">Recommended Action &amp; Conviction Weight</div>
                <p><strong>${escapeHtml(data.recommended_action || data.permissibility || "Permissible")}</strong></p>
                ${data.conviction_rationale ? `<p style="margin-top:0.3rem; color:var(--text-muted); font-size:0.85rem;"><em>Conviction Rationale:</em> ${escapeHtml(data.conviction_rationale)}</p>` : ""}
            </div>
            <div class="info-block">
                <div class="info-block-title">Duties Upheld</div>
                ${renderDutyList(data.duties_upheld)}
            </div>
            <div class="info-block">
                <div class="info-block-title">Duties Violated</div>
                ${renderDutyList(data.duties_violated)}
            </div>
            <div class="info-block">
                <div class="info-block-title">Categorical Imperatives Assessment</div>
                <p><strong>Universal Law:</strong> ${escapeHtml(data.categorical_imperatives?.universal_law || "")}</p>
                <p style="margin-top:0.3rem;"><strong>Formula of Humanity:</strong> ${escapeHtml(data.categorical_imperatives?.formula_of_humanity || "")}</p>
                <p style="margin-top:0.3rem;"><strong>Kingdom of Ends:</strong> ${escapeHtml(data.categorical_imperatives?.kingdom_of_ends || "")}</p>
            </div>
            <div class="info-block">
                <div class="info-block-title">Kantian Plain English Summary</div>
                <p>${escapeHtml(data.deontological_summary || "")}</p>
            </div>
        `;
    }

    function renderVirtueEthics(data) {
        if (!data) return;
        if (typeof data === "string") {
            try { data = JSON.parse(data); } catch {
                virtueRes.innerHTML = escapeHtml(data);
                return;
            }
        }

        const score = data.score !== undefined ? data.score : "-";
        const conviction = data.conviction_score !== undefined ? ` • Conviction: ${data.conviction_score}/10` : "";
        virtueBadge.innerText = `${score} / 10${conviction}`;
        virtueBadge.setAttribute("aria-label", `Virtue Ethics Score ${score} out of 10`);

        let sagesHtml = "";
        if (data.sages && Array.isArray(data.sages)) {
            sagesHtml = `
                <div class="sage-grid">
                    ${data.sages.map(s => {
                        const rawName = s.name || '';
                        const displayName = rawName.replace(/^AI\s+/i, 'Inspired by ');
                        const voteClass = s.vote === 'support' ? 'vote-support' : (s.vote === 'reject' ? 'vote-reject' : 'vote-abstain');
                        return `
                            <div class="sage-card">
                                <div class="sage-header">
                                    <span class="sage-name">${escapeHtml(displayName)}</span>
                                    <span class="vote-badge ${voteClass}">${escapeHtml(s.vote || 'vote')}</span>
                                </div>
                                <div style="font-size:0.75rem; color:var(--accent-cyan);">${escapeHtml(s.core_virtue || "")}</div>
                                <div class="sage-counsel">${escapeHtml(s.counsel || "")}</div>
                            </div>
                        `;
                    }).join("")}
                </div>
            `;
        }

        const tally = data.council_vote_tally || {};
        const tallyText = `Support: ${tally.support ?? 0} &bull; Reject: ${tally.reject ?? 0} &bull; Abstain: ${tally.abstain ?? 0}`;

        virtueRes.innerHTML = `
            <div class="info-block">
                <div class="info-block-title">Council Recommended Action &amp; Conviction Weight</div>
                <p><strong>${escapeHtml(data.recommended_action || "Virtuous Guidance")}</strong></p>
                ${data.conviction_rationale ? `<p style="margin-top:0.3rem; color:var(--text-muted); font-size:0.85rem;"><em>Conviction Rationale:</em> ${escapeHtml(data.conviction_rationale)}</p>` : ""}
            </div>
            <div class="info-block">
                <div class="info-block-title">Council Vote Tally (${tallyText})</div>
                ${sagesHtml}
            </div>
            <div class="info-block">
                <div class="info-block-title">Council Majority Consensus</div>
                <p>${escapeHtml(data.majority_consensus || "")}</p>
            </div>
            <div class="info-block">
                <div class="info-block-title">Dissenting Rebuttal &amp; Council Perspectives</div>
                <p>${escapeHtml(data.dissenting_rebuttal || "")}</p>
            </div>
        `;
    }

    function renderCareEthics(data) {
        if (!data) return;
        if (typeof data === "string") {
            try { data = JSON.parse(data); } catch {
                careRes.innerHTML = escapeHtml(data);
                return;
            }
        }

        const score = data.score !== undefined ? data.score : "-";
        const conviction = data.conviction_score !== undefined ? ` • Conviction: ${data.conviction_score}/10` : "";
        careBadge.innerText = `${score} / 10${conviction}`;
        careBadge.setAttribute("aria-label", `Care Ethics Score ${score} out of 10`);

        let stakeholdersHtml = "";
        if (data.vulnerable_stakeholders && Array.isArray(data.vulnerable_stakeholders)) {
            stakeholdersHtml = `
                <div class="info-block">
                    <div class="info-block-title">Vulnerable &amp; Dependent Stakeholders</div>
                    <ul class="duty-list">
                        ${data.vulnerable_stakeholders.map(st => `
                            <li><strong>${escapeHtml(st.stakeholder || "")}</strong>: ${escapeHtml(st.vulnerability_nature || "")}</li>
                        `).join("")}
                    </ul>
                </div>
            `;
        }

        careRes.innerHTML = `
            <div class="info-block">
                <div class="info-block-title">Recommended Action &amp; Conviction Weight</div>
                <p><strong>${escapeHtml(data.recommended_action || "Protect Vulnerable and Preserve Relationships")}</strong></p>
                ${data.conviction_rationale ? `<p style="margin-top:0.3rem; color:var(--text-muted); font-size:0.85rem;"><em>Conviction Rationale:</em> ${escapeHtml(data.conviction_rationale)}</p>` : ""}
            </div>
            ${stakeholdersHtml}
            <div class="info-block">
                <div class="info-block-title">Relational Impact &amp; Human Bonds</div>
                <p>${escapeHtml(data.relational_impact || "")}</p>
            </div>
            <div class="info-block">
                <div class="info-block-title">Emotional &amp; Dependency Needs</div>
                <p>${escapeHtml(data.emotional_and_dependency_needs || "")}</p>
            </div>
            <div class="info-block">
                <div class="info-block-title">Care Ethics Plain English Synthesis</div>
                <p>${escapeHtml(data.care_ethics_summary || "")}</p>
            </div>
        `;
    }

    // ==========================================
    // REPOSITORY & VECTOR SEARCH (PUBLIC)
    // ==========================================

    async function fetchDilemmas() {
        try {
            const response = await fetch(getApiUrl("/api/dilemmas?limit=12"), { headers: getAuthHeaders() });
            if (!response.ok) return;
            const dilemmas = await response.json();
            renderDilemmaList(dilemmas);
        } catch (error) {
            console.error("Failed to fetch dilemmas:", error);
        }
    }

    async function handleSearch() {
        const query = searchInput.value.trim();
        if (!query) {
            fetchDilemmas();
            return;
        }

        try {
            const response = await fetch(getApiUrl(`/api/search?q=${encodeURIComponent(query)}&limit=6`), { headers: getAuthHeaders() });
            if (!response.ok) return;
            const results = await response.json();
            renderDilemmaList(results, true);
        } catch (error) {
            console.error("Search failed:", error);
        }
    }

    function renderDilemmaList(dilemmas, isSearch = false) {
        dilemmaList.innerHTML = "";

        if (dilemmas.length === 0) {
            dilemmaList.innerHTML = `<p class="loading-text" style="text-align: center;">${isSearch ? "No matching dilemmas found in PGVector index." : "No evaluated dilemmas recorded yet."}</p>`;
            return;
        }

        dilemmas.forEach(item => {
            const dateStr = item.created_at ? new Date(item.created_at).toLocaleString() : "";
            const modelName = item.model_details || "gemini-3.5-flash-lite";
            const el = document.createElement("div");
            el.className = "dilemma-item";
            el.innerHTML = `
                <div class="dilemma-item-header">
                    <span class="badge-sm">${escapeHtml(modelName)}</span>
                    <span>${dateStr}</span>
                </div>
                <div class="dilemma-item-text">${escapeHtml(item.dilemma_text)}</div>
            `;
            el.addEventListener("click", () => {
                dilemmaInput.value = item.dilemma_text;
                for (let i = 0; i < modelSelect.options.length; i++) {
                    if (modelSelect.options[i].value === item.model_details) {
                        modelSelect.selectedIndex = i;
                        break;
                    }
                }
                currentDilemmaId = item.id;
                displayResults(item);
            });
            dilemmaList.appendChild(el);
        });
    }

    function escapeHtml(str) {
        if (!str) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }
});