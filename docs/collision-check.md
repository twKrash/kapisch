# Public identifier collision check

Checked 2026-07-21 before publication. The selected identity set is display
name **KAPISCH**, repository **twKrash/kapisch**, plugin ID **kapisch**, skill
**$kapisch**, Python distribution **kapisch-validation**, and artifact
namespace **.kapisch/**.

| Ecosystem | Check | Outcome |
| --- | --- | --- |
| OpenAI/Codex plugins | Public search for `KAPISCH` and `kapisch` | No Codex plugin collision returned. |
| GitHub | GitHub Search API query `kapisch` | Returned four repositories: `twKrash/kapisch`, `kapische/kapische`, and two unrelated Kapischool repositories. The target repository name is already owned by this project. |
| PyPI | `https://pypi.org/pypi/kapisch-validation/json` | HTTP 404: the exact distribution name was unclaimed at the check time. |
| npm | `https://registry.npmjs.org/kapisch` | HTTP 404: the exact package name was unclaimed at the check time. |
| Adjacent coding tools | Public search for `KAPISCH` with Cursor, Claude Code, and GitHub Copilot | No workflow-plugin collision returned. |

The generic word/name is already used in unrelated products and people, so it is
not claimed as an exclusive trademark. The namespaced repository, plugin ID,
skill invocation, and distribution name are the collision-resistant public
identifiers. Re-run this check immediately before publication and record any
new result here rather than silently changing one identifier independently.
