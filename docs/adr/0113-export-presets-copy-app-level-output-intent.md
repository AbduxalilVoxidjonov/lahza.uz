# ADR 0113: Export presets copy app-level output intent

Status: Accepted

## Context

Project `export.json` remembers export settings but cannot provide reusable
personal recipes across projects. The existing quality shortcut only controls
video bitrate, not the complete output configuration.

## Decision

An Export preset is a named, versioned set of portable output parameters. Four
read-only built-ins cover matching the project, 720p HD landscape, 1080p Full HD
landscape and 4K UHD landscape. Personal presets and the default preset ID live
in `app_settings.json`, using its existing atomic main-process ownership and
change stream. Library changes are individual create/update/rename/delete
operations against the latest settings, not replacement arrays from renderers.

The export dialog is the sole human UI preset management entry point. One menu button
alongside its title groups built-in and personal choices, marks the current
choice separately from the default, and places commands below the choices.
Save-as, update and restore stay in this menu; the footer contains only Cancel
and Export. Update appears only for a modified personal preset, and Restore
for any modified preset.
There is no settings page, separate parameter editor, repeated label, summary
or explanatory text. Users apply a preset, modify the existing export form,
and explicitly update the preset, save a new one or restore the applied values.
Personal recipes additionally offer renaming and deletion. Setting the
new-project default is an explicit command. Only name entry opens a dialog.
Engine/acceleration choices, file paths, collision policy and export ranges
are excluded from presets.

Names have a 40-character storage limit, with a count in the naming form.
The title control is capped at 240 UI pixels and the menu at 320 UI pixels,
constrained by available window space. Long names use single-line ellipsis;
hover or keyboard focus reveals the full name in a tooltip. Default and
modified markers remain separate from the truncated name.

This follows the compact template-menu precedent of After Effects' output
module menu with its Make Template action, rather than adopting Premiere's
separate catalog-style Preset Manager for this small initial library.

Applying a preset copies its output values into the current dialog. Saving or
updating the library is explicit. Existing projects retain their parameter
snapshots when a preset is modified or deleted; project files do not need a live
reference to the library. Existing project settings take priority over the
personal default, then the match-project built-in. UI and MCP use the same
default resolver. Starting a UI export continues to save project settings as
before; MCP overrides remain per-job.

MCP exposes list/create/update/rename/delete/set-default tools over the same
application settings store and change stream, available without an open project.
`get_export_options` and `start_export` accept an optional `preset_id`: selecting
one copies its project-adapted output values, followed by per-job overrides.
Omitting the ID preserves the existing saved-project/default precedence. An
admitted job snapshots the selected preset; later library edits or deletion do
not affect it, including when the same request ID is replayed.
Creating a personal copy through MCP without a project copies the base recipe's
fixed values (standard-frame-rate bitrate for built-ins), not its adaptive rule.
An agent can preview an applied built-in through `get_export_options`, then
copy the desired portable values explicitly.

Resolution keeps the current height-based, aspect-preserving, downscale-only
contract. There is no orientation adaptation or forced 16:9 frame. Applying a
larger resolution or frame-rate target to a smaller project follows the project
instead. Resolution and frame-rate controls show the chosen output settings. Built-in
delivery recipes seed explicit bitrates for standard/high frame rates, reducing
the target when the output pixel count is lower. Personal recipes saved from
the dialog retain the chosen fixed rate (or existing quality heuristic).
Saving an applied built-in as a personal recipe captures the current resolved
parameters. Fractional project frame rates stay
fractional when following the project.

## Consequences

Version 1 preset entries are validated through the shared export validator.
Corrupt or unsupported entries are recovered independently; a missing/deleted
default falls back to match-project. Built-in IDs are reserved and read-only.
No project migration, new encoding pipeline, cloud sync or import/export format
is introduced.
