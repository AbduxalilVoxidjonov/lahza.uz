---
status: accepted
---

# The project folder is an agent's working directory

Date: 2026-10-28

## Context

Users start coding agents (Claude Code, Codex, Cursor and others) inside a
project folder and want to work from there: mention a media file and have
the agent tie it to the app's media pool, edit the project's TASTE.md, read
the project. The app supports any MCP client, so what it builds on has to
work for all of them.

Several mechanisms tell a server where its client works. None is shared by
every client:

- MCP roots: the client lists its directories on request. Few clients
  implement them, and the draft specification deprecates them.
- Claude Code sets `CLAUDE_PROJECT_DIR` in a stdio server's environment.
  No other client does.
- An @-mention of a resource is a client feature. Claude Code lists a
  server's resources at its prompt and attaches the one picked; a client that
  supports tools alone offers none of this.

Tools are the one surface every client has. Every coding agent also knows its
own working directory, and when a user mentions a file it hands the model a
path.

## Decision

- **A relative path is read from the open project's folder.** `import_media`
  takes an absolute path, or one relative to the folder of the project open
  in the app. The app never tries to learn the client's working directory.
  When that directory is the project folder, the two agree. When the path
  names nothing there, or no project is open, the call is refused, the
  refusal names the folder, and it asks for an absolute path. A Windows drive
  path counts as absolute on every host. The shim is unchanged.
- **The agent checks that its folder is the open project.** `project://session`
  already reports `project.dir`. The initialize instructions tell an agent
  whose working directory holds `project.json` to compare the two and to ask
  if they differ.
- **The folder's files change through tools, TASTE.md aside.** `project.json`
  is written only by the app, whose autosave would overwrite an agent's edit.
  The pool records `Media/` files by path, so they are never renamed or
  moved. `Cache/` is derived data. TASTE.md is the one file an agent edits by
  hand (ADR 0126). `project://taste` reports where TASTE.md goes even before
  it exists. The initialize instructions carry the rule in one sentence, and
  the skill carries the long form.
- **A mentioned file is matched by importing it.** The import answers the
  pool item a file already has (ADR 0151), so `import_media` is how a path
  becomes a media id. No lookup tool is added.
- **Each pooled file is a resource, `media://{id}`.** `resources/list` names
  one per pooled file. Reading it answers a short card: the record, its
  `path_rel`, the layers that place it, and its sub-resources. A client that
  offers resources at its prompt therefore lets the user @-mention a media
  item. The server declares `resources.listChanged` and notifies when the
  pool's files or names change. `read_project { view: "media", id }` reads
  the same card for a client that supports tools alone. This is an
  enhancement: nothing above depends on it.

## Consequences

The same steps work in every client: an agent in the project folder passes
the path it was shown to `import_media` and gets back the id the app uses.
In clients that list resources, the user can also pick a media item by name.
`resources/list` grows with the pool. The initialize instructions grew from
1400 to 1550 characters to carry the folder rule, because an agent working
in the folder would otherwise edit `project.json` while the app autosaves.
