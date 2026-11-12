# Build downloads

The product name is **Chess Engine Battle**. Nocturne Chess is its upstream
dependency, not this application's name. Keep upstream license attributions.

Default to a dark theme. Keep Reset view and the current-match game picker
accessible even when users resize or hide the games table.

Use the existing **main** branch for all changes and builds. Do not create a new
branch per version or build. Preserve existing historical branches and download
links; new releases continue on main without resetting or rewriting history.

For each version, add brief user-facing change notes to CHANGELOG.md. After its
Windows build succeeds, add the direct download link and a short description of
what changed to the top of README.md's Build downloads list. Keep prior entries.
Commit download-only documentation updates with [skip ci] to avoid another build.

For every new build produced for the user, include its version and a direct clickable link to the completed build in the main README and in the chat response. Keep earlier build links available. Clearly state the target platform, and do not describe a build as complete or link to an artifact until the build has succeeded. The user prefers Windows builds. Record links to published durable artifacts in the README; clearly mark any local-only artifacts.
