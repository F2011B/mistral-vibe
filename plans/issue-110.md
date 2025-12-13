# Plan for Issue #110: Cannot install package in editable mode using pip

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/110

## Description
### Description  
When installing this project via pip (either in editable mode with `pip install -e .` or with a normal `pip install .`), the installation itself succeeds on Windows. However, when running the CLI executable `vibe` after installation, it fails with an error indicating that the `vibe` package cannot be found. The repository is checked out under the name `mistral-vibe`, but the registered entry point expects a `vibe` package, which appears to cause the import error.  

### Steps to reproduce  
- Clone the repository (the directory is named `mistral-vibe`).  
- Change into the repository directory.  
- Run `pip install -e .` (or `pip install .`) – it installs without error.  
- Invoke the CLI by running `vibe` from the command line.  

### Expected behavior  
- After installation, running the `vibe` executable should start the CLI without errors.  

### Actual behavior  
- The package installs without errors via pip.  
- When executing the `vibe` command, it aborts with an import error stating that the `vibe` package cannot be found, likely because the project directory is named `mistral-vibe` but the entry point references the `vibe` package.  

### Environment  
- Operating system: Windows 11  
- Python version: 3.12  
- pip version: 24.0
