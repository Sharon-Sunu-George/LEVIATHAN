use std::path::PathBuf;

/// Locate the project root by searching upwards from the current directory or executable.
pub fn find_project_root() -> Option<PathBuf> {
    // 1. Try current working directory
    if let Ok(cwd) = std::env::current_dir() {
        let mut cur = cwd.clone();
        for _ in 0..6 {
            if cur.join("services").join("brain").join("main.py").exists() {
                return Some(cur);
            }
            if !cur.pop() {
                break;
            }
        }
    }

    // 2. Try executable directory
    if let Ok(exe_path) = std::env::current_exe() {
        let mut cur = exe_path;
        for _ in 0..6 {
            if cur.join("services").join("brain").join("main.py").exists() {
                return Some(cur);
            }
            if !cur.pop() {
                break;
            }
        }
    }

    None
}

/// Find services/brain directory
pub fn get_brain_dir() -> Option<PathBuf> {
    find_project_root().map(|root| root.join("services").join("brain"))
}

/// Read the session token from services/brain/.session_token in native memory
pub fn read_session_token() -> Option<String> {
    let brain_dir = get_brain_dir()?;
    let token_path = brain_dir.join(".session_token");
    if token_path.exists() {
        if let Ok(token) = std::fs::read_to_string(&token_path) {
            let trimmed = token.trim().to_string();
            if !trimmed.is_empty() {
                return Some(trimmed);
            }
        }
    }
    None
}

