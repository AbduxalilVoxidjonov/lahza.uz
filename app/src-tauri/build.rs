fn main() {
    // A release must run on a fresh computer, without PATH/Homebrew fallbacks.
    if std::env::var("PROFILE").as_deref() == Ok("release") {
        let suffix = if std::env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("windows") {
            ".exe"
        } else {
            ""
        };
        for name in ["ffmpeg", "ffprobe", "llama-server"] {
            let path = std::path::Path::new("resources/bin").join(format!("{name}{suffix}"));
            println!("cargo:rerun-if-changed={}", path.display());
            assert!(
                path.is_file(),
                "Required bundled runtime missing: {}",
                path.display()
            );
        }
    }
    let catalog_dir = std::path::Path::new("../../build/sidecar/catalog");
    let catalog_key = catalog_dir.join("catalog.pub");
    println!("cargo:rerun-if-env-changed=LAHZA_CATALOG_PUBKEY");
    println!("cargo:rerun-if-changed={}", catalog_key.display());
    println!(
        "cargo:rerun-if-changed={}",
        catalog_dir.join("catalog.json").display()
    );
    let key = std::fs::read_to_string(&catalog_key)
        .expect("Run scripts/build_sidecar.py --catalog-only (or a full sidecar build) first");
    let key = key.trim();
    assert!(!key.is_empty(), "Bundled catalog public key is empty");
    if let Ok(explicit) = std::env::var("LAHZA_CATALOG_PUBKEY") {
        assert_eq!(explicit.trim(), key, "Explicit catalog key differs from staged catalog; rerun scripts/build_sidecar.py with the same key");
    }
    println!("cargo:rustc-env=LAHZA_BUNDLED_CATALOG_PUBKEY={key}");
    tauri_build::build()
}
