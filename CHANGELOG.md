# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2025-09-22

### Added
- **Project Screenshots**: Added a new screenshot gallery to the `README.md` to visually showcase the application's user interface.
- **Changelog**: Created a `CHANGELOG.md` file to track project versions and notable changes.
- **AI-Assisted Workflow**: Established a new workflow for updating version numbers and changelogs at the end of each issue.

### Changed
- **Project Structure**: Major refactoring of the project layout to follow standard conventions.
  - Renamed `wkndPlanning` directory to `src/`.
  - Moved runtime-generated directories (`logs`, `output`) to the project root.
  - Created a new `instance/` directory for the database.
  - Created a `docs/assets/` directory for documentation images.
- **Documentation**: Overhauled and updated the `README.md` with a more detailed and user-friendly "Setup and Installation" section and accurate project structure.
- **Issue Management**: Streamlined the issue and documentation workflow.
  - The AI assistant will now use the `gh issue list` command to fetch issues directly from GitHub.
  - Updated AI instruction files (`.github/AGENT.md`, `.github/copilot-instructions.md`) to reflect the new workflow.

### Removed
- **Obsolete `uploads` Directory**: Removed the unused `uploads` folder and all associated references from the code, configuration, and documentation.
- **Redundant Documentation**: Deleted obsolete `issues.md` and `ROADMAP.md` files to establish GitHub as the single source of truth.

## [1.1.0] - 2024-05-01

- Initial release version after major feature implementation.
