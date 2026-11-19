// Expandable Mini Spotlight (Alt + Space) & Command Output Logic

document.addEventListener("DOMContentLoaded", () => {
  const overlay = document.getElementById("spotlight-overlay");
  const input = document.getElementById("spotlight-input");
  const terminal = document.getElementById("spotlight-terminal");

  // Global Kısayol Dinleyicisi: Alt + Space
  window.addEventListener("keydown", (e) => {
    if (e.altKey && (e.code === "Space" || e.keyCode === 32)) {
      e.preventDefault();
      toggleSpotlight();
    } else if (e.key === "Escape" && overlay.classList.contains("active")) {
      closeSpotlight();
    }
  });

  function toggleSpotlight() {
    if (overlay.classList.contains("active")) {
      closeSpotlight();
    } else {
      openSpotlight();
    }
  }

  function openSpotlight() {
    overlay.classList.add("active");
    input.value = "";
    input.focus();
    terminal.classList.remove("visible");
    terminal.innerHTML = "";
  }

  function closeSpotlight() {
    overlay.classList.remove("active");
    input.blur();
  }

  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) {
      closeSpotlight();
    }
  });

  const esc = (s) => (typeof escapeHtml === "function" ? escapeHtml(s) : String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"));
  let inFlight = false;

  // Spotlight Komut Gönderimi (Enter)
  input.addEventListener("keydown", async (e) => {
    if (e.key === "Enter") {
      if (inFlight) return;
      const q = input.value.trim();
      if (!q) return;

      inFlight = true;
      terminal.classList.add("visible");
      terminal.innerHTML = `<span style="color:var(--accent-purple);">⚡ [Komut Yürütülüyor]:</span> ${esc(q)}\n<span style="color:var(--text-dim);">Lütfen bekleyin...</span>`;

      try {
        const chk = document.getElementById("chk-human-approval");
        const requireApproval = chk ? chk.checked : true;

        const res = await fetch("http://127.0.0.1:8000/agent/react", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: q, max_steps: 3, require_approval: requireApproval })
        });
        if (res.ok) {
          const data = await res.json();
          let out = `<span style="color:var(--accent-cyan);">=== ÇIKTI / SONUÇ ===</span>\n${esc(data.final_answer)}\n`;
          if (data.status === "WAITING_APPROVAL" && data.pending_action) {
            out += `\n<span style="color:var(--accent-amber);">🛡️ [İNSAN ONAYI GEREKLİ]: '${esc(data.pending_action.tool)}' aracı ana ekranda onay kartı olarak açıldı.</span>\n`;
            if (typeof window.auraAppendApprovalCard === "function") {
              window.auraAppendApprovalCard(data.pending_action);
            }
          }
          if (data.trace && data.trace.length > 0) {
            out += `\n<span style="color:var(--text-dim);">[İşlenen Adımlar: ${esc(data.total_steps)}]</span>`;
          }
          terminal.innerHTML = out;
        } else {
          let errMsg = `HTTP ${res.status}`;
          try {
            const err = await res.json();
            errMsg = err.detail || errMsg;
          } catch (_) {}
          terminal.innerHTML = `<span style="color:var(--accent-red);">Hata: ${esc(errMsg)}</span>`;
        }
      } catch (err) {
        terminal.innerHTML = `<span style="color:var(--accent-red);">Bağlantı hatası: ${esc(err.message)}</span>`;
      } finally {
        inFlight = false;
      }
    }
  });
});
