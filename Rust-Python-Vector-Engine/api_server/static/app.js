document.addEventListener("DOMContentLoaded", () => {
  const chatHistory = document.getElementById("chat-history");
  const chatForm = document.getElementById("chat-form");
  const userInput = document.getElementById("user-input");
  const docCountStat = document.getElementById("stat-doc-count");
  const btnIngest = document.getElementById("btn-ingest");
  const docContentInput = document.getElementById("doc-content");
  const docCategoryInput = document.getElementById("doc-category");
  const btnVacuum = document.getElementById("btn-vacuum");
  const btnSaveDb = document.getElementById("btn-save-db");

  // 1. Veritabanı Durumunu Getir
  async function updateDbStatus() {
    try {
      const res = await fetch("/db/status");
      if (res.ok) {
        const data = await res.json();
        docCountStat.textContent = (data.active_vectors_count !== undefined) ? data.active_vectors_count : (data.active_documents || 0);
      }
    } catch (err) {
      console.warn("Veritabanı durumu alınamadı:", err);
    }
  }
  updateDbStatus();

  // 2. Mesaj Ekleme Yardımcısı
  function appendMessage(sender, text, retrievedChunks = null) {
    const msgDiv = document.createElement("div");
    msgDiv.className = `chat-message ${sender}`;

    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = sender === "user" ? "👤" : "🤖";

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";

    const content = document.createElement("div");
    content.className = "bubble-content";
    content.innerHTML = text.replace(/\n/g, "<br>");
    bubble.appendChild(content);

    // Eğer RAG tarafından çekilen bağlam parçaları varsa ekle
    if (retrievedChunks && retrievedChunks.length > 0) {
      const contextBox = document.createElement("div");
      contextBox.className = "context-box";
      
      const contextHeader = document.createElement("div");
      contextHeader.className = "context-header";
      contextHeader.innerHTML = `<span>🔍</span> HNSW Grafından Çekilen İlgili Bağlamlar (${retrievedChunks.length}):`;
      contextBox.appendChild(contextHeader);

      retrievedChunks.forEach((chunk) => {
        const item = document.createElement("div");
        item.className = "context-item";
        item.textContent = `[ID: ${chunk.id} | Mesafe: ${chunk.distance.toFixed(3)}] ${chunk.text}`;
        contextBox.appendChild(item);
      });

      bubble.appendChild(contextBox);
    }

    msgDiv.appendChild(avatar);
    msgDiv.appendChild(bubble);
    chatHistory.appendChild(msgDiv);
    chatHistory.scrollTop = chatHistory.scrollHeight;
    return msgDiv;
  }

  // 3. Geçici "Yazıyor..." Göstergesi
  function showTypingIndicator() {
    const msgDiv = document.createElement("div");
    msgDiv.className = "chat-message ai";
    msgDiv.id = "typing-indicator";

    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = "🤖";

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";

    const content = document.createElement("div");
    content.className = "bubble-content";
    content.innerHTML = `
      <div class="typing-dots">
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
      </div>
    `;
    bubble.appendChild(content);
    msgDiv.appendChild(avatar);
    msgDiv.appendChild(bubble);
    chatHistory.appendChild(msgDiv);
    chatHistory.scrollTop = chatHistory.scrollHeight;
  }

  function removeTypingIndicator() {
    const indicator = document.getElementById("typing-indicator");
    if (indicator) indicator.remove();
  }

  const chatMode = document.getElementById("chat-mode");
  const modeHint = document.getElementById("mode-hint");

  if (chatMode && modeHint) {
    chatMode.addEventListener("change", () => {
      if (chatMode.value === "agent") {
        modeHint.textContent = "🛠️ Araçları otomatik çağırır (Hesaplama, CPU/RAM, Web, Python)";
      } else if (chatMode.value === "react") {
        modeHint.textContent = "🧠 Çok adımlı planlama, muhakeme ve ardışık araç yürütme";
      } else {
        modeHint.textContent = "📚 Hafızadaki dokümanlara göre cevap üretir";
      }
    });
  }

  function appendApprovalCard(pendingAction) {
    const msgDiv = document.createElement("div");
    msgDiv.className = "chat-message ai";
    msgDiv.id = `approval-${pendingAction.action_id}`;

    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = "🛡️";

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";
    bubble.style.border = "1px solid rgba(245, 158, 11, 0.4)";
    bubble.style.background = "rgba(245, 158, 11, 0.05)";

    const content = document.createElement("div");
    content.className = "bubble-content";
    content.innerHTML = `
      <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
        <span style="background: #f59e0b; color: #000; font-weight: bold; font-size: 0.7rem; padding: 2px 6px; border-radius: 4px;">İNSAN ONAYI GEREKİYOR</span>
        <strong style="color: #f59e0b;">${pendingAction.tool}</strong>
      </div>
      <p style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 8px;">
        Yapay zeka sistemi veya dosyaları değiştirecek kritik bir eylem gerçekleştirmek istiyor:
      </p>
      <pre style="background: rgba(0,0,0,0.5); padding: 8px; border-radius: 6px; font-size: 0.8rem; overflow-x: auto; color: #a5f3fc; border: 1px solid rgba(255,255,255,0.08);">${JSON.stringify(pendingAction.args, null, 2)}</pre>
      
      <div style="display: flex; gap: 10px; margin-top: 12px;" id="actions-${pendingAction.action_id}">
        <button id="btn-approve-${pendingAction.action_id}" style="background: #10b981; color: white; border: none; padding: 6px 14px; border-radius: 6px; font-weight: 600; cursor: pointer; font-size: 0.8rem; display: flex; align-items: center; gap: 5px;">
          ✅ İzin Ver ve Çalıştır
        </button>
        <button id="btn-reject-${pendingAction.action_id}" style="background: #ef4444; color: white; border: none; padding: 6px 14px; border-radius: 6px; font-weight: 600; cursor: pointer; font-size: 0.8rem; display: flex; align-items: center; gap: 5px;">
          ❌ Reddet / İptal Et
        </button>
      </div>
      <div id="decision-result-${pendingAction.action_id}" style="display: none; margin-top: 10px; font-size: 0.85rem;"></div>
    `;
    bubble.appendChild(content);
    msgDiv.appendChild(avatar);
    msgDiv.appendChild(bubble);
    chatHistory.appendChild(msgDiv);
    chatHistory.scrollTop = chatHistory.scrollHeight;

    // Buton dinleyicileri
    const btnApprove = document.getElementById(`btn-approve-${pendingAction.action_id}`);
    const btnReject = document.getElementById(`btn-reject-${pendingAction.action_id}`);
    const actionsContainer = document.getElementById(`actions-${pendingAction.action_id}`);
    const resBox = document.getElementById(`decision-result-${pendingAction.action_id}`);

    async function sendDecision(approved, reason = "") {
      btnApprove.disabled = true;
      btnReject.disabled = true;
      try {
        const res = await fetch("/agent/action/decision", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            action_id: pendingAction.action_id,
            approved: approved,
            rejection_reason: reason
          })
        });
        const data = await res.json();
        actionsContainer.style.display = "none";
        resBox.style.display = "block";
        if (approved) {
          resBox.innerHTML = `<span style="color: #10b981;">✅ <strong>Onaylandı ve Çalıştırıldı:</strong></span><pre style="background: rgba(0,0,0,0.4); padding: 6px; border-radius: 4px; margin-top: 4px; font-size: 0.8rem;">${typeof data.result === 'object' ? JSON.stringify(data.result, null, 2) : data.result}</pre>`;
        } else {
          resBox.innerHTML = `<span style="color: #ef4444;">❌ <strong>İptal Edildi:</strong> Eylem yürütülmedi.</span>`;
        }
      } catch (err) {
        alert("Karar iletilirken hata: " + err.message);
      }
    }

    btnApprove.addEventListener("click", () => sendDecision(true));
    btnReject.addEventListener("click", () => sendDecision(false, "Kullanıcı arayüzden reddetti."));
  }

  // 4. Sohbet Formu Gönderimi
  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const query = userInput.value.trim();
    if (!query) return;

    appendMessage("user", query);
    userInput.value = "";
    showTypingIndicator();

    const mode = chatMode ? chatMode.value : "rag";
    const chkApproval = document.getElementById("chk-human-approval");
    const requireApproval = chkApproval ? chkApproval.checked : true;

    try {
      if (mode === "react") {
        const res = await fetch("/agent/react", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: query, max_steps: 5, require_approval: requireApproval })
        });
        removeTypingIndicator();
        if (res.ok) {
          const data = await res.json();
          let stepChunks = null;
          if (data.trace && data.trace.length > 0) {
            stepChunks = data.trace.map(t => ({
              id: `Adım ${t.step_number}`,
              distance: 0.0,
              text: `🤔 Düşünce: ${t.thought}${t.action ? ` | 🛠️ Eylem: ${t.action}(${JSON.stringify(t.action_input)}) => Gözlem: ${JSON.stringify(t.observation)}` : ''}`
            }));
          }
          appendMessage("ai", data.final_answer, stepChunks);

          // Eğer insan onayı bekleniyorsa onay kartını render et
          if (data.status === "WAITING_APPROVAL" && data.pending_action) {
            appendApprovalCard(data.pending_action);
          }
        } else {
          const err = await res.json();
          appendMessage("ai", `⚠️ ReAct Hatası: ${err.detail || "Sunucu hatası"}`);
        }
      } else if (mode === "agent") {
        const res = await fetch("/agent/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: query })
        });
        removeTypingIndicator();
        if (res.ok) {
          const data = await res.json();
          let toolChunks = null;
          if (data.tool_used) {
            toolChunks = [{
              id: "TOOL",
              distance: 0.0,
              text: `🛠️ ${data.tool_used.name}(${JSON.stringify(data.tool_used.args)}) => Sonuç: ${JSON.stringify(data.tool_result)}`
            }];
          }
          appendMessage("ai", data.answer, toolChunks);
        } else {
          const err = await res.json();
          appendMessage("ai", `⚠️ Ajan Hatası: ${err.detail || "Sunucu hatası"}`);
        }
      } else {
        const res = await fetch("/rag/ask", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: query, top_k: 2 })
        });
        removeTypingIndicator();
        if (res.ok) {
          const data = await res.json();
          appendMessage("ai", data.answer, data.retrieved_chunks);
        } else {
          const err = await res.json();
          appendMessage("ai", `⚠️ Hata oluştu: ${err.detail || "Bilinmeyen sunucu hatası"}`);
        }
      }
    } catch (err) {
      removeTypingIndicator();
      appendMessage("ai", `⚠️ Bağlantı hatası: Sunucuya erişilemedi (${err.message}).`);
    }
  });

  // 5. Belge İndeksleme Butonu
  btnIngest.addEventListener("click", async () => {
    const text = docContentInput.value.trim();
    const cat = docCategoryInput.value.trim() || "genel";

    if (!text) {
      alert("Lütfen indekslenecek bir metin girin.");
      return;
    }

    btnIngest.disabled = true;
    btnIngest.innerHTML = "<span>⏳</span> Vektörleştiriliyor...";

    try {
      const res = await fetch("/rag/ingest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          documents: [text],
          metadatas: [{ category: cat }]
        })
      });

      if (res.ok) {
        docContentInput.value = "";
        docCategoryInput.value = "";
        updateDbStatus();
        appendMessage("ai", `✅ Yeni bilgi HNSW hafızasına eklendi: <em>"${text.substring(0, 80)}${text.length > 80 ? '...' : ''}"</em>`);
      } else {
        const err = await res.json();
        alert(`İndeksleme başarısız: ${err.detail}`);
      }
    } catch (err) {
      alert(`Bağlantı hatası: ${err.message}`);
    } finally {
      btnIngest.disabled = false;
      btnIngest.innerHTML = "<span>⚡</span> HNSW Grafına İndeksle";
    }
  });

  // 6. Vacuum & Save İşlemleri
  btnVacuum.addEventListener("click", async () => {
    if (!confirm("Silinmiş tombstone kayıtlar HNSW grafından fiziksel olarak temizlensin mi?")) return;
    try {
      const res = await fetch("/db/vacuum", { method: "POST" });
      const data = await res.json();
      alert(data.message);
      updateDbStatus();
    } catch (e) {
      alert("Vacuum hatası: " + e.message);
    }
  });

  btnSaveDb.addEventListener("click", async () => {
    try {
      const res = await fetch("/db/save", { method: "POST" });
      const data = await res.json();
      alert(data.message);
    } catch (e) {
      alert("Kayıt hatası: " + e.message);
    }
  });

  // 7. Kişisel Hafıza Ekleme
  const btnRemember = document.getElementById("btn-remember");
  const memoryFactInput = document.getElementById("memory-fact-input");

  if (btnRemember && memoryFactInput) {
    btnRemember.addEventListener("click", async () => {
      const fact = memoryFactInput.value.trim();
      if (!fact) {
        alert("Lütfen kaydedilecek bir bilgi/anı girin.");
        return;
      }
      btnRemember.disabled = true;
      btnRemember.textContent = "⏳ Kaydediliyor...";
      try {
        const res = await fetch("/memory/remember", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ fact: fact, topic: "personal" })
        });
        if (res.ok) {
          memoryFactInput.value = "";
          updateDbStatus();
          appendMessage("ai", `🧠 Kişisel hafızama kalıcı olarak işledim: <em>"${fact}"</em>`);
        } else {
          alert("Hafıza kaydı başarısız oldu.");
        }
      } catch (err) {
        alert("Bağlantı hatası: " + err.message);
      } finally {
        btnRemember.disabled = false;
        btnRemember.textContent = "💾 Hafızaya Kaydet";
      }
    });
  }
});
