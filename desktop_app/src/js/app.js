// Main Desktop UI Logic, Tauri Window Controls, Collapsible Sidebar, and API Calls

const API_BASE = "http://127.0.0.1:8000";

document.addEventListener("DOMContentLoaded", () => {
  const sidebar = document.getElementById("sidebar");
  const btnCollapseSidebar = document.getElementById("btn-collapse-sidebar");
  const btnToggleSidebar = document.getElementById("btn-toggle-sidebar");
  const chatHistory = document.getElementById("chat-history");
  const chatForm = document.getElementById("chat-form");
  const userInput = document.getElementById("user-input");
  const chatMode = document.getElementById("chat-mode");
  const chkApproval = document.getElementById("chk-human-approval");
  const btnClearChat = document.getElementById("btn-clear-chat");
  const btnViewAudit = document.getElementById("btn-view-audit");

  // Helper: Smart Auto-Scroll Anchoring (Claude / Linear standard)
  function smartScroll(container) {
    if (!container) return;
    const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
    if (distanceFromBottom < 120) {
      container.scrollTop = container.scrollHeight;
    }
  }

  // Helper: Safe HTML Entity Escaping
  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // 0. Multi-Model Selector
  const modelSelector = document.getElementById("model-selector");
  if (modelSelector) {
    modelSelector.addEventListener("change", async () => {
      const selectedId = modelSelector.value;
      try {
        const res = await fetch(`${API_BASE}/models/switch`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ model_id: selectedId })
        });
        const data = await res.json();
        if (res.ok) {
          appendMessage("ai", `🔄 **Model Değiştirildi:** \`${data.active_model.name}\`\n${data.active_model.recommended_for}`);
        } else {
          alert("Model değiştirme hatası: " + data.detail);
        }
      } catch (err) {
        console.error("Model switch error:", err);
      }
    });

    // Sayfa açıldığında donanıma göre önerilen modeli kontrol et
    fetch(`${API_BASE}/models/hardware`)
      .then(res => res.json())
      .then(hw => {
        if (hw.recommended_model_id && modelSelector.value !== hw.recommended_model_id) {
          modelSelector.value = hw.recommended_model_id;
        }
      })
      .catch(() => {});
  }

  // 0.1 Model Hub Modal & Streaming Downloader
  const btnOpenModelHub = document.getElementById("btn-open-model-hub");
  const modelHubModal = document.getElementById("model-hub-modal");
  const btnCloseModelHub = document.getElementById("btn-close-model-hub");
  const hubSearchInput = document.getElementById("hub-search-input");
  const btnHubSearch = document.getElementById("btn-hub-search");
  const hubResultsGrid = document.getElementById("hub-results-grid");
  const hubDownloadBox = document.getElementById("hub-download-status-box");
  const hubDownloadTitle = document.getElementById("hub-download-title");
  const hubDownloadStats = document.getElementById("hub-download-stats");
  const hubProgressBar = document.getElementById("hub-download-progress-bar");

  async function searchHuggingFaceHub(query) {
    if (!query) return;
    hubResultsGrid.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; color: var(--accent-cyan); padding: 30px 0;">🔍 HuggingFace modelleri aranıyor...</div>`;
    try {
      const res = await fetch(`${API_BASE}/models/hub/search?query=${encodeURIComponent(query)}`);
      const data = await res.json();
      if (!Array.isArray(data) || data.length === 0) {
        hubResultsGrid.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; color: var(--text-dim); padding: 30px 0;">Hiç model bulunamadı. Farklı bir arama deneyin.</div>`;
        return;
      }
      hubResultsGrid.innerHTML = data.map(item => {
        const repo = item.id;
        const quant = item.recommended_quant || (repo.split('/')[1] ? repo.split('/')[1].toLowerCase() + "-q4_k_m.gguf" : "model-q4.gguf");
        return `
          <div class="hub-card">
            <div>
              <div class="hub-card-title">${repo}</div>
              <div class="hub-card-author">Geliştirici: ${item.author || "Community"}</div>
              <div class="hub-card-meta">
                <span>${(item.downloads || 0).toLocaleString()} indirme</span>
                <span>·</span>
                <span>${quant}</span>
              </div>
            </div>
            <button class="btn-pull-model" data-repo="${repo}" data-file="${quant}" style="background: var(--bg-surface-elevated); color: var(--text-main); font-weight: 500; border: 1px solid var(--border-hairline); padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 0.74rem; width: 100%; transition: all 0.15s;">
              İndir
            </button>
          </div>
        `;
      }).join('');

      document.querySelectorAll(".btn-pull-model").forEach(btn => {
        btn.addEventListener("click", async () => {
          if (btn.disabled) return;
          btn.disabled = true;
          btn.style.opacity = "0.5";
          const repo = btn.getAttribute("data-repo");
          const file = btn.getAttribute("data-file");
          try {
            await pullModelStreaming(repo, file);
          } finally {
            btn.disabled = false;
            btn.style.opacity = "1";
          }
        });
      });
    } catch (err) {
      hubResultsGrid.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; color: var(--accent-red); padding: 30px 0;">Arama hatası: ${err.message}</div>`;
    }
  }

  async function pullModelStreaming(repo, filename) {
    hubDownloadBox.style.display = "block";
    hubDownloadTitle.textContent = `İndiriliyor: ${repo} (${filename})`;
    hubDownloadStats.textContent = "Bağlantı kuruluyor...";
    hubProgressBar.style.width = "0%";

    try {
      const response = await fetch(`${API_BASE}/models/pull`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo: repo, filename: filename })
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split("\n");

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const dataStr = line.slice(6).trim();
            if (!dataStr) continue;
            try {
              const event = JSON.parse(dataStr);
              if (event.status === "downloading") {
                const pct = event.progress || 0;
                hubProgressBar.style.width = `${pct}%`;
                hubDownloadStats.textContent = `${pct}% • ${event.speed_mb || 0} MB/s • İndirilen: ${event.downloaded_gb || 0} GB`;
              } else if (event.status === "completed") {
                hubProgressBar.style.width = "100%";
                hubDownloadStats.textContent = "✅ Tamamlandı ve kataloğa eklendi!";
                appendMessage("ai", `🎉 **Yeni Model İndirildi ve Kataloğa Eklendi:** \`${event.model_id || filename}\`\nArtık model seçiciden doğrudan bu modeli seçebilirsiniz.`);
                refreshModelSelector();
              }
            } catch (e) {}
          }
        }
      }
    } catch (err) {
      hubDownloadStats.textContent = `⚠️ Hata: ${err.message}`;
    }
  }

  async function refreshModelSelector() {
    try {
      const res = await fetch(`${API_BASE}/models`);
      if (res.ok) {
        const models = await res.json();
        if (modelSelector) {
          modelSelector.innerHTML = models.map(m => `
            <option value="${m.id}">${m.id === "qwen2.5-coder-7b" ? "🧠" : "⚡"} ${m.name} (${m.disk_size_gb} GB)</option>
          `).join('');
        }
      }
    } catch (e) {}
  }

  if (btnOpenModelHub) {
    btnOpenModelHub.addEventListener("click", () => {
      modelHubModal.style.display = "flex";
      searchHuggingFaceHub(hubSearchInput.value.trim() || "qwen");
    });
  }

  if (btnCloseModelHub) {
    btnCloseModelHub.addEventListener("click", () => {
      modelHubModal.style.display = "none";
    });
  }

  if (btnHubSearch) {
    btnHubSearch.addEventListener("click", () => {
      searchHuggingFaceHub(hubSearchInput.value.trim());
    });
  }

  // 1. Frameless Window Controls (Tauri or Browser fallback)
  const winMin = document.getElementById("win-min");
  const winMax = document.getElementById("win-max");
  const winClose = document.getElementById("win-close");

  if (window.__TAURI__ && window.__TAURI__.window) {
    const appWindow = window.__TAURI__.window.getCurrentWindow();
    winMin.addEventListener("click", () => appWindow.minimize());
    winMax.addEventListener("click", () => appWindow.toggleMaximize());
    winClose.addEventListener("click", () => appWindow.hide());
  } else {
    winMin.addEventListener("click", () => console.log("Minimize"));
    winMax.addEventListener("click", () => console.log("Maximize"));
    winClose.addEventListener("click", () => {
      document.querySelector(".app-container").style.opacity = "0.7";
      setTimeout(() => alert("Uygulama sistem tepsisine gizlendi."), 200);
    });
  }

  // 2. Collapsible Sidebar Controls
  function toggleSidebar() {
    sidebar.classList.toggle("collapsed");
  }
  btnCollapseSidebar.addEventListener("click", toggleSidebar);
  btnToggleSidebar.addEventListener("click", toggleSidebar);

  // 3. Clear Chat
  btnClearChat.addEventListener("click", () => {
    chatHistory.innerHTML = `
      <div class="chat-message ai">
        <div class="avatar">A</div>
        <div class="message-bubble">
          Sohbet geçmişi temizlendi. Yeni bir komut veya soru girebilirsiniz.
        </div>
      </div>
    `;
  });

  // 3.1 Optional Project Workspace Logic
  const workspaceUnboundBox = document.getElementById("workspace-unbound-box");
  const workspaceBoundBox = document.getElementById("workspace-bound-box");
  const workspaceInputPath = document.getElementById("workspace-input-path");
  const btnBindWorkspace = document.getElementById("btn-bind-workspace");
  const btnUnbindWorkspace = document.getElementById("btn-unbind-workspace");
  const btnIndexWorkspace = document.getElementById("btn-index-workspace");
  const boundProjectName = document.getElementById("bound-project-name");
  const treeContainer = document.getElementById("workspace-tree-container");

  async function refreshWorkspaceUI() {
    try {
      const res = await fetch(`${API_BASE}/workspace/status`);
      if (res.ok) {
        const data = await res.json();
        if (data.is_project_bound) {
          workspaceUnboundBox.style.display = "none";
          workspaceBoundBox.style.display = "block";
          boundProjectName.textContent = `🟢 ${data.project_name}`;
          loadWorkspaceTree();
        } else {
          workspaceUnboundBox.style.display = "block";
          workspaceBoundBox.style.display = "none";
          treeContainer.innerHTML = "";
        }
      }
    } catch (e) {}
  }

  async function loadWorkspaceTree() {
    try {
      const res = await fetch(`${API_BASE}/workspace/tree?max_depth=2`);
      if (res.ok) {
        const data = await res.json();
        let treeHtml = "";
        function renderNode(node, indent = 0) {
          const pad = "&nbsp;".repeat(indent * 2);
          const icon = node.is_dir ? "📁 " : "📄 ";
          treeHtml += `<div>${pad}${icon}${node.name}</div>`;
          if (node.children) {
            node.children.forEach(c => renderNode(c, indent + 1));
          }
        }
        if (data.tree && data.tree.children) {
          data.tree.children.forEach(c => renderNode(c, 0));
        }
        treeContainer.innerHTML = treeHtml || "<div>(Boş klasör)</div>";
      }
    } catch (e) {}
  }

  btnBindWorkspace.addEventListener("click", async () => {
    const path = workspaceInputPath.value.trim();
    if (!path) return;
    try {
      const res = await fetch(`${API_BASE}/workspace/bind`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: path })
      });
      const data = await res.json();
      if (res.ok) {
        appendMessage("ai", `📁 **Proje Çalışma Alanı Bağlandı:** \`${data.project_name}\`\nArtık dosyaları bu proje kapsamında okuyabilir, düzenleyebilir ve derleyebilirsiniz.`);
        refreshWorkspaceUI();
      } else {
        alert("Bağlama hatası: " + data.detail);
      }
    } catch (err) {
      alert("Hata: " + err.message);
    }
  });

  btnUnbindWorkspace.addEventListener("click", async () => {
    try {
      const res = await fetch(`${API_BASE}/workspace/unbind`, { method: "POST" });
      if (res.ok) {
        appendMessage("ai", `✕ **Proje Bağlantısı Kesildi.** Sistem hafif ve genel amaçlı kişisel asistan moduna geri döndü.`);
        refreshWorkspaceUI();
      }
    } catch (err) {
      alert("Hata: " + err.message);
    }
  });

  btnIndexWorkspace.addEventListener("click", async () => {
    btnIndexWorkspace.disabled = true;
    btnIndexWorkspace.textContent = "⏳ İndeksleniyor...";
    try {
      const res = await fetch(`${API_BASE}/workspace/index`, { method: "POST" });
      const data = await res.json();
      if (res.ok) {
        appendMessage("ai", `⚡ **Proje Hafızaya Alındı:** ${data.indexed_files_count} kaynak kod dosyası HNSW grafına indekslendi!`);
      } else {
        alert("İndeksleme hatası: " + data.detail);
      }
    } catch (e) {
      alert("Hata: " + e.message);
    } finally {
      btnIndexWorkspace.disabled = false;
      btnIndexWorkspace.textContent = "⚡ Kodları İndeksle";
    }
  });

  refreshWorkspaceUI();


  // 4. View Audit Log
  btnViewAudit.addEventListener("click", async () => {
    appendMessage("user", "Güvenlik denetim günlüğünü (Audit Log) göster.");
    try {
      const res = await fetch(`${API_BASE}/agent/tools`);
      if (res.ok) {
        appendMessage("ai", "📜 **Son Güvenlik ve İnsan Onayı (HITL) Kayıtları:**\n- Sistemdeki tüm kritik dosya ve komut onayları `hitl_audit.log` dosyasında güvenle saklanmaktadır.");
      }
    } catch (e) {
      appendMessage("ai", `⚠️ Sunucu bağlantı hatası: ${e.message}`);
    }
  });

  // 5. Append Chat Messages
  function appendMessage(sender, text, isHtml = false) {
    const msg = document.createElement("div");
    msg.className = `chat-message ${sender}`;

    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = sender === "user" ? "U" : "A";

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";

    if (isHtml) {
      bubble.innerHTML = text;
    } else {
      bubble.innerHTML = renderMarkdown(text);
    }

    msg.appendChild(avatar);
    msg.appendChild(bubble);
    chatHistory.appendChild(msg);
    chatHistory.scrollTop = chatHistory.scrollHeight;
    return msg;
  }

  // 6. Minimalist Linear/Cursor HITL Approval Card
  function appendApprovalCard(pendingAction) {
    const cardHtml = `
      <div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;">
        <span style="background:rgba(251, 191, 36, 0.12); color:var(--accent-amber); border:1px solid rgba(251, 191, 36, 0.25); font-weight:600; font-size:0.68rem; font-family:var(--font-code); padding:2px 6px; border-radius:4px;">İNSAN ONAYI GEREKİYOR</span>
        <strong style="color:var(--text-main); font-size:0.82rem; font-family:var(--font-code);">${pendingAction.tool}</strong>
      </div>
      <p style="font-size:0.80rem; color:var(--text-muted); margin-bottom:8px;">
        Ajan kalıcı değişiklik yapacak bir işlem için onayınızı talep ediyor:
      </p>
      <pre style="background:#090a0d; padding:8px 10px; border-radius:5px; font-size:0.75rem; overflow-x:auto; color:var(--text-secondary); border:1px solid var(--border-hairline); font-family:var(--font-code);">${JSON.stringify(pendingAction.args, null, 2)}</pre>
      
      <div style="display:flex; gap:8px; margin-top:10px;" id="actions-${pendingAction.action_id}">
        <button id="btn-approve-${pendingAction.action_id}" style="background:var(--text-main); color:#0c0d0f; border:none; padding:5px 12px; border-radius:4px; font-weight:550; cursor:pointer; font-size:0.76rem;">
          Onayla ve Çalıştır
        </button>
        <button id="btn-reject-${pendingAction.action_id}" style="background:transparent; color:var(--text-muted); border:1px solid var(--border-hairline); padding:5px 12px; border-radius:4px; font-weight:500; cursor:pointer; font-size:0.76rem;">
          Reddet
        </button>
      </div>
      <div id="res-${pendingAction.action_id}" style="display:none; margin-top:8px; font-size:0.78rem;"></div>
    `;

    appendMessage("ai", cardHtml, true);

    const btnApprove = document.getElementById(`btn-approve-${pendingAction.action_id}`);
    const btnReject = document.getElementById(`btn-reject-${pendingAction.action_id}`);
    const actionsBox = document.getElementById(`actions-${pendingAction.action_id}`);
    const resBox = document.getElementById(`res-${pendingAction.action_id}`);

    async function sendDecision(approved, reason = "") {
      btnApprove.disabled = true;
      btnReject.disabled = true;
      try {
        const res = await fetch(`${API_BASE}/agent/action/decision`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            action_id: pendingAction.action_id,
            approved: approved,
            rejection_reason: reason
          })
        });
        const data = await res.json();
        actionsBox.style.display = "none";
        resBox.style.display = "block";
        if (approved) {
          resBox.innerHTML = `<span style="color:var(--accent-green);">✅ <strong>Onaylandı ve Çalıştırıldı:</strong></span><pre style="background:rgba(0,0,0,0.5); padding:6px; border-radius:4px; margin-top:4px; font-size:0.8rem;">${typeof data.result === 'object' ? JSON.stringify(data.result, null, 2) : data.result}</pre>`;
        } else {
          resBox.innerHTML = `<span style="color:var(--accent-red);">❌ <strong>İptal Edildi:</strong> Eylem yürütülmedi.</span>`;
        }
      } catch (err) {
        alert("Karar uygulanırken hata: " + err.message);
      }
    }

    btnApprove.addEventListener("click", () => sendDecision(true));
    btnReject.addEventListener("click", () => sendDecision(false, "Kullanıcı masaüstü arayüzünden reddetti."));
  }

  // 7. Chat Form Submit
  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const query = userInput.value.trim();
    if (!query) return;

    appendMessage("user", query);
    userInput.value = "";

    const mode = chatMode.value;
    const requireApproval = chkApproval.checked;

    try {
      if (mode === "react") {
        // SSE Canlı Akış (Streaming) ReAct & Fast-Path Motoru (Claude Editorial Fluid)
        const msgDiv = document.createElement("div");
        msgDiv.className = "chat-message ai";

        const avatar = document.createElement("div");
        avatar.className = "avatar";
        avatar.textContent = "A";

        const bubble = document.createElement("div");
        bubble.className = "message-bubble";

        // Claude Editorial: Canlı Kronometreli Düşünce Rozeti (Live Stopwatch Thinking Pill)
        const startTime = performance.now();
        let finalThinkTime = null;
        let isStreaming = true;
        let hasFinalAnswer = false;

        bubble.innerHTML = `
          <div class="thinking-pill">
            <div class="thinking-dot"></div>
            <span class="thinking-text">Düşünülüyor</span>
            <span class="thinking-timer">· 0.0s</span>
          </div>
        `;

        msgDiv.appendChild(avatar);
        msgDiv.appendChild(bubble);
        chatHistory.appendChild(msgDiv);
        smartScroll(chatHistory);

        const timerInterval = setInterval(() => {
          if (finalThinkTime !== null) return;
          const timerEl = bubble.querySelector(".thinking-timer");
          if (timerEl) {
            const elapsed = ((performance.now() - startTime) / 1000).toFixed(1);
            timerEl.textContent = `· ${elapsed}s`;
          }
        }, 100);

        let accumulatedTokens = "";
        let thoughts = [];
        let actions = [];
        let pendingAction = null;
        let renderScheduled = false;

        function renderBubbleUI() {
          renderScheduled = false;
          let html = "";

          // Düşünce veya Eylem varsa Claude stili akordeon kutusu oluştur
          if (thoughts.length > 0 || actions.length > 0) {
            const thinkSeconds = finalThinkTime || ((performance.now() - startTime) / 1000).toFixed(1);
            const totalSteps = thoughts.length + actions.length;
            const isOpen = !hasFinalAnswer && accumulatedTokens.length === 0;

            let thoughtBody = thoughts.map(t => escapeHtml(t)).join("<br><br>");
            if (actions.length > 0) {
              const actionsHtml = actions.map(act => `
                <div style="font-size:0.75rem; color:var(--accent-primary); font-family:var(--font-code); padding:4px 8px; background:rgba(0,0,0,0.3); border-radius:4px; margin:4px 0; border:1px solid var(--border-hairline);">
                  ⚙ <strong>${escapeHtml(act.tool)}</strong>: <code>${escapeHtml(JSON.stringify(act.args || {}))}</code>
                  ${act.observation ? `<div style="color:var(--text-muted); margin-top:2px; font-size:0.70rem;">Sonuç: ${escapeHtml(act.observation)}</div>` : ''}
                </div>
              `).join("");
              thoughtBody = thoughtBody ? `${thoughtBody}<br><br>${actionsHtml}` : actionsHtml;
            }

            html += `
              <details class="thought-box" ${isOpen ? 'open' : ''}>
                <summary class="thought-toggle">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
                  <span>${thinkSeconds}s boyunca düşünüldü</span>
                  <span class="thought-badge">${totalSteps} Adım</span>
                </summary>
                <div class="thought-content">${thoughtBody}</div>
              </details>
            `;
          } else if (accumulatedTokens.length === 0 && !hasFinalAnswer) {
            // Henüz yanıt veya düşünce gelmedi, canlı kronometre devam ediyor
            const elapsed = ((performance.now() - startTime) / 1000).toFixed(1);
            html += `
              <div class="thinking-pill">
                <div class="thinking-dot"></div>
                <span class="thinking-text">Düşünülüyor</span>
                <span class="thinking-timer">· ${elapsed}s</span>
              </div>
            `;
          }

          // Nihai veya akan metin
          if (accumulatedTokens.length > 0) {
            html += renderMarkdown(accumulatedTokens);
            if (isStreaming) {
              html += `<span class="streaming-caret"></span>`;
            }
          }

          bubble.innerHTML = html;
          smartScroll(chatHistory);
        }

        function scheduleRender() {
          if (!renderScheduled) {
            renderScheduled = true;
            requestAnimationFrame(renderBubbleUI);
          }
        }

        const response = await fetch(`${API_BASE}/agent/react/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: query, max_steps: 5, require_approval: requireApproval })
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop();

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              const dataStr = line.slice(6).trim();
              if (dataStr === "[DONE]") break;

              try {
                const event = JSON.parse(dataStr);

                if (event.type === "token") {
                  if (finalThinkTime === null) {
                    finalThinkTime = ((performance.now() - startTime) / 1000).toFixed(1);
                    clearInterval(timerInterval);
                  }
                  accumulatedTokens += event.content;
                  scheduleRender();
                } else if (event.type === "thought") {
                  thoughts.push(event.content);
                  scheduleRender();
                } else if (event.type === "action") {
                  actions.push({ tool: event.tool, args: event.args });
                  scheduleRender();
                } else if (event.type === "observation") {
                  if (actions.length > 0 && actions[actions.length - 1].tool === event.tool) {
                    actions[actions.length - 1].observation = event.observation;
                  } else {
                    actions.push({ tool: event.tool, observation: event.observation });
                  }
                  scheduleRender();
                } else if (event.type === "final_answer") {
                  if (finalThinkTime === null) {
                    finalThinkTime = ((performance.now() - startTime) / 1000).toFixed(1);
                    clearInterval(timerInterval);
                  }
                  hasFinalAnswer = true;
                  accumulatedTokens = event.content;
                  scheduleRender();
                } else if (event.type === "waiting_approval") {
                  if (finalThinkTime === null) {
                    finalThinkTime = ((performance.now() - startTime) / 1000).toFixed(1);
                    clearInterval(timerInterval);
                  }
                  pendingAction = event.pending_action;
                  scheduleRender();
                }
              } catch (e) {}
            }
          }
        }

        clearInterval(timerInterval);
        if (finalThinkTime === null) {
          finalThinkTime = ((performance.now() - startTime) / 1000).toFixed(1);
        }
        isStreaming = false;
        hasFinalAnswer = true;
        renderBubbleUI();

        if (pendingAction) {
          appendApprovalCard(pendingAction);
        }
      } else if (mode === "swarm") {
        const swarmMsgDiv = document.createElement("div");
        swarmMsgDiv.className = "chat-message ai";
        swarmMsgDiv.innerHTML = `
          <div class="avatar">🐝</div>
          <div class="message-bubble">
            <div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;">
              <span class="swarm-badge architect">🐝 ÇOKLU-AJAN SÜRÜSÜ BAŞLATILDI</span>
              <span style="font-size:0.75rem; color:var(--text-dim); font-family:var(--font-code);">${query}</span>
            </div>
            <div class="swarm-events-container" style="display:flex; flex-direction:column; gap:8px;"></div>
          </div>
        `;
        chatHistory.appendChild(swarmMsgDiv);
        chatHistory.scrollTop = chatHistory.scrollHeight;

        const eventsContainer = swarmMsgDiv.querySelector(".swarm-events-container");

        const response = await fetch(`${API_BASE}/agent/swarm/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ task: query, max_correction_loops: 2, auto_rollback_on_failure: true })
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split("\n");

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              const dataStr = line.slice(6).trim();
              if (dataStr === "[DONE]") break;
              try {
                const event = JSON.parse(dataStr);
                const card = document.createElement("div");
                card.className = "swarm-card";

                if (event.agent === "architect") {
                  card.innerHTML = `
                    <div class="swarm-header">
                      <span class="swarm-badge architect">MİMAR · ARCHITECT</span>
                      <span style="font-size:0.70rem; color:var(--text-dim); font-family:var(--font-code);">${event.action || 'plan'}</span>
                    </div>
                    <div style="font-size:0.82rem; color:var(--text-main); margin-bottom:4px;">${event.message}</div>
                    ${event.plan && event.plan.steps ? `
                      <div style="background:#090a0d; border:1px solid var(--border-hairline); padding:6px 10px; border-radius:5px; margin-top:6px;">
                        ${event.plan.steps.map((s, idx) => `<div class="swarm-dag-step"><span style="color:var(--text-dim);">${idx+1}.</span> <span>${s}</span></div>`).join('')}
                      </div>
                    ` : ''}
                  `;
                } else if (event.agent === "coder") {
                  card.innerHTML = `
                    <div class="swarm-header">
                      <span class="swarm-badge coder">GELİŞTİRİCİ · CODER</span>
                      <span style="font-size:0.70rem; color:var(--text-dim); font-family:var(--font-code);">${event.action || 'patch'}</span>
                    </div>
                    <div style="font-size:0.82rem; color:var(--text-main);">${event.message}</div>
                    ${event.target_file ? `<div class="swarm-diff-box">Dosya: ${event.target_file}<br>Durum: ${event.result || 'Değişiklik hazırlandı'}</div>` : ''}
                  `;
                } else if (event.agent === "verifier") {
                  const isVerifying = event.action === "verifying";
                  const isPassed = event.verdict === "PASSED";
                  const badgeClass = isVerifying ? "coder" : (isPassed ? "verifier" : "rejected");
                  const badgeText = isVerifying ? "KONTROL EDİLİYOR" : (isPassed ? "PASSED" : "FAILED");
                  card.innerHTML = `
                    <div class="swarm-header">
                      <span class="swarm-badge ${badgeClass}">DENETÇİ · VERIFIER</span>
                      <span style="font-size:0.70rem; font-weight:600; font-family:var(--font-code); color:${isVerifying ? 'var(--accent-primary)' : (isPassed ? 'var(--accent-green)' : 'var(--accent-red)')};">${badgeText}</span>
                    </div>
                    <div style="font-size:0.82rem; color:var(--text-main);">${event.message}</div>
                    ${event.error ? `<pre style="background:rgba(248,113,113,0.08); border:1px solid rgba(248,113,113,0.2); color:#fca5a5; padding:6px; border-radius:4px; font-size:0.74rem; font-family:var(--font-code); margin-top:4px;">${event.error}</pre>` : ''}
                  `;
                } else if (event.status) {
                  card.innerHTML = `
                    <div style="display:flex; align-items:center; gap:6px; font-size:0.80rem; font-weight:500; color:var(--accent-green);">
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>
                      <span>${event.message}</span>
                    </div>
                  `;
                }

                eventsContainer.appendChild(card);
                chatHistory.scrollTop = chatHistory.scrollHeight;
              } catch (e) {}
            }
          }
        }
      } else if (mode === "agent") {
        // Canlı Streaming Daktilo Efekti (SSE) — Claude Editorial Fluid
        const msgDiv = document.createElement("div");
        msgDiv.className = "chat-message ai";
        const avatar = document.createElement("div");
        avatar.className = "avatar";
        avatar.textContent = "A";
        const bubble = document.createElement("div");
        bubble.className = "message-bubble";

        const startTime = performance.now();
        let finalThinkTime = null;
        let isStreaming = true;

        bubble.innerHTML = `
          <div class="thinking-pill">
            <div class="thinking-dot"></div>
            <span class="thinking-text">Düşünülüyor</span>
            <span class="thinking-timer">· 0.0s</span>
          </div>
        `;

        msgDiv.appendChild(avatar);
        msgDiv.appendChild(bubble);
        chatHistory.appendChild(msgDiv);
        smartScroll(chatHistory);

        const timerInterval = setInterval(() => {
          if (finalThinkTime !== null) return;
          const timerEl = bubble.querySelector(".thinking-timer");
          if (timerEl) {
            const elapsed = ((performance.now() - startTime) / 1000).toFixed(1);
            timerEl.textContent = `· ${elapsed}s`;
          }
        }, 100);

        let accumulatedText = "";
        let renderScheduled = false;

        function renderAgentUI() {
          renderScheduled = false;
          let html = "";
          if (accumulatedText.length === 0) {
            const elapsed = ((performance.now() - startTime) / 1000).toFixed(1);
            html = `
              <div class="thinking-pill">
                <div class="thinking-dot"></div>
                <span class="thinking-text">Düşünülüyor</span>
                <span class="thinking-timer">· ${elapsed}s</span>
              </div>
            `;
          } else {
            html = renderMarkdown(accumulatedText);
            if (isStreaming) {
              html += `<span class="streaming-caret"></span>`;
            }
          }
          bubble.innerHTML = html;
          smartScroll(chatHistory);
        }

        const response = await fetch(`${API_BASE}/agent/chat/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: query, max_tokens: 400 })
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split("\n");

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              const dataStr = line.slice(6).trim();
              if (dataStr === "[DONE]") {
                break;
              }
              try {
                const parsed = JSON.parse(dataStr);
                if (parsed.token) {
                  if (finalThinkTime === null) {
                    finalThinkTime = ((performance.now() - startTime) / 1000).toFixed(1);
                    clearInterval(timerInterval);
                  }
                  accumulatedText += parsed.token;
                  if (!renderScheduled) {
                    renderScheduled = true;
                    requestAnimationFrame(renderAgentUI);
                  }
                }
              } catch (e) {}
            }
          }
        }
        clearInterval(timerInterval);
        isStreaming = false;
        renderAgentUI();
      } else {
        const res = await fetch(`${API_BASE}/rag/ask`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: query, top_k: 2 })
        });
        if (res.ok) {
          const data = await res.json();
          appendMessage("ai", data.answer);
        }
      }
    } catch (err) {
      appendMessage("ai", `⚠️ Sunucuya bağlanılamadı (${err.message}). API sunucusunun http://127.0.0.1:8000 üzerinde çalıştığından emin olun.`);
    }
  });
});
