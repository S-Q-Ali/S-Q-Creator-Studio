"""What a page can see about the browser the app opens.

Measured on Chrome 156, 2026-10-29:

* Playwright's own launch leaves ``navigator.webdriver`` true. That is the one
  tell a page can read without guessing, and it is what a platform's bot check
  looks at first.
* Playwright does **not** leak the CDP debugger: the ``console.debug`` stack
  probe stays silent. So no patched Playwright is needed.
* ``navigator.languages`` came back with a single language where a real
  Chrome lists several.

The init script below fixes exactly those two, and the launch flags stop
Chrome from advertising that it was started for automation. Nothing else is
faked: a page that reports the machine's real GPU, its real screen and its
real plugins looks like the same browser a person uses.
"""

from __future__ import annotations

#: The flags Chrome is started with. ``AutomationControlled`` is what sets
#: ``navigator.webdriver``; the rest keep a first run from opening a welcome
#: tab or an infobar over the page.
STEALTH_ARGS: tuple[str, ...] = (
    "--disable-blink-features=AutomationControlled",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-infobars",
)

#: Patched into every page before the page's own scripts run. The languages
#: match the locale the browser session asks for.
STEALTH_INIT_JS = """
(() => {
  try {
    Object.defineProperty(Navigator.prototype, 'webdriver', {
      get: () => undefined,
      configurable: true,
    });
  } catch (e) {}
  try {
    Object.defineProperty(Navigator.prototype, 'languages', {
      get: () => ['en-US', 'en'],
      configurable: true,
    });
  } catch (e) {}
})();
"""


def harden(context) -> None:
    """Make the pages of this context look like a normal browser's.

    ``context`` is a Playwright browser context. The script is installed on
    the context, so it applies to every page the session opens, including the
    ones opened later.
    """
    context.add_init_script(STEALTH_INIT_JS)
