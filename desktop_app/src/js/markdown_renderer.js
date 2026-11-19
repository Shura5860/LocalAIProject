// ==============================================================================
// AURA STUDIO — XSS-Safe Markdown, Thinking Blocks & Code Renderer
// ==============================================================================

function escapeHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function renderMarkdown(content) {
  if (!content) return "";

  const blocks = [];
  function holdBlock(htmlSnippet) {
    const token = `___AURA_BLOCK_${blocks.length}___`;
    blocks.push(htmlSnippet);
    return token;
  }

  let text = String(content);

  // 1. Claude-style Thinking Tag: <think>...</think> (extracted first, escaped safely)
  text = text.replace(/<think>([\s\S]*?)<\/think>/gi, (match, thought) => {
    const cleanThought = thought.trim();
    if (!cleanThought) return "";
    const safeThought = escapeHtml(cleanThought).replace(/\n/g, "<br>");
    return holdBlock(
      `<details class="thought-box"><summary class="thought-toggle">` +
      `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>` +
      `<span>Düşünce Süreci</span><span class="thought-badge">Gizle / Göster</span></summary>` +
      `<div class="thought-content">${safeThought}</div></details>`
    );
  });

  // 2. Fenced Code Blocks: ```lang\n...``` (extracted BEFORE math & inline markdown)
  text = text.replace(/```([a-zA-Z0-9_\-\.]*)\r?\n([\s\S]*?)```/g, (match, lang, code) => {
    const language = escapeHtml(lang.trim().toLowerCase() || "code");
    const cleanCode = code.replace(/\r?\n$/, "");
    const lines = cleanCode.split("\n");

    const linesHtml = lines.map((line, idx) => {
      let isAdd = false;
      let isDel = false;
      if (language === "diff" || language === "patch") {
        if (line.startsWith("+") && !line.startsWith("+++")) isAdd = true;
        if (line.startsWith("-") && !line.startsWith("---")) isDel = true;
      }

      let safe = escapeHtml(line);

      const tokens = [];
      safe = safe.replace(/(\/\/.*$|&quot;(?:\\.|(?!&quot;).)*&quot;|&#39;(?:\\.|(?!&#39;).)*&#39;|(?<!&)#.*$)/g, (m) => {
        const id = `___TOKEN_${tokens.length}___`;
        if (m.startsWith("//") || m.startsWith("#")) {
          tokens.push(`<span class="token-comment">${m}</span>`);
        } else {
          tokens.push(`<span class="token-string">${m}</span>`);
        }
        return id;
      });

      safe = safe
        .replace(/\b(fn|def|let|mut|const|struct|impl|class|import|from|pub|return|if|else|match|for|in|while|async|await)\b/g, '<span class="token-keyword">$1</span>')
        .replace(/\b(String|str|bool|u32|i32|u64|i64|f64|f32|usize|Vec|Option|Result|int|float|dict|list)\b/g, '<span class="token-type">$1</span>');

      tokens.forEach((t, i) => {
        safe = safe.replace(`___TOKEN_${i}___`, () => t);
      });

      const trClass = isAdd ? ' class="diff-line-add"' : isDel ? ' class="diff-line-del"' : "";
      return `<tr${trClass}><td class="code-line-num">${idx + 1}</td><td class="code-line-text">${safe || "&nbsp;"}</td></tr>`;
    }).join("");

    const blockId = "code-" + Math.random().toString(36).substring(2, 9);

    return holdBlock(
      `<div class="code-container" id="${blockId}"><div class="code-header"><span class="code-lang">` +
      `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"></polyline><polyline points="8 6 2 12 8 18"></polyline></svg>` +
      `${language}</span><div class="code-actions"><button class="btn-code-action btn-copy" onclick="copyCodeContent('${blockId}')">` +
      `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>` +
      `<span>Kopyala</span></button></div></div><div class="code-content"><table class="code-table"><tbody>${linesHtml}</tbody></table></div></div>`
    );
  });

  // 3. Inline code: `...` (extracted before math & HTML escaping)
  text = text.replace(/`([^`\n]+)`/g, (match, codeText) => {
    return holdBlock(
      `<code style="background:rgba(255,255,255,0.06); padding:2px 5px; border-radius:4px; font-family:var(--font-code); color:var(--text-main); font-size:0.82rem; border:1px solid var(--border-hairline);">${escapeHtml(codeText)}</code>`
    );
  });

  // 4. Math formulas: $$formula$$ (Display) or $formula$ (Inline)
  text = text.replace(/\$\$([\s\S]*?)\$\$/g, (match, formula) => {
    try {
      if (window.katex) {
        return holdBlock(`<div class="katex-display-wrapper">${window.katex.renderToString(formula.trim(), { displayMode: true })}</div>`);
      }
    } catch (e) {}
    return holdBlock(`<div class="katex-display-wrapper"><code>${escapeHtml(formula.trim())}</code></div>`);
  });

  text = text.replace(/\$([^\$\n]+)\$/g, (match, formula) => {
    try {
      if (window.katex) {
        return holdBlock(window.katex.renderToString(formula.trim(), { displayMode: false }));
      }
    } catch (e) {}
    return holdBlock(`<code>${escapeHtml(formula)}</code>`);
  });

  // 5. HTML-escape ALL remaining prose (neutralizes any XSS in user/LLM/RAG text)
  let html = escapeHtml(text);

  // 6. Markdown Tables: | col1 | col2 | (requires valid |---| separator row)
  html = html.replace(/((?:\|[^\n]+\|\r?\n?)+)/g, (match, tableText) => {
    const rows = tableText.trim().split("\n");
    if (rows.length < 2) return match;
    if (!/^\|[\s:\-\|]+\|$/.test(rows[1].trim())) return match;

    const headerCols = rows[0].split("|").filter((c, i, a) => i !== 0 && i !== a.length - 1);
    let tableHtml = '<table class="markdown-table"><thead><tr>' +
      headerCols.map((c) => `<th>${c.trim()}</th>`).join("") +
      "</tr></thead><tbody>";

    for (let i = 2; i < rows.length; i++) {
      const cols = rows[i].split("|").filter((c, idx, a) => idx !== 0 && idx !== a.length - 1);
      if (cols.length === headerCols.length) {
        tableHtml += "<tr>" + cols.map((c) => `<td>${c.trim()}</td>`).join("") + "</tr>";
      }
    }
    tableHtml += "</tbody></table>";
    return holdBlock(tableHtml);
  });

  // 7. Inline formatting on escaped prose
  html = html
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.*?)\*/g, "<em>$1</em>")
    .replace(/\n\n/g, "<br><br>")
    .replace(/\n/g, "<br>");

  // 8. Restore all protected HTML blocks safely using callback replacement
  for (let i = blocks.length - 1; i >= 0; i--) {
    html = html.replace(`___AURA_BLOCK_${i}___`, () => blocks[i]);
  }

  return html;
}

function copyCodeContent(blockId) {
  const container = document.getElementById(blockId);
  if (!container) return;
  const lineTexts = container.querySelectorAll(".code-line-text");
  const fullText = Array.from(lineTexts).map((el) => el.textContent).join("\n");

  if (!navigator.clipboard || !navigator.clipboard.writeText) return;
  navigator.clipboard.writeText(fullText).then(() => {
    const btn = container.querySelector(".btn-copy span");
    if (btn) {
      const oldText = btn.textContent;
      btn.textContent = "Kopyalandı!";
      setTimeout(() => { btn.textContent = oldText; }, 1800);
    }
  }).catch(() => {});
}
