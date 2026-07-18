// CHSuite - Tauri shell.
//
// Responsibilities of the Rust layer are intentionally thin: it owns the native
// window (frameless, custom titlebar drawn by the web frontend) and launches the
// Python "sidecar" that hosts all of the real Clone Hero tooling logic over a
// localhost HTTP API. The frontend talks to that API directly; Rust only needs
// to tell the frontend which ephemeral port the sidecar bound to.

use std::io::{BufRead, BufReader};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;

use tauri::{Manager, State};

/// Shared handle to the running sidecar process + the port it reported.
#[derive(Default)]
struct Sidecar {
    port: Mutex<Option<u16>>,
    child: Mutex<Option<Child>>,
}

/// Returned to the frontend so it can build the API base URL.
#[tauri::command]
fn sidecar_port(state: State<Sidecar>) -> Option<u16> {
    *state.port.lock().unwrap()
}

/// Resolve the python interpreter to use. A bundled/venv interpreter takes
/// precedence so end users never need a system Python; otherwise fall back to
/// whatever is on PATH (handy during development).
fn resolve_python(app: &tauri::AppHandle) -> (std::path::PathBuf, std::path::PathBuf) {
    use tauri::path::BaseDirectory;

    // In a bundled build the sidecar ships under resources/sidecar.
    let bundled_script = app
        .path()
        .resolve("sidecar/chsuite_api.py", BaseDirectory::Resource)
        .ok();

    // During `tauri dev` the cwd is src-tauri, so the sidecar lives one up.
    let dev_script = std::env::current_dir()
        .map(|d| d.join("..").join("sidecar").join("chsuite_api.py"))
        .ok();

    let script = bundled_script
        .filter(|p| p.exists())
        .or(dev_script)
        .unwrap_or_else(|| std::path::PathBuf::from("../sidecar/chsuite_api.py"));

    let sidecar_dir = script
        .parent()
        .map(|p| p.to_path_buf())
        .unwrap_or_else(|| std::path::PathBuf::from("."));

    // Prefer a venv interpreter colocated with the sidecar if present.
    #[cfg(windows)]
    let venv_py = sidecar_dir.join(".venv").join("Scripts").join("python.exe");
    #[cfg(not(windows))]
    let venv_py = sidecar_dir.join(".venv").join("bin").join("python");

    let python = if venv_py.exists() {
        venv_py
    } else {
        // `python` on Windows, `python3` elsewhere as a sane default.
        #[cfg(windows)]
        {
            std::path::PathBuf::from("python")
        }
        #[cfg(not(windows))]
        {
            std::path::PathBuf::from("python3")
        }
    };

    (python, script)
}

/// Resolve how to start the sidecar. In a bundled/production build we ship a
/// standalone PyInstaller executable (no Python required on the target machine);
/// during development we fall back to running the script with an interpreter.
fn resolve_sidecar_command(app: &tauri::AppHandle) -> Command {
    use tauri::path::BaseDirectory;

    let exe_name = if cfg!(windows) {
        "chsuite-sidecar.exe"
    } else {
        "chsuite-sidecar"
    };

    // 1. Bundled standalone sidecar (production): resources/sidecar/<exe>.
    let bundled = app
        .path()
        .resolve(format!("sidecar/{exe_name}"), BaseDirectory::Resource)
        .ok();
    // 2. A locally-built standalone sidecar next to the sources (dev convenience).
    let dev_exe = std::env::current_dir()
        .ok()
        .map(|d| d.join("..").join("sidecar").join(exe_name));

    for cand in [bundled, dev_exe].into_iter().flatten() {
        if cand.exists() {
            return Command::new(cand);
        }
    }

    // 3. Development fallback: a Python interpreter running the script directly.
    let (python, script) = resolve_python(app);
    let mut cmd = Command::new(python);
    cmd.arg(script);
    cmd
}

/// Launch the sidecar and capture the port it announces on stdout
/// (`CHSUITE_PORT=<n>`). Returns the process handle and the resolved port.
fn spawn_sidecar(app: &tauri::AppHandle) -> Result<(Child, u16), String> {
    let mut cmd = resolve_sidecar_command(app);
    cmd.stdout(Stdio::piped()).stderr(Stdio::inherit());

    // Hide the console window the child would otherwise flash on Windows.
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }

    let mut child = cmd
        .spawn()
        .map_err(|e| format!("failed to launch sidecar: {e}"))?;

    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| "sidecar produced no stdout".to_string())?;

    // Read the announcement line (blocking, but it is the very first thing the
    // sidecar prints, so startup latency is just the Python import time).
    let mut reader = BufReader::new(stdout);
    let mut port: Option<u16> = None;
    let mut line = String::new();
    for _ in 0..50 {
        line.clear();
        match reader.read_line(&mut line) {
            Ok(0) => break, // EOF - sidecar died
            Ok(_) => {
                if let Some(rest) = line.trim().strip_prefix("CHSUITE_PORT=") {
                    if let Ok(p) = rest.parse::<u16>() {
                        port = Some(p);
                        break;
                    }
                }
            }
            Err(_) => break,
        }
    }

    // Keep draining stdout in the background so the pipe never fills and blocks
    // the sidecar (it logs request lines there).
    std::thread::spawn(move || {
        let mut sink = String::new();
        while reader.read_line(&mut sink).map(|n| n > 0).unwrap_or(false) {
            sink.clear();
        }
    });

    match port {
        Some(p) => Ok((child, p)),
        None => {
            let _ = child.kill();
            Err("sidecar did not report a port".into())
        }
    }
}

/// Kill the sidecar and every process it spawned. A plain `Child::kill()` only
/// signals the direct child - fine for a plain script, but the bundled sidecar
/// is a PyInstaller onefile executable, which re-execs itself as a child
/// process on first launch. `child.kill()` alone leaves that re-exec'd process
/// (the one actually holding the HTTP server / scan threads / song cache file)
/// running forever as an orphan after the window closes. `taskkill /T` walks
/// the whole process tree rooted at the child's PID instead.
fn kill_tree(child: &mut Child) {
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        let _ = Command::new("taskkill")
            .args(["/PID", &child.id().to_string(), "/T", "/F"])
            .creation_flags(CREATE_NO_WINDOW)
            .status();
    }
    #[cfg(not(windows))]
    {
        let _ = child.kill();
    }
    let _ = child.wait();
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(Sidecar::default())
        .invoke_handler(tauri::generate_handler![sidecar_port])
        .setup(|app| {
            let handle = app.handle().clone();
            match spawn_sidecar(&handle) {
                Ok((child, port)) => {
                    let state = app.state::<Sidecar>();
                    *state.port.lock().unwrap() = Some(port);
                    *state.child.lock().unwrap() = Some(child);
                    eprintln!("[chsuite] sidecar listening on 127.0.0.1:{port}");
                }
                Err(e) => {
                    eprintln!("[chsuite] WARNING: {e}");
                }
            }
            Ok(())
        })
        .on_window_event(|window, event| {
            // Make sure the sidecar process is reaped when the app closes.
            if let tauri::WindowEvent::Destroyed = event {
                if let Some(state) = window.try_state::<Sidecar>() {
                    if let Some(mut child) = state.child.lock().unwrap().take() {
                        kill_tree(&mut child);
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running CHSuite");
}
