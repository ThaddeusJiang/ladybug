//! Keep native link inputs separate from `CMake` objects and configuration state.

use std::{
    collections::BTreeMap,
    fs, io,
    path::{Path, PathBuf},
};

pub fn stage_library(source: &Path, destination: &Path) -> io::Result<()> {
    if destination.exists() && fs::read(source)? == fs::read(destination)? {
        return Ok(());
    }
    fs::copy(source, destination)?;
    Ok(())
}

pub fn stage_directories(sources: &[PathBuf], destination: &Path) -> io::Result<()> {
    let mut libraries = BTreeMap::new();
    for source in sources {
        for entry in fs::read_dir(source)? {
            let entry = entry?;
            let name = entry.file_name();
            let text = name.to_string_lossy();
            let library = text.ends_with(".a")
                || text.ends_with(".lib")
                || text.ends_with(".dylib")
                || text.ends_with(".so")
                || text.contains(".so.");
            if library && entry.path().is_file() {
                if let Some(previous) = libraries.insert(name.clone(), entry.path()) {
                    if fs::read(previous)? != fs::read(entry.path())? {
                        return Err(io::Error::new(
                            io::ErrorKind::AlreadyExists,
                            format!(
                                "different native libraries share {}",
                                name.to_string_lossy()
                            ),
                        ));
                    }
                }
            }
        }
    }
    fs::create_dir_all(destination)?;
    // This directory belongs to this build script. Remove obsolete staged
    // libraries when the selected native dependencies change.
    for entry in fs::read_dir(destination)? {
        let entry = entry?;
        if !libraries.contains_key(&entry.file_name()) {
            fs::remove_file(entry.path())?;
        }
    }
    for (name, source) in libraries {
        stage_library(&source, &destination.join(name))?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn stages_only_link_inputs_and_rejects_conflicting_names() -> io::Result<()> {
        let root = std::env::temp_dir().join(format!(
            "lbug-native-cache-{}-{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        let source = root.join("cmake");
        let output = root.join("native");
        fs::create_dir_all(source.join("CMakeFiles"))?;
        fs::create_dir_all(&output)?;
        for name in [
            "libfixture.a",
            "fixture.lib",
            "libfixture.so.1",
            "libfixture.dylib",
        ] {
            fs::write(source.join(name), name)?;
        }
        fs::write(source.join("fixture.o"), "object")?;
        fs::write(source.join("CMakeCache.txt"), "configuration")?;
        fs::write(source.join("CMakeFiles/large.o"), "object")?;
        stage_directories(std::slice::from_ref(&source), &output)?;
        assert_eq!(fs::read_dir(&output)?.count(), 4);
        assert!(!output.join("CMakeFiles").exists());
        assert!(!output.join("fixture.o").exists());
        stage_directories(std::slice::from_ref(&source), &output)?;
        fs::write(source.join("libfixture.a"), "different")?;
        stage_directories(std::slice::from_ref(&source), &output)?;
        assert_eq!(
            fs::read_to_string(output.join("libfixture.a"))?,
            "different"
        );
        let other = root.join("other");
        fs::create_dir_all(&other)?;
        fs::write(other.join("libfixture.a"), "conflict")?;
        assert_eq!(
            stage_directories(&[source, other], &output)
                .unwrap_err()
                .kind(),
            io::ErrorKind::AlreadyExists
        );
        fs::remove_dir_all(root)
    }
}
