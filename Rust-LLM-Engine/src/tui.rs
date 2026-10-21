use anyhow::Result;
use crossterm::{
    event::{self, Event, KeyCode, KeyModifiers},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use ratatui::{
    backend::CrosstermBackend,
    layout::{Constraint, Direction, Layout},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, Paragraph, Wrap},
    Terminal,
};
use std::io;
use std::sync::mpsc::{self, Receiver, Sender};
use std::sync::Arc;
use std::thread;
use std::time::Duration;

use crate::engine::runner::{InferenceMessage, ModelRunner};
use crate::ops::SamplerParams;

pub struct ChatMessage {
    pub sender: String,
    pub content: String,
}

pub struct TuiApp {
    pub input: String,
    pub messages: Vec<ChatMessage>,
    pub scroll: u16,
    pub is_generating: bool,
    pub model_name: String,
    pub prefill_tok_s: f64,
    pub decode_tok_s: f64,
    pub ms_per_tok: f64,
    pub total_gen_tokens: usize,
}

impl TuiApp {
    pub fn new(model_name: String) -> Self {
        Self {
            input: String::new(),
            messages: vec![ChatMessage {
                sender: "System".to_string(),
                content: "🚀 Rust LLM Engine TUI Hazır! Mesajınızı yazıp Enter'a basın. (/clear sohbeti temizler, Esc çıkış yapar)".to_string(),
            }],
            scroll: 0,
            is_generating: false,
            model_name,
            prefill_tok_s: 0.0,
            decode_tok_s: 0.0,
            ms_per_tok: 0.0,
            total_gen_tokens: 0,
        }
    }

    pub fn run(mut self, runner: Arc<ModelRunner>) -> Result<()> {
        enable_raw_mode()?;
        let mut stdout = io::stdout();
        execute!(stdout, EnterAlternateScreen)?;
        let backend = CrosstermBackend::new(stdout);
        let mut terminal = Terminal::new(backend)?;

        let (tx, rx): (Sender<InferenceMessage>, Receiver<InferenceMessage>) = mpsc::channel();

        loop {
            // Process incoming inference tokens/metrics
            while let Ok(msg) = rx.try_recv() {
                match msg {
                    InferenceMessage::Token(token) => {
                        if let Some(last_msg) = self.messages.last_mut() {
                            if last_msg.sender == "AI" {
                                last_msg.content.push_str(&token);
                            }
                        }
                    }
                    InferenceMessage::Metrics {
                        prefill_tok_s,
                        decode_tok_s,
                        ms_per_tok,
                        total_gen_tokens,
                    } => {
                        self.prefill_tok_s = prefill_tok_s;
                        self.decode_tok_s = decode_tok_s;
                        self.ms_per_tok = ms_per_tok;
                        self.total_gen_tokens = total_gen_tokens;
                    }
                    InferenceMessage::Finished => {
                        self.is_generating = false;
                    }
                    InferenceMessage::Error(err) => {
                        self.messages.push(ChatMessage {
                            sender: "Error".to_string(),
                            content: err,
                        });
                        self.is_generating = false;
                    }
                }
            }

            terminal.draw(|f| self.draw(f))?;

            // Poll keyboard events (non-blocking with timeout to maintain 60 FPS)
            if event::poll(Duration::from_millis(16))? {
                if let Event::Key(key) = event::read()? {
                    match key.code {
                        KeyCode::Esc => {
                            break;
                        }
                        KeyCode::Char('c') if key.modifiers.contains(KeyModifiers::CONTROL) => {
                            break;
                        }
                        KeyCode::Enter => {
                            if !self.input.trim().is_empty() && !self.is_generating {
                                let user_text = self.input.trim().to_string();
                                self.input.clear();

                                if user_text == "/clear" {
                                    self.messages.clear();
                                    self.messages.push(ChatMessage {
                                        sender: "System".to_string(),
                                        content: "🧹 Sohbet geçmişi temizlendi.".to_string(),
                                    });
                                } else if user_text == "/help" {
                                    self.messages.push(ChatMessage {
                                        sender: "System".to_string(),
                                        content: "💡 Komutlar:\n  • /clear - Sohbeti temizler\n  • /help - Yardım gösterir\n  • Esc - Uygulamadan çıkar".to_string(),
                                    });
                                } else {
                                    // Add User Message
                                    self.messages.push(ChatMessage {
                                        sender: "User".to_string(),
                                        content: user_text.clone(),
                                    });

                                    // Add empty AI response placeholder
                                    self.messages.push(ChatMessage {
                                        sender: "AI".to_string(),
                                        content: String::new(),
                                    });

                                    self.is_generating = true;

                                    // Spawn Background Inference Thread
                                    let runner_clone = Arc::clone(&runner);
                                    let tx_clone = tx.clone();
                                    let prompt = format!(
                                        "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\nYou are a helpful AI assistant.<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n{}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n",
                                        user_text
                                    );

                                    thread::spawn(move || {
                                        let params = SamplerParams::default();
                                        if let Err(e) = runner_clone.generate_tui_stream(&prompt, 200, &params, &tx_clone) {
                                            let _ = tx_clone.send(InferenceMessage::Error(e.to_string()));
                                        }
                                    });
                                }
                            }
                        }
                        KeyCode::Char(c) => {
                            if !self.is_generating {
                                self.input.push(c);
                            }
                        }
                        KeyCode::Backspace => {
                            if !self.is_generating {
                                self.input.pop();
                            }
                        }
                        KeyCode::Up => {
                            if self.scroll > 0 {
                                self.scroll -= 1;
                            }
                        }
                        KeyCode::Down => {
                            self.scroll += 1;
                        }
                        _ => {}
                    }
                }
            }
        }

        disable_raw_mode()?;
        execute!(terminal.backend_mut(), LeaveAlternateScreen)?;
        terminal.show_cursor()?;

        Ok(())
    }

