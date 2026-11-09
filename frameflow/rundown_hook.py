"""The Daily Habit's own rundown checks, loaded by the shorts-writer skill as its lint hook (research/rundown.json
lint_hook): the skill passes (script, input) and gets back the errors of show.project_lint."""
from frameflow import show


def lint(script, inp):
    if inp.get("slug"):
        show._SLUG["now"] = inp["slug"]   # the analogy catalogue the writer was given (it leaves out recent episodes)
    return show.project_lint(script, {"stories": [{"story": 0, "facts": inp["facts"]}]})
