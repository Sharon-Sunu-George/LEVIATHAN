mod backend;
mod commands;
mod token;

use commands::AppState;
use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .manage(AppState::default())
        .invoke_handler(tauri::generate_handler![
            commands::check_brain_health,
            commands::send_chat_message,
            commands::cancel_chat,
            commands::list_conversations,
            commands::create_conversation,
            commands::get_conversation_messages,
            commands::rename_conversation,
            commands::delete_conversation
        ])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            if let tauri::RunEvent::Exit = event {
                // Shut down child process started by LEVIATHAN
                if let Some(state) = app_handle.try_state::<AppState>() {
                    state.backend.shutdown();
                }
            }
        });
}
