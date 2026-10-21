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

  // 0.1 Commercial License Enforcement & Modal Handling
  const licenseBadge = document.getElementById("license-badge");
  const licenseModal = document.getElementById("license-modal");
  const modalHwId = document.getElementById("modal-hw-id");
  const btnCopyHw = document.getElementById("btn-copy-hw");
  const licenseInputKey = document.getElementById("license-input-key");
  const btnActivateLicense = document.getElementById("btn-activate-license");
  const licenseModalMsg = document.getElementById("license-modal-msg");

  async function checkLicenseStatus() {
    try {
      const res = await fetch(`${API_BASE}/license/status`);
      const data = await res.json();
      modalHwId.textContent = data.hardware_id || "Bilinmiyor";

      if (data.is_licensed && data.details) {
        licenseBadge.style.color = "#10b981";
        licenseBadge.style.background = "rgba(16,185,129,0.1)";
        licenseBadge.style.borderColor = "rgba(16,185,129,0.3)";
        if (data.details.is_lifetime) {
          licenseBadge.textContent = "💎 Sınırsız Lisans";
        } else {
          licenseBadge.textContent = `🟢 ${data.details.tier_name.split(' ')[0]} (${data.details.days_left} Gün)`;
        }
        licenseModal.style.display = "none";
      } else {
        licenseBadge.style.color = "#ef4444";
        licenseBadge.style.background = "rgba(239,68,68,0.1)";
        licenseBadge.style.borderColor = "rgba(239,68,68,0.3)";
        licenseBadge.textContent = "🔴 Lisanssız (Kilitli)";
        licenseModal.style.display = "flex";
      }
    } catch (err) {
      console.error("Lisans kontrol hatası:", err);
    }
  }

  if (licenseBadge) {
    licenseBadge.addEventListener("click", () => {
      licenseModal.style.display = "flex";
    });
  }

  if (btnCopyHw) {
    btnCopyHw.addEventListener("click", () => {
      navigator.clipboard.writeText(modalHwId.textContent);
      btnCopyHw.textContent = "Kopyalandı!";
      setTimeout(() => { btnCopyHw.textContent = "Kopyala"; }, 1500);
    });
  }

  // 0.2 EULA Viewer & Mandatory Checkbox Logic
  const chkEulaAgree = document.getElementById("chk-eula-agree");
  const btnViewEula = document.getElementById("btn-view-eula");
  const eulaViewerModal = document.getElementById("eula-viewer-modal");
  const eulaContentBody = document.getElementById("eula-content-body");
  const btnCloseEula = document.getElementById("btn-close-eula");
  const btnAcceptEula = document.getElementById("btn-accept-eula");

  async function loadEulaContent() {
    try {
      const res = await fetch("/desktop/EULA.md");
      if (res.ok) {
        const text = await res.text();
        eulaContentBody.textContent = text;
      } else {
        const resDirect = await fetch("/EULA.md");
        if (resDirect.ok) {
          eulaContentBody.textContent = await resDirect.text();
        } else {
          eulaContentBody.textContent = "Sözleşme yüklenemedi. Lütfen 'EULA.md' dosyasını kontrol edin.";
        }
      }
    } catch (err) {
      eulaContentBody.textContent = "Sözleşme yüklenirken hata: " + err.message;
    }
  }

  if (btnViewEula) {
    btnViewEula.addEventListener("click", (e) => {
      e.preventDefault();
      loadEulaContent();
      eulaViewerModal.style.display = "flex";
    });
  }

  if (btnCloseEula) {
    btnCloseEula.addEventListener("click", () => {
      eulaViewerModal.style.display = "none";
    });
  }

  if (btnAcceptEula) {
    btnAcceptEula.addEventListener("click", () => {
      if (chkEulaAgree) chkEulaAgree.checked = true;
      eulaViewerModal.style.display = "none";
    });
  }

  if (btnActivateLicense) {
    btnActivateLicense.addEventListener("click", async () => {
      if (chkEulaAgree && !chkEulaAgree.checked) {
        licenseModalMsg.style.color = "#ef4444";
        licenseModalMsg.textContent = "Lütfen önce EULA Kullanıcı Sözleşmesi'ni kabul ediniz.";
        return;
      }

      const key = licenseInputKey.value.trim();
      if (!key) {
        licenseModalMsg.style.color = "#ef4444";
        licenseModalMsg.textContent = "Lütfen lisans anahtarınızı giriniz.";
        return;
      }
      licenseModalMsg.style.color = "#00f3ff";
      licenseModalMsg.textContent = "Doğrulanıyor...";

      try {
        const res = await fetch(`${API_BASE}/license/activate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ license_key: key })
        });
        const data = await res.json();
        if (res.ok) {
          licenseModalMsg.style.color = "#10b981";
          licenseModalMsg.textContent = "✅ " + data.message;
          setTimeout(() => {
            checkLicenseStatus();
          }, 1000);
        } else {
          licenseModalMsg.style.color = "#ef4444";
          licenseModalMsg.textContent = "❌ " + (data.detail || "Lisans doğrulanamadı.");
        }
      } catch (err) {
        licenseModalMsg.style.color = "#ef4444";
        licenseModalMsg.textContent = "Sunucu iletişim hatası: " + err.message;
      }
    });
  }

  checkLicenseStatus();

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
        <div class="avatar">🤖</div>
        <div class="message-bubble">
          Sohbet geçmişi temizlendi. Size nasıl yardımcı olabilirim?
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
    avatar.textContent = sender === "user" ? "👤" : "🤖";

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

  // 6. Floating Neon HITL Approval Card
  function appendApprovalCard(pendingAction) {
    const cardHtml = `
      <div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;">
        <span style="background:var(--accent-amber); color:#000; font-weight:bold; font-size:0.7rem; padding:2px 6px; border-radius:4px;">İNSAN ONAYI GEREKİYOR</span>
        <strong style="color:var(--accent-amber);">${pendingAction.tool}</strong>
      </div>
      <p style="font-size:0.85rem; color:var(--text-muted); margin-bottom:8px;">
        Ajan kalıcı değişiklik yapacak bir eylem gerçekleştirmek istiyor:
      </p>
      <pre style="background:rgba(0,0,0,0.6); padding:8px; border-radius:6px; font-size:0.8rem; overflow-x:auto; color:var(--accent-cyan); border:1px solid var(--border-neon-purple);">${JSON.stringify(pendingAction.args, null, 2)}</pre>
      
      <div style="display:flex; gap:10px; margin-top:12px;" id="actions-${pendingAction.action_id}">
        <button id="btn-approve-${pendingAction.action_id}" style="background:var(--accent-green); color:white; border:none; padding:6px 14px; border-radius:6px; font-weight:600; cursor:pointer; font-size:0.8rem;">
          ✅ İzin Ver ve Çalıştır
        </button>
        <button id="btn-reject-${pendingAction.action_id}" style="background:var(--accent-red); color:white; border:none; padding:6px 14px; border-radius:6px; font-weight:600; cursor:pointer; font-size:0.8rem;">
          ❌ Reddet / İptal Et
        </button>
      </div>
      <div id="res-${pendingAction.action_id}" style="display:none; margin-top:10px; font-size:0.85rem;"></div>
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
        const res = await fetch(`${API_BASE}/agent/react`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: query, max_steps: 5, require_approval: requireApproval })
        });
        if (res.ok) {
          const data = await res.json();
          appendMessage("ai", data.final_answer);
          if (data.status === "WAITING_APPROVAL" && data.pending_action) {
            appendApprovalCard(data.pending_action);
          }
        } else {
          const err = await res.json();
          appendMessage("ai", `⚠️ Hata: ${err.detail || "Sunucu hatası"}`);
        }
      } else if (mode === "agent") {
        // Canlı Streaming Daktilo Efekti (SSE)
        const msgDiv = document.createElement("div");
        msgDiv.className = "chat-message ai";
        const avatar = document.createElement("div");
        avatar.className = "avatar";
        avatar.textContent = "🤖";
        const bubble = document.createElement("div");
        bubble.className = "message-bubble";
        bubble.innerHTML = "<span class='cursor'>▋</span>";
        msgDiv.appendChild(avatar);
        msgDiv.appendChild(bubble);
        chatHistory.appendChild(msgDiv);
        chatHistory.scrollTop = chatHistory.scrollHeight;

        let accumulatedText = "";

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
                  accumulatedText += parsed.token;
                  bubble.innerHTML = renderMarkdown(accumulatedText) + "<span class='cursor'>▋</span>";
                  chatHistory.scrollTop = chatHistory.scrollHeight;
                }
              } catch (e) {}
            }
          }
        }
        bubble.innerHTML = renderMarkdown(accumulatedText);
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
