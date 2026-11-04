# Troubleshooting

**No PNG, or "Playwright isn't installed".** A PNG, and the SVG the editor
draws, need Playwright and its Chromium. Without them `compose` and
`export:project` write the HTML and an SVG from the static renderer and print
`no PNG written:` with the reason; `--formats png` named on purpose stops
before anything is written. The message gives the exact commands for the
Python that runs `infragram`; in general:

```bash
python -m pip install playwright pillow
python -m playwright install chromium     # on Linux: python -m playwright install --with-deps chromium
```

An install made with `uv tool` has no pip: reinstall it with the `png` extra
and Playwright's own command, then install the browser with it, so the
browser matches that Playwright:

```bash
uv tool install --reinstall "./plugin[png]" --with-executables-from playwright   # or the source you installed from
playwright install chromium
```

(`--with-deps` installs the system libraries Chromium needs, so it asks for
root.)

**A slow machine: the export gives up while drawing.** A page gets 120 seconds
to draw. Give it longer with `--timeout SECONDS` on any exporting command
(`infragram compose shop.py --timeout 300`) or `INFRAGRAM_RENDER_TIMEOUT_MS`
in the environment, in milliseconds.

**No network, or a proxy.** Drawing needs no network: a page carries its
libraries and fonts, and prices come from the tables shipped with Infragram.
`--offline` (or `INFRAGRAM_RENDER_OFFLINE=1`) makes the browser refuse any
request while it draws. Only `--prices` reads the network during an export
(EC2's published prices, over https); behind a proxy, set `HTTPS_PROXY` as for
any Python program.

**Windows: a path too long.** The deepest file in the wheel is 157 characters
below `site-packages` (an AWS icon under `infragram/_plugin/skills/`), so an
install into a deep folder can pass Windows' 260-character limit and fail
writing it. Either turn on long paths (Windows 10 1607 or later: the "Enable
Win32 long paths" group policy, or `LongPathsEnabled` set to 1 under
`HKLM\SYSTEM\CurrentControlSet\Control\FileSystem`; then open a new terminal),
or install to a short path: set `UV_TOOL_DIR` to a folder such as `C:\uvtools`
before `uv tool install`, or make the virtual environment near the drive's
root. A checkout is as deep below `plugin/`: clone near the root, or run
`git config --global core.longpaths true`.

**"refusing to overwrite".** An export replaces the files it wrote there last
time. A file it did not write, or one edited since (a page saved from the
editor, a diagram file changed by hand), stops the export before anything is
written, and the message names each file. `--force` replaces them. What was
written is recorded in Infragram's cache (`INFRAGRAM_CACHE`; by default
`%LOCALAPPDATA%\infragram\cache` on Windows and `~/.cache/infragram`
elsewhere), not beside the files, so a folder copied from another machine is
refused until `--force`.

**The page shows an older drawing, or an older editor.** An exported page
carries its own copy of the editor, so an upgrade changes no page already
written: export it again. The editor also keeps each document in the
browser's local storage under its slug (`infragram-editor:<slug>`), written
as soon as the page opens, and opens with what is kept there. A page exported
again under the same name can therefore come up as the earlier copy was left.
Add `?fresh=1` to the page's address for a workspace that starts from what the
page carries (any name after `fresh=` gives a separate one), or delete that
entry in the browser's developer tools (Application, Local storage).

[Documentation](README.md) · [Project README](../README.md)
