use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use futures_util::StreamExt;
use serde::{Deserialize, Serialize};
use tauri::ipc::Channel;
use tauri::State;

use crate::backend::BackendManager;
use crate::token::read_session_token;

#[derive(Default)]
pub struct AppState {
    pub backend: BackendManager,
    pub cancellations: Arc<Mutex<HashMap<String, Arc<AtomicBool>>>>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct HealthStatus {
    pub healthy: bool,
    pub status: Option<String>,
    pub service: Option<String>,
    pub version: Option<String>,
    pub error: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatMessagePayload {
    pub role: String,
    pub content: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ChatRequestPayload {
    pub model: String,
    pub messages: Vec<ChatMessagePayload>,
    pub temperature: Option<f32>,
    pub request_id: String,
    pub conversation_id: Option<String>,
    pub user_message_id: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConversationItem {
    pub id: String,
    pub title: String,
    pub model: String,
    pub mode: String,
    pub created_at: i64,
    pub updated_at: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StoredMessage {
    pub id: String,
    pub conversation_id: String,
    pub sequence: i64,
    pub role: String,
    pub content: String,
    pub created_at: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatChunkEvent {
    pub delta: String,
    pub done: bool,
    pub error: Option<String>,
}

/// Ensure Python Brain is running and verify authenticated /health
#[tauri::command]
pub async fn check_brain_health(state: State<'_, AppState>) -> Result<HealthStatus, String> {
    // 1. Try to ensure backend child is started
    if let Err(e) = state.backend.ensure_started().await {
        return Ok(HealthStatus {
            healthy: false,
            status: None,
            service: None,
            version: None,
            error: Some(e),
        });
    }

    // 2. Fetch authenticated health response
    let token = match read_session_token() {
        Some(t) => t,
        None => {
            return Ok(HealthStatus {
                healthy: false,
                status: None,
                service: None,
                version: None,
                error: Some("Session token could not be read from disk".to_string()),
            });
        }
    };

    let client = reqwest::Client::new();
    match client
        .get("http://127.0.0.1:8000/health")
        .header("Authorization", format!("Bearer {}", token))
        .send()
        .await
    {
        Ok(res) => {
            if res.status().is_success() {
                #[derive(Deserialize)]
                struct RawHealth {
                    status: String,
                    service: String,
                    version: String,
                }
                if let Ok(data) = res.json::<RawHealth>().await {
                    Ok(HealthStatus {
                        healthy: true,
                        status: Some(data.status),
                        service: Some(data.service),
                        version: Some(data.version),
                        error: None,
                    })
                } else {
                    Ok(HealthStatus {
                        healthy: true,
                        status: Some("ok".to_string()),
                        service: Some("leviathan-brain".to_string()),
                        version: None,
                        error: None,
                    })
                }
            } else {
                Ok(HealthStatus {
                    healthy: false,
                    status: None,
                    service: None,
                    version: None,
                    error: Some(format!("Backend returned HTTP {}", res.status())),
                })
            }
        }
        Err(e) => Ok(HealthStatus {
            healthy: false,
            status: None,
            service: None,
            version: None,
            error: Some(format!("Failed to connect to Brain on 127.0.0.1:8000: {}", e)),
        }),
    }
}

/// Stream chat response from 127.0.0.1:8000/chat using Tauri Channel
#[tauri::command]
pub async fn send_chat_message(
    payload: ChatRequestPayload,
    on_event: Channel<ChatChunkEvent>,
    state: State<'_, AppState>,
) -> Result<(), String> {
    // 1. Ensure backend is running
    if let Err(e) = state.backend.ensure_started().await {
        let _ = on_event.send(ChatChunkEvent {
            delta: String::new(),
            done: true,
            error: Some(format!("Backend error: {}", e)),
        });
        return Err(e);
    }

    // 2. Read session token securely in native Rust memory
    let token = match read_session_token() {
        Some(t) => t,
        None => {
            let err_msg = "Cannot authenticate: session token not found".to_string();
            let _ = on_event.send(ChatChunkEvent {
                delta: String::new(),
                done: true,
                error: Some(err_msg.clone()),
            });
            return Err(err_msg);
        }
    };

    // 3. Register atomic cancellation flag for this request_id
    let cancel_flag = Arc::new(AtomicBool::new(false));
    {
        let mut map = state.cancellations.lock().unwrap();
        map.insert(payload.request_id.clone(), cancel_flag.clone());
    }

    let request_id_clone = payload.request_id.clone();
    let cancellations_clone = state.cancellations.clone();

    // 4. Send request to Python Brain POST /chat
    let client = reqwest::Client::new();
    let mut body = serde_json::json!({
        "model": payload.model,
        "messages": payload.messages,
        "temperature": payload.temperature.unwrap_or(0.7)
    });
    if let Some(conv_id) = &payload.conversation_id {
        body["conversation_id"] = serde_json::Value::String(conv_id.clone());
    }
    if let Some(msg_id) = &payload.user_message_id {
        body["user_message_id"] = serde_json::Value::String(msg_id.clone());
    }

    let resp = client
        .post("http://127.0.0.1:8000/chat")
        .header("Authorization", format!("Bearer {}", token))
        .header("Content-Type", "application/json")
        .json(&body)
        .send()
        .await;

    let response = match resp {
        Ok(r) => r,
        Err(e) => {
            let mut map = cancellations_clone.lock().unwrap();
            map.remove(&request_id_clone);
            let err_msg = format!("Failed to reach Brain chat endpoint: {}", e);
            let _ = on_event.send(ChatChunkEvent {
                delta: String::new(),
                done: true,
                error: Some(err_msg.clone()),
            });
            return Err(err_msg);
        }
    };

    if !response.status().is_success() {
        let status = response.status();
        let error_body = response.text().await.unwrap_or_default();
        let mut map = cancellations_clone.lock().unwrap();
        map.remove(&request_id_clone);
        let err_msg = format!("Brain error (HTTP {}): {}", status, error_body);
        let _ = on_event.send(ChatChunkEvent {
            delta: String::new(),
            done: true,
            error: Some(err_msg.clone()),
        });
        return Err(err_msg);
    }

    // 5. Stream SSE chunks from byte stream
    let mut stream = response.bytes_stream();
    let mut line_buffer = String::new();
    let mut stream_terminated = false;

    while let Some(chunk_result) = stream.next().await {
        if cancel_flag.load(Ordering::Relaxed) {
            let _ = on_event.send(ChatChunkEvent {
                delta: String::new(),
                done: true,
                error: Some("Generation stopped by user".to_string()),
            });
            stream_terminated = true;
            break;
        }

        match chunk_result {
            Ok(bytes) => {
                let text = String::from_utf8_lossy(&bytes);
                line_buffer.push_str(&text);

                // Process complete SSE lines delimited by \n
                while let Some(pos) = line_buffer.find('\n') {
                    let line = line_buffer[..pos].trim().to_string();
                    line_buffer = line_buffer[pos + 1..].to_string();

                    if line.starts_with("data: ") {
                        let data = &line[6..].trim();
                        if *data == "[DONE]" {
                            let _ = on_event.send(ChatChunkEvent {
                                delta: String::new(),
                                done: true,
                                error: None,
                            });
                            stream_terminated = true;
                            break;
                        }

                        #[derive(Deserialize)]
                        struct ServerChunk {
                            delta: Option<String>,
                            done: Option<bool>,
                            error: Option<String>,
                        }

                        if let Ok(parsed) = serde_json::from_str::<ServerChunk>(data) {
                            let is_done = parsed.done.unwrap_or(false);
                            let delta_str = parsed.delta.unwrap_or_default();
                            let err = parsed.error;

                            let _ = on_event.send(ChatChunkEvent {
                                delta: delta_str,
                                done: is_done,
                                error: err,
                            });

                            if is_done {
                                stream_terminated = true;
                                break;
                            }
                        }
                    }
                }

                if stream_terminated {
                    break;
                }
            }
            Err(e) => {
                let _ = on_event.send(ChatChunkEvent {
                    delta: String::new(),
                    done: true,
                    error: Some(format!("Streaming read error: {}", e)),
                });
                stream_terminated = true;
                break;
            }
        }
    }

    if !stream_terminated {
        let _ = on_event.send(ChatChunkEvent {
            delta: String::new(),
            done: true,
            error: None,
        });
    }

    // Clean up cancellation token
    let mut map = cancellations_clone.lock().unwrap();
    map.remove(&request_id_clone);

    Ok(())
}

/// Cancel an in-flight chat generation
#[tauri::command]
pub fn cancel_chat(request_id: String, state: State<'_, AppState>) -> bool {
    let map = state.cancellations.lock().unwrap();
    if let Some(flag) = map.get(&request_id) {
        flag.store(true, Ordering::Relaxed);
        true
    } else {
        false
    }
}

/// Helper to get an authenticated HTTP client and token
async fn get_auth_token(state: &State<'_, AppState>) -> Result<String, String> {
    if let Err(e) = state.backend.ensure_started().await {
        return Err(format!("Backend error: {}", e));
    }
    match read_session_token() {
        Some(token) => Ok(token),
        None => Err("Cannot authenticate: session token not found".to_string()),
    }
}

/// List conversations, optionally filtered by mode (default: 'personal')
#[tauri::command]
pub async fn list_conversations(
    mode: Option<String>,
    state: State<'_, AppState>,
) -> Result<Vec<ConversationItem>, String> {
    let token = get_auth_token(&state).await?;
    let client = reqwest::Client::new();
    let url = match &mode {
        Some(m) => format!("http://127.0.0.1:8000/conversations?mode={}", m),
        None => "http://127.0.0.1:8000/conversations".to_string(),
    };

    let resp = client
        .get(&url)
        .header("Authorization", format!("Bearer {}", token))
        .send()
        .await
        .map_err(|e| format!("Failed to fetch conversations: {}", e))?;

    if !resp.status().is_success() {
        let err = resp.text().await.unwrap_or_default();
        return Err(format!("Failed to list conversations: {}", err));
    }

    resp.json::<Vec<ConversationItem>>()
        .await
        .map_err(|e| format!("Failed to parse conversations response: {}", e))
}

/// Create a new conversation
#[tauri::command]
pub async fn create_conversation(
    title: String,
    model: String,
    mode: String,
    state: State<'_, AppState>,
) -> Result<ConversationItem, String> {
    let token = get_auth_token(&state).await?;
    let client = reqwest::Client::new();

    let body = serde_json::json!({
        "title": title,
        "model": model,
        "mode": mode,
    });

    let resp = client
        .post("http://127.0.0.1:8000/conversations")
        .header("Authorization", format!("Bearer {}", token))
        .header("Content-Type", "application/json")
        .json(&body)
        .send()
        .await
        .map_err(|e| format!("Failed to create conversation: {}", e))?;

    if !resp.status().is_success() {
        let err = resp.text().await.unwrap_or_default();
        return Err(format!("Failed to create conversation: {}", err));
    }

    resp.json::<ConversationItem>()
        .await
        .map_err(|e| format!("Failed to parse conversation response: {}", e))
}

/// Retrieve all messages for a given conversation
#[tauri::command]
pub async fn get_conversation_messages(
    conversation_id: String,
    mode: Option<String>,
    state: State<'_, AppState>,
) -> Result<Vec<StoredMessage>, String> {
    let token = get_auth_token(&state).await?;
    let client = reqwest::Client::new();
    let url = match &mode {
        Some(m) => format!(
            "http://127.0.0.1:8000/conversations/{}/messages?mode={}",
            conversation_id, m
        ),
        None => format!(
            "http://127.0.0.1:8000/conversations/{}/messages",
            conversation_id
        ),
    };

    let resp = client
        .get(&url)
        .header("Authorization", format!("Bearer {}", token))
        .send()
        .await
        .map_err(|e| format!("Failed to fetch messages: {}", e))?;

    if !resp.status().is_success() {
        let err = resp.text().await.unwrap_or_default();
        return Err(format!("Failed to get conversation messages: {}", err));
    }

    resp.json::<Vec<StoredMessage>>()
        .await
        .map_err(|e| format!("Failed to parse messages response: {}", e))
}

/// Rename an existing conversation
#[tauri::command]
pub async fn rename_conversation(
    conversation_id: String,
    title: String,
    state: State<'_, AppState>,
) -> Result<ConversationItem, String> {
    let token = get_auth_token(&state).await?;
    let client = reqwest::Client::new();

    let body = serde_json::json!({ "title": title });

    let resp = client
        .patch(format!(
            "http://127.0.0.1:8000/conversations/{}",
            conversation_id
        ))
        .header("Authorization", format!("Bearer {}", token))
        .header("Content-Type", "application/json")
        .json(&body)
        .send()
        .await
        .map_err(|e| format!("Failed to rename conversation: {}", e))?;

    if !resp.status().is_success() {
        let err = resp.text().await.unwrap_or_default();
        return Err(format!("Failed to rename conversation: {}", err));
    }

    resp.json::<ConversationItem>()
        .await
        .map_err(|e| format!("Failed to parse renamed conversation: {}", e))
}

/// Delete a conversation and all its messages
#[tauri::command]
pub async fn delete_conversation(
    conversation_id: String,
    state: State<'_, AppState>,
) -> Result<bool, String> {
    let token = get_auth_token(&state).await?;
    let client = reqwest::Client::new();

    let resp = client
        .delete(format!(
            "http://127.0.0.1:8000/conversations/{}",
            conversation_id
        ))
        .header("Authorization", format!("Bearer {}", token))
        .send()
        .await
        .map_err(|e| format!("Failed to delete conversation: {}", e))?;

    if !resp.status().is_success() {
        let err = resp.text().await.unwrap_or_default();
        return Err(format!("Failed to delete conversation: {}", err));
    }

    Ok(true)
}
