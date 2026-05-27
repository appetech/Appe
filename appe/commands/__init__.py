"""
Bench commands & runtime patches for the `appe` app.

This module is auto-discovered by Frappe's bench command loader on every bench
invocation (it calls `importlib.import_module("appe.commands")`). We use that
hook to apply a runtime monkey-patch that fixes an upstream bug in
`frappe.installer.remove_app`.

------------------------------------------------------------------------------
Upstream bug (Frappe core)
------------------------------------------------------------------------------
`frappe/installer.py :: remove_app()` blocks uninstallation if the target app is
a dependency of any other installed app. The check (in the affected versions)
is:

    if hooks.required_apps and any(
        app_name in required_app for required_app in hooks.required_apps
    ):
        ...

`app_name in required_app` is a SUBSTRING match, not an equality check. So when
we try to uninstall `appe`, the loop iterates over installed apps and looks at
`hrms`'s required_apps which is `["frappe/erpnext"]`. The substring "appe"
appears inside "fr**appe**/erpnext", so the check spuriously returns True and
prints:

    App appe is a dependency of hrms. Uninstall hrms first.

...even though `hrms` does NOT actually require `appe`.

------------------------------------------------------------------------------
Fix
------------------------------------------------------------------------------
We rewrite `frappe.installer.remove_app` IN-PLACE by:
  1. Grabbing its source via `inspect.getsource`.
  2. Replacing the single buggy expression with an EXACT-match version that
     strips the optional `"org/"` prefix from each `required_apps` entry.
  3. Re-executing the patched source inside `frappe.installer`'s namespace so
     the fixed function literally replaces the original.

This approach is intentionally narrow: only the buggy expression is rewritten,
everything else (backups, hooks, doctype deletion, etc.) stays exactly as
Frappe ships it. If Frappe later fixes the bug upstream (or refactors the
function), the `.replace()` simply finds nothing and the patch becomes a no-op
-- safe by design.

Removing this patch later: delete this file (or `git rm` the commands folder),
restart bench, done.
"""

from __future__ import annotations

import inspect

import click

# The exact buggy line in Frappe core that we replace.
_BUGGY_EXPR = (
	"any(app_name in required_app for required_app in hooks.required_apps)"
)
_FIXED_EXPR = (
	'any(app_name == required_app.split("/")[-1] '
	"for required_app in hooks.required_apps)"
)


def _patch_frappe_remove_app() -> None:
	"""Monkey-patch `frappe.installer.remove_app` to use an exact dependency check."""
	try:
		import frappe.installer as _installer
	except Exception:
		# Frappe not importable (e.g. running outside a bench context). Skip silently.
		return

	original = getattr(_installer, "remove_app", None)
	if original is None or getattr(original, "_appe_dependency_patch", False):
		return

	try:
		source = inspect.getsource(original)
	except (OSError, TypeError):
		return

	if _BUGGY_EXPR not in source:
		# Frappe already fixed it upstream, or signature/body changed. Don't touch it.
		return

	patched_source = source.replace(_BUGGY_EXPR, _FIXED_EXPR)

	try:
		exec(compile(patched_source, _installer.__file__, "exec"), _installer.__dict__)
	except Exception as exc:
		click.secho(
			f"[appe] Warning: failed to apply remove_app() dependency-check patch: {exc}",
			fg="yellow",
		)
		return

	patched = _installer.__dict__.get("remove_app")
	if patched is not None:
		patched._appe_dependency_patch = True


_patch_frappe_remove_app()

commands: list = []
