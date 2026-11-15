Resolve every conflicted file keeping both sides' intent; leave unconflicted files untouched. Never
delete what one side added just to apply: only genuinely incompatible changes supersede, and then
name which and why. In `AGENTS.md` and `CLAUDE.md`, resolve the conflicts and change nothing else.

Then find what git did not flag. `oldHead` and `newBase` come with the task; without them, after
`git fetch`, `oldHead=$(git rev-parse HEAD)` and `newBase=origin/<base>`:

    oldBase=$(git merge-base "$newBase" "$oldHead")
    git range-diff "$oldBase".."$oldHead" "$newBase"..HEAD
    git diff "$oldBase" "$newBase" -- $(git diff --name-only "$newBase" HEAD)

A symbol this branch still uses that upstream renamed or removed, a changed signature, logic
upstream now also does, a colliding migration or config key: each is a finding to fix, not a rebase
artifact.

When both sides changed the same logic incompatibly and the task does not decide it, `git rebase
--abort` and report the question. Never invent intent.