    fn draw(&self, f: &mut ratatui::Frame) {
        let chunks = Layout::default()
            .direction(Direction::Vertical)
            .constraints([Constraint::Min(5), Constraint::Length(3)].as_ref())
            .split(f.area());

        let main_chunks = Layout::default()
            .direction(Direction::Horizontal)
            .constraints([Constraint::Length(34), Constraint::Min(20)].as_ref())
            .split(chunks[0]);

        // 1. LEFT PANEL: STATUS & METRICS
        let metrics_text = vec![
            Line::from(vec![
                Span::styled("🤖 Model: ", Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD)),
                Span::raw(&self.model_name),
            ]),
            Line::from(vec![
                Span::styled("📦 Quant: ", Style::default().fg(Color::Yellow)),
                Span::styled("Q4_K / Q6_K SIMD", Style::default().fg(Color::Green)),
            ]),
            Line::from(vec![
                Span::styled("💾 KV-Cache: ", Style::default().fg(Color::Yellow)),
                Span::styled("FP16 (~50% RAM)", Style::default().fg(Color::Cyan)),
            ]),
            Line::from(Span::raw("──────────────────────────────")),
            Line::from(vec![
                Span::styled("⚡ Status: ", Style::default().fg(Color::Yellow)),
                if self.is_generating {
                    Span::styled("Generating... ⏳", Style::default().fg(Color::LightGreen).add_modifier(Modifier::BOLD))
                } else {
                    Span::styled("Idle 🟢", Style::default().fg(Color::Gray))
                },
            ]),
            Line::from(Span::raw("──────────────────────────────")),
            Line::from(vec![
                Span::styled("🚀 Prefill: ", Style::default().fg(Color::Cyan)),
                Span::styled(format!("{:.2} tok/s", self.prefill_tok_s), Style::default().fg(Color::White).add_modifier(Modifier::BOLD)),
            ]),
            Line::from(vec![
                Span::styled("🔥 Decode:  ", Style::default().fg(Color::Magenta)),
                Span::styled(format!("{:.2} tok/s", self.decode_tok_s), Style::default().fg(Color::Green).add_modifier(Modifier::BOLD)),
            ]),
            Line::from(vec![
                Span::styled("⏱️ Latency: ", Style::default().fg(Color::Blue)),
                Span::styled(format!("{:.2} ms/tok", self.ms_per_tok), Style::default().fg(Color::White)),
            ]),
            Line::from(vec![
                Span::styled("🔢 Generated: ", Style::default().fg(Color::Gray)),
                Span::raw(format!("{} tokens", self.total_gen_tokens)),
            ]),
        ];

        let metrics_block = Paragraph::new(metrics_text).block(
            Block::default()
                .title(" 📊 Status & Metrics ")
                .borders(Borders::ALL)
                .border_style(Style::default().fg(Color::Cyan)),
        );
        f.render_widget(metrics_block, main_chunks[0]);

        // 2. CHAT LOG PENCERESİ
        let mut chat_lines = Vec::new();
        for msg in &self.messages {
            let header_style = match msg.sender.as_str() {
                "User" => Style::default().fg(Color::LightCyan).add_modifier(Modifier::BOLD),
                "AI" => Style::default().fg(Color::LightMagenta).add_modifier(Modifier::BOLD),
                "System" => Style::default().fg(Color::Yellow).add_modifier(Modifier::ITALIC),
                _ => Style::default().fg(Color::Red),
            };

            chat_lines.push(Line::from(vec![
                Span::styled(format!("[{}]: ", msg.sender), header_style),
            ]));

            for line in msg.content.lines() {
                chat_lines.push(Line::from(Span::styled(
                    format!("  {}", line),
                    if msg.sender == "AI" {
                        Style::default().fg(Color::White)
                    } else {
                        Style::default().fg(Color::Gray)
                    },
                )));
            }
            chat_lines.push(Line::from(""));
        }

        let chat_block = Paragraph::new(chat_lines)
            .block(
                Block::default()
                    .title(" 💬 Chat Log (Scroll: ↑/↓) ")
                    .borders(Borders::ALL)
                    .border_style(Style::default().fg(Color::Magenta)),
            )
            .wrap(Wrap { trim: false })
            .scroll((self.scroll, 0));
        f.render_widget(chat_block, main_chunks[1]);

        // 3. INPUT BOX
        let input_style = if self.is_generating {
            Style::default().fg(Color::DarkGray)
        } else {
            Style::default().fg(Color::White)
        };

        let input_block = Paragraph::new(self.input.as_str())
            .style(input_style)
            .block(
                Block::default()
                    .title(if self.is_generating { " ⏳ Model yanıt üretiyor... " } else { " ⌨️ Mesajınızı yazın (Enter: Gönder) " })
                    .borders(Borders::ALL)
                    .border_style(if self.is_generating { Style::default().fg(Color::DarkGray) } else { Style::default().fg(Color::Green) }),
            );
        f.render_widget(input_block, chunks[1]);
    }
}
