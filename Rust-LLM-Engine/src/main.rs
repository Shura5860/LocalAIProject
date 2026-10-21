use anyhow::Result;
use memmap2::MmapOptions;
use std::env;
use std::fs::File;
use std::io::Cursor;
use std::sync::Arc;

use rust_llm_engine::ops::SamplerParams;
use rust_llm_engine::{GgufHeader, ModelRunner, TuiApp};

fn main() -> Result<()> {
    let args: Vec<String> = env::args().collect();
    let mut model_path = "model.gguf".to_string();
    let mut prompt: Option<String> = None;
    let mut max_tokens: usize = 256;
    let mut is_cli_mode = false;

    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--model" => {
                if i + 1 < args.len() {
                    model_path = args[i + 1].clone();
                    i += 1;
                }
            }
            "--prompt" => {
                if i + 1 < args.len() {
                    prompt = Some(args[i + 1].clone());
                    i += 1;
                }
            }
            "--max-tokens" => {
                if i + 1 < args.len() {
                    if let Ok(val) = args[i + 1].parse::<usize>() {
                        max_tokens = val;
                    }
                    i += 1;
                }
            }
            "--cli" => {
                is_cli_mode = true;
            }
            _ => {}
        }
        i += 1;
    }

    let file = File::open(&model_path)?;
    let mmap = unsafe { MmapOptions::new().map(&file)? };
    let mut reader = Cursor::new(&mmap[..]);

    let header = GgufHeader::parse(&mut reader)?;

    let mut tensor_data_offset = reader.position() as usize;
    let alignment = header
        .metadata
        .get("general.alignment")
        .and_then(|v| v.to_u64())
        .unwrap_or(32) as usize;
    let remainder = tensor_data_offset % alignment;
    if remainder != 0 {
        tensor_data_offset += alignment - remainder;
    }

    let runner = ModelRunner::load(header, &mmap, tensor_data_offset)?;

    if is_cli_mode || prompt.is_some() {
        let p = prompt.unwrap_or_else(|| "Merhaba, sen kimsin?".to_string());
        let params = SamplerParams {
            temperature: 0.7,
            top_k: 40,
            top_p: 0.9,
            repetition_penalty: 1.1,
        };
        let response = runner.generate_string(&p, max_tokens, &params)?;
        println!("{}", response);
        return Ok(());
    }

    println!("🚀 Full Engine (Ratatui TUI Mode) Yükleniyor...");
    let runner_arc = Arc::new(runner);
    let app = TuiApp::new("Llama-3 1B".to_string());
    app.run(runner_arc)?;

    Ok(())
}