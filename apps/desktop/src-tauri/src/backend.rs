use std::process::{Child, Command};
use std::sync::{Arc, Mutex};
use std::time::Duration;
use crate::token::{get_brain_dir, read_session_token};

#[derive(Default)]
pub struct BackendManager {
    child: Arc<Mutex<Option<Child>>>,
}

impl BackendManager {
    pub fn new() -> Self {
        Self {
            child: Arc::new(Mutex::new(None)),
        }
    }

    /// Check if backend is already healthy at http://127.0.0.1:8000/health
    pub async fn is_healthy(&self) -> bool {
        let token = match read_session_token() {
            Some(t) => t,
            None => return false,
        };

        let client = match reqwest::Client::builder()
            .timeout(Duration::from_millis(1500))
            .build()
        {
            Ok(c) => c,
            Err(_) => return false,
        };

        let resp = client
            .get("http://127.0.0.1:8000/health")
            .header("Authorization", format!("Bearer {}", token))
            .send()
            .await;

        if let Ok(res) = resp {
            res.status().is_success()
        } else {
            false
        }
    }

    /// Start the Python Brain backend child process if not already running
    pub async fn ensure_started(&self) -> Result<(), String> {
        // If already responding to authenticated /health, reuse existing instance
        if self.is_healthy().await {
            return Ok(());
        }

        let brain_dir = get_brain_dir().ok_or_else(|| {
            "Could not locate services/brain directory in project root".to_string()
        })?;

        let python_exe = brain_dir.join(".venv").join("Scripts").join("python.exe");
        if !python_exe.exists() {
            return Err(format!(
                "Python virtual environment executable not found at: {}",
                python_exe.display()
            ));
        }

        let main_py = brain_dir.join("main.py");
        if !main_py.exists() {
            return Err(format!("main.py not found at: {}", main_py.display()));
        }

        // Spawn python main.py inside services/brain
        let mut cmd = Command::new(&python_exe);
        cmd.arg("main.py").current_dir(&brain_dir);

        // Hide console window on Windows for child process if desired
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            const CREATE_NO_WINDOW: u32 = 0x08000000;
            cmd.creation_flags(CREATE_NO_WINDOW);
        }

        let child = cmd
            .spawn()
            .map_err(|e| format!("Failed to spawn Python Brain backend: {}", e))?;

        {
            let mut guard = self.child.lock().unwrap();
            *guard = Some(child);
        }

        // Wait up to 10 seconds for backend to initialize and become healthy
        for _ in 0..20 {
            tokio::time::sleep(Duration::from_millis(500)).await;
            if self.is_healthy().await {
                return Ok(());
            }
        }

        Err("Python Brain was spawned but failed to become healthy within 10 seconds. Check port 8000 conflicts or logs.".to_string())
    }

    /// Shut down the child process started by LEVIATHAN
    pub fn shutdown(&self) {
        let mut guard = self.child.lock().unwrap();
        if let Some(mut child) = guard.take() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

