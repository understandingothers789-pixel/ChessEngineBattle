# Chess Engine Battle changes

Download links and validation details are in [README.md](README.md#build-downloads).
New builds use the main branch; version numbers distinguish downloads.

## 0.3.8

- Renamed the app to Chess Engine Battle, including its window, dialogs,
  Windows executable and download archive. Existing settings and games stay available.
- Brought all recent features and build notes onto main. Future automatic builds
  use main instead of creating a branch for each build.
- Kept the download history in the README and recorded the release process in
  the repository instructions.

## 0.3.7

- Show live MultiPV thinking on the right with hover previews; clicking a played
  move opens its recorded final search.
- Add manual and evaluation-based adjudication, plus automatic draw agreement
  after move 50 at ±0.20 pawns for ten consecutive plies.
- Distribute opening books separately from the application. Accept six-field FEN
  positions inside EPD opening files (included since 0.3.6).

Earlier versions and their change notes remain in the README's download history.
